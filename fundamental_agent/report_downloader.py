"""Compatibility wrapper for the root FinMind downloader."""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from report_downloader import download_financial_report, fetch_price_history  # noqa: E402,F401


if __name__ == "__main__":
    data = download_financial_report("2330", years=5)
    for item in data:
        print(item)
