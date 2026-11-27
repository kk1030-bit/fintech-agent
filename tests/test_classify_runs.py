"""Decisions 49-50: classify runs that did not succeed, and check each stop reason against the run log.

Offline: synthetic events and throwaway files only; never the formal database, the run log, the key or Gemini.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import classify_runs as cr  # noqa: E402
import formal_runs as fr  # noqa: E402

E = cr.Event


def call(role="researcher", n=1, finish="FinishReason.STOP"):
    return E(role, "model_call", None, {"call_number": n, "finish_reason": finish})


def tool(status="ok", role="researcher"):
    return E(role, "tool_call", "get_financial_snapshot", {"status": status})


def draft(status="draft", claims=2):
    return E("researcher", "draft", None, {"status": status, "claims": claims})


def review(final, critical=(), rnd=1):
    return E("reviewer", "review", None, {"round": rnd, "final_decision": final, "critical": list(critical)})


def facts(stop):
    return E("system", "stop_facts", None, {"stop_reason": stop})


def run(mode, status, stop, events, sends=None, **budget):
    sends = sends if sends is not None else [(e.role, "ok") for e in events if e.type == "model_call"]
    b = {"calls_used": len(sends), "tool_calls_used": 0, "tokens_observed": 9000, "supplement_rounds": 0,
         "active_seconds": 10.0, **budget}
    return cr.Run(f"R-{mode}", "CASE-X", mode, status, stop, b, events, sends)


# -- reading the log ----------------------------------------------------------------
def test_read_job_keeps_codes_and_drops_every_text_field(tmp_path):
    con = sqlite3.connect(tmp_path / "jobs.sqlite3")
    con.execute("create table job_events (job_id text, event_seq integer, created_at text, role text, event_type text, "
                "tool_name text, detail text)")
    con.execute("create table model_usage (usage_id integer primary key autoincrement, job_id text, role text, outcome text)")
    rows = [("researcher", "model_call", None, {"call_number": 1, "finish_reason": "FinishReason.STOP", "usage": {"x": 1}}),
            ("researcher", "tool_call", "search_evidence", {"status": "no_data", "reason": "原文片段", "obs_id": "obs-1"}),
            ("researcher", "draft_invalid", None, {"problems": ["主張文字"]}),
            ("researcher", "draft", None, {"status": "insufficient", "claims": 0, "decision_summary": "草稿摘要"}),
            ("system", "stop_facts", None, {"stop_reason": "researcher_insufficient", "facts": ["事實文字"]})]
    for i, (role, et, t, d) in enumerate(rows):
        con.execute("insert into job_events values ('j1', ?, '', ?, ?, ?, ?)", (i, role, et, t, json.dumps(d, ensure_ascii=False)))
    con.execute("insert into model_usage (job_id, role, outcome) values ('j1', 'researcher', 'ok')")
    events, sends = cr.read_job(con, "j1")
    assert [e.type for e in events] == ["model_call", "tool_call", "draft_invalid", "draft", "stop_facts"]
    assert events[1].d == {"status": "no_data"} and events[2].d == {} and events[3].d == {"status": "insufficient", "claims": 0}
    assert events[4].d == {"stop_reason": "researcher_insufficient"} and sends == [("researcher", "ok")]
    text = json.dumps([e.d for e in events], ensure_ascii=False)
    assert all(s not in text for s in ("原文片段", "主張文字", "草稿摘要", "事實文字", "usage"))


# -- classification (decision 49) -------------------------------------------------------
def test_succeeded_runs_are_not_classified():
    r = run("single", "succeeded", "draft_without_review", [call(), draft(), ])
    assert cr.classify(r) == ("成功", "")


def test_a_provider_error_on_the_last_send_is_an_execution_failure_whatever_the_stop_code():
    r = run("workflow", "insufficient_evidence", "reserved_for_review", [], sends=[("researcher", "error_503")])
    assert cr.classify(r) == ("執行失敗", "供應商錯誤")
    r = run("dual", "failed", "worker_error: 503 UNAVAILABLE", [call()], sends=[("researcher", "ok"), ("researcher", "error_504")])
    assert cr.classify(r) == ("執行失敗", "供應商錯誤")
    assert cr.classify(run("dual", "failed", "worker_error: KeyError", [call()])) == ("執行失敗", "其他")
    assert cr.classify(run("single", "timed_out", "active_time", [call()])) == ("執行失敗", "其他")


def test_a_last_output_that_failed_the_format_check_is_a_format_failure():
    invalid = E("researcher", "draft_invalid", None, {})
    cut = run("single", "insufficient_evidence", "researcher_insufficient",
              [call(finish="FinishReason.MAX_TOKENS"), invalid, draft("insufficient", 0), facts("researcher_insufficient")])
    assert cr.classify(cut) == ("格式失敗", "截斷")
    bad = run("single", "insufficient_evidence", "researcher_insufficient",
              [call(), invalid, draft("insufficient", 0), facts("researcher_insufficient")])
    assert cr.classify(bad) == ("格式失敗", "格式不符")
    fixed = run("single", "insufficient_evidence", "researcher_insufficient",   # 重送成功：照最後狀態分類
                [call(), invalid, call(n=2), draft("insufficient", 1), facts("researcher_insufficient")])
    assert cr.classify(fixed) == ("Researcher 判定不足", "")
    reviewer = run("dual", "insufficient_evidence", "review_insufficient",
                   [call(), draft(), call("reviewer", 2), E("reviewer", "review_invalid", None, {}),
                    review("insufficient"), facts("review_insufficient")])
    assert cr.classify(reviewer) == ("格式失敗", "格式不符")   # Reviewer 格式錯不算覆核擋下（B 11/18）


def test_truncation_counts_even_when_the_stop_code_says_researcher_insufficient():
    r = run("dual", "insufficient_evidence", "researcher_insufficient",
            [call(finish="FinishReason.MAX_TOKENS"), draft("insufficient", 0), facts("researcher_insufficient")])
    assert cr.classify(r) == ("格式失敗", "截斷")


def test_format_stop_codes():
    nodraft = run("single", "insufficient_evidence", "no_draft_on_final_turn",
                  [call(), E("researcher", "tools_refused", None, {}), facts("no_draft_on_final_turn")])
    assert cr.classify(nodraft) == ("格式失敗", "沒交")
    wf = run("workflow", "insufficient_evidence", "workflow_invalid_draft",
             [call(), E("researcher", "draft_invalid", None, {}), draft("insufficient", 0), facts("workflow_invalid_draft")])
    assert cr.classify(wf) == ("格式失敗", "格式不符")


def test_budget_review_and_researcher_stops():
    assert cr.classify(run("single", "insufficient_evidence", "call_limit", [call()])) == ("預算用盡", "call_limit")
    for stop in ("review_insufficient", "unresolved_critical", "supplement_limit"):
        r = run("dual", "insufficient_evidence", stop, [call(), draft(), call("reviewer", 2), review("revise")])
        assert cr.classify(r) == ("覆核擋下", "")
    plain = run("single", "insufficient_evidence", "researcher_insufficient",
                [call(), tool("no_data"), call(n=2), draft("insufficient", 0), facts("researcher_insufficient")])
    assert cr.classify(plain) == ("Researcher 判定不足", "")
    broken = run("single", "insufficient_evidence", "researcher_insufficient",
                 [call(), tool("tool_error"), call(n=2), draft("insufficient", 0), facts("researcher_insufficient")])
    assert cr.classify(broken) == ("Researcher 判定不足", "工具失敗後停止")
    assert cr.classify(run("single", "insufficient_evidence", "something_new", [call()])) == ("規則沒涵蓋", "something_new")
    assert cr.classify(None) == ("未執行", "")


def test_refine_review_blocks_with_adjudicated_labels():
    r = run("dual", "insufficient_evidence", "unresolved_critical",
            [call(), draft(), call("reviewer", 2), review("revise", ["c2"])])
    f = lambda cid, label, kind="fact": {"claim_id": cid, "kind": kind, "label": label}  # noqa: E731
    assert cr.refine("覆核擋下", "", r, None, None, None)[0] == "待裁決標註"
    assert cr.refine("覆核擋下", "", r, [f("c1", "unknown", "inference")], None, None)[0] == "無法判斷（沒有事實主張）"
    assert cr.refine("覆核擋下", "", r, [f("c1", "supported"), f("c2", "supported")], None, None)[0] == "可能誤擋"
    assert cr.refine("覆核擋下", "", r, [f("c1", "supported"), f("c2", "unknown")], None, None)[0] == "擋得對"
    assert cr.refine("覆核擋下", "", r, [f("c1", "unsupported"), f("c2", "supported")], None, None)[0] == "無法判斷（指到別條）"


def test_refine_researcher_insufficient_with_allow_insufficient_and_the_gap_label():
    r = run("single", "insufficient_evidence", "researcher_insufficient", [])
    assert cr.refine("Researcher 判定不足", "", r, None, None, False) == ("該答未答", "")
    assert cr.refine("Researcher 判定不足", "", r, None, True, True) == ("合理拒答", "")
    assert cr.refine("Researcher 判定不足", "", r, None, False, True) == ("沒說明缺口", "")
    assert cr.refine("Researcher 判定不足", "", r, None, None, True)[0] == "待裁決標註"
    assert cr.refine("Researcher 判定不足", "工具失敗後停止", r, None, True, True) == ("工具失敗後停止", "")


# -- stop reason against the log (decision 50) ---------------------------------------------
def test_consistent_stop_reasons():
    cases = [
        run("dual", "succeeded", "review_pass", [call(), draft(), call("reviewer", 2), review("pass")]),
        run("single", "succeeded", "draft_without_review", [call(), draft()]),
        run("workflow", "succeeded", "workflow_draft_without_review", [tool(), call(), draft()]),
        run("dual", "insufficient_evidence", "review_insufficient",
            [call(), draft(), call("reviewer", 2), review("insufficient"), facts("review_insufficient")]),
        run("dual", "insufficient_evidence", "unresolved_critical",
            [call(), draft(), call("reviewer", 2), review("revise"), facts("unresolved_critical")], supplement_rounds=2),
        run("single", "insufficient_evidence", "researcher_insufficient",
            [call(), draft("insufficient", 0), facts("researcher_insufficient")]),
        run("workflow", "insufficient_evidence", "reserved_for_review", [], sends=[("researcher", "error_503")]),
        run("single", "insufficient_evidence", "call_limit", [call(n=i) for i in range(1, 9)]),
        run("dual", "failed", "worker_error: 503", [E("researcher", "model_error", None, {"code": 503})],
            sends=[("researcher", "error_503")]),
    ]
    for r in cases:
        assert cr.check_stop(r) == ("一致", []), r.stop_reason


def test_inconsistent_stop_reasons_are_reported():
    pass_but_revise = run("dual", "succeeded", "review_pass", [call(), draft(), call("reviewer", 2), review("revise")])
    assert cr.check_stop(pass_but_revise)[0] == "不一致"
    wrong_mode = run("dual", "succeeded", "draft_without_review", [call(), draft()])
    assert any("模式" in x for x in cr.check_stop(wrong_mode)[1])
    miscount = run("single", "succeeded", "draft_without_review", [call(), draft()], calls_used=3)
    assert any("發送計數" in x for x in cr.check_stop(miscount)[1])
    rounds_left = run("dual", "insufficient_evidence", "unresolved_critical",
                      [call(), draft(), call("reviewer", 2), review("revise"), facts("unresolved_critical")])
    assert any("還有剩" in x for x in cr.check_stop(rounds_left)[1])
    other_facts = run("single", "insufficient_evidence", "researcher_insufficient",
                      [call(), draft("insufficient", 0), facts("review_insufficient")])
    assert any("stop_facts" in x for x in cr.check_stop(other_facts)[1])
    early = run("single", "insufficient_evidence", "call_limit", [call()])
    assert cr.check_stop(early)[0] == "不一致"
    assert cr.check_stop(run("single", "insufficient_evidence", "input_too_large", [call()]))[0] == "無法核對"
    assert cr.check_stop(run("single", "runner_error", "RuntimeError", []))[0] == "無法核對"


# -- the formal run: gate, latest attempt, labels, output ---------------------------------
def _db(path: Path, jobs: dict[str, tuple[list[tuple], list[tuple]]]) -> None:
    con = sqlite3.connect(path)
    con.execute("create table job_events (job_id text, event_seq integer, created_at text, role text, event_type text, "
                "tool_name text, detail text)")
    con.execute("create table model_usage (usage_id integer primary key autoincrement, job_id text, role text, outcome text)")
    con.execute("create table research_jobs (job_id text, idempotency_key text, status text, data text)")
    for job, (events, sends) in jobs.items():
        for i, (role, et, d) in enumerate(events):
            con.execute("insert into job_events values (?, ?, '', ?, ?, NULL, ?)", (job, i, role, et, json.dumps(d)))
        for role, outcome in sends:
            con.execute("insert into model_usage (job_id, role, outcome) values (?, ?, ?)", (job, role, outcome))
    con.execute("insert into research_jobs values ('j9', 'CASE-C-single-formal-v2', 'paused_quota', '{}')")
    con.commit()
    con.close()


@pytest.fixture
def formal(tmp_path, monkeypatch):
    plan = {"experiment": fr.EXPERIMENT, "runs": [
        {"seq": 1, "run_id": "formal-v2-CASE-A-dual", "case_id": "CASE-A", "mode": "dual"},
        {"seq": 2, "run_id": "formal-v2-CASE-B-workflow", "case_id": "CASE-B", "mode": "workflow"},
        {"seq": 3, "run_id": "formal-v2-CASE-C-single", "case_id": "CASE-C", "mode": "single"}]}
    (tmp_path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    b = lambda n, rounds=0: {"calls_used": n, "tool_calls_used": 1, "tokens_observed": 9000,  # noqa: E731
                             "supplement_rounds": rounds, "active_seconds": 5.0}
    rows = [{"run_id": "formal-v2-CASE-A-dual", "job_id": "j1", "status": "insufficient_evidence",
             "stop_reason": "unresolved_critical", "budget": b(5, 2)},
            {"run_id": "formal-v2-CASE-B-workflow", "job_id": "j2", "status": "insufficient_evidence",
             "stop_reason": "reserved_for_review", "budget": b(1)},
            {"run_id": "formal-v2-CASE-B-workflow-r1", "job_id": "j3", "status": "succeeded",
             "stop_reason": "workflow_draft_without_review", "budget": b(1), "rerun_of": "formal-v2-CASE-B-workflow",
             "attempt": 1}]
    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    ok = lambda role: [(role, "ok")]  # noqa: E731
    _db(tmp_path / "jobs.sqlite3", {
        "j1": ([("researcher", "model_call", {"call_number": 1, "finish_reason": "FinishReason.STOP"}),
                ("researcher", "draft", {"status": "draft", "claims": 2}),
                ("reviewer", "model_call", {"call_number": 2, "finish_reason": "FinishReason.STOP"}),
                ("reviewer", "review", {"round": 1, "final_decision": "revise", "critical": ["c2"]}),
                ("system", "stop_facts", {"stop_reason": "unresolved_critical"})],
               [("researcher", "ok"), ("reviewer", "ok"), ("researcher", "ok"), ("researcher", "ok"), ("reviewer", "ok")]),
        "j2": ([("researcher", "model_error", {"call_number": 1, "code": 503})], [("researcher", "error_503")]),
        "j3": ([("researcher", "tool_call", {"status": "ok"}),
                ("researcher", "model_call", {"call_number": 1, "finish_reason": "FinishReason.STOP"}),
                ("researcher", "draft", {"status": "draft", "claims": 1})], ok("researcher"))})
    scoring = tmp_path / "scoring"
    scoring.mkdir()
    monkeypatch.setattr(fr, "PLAN", tmp_path / "plan.json")
    monkeypatch.setattr(fr, "RUNS", tmp_path / "runs.jsonl")
    monkeypatch.setattr(fr, "DB", tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(fr, "SEALED", tmp_path / "sealed.json")
    monkeypatch.setattr(cr, "SCORING", scoring)
    monkeypatch.setattr(cr, "OUT_CSV", tmp_path / "classification.csv")
    monkeypatch.setattr(cr, "OUT_MD", tmp_path / "classification.md")
    return tmp_path, scoring


def _reveal(scoring: Path) -> None:
    key = {"key": [{"answer_id": "A-1", "run_id": "formal-v2-CASE-A-dual", "mode": "dual", "rerun_of": None},
                   {"answer_id": "A-2", "run_id": "formal-v2-CASE-B-workflow-r1", "mode": "workflow",
                    "rerun_of": "formal-v2-CASE-B-workflow"}]}
    (scoring / "key.json").write_text(json.dumps(key), encoding="utf-8")


def _read(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return {r["run_id"]: r for r in csv.DictReader(f)}


def test_formal_refuses_before_the_reveal(formal):
    tmp, _ = formal
    with pytest.raises(SystemExit):
        cr.main(["--formal"])
    assert not (tmp / "classification.csv").exists()


def test_formal_uses_the_latest_attempt_and_lists_the_rerun(formal):
    tmp, scoring = formal
    _reveal(scoring)
    assert cr.main(["--formal"]) == 0
    rows = _read(tmp / "classification.csv")
    a, b, c = rows["formal-v2-CASE-A-dual"], rows["formal-v2-CASE-B-workflow"], rows["formal-v2-CASE-C-single"]
    assert (a["category"], a["subcategory"], a["stop_check"]) == ("覆核擋下", "待裁決標註", "一致")
    assert (b["category"], b["attempts"], b["stop_check"]) == ("成功", "2", "一致")
    assert (c["category"], c["note"]) == ("未執行", "已開始、暫停")
    md = (tmp / "classification.md").read_text(encoding="utf-8")
    assert "重跑的 run：1 個；重跑總次數：1 次" in md and "insufficient_evidence reserved_for_review" in md
    assert "| 覆核擋下 | 待裁決標註 | 0／1 | 1／1 | 0／1 |" in md


def test_formal_with_adjudicated_labels_fills_the_subcategories(formal):
    tmp, scoring = formal
    _reveal(scoring)
    (tmp / "sealed.json").write_text(json.dumps({"cases": [{"case_id": c, "allow_insufficient": True}
                                                           for c in ("CASE-A", "CASE-B", "CASE-C")]}), encoding="utf-8")
    (tmp / "claims.csv").write_text("answer_id,claim_id,kind,label\nA-1,c1,fact,supported\nA-1,c2,fact,unsupported\n",
                                    encoding="utf-8")
    (tmp / "refusals.csv").write_text("answer_id,explained_gap\nA-1,否\n", encoding="utf-8")
    assert cr.main(["--formal", "--claims", str(tmp / "claims.csv"), "--refusals", str(tmp / "refusals.csv")]) == 0
    assert _read(tmp / "classification.csv")["formal-v2-CASE-A-dual"]["subcategory"] == "擋得對"


def test_labels_for_an_unknown_answer_stop(formal):
    tmp, scoring = formal
    _reveal(scoring)
    (tmp / "sealed.json").write_text(json.dumps({"cases": []}), encoding="utf-8")
    (tmp / "claims.csv").write_text("answer_id,claim_id,kind,label\nA-9,c1,fact,supported\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        cr.main(["--formal", "--claims", str(tmp / "claims.csv")])
