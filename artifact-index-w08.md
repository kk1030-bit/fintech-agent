# 簡報成果與素材索引（W08-E）

> 供組長審核。W08 僅用於檔案管理，簡報內不需顯示週次。依 GitHub main 的原始任務、`W08-status.md`（2026-11-11）及 A/B/C/D 交付文件整理；不自行認定實驗結果正確或已驗收。

## 一、交付項目

| 項目 | 位置／說明 | 狀態 |
|---|---|---|
| 整合簡報 PDF | `deliverables/E/deck-W08-E-integrated-v1.pdf` | 預定上傳，尚待確認 |
| Canva 可編輯版 | https://www.canva.com/design/DAHaa9fBxbs/edit | 已有連結，請組長確認存取權 |
| 成果索引 | `deliverables/E/artifact-index-w08.md` | 本文件 |
| 原規格 `slides/deck-v7.pptx` | 擬以 PDF＋Canva 替代 | **待組長同意** |
| 原規格 `slides/v12-graph-and-limits.pptx` | 擬以整合簡報的來源／限制頁替代 | **待組長同意** |

原始規格另要求修改第 10 頁與備用第 19 頁、整理八件成果、資源成本、2D 來源與限制。現有 28 頁由組長決定刪減；尚不能宣稱符合原規格 16 主頁＋4 備用。

## 二、八件成果及證據狀態

以下沿用 `W08-status.md` 與 `docs/v12-limitations-midterm.md` 的狀態，不以完成百分比代替驗收。

| # | 成果 | 狀態 | 來源／缺口 |
|---|---|---|---|
| 1 | 網站、三檔入口、季度、同業比較、收藏儀表板 | 核心已簽核 | `W08-status.md`；F06 延後、手機實機未測 |
| 2 | Researcher／Reviewer 閉環 | 已簽核，附限制 | `handoff/W06-gate-v12.md`；v2 正式評估待驗證 |
| 3 | 來源、動作、版本、預算、停止原因可追溯 | 有證據 | `evaluation/v12-forward-manifest.csv`；v2 停止原因待正式驗證 |
| 4 | 三份研究 PDF | 部分達成 | 2330、2317 LIVE 已發布；2454 無 LIVE 已發布報告 |
| 5 | 30 案三模式執行與評分紀錄 | 開發集有紀錄 | 保留集 20 案×3 模式＝60 run 尚待正式評分 |
| 6 | 20–25 頁論文 | 進行中 | 第四章 v1 已提交；第五、六章待完成 |
| 7 | 簡報、講稿、展示與錄影 | 進行中 | 本次 E 交付待審核；錄影排 W13 |
| 8 | 版本、設定、測試、來源交接包 | 進行中 | `handoff/`、`data-freeze.md`；完整交接排 W12–W13 |

## 三、簡報素材來源索引

| 內容 | GitHub main 路徑 | 標籤與限制 |
|---|---|---|
| Render 研究工作台 | `design/w08/e-render/01-render-overview-1440.jpg` | Render 介面；研究 job 在組長 Mac 執行 |
| 2330 LIVE v2 詳情 | `design/w08/e-render/03-render-report-2330-live-v2-1440.jpg` | LIVE；`rv-db6b0e1b`；截止 2026/11/06 21:00 |
| 2317 LIVE v2 詳情 | `design/w08/e-render/03-render-report-2317-live-v2-1440.jpg` | LIVE；`rv-2ed6652e`；截止 2026/10/30 21:00 |
| 2330 PDF 展示 | `design/w08/e-render/05-render-pdf-2330-live-v2-p1.png`（p2–p3 同目錄） | LIVE；不是保留集正式評分 |
| 2317 PDF 展示 | `design/w08/e-render/05-render-pdf-2317-live-v2-p1.png`（p2–p3 同目錄） | LIVE；TTM FCF ≤ 0，DCF 無法判定 |
| REPLAY 流程 | `design/w08/e-render/04-render-replay-case04-1440.jpg` | 真實紀錄重播，不是現場運算 |
| 2454 PDF（如引用） | `design/w08/e-render/06-local-pdf-2454-mock-p1.png` | MOCK；不能稱為 LIVE 結論 |
| 已發布清單 `02-*` | `design/w08/e-render/README.md` | 舊版畫面，A 待補拍，暫不使用 |
| D 安全／故障測試 | `evaluation/fault-and-security-w08.md` | 本機離線 mock；417 passed，非上線測試 |
| A 效能、D 核對 | `design/performance-w08.md`、`evaluation/v12-load-graph-check.md` | A 本機量測；D 未自行重測 |
| 2D 關係與來源 | `data/v12-capacity-and-graph-audit.md`、`ui/v12-graph-check.md` | F06 延後；不能宣稱圖已上線 |
| 資源成本與限制 | `docs/v12-limitations-midterm.md`、`operations/v12-resource-gate.md` | 實值與規劃分開 |

LIVE 表示真實執行且經組長核准發布，**覆核通過不等於結論正確**。REPLAY 是執行紀錄重播；MOCK 是預錄模型決策的介面測試。均不可代替保留集正式評分。

## 四、資源成本及操作限制（實值／估算分開）

| 項目 | 數值與事實 | 分類 |
|---|---|---|
| Render | Free、512 MB RAM，閒置休眠 | 實際方案 |
| Render 2 GB | 規劃在 PDF 記憶體不足時評估升級，US$25／月，未開通 | **條件式規劃** |
| Render 記憶體峰值 | Free 無記憶體圖；發布成功無重啟，但無法得知峰值 | **待實測** |
| A 本機 PDF 記憶體峰值 | 約 468–479 MB | 本機量測，非 Render |
| A 本機唯讀負載 | 10 位訪客＋1 job，5 分鐘 9,293 筆，p95 14.8 ms，5xx 0；PDF 發布期間 p95 2,428 ms | 本機量測，D 僅核對 |
| Gemini 免費層 | 15 RPM、500 RPD；TPM 約 250,000 為後台圖表判讀、精確值未確認 | 組長紀錄 |
| 單 job 上限 | 8 次模型發送、10 工具、2 補查輪、180 秒主動時間 | 規格限制 |
| Supabase Free | DB 0.5 GB、Storage 1 GB、每月流量 5 GB | 方案限制 |
| 容量 80% 停止線 | Storage 800 MB、DB 400 MB、流量 4 GB；原則採用、尚未寫入發布流程 | **未實作** |

## 五、2D 來源表與待辦

**F06 2D 圖已由組長決定延後；網站和 PDF 沒有正式 2D 圖。** B 已核對的關係資料只有：

| ID | 關係 | 證據 | 狀態 |
|---|---|---|---|
| REL-01 | 2454 → 2330 晶圓代工供應 | 聯發科 114 年度年報 p.74，TWSE 2026/05/29 上傳 | 已核對，僅資料表 |
| REL-02 | 2379 → 2330 晶圓代工供應 | 瑞昱 114 年度年報 p.94，TWSE 2026/05/27 上傳 | 已核對，僅資料表 |

3034 → 2330 未獲年報證實，不能新增。

**待實測／受阻：** 真實 Supabase DB 暫失（無授權測試庫）、20 個並行請求（D 僅測循序）、Render 記憶體峰值、手機實機、容量 80% 停止線實作、2454 LIVE 發布、保留集 60 run 正式評分，以及 A 的最新版已發布清單截圖。

D 於 2026/11/07 本機離線 mock 全套 **417 passed**；B 已交叉核對、組長合併補註，但不可說成 Render 或正式 Supabase 實測。另 `docs/v12-limitations-midterm.md` 提及較新全套 449 項測試，兩數來自不同紀錄時點，不應混寫為 D 本次結果。

## 六、組長待確認

- [ ] 是否接受 **PDF＋Canva 編輯連結** 取代原規格兩份 PPTX。
- [ ] 是否接受先保留 28 頁，由組長自行刪減。
- [ ] 第 10 頁及備用第 19 頁的資源限制與 2D 資料表是否符合要求。
- [ ] A 圖片版本、B 來源資料、C 文字、D 測試及核准狀態是否一致。
- [ ] 後續正式保留集結果僅以 D 核准資料補入。

## 七、主要來源

- [原始 W08-E 任務](https://github.com/kk1030-bit/fintech-agent/blob/main/docs/handbook_V1.2/16_%E5%85%AD%E4%BA%BA84%E9%A0%85%E4%BB%BB%E5%8B%99.csv)
- [W08 中期狀態](https://github.com/kk1030-bit/fintech-agent/blob/main/W08-status.md)
- [中期研究限制](https://github.com/kk1030-bit/fintech-agent/blob/main/docs/v12-limitations-midterm.md)
- [A 截圖 README](https://github.com/kk1030-bit/fintech-agent/blob/main/design/w08/e-render/README.md)
- [D 故障安全測試](https://github.com/kk1030-bit/fintech-agent/blob/main/evaluation/fault-and-security-w08.md)
- [D 效能核對](https://github.com/kk1030-bit/fintech-agent/blob/main/evaluation/v12-load-graph-check.md)
- [B 關係來源稽核](https://github.com/kk1030-bit/fintech-agent/blob/main/data/v12-capacity-and-graph-audit.md)

**編製：E 文書與美編整合｜狀態：待組長審核。**
