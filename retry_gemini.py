"""Compatibility script for backfilling rule-based financial analysis.

The old workflow used Gemini. The current workflow is deterministic and uses
FinMind data only, but this filename is kept so older notes still work.
"""

import os
import time

from dotenv import load_dotenv
from supabase import create_client

from financial_analyzer import analyze_financials
from report_downloader import download_financial_report

load_dotenv()
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

result = supabase.table("fundamental_data").select("stock_code, company").execute()
stocks = sorted({(row["stock_code"], row.get("company") or row["stock_code"]) for row in result.data or []})
print(f"共 {len(stocks)} 支待補自動化財務分析")

for index, (code, name) in enumerate(stocks, start=1):
    print(f"[{index}/{len(stocks)}] {code} {name}...")
    try:
        data = download_financial_report(code, years=5)
        analysis_result = analyze_financials(data, code, name)
        if not analysis_result.get("summary"):
            print("  [ERROR] 分析結果為空")
            continue
        from fundamental_uploader import upload_to_supabase

        upload_to_supabase(data, analysis_result)
        print("  [OK] 補完")
    except Exception as exc:
        print(f"  [ERROR] {exc}")
        break
    time.sleep(2)

print("\n自動化財務分析補跑完成。")
