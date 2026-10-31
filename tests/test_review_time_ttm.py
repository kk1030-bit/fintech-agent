"""10/31：TTM 季度可由 period 判定（CASE-22）；時間比對由程式決定（CASE-11）。"""
import json

import pytest

from agents.review_checks import check_draft, drop_refuted_timing_issues, ttm_quarters
from agents.snapshot import SnapshotToolbox

CUTOFF = "2026-08-12T09:00:00+00:00"
EV = {"evidence_version_id": "ev-1", "available_at": "2026-08-12T14:15:01+08:00", "paragraph": "EPS 4.27"}
LATE = {"evidence_version_id": "ev-late", "available_at": "2026-08-12T18:00:00+08:00", "paragraph": "EPS 4.27"}
CAPTURED = {"evidence_version_id": "ev-cap", "captured_at": "2026-08-12T01:00:00+00:00", "paragraph": "EPS 4.27"}


def draft(ref="ev-1"):
    return {"claims": [{"claim_id": "c1", "kind": "fact", "text": "EPS 4.27", "evidence_refs": [ref], "facts": []}]}


def review(reason, decision="insufficient", severity="critical"):
    return {"decision": decision, "checked_refs": [], "checked_metric_ids": [], "decision_summary": "x",
            "issues": [{"claim_id": "c1", "severity": severity, "reason": reason, "required_evidence": "read_evidence(ev-1)"}]}


@pytest.mark.parametrize("period,ok", [
    ("2025Q3-2026Q2", True), ("2025Q3至2026Q2", True), ("2025Q3,2025Q4,2026Q1,2026Q2", True),
    ("2026Q2", False), ("2025Q3,2026Q2", False), ("2025Q1-2026Q2", False), ("2024Q3-2025Q1", False), ("2026Q2-2025Q3", False), (None, False),
])
def test_ttm_period_forms(period, ok):
    snap = {"ticker": "2330", "evidences": [], "tool_numbers": [86.28]}
    d = {"claims": [{"claim_id": "c1", "kind": "fact", "text": "TTM EPS 86.28", "evidence_refs": ["snap"],
                     "facts": [{"metric": "eps_ttm", "value": 86.28, "unit": "元", "currency": "TWD", "period": period,
                                "period_basis": "ttm", "source_ref": "snap"}]}]}
    issues = check_draft(d, snap, CUTOFF, "snap")["review"]["issues"]
    assert any("TTM 需要四個連續單季" in i["reason"] for i in issues) is not ok


def test_quarters_field_wins_over_period():
    assert ttm_quarters({"quarters": ["2026Q2"], "period": "2025Q3-2026Q2"}) == ["2026Q2"]


def test_case_11_false_timing_issue_removed_and_decision_recomputed():
    out, dropped = drop_refuted_timing_issues(review("ev-1 的 available_at 晚於 cutoff_at，違反時效性規定"), draft(), {"evidences": [EV]}, CUTOFF)
    assert len(dropped) == 1 and out["issues"] == [] and out["decision"] == "pass"


def test_real_lookahead_is_kept_by_model_filter_and_caught_by_rules():
    snap = {"evidences": [dict(LATE, available_at="2026-08-13T00:00:00+08:00")]}
    out, dropped = drop_refuted_timing_issues(review("ev-late 的 available_at 晚於 cutoff_at"), draft("ev-late"), snap, CUTOFF)
    assert dropped == [] and out["decision"] == "insufficient"
    assert any("前視" in i["reason"] for i in check_draft(draft("ev-late"), snap, CUTOFF, "snap")["review"]["issues"])


def test_non_timing_issue_and_other_criticals_stay():
    out, dropped = drop_refuted_timing_issues(review("原文沒有這個數字"), draft(), {"evidences": [EV]}, CUTOFF)
    assert dropped == [] and out["decision"] == "insufficient"
    both = review("available_at 晚於 cutoff", decision="revise")
    both["issues"].append({"claim_id": "c1", "severity": "critical", "reason": "原文沒有這個數字", "required_evidence": "read_evidence(ev-1)"})
    out, dropped = drop_refuted_timing_issues(both, draft(), {"evidences": [EV]}, CUTOFF)
    assert len(dropped) == 1 and out["decision"] == "revise" and len(out["issues"]) == 1


def test_unknown_ref_and_failed_observation_are_not_refuted():
    r = review("available_at 晚於 cutoff")
    assert drop_refuted_timing_issues(r, draft("ev-x"), {"evidences": [EV]}, CUTOFF)[1] == []
    assert drop_refuted_timing_issues(r, draft("obs-1"), {"evidences": []}, CUTOFF,
                                      [{"obs_id": "obs-1", "status": "no_data"}])[1] == []


def test_captured_at_source_uses_fallback_in_both_checks():
    snap = {"evidences": [CAPTURED]}
    assert len(drop_refuted_timing_issues(review("cutoff 前不可得"), draft("ev-cap"), snap, CUTOFF)[1]) == 1
    assert not any("前視" in i["reason"] for i in check_draft(draft("ev-cap"), snap, CUTOFF, "snap")["review"]["issues"])


def test_case_22_and_case_11_real_snapshots():
    fixtures = json.load(open("fixtures/dev/case_fixtures.json", encoding="utf-8"))["snapshots"]
    tb = SnapshotToolbox("2317", "snap-dev-case-11", fixtures["snap-dev-case-11"].get("cutoff_at") or CUTOFF)
    out, dropped = drop_refuted_timing_issues(review("ev-dev-11-consolidated 的 available_at 晚於 cutoff_at"), draft("ev-dev-11-consolidated"), tb.snapshot_view(), CUTOFF)
    assert len(dropped) == 1 and out["decision"] == "pass"
