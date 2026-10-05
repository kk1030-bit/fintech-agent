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
