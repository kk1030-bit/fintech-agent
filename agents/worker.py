"""Worker loop skeleton (W02-L). The real LangGraph Researcher/Reviewer graph
plugs in as `handler` in W04/W05; for now `mock_handler` exercises the lease,
heartbeat, fencing and restart paths without any model call.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Protocol

from .budget import BudgetExceeded
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
        try:
            result = handler(lease)
        except BudgetExceeded as exc:
            # A budget stop is an outcome, not a crash: paused_quota / timed_out / insufficient_evidence.
            result = {"status": exc.job_status, "stop_reason": exc.reason, "stop_detail": str(exc)[:500]}
            if exc.job_status == "paused_quota":
                if exc.wait_seconds is not None:  # quota_unknown has none: resumes only via store.requeue
                    result["resume_after"] = store.clock() + exc.wait_seconds
            else:
                result["stage"] = "finished"
        except StaleLeaseError:
            raise
        except Exception as exc:  # noqa: BLE001 - persist any failure instead of losing the job
            result = {"status": "failed", "stage": "finished", "stop_reason": f"worker_error: {exc}"[:500]}
        return lease.save(result)
    except StaleLeaseError:
        # Another worker owns the job now (our lease expired); drop our results.
        return None


def run_forever(store: JobStore, worker_id: str, handler: Handler = mock_handler) -> None:  # pragma: no cover
    while True:
        if run_once(store, worker_id, handler) is None:
            time.sleep(POLL_SECONDS)


__all__ = ["HEARTBEAT_SECONDS", "mock_handler", "run_forever", "run_once"]
