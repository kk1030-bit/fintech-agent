"""Decision 47 (lead 11/21): a run that ended on a provider error gets one rerun.

Offline: synthetic rows and a throwaway SQLite file only; never the formal database, the run log or Gemini.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import formal_reruns as frr  # noqa: E402
import formal_runs as fr  # noqa: E402


def _ledger(path: Path, sends: dict[str, list[str]]) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("create table model_usage (usage_id integer primary key autoincrement, job_id text, outcome text)")
    for job_id, outcomes in sends.items():
        for o in outcomes:
            con.execute("insert into model_usage (job_id, outcome) values (?, ?)", (job_id, o))
    con.commit()
    return con


def _plan(n: int) -> dict:
    return {"experiment": fr.EXPERIMENT, "runs": [
        {"seq": i, "run_id": f"{fr.EXPERIMENT}-CASE-X{i}-dual", "case_id": f"CASE-X{i}", "mode": "dual"}
        for i in range(1, n + 1)]}


def test_provider_error_codes():
    assert frr.provider_error("error_503") and frr.provider_error("error_500") and frr.provider_error("error_408")
    for outcome in ("ok", "error_429", "error_unknown", "error_", None, ""):
        assert not frr.provider_error(outcome)


def test_only_runs_that_ended_on_a_provider_error_are_eligible(tmp_path):
    plan = _plan(8)
    rid = [r["run_id"] for r in plan["runs"]]
    done = {
        rid[0]: {"run_id": rid[0], "job_id": "j1", "status": "insufficient_evidence"},  # last send 503
        rid[1]: {"run_id": rid[1], "job_id": "j2", "status": "insufficient_evidence"},  # 503, then the retry finished it
        rid[2]: {"run_id": rid[2], "job_id": "j3", "status": "failed"},                 # already rerun once
        rid[2] + "-r1": {"run_id": rid[2] + "-r1", "job_id": "j3r", "status": "failed", "rerun_of": rid[2]},
        rid[3]: {"run_id": rid[3], "job_id": "j4", "status": "succeeded"},
        rid[4]: {"run_id": rid[4], "job_id": "j5", "status": "insufficient_evidence"},  # 429 is quota, not a provider failure
        rid[5]: {"run_id": rid[5], "job_id": "j6", "status": "failed"},                 # unknown error: not the provider's
        rid[6]: {"run_id": rid[6], "job_id": "j7", "status": "failed"},                 # timeout / transport error (408)
    }                                                                                    # rid[7]: not run yet
    con = _ledger(tmp_path / "jobs.sqlite3", {
        "j1": ["ok", "error_503"], "j2": ["error_503", "ok"], "j3": ["error_503"], "j3r": ["error_503"],
        "j4": ["ok"], "j5": ["error_429"], "j6": ["error_unknown"], "j7": ["ok", "error_408", "error_408"]})
    assert [(p["run_id"], last) for p, _, last in frr.eligible(plan, done, con)] == [(rid[0], "error_503"), (rid[6], "error_408")]


def test_a_database_without_the_send_ledger_has_nothing_to_rerun(tmp_path):
    con = sqlite3.connect(tmp_path / "jobs.sqlite3")
    con.execute("create table research_jobs (job_id text, data text)")
    plan = _plan(1)
    done = {plan["runs"][0]["run_id"]: {"run_id": plan["runs"][0]["run_id"], "job_id": "j1", "status": "failed"}}
    assert frr.eligible(plan, done, con) == []


def test_rerun_row_keeps_the_original_and_names_the_rule():
    p = {"seq": 22, "run_id": f"{fr.EXPERIMENT}-CASE-X-dual", "case_id": "CASE-X", "mode": "dual"}
    result = {"job_id": "j-new", "status": "succeeded", "stop_reason": "review_pass", "budget": {}, "steps": []}
    row = frr.rerun_row(p, {"job_id": "j-orig"}, "error_503", result, "m", "abc1234", "2026-11-26T11:30:00+00:00")
    assert row["run_id"] == p["run_id"] + "-r1" and row["rerun_of"] == p["run_id"] and row["rerun_of_job_id"] == "j-orig"
    assert row["seq"] == 22 and row["mode"] == "dual" and row["experiment"] == fr.EXPERIMENT and row["job_id"] == "j-new"
    assert row["rerun_reason"] == "provider_error:error_503" and row["rule"] == "decision 47"


def test_analysis_uses_the_rerun_row_when_there_is_one():
    done = {"r": {"run_id": "r", "status": "failed"}, "r-r1": {"run_id": "r-r1", "status": "succeeded", "rerun_of": "r"},
            "s": {"run_id": "s", "status": "succeeded"}}
    assert frr.analysis_row(done, "r")["run_id"] == "r-r1"
    assert frr.analysis_row(done, "s")["run_id"] == "s"


@pytest.fixture
def env(tmp_path, monkeypatch):
    plan = _plan(2)
    (tmp_path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(fr, "PLAN", tmp_path / "plan.json")
    monkeypatch.setattr(fr, "RUNS", tmp_path / "runs.jsonl")
    monkeypatch.setattr(fr, "DB", tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(fr, "lock_ok", lambda: pytest.fail("must stop before the strict check or any live call"))
    _ledger(tmp_path / "jobs.sqlite3", {"j1": ["error_503"], "j2": ["ok"]}).close()
    return tmp_path, plan


def test_live_refuses_until_every_planned_run_is_recorded(env, capsys):
    tmp, plan = env
    (tmp / "runs.jsonl").write_text(json.dumps({"run_id": plan["runs"][0]["run_id"], "job_id": "j1", "status": "failed"}) + "\n",
                                    encoding="utf-8")
    assert frr.main(["--live"]) == 1
    assert "未執行" in capsys.readouterr().out


def test_list_is_read_only(env, capsys):
    tmp, plan = env
    rows = [{"run_id": plan["runs"][0]["run_id"], "job_id": "j1", "status": "failed"},
            {"run_id": plan["runs"][1]["run_id"], "job_id": "j2", "status": "succeeded"}]
    text = "".join(json.dumps(r) + "\n" for r in rows)
    (tmp / "runs.jsonl").write_text(text, encoding="utf-8")
    assert frr.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "待重跑 1 個" in out and plan["runs"][0]["run_id"] in out and plan["runs"][1]["run_id"] not in out
    assert (tmp / "runs.jsonl").read_text(encoding="utf-8") == text
