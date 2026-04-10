import yfinance as yf
import pandas as pd

def get_market_data():
    """
    抓取台灣加權指數與 S&P 500 近 12 個月的月均收盤價與月報酬率
    """
    results = []
    
    # 定義要抓取的標的
    symbols = {
        '^TWII': 'TWII', 
        '^GSPC': 'S&P500'
    }

    print("開始抓取 Yahoo Finance 數據...")
    for ticker_symbol, name in symbols.items():
        try:
            # 建立 yfinance Ticker 物件
            ticker = yf.Ticker(ticker_symbol)
            # 取得近一年、以月為單位的歷史資料
            hist = ticker.history(period="1y", interval="1mo")
            
            # 如果抓不到資料則跳過
            if hist.empty:
                continue

            # 確保資料沒有空值
            hist = hist.dropna(subset=['Close'])
            
            # 計算月報酬率（月漲跌幅）
            hist['Return'] = hist['Close'].pct_change()
            
            for date, row in hist.iterrows():
                date_str = date.strftime("%Y-%m")
                
                # 1. 儲存月收盤價
                results.append({
                    "date": date_str,
                    "indicator": name,
                    "value": round(float(row['Close']), 2),
                    "source": "Yahoo Finance"
                })
                
                # 2. 儲存月報酬率（略過第一個月的 NaN）
                if pd.notna(row['Return']):
                    results.append({
                        "date": date_str,
                        "indicator": f"{name}_Return",
                        "value": round(float(row['Return']), 4), # 保留四位小數
                        "source": "Yahoo Finance"
                    })
            print(f"  - {name} 抓取完成")
        except Exception as e:
            print(f"  - 抓取 {name} 失敗: {e}")
            
    return results

# 測試用：如果直接執行此檔案，會印出結果
if __name__ == "__main__":
    data = get_market_data()
    print(data[:5]) # 只印前5筆檢查格式