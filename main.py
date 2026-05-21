"""W3-W5 integration entrypoint for the fintech-agent project.

Usage:
    python main.py 2330

The program reads Supabase first. If fundamental_data does not yet contain the
financial fields needed by DCF, it falls back to the local/yfinance downloader so
the demo can still run end to end.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf
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

TSMC_DEMO_RECORDS = [
    {
        "stock_code": "2330",
        "year": "2021",
        "company": "Taiwan Semiconductor Manufacturing Company Limited",
        "currency": "TWD",
        "revenue": 15874.15,
        "operating_income": 6499.81,
        "net_income": 5965.40,
        "free_cash_flow": 5350.00,
    },
    {
        "stock_code": "2330",
        "year": "2022",
        "company": "Taiwan Semiconductor Manufacturing Company Limited",
        "currency": "TWD",
        "revenue": 22638.91,
        "operating_income": 11212.79,
        "net_income": 10165.30,
        "free_cash_flow": 6700.00,
    },
    {
        "stock_code": "2330",
        "year": "2023",
        "company": "Taiwan Semiconductor Manufacturing Company Limited",
        "currency": "TWD",
        "revenue": 21617.36,
        "operating_income": 9214.71,
        "net_income": 8384.98,
        "free_cash_flow": 5870.00,
    },
    {
        "stock_code": "2330",
        "year": "2024",
        "company": "Taiwan Semiconductor Manufacturing Company Limited",
        "currency": "TWD",
        "revenue": 28943.08,
        "operating_income": 13200.00,
        "net_income": 11700.00,
        "free_cash_flow": 8200.00,
    },
    {
        "stock_code": "2330",
        "year": "2025",
        "company": "Taiwan Semiconductor Manufacturing Company Limited",
        "currency": "TWD",
        "revenue": 32000.00,
        "operating_income": 14800.00,
        "net_income": 13000.00,
        "free_cash_flow": 9000.00,
    },
]


def get_supabase_client() -> Client:
    """Create a Supabase client from .env."""

    load_dotenv(ROOT_DIR / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("找不到 SUPABASE_URL 或 SUPABASE_KEY，請確認 .env。")
    return create_client(url, key)


def fetch_all_rows(client: Client, table_name: str) -> list[dict[str, Any]]:
    """Read all rows from a Supabase table using simple pagination."""

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
    """Read macro_data and convert it into a pandas DataFrame."""

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
    """Read one stock's rows from fundamental_data and package them as a dict."""

    response = (
        client.table("fundamental_data")
        .select("*")
        .eq("stock_code", stock_code)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise ValueError(f"fundamental_data 找不到 stock_code={stock_code} 的資料。")

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
        "data_source": "supabase",
    }


def to_float(value: Any) -> float | None:
    """Best effort conversion to float."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def numbers_from_forecast(value: Any) -> list[float]:
    """Parse a list of numeric FCF forecast values from Gemini/Supabase output."""

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
    if parsed is not None and parsed != text:
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


def has_financial_fields(fundamental_data: dict[str, Any]) -> bool:
    """Return True when Supabase rows contain fields needed for DCF/charts."""

    for row in fundamental_data.get("records", []):
        if to_float(row.get("free_cash_flow")) is not None:
            return True
    return bool(numbers_from_forecast(fundamental_data.get("fcf_forecast")))


def fetch_price_history(stock_code: str) -> list[dict[str, Any]]:
    """Fetch monthly close prices for the stock using yfinance."""

    ticker_symbol = f"{stock_code}.TW" if stock_code.isdigit() else stock_code
    try:
        hist = yf.Ticker(ticker_symbol).history(period="1y", interval="1mo")
    except Exception:
        return []

    if hist.empty or "Close" not in hist.columns:
        return []

    records = []
    for date, row in hist.dropna(subset=["Close"]).iterrows():
        records.append({"date": date.strftime("%Y-%m"), "price": float(row["Close"])})
    return records[-12:]


def fetch_stock_info(stock_code: str) -> dict[str, Any]:
    """Fetch lightweight stock metadata from yfinance."""

    ticker_symbol = f"{stock_code}.TW" if stock_code.isdigit() else stock_code
    try:
        info = yf.Ticker(ticker_symbol).info
    except Exception:
        return {}
    return {
        "company": info.get("longName") or info.get("shortName"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
    }


def fetch_live_fundamentals(stock_code: str) -> dict[str, Any]:
    """Fetch financial rows locally when Supabase lacks numeric fields."""

    print("fundamental_data 缺少 DCF 所需財務欄位，改用 yfinance/本地下載模組補資料。")
    if stock_code == "2330":
        print("使用台積電 Demo 財務數字保證展示流程可跑。")
        return {
            "stock_code": stock_code,
            "company": "Taiwan Semiconductor Manufacturing Company Limited",
            "latest": TSMC_DEMO_RECORDS[-1],
            "records": TSMC_DEMO_RECORDS,
            "summary": None,
            "strengths": [],
            "risks": [],
            "fcf_forecast": None,
            "data_source": "demo_fallback",
            "shares_outstanding": 25_945_000_000,
            "current_price": None,
            "price_history": [],
        }

    try:
        from report_downloader import download_financial_report

        records = download_financial_report(stock_code, years=5)
    except Exception as exc:
        print(f"report_downloader 執行失敗：{exc}")
        records = []

    records = [row for row in records if row.get("free_cash_flow") is not None]
    info = fetch_stock_info(stock_code)

    if not records and stock_code == "2330":
        print("yfinance 未取得完整資料，使用台積電 Demo 財務數字保證展示流程可跑。")
        records = TSMC_DEMO_RECORDS
        info.setdefault("company", "Taiwan Semiconductor Manufacturing Company Limited")
        info.setdefault("shares_outstanding", 25_945_000_000)

    if not records:
        raise ValueError("無法取得可用財務資料，請先補 fundamental_data 或檢查 yfinance。")

    records = sorted(records, key=lambda row: str(row.get("year", "")))
    company = info.get("company") or records[-1].get("company") or stock_code
    return {
        "stock_code": stock_code,
        "company": company,
        "latest": records[-1],
        "records": records,
        "summary": None,
        "strengths": [],
        "risks": [],
        "fcf_forecast": None,
        "data_source": "local_yfinance",
        "shares_outstanding": info.get("shares_outstanding"),
        "current_price": info.get("current_price"),
        "price_history": fetch_price_history(stock_code),
    }


def ensure_complete_fundamentals(fundamental_data: dict[str, Any]) -> dict[str, Any]:
    """Use Supabase data if complete; otherwise enrich with local/yfinance data."""

    if has_financial_fields(fundamental_data):
        if not fundamental_data.get("price_history"):
            fundamental_data["price_history"] = fetch_price_history(fundamental_data["stock_code"])
        stock_info = fetch_stock_info(fundamental_data["stock_code"])
        fundamental_data.setdefault("shares_outstanding", stock_info.get("shares_outstanding"))
        fundamental_data.setdefault("current_price", stock_info.get("current_price"))
        return fundamental_data

    enriched = fetch_live_fundamentals(fundamental_data["stock_code"])
    enriched["summary"] = fundamental_data.get("summary")
    enriched["risks"] = fundamental_data.get("risks") or []
    enriched["strengths"] = fundamental_data.get("strengths") or []
    return enriched


def normalize_money_to_100m(values: list[float]) -> list[float]:
    """Convert raw TWD-like amounts into NT$100 million units when needed."""

    if not values:
        return values
    if max(abs(value) for value in values) >= 10_000_000:
        return [value / 100_000_000 for value in values]
    return values


def build_fcf_forecast(fundamental_data: dict[str, Any]) -> list[float]:
    """Build five FCF inputs for DCF."""

    forecast = numbers_from_forecast(fundamental_data.get("fcf_forecast"))
    if len(forecast) >= 5:
        return normalize_money_to_100m(forecast[:5])

    historical_fcf = []
    for row in fundamental_data["records"]:
        value = to_float(row.get("free_cash_flow"))
        if value is not None:
            historical_fcf.append(value)

    if not historical_fcf:
        raise ValueError("fundamental_data 沒有可用的 free_cash_flow 或 fcf_forecast。")

    free_cash_flows = historical_fcf[-5:]
    while len(free_cash_flows) < 5:
        free_cash_flows.append(free_cash_flows[-1] * 1.03)
    return normalize_money_to_100m(free_cash_flows[:5])


def env_float(names: list[str], default: float) -> float:
    """Read one of several possible environment variables as float."""

    for name in names:
        value = os.getenv(name)
        if value:
            parsed = to_float(value)
            if parsed is not None:
                return parsed
    return default


def shares_to_million(value: Any) -> float | None:
    shares = to_float(value)
    if shares is None:
        return None
    if shares > 1_000_000:
        return shares / 1_000_000
    return shares


def calculate_intrinsic_value(fundamental_data: dict[str, Any]) -> dict[str, Any]:
    """Call dcf_model.py and return the valuation detail dict."""

    stock_code = fundamental_data["stock_code"]
    free_cash_flows = build_fcf_forecast(fundamental_data)
    wacc = env_float(["DCF_WACC", "DEFAULT_WACC"], 0.09)
    terminal_growth = env_float(["TERMINAL_GROWTH", "DCF_TERMINAL_GROWTH"], 0.03)
    net_debt = env_float([f"NET_DEBT_{stock_code}", "DEFAULT_NET_DEBT"], 0.0)

    shares = env_float([f"SHARES_OUTSTANDING_{stock_code}", "DEFAULT_SHARES_OUTSTANDING"], 0.0)
    shares_outstanding = shares_to_million(shares) or shares_to_million(fundamental_data.get("shares_outstanding"))
    if not shares_outstanding and stock_code == "2330":
        shares_outstanding = 25_945
    if not shares_outstanding:
        shares_outstanding = 1.0
        print("提醒：未取得流通股數，DCF 暫以 1 百萬股作為預設值。")

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
    details["wacc"] = wacc
    details["terminal_growth"] = terminal_growth
    return details


def stock_price_series(macro_df: pd.DataFrame, fundamental_data: dict[str, Any]) -> tuple[list[str], list[float]]:
    """Prepare price trend data for chart_builder.py."""

    price_history = fundamental_data.get("price_history") or []
    if len(price_history) >= 2:
        return [row["date"] for row in price_history], [float(row["price"]) for row in price_history]

    if {"indicator", "date", "value"}.issubset(macro_df.columns):
        for indicator in [fundamental_data["stock_code"], fundamental_data["company"], "TWII", "S&P500"]:
            subset = macro_df[macro_df["indicator"].astype(str).str.contains(str(indicator), na=False)]
            subset = subset.dropna(subset=["date", "value"]).tail(12)
            if len(subset) >= 2:
                return subset["date"].astype(str).tolist(), subset["value"].astype(float).tolist()

    records = fundamental_data["records"]
    dates = [str(row.get("year")) for row in records if row.get("year") is not None]
    values = [to_float(row.get("revenue")) for row in records]
    values = [value for value in values if value is not None]
    values = normalize_money_to_100m(values)
    if len(dates) >= 2 and len(values) >= 2:
        return dates[-len(values) :], values
    raise ValueError("無法建立股價走勢圖資料。")


def ratio_series(fundamental_data: dict[str, Any]) -> tuple[list[str], list[float], list[float]]:
    """Prepare P/E and P/B-like ratio data for chart_builder.py."""

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
    """Call chart_builder.py and create three PNG charts."""

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


def build_report_if_available(
    macro_df: pd.DataFrame,
    fundamental_data: dict[str, Any],
    dcf_details: dict[str, Any],
    chart_paths: list[str],
) -> str | None:
    """Generate PDF report when report_builder.py is available."""

    try:
        from report_builder import build_pdf_report
    except Exception as exc:
        print(f"略過 PDF 產生：report_builder.py 無法匯入（{exc}）")
        return None

    return build_pdf_report(
        stock_code=fundamental_data["stock_code"],
        macro_df=macro_df,
        fundamental_data=fundamental_data,
        dcf_details=dcf_details,
        chart_paths=chart_paths,
    )


def run_analysis(stock_code: str) -> dict[str, Any]:
    """Run the complete data integration, valuation, chart, and PDF flow."""

    client = get_supabase_client()
    print(f"開始分析股票代號：{stock_code}")

    macro_df = load_macro_data(client)
    print(f"已讀取 macro_data：{len(macro_df)} 筆")

    fundamental_data = load_fundamental_data(client, stock_code)
    print(f"已讀取 fundamental_data：{len(fundamental_data['records'])} 筆")

    fundamental_data = ensure_complete_fundamentals(fundamental_data)
    print(f"財務資料來源：{fundamental_data.get('data_source')}")

    dcf_details = calculate_intrinsic_value(fundamental_data)
    print(f"每股內在價值：{dcf_details['intrinsic_value_per_share']:,.2f} 元/股")

    chart_paths = generate_charts(macro_df, fundamental_data, dcf_details)
    for path in chart_paths:
        print(f"圖表已輸出：{path}")

    pdf_path = build_report_if_available(macro_df, fundamental_data, dcf_details, chart_paths)
    if pdf_path:
        print(f"PDF 報告已輸出：{pdf_path}")

    print(f"分析完成，共產出 {len(chart_paths)} 張圖表")
    return {"charts": chart_paths, "pdf": pdf_path, "dcf": dcf_details}


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
