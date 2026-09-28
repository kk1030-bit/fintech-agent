"""LangGraph state schema for the Researcher/Reviewer graph (W02-L).

The graph itself is built in W04 (Researcher loop) and W05 (Reviewer). The
in-memory LangGraph state is NOT the persistence layer: every checkpoint and
budget counter is written to the job store (see store.py).
"""

from __future__ import annotations

from typing import Literal, TypedDict


class Claim(TypedDict):
    claim_id: str
    kind: Literal["fact", "inference", "unknown"]
    text: str
    evidence_refs: list[str]
    limitations: list[str]


class ReviewIssue(TypedDict):
    claim_id: str
    severity: Literal["critical", "minor"]
    reason: str
    required_evidence: str


class Review(TypedDict):
    decision: Literal["pass", "revise", "insufficient"]
    issues: list[ReviewIssue]


class ToolObservation(TypedDict):
    tool_name: str
    args_hash: str
    output_hash: str
    evidence_refs: list[str]
    summary: str


class ResearchState(TypedDict, total=False):
    job_id: str
    ticker: str
    cutoff_at: str
    source_snapshot_id: str
    mode: Literal["workflow", "single", "dual"]
    stage: Literal["research", "tools", "review", "revision", "finished"]
    messages: list[dict]            # provider-neutral turns, redacted
    observations: list[ToolObservation]
    claims: list[Claim]
    review: Review | None
    supplement_rounds: int
    stop_reason: str | None
    checkpoint_version: int
