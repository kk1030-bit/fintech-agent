import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# 匯入你前面寫好的爬蟲模組
from fred_scraper import get_fred_data
from tw_market_scraper import get_market_data

def upload_to_supabase(all_data):
    """
    負責將整合後的資料上傳至 Supabase
    """
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError("找不到 Supabase 環境變數，請確認 .env 檔案設定。")
        
    supabase: Client = create_client(url, key)
    
    print("  -> 正在清理舊資料 (避免重複)...")
    for record in all_data:
        try:
            supabase.table("macro_data").delete().eq("date", record["date"]).eq("indicator", record["indicator"]).execute()
        except Exception as e:
            print(f"  [警告] 清理舊資料 ({record['date']}, {record['indicator']}) 時發生錯誤: {e}")

    print("  -> 正在批次寫入新資料...")
    response = supabase.table("macro_data").insert(all_data).execute()
    return len(response.data)

def main():
    print("="*50)
    print("🚀 啟動總經數據自動化更新排程")
    print("="*50)
    
    fred_data = []
    market_data = []
    
    # -------------------------
    # 步驟一：爬取 FRED 數據
    # -------------------------
    try:
        print("\n[1/3] 準備抓取 FRED 總經數據...")
        fred_data = get_fred_data()
        print(f"  -> ✅ FRED 抓取成功，共 {len(fred_data)} 筆。")
    except Exception as e:
        print(f"  -> ❌ FRED 爬蟲執行失敗: {e}")
        
    # -------------------------
    # 步驟二：爬取 Yahoo Finance 數據
    # -------------------------
    try:
        print("\n[2/3] 準備抓取 Yahoo Finance 大盤數據...")
        market_data = get_market_data()
        print(f"  -> ✅ Yahoo Finance 抓取成功，共 {len(market_data)} 筆。")
    except Exception as e:
        print(f"  -> ❌ Yahoo Finance 爬蟲執行失敗: {e}")
        
    # -------------------------
    # 整合數據
    # -------------------------
    all_data = fred_data + market_data
    
    if not all_data:
        print("\n❌ 嚴重錯誤：沒有抓取到任何資料，排程終止。")
        sys.exit(1)
        
    # 計算摘要要用的統計資訊
    unique_indicators = set([item['indicator'] for item in all_data])
    
    # -------------------------
    # 步驟三：上傳至 Supabase
    # -------------------------
    upload_success = False
    inserted_count = 0
    try:
        print(f"\n[3/3] 準備上傳 {len(all_data)} 筆資料至 Supabase...")
        inserted_count = upload_to_supabase(all_data)
        upload_success = True
    except Exception as e:
        print(f"  -> ❌ Supabase 上傳失敗: {e}")
        
    # -------------------------
    # 步驟四：印出執行摘要報告
    # -------------------------
    print("\n" + "="*50)
    print("📊 執行摘要報告")
    print("="*50)
    print(f"🔸 涵蓋指標總數 : {len(unique_indicators)} 個")
    print(f"   ({', '.join(unique_indicators)})")
    print(f"🔸 嘗試處理筆數 : {len(all_data)} 筆")
    
    if upload_success:
        print(f"✅ 最終上傳狀態 : 成功 (成功寫入 {inserted_count} 筆)")
    else:
        print(f"❌ 最終上傳狀態 : 失敗 (請往上查看錯誤訊息)")
    print("="*50)

if __name__ == "__main__":
    main()