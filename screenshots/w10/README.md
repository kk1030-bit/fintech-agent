# W10 截圖（A，2026-11-18）

擷取方式：

- Render 網頁：用 Claude 桌面 App 的內建瀏覽器實際開啟，以 html2canvas 1.4.1 擷取（scale 2），沒有修圖。
- PDF 頁面：Render 下載的原檔用 PyMuPDF 轉成圖（110 dpi）。
- 手機尺寸：內建瀏覽器的 375×812 手機模擬。

全部是**部署本分支之前**的線上畫面（main b4c36a7）。本分支合併部署後，報告頁會多出「基本面觀察／正面因素／未知事項」和「來源清單」，屆時再補拍 02、03、04、06。

給 E 用的時候，依 AGENTS.md 第五節：LIVE 圖不用另外加標籤；FIXTURE 圖旁邊寫短標籤「測試資料」。

| 檔案 | 畫面 | 網址 | 版本 | 標籤 | 這張圖要看什麼 |
|---|---|---|---|---|---|
| `w10-01-render-dashboard-1440.jpg` | S07 儀表板 | `/research` | 清單：2317、2330 各第 2 版＋3 份 FIXTURE | LIVE＋FIXTURE | 已發布清單每份研究只列最新版，舊版數量寫在卡片上 |
| `w10-02-render-2330-v2-report-1440.jpg` | S04 報告 | `/research?report=rv-db6b0e1b-…` | 2330 第 2 版（Agent v1） | LIVE | 版本、資料截止、快照、PDF 按鈕、季度表、DCF、歷史版本在同一頁 |
| `w10-03-render-2330-v1-old-version-1440.jpg` | S04 舊版 | `/research?report=rv-b2d43742-…` | 2330 第 1 版 | LIVE（舊版） | 舊版上方有提示並連到第 2 版；舊版保留供追溯 |
| `w10-04-render-2317-v2-dcf-na-1440.jpg` | S04 缺值 | `/research?report=rv-2ed6652e-…` | 2317 第 2 版 | LIVE | TTM FCF ≤ 0 時估值寫「無法判定」並附原因，不以 0 代替 |
| `w10-05-render-fixture-2454-labelled-1440.jpg` | 測試資料 | `/research?report=rv-fixture-2454-0002` | FIXTURE | FIXTURE | 測試資料在卡片、標題、模型欄（「非 Agent 產出」）、來源抽屜都標 FIXTURE，沒有 PDF |
| `w10-06-render-2330-v2-report-375.jpg` | S06 手機 | 同 02 | 2330 第 2 版 | LIVE | 手機寬度沒有溢出；「預覽 PDF／下載 PDF」高 40 px |
| `w10-07-render-2330-v2-drawer-375.jpg` | S04 來源抽屜（手機） | 同 02 | `ev-fwd1-2330-rev-202609` | LIVE | 來源 hash 吻合、cutoff 前可得、原始網址與段落 |
| `w10-08-render-dashboard-375.jpg` | S07 手機 | `/research` | 同 01 | LIVE＋FIXTURE | 手機上的已發布清單 |
| `w10-09-render-2330-v2-pdf-preview-375.jpg` | S06 PDF 預覽 | `/api/ui/reports/rv-db6b0e1b-….pdf` | 2330 第 2 版 | LIVE | 手機尺寸下按「預覽 PDF」直接在瀏覽器開啟（3 頁）。此為內建瀏覽器的檢視器，實機畫面依手機系統而定 |
| `w10-10-render-2330-v2-pdf-p1～p3.png` | PDF 內頁 | 同上 | 2330 第 2 版 | LIVE | PDF 第 1 頁的版本號、hash、快照與網頁相同 |
| `w10-11-render-2317-v2-pdf-p1～p3.png` | PDF 內頁 | `/api/ui/reports/rv-2ed6652e-….pdf` | 2317 第 2 版 | LIVE | DCF 無法判定時，PDF 同樣寫原因 |

備註：

- 02、06、07、08 與 W09 同一畫面的截圖位元組相同，因為頁面自 11/14 起沒有變動、擷取結果一致。
- html2canvas 會把 PDF 預覽折疊列畫成「1.」編號，實際頁面沒有這個編號。
