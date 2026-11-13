# fintech-agent 多智能體投資分析系統

在有限 Gemini API 預算下，以 Researcher（研究）與 Reviewer（覆核）兩個 Agent 協作，提高台股投資分析的證據完整度與可追溯性。研究標的 2330、2317、2454；2379、3034 只作 2454 的比較參照。

- 專題期間：2026/09/14–12/18（12/11 內部定稿）
- 執行計畫：Notion《fintech-agent｜專題執行手冊 V1.2》（本機副本 `docs/handbook_V1.2/`）
- 分支：**只有 `main` 是正式版**。功能分支合併後即刪除（11/13 已清掉 29 個已合併分支，紀錄在 `docs/archive/deleted-branches-2026-11-13.md`）。

## 先看哪裡

| 想知道 | 看這裡 |
|---|---|
| 給協作 AI 與組員的規則（什麼算可用、什麼不能自己決定） | `AGENTS.md` |
| 組長核定過的決定（WACC、口徑、F06…） | `handoff/decisions-2026-10.md` |
| Agent 版本差異（v1、v2，哪批結果用哪一版） | `handoff/agent-version-changes.md` |
| 凍結了哪些檔案、修訂紀錄 | `data-freeze.md`、`data/v12-frozen-manifest.json` |
| 進度與驗收 | `handoff/W06-gate-v12.md`（W06）、`W08-status.md`（W08） |
| job 狀態與預算規則 | `handoff/state-machine-v1.md` |
| 模型與額度設定 | `handoff/model-config.md`、`handoff/quota-baseline.json` |
| 資料口徑（單季／TTM、淨負債、股數） | `data-contract.md`、`data/v12-finance-fact-sheet.md` |
| B 的檔案總說明 | `docs/B-W01-W06-檔案說明.md` |
| A 的畫面交接 | `design/A-W05-W06-handoff.md` |
| D 的評估草稿 | `evaluation/d-drafts/README.md` |

## 名字很像的資料夾，不要搞混

| 資料夾 | 是什麼 |
|---|---|
| `agents/` | Agent 的**程式**（研究、覆核、工具、預算） |
| `agent/` | Agent 跑出來的**紀錄**（開發集校準、煙霧測試的結果 JSON） |
| `research/` | 前瞻研究各批次的結果與來源 |
| `research_ui/` | 網站研究工作台的程式 |
| `report/` | 書面報告各章的 Word 檔（C、E） |
| `reports/` | 網站產生的線上 PDF 與檢查紀錄（A） |
| `evaluation/` | 案例清單、評分規則、正式實驗紀錄（`evaluation/formal/`） |
| `fixtures/` | 案例快照：`dev/` 開發集、`test/` 保留集（封存，不要打開） |
| `slides/`、`deliverables/E/` | 簡報：`slides/` 放目前版本，`deliverables/E/` 放各週交付 |
| `design/`、`ui/` | 畫面規格與截圖（A）：`design/` 依週次，`ui/` 是 V1.2 驗收用 |
| `output/` | 舊版分析流程輸出的 PDF 與圖表 |
| `docs/archive/` | 已不使用的舊檔（上學期文件等），只留存不維護 |

## 不要搬動或改名的檔案

下列位置被凍結紀錄、部署設定或程式寫死，搬了會讓凍結驗證失敗或網站掛掉。要整理請等正式實驗結束（11/25 之後）並先問組長。

- 根目錄的 `data-contract.md`、`data-freeze.md`、`source-register.csv`、`graph-*.csv`、`graph-approved.json`，以及 `data/`、`agents/`、`evaluation/`、`fixtures/`：凍結清單以路徑核對 hash。
- 根目錄的 `web_app.py`、`main.py` 等 `.py`、`requirements*.txt`、`render.yaml`：Render 從根目錄啟動，程式互相 import。
- 根目錄的 `W01-meeting.md`、`W06-freeze-minutes.md`、`W08-status.md`、`glossary.md`、`method-budget.md`、`case-walkthrough-v1.md`、`evidence-audit-w07.md`、`artifact-index.md`、`v12-asset-index.md`、`deck-template.pptx`：手冊指定的交付檔名，其他文件以這些路徑引用。

新檔案請放進對應資料夾，不要再放根目錄。

## 資料夾地圖（依負責人）

### 組長｜Agent 執行器、預算、發布
| 位置 | 內容 |
|---|---|
| `agents/` | 核心程式：`research_graph.py`（LangGraph 研究迴圈＋覆核）、`provider.py`（Gemini）、`budget.py`（8 次／10 工具／token／每日上限）、`store.py`、`worker.py`（持久 job、lease）、`api.py`、`admin.py`（組長登入）、`publication.py`（核准、版本、PDF）、`snapshot.py`（工具綁定 job 快照）、`tools.py`（六工具契約與驗證） |
| `agents/prompts/` | Researcher／Reviewer 系統提示詞（版本化） |
| `agent/` | 開發案例 live／mock 軌跡、校準與煙霧測試結果、覆核契約 |
| `contracts/` | job／報告資料契約、六工具契約 |
| `handoff/` | 每週交接文件與決策紀錄 |
| `supabase_migrations/` | 資料表遷移草案（尚未在正式庫執行） |
| `scripts/dev_traces.py`、`scripts/live_check.py` | live 開發測試（只跑開發集） |
| `scripts/formal_runs.py`、`scripts/export_for_scoring.py`、`evaluation/formal/` | 正式實驗（保留集 20 案 × 3 模式）與盲評匯出 |
| `research/`、`scripts/forward_research.py` | 前瞻研究批次 |

### B｜資料、工具、案例
| 位置 | 內容 |
|---|---|
| `agents/tools_impl.py`、`agents/calculator.py`、`agents/register_tools.py` | 六工具實作與計算 |
| `data/` | 財務快照、同業快照、資料契約、事實清冊、凍結清單；`data/manual/` 人工來源 |
| `fixtures/dev/`、`fixtures/test/` | 10 個開發案例快照／20 個保留案例（**保留集只供 W10–W11 正式評分，組長不讀內容**） |
| `evaluation/dev-cases.json`、`evaluation/cases_manifest_v1.json`、`evaluation/test-cases-sealed.json` | 30 案清單（v1.5） |
| `scripts/build_*.py`、`scripts/check_*.py`、`scripts/verify_fact_sheet.py` | 建快照、凍結、核對 |
| 根目錄 `data-contract.md`、`data-freeze.md`、`source-register.csv`、`graph-*.csv`、`graph-approved.json` | 契約、凍結紀錄、來源登記（凍結清單以這些路徑核對 hash，暫不搬移） |

### A｜網站畫面
| 位置 | 內容 |
|---|---|
| `research_ui/`、`templates/research.html`、`static/` | 研究工作台、收藏、比較面板 |
| `design/`、`ui/` | 畫面規格、截圖、驗收 |

### D｜覆核、測試、評分
| 位置 | 內容 |
|---|---|
| `evaluation/d-drafts/` | W01–W05 驗收矩陣、案例規格、Reviewer prompt 與規則草稿（規則已由組長納入 `agents/review_checks.py`） |

### 共用與舊版網站
| 位置 | 內容 |
|---|---|
| `web_app.py` | Flask 入口（舊站＋V1.2 研究 API＋公開報告） |
| `main.py`、`financial_analyzer.py`、`report_downloader.py`、`report_builder.py`、`valuation_agent/`、`macro_agent/`、`fundamental_agent/`、`fundamental_uploader.py` | 既有分析流程（FinMind、DCF、圖表、PDF） |
| `tests/` | 全專案測試 |
| `docs/handbook_V1.2/` | 專題手冊本機副本 |
| `pdf_parser.py`、`retry_gemini.py`、`gemini_analyzer.py`、`run_fundamental.py`、`seed_fundamental_data.py`、`quality_checker.py` | 上學期遺留檔，現行流程不使用；凍結結束後再移到 `legacy/` |
| `docs/archive/2026-spring/` | 上學期的文獻 Word 檔與摘要頁（11/13 由根目錄移入） |

## 執行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-agent.txt
.venv/bin/python -m pytest -q          # 全專案測試（離線，不呼叫 API）
.venv/bin/python web_app.py            # 本機網站 http://127.0.0.1:5000
```

`.env`（不進版控）需要：`SUPABASE_URL`、`SUPABASE_KEY`、`GEMINI_API_KEY`、`GEMINI_MODEL`、`RESEARCH_API_TOKEN`、`FLASK_SECRET_KEY`、`ADMIN_PASSWORD`。

## 協作規則

- 直接推 `main` 或開 PR 都可以；PR 合併後刪除該分支。
- 保留集（`fixtures/test/`、`test-cases-sealed.json`）不得用於開發或調整 prompt。
- 不把 `.env`、金鑰放進 repo；資料缺值保留 null，不補 0。
