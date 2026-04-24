"""W3-4 資料整合主程式。

執行範例：
    python main.py 2330
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client

from valuation_agent.chart_builder import (
    plot_dcf_waterfall,
    plot_financial_ratios,
    plot_stock_price,
)
from valuation_agent.dcf_model import calculate_dcf_details

ROOT_DIR = Path(__file__).resolve().parent
PAGE_SIZE = 1000


def get_supabase_client() -> Client:
    """從 .env 讀取 Supabase 設定並建立連線。"""

    load_dotenv(ROOT_DIR / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("找不到 SUPABASE_URL 或 SUPABASE_KEY，請確認 .env 設定。")

    return create_client(url, key)


def fetch_all_rows(client: Client, table_name: str) -> list[dict[str, Any]]:
    """分頁讀取 Supabase 資料表所有資料。"""

    rows: list[dict[str, Any]] = []
    start = 0

    while True:
        end = start + PAGE_SIZE - 1
        response = client.table(table_name).select("*").range(start, end).execute()
        batch = response.data or []
        rows.extend(batch)

        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    return rows


def load_macro_data(client: Client) -> pd.DataFrame:
    """從 macro_data 讀取所有總經指標資料，整理成 DataFrame。"""

    rows = fetch_all_rows(client, "macro_data")
    macro_df = pd.DataFrame(rows)

    if macro_df.empty:
        raise ValueError("macro_data 目前沒有資料。")

    if "value" in macro_df.columns:
        macro_df["value"] = pd.to_numeric(macro_df["value"], errors="coerce")
    if "date" in macro_df.columns:
        macro_df = macro_df.sort_values("date").reset_index(drop=True)

    return macro_df


def load_fundamental_data(client: Client, stock_code: str) -> dict[str, Any]:
    """從 fundamental_data 讀取指定股票資料，整理成 dict。"""

    response = (
        client.table("fundamental_data")
        .select("*")
        .eq("stock_code", stock_code)
        .execute()
    )
    rows = response.data or []

    if not rows:
        sample_response = (
            client.table("fundamental_data")
            .select("stock_code")
            .limit(10)
            .execute()
        )
        sample_codes = sorted(
            {
                str(row.get("stock_code"))
                for row in (sample_response.data or [])
                if row.get("stock_code")
            }
        )
        if sample_codes:
            available = ", ".join(sample_codes)
            raise ValueError(
                f"fundamental_data 找不到 stock_code={stock_code} 的資料。"
                f"目前可用股票代號：{available}"
            )
        raise ValueError("fundamental_data 目前沒有任何資料，請先完成財報資料上傳。")

    rows = sorted(rows, key=lambda row: str(row.get("year", "")))
    latest = rows[-1]

    return {
        "stock_code": stock_code,
        "company": latest.get("company") or stock_code,
        "latest": latest,
        "records": rows,
        "summary": latest.get("summary"),
        "strengths": latest.get("strengths"),
        "risks": latest.get("risks"),
        "fcf_forecast": latest.get("fcf_forecast"),
    }


def to_float(value: Any) -> float | None:
    """把 Supabase 讀出的數字欄位轉成 float。"""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def numbers_from_forecast(value: Any) -> list[float]:
    """從 fcf_forecast 欄位解析數字。"""

    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]

    if isinstance(value, dict):
        numbers: list[float] = []
        for item in value.values():
            numbers.extend(numbers_from_forecast(item))
        return numbers

    if isinstance(value, list):
        numbers: list[float] = []
        for item in value:
            numbers.extend(numbers_from_forecast(item))
        return numbers

    text = str(value).strip()
    if not text:
        return []

    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        parsed = None

    if parsed is not None and parsed is not value:
        parsed_numbers = numbers_from_forecast(parsed)
        if parsed_numbers:
            return parsed_numbers

    numbers: list[float] = []
    for line in text.splitlines() or [text]:
        target = line.split(":", 1)[-1]
        matches = re.findall(r"-?\d+(?:\.\d+)?", target.replace(",", ""))
        if matches:
            numbers.append(float(matches[-1]))

    return numbers


def build_fcf_forecast(fundamental_data: dict[str, Any]) -> list[float]:
    """優先使用 Gemini FCF 預測，沒有時使用歷史 free_cash_flow 補足 5 年。"""

    forecast = numbers_from_forecast(fundamental_data.get("fcf_forecast"))
    if len(forecast) >= 5:
        return forecast[:5]

    historical_fcf = [
        to_float(row.get("free_cash_flow"))
        for row in fundamental_data["records"]
        if to_float(row.get("free_cash_flow")) is not None
    ]

    if not historical_fcf:
        raise ValueError("fundamental_data 沒有可用的 free_cash_flow 或 fcf_forecast。")

    free_cash_flows = historical_fcf[-5:]
    while len(free_cash_flows) < 5:
        free_cash_flows.append(free_cash_flows[-1] * 1.03)

    return free_cash_flows[:5]


def env_float(names: list[str], default: float) -> float:
    """依序讀取多個環境變數名稱，沒有就用預設值。"""

    for name in names:
        value = os.getenv(name)
        if value:
            parsed = to_float(value)
            if parsed is not None:
                return parsed
    return default


def calculate_intrinsic_value(fundamental_data: dict[str, Any]) -> dict[str, Any]:
    """呼叫 dcf_model.py 計算每股內在價值。"""

    stock_code = fundamental_data["stock_code"]
    free_cash_flows = build_fcf_forecast(fundamental_data)
    wacc = env_float(["DCF_WACC", "DEFAULT_WACC"], 0.09)
    terminal_growth = env_float(["TERMINAL_GROWTH", "DCF_TERMINAL_GROWTH"], 0.03)
    net_debt = env_float([f"NET_DEBT_{stock_code}", "DEFAULT_NET_DEBT"], 0.0)
    shares_outstanding = env_float(
        [f"SHARES_OUTSTANDING_{stock_code}", "DEFAULT_SHARES_OUTSTANDING"],
        1.0,
    )

    if shares_outstanding == 1.0:
        print("提醒：未在 .env 設定流通股數，DCF 會先以 1 作為預設值。")

    details = calculate_dcf_details(
        free_cash_flows=free_cash_flows,
        wacc=wacc,
        terminal_growth=terminal_growth,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    details["free_cash_flows"] = free_cash_flows
    details["net_debt"] = net_debt
    details["shares_outstanding"] = shares_outstanding
    return details


def stock_price_series(
    macro_df: pd.DataFrame,
    fundamental_data: dict[str, Any],
) -> tuple[list[str], list[float]]:
    """準備股價走勢圖資料。

    若 macro_data 沒有指定股票價格，會使用 TWII 或第一組可用市場指標作為走勢代理。
    """

    stock_code = fundamental_data["stock_code"]
    company = fundamental_data["company"]

    if {"indicator", "date", "value"}.issubset(macro_df.columns):
        candidates = [stock_code, company, "TWII", "S&P500"]
        for indicator in candidates:
            subset = macro_df[macro_df["indicator"].astype(str).str.contains(indicator, na=False)]
            subset = subset.dropna(subset=["date", "value"]).tail(12)
            if len(subset) >= 2:
                return subset["date"].astype(str).tolist(), subset["value"].astype(float).tolist()

        for _, subset in macro_df.dropna(subset=["date", "value"]).groupby("indicator"):
            subset = subset.tail(12)
            if len(subset) >= 2:
                return subset["date"].astype(str).tolist(), subset["value"].astype(float).tolist()

    records = fundamental_data["records"]
    dates = [str(row.get("year")) for row in records if row.get("year") is not None]
    prices = [to_float(row.get("revenue")) for row in records]
    prices = [value for value in prices if value is not None]

    if len(dates) >= 2 and len(prices) >= 2:
        return dates[-len(prices) :], prices

    raise ValueError("無法建立股價走勢圖資料。")


def ratio_series(fundamental_data: dict[str, Any]) -> tuple[list[str], list[float], list[float]]:
    """準備 P/E 與 P/B 圖表資料。

    若 fundamental_data 沒有 pe_ratio/pb_ratio 欄位，就用現有財報欄位建立可視化替代值。
    """

    years: list[str] = []
    pe_list: list[float] = []
    pb_list: list[float] = []

    for row in fundamental_data["records"]:
        year = row.get("year")
        if year is None:
            continue

        pe = to_float(row.get("pe_ratio") or row.get("pe"))
        pb = to_float(row.get("pb_ratio") or row.get("pb"))

        revenue = to_float(row.get("revenue"))
        net_income = to_float(row.get("net_income"))
        operating_income = to_float(row.get("operating_income"))

        if pe is None and revenue and net_income:
            pe = abs(revenue / net_income)
        if pb is None and revenue and operating_income:
            pb = abs(revenue / operating_income)

        if pe is not None and pb is not None:
            years.append(str(year))
            pe_list.append(round(pe, 2))
            pb_list.append(round(pb, 2))

    if len(years) < 2:
        raise ValueError("無法建立 P/E 與 P/B 圖表資料。")

    return years, pe_list, pb_list


def generate_charts(
    macro_df: pd.DataFrame,
    fundamental_data: dict[str, Any],
    dcf_details: dict[str, Any],
) -> list[str]:
    """呼叫 chart_builder.py 生成三張圖表。"""

    stock_name = fundamental_data["company"]

    stock_dates, stock_prices = stock_price_series(macro_df, fundamental_data)
    ratio_years, pe_list, pb_list = ratio_series(fundamental_data)

    waterfall_components = ["五年 FCF 現值", "終端價值現值", "淨負債調整"]
    waterfall_values = [
        dcf_details["pv_fcf"],
        dcf_details["pv_terminal"],
        -dcf_details["net_debt"],
    ]

    return [
        plot_stock_price(stock_dates, stock_prices, stock_name),
        plot_financial_ratios(ratio_years, pe_list, pb_list, stock_name),
        plot_dcf_waterfall(waterfall_components, waterfall_values, stock_name),
    ]


def run_analysis(stock_code: str) -> list[str]:
    """執行完整 W3-4 資料整合流程。"""

    client = get_supabase_client()
    print(f"開始分析股票代號：{stock_code}")

    macro_df = load_macro_data(client)
    print(f"已讀取 macro_data：{len(macro_df)} 筆")

    fundamental_data = load_fundamental_data(client, stock_code)
    print(f"已讀取 fundamental_data：{len(fundamental_data['records'])} 筆")

    dcf_details = calculate_intrinsic_value(fundamental_data)
    print(f"每股內在價值：{dcf_details['intrinsic_value_per_share']:,.2f}")

    chart_paths = generate_charts(macro_df, fundamental_data, dcf_details)
    for path in chart_paths:
        print(f"圖表已輸出：{path}")

    print(f"分析完成，共產出 {len(chart_paths)} 張圖表")
    return chart_paths


def main() -> None:
    stock_code = sys.argv[1] if len(sys.argv) > 1 else input("請輸入股票代號：").strip()
    if not stock_code:
        raise ValueError("stock_code 不可為空。")
    try:
        run_analysis(stock_code)
    except Exception as exc:
        print(f"分析失敗：{exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
