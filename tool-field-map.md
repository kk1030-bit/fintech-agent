# Agent 6大工具與模組對照表 (V1.2)
| 工具名稱 | 重用模組位置 | 職責與規則限制 | 欄位/快照快取要求 |
| :--- | :--- | :--- | :--- |
| `search_evidence` | `agents/tools/search.py` (待建) | 查詢財報公告、重大訊息。缺值回傳 `no_data`。不假造來源。 | `source_url`, `captured_at`, `hash` |
| `read_evidence` | `agents/tools/reader.py` (待建) | 讀取指定文件/URL。僅供審查與提取，不計算。 | `content_hash`, `available_at` |
| `get_financial_snapshot` | `report_downloader_2.py` 改寫 | 抓取三大表。嚴格區分 `single_quarter` (單季) / `ytd` (累計) / `instant` (存量)。 | `period`, `unit`, `currency`, `statement_basis` |
| `get_macro_snapshot` | `fred_scraper.py` | 抓取 FRED 總經快照 (CPI, GDP 等)。 | `vintage_date`, `observation_date`, `unit` |
| `get_price_window` | `report_downloader_2.py` (`fetch_price_history`) | 抓取指定區間股價，作為 P/E, P/B 分子。 | `close_price`, `currency`, `trade_date` |
| `calculate_metrics` | `financial_analyzer.py` 擴充 | 計算 TTM, YoY, P/E, P/B, FCF 及 `peer_comparison`。同日價格處理，2330 為產業參照，不入 2454 平均。 | `metric_type`, `calculation_basis` |