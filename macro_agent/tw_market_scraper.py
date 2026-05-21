"""Taiwan market scraper using FinMind."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import requests

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"


def get_market_data() -> list[dict]:
    """Fetch TAIEX monthly values and returns from FinMind."""

    start_date = (date.today() - timedelta(days=430)).isoformat()
    end_date = date.today().isoformat()
    params = {
        "dataset": "TaiwanStockTotalReturnIndex",
        "data_id": "TAIEX",
        "start_date": start_date,
        "end_date": end_date,
    }

    print("開始抓取 FinMind 台灣加權報酬指數數據...")
    response = requests.get(FINMIND_API_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind 回傳失敗：{payload.get('msg')}")

    df = pd.DataFrame(payload.get("data") or [])
    if df.empty:
        return []

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    monthly = df["price"].resample("ME").last().dropna().tail(12)
    returns = monthly.pct_change()

    results: list[dict] = []
    for index, value in monthly.items():
        month = index.strftime("%Y-%m")
        results.append(
            {
                "date": month,
                "indicator": "TWII",
                "value": round(float(value), 2),
                "source": "FinMind",
            }
        )
        if pd.notna(returns.loc[index]):
            results.append(
                {
                    "date": month,
                    "indicator": "TWII_Return",
                    "value": round(float(returns.loc[index]), 4),
                    "source": "FinMind",
                }
            )

    print(f"  - TWII 抓取完成，共 {len(results)} 筆")
    return results


if __name__ == "__main__":
    data = get_market_data()
    print(data[:5])
