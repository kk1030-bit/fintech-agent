# W09-A｜核心介面回歸與展示素材

- 負責：A（陳柏臣）｜擷取與測試日期：2026-11-14（台北）｜驗收人：組長
- 分支：`codex/W09-A`（基於 main 22618ac）；程式 commit 476aa5b，文件與素材另一個 commit
- Render：https://fintech-agent-di0z.onrender.com/research（擷取時 main = 22618ac；沒有另外核對 Render 實際部署的 commit）
- 本機：`gunicorn web_app:app`，`RESEARCH_UI_MOCK=1`，報告庫用 `scripts/w07_demo_store.py` 載入的 W07 MOCK 驗收版本
- 素材總表：`media/v12-screenshots-manifest.csv`（每張圖的 URL、日期、版本、LIVE／REPLAY／MOCK）

## 一、五點重述

| 項目 | 內容 |
|---|---|
| 目標 | 確認 job 恢復、PDF、手機沒有阻擋展示的問題；三條示範路徑能在網站上真實操作；交 E 一段標版本的操作片段與可用截圖 |
| 既有狀態 | W08 已做 PDF 快取／ETag、慢伺服器提示、重試；11/09 已上線「清單只列最新版」。回放清單只有 v1 之前的開發期紀錄 |
| 輸入 | `demo/script-v1.md`（E 的三分鐘講稿）、手冊 06 E01、`handoff/agent-version-changes.md`、`agent/` 的真實執行紀錄、Render 上的 LIVE 第 2 版 |
| 交付 | 本文件、`demo/sample-w09.mp4`、`media/v12-screenshots-manifest.csv`、`media/w09/` 16 張圖、回放清單修正與測試 |
| 驗收人 | 組長 |

## 二、job 恢復／PDF／手機：檢查結果

用 `scripts/w09_ui_probe.py` 在本機以瀏覽器實際操作，1440 與 390 兩種寬度各跑一次。結果檔 `design/w09/ui-probe.json`：**25／25 通過**。

| 項目 | 怎麼測 | 結果 |
|---|---|---|
| 執行中重新整理 | 送出 MOCK job，1.5 秒後重新整理 | 網址保留 `?job=`，畫面讀回同一個 job，之後照常跑完（`review_pass`），計數沒有歸零 |
| 輪詢時斷線 | 測試中攔截 `/api/ui/jobs/*` 5 秒 | 畫面保留最後狀態，寫「連線中斷，N 秒後重試」；恢復後自動接上 |
| 不存在的 job | 開 `?job=nonexistent-w09` | 顯示「找不到這個 job」，不會一直停在讀取中 |
| 配額暫停 | MOCK `paused_quota` | 顯示「暫停：配額」、停止原因 `daily_quota_exhausted`、模型請求 x/8、工具 x/10、補查 x/2、主動時間 x/180s（上限與 `agents/budget.py` 相同） |
| PDF | 預覽、下載、條件請求 | 預覽 inline、下載 attachment、位元組相同、帶 ETag 再請求回 304 |
| 手機版面 | 390 寬開報告、開來源抽屜 | 沒有水平溢出（DCF 敏感度表在自己的捲動框內）；PDF 按鈕沒被遮住、高 40 px；抽屜在畫面內 |
| 頁面錯誤 | 全程監聽 | 0 筆 |

Render 上另外實測（內建瀏覽器，375 寬模擬手機）：2330 第 2 版 PDF 預覽 200、下載 200、檔頭 `%PDF-`、376,205 bytes、同一 ETag、條件請求 304；頁面寬 375 沒有溢出；來源抽屜 hash 吻合。Render 開 `?job=` 會顯示「研究入口未啟用」，這是組長的設定（Render 不開放研究入口），不是錯誤。

**結論：job 恢復、PDF、手機都沒有找到嚴重問題，這三項沒有改程式。**

只有一點照實記錄：檢查腳本第一次把「按鈕至少 40 px 高」也套到桌面版，桌面按鈕是 34 px，所以 24／25。這條規則是給手指點的，所以只檢查手機版；改完重跑 25／25。桌面版沒有改。

## 三、修掉的缺陷：回放清單沒有 Agent v2，也沒有版本標示

**問題**：網站的「真實執行紀錄回放」只讀三個開發期檔案（researcher-v1.2.0／1.2.1，10/15–10/21）：

- 11 筆全部都停在資料不足。
- 每一筆都沒有標 Agent 版本。

所以兩條示範路徑在網站上沒有可展示的 Agent v2 紀錄：

- 「覆核要求補查」（E 講稿 01:20–02:10）
- 「資料不足」（02:40–03:00）

觀眾也分不出某筆回放是哪一版 Agent 跑的，可能會把不同版本的結果混在一起看（AGENTS.md：v1 與 v2 不放同一張表）。

**修正**（`research_ui/replays.py`、`static/research.js`）：

1. 回放清單加入 5 個 Agent v2 dual 紀錄檔（`agent/calib-v2-dual-*.json`），共 17 筆。每一筆都標上：
   - Agent 版本
   - prompt 版本
   - 執行條件：補股價前或後、題目送 variant；這是第 25、31 節要求分開標示的條件
2. 下拉選單每個 Agent 版本一組，v2 在最上面，開發期在下面，不混在一起。
3. 回放畫面最上方顯示版本與條件，並加上版本標籤。
4. v2 回放顯示凍結開發集案例的資料截止時間與快照編號。10/25 凍結前的舊紀錄不顯示：當時的案例可能不同，所以寫「—」，不去猜。
5. `calib-v2-dual-postprice-1112:CASE-04` 加註「覆核程式誤判，規則已修」（決策紀錄第 28 節），紀錄本身照實保留。

只讀 `agent/` 的開發集紀錄，不讀保留集；測試裡也檢查了這一點。

**前後對照**（同一段檢查分別在 main 22618ac 與本分支執行）：

| | 修正前（main） | 修正後 |
|---|---|---|
| 回放筆數 | 11 | 28 |
| 有沒有版本欄位 | 沒有 | 每筆都有 |
| 有 Agent v2 的紀錄 | 0 | 17 |
| 有「退回修正」那一輪的紀錄 | 2 筆，都是開發期 | 另加 2 筆 Agent v2（CASE-15 day3、CASE-04 postprice） |
| 停止狀態 | 只有資料不足 | 也有通過覆核（v2 共 9 筆 `review_pass`） |

**測試**：`tests/test_w09_ui.py`，6 項。

- 在 main 上跑：載入失敗（`ImportError: cannot import name 'V2'`），因為 main 沒有版本欄位。
- 在本分支：6 項全過；全套 `pytest` **477 passed**（原本 471，加 6）。

## 四、三條示範路徑

依據：E 的講稿（`demo/script-v1.md`）與手冊 06 E01。E01 要求三個固定示範案例在有配額時真的執行，且至少一次覆核要求補查後修正、一次不足證據停止；Replay 只能證明回放，不能當 live。

| 路徑 | 網站上用什麼 | 標籤 | 驗證結果 |
|---|---|---|---|
| ① 正常：已核准報告 → 來源 → PDF | Render 2330 第 2 版 `rv-db6b0e1b…`（資料截止 11/06 21:00），也可用 2317 第 2 版 `rv-2ed6652e…` | **LIVE**（Agent v1，前瞻第 2 批） | ✅ Render 實測：清單、報告、來源抽屜、PDF 預覽／下載，桌面與手機都可操作 |
| ② 覆核要求補查 | 回放 `calib-v2-dual-day3:CASE-15`（11/08，開發集）。流程：第 1 輪 Reviewer 退回修正（c1、c2 critical）→ Researcher 補查改稿 → 第 2 輪仍資料不足，停止 | **REPLAY**（Agent v2） | ✅ 本機可操作；Render 要等本分支合併部署 |
| ③ 資料不足 | 回放 `calib-v2-dual-rerun-1112:CASE-18`（11/12，開發集，關鍵證據在 cutoff 之後）。Researcher 自己判定不足而停止，不下結論 | **REPLAY**（Agent v2） | ✅ 本機可操作；Render 同上 |

**路徑 ② 要照實講**：

- `agent/` 裡沒有任何一筆 Agent v2 紀錄是「退回修正後再通過」。v2 dual 的 9 筆通過，都是第 1 輪就通過。
- 能展示的是「要求補查 → 改稿 → 仍不足而停止」。講稿不能說成「補查後通過」。
- MOCK 的 `revise_then_pass` 情境畫面上有「退回 → 補查 → 通過」，但那是預錄腳本，只能說是介面展示。

**還不符合 E01 的地方**：

- ②③ 是 REPLAY，不是現場 LIVE 執行。
- Render 的研究入口沒有開放，現場沒辦法新開 LIVE job。
- 要現場跑，需要組長決定是否開放入口、要用哪天的配額。11/16–11/25 的配額已排給正式實驗（決策第 22 節）。

**路徑的選擇**：② 與 ③ 用哪一筆，由 D 核對 trace 後確認（E 講稿也寫待 D 核對）。上表是 A 的建議。

## 五、短操作片段 `demo/sample-w09.mp4`

- 71 秒，1280×800。用 `scripts/w09_record_sample.py` 以 Playwright 錄本機畫面，ffmpeg 只在上方加一條標籤列。
- 每一格畫面都標「本機（非 Render）・codex/W09-A 476aa5b・錄製 2026-11-14・MOCK／REPLAY，非 LIVE・無模型呼叫」。第二行寫目前這段在做什麼。

片段依序是：

1. 研究工作台與儀表板。已發布清單是本機核准的 MOCK 驗收版本。
2. 送出 MOCK job，看狀態與預算計數。
3. 執行中重新整理，同一個 job 從資料庫讀回。
4. MOCK job 結束：退回 → 補查 → 通過，未經人工核准不發布。
5. Agent v2 回放的版本標示。
6. CASE-15 的覆核兩輪。
7. CASE-18 資料不足。
8. 已核准報告與來源抽屜。
9. PDF 按鈕。

**限制**：

- 片中沒有 PDF 內頁，因為 headless 瀏覽器沒有 PDF 檢視器。PDF 畫面請用 `design/w08/e-render/05-render-pdf-*`，那是 Render LIVE 第 2 版的原檔轉圖。
- 片中的報告是 MOCK 驗收版。LIVE 報告畫面請用 `media/w09/w09-r02`、`r03`、`r05`。
- 容器與 Render 之間連不通，所以無法直接錄 Render。

## 六、S07 儀表板／S08 圖

- **S07**：Render 實拍，桌面 `w09-r01`、手機 `w09-r04`。清單只列每份研究的最新版，舊版在報告詳情裡標「舊版」。這兩張取代 11/08 的 `02-render-published-list-*`（已在 `design/w08/e-render/README.md` 註明不要再用）。
- **S08 2D 關聯圖：延後，不放圖。** F06 在 V1.2 不上線，網站與 PDF 都沒有 2D 圖。依據：決策紀錄第五節（10/22）、`ui/v12-graph-check.md`。簡報第 11 頁寫「2D 關聯圖延後至後續版本」，不要用示意圖代替。

## 七、未完成與需要誰

| 事項 | 原因 | 誰 |
|---|---|---|
| Render 上看到 Agent v2 回放 | 程式在 `codex/W09-A`，要合併到 main、Render 部署後才有 | 組長合併 |
| 路徑 ②③ 用哪一筆紀錄 | 講稿規定 trace 由 D 核對 | D |
| E01「示範案例有配額時真的執行」 | Render 研究入口不開放；配額已排正式實驗 | 組長決定（見交接短訊） |
| 交件時間 | 手冊排 11/13 週五交，本次 11/14 才完成 | — |

## 八、實際執行的命令（皆 exit 0）

```
python scripts/w07_demo_store.py /tmp/w09/store
REPORT_DB_PATH=… REPORT_STORAGE_DIR=… RESEARCH_UI_MOCK=1 RESEARCH_UI_MOCK_DB=… gunicorn web_app:app --workers 1 -b 127.0.0.1:5109
python -m pytest -q                                   # 477 passed
python -m pytest -q tests/test_w09_ui.py              # main 22618ac：ImportError；本分支 6 passed
python scripts/w09_ui_probe.py --base http://127.0.0.1:5109 --out design/w09/ui-probe.json   # 25/25
python scripts/w09_record_sample.py --base http://127.0.0.1:5109 --out tmp/w09-video --marks tmp/w09-video/marks.json
python -c "import scripts.w09_record_sample as m; m.caption('tmp/w09-video','demo/sample-w09.mp4', '<標籤列文字>')"
python scripts/w09_local_shots.py --base http://127.0.0.1:5109 --out media/w09
```

Render 截圖：Claude 桌面 App 內建瀏覽器開 Render，html2canvas 1.4.1 擷取（scale 2），存到下載資料夾再放進 repo，沒有修圖。

Render 端的 PDF 與 304 檢查：在同一頁用 `fetch` 執行。
