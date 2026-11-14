"""11/14（決策 37）：覆核視圖（SnapshotToolbox.snapshot_view）＝這個 job 的工具實際回傳的內容。
工具對 Agent 回 no_data（tool_simulation）時，它的數字與 TTM 季度不算「工具回傳過」。合成資料，不含保留集內容。"""
import json
from pathlib import Path

import pytest

import agents.snapshot as snapshot
from agents.review_checks import check_draft, consecutive_quarters
from agents.snapshot import SnapshotToolbox

FIX = Path(__file__).parent / "fixtures" / "agent_case_fixtures.json"
SID, CUT = "snap-dev-case-01", "2026-08-12T17:00:00+08:00"
Q4 = ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]
CASE_FIN = {"ticker": "2330", "period": "2026Q2", "period_basis": "single_quarter", "currency": "TWD", "eps_single_quarter": 11.11,
            "eps_ttm": 44.44, "ttm_periods": Q4, "available_at": "2026-08-01T10:00:00+08:00", "synthetic_fixture": True}
NO_DATA = {"tool_name": "get_financial_snapshot", "behavior": "no_data"}


@pytest.fixture
def view_of(tmp_path, monkeypatch):
    def make(**extra):
        data = json.loads(FIX.read_text(encoding="utf-8"))
        data["snapshots"][SID].update(extra)
        path = tmp_path / f"fx-{len(list(tmp_path.iterdir()))}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(snapshot, "DEV_FIXTURES", path)
        return SnapshotToolbox("2330", SID, CUT).snapshot_view()
    return make


def test_view_carries_the_ttm_the_financial_tool_returned_from_the_shared_store(view_of):
    view = view_of()
    assert "financial_snapshot" not in view                       # 這個案例的財報由共用資料庫提供
    assert consecutive_quarters(view["tool_ttm"]["ttm_periods"])
    assert isinstance(view["tool_ttm"]["eps_ttm"], (int, float)) and view["tool_ttm"]["eps_ttm"] in view["tool_numbers"]


def test_view_carries_the_ttm_of_a_case_level_financial_snapshot(view_of):
    view = view_of(financial_snapshot=CASE_FIN)
    assert view["tool_ttm"] == {"ttm_periods": Q4, "eps_ttm": 44.44} and 44.44 in view["tool_numbers"]


@pytest.mark.parametrize("extra", [{}, {"financial_snapshot": CASE_FIN}])
def test_simulated_no_data_removes_the_financial_numbers_and_ttm_from_the_view(view_of, extra):
    plain, simulated = view_of(**extra), view_of(tool_simulation=NO_DATA, **extra)
    assert simulated["tool_ttm"] == {}
    gone = set(plain["tool_numbers"]) - set(simulated["tool_numbers"])
    assert plain["tool_ttm"]["eps_ttm"] in gone                   # Agent 沒拿到的財報數字不再算「工具回傳過」
    assert simulated["tool_numbers"]                              # 股價工具沒有被模擬，數字照舊


def test_ttm_rule_follows_the_view_end_to_end(view_of):
    def flags(view):
        facts = [{"metric": "eps_ttm", "value": 44.44, "currency": "TWD", "period": "2026Q2", "period_basis": "ttm", "source_ref": SID}]
        draft = {"status": "draft", "valuation_scenarios": ["v"], "macro_observations": ["m"],
                 "claims": [{"claim_id": "c1", "kind": "fact", "text": "TTM EPS 44.44", "evidence_refs": [SID], "facts": facts}]}
        issues = check_draft(draft, view, CUT, SID)["review"]["issues"]
        return sorted({i["claim_id"] for i in issues if i["severity"] == "critical"})
    assert flags(view_of(financial_snapshot=CASE_FIN)) == []
    assert flags(view_of(financial_snapshot=CASE_FIN, tool_simulation=NO_DATA)) == ["c1"]  # TTM 季度與數字都沒有依據
