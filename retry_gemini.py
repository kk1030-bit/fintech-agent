import time
from report_downloader import download_financial_report
from gemini_analyzer import analyze_financials
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# 找出沒有 summary 的股票
result = supabase.table('fundamental_data').select('stock_code, company, year, summary').execute()
no_analysis = {}
for r in result.data:
    if not r.get('summary'):
        code = r['stock_code']
        if code not in no_analysis:
            no_analysis[code] = r.get('company', '')

stocks = list(no_analysis.items())
print(f"共 {len(stocks)} 支待補，今天最多跑 18 支")
stocks = stocks[:18]

for i, (code, name) in enumerate(stocks):
    print(f"[{i+1}/{len(stocks)}] {code} {name}...")
    try:
        data = download_financial_report(code, years=5)
        gemini_result = analyze_financials(data, code, name)
        if gemini_result.get('summary'):
            for d in data:
                if d.get('revenue') is None:
                    continue
                supabase.table('fundamental_data').update({
                    'summary': gemini_result.get('summary'),
                    'strengths': gemini_result.get('strengths'),
                    'risks': gemini_result.get('risks'),
                    'fcf_forecast': gemini_result.get('fcf_forecast'),
                }).eq('stock_code', code).eq('year', d['year']).execute()
            print(f"  ✅ 補完")
        else:
            print(f"  ❌ Gemini 無回應，配額用完")
            break
    except Exception as e:
        print(f"  ❌ 錯誤：{e}")
        break
    time.sleep(5)

print("\n今天補跑完成！明天繼續執行 python retry_gemini.py")
