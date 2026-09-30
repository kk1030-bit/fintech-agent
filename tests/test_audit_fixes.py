"""Regression tests for the 2026-09-30 audit findings that affect the final product."""

import httpx
import pytest
from flask import Flask
from google.genai import types

from agents.api import bp
from agents.budget import BudgetExceeded, BudgetGate, ProjectQuota
from agents.contract import ContractError, validate_job_request
from agents.provider import GeminiAdapter
from agents.store import LEASE_SECONDS, JobStore
from agents.tools import _REGISTRY, dispatch, register_tool
from agents.worker import run_once
from conftest import job_request
from test_provider_mock import MODEL, FakeClient, api_error, text_response

JOB_CUTOFF = "2026-09-30T13:30:00+08:00"


# ----- worker maps budget stops to the right status and can resume -----
def test_daily_quota_pauses_and_resumes_later(store, clock):
    job, _ = store.create_job(validate_job_request(job_request()), None)

    def quota_hit(lease):
        lease.save({"calls_used": 3})
        raise BudgetExceeded("daily_quota", "x", wait_seconds=3600)

    paused = run_once(store, "w1", quota_hit)
    assert paused["status"] == "paused_quota" and paused["stop_reason"] == "daily_quota"
    assert store.claim_next("w2") is None  # not before resume_after
    clock.advance(3601)
    resumed, _ = store.claim_next("w2")
    assert resumed["job_id"] == job["job_id"] and resumed["calls_used"] == 3  # budget not reset
    assert "resume_after" not in resumed


def test_quota_unknown_waits_for_manual_requeue(store, clock):
    job, _ = store.create_job(validate_job_request(job_request()), None)

    def unknown(lease):
        raise BudgetExceeded("quota_unknown", "x")

    assert run_once(store, "w1", unknown)["status"] == "paused_quota"
    clock.advance(10**6)
    assert store.claim_next("w1") is None
    store.requeue(job["job_id"])
    assert store.claim_next("w1")[0]["job_id"] == job["job_id"]


@pytest.mark.parametrize("reason,status", [("active_time", "timed_out"), ("call_limit", "insufficient_evidence")])
def test_budget_stop_is_not_reported_as_failed(store, reason, status):
    store.create_job(validate_job_request(job_request()), None)

    def stop(lease):
        raise BudgetExceeded(reason, "x")

    final = run_once(store, "w1", stop)
    assert final["status"] == status and final["stop_reason"] == reason and final["stage"] == "finished"


def test_expired_lease_on_final_save_does_not_crash_worker(store, clock):
    store.create_job(validate_job_request(job_request()), None)

    def slow(lease):
        clock.advance(LEASE_SECONDS + 1)
        return {"status": "succeeded", "stage": "finished"}

    assert run_once(store, "w1", slow) is None


# ----- idempotency -----
def test_same_key_different_payload_is_rejected(store):
    store.create_job(validate_job_request(job_request()), None)
    with pytest.raises(ContractError):
        store.create_job(validate_job_request(job_request(ticker="2454")), None)


def test_api_clean_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_DB_PATH", str(tmp_path / "api.sqlite3"))
    app = Flask(__name__)
    app.config["RESEARCH_API_TOKEN"] = "t"
    app.register_blueprint(bp)
    c = app.test_client()
    auth = {"Authorization": "Bearer t"}
    assert c.post("/api/research/jobs", json=[1], headers=auth).status_code == 400
    assert c.post("/api/research/jobs", json=job_request(), headers={"Authorization": "Bearer tést"}).status_code == 401
    assert c.post("/api/research/jobs", json=job_request(), headers=auth).status_code == 202
    assert c.post("/api/research/jobs", json=job_request(ticker="2454"), headers=auth).status_code == 409


# ----- tools: no look-ahead, no crashes -----
def test_tool_time_after_job_cutoff_is_refused():
    late = dispatch("researcher", "get_price_window",
                    {"ticker": "2330", "end_at": "2026-10-05T13:30:00+08:00", "sessions": 5}, job_cutoff=JOB_CUTOFF)
    assert late["status"] == "invalid_input" and "cutoff" in late["reason"]
    ok = dispatch("researcher", "get_price_window",
                  {"ticker": "2330", "end_at": "2026-09-30T13:30:00+08:00", "sessions": 5}, job_cutoff=JOB_CUTOFF)
    assert ok["status"] == "no_data"  # passed validation; no implementation registered yet
    naive = dispatch("researcher", "get_price_window", {"ticker": "2330", "end_at": "2026-09-30", "sessions": 5})
    assert naive["status"] == "invalid_input"


def test_peer_comparison_price_date_after_cutoff_and_bad_types():
    base = {"subject": "2454", "comparators": ["2379", "3034"], "price_as_of": "2026-10-01",
            "cutoff": JOB_CUTOFF, "snapshot_ids": {"2454": "s1", "2379": "s2", "3034": "s3"},
            "metrics": ["pe_ttm"], "method_version": "peer-v1"}
    late = dispatch("researcher", "calculate_metrics",
                    {"operation": "peer_comparison", "values": base, "evidence_refs": []}, job_cutoff=JOB_CUTOFF)
    assert late["status"] == "invalid_input"
    weird = dict(base, price_as_of="2026-09-30", comparators=[{"x": 1}])
    out = dispatch("researcher", "calculate_metrics",
                   {"operation": "peer_comparison", "values": weird, "evidence_refs": []}, job_cutoff=JOB_CUTOFF)
    assert out["status"] == "invalid_input"


def test_crashing_tool_returns_fixed_error():
    def boom(args):
        raise RuntimeError("db down")

    register_tool("read_evidence", boom)
    try:
        out = dispatch("reviewer", "read_evidence", {"evidence_version_id": "ev-1"})
        assert out["status"] == "tool_error" and "db down" in out["reason"] and out["data"] is None
        bad_id = dispatch("reviewer", "read_evidence", {"evidence_version_id": "../x"})
        assert bad_id["status"] == "invalid_input"
    finally:
        _REGISTRY.pop("read_evidence", None)


@pytest.mark.parametrize("query,blocked", [("select customers from US", False), ("R&D 支出與營收 / 淨利", False),
                                           ("www.evil.com", True), ("~/secrets", True), ("C:\\x", True),
                                           ("a && b", True), ("select * from t", True)])
def test_query_filter(query, blocked):
    out = dispatch("researcher", "search_evidence",
                   {"ticker": "2330", "query": query, "cutoff": JOB_CUTOFF, "limit": 3}, job_cutoff=JOB_CUTOFF)
    assert (out["status"] == "invalid_input") is blocked


# ----- provider: heartbeat, timeouts, long Retry-After -----
def _adapter(store, script):
    job, _ = store.create_job(validate_job_request(job_request()), MODEL)
    _, token = store.claim_next("w1")
    gate = BudgetGate(store=store, job=store.get_job(job["job_id"]),
                      persist=lambda ch: store.update_job(job["job_id"], "w1", token, ch),
                      quota=ProjectQuota(model_id=MODEL, rpm=100, tpm=10**6, rpd=1000))
    beats, sleeps = [], []
    adapter = GeminiAdapter(FakeClient(script), MODEL, gate, prompt_version="v1.2",
                            sleep=sleeps.append, heartbeat=lambda: beats.append(1))
    return adapter, beats, sleeps


X = [types.Content(role="user", parts=[types.Part.from_text(text="x")])]


def test_heartbeat_before_every_send(store):
    adapter, beats, _ = _adapter(store, [api_error(503), text_response("ok")])
    adapter.send("researcher", X, "sys")
    assert len(beats) >= 2  # one per HTTP send at least


def test_client_timeout_is_counted_and_retried_once(store):
    adapter, _, sleeps = _adapter(store, [httpx.ReadTimeout("slow"), text_response("ok")])
    adapter.send("researcher", X, "sys")
    job = store.get_job(adapter.job_id)
    assert job["calls_used"] == 2 and len(sleeps) == 1
    outcomes = [u["outcome"] for u in store.list_usage(adapter.job_id)]
    assert outcomes == ["error_408", "ok"]


def test_long_retry_after_pauses_instead_of_sleeping(store):
    class Resp:
        headers = {"retry-after": "120"}

    err = api_error(503)
    err.response = Resp()
    adapter, _, sleeps = _adapter(store, [err])
    with pytest.raises(BudgetExceeded) as exc:
        adapter.send("researcher", X, "sys")
    assert exc.value.job_status == "paused_quota" and sleeps == []


def test_active_time_overflow_after_send_still_settles_ledger(store):
    adapter, _, _ = _adapter(store, [text_response("ok", total=100)])
    adapter.gate.persist({"active_seconds": 179.0})
    adapter.gate.job = store.get_job(adapter.job_id)
    t = iter([0.0, 5.0])
    adapter.monotonic = lambda: next(t)
    with pytest.raises(BudgetExceeded):
        adapter.send("researcher", X, "sys")
    assert store.list_usage(adapter.job_id)[0]["outcome"] == "ok"
    assert [e["event_type"] for e in store.list_events(adapter.job_id)][-1] == "model_call"
