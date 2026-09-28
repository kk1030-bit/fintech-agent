# Quota／預算測試紀錄（W03-L）

## 2026-09-28 離線（MOCK）測試 — 已執行

- 環境：macOS、Python 3.14.7、google-genai 2.25.0、langgraph 1.2.12、pytest 9.1.1
- 基於 commit：`69fb3f2`＋本次 W01–W03 組長變更
- 命令：`.venv/bin/python -m pytest -q tests`
- 結果：**52 passed, 1 warning**（warning 為 google-genai 在 Python 3.14 的 `_UnionGenericAlias` DeprecationWarning，非本專案程式）
- 變異檢查：暫時把 `max_calls` 改為 9 → `test_eight_call_cap_counts_failures_and_is_persisted`、`test_retries_share_the_eight_call_cap` 失敗（2 failed, 50 passed），確認測試真的會擋；已改回 8 並重跑通過。

| 驗收項 | 測試 | 結果 |
|---|---|---|
| 8 次上限含失敗 | `test_eight_call_cap_counts_failures_and_is_persisted`、`test_non_retryable_error_counts_and_raises` | 通過（MOCK） |
| 重試共用 8 次上限 | `test_retries_share_the_eight_call_cap`、`test_429_retry_once_then_pause_and_both_sends_counted` | 通過（MOCK） |
| usage 記錄 model/prompt 版本 | `test_usage_records_model_and_prompt_version` | 通過（MOCK） |
| 不啟用付費 fallback | `test_no_fallback_model`；程式無備援 model 路徑 | 通過 |
| 仍六工具 | `test_still_six_tools_and_peer_comparison_is_an_operation` | 通過 |
| 參照股不新增 LLM job | `test_comparison_only_tickers_do_not_create_llm_jobs`、`test_api_rejects_reference_ticker` | 通過 |
| peer_comparison 最多 4 家 | `test_peer_comparison_rejections` | 通過 |
| 未核實 quota 不送出 | `test_unknown_quota_blocks_live_sends`、`test_unknown_quota_sends_nothing` | 通過 |

## Live 驗證 — 未執行

- 原因：本機 `.env` 無 `GEMINI_API_KEY`；`GEMINI_MODEL` 未定；quota 未核實（J=0）。
- 待組長提供後的建議最小批次（共 ≤3 次發送，待組長核准）：
  1. 一次純文字、無工具的脫敏請求（W01 步驟 2），記錄 usageMetadata 與估計 token 的差距。
  2. 一次工具呼叫往返（2 次發送），工具回合成 fixture（`synthetic_fixture: true`），不涉及真實財報。
- 每次結果貼在本檔：日期時間、model_id、model_version、prompt_hash、usage、估計 token、結果碼。
