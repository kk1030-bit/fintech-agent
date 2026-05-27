"""Upload fundamental data to Supabase.

The current project database may not yet have dedicated numeric columns such as
revenue/free_cash_flow. This uploader detects the available table schema:

- If numeric columns exist, it writes the values into those columns.
- If they do not exist, it stores the same FinMind numeric payload and analysis
  payload as JSON in the existing summary column so main.py can still read real
  Supabase data.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from supabase import create_client

ROOT_DIR = Path(__file__).resolve().parent
NUMERIC_COLUMNS = {
    "currency",
    "revenue",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
    "shares_outstanding",
    "net_debt",
    "pe_ratio",
    "pb_ratio",
    "fcf_forecast",
    "data_source",
}


def supabase_config() -> tuple[str, str]:
    """Read Supabase config from .env."""

    load_dotenv(ROOT_DIR / ".env")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("找不到 SUPABASE_URL 或 SUPABASE_KEY，請確認 .env。")
    return url, key


def get_table_columns(table_name: str = "fundamental_data") -> set[str]:
    """Read table columns from Supabase PostgREST OpenAPI metadata."""

    url, key = supabase_config()
    response = requests.get(
        url.rstrip("/") + "/rest/v1/",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    )
    response.raise_for_status()
    definition = response.json().get("definitions", {}).get(table_name, {})
    return set((definition.get("properties") or {}).keys())


def text_or_json(value: Any) -> str | None:
    """Convert values into a text-safe representation for existing text columns."""

    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def build_summary_payload(financial_row: dict[str, Any], analysis_result: dict[str, Any] | None) -> str:
    """Store FinMind numbers and analysis in summary for compact schemas."""

    payload = {
        "summary_text": analysis_result.get("summary") if analysis_result else "FinMind 財務數據已匯入，供 DCF 模型使用。",
        "data_source": financial_row.get("data_source", "finmind"),
        "financials": {
            key: financial_row.get(key)
            for key in [
                "currency",
                "revenue",
                "operating_income",
                "net_income",
                "operating_cash_flow",
                "capital_expenditure",
                "free_cash_flow",
                "shares_outstanding",
                "net_debt",
                "pe_ratio",
                "pb_ratio",
                "fcf_forecast",
                "data_source",
            ]
            if financial_row.get(key) is not None
        },
    }
    if analysis_result:
        payload["analysis"] = {
            "method": analysis_result.get("analysis_method", "rule_based_finmind"),
            "strengths": analysis_result.get("strengths") or [],
            "risks": analysis_result.get("risks") or [],
            "fcf_forecast": analysis_result.get("fcf_forecast") or [],
            "created_at": analysis_result.get("created_at"),
        }
    return json.dumps(payload, ensure_ascii=False)


def build_record(
    financial_row: dict[str, Any],
    analysis_result: dict[str, Any] | None,
    columns: set[str],
) -> dict[str, Any]:
    """Build an insert/update record that matches the current table schema."""

    record: dict[str, Any] = {
        "stock_code": str(financial_row["stock_code"]),
        "year": str(financial_row["year"]),
        "company": financial_row.get("company") or str(financial_row["stock_code"]),
        "created_at": datetime.now().isoformat(),
    }

    has_numeric_columns = {"revenue", "free_cash_flow"}.issubset(columns)
    if has_numeric_columns:
        record["summary"] = analysis_result.get("summary") if analysis_result else None
        for column in NUMERIC_COLUMNS:
            if column in columns and financial_row.get(column) is not None:
                record[column] = financial_row.get(column)
        if "fcf_forecast" in columns and financial_row.get("fcf_forecast") is None and analysis_result:
            record["fcf_forecast"] = analysis_result.get("fcf_forecast")
    else:
        record["summary"] = build_summary_payload(financial_row, analysis_result)

    if analysis_result:
        if "strengths" in columns:
            record["strengths"] = text_or_json(analysis_result.get("strengths"))
        if "risks" in columns:
            record["risks"] = text_or_json(analysis_result.get("risks"))
    elif "risks" in columns:
        record["risks"] = None

    return {key: value for key, value in record.items() if key in columns}


def upload_to_supabase(financial_data: list[dict[str, Any]], analysis_result: dict[str, Any] | None = None) -> bool:
    """Upload financial data to Supabase fundamental_data."""

    url, key = supabase_config()
    supabase = create_client(url, key)
    columns = get_table_columns("fundamental_data")
    missing_numeric = sorted({"revenue", "free_cash_flow"} - columns)
    if missing_numeric:
        print("fundamental_data 尚未有獨立數值欄位，會先把 FinMind 數值寫入 summary JSON。")

    for item in financial_data:
        if item.get("revenue") is None or item.get("free_cash_flow") is None:
            continue
        record = build_record(item, analysis_result, columns)
        stock_code = str(item["stock_code"])
        year = str(item["year"])

        try:
            existing = (
                supabase.table("fundamental_data")
                .select("id")
                .eq("stock_code", stock_code)
                .eq("year", year)
                .execute()
            )
            if existing.data:
                (
                    supabase.table("fundamental_data")
                    .update(record)
                    .eq("stock_code", stock_code)
                    .eq("year", year)
                    .execute()
                )
                print(f"  [OK] 更新 {stock_code} {year}")
            else:
                supabase.table("fundamental_data").insert(record).execute()
                print(f"  [OK] 新增 {stock_code} {year}")
        except Exception as exc:
            print(f"  [ERROR] 上傳失敗 {stock_code} {year}: {exc}")
            return False

    return True


if __name__ == "__main__":
    from report_downloader import download_financial_report

    data = download_financial_report("2330", years=5)
    print("\n開始上傳到 Supabase...")
    ok = upload_to_supabase(data)
    print("\n上傳完成" if ok else "\n上傳失敗")
