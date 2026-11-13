"""11/13（決策 31）：focus 改送 task；task_input、draft_under_review 以同名欄位原樣進三種模式與 Reviewer 的輸入。合成資料。"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agents.snapshot as snapshot  # noqa: E402
import dev_traces  # noqa: E402
from agents.budget import ProjectQuota  # noqa: E402
from agents.contract import validate_job_request  # noqa: E402
from agents.research_graph import CASE_INPUT_FIELDS, make_research_handler  # noqa: E402
from agents.worker import run_once  # noqa: E402
from conftest import job_request  # noqa: E402
from test_provider_mock import MODEL, FakeClient, text_response  # noqa: E402

QUOTA = ProjectQuota(model_id=MODEL, rpm=1000, tpm=10**7, rpd=100000)
FIX = Path(__file__).parent / "fixtures" / "agent_case_fixtures.json"
TASK_INPUT = {"note": "SYNTHETIC-TASK-INPUT", "price": 123.0}
UNDER_REVIEW = {"claims": [{"claim_id": "x1", "text": "SYNTHETIC-DRAFT-UNDER-REVIEW"}]}
INSUFFICIENT = json.dumps({"status": "insufficient", "decision_summary": "s", "claims": [], "conflicts": [],
                           "limitations": [], "unknowns": []}, ensure_ascii=False)
DRAFT = json.dumps({"status": "draft", "decision_summary": "s", "conflicts": [], "limitations": [], "unknowns": [],
                    "claims": [{"claim_id": "c1", "kind": "unknown", "text": "x", "evidence_refs": [], "limitations": []}]},
                   ensure_ascii=False)
PASS = json.dumps({"decision": "pass", "issues": [], "checked_refs": [], "checked_metric_ids": [], "decision_summary": "s"})


@pytest.fixture
def fixtures(tmp_path, monkeypatch):
    def use(extra: dict):
        data = json.loads(FIX.read_text(encoding="utf-8"))
        data["snapshots"]["snap-dev-case-01"].update(extra)
        path = tmp_path / "fx.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(snapshot, "DEV_FIXTURES", path)
    use({})
    return use


def sent(store, mode, script):
    req = validate_job_request(job_request(idempotency_key=f"ti-{mode}", mode=mode, ticker="2330",
                                           cutoff_at="2026-07-20T17:00:00+08:00", source_snapshot_id="snap-dev-case-01",
                                           focus="題目原樣"))
    store.create_job(req, MODEL)
    client = FakeClient(script)
    run_once(store, "w1", make_research_handler(client, MODEL, QUOTA, sleep=lambda s: None))
    return ["".join(p.text or "" for c in call["contents"] for p in c.parts) for call in client.calls]


def trusted(text: str) -> dict:
    return json.loads(text.split("可信輸入：", 1)[1].split("\n")[0]) if "可信輸入：" in text else {}


@pytest.mark.parametrize("mode", ["single", "dual", "workflow"])
def test_fields_reach_the_researcher_under_their_own_names(store, fixtures, mode):
    fixtures({"task_input": TASK_INPUT, "draft_under_review": UNDER_REVIEW, "required_elements": ["SCORER-ONLY"]})
    first = sent(store, mode, [text_response(INSUFFICIENT)])[0]
    assert json.dumps(TASK_INPUT, ensure_ascii=False) in first and json.dumps(UNDER_REVIEW, ensure_ascii=False) in first
    assert '"task_input"' in first and '"draft_under_review"' in first and "題目原樣" in first
    assert "SCORER-ONLY" not in first and "required_elements" not in first  # 只給評分者


def test_fields_reach_the_reviewer_in_dual(store, fixtures):
    fixtures({"task_input": TASK_INPUT, "draft_under_review": UNDER_REVIEW})
    texts = sent(store, "dual", [text_response(DRAFT), text_response(PASS)])
    assert len(texts) == 2
    assert json.dumps(TASK_INPUT, ensure_ascii=False) in texts[1] and json.dumps(UNDER_REVIEW, ensure_ascii=False) in texts[1]


@pytest.mark.parametrize("mode", ["single", "dual", "workflow"])
def test_snapshot_without_the_fields_adds_nothing(store, fixtures, mode):
    first = sent(store, mode, [text_response(INSUFFICIENT)])[0]
    assert not any(k in first for k in CASE_INPUT_FIELDS)


def test_focus_is_the_task_unchanged_and_variant_only_without_one():
    assert dev_traces.focus_for({"task": " 原樣 題目？", "variant": "標籤", "title": "標題"}) == (" 原樣 題目？", "task")
    assert dev_traces.focus_for({"variant": "標籤"}) == ("標籤", "variant")


def test_dev_tasks_file_is_read_in_preference(tmp_path, monkeypatch):
    path = tmp_path / "dev-tasks.json"
    path.write_text(json.dumps({"tasks": [{"case_id": "CASE-01", "task": "合成題目"}]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(dev_traces, "DEV_TASKS", path)
    cases = dev_traces.load_cases()
    assert dev_traces.focus_for(cases["CASE-01"]) == ("合成題目", "task")
    assert dev_traces.focus_for(cases["CASE-04"])[1] == "variant"
