# Render 部署筆記

本專案的網站入口是 `web_app.py` 裡的 Flask `app`。

## Render 設定

- Runtime: Python
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn web_app:app --workers 1 --timeout 120`
- Branch: `main`

## 必填環境變數

Render 後台建立服務時，請填入：

- `SUPABASE_URL`
- `SUPABASE_KEY`

`FINMIND_TOKEN` 目前不是必填；FinMind 公開 API 可先不填。若之後遇到查詢頻率限制，再到 Render 後台 Environment 補上。

## 部署後驗證

部署完成後，用 Render 提供的 `https://...onrender.com` 網址測試：

- `/`：網站首頁
- `/api/stocks`：確認 Supabase 可讀取已分析股票
- 網站輸入 `2330`：確認可產生估值、圖表與 PDF

注意：Render 免費服務可能會休眠，第一次開啟會比較慢。
