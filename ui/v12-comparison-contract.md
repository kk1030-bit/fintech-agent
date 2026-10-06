# W03-A｜2454 季度同業比較面板 介面契約（UI ↔ B 資料）

- 任務 ID：W03-A｜日期 2026-10-05｜驗收人：組長｜數字核對：B、D
- 依據：手冊第 04 章 F02、第 02 章 `calculate_metrics(peer_comparison)`；B 的 `data/v12-peer-snapshot.json`、`data/financial-snapshots.json`、`agents/tools_impl.py`、`agents/calculator.py`
- 狀態：契約草案，W04-A 依此實作 `GET /api/ui/comparison/2454`

## 1. 角色與上限（固定）

| 代號 | 角色 | 入同業平均 | 可建研究 job |
|---|---|---|---|
| 2454 聯發科 | `subject` 主體 | — | 是 |
| 2379 瑞昱 | `peer` 同業 | 是 | **否**（只跑確定性工具） |
| 3034 聯詠 | `peer` 同業 | 是 | **否** |
| 2330 台積電 | `industry_reference` 產業參照 | **否**（畫面標「產業參照・不入平均」） | 是（但在本面板只作參照） |

最多 4 家（含主體）。面板純讀，0 次 LLM；切換、重整不會重算或建立 job。

## 2. UI 端點回傳格式（W04 實作）

```json
{
  "ok": true,
  "subject": "2454",
  "price_as_of": "2026-09-30",
  "cutoff_at": "2026-09-30T17:00:00+08:00",
  "method_version": "ui-peer-v1 / calculator(B) / tools-v12.0",
  "synthetic_fixture": true,
  "fixture_note": "B 快照尚未經 D 確認",
  "rows": [
    {
      "ticker": "2454", "name": "聯發科", "role": "subject",
      "financial_period": "2026Q2", "available_at": "2026-08-10T16:00:00+08:00",
      "price": {"value": 1250.0, "trade_date": "2026-09-30", "basis": "raw_close"},
      "metrics": {
        "pe_ttm":              {"value": 18.38, "na_reason": null, "source": "tool", "snapshot_value": 18.38, "consistent": true},
        "pb":                  {"value": null,  "na_reason": "快照沒有 BVPS，工具無法重算", "source": "snapshot_only", "snapshot_value": 3.85},
        "revenue_yoy_quarter": {"value": null,  "na_reason": "缺去年同季基期（2025Q2）", "source": "snapshot_only", "snapshot_value": 0.15},
        "fcf_ttm":             {"value": 1123.9, "unit": "億元", "source": "tool", "snapshot_value": 1123.9, "consistent": true},
        "dcf_gap":             {"value": null,  "na_reason": "DCF 參數（WACC、g）未提供", "source": "snapshot_only", "snapshot_value": -0.7478}
      },
      "evidence_refs": ["ev-2454-2026q2-01", "ev-price-20260930-2454"],
      "include_in_peer_stats": false
    }
  ],
  "peer_stats": {"basis": "只用 role=peer 且同期間、值可由工具重現者", "pe_ttm": null, "n": 0, "excluded": ["2454", "2330"]},
  "checks": [{"ticker": "2379", "metric": "pe_ttm", "issue": "TTM 需連續 4 季，快照只有 2026Q2"}]
}
```

（上表數值僅示範欄位結構，實際由程式從 B 的檔案即時算出。）

## 3. 每格的取值規則

| 指標 | 公式 | 主值來源 | NA 條件（顯示「NA＋原因」，**永不顯示 0**） |
|---|---|---|---|
| P/E (TTM) | 同日收盤價 ÷ TTM EPS | `get_price_window(sessions=1)` + `get_financial_snapshot` 的 `eps_ttm`，再用 `calculate_metrics(pe_ttm)` | 無同日價格；TTM 不足連續 4 季；EPS ≤ 0 |
| P/B | 同日收盤價 ÷ BVPS | 需 BVPS；目前快照沒有 | 無 BVPS 或 BVPS ≤ 0 |
| 單季營收 YoY | (本季 − 去年同季) ÷ 去年同季 | `calculate_metrics(growth_rate)` | 缺去年同季、基期為 0 |
| FCF (TTM) | 營業現金流 − 正值 CapEx，連續 4 季加總 | `get_financial_snapshot` 的 `fcf_ttm` | 不足 4 季 |
| DCF 差距 | (DCF 每股值 − 同日市價) ÷ 同日市價 | 需 WACC、g、淨負債、股數、FCF；W05 才判 ±15% | 任一參數缺 |

- **主值只能是工具可重現的數字**。B 快照裡有、但工具重現不了的值，放在 `snapshot_value`，畫面標「B 快照值・工具未能重現」，不進同業平均。
- 主值與快照值不同時 `consistent=false`，列入 `checks` 交 B、D。
- 每列顯示**實際財報期**與 `available_at`；不同公司財報期不同時，面板頂端提示「財報期不一致」，同業統計只用期間一致者。
- 價格基準：`raw_close`，同一 `price_as_of`；某公司當日無價 → 該列 P/E、P/B、DCF 差距全部 NA，不拿別天價格補。
- 2330 一律 `include_in_peer_stats=false`。

## 4. 目前 B 資料的實查結果（2026-10-05，交 B、D）

| # | 問題 | 影響 | 需要誰 |
|---|---|---|---|
| 1 | `financial-snapshots.json` 中 2379、3034、2330 **只有 2026Q2 一季**，但 `v12-peer-snapshot.json` 給了 `eps_ttm` 26.15／35.53／38.2、`fcf_100m` 120.5／180.2／4500 | 工具算不出 TTM → 三家 P/E、FCF 主值為 NA，只能顯示快照值 | B 補 2025Q3–2026Q1 單季資料與來源 |
| 2 | 兩筆 evidence 的 `content_hash` 與 `sha256(paragraph)` **不相符** | 來源抽屜會標「hash 不符」 | B 重算 hash，或說明 hash 對象不是 paragraph |
| 3 | `ev-2379-2026q2-01`、`ev-3034-2026q2-01`、`ev-price-20260930-*` 在快照中**不存在** | 這些引用在畫面顯示「無來源」 | B 補 evidence 片段 |
| 4 | 快照沒有 BVPS、去年同季營收 | P/B、單季 YoY 只能顯示快照值 | B 補欄位 |
| 5 | 兩個快照檔都沒有 `synthetic_fixture` 欄位；`source_url` 皆為 MOPS 通用查詢頁 | 無法判定是真實財報或合成資料 → 畫面一律標 FIXTURE | B 標明真實/合成，補精確來源連結 |
| 6 | 2454 的 P/E 18.38、FCF 1123.9 由工具重現**一致**；同業平均 P/E 17.35 只用 2379、3034 算，排除 2330 **正確** | — | D 覆核 |
