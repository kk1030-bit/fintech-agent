"""Validate generated financial analysis records in Supabase."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

ROOT_DIR = Path(__file__).resolve().parent


def parse_json_text(value: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def extract_analysis(row: dict[str, Any]) -> dict[str, Any]:
    summary_payload = parse_json_text(row.get("summary"))
    if isinstance(summary_payload, dict):
        analysis = summary_payload.get("analysis") or {}
        financials = summary_payload.get("financials") or {}
        return {
            "summary": summary_payload.get("summary_text") or "",
            "strengths": analysis.get("strengths") or [],
            "risks": analysis.get("risks") or parse_json_text(row.get("risks")) or [],
            "fcf_forecast": analysis.get("fcf_forecast") or financials.get("fcf_forecast") or [],
            "financials": financials,
            "data_source": summary_payload.get("data_source"),
        }

    return {
        "summary": row.get("summary") or "",
        "strengths": parse_json_text(row.get("strengths")) or [],
        "risks": parse_json_text(row.get("risks")) or [],
        "fcf_forecast": parse_json_text(row.get("fcf_forecast")) or [],
        "financials": {},
        "data_source": row.get("data_source"),
    }


def forecast_numbers(value: Any) -> list[float]:
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(forecast_numbers(item))
        return result
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        return [float(match) for match in re.findall(r"-?\d+(?:\.\d+)?", value.replace(",", ""))]
    return []


def check_stock(client, stock_code: str) -> tuple[bool, list[str]]:
    rows = (
        client.table("fundamental_data")
        .select("*")
        .eq("stock_code", stock_code)
        .order("year")
        .execute()
        .data
        or []
    )
    if not rows:
        return False, [f"{stock_code}: Supabase 沒有資料"]

    latest = rows[-1]
    analysis = extract_analysis(latest)
    issues = []
    summary = str(analysis["summary"])
    risks = analysis["risks"] if isinstance(analysis["risks"], list) else [analysis["risks"]]
    forecasts = forecast_numbers(analysis["fcf_forecast"])
    financials = analysis.get("financials") or {}

    if len(summary) < 100:
        issues.append("summary 未達 100 字")
    if len([risk for risk in risks if str(risk).strip()]) < 3:
        issues.append("risks 少於 3 點")
    if len(forecasts) < 5:
        issues.append("fcf_forecast 少於 5 個數字")
    if any(value == 0 for value in forecasts[:5]):
        issues.append("fcf_forecast 含 0")
    if analysis.get("data_source") != "finmind":
        issues.append("data_source 不是 finmind")
    if financials.get("free_cash_flow") is None:
        issues.append("缺少 FinMind free_cash_flow")

    return not issues, issues


def main() -> None:
    stock_codes = sys.argv[1:] or ["2330", "2317"]
    load_dotenv(ROOT_DIR / ".env")
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

    all_ok = True
    for stock_code in stock_codes:
        ok, issues = check_stock(client, stock_code)
        if ok:
            print(f"[OK] {stock_code} 分析品質合格")
        else:
            all_ok = False
            print(f"[ERROR] {stock_code}: {'; '.join(issues)}")

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
