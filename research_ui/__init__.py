"""V1.2 research workspace UI (A: W02–W04).

Routes
------
GET  /research                    workspace page (no job is created by opening it)
GET  /api/ui/published            published report metadata (read-only, 0 LLM)
POST /api/ui/mock/jobs            MOCK job create — only when RESEARCH_UI_MOCK=1
GET  /api/ui/jobs/<job_id>        MOCK job status + trace, read from the job DB

Rules from the handbook kept here:
* No API key or token is ever sent to the browser; the page cannot reach the
  real research API (authorisation is MOCK-only until 組長 decides).
* Public reads never start analysis: nothing here calls /api/analyze, FinMind,
  Supabase writes or Gemini.
* Only `publication_status == "published"` rows leave the server.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request

from agents.contract import COMPARISON_ONLY_TICKERS, RESEARCH_TICKERS, ContractError

from .mock_jobs import SCENARIOS, MockJobs

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT / "ui" / "v12-dashboard-fixture.json"

bp = Blueprint("research_ui", __name__)

PUBLISHED_FIELDS = (
    "report_version_id", "ticker", "company", "publication_status", "research_outcome", "cutoff_at",
    "financial_period", "published_at", "data_updated_at", "snapshot_stale", "valuation_status",
    "data_quality_risk", "data_quality_reason", "pdf_status", "synthetic_fixture",
)


def mock_enabled() -> bool:
    flag = current_app.config.get("RESEARCH_UI_MOCK")
    if flag is None:
        flag = os.getenv("RESEARCH_UI_MOCK") == "1"
    return bool(flag)


def get_mock() -> MockJobs:
    mock = current_app.extensions.get("research_ui_mock")
    if mock is None:
        path = current_app.config.get("RESEARCH_UI_MOCK_DB") or os.getenv("RESEARCH_UI_MOCK_DB") \
            or str(ROOT / "tmp" / "research_ui_mock.sqlite3")
        mock = MockJobs(path, ROOT, clock=current_app.config.get("RESEARCH_UI_CLOCK"))
        current_app.extensions["research_ui_mock"] = mock
    return mock


def load_fixture() -> dict[str, Any]:
    path = Path(current_app.config.get("RESEARCH_UI_FIXTURE") or FIXTURE_PATH)
    return json.loads(path.read_text(encoding="utf-8"))


def disabled():
    return jsonify({"ok": False, "error": "research_entry_disabled",
                    "message": "研究入口未啟用：目前只開放 MOCK 測試環境，正式授權由組長決定。"}), 403


@bp.get("/research")
def research_page():
    return render_template(
        "research.html",
        mock_enabled=mock_enabled(),
        research_tickers=RESEARCH_TICKERS,
        comparison_only=COMPARISON_ONLY_TICKERS,
        scenarios=SCENARIOS,
    )


@bp.get("/api/ui/published")
def published_reports():
    try:
        fixture = load_fixture()
    except (OSError, ValueError):
        return jsonify({"ok": False, "error": "published_metadata_unavailable"}), 503
    rows = [
        {key: row.get(key) for key in PUBLISHED_FIELDS}
        for row in fixture.get("published_reports", [])
        if row.get("publication_status") == "published"
    ]
    return jsonify({
        "ok": True,
        "source": "fixture",
        "synthetic_fixture": bool(fixture.get("synthetic_fixture")),
        "fixture_note": fixture.get("fixture_note"),
        "timezone": "Asia/Taipei",
        "reports": rows,
    })


@bp.post("/api/ui/mock/jobs")
def create_mock_job():
    if not mock_enabled():
        return disabled()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "請求內容需為 JSON 物件"}), 400
    try:
        job, created = get_mock().create(payload)
    except ContractError as exc:
        status = 409 if "idempotency_key" in str(exc) else 400
        return jsonify({"ok": False, "error": str(exc)}), status
    return jsonify({"ok": True, "created": created, "job": job}), 202 if created else 200


@bp.get("/api/ui/jobs/<job_id>")
def mock_job_status(job_id: str):
    if not mock_enabled():
        return disabled()
    found = get_mock().get(job_id)
    if found is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    job, events = found
    return jsonify({"ok": True, "job": job, "events": events})
