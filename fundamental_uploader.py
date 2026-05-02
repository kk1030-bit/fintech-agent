import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime

# 載入 .env
load_dotenv()

def upload_to_supabase(financial_data: list, gemini_result: dict = None) -> bool:
    """上傳財務數據到 Supabase fundamental_data 表"""
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    supabase = create_client(url, key)

    for d in financial_data:
        if d.get('revenue') is None:
            continue

        record = {
            'stock_code': d['stock_code'],
            'year': d['year'],
            'company': d['company'],
            'currency': d['currency'],
            'revenue': d['revenue'],
            'operating_income': d['operating_income'],
            'net_income': d['net_income'],
            'free_cash_flow': d['free_cash_flow'],
            'summary': gemini_result.get('summary') if gemini_result else None,
            'strengths': gemini_result.get('strengths') if gemini_result else None,
            'risks': gemini_result.get('risks') if gemini_result else None,
            'fcf_forecast': gemini_result.get('fcf_forecast') if gemini_result else None,
            'created_at': datetime.now().isoformat(),
        }

        try:
            # 先檢查是否已存在
            existing = supabase.table('fundamental_data') \
                .select('id') \
                .eq('stock_code', d['stock_code']) \
                .eq('year', d['year']) \
                .execute()

            if existing.data:
                # 已存在則更新
                supabase.table('fundamental_data') \
                    .update(record) \
                    .eq('stock_code', d['stock_code']) \
                    .eq('year', d['year']) \
                    .execute()
                print(f"  🔄 更新：{d['stock_code']} {d['year']}年")
            else:
                # 不存在則新增
                supabase.table('fundamental_data').insert(record).execute()
                print(f"  ✅ 新增：{d['stock_code']} {d['year']}年")

        except Exception as e:
            print(f"  ❌ 失敗：{d['stock_code']} {d['year']}年 → {e}")
            return False

    return True

if __name__ == "__main__":
    from report_downloader import download_financial_report
    data = download_financial_report("2330", years=5)
    print("\n正在上傳到 Supabase...")
    success = upload_to_supabase(data)
    print("\n✅ 上傳完成！" if success else "\n❌ 上傳失敗")
