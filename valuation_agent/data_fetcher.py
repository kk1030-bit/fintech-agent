"""Financial data fetcher for valuation_agent, powered by FinMind."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from report_downloader import download_financial_report  # noqa: E402


def fetch_stock_data(stock_code: str) -> dict | None:
    """Fetch DCF-ready financial data from FinMind."""

    try:
        records = download_financial_report(stock_code, years=5)
        if not records:
            return None
        latest = records[-1]
        return {
            "stock_code": stock_code,
            "company_name": latest.get("company", stock_code),
            "free_cash_flows": [row["free_cash_flow"] for row in records],
            "net_debt": latest.get("net_debt") or 0,
            "shares_outstanding": latest.get("shares_outstanding") or 1,
            "current_price": 0,
            "data_source": "finmind",
        }
    except Exception as exc:
        print(f"抓取失敗：{exc}")
        return None


if __name__ == "__main__":
    data = fetch_stock_data("2330")
    if data:
        print(f"自由現金流：{data['free_cash_flows']}")
