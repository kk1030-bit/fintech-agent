# DCF（現金流折現）估值模型
# 用於計算股票的每股內在價值

def calculate_dcf(free_cash_flows, wacc=0.1, terminal_growth=0.03, net_debt=0, shares_outstanding=1):
    """
    DCF 估值函數
    
    參數說明：
    - free_cash_flows: 未來5年預測自由現金流（list，單位：元）
    - wacc: 加權平均資金成本，即折現率（預設10%）
    - terminal_growth: 終端成長率（預設3%）
    - net_debt: 淨負債 = 總負債 - 現金（單位：元）
    - shares_outstanding: 流通股數（單位：股）
    
    回傳：每股內在價值（元）
    """
    
    # 步驟一：折現每一年的自由現金流
    pv_fcf = 0
    for i, fcf in enumerate(free_cash_flows):
        # 第 i+1 年的現金流折現回現在的價值
        pv = fcf / ((1 + wacc) ** (i + 1))
        pv_fcf += pv
    
    # 步驟二：計算終端價值（第5年之後的永續價值）
    terminal_value = free_cash_flows[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    
    # 步驟三：將終端價值折現回現在
    pv_terminal = terminal_value / ((1 + wacc) ** len(free_cash_flows))
    
    # 步驟四：計算企業總價值
    enterprise_value = pv_fcf + pv_terminal
    
    # 步驟五：扣除淨負債，得到股權價值
    equity_value = enterprise_value - net_debt
    
    # 步驟六：除以流通股數，得到每股內在價值
    intrinsic_value_per_share = equity_value / shares_outstanding
    
    return round(intrinsic_value_per_share, 2)


# 測試用範例（以台積電為假設數據）
if __name__ == "__main__":
    # 假設未來5年自由現金流（單位：億元）
    fcf_list = [8000, 8500, 9000, 9500, 10000]
    
    # 計算每股內在價值
    value = calculate_dcf(
        free_cash_flows=fcf_list,
        wacc=0.1,
        terminal_growth=0.03,
        net_debt=5000,
        shares_outstanding=259
    )
    
    print(f"每股內在價值：{value} 億元/股")
    print("DCF 模型載入成功 ✅")