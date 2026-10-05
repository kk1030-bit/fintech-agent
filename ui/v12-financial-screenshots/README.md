# W04-A｜報告詳情、來源抽屜、季度同業比較

- 任務 ID：W04-A（2026-10-05～10-09）｜驗收人：組長｜數字確認：B、D
- 分支：`codex/W04-A-report-detail`（基於 W03-A）
- 前置：W03-A ✓；W04-L（組長 Researcher runner）**尚未在 main** → 報告內容用 FIXTURE

## 做了什麼

1. **報告詳情**（`GET /api/ui/reports/<report_version_id>`，`/research?report=`）：只回 `published` 版本，草稿與不存在一律 404。主張標「事實／推論／未知」，另標「無來源」「有限制」「快照過期」；列反向證據、下一個確認訊號、方法限制。
2. **來源抽屜**（`GET /api/ui/evidence/<evidence_version_id>`）：用 B 的 `read_evidence` 讀快照內不可變片段，顯示原文、可得時間、原始連結；**重算 sha256 與記錄 hash 比對**，並依報告 cutoff 標「cutoff 前可得／後才可得」。只開放已發布報告或比較面板引用的 ID。快照中沒有的 ID → 「無來源」，按鈕加刪除線。
3. **2454 季度同業比較**（`GET /api/ui/comparison/2454`）：依 `ui/v12-comparison-contract.md`。主值只採 B 工具可重現的數字（`get_financial_snapshot`、`get_price_window`、`calculate_metrics`）；B 快照有但工具重現不了的值，以「B 快照值・工具未能重現」小字呈現，不進同業平均。每列顯示財報期、可得季數、同日收盤價與日期；2330 標「產業參照・不入平均」。手機改卡片。
4. P/E 一律 = 同日收盤價 ÷ TTM EPS（`calculate_metrics(pe_ttm)`），**不再使用 `main.py` 的營收/淨利替代值**。

## 截圖（本機，headless Chromium，2026-10-05，橫向溢出皆 0 px）

| 檔案 | 內容 | 尺寸 |
|---|---|---|
| W04-report-2454-1440-full.png | 2454 報告：4 項主張、無來源/限制標籤 | 1440 寬全頁 |
| W04-source-drawer-hash-1440x900.png | 來源抽屜：hash 不符、cutoff 前可得 | 1440×900 |
| W04-source-drawer-390x844.png | 來源抽屜（手機底部面板） | 390×844 |
| W04-no-source-390x844.png | 點刪除線來源 → 無來源說明 | 390×844 |
| W04-comparison-1440x900.png | 同業比較表：NA＋原因、快照值、產業參照 | 1440×900 |
| W04-report-and-comparison-390-full.png | 手機全頁：報告＋比較卡片 | 390 寬全頁 |
| W04-report-2317-insufficient-1440x900.png | 2317 資料不足報告 | 1440×900 |

## 測試（實際執行）

`.venv/bin/python -m pytest -q tests` → **111 passed**（2026-10-05）。W04 新增：主張種類與無來源判定、草稿內容不出現在任何公開回應、hash 不符會如實回報、cutoff 檢查、缺片段 404 no_data、未引用 ID 拒絕、比較 ≤4 家／2330 排除／P/E = 價格÷TTM EPS／任何指標不顯示 0／缺值必有原因、研究頁模組不 import 模型或預算程式。

## 驗收自查

| 驗收項 | 結果 |
|---|---|
| 來源內容與引用一致 | ✓ c1「1,272.7 億、EPS 16.19」與 `ev-2454-2026q2-01` 原文一致（測試）；但該片段 **hash 不符**，已在畫面標示，待 B |
| 不以記憶補數字 | ✓ 所有數字來自 B 快照或工具；工具重現不了的不當主值 |
| 桌機/手機長文無重疊 | ✓ 1440/390 截圖、溢出 0 px |
| 每列來源/時間可查；不再用營收比當 PE/PB | ✓ 每列有財報期、可得時間、收盤日、來源 ID；P/E 走 `pe_ttm`；P/B 無 BVPS → NA |
| B/D 確認數字 | ✗ **尚未**。B、D 需確認比較契約 §4 的 6 項問題 |

## 另發現（交 B）

- 2454 的 evidence `available_at` 為 15:00，但同一季財報快照的 `available_at` 為 16:00，同一事件兩個可得時間。
