# A｜W01–W04 交付紀錄與交接（2026-10-05）

> 依工作包「最終回覆固定」五段格式。狀態一律「待驗收」，只有組長確認後才能在 84 項任務資料庫改「已完成」。

## 1. 實際產物與連結

四個分支依序疊加（每個都從前一個分支長出來），合併時照順序：

| 任務 | 分支 | commit | 主要產物 |
|---|---|---|---|
| W01-A | `codex/W01-A-site-baseline` | `80253d2` | `design/site-baseline.md`、`design/v12-screen-map.md`、`design/baseline-w01/`（6 張截圖＋Render 實測 JSON）、`design/wireframes/`、`scripts/ui_screenshots/` |
| W02-A | `codex/W02-A-research-workspace` | `7bf67b1` | `research_ui/`、`templates/research.html`、`static/research.{css,js}`、`ui/v12-dashboard-fixture.json`、`design/research-flow.md`、`design/w02/` |
| W03-A | `codex/W03-A-job-trace` | `623fabc` | 軌跡 UI、狀態測試、`ui/v12-comparison-contract.md`、`design/w03/` |
| W04-A | `codex/W04-A-report-detail` | `5bad01a` | 報告詳情、來源抽屜、`research_ui/comparison.py`、`ui/v12-financial-screenshots/` |

`web_app.py` 只加了 2 行（註冊 `research_ui` blueprint），首頁 `dashboard.html` 與 `/api/analyze` 未改。

## 2. 逐項驗收結果

| 任務 | 驗收項 | 結果 |
|---|---|---|
| W01 | 每圖有 URL/日期/尺寸 | ✓ |
| W01 | 新舊功能分開 | ✓ |
| W01 | 未因頁面存在就標 Agent 完成 | ✓ |
| W01 | 含空白/錯誤/資料不足/暫停狀態；不把新畫面寫成已有 | 部分：既有網站只有空白/載入/錯誤/PDF 不可用；資料不足、暫停在既有網站**不存在**，已列為新增畫面 |
| W02 | 不把 API key 傳前端 | ✓ |
| W02 | 重複點擊不產生多 job | ✓ |
| W02 | 390px 無橫向破版 | ✓（0 px） |
| W02 | 重整收藏仍在；無 key 或敏感財務；比較標的不開研究 job | ✓ |
| W03 | 不顯示秘密與隱藏思考鏈 | ✓ |
| W03 | 狀態從 DB 取得 | ✓（組長 JobStore，MOCK 專用 SQLite） |
| W03 | pending 不冒充完成 | ✓ |
| W03 | 最多 4 公司；不同期或缺值不用 0 補；標示 fixture | ✓（契約＋W04 實作） |
| W04 | 來源內容與引用一致 | ✓ 文字一致；✗ 片段 hash 不符（已在畫面標示，待 B） |
| W04 | 不以記憶補數字 | ✓ |
| W04 | 桌機/手機長文無重疊 | ✓ |
| W04 | 每列來源/時間可查；不再用營收比當 PE/PB | ✓ |
| W04 | B/D 確認數字 | ✗ 尚未 |

## 3. 來源、測試與版本

- 程式基線：`main` @ `35f7379`；Render 首頁 sha256 與此版相同（2026-10-05 實測）。
- 測試命令：`.venv/bin/python -m pytest -q tests`
  - W01 分支 82 passed、W02 95 passed、W03 105 passed、W04 **111 passed**（皆 2026-10-05 在乾淨 checkout 實跑，Python 3.13）。
- Render 設定模擬（`RENDER=1`、未設 `RESEARCH_UI_MOCK`）：`/research`、已發布清單、報告、比較皆 200；建立/讀取 MOCK job 皆 403；不會建立 `tmp/` 資料庫。
- 截圖工具：`scripts/ui_screenshots/shoot.mjs`（headless Chromium，開發用，不是執行依賴）。
- 資料：B 的 `data/financial-snapshots.json`（manifest v1.2）、`data/v12-peer-snapshot.json`（v1.2-w04）。
- 未執行：Render 上的成功分析（會寫正式 Supabase）、真實 Gemini job（授權決定為 MOCK）、gunicorn 實機。

## 4. 未完成、原因與提供人

| 項目 | 原因 | 提供人 |
|---|---|---|
| 正式授權方式（登入/角色），把 MOCK 入口換成伺服器代呼正式 API | 2026-10-05 決定先全用 MOCK | 組長 |
| `/api/stocks` 在 Render 回 500 | 需看 Render log／Supabase 環境變數 | 組長 |
| 成功分析畫面與耗時基線 | 會寫入正式 Supabase，需授權 | 組長 |
| 真實 Researcher 軌跡與報告 | W04-L runner 尚未在 main | 組長 |
| 同業 2379/3034/2330 只有 1 季、缺 BVPS、缺去年同季、缺 evidence、hash 不符、未標真實/合成 | B 快照內容 | B（補資料）、D（覆核） |
| 取消排隊中 job | JobStore 只允許 lease 持有者改狀態 | 組長（CR-A03） |
| `/api/analyze` 是否納入授權/配額 | 手冊要求不可留繞過路徑 | 組長＋A（CR-A01） |

## 5. 給組長的交接短訊（草稿，未發送）

> 組長好，我是 A。W01–W04 已補完，四個分支 `codex/W01-A-site-baseline` → `W02` → `W03` → `codex/W04-A-report-detail` 依序疊加，請照順序 review／合併。
> 重點：①新頁 `/research`（研究工作台、狀態與軌跡、收藏與已發布清單、報告詳情與來源抽屜、2454 同業比較），首頁和 `/api/analyze` 沒動；②授權先用 MOCK，Render 上建立 job 一律 403，頁面不持有任何 token；③測試 111 passed。
> 需要你：Render `/api/stocks` 目前 500；正式授權方式；W04-L runner 好了我就把軌跡改接正式 job DB。
> B 的同業快照有 6 個問題（只有 1 季、hash 不符等），整理在 `ui/v12-comparison-contract.md` §4，已請 B、D 看。
