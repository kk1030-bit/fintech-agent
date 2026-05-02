import sys
import time
from datetime import datetime
from report_downloader import download_financial_report
from gemini_analyzer import analyze_financials
from fundamental_uploader import upload_to_supabase

# 台灣市值前100大對照表
STOCK_NAMES = {
    "2330":"台積電","2308":"台達電","2317":"鴻海","2454":"聯發科","3711":"日月光投控",
    "0050":"元大台灣50","2382":"廣達","2881":"富邦金","2383":"台光電","2882":"國泰金",
    "2891":"中信金","2412":"中華電","2345":"智邦","3037":"欣興","3017":"奇鋐",
    "2360":"致茂","2303":"聯電","7769":"鴻勁","2408":"南亞科","1303":"南亞",
    "6669":"緯穎","2885":"元大金","2327":"國巨","2887":"台新金","2886":"兆豐金",
    "3653":"健策","0056":"元大高股息","6505":"台塑化","2368":"金像電","2884":"玉山金",
    "2890":"永豐金","2880":"華南金","00878":"國泰永續高股息","00919":"群益台灣精選高息",
    "2603":"長榮","3665":"貿聯-KY","2357":"華碩","3231":"緯創","2344":"華邦電",
    "8046":"南電","3045":"台灣大","1216":"統一","2892":"第一金","5880":"合庫金",
    "3443":"創意","2449":"京元電子","2883":"凱基金","2301":"光寶科","006208":"富邦台50",
    "4904":"遠傳","2313":"華通","1301":"台塑","3008":"大立光","2002":"中鋼",
    "2059":"川湖","6515":"穎崴","2395":"研華","1326":"台化","3036":"文曄",
    "2207":"和泰車","2337":"旺宏","2379":"瑞昱","1519":"華城","3533":"嘉澤",
    "3661":"世芯-KY","2801":"彰銀","4958":"臻鼎-KY","6446":"藥華藥","3034":"聯詠",
    "2912":"統一超","6770":"力積電","1590":"亞德客-KY","2615":"萬海","3481":"群創",
    "4938":"和碩","3044":"健鼎","3189":"景碩","5876":"上海商銀","1101":"台泥",
    "2618":"長榮航","5871":"中租-KY","1802":"台玻","2404":"漢唐","2376":"技嘉",
    "2609":"陽明","6442":"光聖","6239":"力成","6919":"康霈","3702":"大聯大",
    "2356":"英業達","2633":"台灣高鐵","2834":"臺企銀","1504":"東元","6139":"亞翔",
    "1402":"遠東新","1605":"華新","2347":"聯強","2409":"友達","2324":"仁寶",
    "1102":"亞泥","2812":"台中銀",
}

def print_progress(current, total, stock_code, company):
    pct = int(current / total * 40)
    bar = "█" * pct + "░" * (40 - pct)
    print(f"\r[{bar}] {current}/{total} {stock_code} {company}    ", end="", flush=True)

def run(stock_list):
    total = len(stock_list)
    print(f"🚀 開始執行，共 {total} 支股票\n")
    
    results = []
    
    for i, code in enumerate(stock_list):
        name = STOCK_NAMES.get(code, code)
        print_progress(i + 1, total, code, name)
        
        start_time = datetime.now()
        status = "✅"
        note = ""
        
        try:
            data = download_financial_report(code, years=5)
            gemini_result = analyze_financials(data, code, name)
            success = upload_to_supabase(data, gemini_result)
            if not success:
                status = "❌"
                note = "上傳失敗"
        except Exception as e:
            status = "❌"
            note = str(e)[:40]
        
        upload_time = datetime.now().strftime("%H:%M:%S")
        results.append((code, name, status, upload_time, note))
        
        if i < total - 1:
            time.sleep(3)
    
    # 印出摘要表格
    print(f"\n\n{'='*70}")
    print(f"{'代號':<8} {'公司名稱':<20} {'狀態':<6} {'上傳時間':<10} {'備註'}")
    print(f"{'-'*70}")
    for code, name, status, upload_time, note in results:
        print(f"{code:<8} {name:<20} {status:<6} {upload_time:<10} {note}")
    print(f"{'='*70}")
    
    success_count = sum(1 for r in results if r[2] == "✅")
    print(f"\n✅ 成功：{success_count} 支　❌ 失敗：{total - success_count} 支")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 從命令列接收股票代號，例如：python run_fundamental.py 2330 2317 2454 1303
        stocks = sys.argv[1:]
    else:
        # 預設跑前4支測試
        stocks = ["2330", "2317", "2454", "1303"]
    
    run(stocks)
