# V1.2 資料適配層與計算工具測試規約 (W03-B)

本規約定義由組員 B 實作之 6 大工具適配層的單元測試要求。由組員 D 整合至 `tests/test_audit_fixes.py` 或獨立測試套件中執行。

---

## 一、測試涵蓋清單

| 測試案例 ID | 目標工具 / 運算 | 測試情境與邊界條件 | 預期返回結果 |
| :--- | :--- | :--- | :--- |
| **TEST-01** | `search_evidence` | 查詢 cutoff（如 `2026-06-01`）晚於入庫時間之公告 | 回傳 `status: "no_data"`，嚴禁 Look-Ahead 前視洩漏 |
| **TEST-02** | `read_evidence` | 輸入不存在的 `evidence_version_id` | 回傳 `status: "no_data"`，不拋出未捕獲例外 |
| **TEST-03** | `get_financial_snapshot` | 僅有 3 季數據，嘗試計算 TTM | `eps_ttm` 與 `fcf_ttm` 回傳 `null`，不可僅以 3 季年化 |
| **TEST-04** | `get_price_window` | 請求 `sessions: 10`（非 1, 5, 20） | 回傳 `status: "invalid_input"` |
| **TEST-05** | `calculate_metrics` (`pe_ttm`) | 輸入 `eps_ttm <= 0` | 回傳 `status: "invalid_input"`，標註 NA 不算負 PE |
| **TEST-06** | `calculate_metrics` (`dcf_scenario`) | 輸入 $WACC \le g$（例如 $WACC=0.03, g=0.03$） | 回傳 `status: "invalid_input"`，拒絕無效折現計算 |
| **TEST-07** | `calculate_metrics` (`dcf_scenario`) | 關鍵參數（如 `net_debt`）為缺失 `None` | 回傳 `status: "invalid_input"`，禁止擅自以 0 補缺值 |
| **TEST-08** | `calculate_metrics` (`peer_comparison`) | 主體非 `2454` 或比較公司超過 4 家 | 回傳 `status: "invalid_input"` |
| **TEST-09** | `calculate_metrics` (`peer_comparison`) | 輸入同業包含 `2330` 產業參照 | 2330 標註為 `industry_reference`，**同業平均值計算嚴格剔除 2330** |

---

## 二、測試執行方式 (供組員 D 執行)

```bash
# 於專案根目錄下執行適配層測試
pytest -q tests/test_adapter_tools.py