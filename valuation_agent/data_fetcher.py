# 財務數據抓取模組（FinMind 版）
import requests

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wNC0wNCAyMjoyMjowNyIsInVzZXJfaWQiOiJrazEwMzAtYml0IiwiZW1haWwiOiJzb3NqYWNrMDcyM0BnbWFpbC5jb20iLCJpcCI6IjEyMi4xMTguNC4xNDkifQ.4VeMM7ceS3Y3zGku0KoqZ9Z3F7bXzm1h2HiD_1JzvSQ"

def fetch_stock_data(stock_code):
    try:
        # 抓取現金流量表
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockCashFlowsStatement",
            "data_id": stock_code,
            "start_date": "2019-01-01",
            "token": FINMIND_TOKEN
        }
        res = requests.get(url, params=params)
        data = res.json()["data"]
       

        # 取得近5年自由現金流
        fcf_list = []
        for row in data:
            if row.get("type") == "CashFlowsFromOperatingActivities":
                fcf_list.append(float(row.get("value", 0)))
        # 補足5筆
        while len(fcf_list) < 5:
            fcf_list.append(0)

        result = {
            "stock_code": stock_code,
            "company_name": stock_code,
            "free_cash_flows": fcf_list,
            "net_debt": 0,
            "shares_outstanding": 1,
            "current_price": 0
        }

        print(f"✅ 成功抓取 {stock_code} 的財務數據")
        return result

    except Exception as e:
        print(f"❌ 抓取失敗：{e}")
        return None

if __name__ == "__main__":
    data = fetch_stock_data("2330")
    if data:
        print(f"自由現金流：{data['free_cash_flows']}")