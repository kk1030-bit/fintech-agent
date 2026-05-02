import yfinance as yf
from datetime import datetime

def download_financial_report(stock_code: str, years: int = 5) -> list[dict]:
    """
    抓取台股近N年的財務數據
    stock_code: 股票代號（如 '2330'）
    years: 要抓幾年（預設5年）
    回傳: list of dict，每年一筆
    """
    ticker_symbol = f"{stock_code}.TW"
    print(f"正在抓取 {ticker_symbol} 近{years}年財務數據...")

    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # 抓損益表（年度）
        income_stmt = ticker.financials          # 損益表
        cashflow_stmt = ticker.cashflow          # 現金流量表
        info = ticker.info                       # 基本資訊

        results = []
        current_year = datetime.now().year

        # 取得所有可用年度的欄位
        available_years = income_stmt.columns.tolist()
        
        for col in available_years[:years]:  # 只取前N年
            year = col.year
            
            try:
                revenue = int(income_stmt.loc['Total Revenue', col]) \
                    if 'Total Revenue' in income_stmt.index else None
            except:
                revenue = None

            try:
                operating_income = int(income_stmt.loc['Operating Income', col]) \
                    if 'Operating Income' in income_stmt.index else None
            except:
                operating_income = None

            try:
                net_income = int(income_stmt.loc['Net Income', col]) \
                    if 'Net Income' in income_stmt.index else None
            except:
                net_income = None

            try:
                free_cash_flow = int(cashflow_stmt.loc['Free Cash Flow', col]) \
                    if 'Free Cash Flow' in cashflow_stmt.index else None
            except:
                free_cash_flow = None

            record = {
                'stock_code': stock_code,
                'year': year,
                'company': info.get('longName', ''),
                'currency': info.get('currency', 'TWD'),
                'revenue': revenue,
                'operating_income': operating_income,
                'net_income': net_income,
                'free_cash_flow': free_cash_flow,
            }
            results.append(record)
            print(f"  ✅ {year}年：revenue={revenue}, op_income={operating_income}, net_income={net_income}, fcf={free_cash_flow}")

        return results

    except Exception as e:
        print(f"❌ 抓取失敗：{e}")
        return []


if __name__ == "__main__":
    data = download_financial_report("2330", years=5)
    print("\n========== 完整結果 ==========")
    for d in data:
        print(d)
