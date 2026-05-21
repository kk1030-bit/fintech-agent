"""FinMind financial data downloader.

It fetches income statement, cash-flow statement, balance sheet, PER/PBR,
price, and stock info from FinMind's public v4 API, then returns annual records
suitable for DCF.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"


def finmind_token() -> str | None:
    """Read an optional FinMind token from .env."""

    load_dotenv(ROOT_DIR / ".env")
    return os.getenv("FINMIND_TOKEN") or None


def fetch_finmind_dataset(
    dataset: str,
    stock_code: str,
    start_date: str,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Fetch a FinMind dataset and return it as a DataFrame."""

    params: dict[str, Any] = {
        "dataset": dataset,
        "data_id": stock_code,
        "start_date": start_date,
    }
    if end_date:
        params["end_date"] = end_date
    token = finmind_token()
    if token:
        params["token"] = token

    response = requests.get(FINMIND_API_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind {dataset} 回傳失敗：{payload.get('msg')}")
    return pd.DataFrame(payload.get("data") or [])


def fetch_stock_name(stock_code: str) -> str:
    """Fetch the stock name from FinMind TaiwanStockInfo."""

    try:
        params: dict[str, Any] = {"dataset": "TaiwanStockInfo", "data_id": stock_code}
        token = finmind_token()
        if token:
            params["token"] = token
        response = requests.get(FINMIND_API_URL, params=params, timeout=30)
        response.raise_for_status()
        rows = response.json().get("data") or []
    except Exception:
        return stock_code
    for row in rows:
        if row.get("stock_name"):
            return str(row["stock_name"])
    return stock_code


def build_fcf_forecast(records: list[dict[str, Any]]) -> list[float]:
    """Create a simple five-year FCF forecast from the latest FinMind history."""

    fcfs = [float(row["free_cash_flow"]) for row in records if row.get("free_cash_flow") is not None]
    if not fcfs:
        return []
    latest = fcfs[-1]
    if len(fcfs) >= 2 and fcfs[-2]:
        growth = latest / fcfs[-2] - 1
        growth = max(min(growth, 0.12), 0.03)
    else:
        growth = 0.05
    forecast = []
    value = latest
    for _ in range(5):
        value *= 1 + growth
        forecast.append(round(value, 2))
    return forecast


def _annual_income_statement(financial_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate FinMind quarterly income statement rows into annual values."""

    if financial_df.empty:
        return pd.DataFrame()
    target_types = ["Revenue", "OperatingIncome", "IncomeAfterTaxes"]
    df = financial_df[financial_df["type"].isin(target_types)].copy()
    df["year"] = pd.to_datetime(df["date"]).dt.year.astype(str)
    annual = df.pivot_table(index="year", columns="type", values="value", aggfunc="sum")
    annual = annual.rename(
        columns={
            "Revenue": "revenue",
            "OperatingIncome": "operating_income",
            "IncomeAfterTaxes": "net_income",
        }
    )
    return annual.reset_index()


def _annual_cash_flow(cashflow_df: pd.DataFrame) -> pd.DataFrame:
    """Use 12/31 cumulative cash-flow rows to compute free cash flow."""

    if cashflow_df.empty:
        return pd.DataFrame()
    target_types = [
        "CashFlowsFromOperatingActivities",
        "NetCashInflowFromOperatingActivities",
        "PropertyAndPlantAndEquipment",
    ]
    df = cashflow_df[cashflow_df["type"].isin(target_types)].copy()
    df = df[df["date"].astype(str).str.endswith("12-31")]
    if df.empty:
        return pd.DataFrame()

    df["year"] = pd.to_datetime(df["date"]).dt.year.astype(str)
    pivot = df.pivot_table(index="year", columns="type", values="value", aggfunc="last")
    cfo = pivot.get("CashFlowsFromOperatingActivities")
    if cfo is None:
        cfo = pivot.get("NetCashInflowFromOperatingActivities")
    capex = pivot.get("PropertyAndPlantAndEquipment")
    result = pd.DataFrame(index=pivot.index)
    result["operating_cash_flow"] = cfo
    result["capital_expenditure"] = capex
    result["free_cash_flow"] = cfo.fillna(0) + capex.fillna(0)
    return result.reset_index()


def _annual_balance_sheet(balance_df: pd.DataFrame) -> pd.DataFrame:
    """Compute shares outstanding and net debt from annual balance sheet rows."""

    if balance_df.empty:
        return pd.DataFrame()
    target_types = [
        "OrdinaryShare",
        "CapitalStock",
        "CashAndCashEquivalents",
        "BondsPayable",
        "LongtermBorrowings",
        "ShorttermBorrowings",
        "ShortTermBorrowings",
    ]
    df = balance_df[balance_df["type"].isin(target_types)].copy()
    df = df[df["date"].astype(str).str.endswith("12-31")]
    if df.empty:
        return pd.DataFrame()

    df["year"] = pd.to_datetime(df["date"]).dt.year.astype(str)
    pivot = df.pivot_table(index="year", columns="type", values="value", aggfunc="last")
    result = pd.DataFrame(index=pivot.index)
    ordinary_share = pivot.get("OrdinaryShare")
    if ordinary_share is None:
        ordinary_share = pivot.get("CapitalStock")
    if ordinary_share is not None:
        result["shares_outstanding"] = ordinary_share / 10

    cash = pivot.get("CashAndCashEquivalents", 0)
    debt = 0
    for column in ["BondsPayable", "LongtermBorrowings", "ShorttermBorrowings", "ShortTermBorrowings"]:
        if column in pivot:
            debt = debt + pivot[column].fillna(0)
    result["net_debt"] = debt - cash
    return result.reset_index()


def _annual_per_pb(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch the last PER/PBR value in each year from FinMind."""

    try:
        per_df = fetch_finmind_dataset("TaiwanStockPER", stock_code, start_date, end_date)
    except Exception:
        return pd.DataFrame()
    if per_df.empty:
        return pd.DataFrame()
    per_df["year"] = pd.to_datetime(per_df["date"]).dt.year.astype(str)
    latest = per_df.sort_values("date").groupby("year").tail(1)
    latest = latest.rename(columns={"PER": "pe_ratio", "PBR": "pb_ratio"})
    return latest[["year", "pe_ratio", "pb_ratio"]]


def fetch_price_history(stock_code: str, months: int = 12) -> list[dict[str, Any]]:
    """Fetch monthly closing prices from FinMind TaiwanStockPrice."""

    today = date.today()
    start_year = max(today.year - 2, 2000)
    try:
        price_df = fetch_finmind_dataset(
            "TaiwanStockPrice",
            stock_code,
            f"{start_year}-01-01",
            today.isoformat(),
        )
    except Exception:
        return []
    if price_df.empty:
        return []

    price_df["date"] = pd.to_datetime(price_df["date"])
    price_df = price_df.sort_values("date")
    monthly = price_df.set_index("date")["close"].resample("ME").last().dropna().tail(months)
    return [
        {"date": index.strftime("%Y-%m"), "price": round(float(value), 2)}
        for index, value in monthly.items()
    ]


def download_financial_report(stock_code: str, years: int = 5) -> list[dict[str, Any]]:
    """Fetch the latest annual financial records from FinMind."""

    current_year = date.today().year
    start_date = f"{current_year - years - 2}-01-01"
    end_date = date.today().isoformat()
    print(f"正在用 FinMind 抓取 {stock_code} 近 {years} 年財務數據...")

    financial_df = fetch_finmind_dataset("TaiwanStockFinancialStatements", stock_code, start_date, end_date)
    cashflow_df = fetch_finmind_dataset("TaiwanStockCashFlowsStatement", stock_code, start_date, end_date)
    balance_df = fetch_finmind_dataset("TaiwanStockBalanceSheet", stock_code, start_date, end_date)

    annual = _annual_income_statement(financial_df)
    annual = annual.merge(_annual_cash_flow(cashflow_df), on="year", how="outer")
    annual = annual.merge(_annual_balance_sheet(balance_df), on="year", how="left")
    annual = annual.merge(_annual_per_pb(stock_code, start_date, end_date), on="year", how="left")
    annual = annual.dropna(subset=["revenue", "operating_income", "net_income", "free_cash_flow"])
    annual = annual.sort_values("year").tail(years)

    company = fetch_stock_name(stock_code)
    records: list[dict[str, Any]] = []
    for _, row in annual.iterrows():
        record = {
            "stock_code": stock_code,
            "year": str(row["year"]),
            "company": company,
            "currency": "TWD",
            "revenue": float(row["revenue"]),
            "operating_income": float(row["operating_income"]),
            "net_income": float(row["net_income"]),
            "operating_cash_flow": float(row["operating_cash_flow"]),
            "capital_expenditure": float(row["capital_expenditure"]),
            "free_cash_flow": float(row["free_cash_flow"]),
            "shares_outstanding": float(row["shares_outstanding"]) if pd.notna(row.get("shares_outstanding")) else None,
            "net_debt": float(row["net_debt"]) if pd.notna(row.get("net_debt")) else None,
            "pe_ratio": float(row["pe_ratio"]) if pd.notna(row.get("pe_ratio")) else None,
            "pb_ratio": float(row["pb_ratio"]) if pd.notna(row.get("pb_ratio")) else None,
            "data_source": "finmind",
        }
        records.append(record)
        print(
            f"  [OK] {record['year']} revenue={record['revenue']:.0f}, "
            f"op_income={record['operating_income']:.0f}, "
            f"net_income={record['net_income']:.0f}, "
            f"fcf={record['free_cash_flow']:.0f}"
        )

    forecast = build_fcf_forecast(records)
    if records and forecast:
        records[-1]["fcf_forecast"] = forecast
    return records


if __name__ == "__main__":
    data = download_financial_report("2330", years=5)
    print("\n========== 完整結果 ==========")
    for item in data:
        print(item)
