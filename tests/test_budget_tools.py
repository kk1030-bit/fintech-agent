"""W03-L: budget gate and six-tool contract (offline, no model calls)."""

import pytest

from agents.budget import BudgetExceeded, BudgetGate, ProjectQuota, daily_job_limit, estimate_tokens
from agents.contract import validate_job_request
from agents.tools import TOOL_NAMES, contract_document, dispatch, validate_tool_call, ToolInputError
from conftest import job_request

QUOTA = ProjectQuota(model_id="test-model", rpm=100, tpm=1_000_000, rpd=1000)


def make_gate(store, quota=QUOTA, stage="research"):
    job, _ = store.create_job(validate_job_request(job_request()), "test-model")
    _, token = store.claim_next("w1")
    if stage != "research":
        job = store.update_job(job["job_id"], "w1", token, {"stage": stage})

    def persist(changes):
        return store.update_job(job["job_id"], "w1", token, changes)

    return BudgetGate(store=store, job=store.get_job(job["job_id"]), persist=persist, quota=quota)


def test_daily_job_limit_formula():
    assert daily_job_limit(None) == 0
    assert daily_job_limit(20) == 2          # floor(16/8)
    assert daily_job_limit(1000) == 6        # capped at 6
    assert daily_job_limit(20, other_reserved=10) == 0


def test_unknown_quota_blocks_live_sends(store):
    gate = make_gate(store, quota=ProjectQuota())
    with pytest.raises(BudgetExceeded) as err:
        gate.reserve_call("reviewer", "hi", "h")
    assert err.value.reason == "quota_unknown" and err.value.job_status == "paused_quota"
    assert gate.job["calls_used"] == 0


def test_researcher_limited_to_four_initial_calls(store):
    gate = make_gate(store)
    for _ in range(4):
        gate.settle(gate.reserve_call("researcher", "x", "h"), "ok", 100)
    with pytest.raises(BudgetExceeded) as err:
        gate.reserve_call("researcher", "x", "h")
    assert err.value.reason == "reserved_for_review"
    gate.settle(gate.reserve_call("reviewer", "x", "h"), "ok", 100)  # 5th goes to review


def test_eight_call_cap_counts_failures_and_is_persisted(store):
    gate = make_gate(store, stage="revision")
    for i in range(8):
        res = gate.reserve_call("researcher" if i % 2 else "reviewer", "x", "h")
        gate.settle(res, "error_503" if i % 3 == 0 else "ok", None if i % 3 == 0 else 50)
    with pytest.raises(BudgetExceeded) as err:
        gate.reserve_call("reviewer", "x", "h")
    assert err.value.reason == "call_limit"
    assert store.get_job(gate.job["job_id"])["calls_used"] == 8
    assert len(store.list_usage(gate.job["job_id"])) == 8


def test_unknown_usage_keeps_reservation(store):
    gate = make_gate(store)
    res = gate.reserve_call("researcher", "x", "h")
    gate.settle(res, "error_timeout", None)
    assert gate.job["tokens_observed"] == res.reserved_tokens
    assert gate.job["tokens_reserved"] == 0


def test_input_and_job_token_limits(store):
    gate = make_gate(store)
    with pytest.raises(BudgetExceeded) as err:
        gate.reserve_call("researcher", "字" * 3001, "h")
    assert err.value.reason == "input_too_large"
    gate.persist({"tokens_observed": 39_000})
    gate.job = store.get_job(gate.job["job_id"])
    with pytest.raises(BudgetExceeded) as err:
        gate.reserve_call("researcher", "x", "h")
    assert err.value.reason == "token_limit"


def test_estimate_is_conservative_for_cjk_and_ascii():
    assert estimate_tokens("台積電") == 3
    assert estimate_tokens("abcd") == 2


def test_project_daily_quota_uses_80_percent(store):
    gate = make_gate(store, quota=ProjectQuota(model_id="test-model", rpm=100, tpm=10**6, rpd=5), stage="revision")
    for _ in range(4):  # floor(0.8*5) = 4
        gate.settle(gate.reserve_call("reviewer", "x", "h"), "ok", 10)
    with pytest.raises(BudgetExceeded) as err:
        gate.reserve_call("reviewer", "x", "h")
    assert err.value.reason == "daily_quota" and err.value.job_status == "paused_quota"


def test_rpm_headroom(store):
    gate = make_gate(store, quota=ProjectQuota(model_id="test-model", rpm=2, tpm=10**6, rpd=1000))
    gate.settle(gate.reserve_call("researcher", "x", "h"), "ok", 10)  # floor(0.8*2)=1
    with pytest.raises(BudgetExceeded) as err:
        gate.reserve_call("researcher", "x", "h")
    assert err.value.reason == "rate_limited"


def test_tool_limits(store):
    gate = make_gate(store)
    gate.register_tool_call("get_price_window", "a")
    gate.register_tool_call("get_price_window", "a")
    with pytest.raises(BudgetExceeded):
        gate.register_tool_call("get_price_window", "a")
    for i in range(8):
        gate.register_tool_call("read_evidence", f"id{i}")
    with pytest.raises(BudgetExceeded) as err:
        gate.register_tool_call("read_evidence", "id-new")
    assert err.value.reason == "tool_limit"


def test_supplement_rounds_and_active_time(store):
    gate = make_gate(store)
    gate.start_supplement_round()
    gate.start_supplement_round()
    with pytest.raises(BudgetExceeded):
        gate.start_supplement_round()
    gate.add_active_time(179)
    with pytest.raises(BudgetExceeded) as err:
        gate.add_active_time(2)
    assert err.value.job_status == "timed_out"


# ----- six-tool contract -------------------------------------------------
PEER_OK = {
    "subject": "2454", "comparators": ["2379", "3034", "2330"],
    "price_as_of": "2026-09-30", "cutoff": "2026-09-30T13:30:00+08:00",
    "snapshot_ids": {"2454": "s1", "2379": "s2", "3034": "s3", "2330": "s4"},
    "metrics": ["pe_ttm", "pb"], "method_version": "peer-v1",
}


def test_still_six_tools_and_peer_comparison_is_an_operation():
    doc = contract_document()
    assert doc["tool_count"] == 6 and "peer_comparison" not in TOOL_NAMES
    assert "peer_comparison" in doc["calculate_metrics_operations"]
    assert doc["peer_comparison"]["llm_jobs_for_comparators"] == 0


def test_peer_comparison_valid_input():
    validate_tool_call("researcher", "calculate_metrics",
                       {"operation": "peer_comparison", "values": PEER_OK, "evidence_refs": ["e1"]})


@pytest.mark.parametrize("patch,msg", [
    ({"comparators": ["2379", "3034", "2330", "2317"]}, "最多 4"),
    ({"subject": "2330"}, "主體"),
    ({"comparators": ["2317"]}, "比較標的"),
    ({"price_as_of": ""}, "price_as_of"),
    ({"metrics": ["buy_rating"]}, "metrics"),
    ({"comparators": ["2379", "2379"]}, "重複"),
])
def test_peer_comparison_rejections(patch, msg):
    values = {**PEER_OK, **patch}
    with pytest.raises(ToolInputError, match=msg):
        validate_tool_call("researcher", "calculate_metrics",
                           {"operation": "peer_comparison", "values": values, "evidence_refs": []})


def test_reviewer_cannot_search_or_fetch_prices():
    for name in ("search_evidence", "get_price_window"):
        with pytest.raises(ToolInputError, match="無權"):
            validate_tool_call("reviewer", name, {})


@pytest.mark.parametrize("query", ["https://evil.example/x", "../../etc/passwd", "1; DROP TABLE jobs",
                                   "select * from research_jobs"])
def test_no_url_path_or_sql(query):
    with pytest.raises(ToolInputError):
        validate_tool_call("researcher", "search_evidence",
                           {"ticker": "2330", "query": query, "cutoff": "2026-09-30T00:00:00+08:00", "limit": 3})


def test_unregistered_tool_returns_fixed_no_data():
    out = dispatch("researcher", "get_price_window",
                   {"ticker": "2330", "end_at": "2026-09-30T13:30:00+08:00", "sessions": 5})
    assert out == {"status": "no_data", "tool": "get_price_window", "reason": "工具實作待 W03-B 註冊", "data": None}
    bad = dispatch("researcher", "get_price_window", {"ticker": "2330", "end_at": "x", "sessions": 3})
    assert bad["status"] == "invalid_input" and bad["data"] is None
