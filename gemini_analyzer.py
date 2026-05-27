"""Compatibility wrapper for the rule-based financial analyzer.

The project no longer requires a Gemini API key. Older scripts still import
analyze_financials from gemini_analyzer.py, so this file keeps that import path
working while delegating to financial_analyzer.py.
"""

from financial_analyzer import analyze_financials


if __name__ == "__main__":
    from report_downloader import download_financial_report

    data = download_financial_report("2330", years=5)
    result = analyze_financials(data, "2330", "台積電")
    print("\n===== 分析結果 =====")
    print("摘要：", result.get("summary"))
    print("優勢：", result.get("strengths"))
    print("風險：", result.get("risks"))
    print("FCF預測：", result.get("fcf_forecast"))
