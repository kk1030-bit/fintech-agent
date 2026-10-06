"""2454 peer-comparison panel data (W04-A), per ui/v12-comparison-contract.md.

Main values are only what B's deterministic tools can reproduce from the fixed
snapshot (get_financial_snapshot, get_price_window, calculate_metrics). A value
that exists only in B's peer snapshot is returned as `snapshot_value` with
`source="snapshot_only"` and never enters peer statistics. Missing → null +
reason, never 0. No LLM, no network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents import tools_impl

ROOT = Path(__file__).resolve().parent.parent
PEER_SNAPSHOT = ROOT / "data" / "v12-peer-snapshot.json"
ORDER = ("2454", "2379", "3034", "2330")
METHOD_VERSION = "ui-peer-v1 / agents.calculator / tools-v12.0"


def _na(reason: str, snapshot_value: Any = None, **extra: Any) -> dict[str, Any]:
    return {"value": None, "na_reason": reason, "source": "snapshot_only" if snapshot_value is not None else "none",
            "snapshot_value": snapshot_value, **extra}


def _tool_value(value: float, snapshot_value: Any, **extra: Any) -> dict[str, Any]:
    consistent = None
    if isinstance(snapshot_value, (int, float)):
        consistent = abs(value - snapshot_value) <= max(0.01, abs(snapshot_value) * 0.001)
    return {"value": value, "na_reason": None, "source": "tool", "snapshot_value": snapshot_value,
            "consistent": consistent, **extra}


def _quarters(ticker: str, cutoff: str) -> list[dict[str, Any]]:
    cutoff_dt = tools_impl._parse_iso(cutoff)
    company = tools_impl._load_snapshots().get("financials", {}).get(ticker) or {}
    return [q for q in company.get("quarters", []) if tools_impl._parse_iso(q["available_at"]) <= cutoff_dt]


def _evidence_exists(ref: str) -> bool:
    return tools_impl.read_evidence(ref).get("status") == "ok"


def build_comparison() -> dict[str, Any]:
    peer = json.loads(PEER_SNAPSHOT.read_text(encoding="utf-8"))
    price_as_of, cutoff = peer["price_as_of"], peer["cutoff_at"]
    rows, checks = [], []

    for code in ORDER:
        snap = peer["companies"].get(code)
        if snap is None:
            continue
        quarters = _quarters(code, cutoff)
        fin = tools_impl.get_financial_snapshot(code, cutoff)
        fin_data = fin.get("data") or {}
        metrics = fin_data.get("metrics") or {}

        price = None
        window = tools_impl.get_price_window(code, f"{price_as_of}T13:30:00+08:00", 1)
        if window.get("status") == "ok":
            last = window["data"]["closes"][-1]
            if last["trade_date"] == price_as_of:
                price = {"value": last["close"], "trade_date": last["trade_date"], "basis": window["data"]["price_basis"]}

        refs = snap.get("evidence_refs") or []
        out: dict[str, Any] = {}

        # P/E (TTM)
        eps_ttm = metrics.get("eps_ttm")
        if price is None:
            out["pe_ttm"] = _na(f"{price_as_of} 無收盤價，不用其他日期補", snap.get("pe_ttm"))
        elif eps_ttm is None:
            out["pe_ttm"] = _na(f"TTM 需連續 4 季，快照只有 {len(quarters)} 季", snap.get("pe_ttm"))
        else:
            calc = tools_impl.calculate_metrics("pe_ttm", {"price": price["value"], "eps_ttm": eps_ttm}, refs or ["snapshot"])
            out["pe_ttm"] = (_tool_value(calc["data"]["result_value"], snap.get("pe_ttm"), eps_ttm=eps_ttm)
                             if calc["status"] == "ok" else _na(calc.get("reason") or "不適用", snap.get("pe_ttm")))

        # P/B — BVPS is not in the snapshot, so the tool cannot reproduce it.
        out["pb"] = _na("快照沒有 BVPS，工具無法重算", snap.get("pb_ratio"))

        # Single-quarter revenue YoY — needs the same quarter one year earlier.
        latest = quarters[-1] if quarters else None
        if latest is None:
            out["revenue_yoy_quarter"] = _na("快照沒有可得季度", snap.get("revenue_yoy_quarter"))
        else:
            year, q = int(latest["period"][:4]), latest["period"][4:]
            base_period = f"{year - 1}{q}"
            base = next((x for x in quarters if x["period"] == base_period), None)
            if base is None:
                out["revenue_yoy_quarter"] = _na(f"缺去年同季基期（{base_period}）", snap.get("revenue_yoy_quarter"))
            else:
                calc = tools_impl.calculate_metrics("growth_rate", {"current": latest.get("revenue"), "previous": base.get("revenue")}, refs or ["snapshot"])
                out["revenue_yoy_quarter"] = (_tool_value(calc["data"]["result_value"], snap.get("revenue_yoy_quarter"))
                                              if calc["status"] == "ok" else _na(calc.get("reason") or "不適用", snap.get("revenue_yoy_quarter")))

        # FCF (TTM) — operating cash flow minus positive CapEx, four consecutive quarters.
        fcf_ttm = metrics.get("fcf_ttm")
        out["fcf_ttm"] = (_tool_value(fcf_ttm, snap.get("fcf_100m"), unit="億元") if fcf_ttm is not None
                          else _na(f"TTM 需連續 4 季，快照只有 {len(quarters)} 季", snap.get("fcf_100m"), unit="億元"))

        # DCF gap — parameters (WACC, g) are not provided; judged in W05.
        out["dcf_gap"] = _na("DCF 參數（WACC、g）未提供，W05 判定", snap.get("dcf_gap_pct"))

        for name, cell in out.items():
            if cell.get("consistent") is False:
                checks.append({"ticker": code, "metric": name, "issue": f"工具值 {cell['value']} 與 B 快照 {cell['snapshot_value']} 不一致"})
            elif cell["source"] == "snapshot_only":
                checks.append({"ticker": code, "metric": name, "issue": cell["na_reason"]})

        role = snap.get("role")
        rows.append({
            "ticker": code,
            "name": snap.get("name") or fin_data.get("company_name"),
            "role": role,
            "financial_period": fin_data.get("latest_period") or snap.get("financial_period"),
            "available_at": fin_data.get("available_at"),
            "quarters_available": len(quarters),
            "price": price,
            "metrics": out,
            "evidence": [{"id": r, "exists": _evidence_exists(r)} for r in refs],
            "include_in_peer_stats": role == "peer",
        })

    subject_period = next((r["financial_period"] for r in rows if r["role"] == "subject"), None)
    peers = [r for r in rows if r["include_in_peer_stats"] and r["financial_period"] == subject_period]
    pe_values = [r["metrics"]["pe_ttm"]["value"] for r in peers if r["metrics"]["pe_ttm"]["value"] is not None]
    periods = sorted({r["financial_period"] for r in rows if r["financial_period"]})

    return {
        "ok": True,
        "subject": "2454",
        "price_as_of": price_as_of,
        "cutoff_at": cutoff,
        "snapshot_version": peer.get("snapshot_version"),
        "method_version": METHOD_VERSION,
        "synthetic_fixture": True,
        "fixture_note": "B 的同業快照未標明真實或合成，且尚未經 D 確認；本面板一律以 FIXTURE 呈現。",
        "periods_consistent": len(periods) <= 1,
        "rows": rows,
        "peer_stats": {
            "basis": "只用 role=peer、與主體同財報期、且 P/E 可由工具重現者；2330 產業參照一律排除",
            "pe_ttm": round(sum(pe_values) / len(pe_values), 2) if pe_values else None,
            "n": len(pe_values),
            "na_reason": None if pe_values else "同業沒有可由工具重現的 P/E",
            "snapshot_value": (peer.get("peer_summary_statistics") or {}).get("peer_avg_pe"),
            "excluded": [r["ticker"] for r in rows if not r["include_in_peer_stats"]],
        },
        "checks": checks,
    }


def referenced_evidence_ids() -> set[str]:
    peer = json.loads(PEER_SNAPSHOT.read_text(encoding="utf-8"))
    return {ref for company in peer["companies"].values() for ref in company.get("evidence_refs") or []}
