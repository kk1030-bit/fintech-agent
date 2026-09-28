"""Worker loop skeleton (W02-L). The real LangGraph Researcher/Reviewer graph
plugs in as `handler` in W04/W05; for now `mock_handler` exercises the lease,
heartbeat, fencing and restart paths without any model call.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Protocol

from .store import HEARTBEAT_SECONDS, POLL_SECONDS, JobStore, StaleLeaseError


class LeaseContext(Protocol):
    job: dict[str, Any]

    def heartbeat(self) -> None: ...
    def save(self, changes: dict[str, Any]) -> dict[str, Any]: ...
    def event(self, role: str | None, event_type: str, tool_name: str | None = None,
              detail: dict[str, Any] | None = None) -> None: ...


class _Lease:
    def __init__(self, store: JobStore, worker_id: str, job: dict[str, Any], token: int):
        self.store, self.worker_id, self.job, self.token = store, worker_id, job, token

    def heartbeat(self) -> None:
        self.store.heartbeat(self.job["job_id"], self.worker_id, self.token)

    def save(self, changes: dict[str, Any]) -> dict[str, Any]:
        self.job = self.store.update_job(self.job["job_id"], self.worker_id, self.token, changes)
        return self.job

    def event(self, role, event_type, tool_name=None, detail=None) -> None:
        self.store.append_event(self.job["job_id"], role, event_type, tool_name, detail)


Handler = Callable[[LeaseContext], dict[str, Any]]


def mock_handler(lease: LeaseContext) -> dict[str, Any]:
    """Deterministic stand-in: one research and one review checkpoint, no LLM."""

    lease.event("researcher", "mock_step", detail={"note": "MOCK：未呼叫模型"})
    lease.save({"stage": "review"})
    lease.heartbeat()
    lease.event("reviewer", "mock_step", detail={"note": "MOCK：未呼叫模型"})
    return {"status": "succeeded", "stage": "finished", "stop_reason": "mock_completed"}


def run_once(store: JobStore, worker_id: str, handler: Handler = mock_handler) -> dict[str, Any] | None:
    """Claim and process one job. Returns the final job row, or None if idle."""

    claimed = store.claim_next(worker_id)
    if not claimed:
        return None
    job, token = claimed
    lease = _Lease(store, worker_id, job, token)
    try:
        result = handler(lease)
    except StaleLeaseError:
        # Another worker owns the job now; drop our results silently.
        return None
    except Exception as exc:  # noqa: BLE001 - persist any failure instead of losing the job
        return lease.save({"status": "failed", "stage": "finished", "stop_reason": f"worker_error: {exc}"[:500]})
    return lease.save(result)


def run_forever(store: JobStore, worker_id: str, handler: Handler = mock_handler) -> None:  # pragma: no cover
    while True:
        if run_once(store, worker_id, handler) is None:
            time.sleep(POLL_SECONDS)


__all__ = ["HEARTBEAT_SECONDS", "mock_handler", "run_forever", "run_once"]
