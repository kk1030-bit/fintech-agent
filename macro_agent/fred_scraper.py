import os
import pandas as pd
from datetime import datetime, timedelta
from fredapi import Fred
from dotenv import load_dotenv

def get_fred_data():
    """
    抓取 FRED 美國總經數據的近 12 個月資料
    """
    # 載入 .env 檔案中的環境變數
    load_dotenv()
    api_key = os.getenv("FRED_API_KEY")
    
    if not api_key:
        print("錯誤：找不到 FRED_API_KEY，請確認 .env 檔案設定。")
        return []

    # 初始化 FRED API 客戶端
    fred = Fred(api_key=api_key)

    # 定義要抓取的指標與我們自訂的名稱
    indicators = {
        'CPIAUCSL': 'CPI',
        'UNRATE': '失業率',
        'FEDFUNDS': '聯邦基金利率',
        'GDP': 'GDP',
        'DGS10': '10年期公債殖利率'
    }

    # 設定時間範圍：抓取過去 365 天（約 12 個月）的數據
    start_date = datetime.now() - timedelta(days=365)
    results = []

    print("開始抓取 FRED 數據...")
    for code, name in indicators.items():
        try:
            # 呼叫 API 取得時間序列資料
            data = fred.get_series(code, observation_start=start_date)
            # 移除空值
            data = data.dropna()
            
            # 將資料整理成指定的字典格式
            for date, value in data.items():
                results.append({
                    "date": date.strftime("%Y-%m"),
                    "indicator": name,
                    "value": float(value),
                    "source": "FRED"
                })
            print(f"  - {name} 抓取完成")
        except Exception as e:
            print(f"  - 抓取 {name} 失敗: {e}")
            
    return results

# 測試用：如果直接執行此檔案，會印出結果
if __name__ == "__main__":
    data = get_fred_data()
    print(data[:5]) # 只印前5筆檢查格式