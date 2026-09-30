# Agent 測試命令（W02-L 鎖定）

所有命令在 repo 根目錄 `~/專題/fintech-agent` 執行。離線測試不需要任何 API key、不連網、不寫正式 Supabase。

## 環境

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-agent.txt
```

## 離線／確定性測試（每次改 `agents/` 都要跑）

```bash
.venv/bin/python -m pytest -q tests
```

| 檔案 | 涵蓋 |
|---|---|
| `tests/test_jobs_queue.py` | 重複建立回同一 job、重啟後 job 仍在、2379/3034 不建 job、單一活躍 job、lease 過期回收且預算不歸零、舊 worker 被 fencing 擋下、heartbeat、mock worker、錯誤持久化、API 未授權 401、未設 token 全拒、API 冪等 |
| `tests/test_budget_tools.py` | J 公式、未核實 quota 不送、前 4 次研究／第 5 次保留覆核、8 次含失敗、usage 未知保留預留、3,000/40,000 token、80% RPD/RPM、工具 10 次／同參數 2 次、補查 2 輪、180 秒、六工具與 peer_comparison 驗證、禁 URL/路徑/SQL |
| `tests/test_provider_mock.py` | **MOCK**：官方 SDK 型別的工具呼叫往返、SDK 隱藏重試與 AFC 關閉、usage 記錄 model/prompt 版本、429 重試一次後 paused_quota、重試共用 8 次、無 fallback、未核實 quota 不送、Reviewer 越權被拒 |

## 重啟測試（mock worker）

`test_expired_lease_is_recovered_and_stale_worker_is_fenced` 以假時鐘模擬 worker 當掉：lease 60 秒過期 → 新 worker 取回同一 job、`calls_used` 保留、舊 token 寫入被拒。

## 整合測試（尚未執行）

| 項目 | 前置 | 狀態 |
|---|---|---|
| Supabase 遷移演練＋rollback | 獨立測試專案（非正式庫） | 未執行：尚無測試專案 |
| Supabase 版 JobStore | 遷移演練通過 | 未實作 |
| Gemini live 往返 | key、model、quota 已設定 | 已執行 2026-09-28（3 次），見 quota-test-log.md |
| gunicorn＋worker 同 instance | W08 | 未執行 |
