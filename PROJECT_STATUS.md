# 多智能體投資分析系統目前狀態

最後更新：2026-05-30

## 專案與 GitHub

- 專案名稱：多智能體投資分析系統
- GitHub Repo: https://github.com/kk1030-bit/fintech-agent
- 目前主要分支：`main`
- 最新 commit: `e2ecf6b 改善公開網站錯誤訊息`

## 公開網站

- Render 公開網址：https://fintech-agent-di0z.onrender.com
- Render 服務名稱：`fintech-agent`
- 部署平台：Render Free
- 目前狀態：
  - 首頁可開啟
  - `/api/stocks` 可讀取 Supabase 內已分析股票
  - 網頁可手動查詢股票代號
  - 已驗證 `2330` 可顯示估值、摘要、風險、FCF 預測與三張圖表
- 注意事項：
  - Render Free 只有 512MB RAM，第一次開啟可能會冷啟動，等待約 50 秒以上屬正常
  - 公開版為了避免記憶體不足，預設略過 PDF 產生
  - 本機版仍可產出 PDF 報告
  - 展示時建議先等頁面顯示「系統待命」，再點股票快捷鍵，不要連續快速點擊

## 已完成功能

- 使用 FinMind 抓取台股股價、財報、比率與現金流資料
- 使用 Supabase 儲存 `macro_data` 與 `fundamental_data`
- 使用 `financial_analyzer.py` 產生規則式財務摘要、優勢、風險與 FCF 預測
- 使用 `valuation_agent/dcf_model.py` 計算 DCF 每股內在價值
- 使用 `valuation_agent/chart_builder.py` 產生三張 PNG 圖表：
  - 股價走勢圖
  - P/E 與 P/B 圖
  - DCF 瀑布圖
- 使用 `main.py` 串接 Supabase、DCF、圖表與報告流程
- 使用 `web_app.py` 建立 Flask 互動式網站
- 使用 Render 部署公開網站
- 本機版可產生 PDF 分析報告

## 重要檔案

- `web_app.py`：Flask 網站入口
- `templates/dashboard.html`：網站前端頁面
- `main.py`：主分析流程
- `report_downloader.py`：FinMind 資料抓取
- `financial_analyzer.py`：規則式財務分析
- `fundamental_uploader.py`：上傳財報資料與分析結果到 Supabase
- `quality_checker.py`：檢核 Supabase 分析資料
- `valuation_agent/dcf_model.py`：DCF 估值模型
- `valuation_agent/chart_builder.py`：圖表產生模組
- `report_builder.py`：PDF 報告產生，本機可用
- `render.yaml`：Render 部署設定
- `DEPLOY_RENDER.md`：Render 部署筆記

## 已驗證股票

- `2330` 台積電
- `2317` 鴻海
- `2454` 聯發科
- `2486` 一詮
- `2308` 台達電曾出現在公開網站股票清單

## 簡報檔案

- 進度更新版：`C:\Users\jack kuo\Downloads\多智能體投資分析系統_進度更新版.pptx`
- 研究動機方法版：`C:\Users\jack kuo\Downloads\多智能體投資分析系統_研究動機方法版.pptx`
- 公開網址版：`C:\Users\jack kuo\Downloads\多智能體投資分析系統_公開網址版.pptx`

## 報告展示說法

可使用以下說法：

> 本專題已完成公開版互動式網站。使用者輸入台股股票代號後，系統會串接 FinMind 與 Supabase，執行財務分析與 DCF 估值，並在網頁上輸出每股內在價值、財務摘要、主要優勢、主要風險與三張視覺化圖表。

補充限制：

> 因 Render Free 記憶體限制，公開網站版主要展示互動查詢、DCF 估值與圖表分析；PDF 報告保留在本機版本產出。

## 新對話接續方式

之後如果開新對話，可以先給 Codex 以下指令：

```text
請讀取 C:\Users\jack kuo\fintech-agent\PROJECT_STATUS.md，接續多智能體投資分析系統專案。
```

不要在聊天或文件中貼出 Supabase secret key。需要更新 Render 環境變數時，請只在 Render 後台處理。
