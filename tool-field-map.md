# Agent 6大工具與模組對照表 (V1.2)

依據專題執行手冊 V1.2 第 02 章「六工具契約」與第 04 章 F01/F02 規格，本表定義 Researcher 與 Reviewer 所呼叫工具之責任邊界、底層重用模組、參數約束與快照欄位需求。

> **核心原則**：
> 1. 全系統嚴格限制為 6 大工具。`peer_comparison` 屬於 `calculate_metrics` 內部的 operation，不可列為獨立工具。
> 2. 工具底層未備齊數據或查無快照時，一律回傳 `{"status": "no_data", "data": null}`，禁止補 0 或模型憑空推估。
> 3. 所有依賴來源必須可追溯至不可變快照（帶 `content_hash` 與 `captured_at`）。

---

| 工具名稱 | 實作與重用模組位置 | 角色權限 | 職責與規則限制 | 欄位/快照快取要求 |
| :--- | :--- | :--- | :--- | :--- |
| `search_evidence` | `agents/tools_impl.py` (`search_evidence`) | Researcher 專用 | 查詢已入庫之公開財報公告、總經指標與重大訊息索引。禁止通用網頁爬蟲。參數包含 `ticker` (2330/2317/2454)、`query` (≤200字)、`cutoff`、`limit` (1~5)。 | `source_id`, `title`, `published_at`, `captured_at`, `available_at`, `content_hash` |
| `read_evidence` | `agents/tools_impl.py` (`read_evidence`) | Researcher / Reviewer | 讀取快照內單一不可變文本片段（繁中 ≤1,200 字）。僅供審查與事實提取，不執行任何數學運算。無效 ID 回傳 `no_data`。 | `evidence_version_id`, `paragraph`, `source_url`, `content_hash`, `available_at` |
| `get_financial_snapshot` | `agents/tools_impl.py` (`get_financial_snapshot`) | Researcher / Reviewer | 取得指定 `cutoff` 前之 FinMind 財務指標。嚴格區分 `single_quarter`、`ytd` 與 `instant`。YTD 轉單季需同口徑前期相減，資產負債存量不可跨期相加。缺值回傳 `null` 並記 `missing_reason`。 | `stock_id`, `metric`, `fiscal_year`, `fiscal_quarter`, `period_basis`, `value`, `unit`, `currency`, `statement_basis`, `available_at` |
| `get_macro_snapshot` | `agents/tools_impl.py` (`get_macro_snapshot`) | Researcher / Reviewer | 取得已核准白名單之總經快照 (FRED: CPI, UNRATE, FEDFUNDS, GDP, DGS10; TW: TWII)。區分資料觀察期 (`observation_date`) 與官方發布/修訂時間 (`available_at`)。 | `series_id`, `indicator`, `observation_date`, `available_at`, `value`, `unit`, `source` |
| `get_price_window` | `agents/tools_impl.py` (`get_price_window`) | Researcher 專用 (Reviewer 需查價退件) | 抓取台股指定交易日數 (`sessions`: 1, 5, 20) 之收盤價視窗，截至 `end_at`。作為 P/E、P/B 等相對估值之分子。停牌或缺價回傳 `no_data`。 | `ticker`, `trade_date`, `close_price`, `currency`, `price_basis` (raw/adjusted) |
| `calculate_metrics` | `agents/calculator.py` (`execute_calculation`) | Researcher / Reviewer | 執行確定性純數學計算，禁止 LLM 自行運算。支援 operations：`growth_rate`、`simple_return`、`pe_ttm`、`dcf_scenario`、`peer_comparison`。所有運算必須帶入 `evidence_refs`。 | `operation`, `calculation_basis`, `result_value`, `is_applicable`, `evidence_refs` |

---

### `calculate_metrics` 專屬作業規則 (Operations)
1. **`pe_ttm`**：基準日收盤價 / 累計 4 季連續單季 EPS。分母 ≤ 0 則標註 `is_applicable=false`，不可計算負 P/E。
2. **`peer_comparison`**：
   - 主體限制：以 `2454` 為核心。
   - 比較同業：`2379`、`3034`。
   - 產業參照：`2330` 標註為「產業參照」，**絕對不可納入同業平均值計算**。
   - 上限：包含主體最多 4 家公司。所有公司股價必須對齊同一基準日，各自財報期需明確揭示。
3. **`dcf_scenario`**：
   - $FCF = CFO - \text{CapEx}$（先校驗 CapEx 符號，資本支出必須為正值流出扣除，若為負數現金流須轉換，禁止任意絕對值處理）。
   - 必要參數：$FCF$（5年數列）、$WACC$、$g$（終端成長率）、淨負債、流通股數。
   - 約束：$WACC > g$，缺關鍵參數一律為 `null`，禁止補 0。