# 模型設定（W03-L）

## 已鎖定（程式強制）

| 設定 | 值 | 位置 |
|---|---|---|
| SDK | 官方 `google-genai` 2.25.0 | `requirements-agent.txt` |
| SDK 隱藏重試 | 關閉：`HttpRetryOptions(attempts=1)` | `agents/provider.py:make_client` |
| 自動函式呼叫 | 關閉：`AutomaticFunctionCallingConfig(disable=True)` | `GeminiAdapter.build_config` |
| 明確重試 | 408/429/5xx 最多 1 次，Retry-After＋0–1 秒抖動，與 8 次上限共用 | `GeminiAdapter.send` |
| 429 重試後仍失敗 | `paused_quota`，不狂重試 | 同上 |
| Fallback | **無**。只用一個 model id；與 quota 核實的 model 不同時拒絕啟動 | `GeminiAdapter.__init__` |
| 付費切換 | 無任何付費 tier 或備援 model 程式路徑 | — |
| 每次輸出上限 | 1,500 token，**含 thinking token**（官方：max_output_tokens 包含 thought tokens）；temperature 0 | `BudgetLimits` |
| thinking | `thinking_level` 預設 `minimal`；依 model 檢查可用等級（3.8/3.7 最低 low，設 minimal 會拒絕啟動）。Gemini 3 無法完全關閉 thinking | `agents/provider.py:THINKING_LEVELS` |
| thought signature | 工具往返時把 model 回應原樣放回對話，保留 `thought_signature`（Gemini 3 多輪 function calling 必要） | `run_tool_roundtrip` |
| 工具 | Researcher 六個、Reviewer 四個（read/financial/macro/calculate） | `agents/tools.py:ROLE_TOOLS` |
| prompt 版本 | `v1.2`；每次發送記 prompt sha256 | `agents/contract.py:PROMPT_VERSION` |
| usage 記錄 | model_id、回傳 model_version、prompt_version、prompt_hash、usageMetadata 全欄 | `job_events`＋`model_usage` |

## 組長設定

| 設定 | 狀態 | 說明 |
|---|---|---|
| `GEMINI_MODEL` | **`gemini-3.6-flash`**（組長 2026-09-28 選定） | 正式版、支援 function calling、免費層級、thinking 可設 minimal |
| `GEMINI_API_KEY` | 本機未設定 | 只放後端 `.env`／Render env，不進 repo、不給 C/E |
| quota | RPM 5／TPM 100,000／RPD 20（AI Studio，2026-09-28 15:50）→ J=2 | `handoff/quota-baseline.json`；截圖待補 |
| thinking 等級 | 預設 minimal | 若 live 測試發現 minimal 選工具品質不足，再由組長核准改 low |

## token 估算方式

送出前以保守上限預估：非 ASCII 字元 1 字 1 token、ASCII 2 字元 1 token（實際通常更少），單次輸入 >3,000 即拒送；每次預留「估計輸入＋1,500（已含 thinking）」，全 job ≤ 40,000。收到回應後以 `usage_metadata.total_token_count` 對帳；供應商沒回 usage 時保留預留值不退。live 驗證時需比對「估計 ≥ 實際」是否成立。

## 選型依據（2026-09-28 查官方文件）

- 來源：ai.google.dev/gemini-api/docs 的 models、pricing、thinking、rate-limits 頁。
- 3.8/3.7 Flash thinking 最低只能 low，會吃掉 1,500 輸出上限，不選；preview 版可能下架，不選；2.5 系列對新 project 限制存取。
- 免費層級資料可能用於改進 Google 產品：只送公開研究素材與合成 fixture。
- RPM 5 → 排程器 80% 為每分鐘 4 次；RPD 20 → 每日 16 次、J=2；900 次總預算需約 57 天，需組長重新評估配分（見 quota-baseline.json）。
