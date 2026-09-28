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
| 每次輸出上限 | 1,500 token；temperature 0 | `BudgetLimits` |
| thinking | `thinking_budget` 預設 0，可設定且計入預留 | `GeminiAdapter(thinking_budget=)` |
| 工具 | Researcher 六個、Reviewer 四個（read/financial/macro/calculate） | `agents/tools.py:ROLE_TOOLS` |
| prompt 版本 | `v1.2`；每次發送記 prompt sha256 | `agents/contract.py:PROMPT_VERSION` |
| usage 記錄 | model_id、回傳 model_version、prompt_version、prompt_hash、usageMetadata 全欄 | `job_events`＋`model_usage` |

## 待組長決定（未填，不猜）

| 設定 | 狀態 | 說明 |
|---|---|---|
| `GEMINI_MODEL` | **未定** | 需在 AI Studio 確認該 model 支援 function calling 與 thinking 設定，並有可用 RPM/TPM/RPD |
| `GEMINI_API_KEY` | 本機未設定 | 只放後端 `.env`／Render env，不進 repo、不給 C/E |
| quota | 未核實 → J=0 | 填 `handoff/quota-baseline.json` 的 gemini 區塊 |
| thinking 是否開啟 | 未定 | 開啟需設上限；每次預留＝輸入估計＋1,500＋thinking_budget |

## token 估算方式

送出前以保守上限預估：非 ASCII 字元 1 字 1 token、ASCII 2 字元 1 token（實際通常更少），單次輸入 >3,000 即拒送；每次預留「估計輸入＋1,500＋thinking」，全 job ≤ 40,000。收到回應後以 `usage_metadata.total_token_count` 對帳；供應商沒回 usage 時保留預留值不退。live 驗證時需比對「估計 ≥ 實際」是否成立。
