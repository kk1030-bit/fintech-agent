# W10-A｜正式研究瀏覽與 PDF 一致性回歸

- 負責：A（陳柏臣）｜日期：2026-11-18（台北）｜驗收人：組長
- 分支：`codex/W10-A`，基於 main b4c36a7
- 線上環境：Render https://fintech-agent-di0z.onrender.com，擷取時部署的是 main b4c36a7
- 依 AGENTS.md 第六節：
  - 鎖定的檔案都沒有動，`build_freeze.py --verify --strict` 顯示「凍結紀錄一致」。
  - 沒有打開正式實驗的執行紀錄（`evaluation/formal/runs-v2.jsonl`）或相關 commit。
  - 正式實驗的輸出不發布，所以本週的「正式輸出」指的是 Render 上已發布的 LIVE 報告。

## 一、五點重述

| 項目 | 內容 |
|---|---|
| 目標 | 同一個 report_version_id 在網頁、PDF、下載檔三處內容一致，NA 與來源沒有遺失；切換新舊版、引用、PDF 都正常；未經人工核准的內容（含正式實驗輸出、測試 fixture）不會被當成正式研究公開 |
| 既有狀態 | Render 上有 4 個 LIVE 版本：2317、2330 各第 1、2 版，都是 Agent v1 跑的；另有 3 份 FIXTURE。前瞻第 3 批 2454 還沒有發布 |
| 輸入 | Render 線上版本、`research_ui/`（網頁、API、PDF）、B 的資料品質規則、決策 43–45 |
| 交付 | 本文件、`screenshots/w10/`（含 README 清單）、`reports/v12-consistency-batch1.md` |
| 驗收人 | 組長 |

## 二、多版本切換、引用、PDF（Render 實測）

| 檢查 | 結果 |
|---|---|
| 已發布清單只列最新版（2317、2330 各第 2 版），卡片寫「另有 1 個舊版」 | ✅ |
| 在第 2 版的「歷史版本」開啟第 1 版 → 網址變成 `?report=<第 1 版>`、標題寫「舊版・第 1 版」、上方提示並附「開啟第 2 版」 | ✅ 2317、2330 都測過 |
| 停在舊版時重新整理 → 仍然是同一個舊版 | ✅ |
| 舊版的引用按鈕 → 來源抽屜開出該片段（hash 吻合、cutoff 前可得） | ✅ |
| 舊版頁面的「預覽／下載 PDF」指向舊版自己的 report_version_id | ✅ |
| 4 個版本的 PDF：預覽為 inline 200、下載為 attachment 200、兩者位元組相同，sha256 等於報告記錄的 pdf_hash；帶 ETag 再請求回 304 | ✅ 4／4 |

PDF 是從 Storage 讀出、由報告的 pdf_hash 驗證後才送出，sha256 一致代表 Storage 下載的就是核准時產生的那一份。

## 三、未經人工核准不公開；測試資料不當正式研究

| 檢查 | 結果 |
|---|---|
| 不存在或未發布的版本：報告、PDF、下載都回 404 | ✅（Render 實測） |
| FIXTURE 沒有 PDF（回 404），清單寫「線上 PDF 尚未提供」 | ✅ |
| Render 上不能送研究：MOCK 建立與 job 查詢都回 403「研究入口未啟用」 | ✅ |
| 研究 API 沒有金鑰不能用：`POST /api/research/jobs` 回 401 | ✅（送空白內容，不會建立任何 job） |
| 來源抽屜只開已發布報告引用過的片段，例如第 3 批未發布的 `ev-fwd3-…` 回 404 | ✅ |
| 正式實驗（保留集）的草稿只在組長 Mac，網站沒有讀取路徑；回放清單只讀 `agent/` 的開發集紀錄 | ✅（`tests/test_w09_ui.py` 檢查不讀保留集） |
| 草稿和「已核准未發布」都不會出現在清單或 API | ✅ 既有測試：`test_draft_is_not_public_until_the_lead_approves_the_seen_hash`、`test_unpublished_versions_have_no_pdf_route`、`test_unpublished_report_never_leaves_server`；本次重跑 61 項通過 |
| FIXTURE 在卡片、標題、模型欄（「無（FIXTURE，非 Agent 產出）」）、來源抽屜都有標示。API 的 `synthetic_fixture` 為 true，LIVE 報告為 false。內容取自 MOPS 原文，不是虛構新聞 | ✅ |

**CR 建議（W11 再做，不在本週範圍）**：FIXTURE 卡片和 LIVE 一樣顯示「已發布」與資料品質，可以在 FIXTURE 卡片加一行「測試資料，非 Agent 研究」，讓不熟系統的人不會誤會。

## 四、抽查正式輸出的季度、比較、DCF 表與 PDF

詳細結果在 `reports/v12-consistency-batch1.md`，比對程式是 `scripts/w10_consistency_check.py`。做法是三方比對同一個 report_version_id：

- 核准 JSON（網頁的資料來源）
- 網頁顯示的文字
- PDF 的文字

以 JSON 為準，逐項去網頁和 PDF 找。

**結果**：

- **數字類全部一致**（4 個版本）：
  - 季度表的營收、營業利益、淨利、EPS 與來源、FCF、可得時間
  - TTM
  - DCF：5 年現值、終端現值、企業價值、淨負債、股東權益
  - 3×3 敏感度
  - 估值狀態、差距、基準收盤價
  - 主張內文、引用、限制
- **NA 沒有遺失**：
  - 2317 的 DCF 兩邊都寫「TTM FCF ≤ 0，5 年持平情境不適用」。
  - 同業比較兩邊都寫「只適用 2454」。
- **找到的不一致：網頁比 PDF 少了內容**，資料本身沒有遺失：
  1. 「未知事項」：4 個版本各 2 條，只出現在 PDF。
  2. 「基本面觀察」「正面因素」：例如 2330 第 2 版，只出現在 PDF。
  3. 兩個舊版各有 1 個來源，只出現在 PDF 的來源清單。網頁本來只顯示主張引用的來源，沒有完整清單。
- **處理**：
  - 報告 API 輸出全部草稿段落。
  - 網頁依 PDF 的標題與順序顯示，並新增「來源清單」。
  - 標題由 `report_pdf.SECTION_TITLES` 統一，`tests/test_w10_consistency.py` 會核對網頁和 PDF 用的是同一份。
  - 只改 `research_ui/`、`static/`。報告內容、PDF、hash 都沒有改，已發布的版本不需要重產。
- **前後測試**：
  - `tests/test_w10_consistency.py` 2 項：在 main 上載入就失敗（沒有 `OBSERVATION_KEYS`），本分支通過。
  - 本機用同一支比對程式跑 3 份 MOCK 驗收版，共 190 項，網頁與 PDF 全部一致。
  - 全套 `pytest`：**530 passed**（main 為 528）。

## 五、手機預覽

- Render，375×812 手機模擬：
  - 報告頁沒有水平溢出（頁寬 375）。
  - 「預覽 PDF／下載 PDF」按鈕高 40 px。
  - 來源抽屜在畫面內。
  - 按「預覽 PDF」會直接在瀏覽器開啟 3 頁 PDF（截圖 09）。
- 限制：截圖 09 是內建瀏覽器的 PDF 檢視器。實機上 iOS 會直接顯示，Android 多半交給系統的 PDF 檢視器或下載。這次沒有用實體手機測試。

## 六、交給 E 的畫面與版本

`screenshots/w10/` 共 15 張圖（Render 實拍與 Render PDF 原檔轉圖），README 裡每張都寫了網址、版本、標籤和「這張圖要看什麼」。

- 報告頁的截圖是部署本分支之前拍的，所以還沒有新增的段落和來源清單。合併部署後補拍 02、03、04、06。
- 可以用在簡報的：
  - 01／08：儀表板
  - 02／06：報告
  - 03：舊版
  - 04：缺值
  - 07：來源
  - 09～11：PDF
- 05 是 FIXTURE，要用的話旁邊標「測試資料」。

## 七、未完成與需要誰

| 事項 | 原因 | 誰 |
|---|---|---|
| Render 上的修正後比對、補拍 02／03／04／06 | 本分支要先合併、Render 要先部署 | 組長合併；A 部署後重跑 |
| 前瞻第 3 批 2454 的一致性與 obs 來源抽屜 | 還沒有發布（等 B 核對） | B、組長 |
| 實體手機預覽 | 這次只用模擬尺寸 | A 下週用自己的手機補測 |
| 存一份到 `E:\專題\2026秋季成果\W10\A\` | 這次無法存取 E 槽 | A 自己複製 |

## 八、實際執行的命令（皆 exit 0）

```
python -m pytest -q                                                    # 530 passed
python -m pytest -q tests/test_online_pdf.py tests/test_research_ui.py tests/test_publication.py tests/test_w10_consistency.py   # 61 passed
python scripts/build_freeze.py --verify --strict                       # 凍結紀錄一致（cases-v1，cases_digest 98af84030d45）
python scripts/w07_demo_store.py /tmp/w10l/store
REPORT_DB_PATH=… REPORT_STORAGE_DIR=… gunicorn web_app:app --workers 1 -b 127.0.0.1:5110
python scripts/w10_capture.py --base http://127.0.0.1:5110 --out /tmp/w10l/cap
python scripts/w10_consistency_check.py --dir /tmp/w10l/cap --http /tmp/w10l/cap/http.json --out /tmp/w10l/local.md   # 3 版 0 缺
python scripts/w10_consistency_check.py --dir <Render 擷取檔> --http <Render HTTP 結果> --out reports/v12-consistency-batch1.md
```

Render 的資料是在內建瀏覽器裡用頁面自己的 `fetch` 取得：4 個版本的 JSON、PDF、網頁文字、HTTP 狀態與 sha256（容器連不到 onrender.com）。原始擷取檔不放進 repo。
