# W01-L 程式基線（補做）

- 記錄日期：2026-09-28（原排程 W01：09-14～09-18，本次補做）
- 記錄人：組長（AI 協作助理整理）
- 驗收人：A、D 技術交叉檢查，組長定案

## 1. Git 狀態

| 項目 | 值 |
|---|---|
| repo | https://github.com/kk1030-bit/fintech-agent（公開） |
| 本機位置 | `~/專題/fintech-agent`（Mac；手冊中的 `E:\專題` 為原 Windows 電腦） |
| 分支 | `main`，基線 commit `baf1d59 docs: add V1.2 data contract for W01-B`（2026-09-19，Tang3961） |
| 其他遠端分支 | `origin/catherine-w2-w5-fix`（`8c6ddbc`，只改 `fundamental_uploader.py`、`gemini_analyzer.py`，舊版財報上傳，未合併） |
| 本機既有未追蹤 | `conversation_2026-06-14_summary.html`、`tmp/`、`.env`（不進版控），保留不動 |
| 舊 Windows 複本差異 | 17 個檔案只差 CRLF/LF 換行，`git diff --ignore-cr-at-eol` 為空，已還原後 fast-forward |

## 2. 執行環境

| 項目 | 值 |
|---|---|
| Python | 3.14.7（`.venv`） |
| requirements.txt | pandas 2.3.3、matplotlib 3.11.2、fpdf2 2.8.8、Flask 3.1.3、supabase 2.31.0、python-dotenv、requests 2.34.2、PyMuPDF 1.28.2、FinMind 2.0.10、fredapi；全部安裝成功（未鎖版本） |
| 新增（requirements-agent.txt） | google-genai 2.25.0、langgraph 1.2.12、pytest 9.1.1 |
| gunicorn | 在 requirements.txt，Mac 本機未實跑 |
| `.env` 變數名稱 | 只有 `SUPABASE_URL`、`SUPABASE_KEY`；**沒有** `GEMINI_API_KEY`、`FINMIND_TOKEN`、`FRED_API_KEY`、`RESEARCH_API_TOKEN`（只檢查名稱，未讀值） |

## 3. 既有測試與實際結果

- **原 repo 沒有任何測試檔**（無 `tests/`、無 `test_*.py`）。「可用測試」＝ 0。
- 基線檢查（2026-09-28 本機實跑）：

| 命令 | 結果 |
|---|---|
| `.venv/bin/python -m compileall -q . -x '\.venv'` | 通過 |
| `import web_app / main / financial_analyzer / report_downloader / report_builder / quality_checker / valuation_agent.dcf_model / valuation_agent.chart_builder / macro_agent.fred_scraper` | 9 個全部可載入 |
| `web_app` 測試客戶端 `GET /` | 200 |

- **未執行**：`/api/analyze`、`/api/stocks`（會連 FinMind 與正式 Supabase，寫入正式資料，本次不做）；Render 線上檢查；PDF 產生。

## 4. 既有程式與 V1.2 的落差（實查，不是推測）

| 手冊項目 | 現況 |
|---|---|
| LangGraph / Gemini 雙 Agent | 不存在。`gemini_analyzer.py` 只是轉呼叫規則式 `financial_analyzer.py` 的相容檔 |
| 持久 job、授權 API | 不存在 → W02 新增 `agents/`（見 agent-test-commands.md） |
| 六工具 | 不存在。`tool-field-map.md`（B）標註 search/read 為待建，其餘改寫既有模組 |
| 季度資料 | `report_downloader.py` 聚合為年度（`_annual_*`），無原始季度層 |
| PE/PB | `main.py` 有非股價替代序列（ch.02 已列為必查），W03 B/D 處理 |
| PDF | Render 預設略過（`ENABLE_PDF_ON_RENDER`），只有本機 `output/` |
| Supabase schema | 只有 `macro_data`、`fundamental_data` 與 `20260521_add_fundamental_dcf_fields.sql` |
