"""agents/calculator.py
W03-B: calculate_metrics 純數學確定性運算實作模組。
負責執行五大操作：
1. growth_rate: 成長率計算 (同口徑、前期非0)
2. simple_return: 簡單價格報酬率
3. pe_ttm: 本益比 (同日市價 / TTM EPS，EPS<=0 標註 NA)
4. dcf_scenario: 現金流折現估值 (WACC > g，缺值不補0)
5. peer_comparison: 同業比較 (以 2454 為主體，2330 嚴格排除於平均值計算之外)
"""

from __future__ import annotations
from typing import Any


def calculate_growth_rate(current: float | None, previous: float | None) -> dict[str, Any]:
    """計算變動百分比，前期缺失或為 0 則判定不適用"""
    if current is None or previous is None:
        return {"result_value": None, "is_applicable": False, "reason": "數值缺失 (null)"}
    if previous == 0:
        return {"result_value": None, "is_applicable": False, "reason": "基期數值為 0，無法計算成長率"}
    
    val = round((current - previous) / abs(previous), 4)
    return {"result_value": val, "is_applicable": True, "reason": None}


def calculate_simple_return(entry_price: float | None, exit_price: float | None) -> dict[str, Any]:
    """計算持有期簡單報酬率"""
    if entry_price is None or exit_price is None or entry_price <= 0:
        return {"result_value": None, "is_applicable": False, "reason": "買進價格無效或非正數"}
    
    ret = round((exit_price - entry_price) / entry_price, 4)
    return {"result_value": ret, "is_applicable": True, "reason": None}


def calculate_pe_ttm(price: float | None, eps_ttm: float | None) -> dict[str, Any]:
    """計算本益比；EPS TTM 非正數時回傳 null 並標註 NA，不產出負本益比"""
    if price is None or eps_ttm is None:
        return {"result_value": None, "is_applicable": False, "reason": "市價或 EPS TTM 缺失"}
    if eps_ttm <= 0:
        return {"result_value": None, "is_applicable": False, "reason": "EPS TTM <= 0，不適用本益比 (NA)"}
    
    pe = round(price / eps_ttm, 2)
    return {"result_value": pe, "is_applicable": True, "reason": None}


def calculate_dcf_scenario(
    free_cash_flows: list[float] | None,
    wacc: float | None,
    terminal_growth: float | None,
    net_debt: float | None,
    shares_outstanding: float | None
) -> dict[str, Any]:
    """計算 DCF 內在價值；約束條件：WACC > g，缺值不可補 0"""
    # 檢查關鍵參數完整性
    if (
        free_cash_flows is None 
        or not free_cash_flows 
        or wacc is None 
        or terminal_growth is None 
        or net_debt is None 
        or shares_outstanding is None
    ):
        return {
            "enterprise_value": None,
            "equity_value": None,
            "intrinsic_value_per_share": None,
            "is_applicable": False,
            "reason": "DCF 關鍵參數缺失，不可假補 0"
        }

    if wacc <= terminal_growth:
        return {
            "enterprise_value": None,
            "equity_value": None,
            "intrinsic_value_per_share": None,
            "is_applicable": False,
            "reason": f"WACC ({wacc}) 必須嚴格大於終端成長率 g ({terminal_growth})"
        }

    if shares_outstanding <= 0:
        return {
            "enterprise_value": None,
            "equity_value": None,
            "intrinsic_value_per_share": None,
            "is_applicable": False,
            "reason": "流通股數必須大於 0"
        }

    # 1. 現金流現值 (PV of FCF)
    pv_fcfs = [fcf / ((1 + wacc) ** idx) for idx, fcf in enumerate(free_cash_flows, start=1)]
    sum_pv_fcf = sum(pv_fcfs)

    # 2. 終端價值 (Terminal Value) 與其現值
    terminal_value = free_cash_flows[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1 + wacc) ** len(free_cash_flows))

    # 3. 企業價值與股權價值
    enterprise_value = sum_pv_fcf + pv_terminal
    equity_value = enterprise_value - net_debt

    # 4. 每股內在價值 (億元 / 百萬股 -> 乘 100 換算為 元/股)
    intrinsic_value_per_share = round((equity_value / shares_outstanding) * 100, 2)

    return {
        "pv_fcf_total": round(sum_pv_fcf, 2),
        "terminal_value": round(terminal_value, 2),
        "pv_terminal": round(pv_terminal, 2),
        "enterprise_value": round(enterprise_value, 2),
        "equity_value": round(equity_value, 2),
        "intrinsic_value_per_share": intrinsic_value_per_share,
        "is_applicable": True,
        "reason": None
    }


def calculate_peer_comparison(
    subject: str,
    comparators: list[str],
    metrics_map: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """
    同業比較指標統計。
    主體限定 2454，可比同業為 2379、3034。
    2330 僅作為半導體權值之「產業參照」，絕對不可納入同業平均值計算。
    """
    if subject != "2454":
        return {"is_applicable": False, "reason": "同業比較主體只限 2454"}
    
    total_companies = [subject] + comparators
    if len(total_companies) > 4:
        return {"is_applicable": False, "reason": "比較公司總數不可超過 4 家"}

    table = {}
    peer_pes = []
    peer_pbs = []

    for code in total_companies:
        data = metrics_map.get(code, {})
        p = data.get("price")
        eps = data.get("eps_ttm")
        pb = data.get("pb")
        yoy = data.get("revenue_yoy")
        fcf = data.get("fcf")

        # PE 計算
        pe = round(p / eps, 2) if (p and eps and eps > 0) else None

        role = "industry_reference" if code == "2330" else ("subject" if code == subject else "peer")

        table[code] = {
            "role": role,
            "price": p,
            "pe_ttm": pe,
            "pb": pb,
            "revenue_yoy": yoy,
            "fcf": fcf
        }

        # 核心防呆：只有 peer 角色才進入同業平均計算，2330 嚴格排除
        if role == "peer":
            if pe is not None:
                peer_pes.append(pe)
            if pb is not None:
                peer_pbs.append(pb)

    avg_pe = round(sum(peer_pes) / len(peer_pes), 2) if peer_pes else None
    avg_pb = round(sum(peer_pbs) / len(peer_pbs), 2) if peer_pbs else None

    return {
        "subject": subject,
        "comparison_table": table,
        "peer_average_stats": {
            "peer_avg_pe": avg_pe,
            "peer_avg_pb": avg_pb,
            "excluded_references": ["2330"]
        },
        "is_applicable": True,
        "reason": None
    }


def execute_calculation(operation: str, values: dict[str, Any], evidence_refs: list[str]) -> dict[str, Any]:
    """計算工具入口分發函式 (對齊 calculate_metrics 工具契約)"""
    if not evidence_refs:
        return {
            "status": "invalid_input",
            "tool": "calculate_metrics",
            "reason": "運算必須引用具體 evidence_refs 依據",
            "data": None
        }

    if operation == "growth_rate":
        res = calculate_growth_rate(values.get("current"), values.get("previous"))
    elif operation == "simple_return":
        res = calculate_simple_return(values.get("entry_price"), values.get("exit_price"))
    elif operation == "pe_ttm":
        res = calculate_pe_ttm(values.get("price"), values.get("eps_ttm"))
    elif operation == "dcf_scenario":
        res = calculate_dcf_scenario(
            values.get("free_cash_flows"),
            values.get("wacc"),
            values.get("terminal_growth"),
            values.get("net_debt"),
            values.get("shares_outstanding")
        )
    elif operation == "peer_comparison":
        res = calculate_peer_comparison(
            values.get("subject", ""),
            values.get("comparators", []),
            values.get("metrics", {})
        )
    else:
        return {
            "status": "invalid_input",
            "tool": "calculate_metrics",
            "reason": f"未知的運算操作: {operation}",
            "data": None
        }

    if not res.get("is_applicable", False):
        return {
            "status": "invalid_input",
            "tool": "calculate_metrics",
            "reason": res.get("reason", "運算條件不滿足"),
            "data": None
        }

    res["evidence_refs"] = evidence_refs
    res["operation"] = operation
    return {
        "status": "ok",
        "tool": "calculate_metrics",
        "data": res
    }