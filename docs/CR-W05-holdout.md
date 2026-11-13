# CR-W05：保留集執行所需之 agents/snapshot.py 調整（組長負責）

B 已依固定分配表重建 20 個保留案例（`evaluation/test-cases-sealed.json`、`fixtures/test/case_fixtures.json`，封存紀錄 `fixtures/test/SEAL.json`）。`agents/snapshot.py` 目前只讀開發集快照，保留集正式執行（W10、60 run）前需以下調整。B 不直接修改組長檔案。

| # | 現況 | 建議 |
|---|---|---|
| 1 | `load_case_snapshot()` 只讀 `fixtures/dev/case_fixtures.json` | 依 `snapshot_id` 前綴：`snap-dev-` 讀開發集、`snap-test-` 讀 `fixtures/test/case_fixtures.json`；保留集只在評分執行時載入 |
| 2 | `tool_simulation` 只在 CR-02 處理 `read_evidence` timeout | 保留案例設定 `tool_name = get_financial_snapshot`、`behavior = no_data` 時回傳 `{"status": "no_data", "reason": <reason>, "data": None}` |
| 3 | `financial_snapshot` 欄位為 null（例如 EPS、淨負債為 null）時直接回傳 | 保持 null 並帶 `missing_reason`，不可由全域快照補值 |
| 4 | 片段 `available_at` 為 null 時 `_t()` 會拋例外 | 以 `captured_at` 判定，兩者皆無視為不可得 |
| 5 | 部分保留案例帶有 `task_input`、`draft_under_review` 欄位，未傳入 job | 由組長決定如何放入研究題目；保留集答案欄位（expected_*）不得進入 prompt |

保留集封存後若需修改，請重跑 `python scripts/build_holdout_cases.py` 並以 `python scripts/check_cases.py` 驗證，再由 D 與組長確認新的 SEAL hash。

## 狀態（2026-10-28 更新；2026-11-08 依組長「保留集內容不出現在共用文件」移除案例編號與情境；2026-11-13 第 5 項完成，本 CR 結案）

- 第 1 項：**已完成**（組長 10/22，`load_case_snapshot()` 依 `snap-test-` 前綴讀 `fixtures/test/case_fixtures.json`）。
- 第 2、4 項：**已完成**（組長 10/26 合併 CR-W06：`agents/snapshot.py` 的 `_avail()` 以 `captured_at` 判定、`_simulated_no_data()` 處理 `behavior = no_data`；測試 `tests/test_snapshot_holdout_guard.py`）。CR-W06 文件已結案刪除，內容可由 git 歷史查回。
- 第 3 項：現行程式原樣回傳 null，符合要求。
- 第 5 項：**已完成**（組長 11/13，決策第 31 節，commit 967f56b）。依 B 11/13 的回覆（只講欄位用法）：研究焦點改送案例的 `task`、一字不改，不再送 `variant`；`task_input`、`draft_under_review` 由程式依欄位名稱從該 job 綁定的快照讀取，以同名欄位、JSON 原樣放進 Agent 輸入，不加說明、不串進 focus，single、workflow、dual（含 Reviewer）都有；`required_elements` 只列給評分者（盲評答卷的 `scorer_only`），不送 Agent；`variant`、`category`、`expected_*`、`allow_insufficient`、`perturbation_location` 都不進 Agent 輸入。每個 run 記 `focus_source`（task 或 variant）；11/12 以前的校準 v1、v2 與煙霧測試是送 `variant` 的條件，不可與送 `task` 的結果直接比較。開發集題目由 B 另放 `evaluation/dev-tasks.json`（`case_id`、`task`），`evaluation/dev-cases.json` 與 cases_digest 不動。測試：`tests/test_task_inputs.py`。
- 本 CR 五項全部完成，保留作為紀錄；之後保留集若需調整，另開新 CR。