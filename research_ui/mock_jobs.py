"""MOCK research jobs for A's UI work (W02-A/W03-A).

Authorisation is still "MOCK only" (decided 2026-10-05): the page never holds
RESEARCH_API_TOKEN and never reaches the real Gemini worker. To still read job
state *from a database* (W03 驗收「狀態從DB取得」) the mock uses 組長's
`agents.store.JobStore` on its own SQLite file, and `agents.contract` for the
same request validation (2379/3034 rejected, cutoff required, idempotent key).

There is no background thread. Each GET calls `pump()`, which applies the
scripted steps whose time has come, through the normal lease/fencing API.
Every event carries `"mock": true`; no model is called anywhere here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agents.contract import ContractError, validate_job_request
from agents.store import JobStore, StaleLeaseError

WORKER_ID = "ui-mock-worker"
STEP_SECONDS = float(os.getenv("RESEARCH_UI_MOCK_STEP_SECONDS", "1.5"))

# Public job fields shown in the UI (same list as agents/api.py, nothing else).
PUBLIC_JOB_FIELDS = (
    "job_id", "ticker", "mode", "status", "stage", "cutoff_at", "source_snapshot_id", "question_version",
    "model_id", "prompt_version", "calls_used", "tokens_observed", "tool_calls_used", "supplement_rounds",
    "active_seconds", "stop_reason", "checkpoint_version", "created_at", "updated_at",
)
# Event detail keys the UI may show. Anything else (raw prompts, args, model text) is dropped.
PUBLIC_DETAIL_KEYS = (
    "mock", "summary", "decision_summary", "evidence_refs", "latency_ms", "tool_status",
    "args_redacted", "output_hash", "claim_id", "severity", "required_evidence", "budget",
)

SCENARIOS = ("succeeded", "insufficient_evidence")


def _snapshot_id(root: Path) -> str:
    path = root / "data" / "financial-snapshots.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        return f"fin-snap:{manifest.get('manifest_version', 'unknown')}"
    except (OSError, ValueError):
        return "fin-snap:unavailable"


def _steps(scenario: str, ticker: str) -> list[dict[str, Any]]:
    """Scripted MOCK steps. Each step = one event (+ optional job changes)."""

    start = [
        {"role": "researcher", "event_type": "plan", "detail": {
            "summary": "MOCK：依研究問題決定先查財報快照", "decision_summary": "缺最新季資料，先取財務快照"}},
        {"role": "researcher", "event_type": "tool_call", "tool": "get_financial_snapshot", "detail": {
            "summary": "MOCK：讀取 cutoff 前可得的單季與 TTM", "args_redacted": {"ticker": ticker, "cutoff": "<job.cutoff_at>"}},
         "changes": {"stage": "tools", "calls_used": 1, "tool_calls_used": 1, "active_seconds": 6.0}},
    ]
    if scenario == "insufficient_evidence":
        return start + [
            {"role": "researcher", "event_type": "stop", "detail": {
                "summary": "MOCK：關鍵資料缺失，停止並保留限制",
                "decision_summary": "財報快照無資料且沒有可用替代工具"},
             "changes": {"status": "insufficient_evidence", "stage": "finished", "calls_used": 2,
                         "active_seconds": 9.0, "stop_reason": "missing_key_financials"}},
        ]
    return start + [
        {"role": "researcher", "event_type": "draft", "detail": {"summary": "MOCK：提出 3 項主張草稿"},
         "changes": {"stage": "review", "calls_used": 2, "active_seconds": 14.0}},
        {"role": "reviewer", "event_type": "review", "detail": {"summary": "MOCK：覆核通過（仍需人工核准才發布）"},
         "changes": {"calls_used": 3, "active_seconds": 19.0}},
        {"role": "system", "event_type": "finished", "detail": {"summary": "MOCK：研究完成，等待人工核准"},
         "changes": {"status": "succeeded", "stage": "finished", "stop_reason": "mock_completed"}},
    ]


class MockJobs:
    def __init__(self, db_path: str | Path, root: Path, clock=None):
        self.root = root
        self.store = JobStore(db_path, clock=clock) if clock else JobStore(db_path)
        self.store._conn.execute(  # side table owned by the UI mock only
            "create table if not exists ui_mock_jobs (job_id text primary key, scenario text not null,"
            " started_at real, step integer not null default 0)"
        )

    # ----- create -----------------------------------------------------------
    def create(self, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        scenario = str(payload.get("scenario") or "succeeded")
        if scenario not in SCENARIOS:
            raise ContractError(f"scenario 只限 {', '.join(SCENARIOS)}（MOCK）")
        req = validate_job_request({**payload, "source_snapshot_id": _snapshot_id(self.root)})
        job, created = self.store.create_job(req, model_id=None)
        if created:
            self.store._conn.execute(
                "insert into ui_mock_jobs (job_id, scenario) values (?, ?)", (job["job_id"], scenario))
            self.store.append_event(job["job_id"], "system", "mock_scenario", None,
                                    {"mock": True, "summary": f"MOCK 情境：{scenario}"})
        return self.public_job(job), created

    # ----- read ---------------------------------------------------------------
    def get(self, job_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        self.pump()
        job = self.store.get_job(job_id)
        if job is None or not self._is_mock(job_id):
            return None
        queue_ahead = 0
        if job["status"] == "queued":
            queue_ahead = self.store._conn.execute(
                "select count(*) from research_jobs where status in ('queued','running') and created_at < ?",
                (job["created_at"],),
            ).fetchone()[0]
        public = self.public_job(job)
        public["queue_ahead"] = queue_ahead
        return public, [self.public_event(e) for e in self.store.list_events(job_id)]

    @staticmethod
    def public_job(job: dict[str, Any]) -> dict[str, Any]:
        out = {key: job.get(key) for key in PUBLIC_JOB_FIELDS}
        out["mock"] = True
        return out

    @staticmethod
    def public_event(event: dict[str, Any]) -> dict[str, Any]:
        detail = event.get("detail") or {}
        return {
            "event_seq": event["event_seq"],
            "created_at": event["created_at"],
            "role": event.get("role"),
            "event_type": event["event_type"],
            "tool_name": event.get("tool_name"),
            "detail": {k: detail[k] for k in PUBLIC_DETAIL_KEYS if k in detail},
        }

    def _is_mock(self, job_id: str) -> bool:
        return self.store._conn.execute("select 1 from ui_mock_jobs where job_id = ?", (job_id,)).fetchone() is not None

    # ----- time-based progression ---------------------------------------------
    def pump(self) -> None:
        conn = self.store._conn
        running = conn.execute(
            "select r.job_id, r.lease_token, r.lease_owner from research_jobs r join ui_mock_jobs m using (job_id)"
            " where r.status = 'running'"
        ).fetchone()
        if running is None or running["lease_owner"] != WORKER_ID:
            claimed = self.store.claim_next(WORKER_ID)
            if not claimed:
                return
            job, token = claimed
            conn.execute("update ui_mock_jobs set started_at = coalesce(started_at, ?) where job_id = ?",
                         (self.store.clock(), job["job_id"]))
            job_id = job["job_id"]
        else:
            job_id, token = running["job_id"], running["lease_token"]
        self._advance(job_id, token)

    def _advance(self, job_id: str, token: int) -> None:
        conn = self.store._conn
        meta = conn.execute("select scenario, started_at, step from ui_mock_jobs where job_id = ?", (job_id,)).fetchone()
        job = self.store.get_job(job_id)
        steps = _steps(meta["scenario"], job["ticker"])
        due = min(len(steps), int((self.store.clock() - meta["started_at"]) / STEP_SECONDS) + 1)
        try:
            for index in range(meta["step"], due):
                step = steps[index]
                detail = {"mock": True, **step.get("detail", {})}
                self.store.append_event(job_id, step["role"], step["event_type"], step.get("tool"), detail)
                if step.get("changes"):
                    self.store.update_job(job_id, WORKER_ID, token, step["changes"])
                else:
                    self.store.heartbeat(job_id, WORKER_ID, token)
                conn.execute("update ui_mock_jobs set step = ? where job_id = ?", (index + 1, job_id))
        except StaleLeaseError:
            return  # lease lapsed (no poll for >60 s); the next pump re-claims and continues
