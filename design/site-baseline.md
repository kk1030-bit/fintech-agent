# W01-A｜既有網站畫面基線

- 任務 ID：W01-A（原排程 2026-09-14～09-18，本次 2026-10-05 補做）
- 記錄人：A｜驗收人：組長
- 程式基線：`main` @ `35f7379`（2026-10-01）
- 公開網址：https://fintech-agent-di0z.onrender.com
- 狀態：待驗收（不是已完成；只有組長確認後才改「已完成」）

## 1. 截圖清單（每張都有 URL、日期、尺寸、環境）

| # | 檔案 | 畫面 / 狀態 | URL | 尺寸 | 環境 | 取得時間（Asia/Taipei） |
|---|---|---|---|---|---|---|
| B01 | `baseline-w01/render-coldstart.jpg` | Render 冷啟動「Application loading」 | https://fintech-agent-di0z.onrender.com/ | 窗格 769×868，存檔縮為 461×520 | **Render 實機**（Claude app 瀏覽器窗格） | 2026-10-05 10:33 |
| B02 | `baseline-w01/B02-home-empty-1440x900.png` | 首頁空白狀態；`/api/stocks` 500 → 快捷鍵退回內建 4 檔 | `/` | 1440×900 | REPLAY（見 §2） | 2026-10-05 10:37 |
| B03 | `baseline-w01/B03-home-empty-390x844.png` | 首頁空白（手機） | `/` | 390×844 | REPLAY | 2026-10-05 10:37 |
| B04 | `baseline-w01/B04-analyze-loading-1440x900.png` | 同步分析載入中（點 2454 快捷鍵） | `/` → `POST /api/analyze` | 1440×900 | REPLAY（回應刻意延遲） | 2026-10-05 10:37 |
| B05 | `baseline-w01/B05-analyze-error-390x844.png` | 輸入非數字代號 → 400 錯誤訊息 | `/` → `POST /api/analyze` | 390×844 | REPLAY（錯誤文字與 Render 實測相同） | 2026-10-05 10:37 |
| B06 | `baseline-w01/B06-pdf-unavailable-1440x900.png` | PDF 不可用：`/output/report.pdf` 404 | `/output/report.pdf` | 1440×900 | REPLAY（Render 實測同為 404） | 2026-10-05 10:37 |

所有 PNG 橫向溢出量實測為 0 px（`scripts/ui_screenshots/shoot.mjs` 輸出）。

## 2. 為何用「REPLAY」以及它代表什麼

- 工作環境連不到 Render 與 FinMind（網路白名單），所以 B02–B06 是在本機跑**同一版** `web_app.py`，只把兩個連網端點換成 Render 實測回應（`scripts/ui_screenshots/replay_baseline.py`）。
- 證明同一版：Render 首頁 HTML 的 sha256 = `f9140eae…c29928`，與本機 `35f7379` 輸出的 sha256 **完全相同**（`baseline-w01/render-probe-2026-10-05.json`）。
- REPLAY 只重播不寫入正式資料的回應；**沒有**重播或捏造成功的分析結果。

## 3. 實測紀錄（Render，2026-10-05 10:35）

| 請求 | 結果 | 耗時 |
|---|---|---|
| 第一次開首頁 | Render 冷啟動頁，約 30 秒後才回首頁 | ~30 s |
| `GET /api/stocks` | **500**（Flask 預設錯誤頁，text/html） | 536 ms |
| `POST /api/analyze` 空字串 | 400「請輸入股票代號。」 | 220 ms |
| `POST /api/analyze` "abc" | 400「目前網站版先支援台股數字代號…」 | 266 ms |
| `GET /api/research/jobs/x` 無 token | 401 unauthorized（組長 W02 API 已上線，拒絕預設生效） | 228 ms |
| `GET /output/report.pdf` | 404 | 209 ms |

**未執行（需組長授權）**：`POST /api/analyze` 對 2330/2317/2454 的成功分析。它會即時抓 FinMind 並 `upload_to_supabase` 寫入正式 `fundamental_data`，所以成功畫面、三張圖與 PDF 可用畫面本次**沒有截圖**，不以舊圖或示意圖代替。

## 4. 既有畫面盤點（只列現在真的存在的）

| 既有畫面 / 元件 | 位置 | 現況 |
|---|---|---|
| 首頁查詢列 | `dashboard.html` `#form` | 可輸入代號，按鈕在請求中 disabled |
| 快捷鍵 | `#quick`，來自 `/api/stocks` | Render 上 `/api/stocks` 500，**退回內建 2330/2317/2454/1303** |
| 估值結論 | `#valuation` | 成功時顯示每股內在價值、WACC、g、資料年度 |
| 分析結果 | `#result` | 摘要、優勢、風險、5 年 FCF、三張圖 |
| PDF 連結 | `#valuation .actions` | Render 上 `pdf=null`，只顯示「公開版略過 PDF」 |
| 載入狀態 | 狀態列＋兩個空白框 | 只有文字，無進度、無耗時、無取消 |
| 錯誤狀態 | 紅字錯誤訊息 | 只有單一錯誤字串 |

**目前不存在**（不能因頁面存在就標完成）：非同步研究入口、job 狀態、Agent 工具軌跡、Reviewer 覆核、來源引用、季度/TTM、同業比較、收藏、已發布清單、資料品質風險、線上 PDF、2D 圖、暫停配額狀態、資料不足狀態。

## 5. 非同步研究的接點與耗時

| 接點 | 檔案 / 行 | 說明 |
|---|---|---|
| 同步分析入口 | `web_app.py` `POST /api/analyze` → `stock_payload()` | 一次請求內：FinMind 下載 5 年 → 規則分析 → **寫入 Supabase** → `run_analysis()`（DCF、3 圖、PDF）。gunicorn `--timeout 120` |
| 研究 job API（組長 W02） | `agents/api.py` `POST /api/research/jobs`、`GET /api/research/jobs/<id>` | Bearer token 拒絕預設；回 job＋events |
| job 狀態來源 | `agents/store.py` `JobStore`（SQLite） | job、events、model_usage 皆持久 |
| worker | `agents/worker.py` | 目前只有 `mock_handler`；W04 起接 Researcher |
| PDF | `main.py:441` `build_report_if_available` | Render 未設 `ENABLE_PDF_ON_RENDER=1` 即略過 |
| 圖表 | `valuation_agent/chart_builder.py` | 已有 `plt.close(fig)`（第 73 行） |

同步分析成功路徑耗時：**未量測**（見 §3 未執行原因）。

## 6. 基線觀察到的問題（記錄，不在 W01 改風格）

1. `/api/stocks` 在 Render 回 500，前端靜默退回內建清單，使用者看不出資料庫讀取失敗。→ 交組長查 Render 環境變數或 Supabase。
2. 背景漸層只到第一屏內容高度（B02、B04 下半部底色不同），`body` 缺 `min-height: 100vh`。
3. 快捷鍵點擊後直接觸發完整同步分析（含寫入 Supabase），連點會重複觸發；無冪等。
4. `main.py:362` 股價走勢圖在無股價時退回**營收序列**，`main.py:403-406` P/E、P/B 在無值時以「營收/淨利」「營收/營業利益」替代。手冊第 02 章已列為必查；新畫面不得沿用這兩個替代值。
5. 手機版快捷鍵 4 顆貼齊換行邊界（B03），之後加入收藏後需改成可換行或水平捲動。

## 7. 交付紀錄

- 版本／日期：`codex/W01-A-site-baseline`／2026-10-05
- 成果：本文件、`design/v12-screen-map.md`、`design/baseline-w01/`（6 張截圖＋實測 JSON）
- 驗收項：每圖有 URL/日期/尺寸 ✓；新舊功能分開 ✓（§4、screen-map）；未因頁面存在標 Agent 完成 ✓；含空白/錯誤/載入/PDF 不可用 ✓；資料不足與暫停配額狀態在現有網站**不存在**，已列為新增畫面
- 未完成：成功分析畫面與耗時（需組長授權執行 `/api/analyze`）；`/api/stocks` 500 原因（需組長看 Render log）
- 實際工時：未記錄（AI 協作）
