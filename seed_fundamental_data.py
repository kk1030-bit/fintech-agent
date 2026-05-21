"""Seed Supabase fundamental_data with FinMind numeric values.

Usage:
    python seed_fundamental_data.py 2330

The script downloads annual financials from FinMind and uploads them through
fundamental_uploader.py. It works with the current compact Supabase schema by
storing numeric values as JSON in summary, and also supports a future schema
with dedicated numeric columns.
"""

from __future__ import annotations

import sys

from fundamental_uploader import upload_to_supabase
from report_downloader import download_financial_report


def seed(stock_code: str, years: int = 5) -> bool:
    """Download FinMind data and upload it to Supabase."""

    records = download_financial_report(stock_code, years=years)
    if not records:
        raise ValueError(f"FinMind 沒有回傳 {stock_code} 可用的財務資料。")

    print(f"\n準備上傳 {len(records)} 筆 FinMind 財務資料到 Supabase...")
    return upload_to_supabase(records)


def main() -> None:
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    ok = seed(stock_code, years)
    if not ok:
        sys.exit(1)
    print(f"\nFinMind 財務資料補完：{stock_code}，共 {years} 年。")


if __name__ == "__main__":
    main()
