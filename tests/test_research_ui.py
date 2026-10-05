"""A's research workspace UI (W02-A, W03-A, W04-A). Offline, no network, no LLM."""

from __future__ import annotations

import json

import pytest
from flask import Flask

from conftest import ROOT
from research_ui import bp

STATIC_JS = (ROOT / "static" / "research.js").read_text(encoding="utf-8")


def make_app(tmp_path, clock=None, mock=True):
    app = Flask(__name__, root_path=str(ROOT), template_folder="templates", static_folder="static")
    app.add_url_rule("/", "index", lambda: "home")
    app.config.update(RESEARCH_UI_MOCK=mock, RESEARCH_UI_MOCK_DB=str(tmp_path / "ui.sqlite3"), RESEARCH_UI_CLOCK=clock)
    app.register_blueprint(bp)
    return app


@pytest.fixture
def ui(tmp_path, clock):
    return make_app(tmp_path, clock).test_client()


def create(client, **overrides):
    payload = {"ticker": "2454", "cutoff_at": "2026-09-30T17:00:00+08:00", "mode": "dual",
               "scenario": "succeeded", "idempotency_key": "ui-test-1"}
    payload.update(overrides)
    return client.post("/api/ui/mock/jobs", json=payload)


# ----- W02: page, safety, favourites/published -------------------------------------
def test_page_renders_without_secrets_or_sync_analysis(ui, monkeypatch):
    monkeypatch.setenv("RESEARCH_API_TOKEN", "super-secret-token")
    monkeypatch.setenv("SUPABASE_KEY", "supabase-secret")
    html = ui.get("/research").get_data(as_text=True)
    assert "研究工作台" in html
    for text in (html, STATIC_JS):
        assert "super-secret-token" not in text and "supabase-secret" not in text
        assert "/api/analyze" not in text and "Authorization" not in text


def test_web_app_registers_workspace():
    import web_app

    rules = {r.rule for r in web_app.app.url_map.iter_rules()}
    assert {"/research", "/api/ui/published", "/api/ui/mock/jobs", "/api/ui/jobs/<job_id>"} <= rules


def test_published_list_hides_drafts_and_marks_fixture(ui):
    body = ui.get("/api/ui/published").get_json()
    ids = [r["report_version_id"] for r in body["reports"]]
    assert ids and all(r["publication_status"] == "published" for r in body["reports"])
    assert "rv-fixture-2454-0002-draft" not in ids
    assert body["synthetic_fixture"] is True and all(r["synthetic_fixture"] for r in body["reports"])


def test_reading_pages_never_starts_analysis(ui, monkeypatch):
    import web_app

    def boom(*_a, **_k):
        raise AssertionError("public read started a synchronous analysis")

    monkeypatch.setattr(web_app, "stock_payload", boom)
    for url in ("/research", "/api/ui/published", "/research?job=x"):
        assert ui.get(url).status_code == 200


def test_favourites_are_codes_only_and_capped():
    assert 'const FAV_MAX = 5;' in STATIC_JS
    assert '["2330", "2317", "2454", "2379", "3034"]' in STATIC_JS
    assert "localStorage.setItem(FAV_KEY, JSON.stringify(list.slice(0, FAV_MAX)))" in STATIC_JS


# ----- W02: MOCK entry ----------------------------------------------------------------
def test_entry_closed_when_mock_disabled(tmp_path):
    client = make_app(tmp_path, mock=False).test_client()
    assert create(client).status_code == 403
    assert client.get("/api/ui/jobs/x").status_code == 403
    assert "研究入口未啟用" in client.get("/research").get_data(as_text=True)


def test_repeated_click_returns_same_job(ui):
    first = create(ui)
    again = create(ui)
    assert first.status_code == 202 and again.status_code == 200
    assert first.get_json()["job"]["job_id"] == again.get_json()["job"]["job_id"]


def test_comparison_tickers_never_create_jobs(ui):
    for code in ("2379", "3034"):
        resp = create(ui, ticker=code, idempotency_key=f"ui-{code}")
        assert resp.status_code == 400 and "比較參照" in resp.get_json()["error"]


def test_bad_requests_rejected(ui):
    assert create(ui, cutoff_at="", idempotency_key="k2").status_code == 400
    assert create(ui, scenario="hack", idempotency_key="k3").status_code == 400
    assert create(ui).status_code == 202
    assert create(ui, ticker="2330").status_code == 409  # same key, different content


def test_job_survives_restart(tmp_path, clock):
    job_id = create(make_app(tmp_path, clock).test_client()).get_json()["job"]["job_id"]
    reopened = make_app(tmp_path, clock).test_client()  # new app, same DB file
    assert reopened.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["job_id"] == job_id


def test_succeeded_path_progresses_from_db(ui, clock):
    job_id = create(ui).get_json()["job"]["job_id"]
    statuses = []
    for _ in range(12):
        statuses.append(ui.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["status"])
        clock.advance(2)
    assert statuses[0] == "running" and statuses[-1] == "succeeded"
    assert "succeeded" not in statuses[:2]  # pending does not pose as complete


def test_insufficient_path(ui, clock):
    job_id = create(ui, ticker="2317", scenario="insufficient_evidence", idempotency_key="k-ins").get_json()["job"]["job_id"]
    for _ in range(8):
        body = ui.get(f"/api/ui/jobs/{job_id}").get_json()
        clock.advance(2)
    assert body["job"]["status"] == "insufficient_evidence"
    assert body["job"]["stop_reason"]


def test_events_expose_only_whitelisted_fields(ui, clock):
    job_id = create(ui).get_json()["job"]["job_id"]
    for _ in range(10):
        body = ui.get(f"/api/ui/jobs/{job_id}").get_json()
        clock.advance(2)
    allowed = {"mock", "summary", "decision_summary", "evidence_refs", "latency_ms", "tool_status", "args_redacted",
               "output_hash", "claim_id", "severity", "required_evidence", "budget"}
    assert body["events"]
    for event in body["events"]:
        assert set(event["detail"]) <= allowed
        assert event["detail"].get("mock") is True or event["event_type"] in ("job_created", "lease_acquired", "lease_recovered")
    assert "idempotency_key" not in json.dumps(body["job"])


# ----- W03: real job states, trace, cancel ------------------------------------------
def run_until_done(client, clock, job_id, polls=20):
    body = None
    for _ in range(polls):
        body = client.get(f"/api/ui/jobs/{job_id}").get_json()
        if body["job"]["status"] not in ("queued", "running"):
            break
        clock.advance(2)
    return body


@pytest.mark.parametrize("scenario,ticker,final", [
    ("succeeded", "2454", "succeeded"),
    ("insufficient_evidence", "2317", "insufficient_evidence"),
    ("paused_quota", "2330", "paused_quota"),
    ("failed", "2454", "failed"),
    ("timed_out", "2454", "timed_out"),
])
def test_each_status_screen_reaches_its_state(ui, clock, scenario, ticker, final):
    job_id = create(ui, ticker=ticker, scenario=scenario, idempotency_key=f"k-{scenario}").get_json()["job"]["job_id"]
    body = run_until_done(ui, clock, job_id)
    assert body["job"]["status"] == final
    assert body["job"]["stop_reason"]
    if final == "paused_quota":
        assert body["job"]["calls_used"] == 2  # accumulated budget kept, not reset
        clock.advance(600)
        assert ui.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["status"] == "paused_quota"  # no silent retry


def test_trace_shows_real_tool_results_and_source_ids(ui, clock):
    job_id = create(ui).get_json()["job"]["job_id"]
    events = run_until_done(ui, clock, job_id)["events"]
    tools = [e for e in events if e["tool_name"]]
    assert {e["tool_name"] for e in tools} == {"search_evidence", "read_evidence", "get_financial_snapshot"}
    read = next(e for e in tools if e["tool_name"] == "read_evidence")
    assert read["detail"]["tool_status"] == "ok" and read["detail"]["evidence_refs"] == ["ev-2454-2026q2-01"]
    assert {e["role"] for e in tools} == {"researcher", "reviewer"}
    for e in tools:
        assert e["created_at"] and e["detail"]["output_hash"] and "latency_ms" in e["detail"]
        assert e["detail"]["args_redacted"].get("cutoff", "<job.cutoff_at>") == "<job.cutoff_at>"


def test_missing_data_is_no_data_not_zero(ui, clock):
    job_id = create(ui, ticker="2317", scenario="insufficient_evidence", idempotency_key="k-2317").get_json()["job"]["job_id"]
    events = run_until_done(ui, clock, job_id)["events"]
    statuses = [e["detail"]["tool_status"] for e in events if e["tool_name"]]
    assert statuses == ["no_data", "no_data"]


def test_second_job_waits_in_queue(ui, clock):
    first = create(ui).get_json()["job"]["job_id"]
    second = create(ui, ticker="2330", idempotency_key="k-second").get_json()["job"]["job_id"]
    ui.get(f"/api/ui/jobs/{first}")
    queued = ui.get(f"/api/ui/jobs/{second}").get_json()["job"]
    assert queued["status"] == "queued" and queued["queue_ahead"] == 1


def test_cancel_running_job_only(ui, clock):
    job_id = create(ui).get_json()["job"]["job_id"]
    ui.get(f"/api/ui/jobs/{job_id}")
    resp = ui.post(f"/api/ui/mock/jobs/{job_id}/cancel")
    assert resp.status_code == 200 and resp.get_json()["job"]["status"] == "cancelled"
    assert ui.post(f"/api/ui/mock/jobs/{job_id}/cancel").status_code == 409
    clock.advance(30)
    assert ui.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["status"] == "cancelled"  # stays cancelled
    assert ui.post("/api/ui/mock/jobs/nope/cancel").status_code == 404


def test_status_is_read_from_db_by_another_process(tmp_path, clock):
    writer = make_app(tmp_path, clock).test_client()
    job_id = create(writer).get_json()["job"]["job_id"]
    run_until_done(writer, clock, job_id)
    reader = make_app(tmp_path, clock).test_client()  # separate app, same DB file
    assert reader.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["status"] == "succeeded"
