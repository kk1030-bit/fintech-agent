import os
from dotenv import load_dotenv
from google import genai
from datetime import datetime

# 載入 .env 檔案
load_dotenv()

def analyze_financials(financial_data: list, stock_code: str, company_name: str) -> dict:
    """用 Gemini 分析財務數據"""

    data_text = ""
    for d in financial_data:
        if d.get('revenue') is None:
            continue
        data_text += f"{d['year']}年：營收={d['revenue']}, 營業利益={d['operating_income']}, 淨利={d['net_income']}, 自由現金流={d['free_cash_flow']}\n"

    prompt = f"""你是一位專業的財務分析師，請根據以下財務數據分析這家公司，請用繁體中文回答。

公司：{company_name}（{stock_code}）
財務數據（新台幣）：
{data_text}

請嚴格按照以下格式回答：
[摘要]
（財務健康摘要200字以內）

[優勢]
1. （優勢1）
2. （優勢2）
3. （優勢3）

[風險]
1. （風險1）
2. （風險2）
3. （風險3）

[FCF預測]
2026: （金額）
2027: （金額）
2028: （金額）
2029: （金額）
2030: （金額）
假設：（說明依據）
"""

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        text = response.text

        result = {
            'company': company_name,
            'stock_code': stock_code,
            'summary': '',
            'strengths': [],
            'risks': [],
            'fcf_forecast': [],
            'created_at': datetime.now().isoformat()
        }

        if '[摘要]' in text and '[優勢]' in text:
            result['summary'] = text.split('[摘要]')[1].split('[優勢]')[0].strip()
        if '[優勢]' in text and '[風險]' in text:
            result['strengths'] = [s.strip() for s in text.split('[優勢]')[1].split('[風險]')[0].strip().split('\n') if s.strip()]
        if '[風險]' in text and '[FCF預測]' in text:
            result['risks'] = [r.strip() for r in text.split('[風險]')[1].split('[FCF預測]')[0].strip().split('\n') if r.strip()]
        if '[FCF預測]' in text:
            result['fcf_forecast'] = [f.strip() for f in text.split('[FCF預測]')[1].strip().split('\n') if f.strip()]

        print(f"✅ Gemini 分析完成：{company_name}")
        return result

    except Exception as e:
        print(f"❌ Gemini 分析失敗：{e}")
        return {}

if __name__ == "__main__":
    from report_downloader import download_financial_report
    data = download_financial_report("2330", years=5)
    result = analyze_financials(data, "2330", "台積電")
    print("\n===== 分析結果 =====")
    print("摘要：", result.get('summary'))
    print("優勢：", result.get('strengths'))
    print("風險：", result.get('risks'))
    print("FCF預測：", result.get('fcf_forecast'))
