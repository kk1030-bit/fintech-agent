import os
from dotenv import load_dotenv
from supabase import create_client, Client
from fred_scraper import get_fred_data
from tw_market_scraper import get_market_data

def main():
    """
    整合爬蟲數據，清除舊資料後批次上傳至 Supabase
    """
    # 載入環境變數
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("錯誤：找不到 Supabase 環境變數，請確認 .env 檔案設定。")
        return

    # 初始化 Supabase 客戶端
    supabase: Client = create_client(url, key)

    # 取得兩邊的數據
    fred_data = get_fred_data()
    market_data = get_market_data()

    # 合併所有資料
    all_data = fred_data + market_data
    
    if not all_data:
        print("沒有抓取到任何資料，取消上傳。")
        return

    print(f"\n共抓取 {len(all_data)} 筆資料，準備上傳至 Supabase...")

    # 1. 先清除 macro_data 表中同一日期、同一指標的舊資料（避免重複）
    print("正在清理舊資料...")
    for record in all_data:
        try:
            # 刪除條件：日期相同 且 指標相同
            supabase.table("marco_data").delete().eq("date", record["date"]).eq("indicator", record["indicator"]).execute()
        except Exception as e:
            print(f"清理舊資料 ({record['date']}, {record['indicator']}) 時發生錯誤: {e}")

    # 2. 批次 insert 新資料
    print("正在批次上傳新資料...")
    try:
        response = supabase.table("macro_data").insert(all_data).execute()
        
        # 3. 印出成功確認訊息
        inserted_count = len(response.data)
        print(f"✅ 成功上傳 {inserted_count} 筆資料到 Supabase！")
    except Exception as e:
        print(f"❌ 上傳資料失敗: {e}")

if __name__ == "__main__":
    main()