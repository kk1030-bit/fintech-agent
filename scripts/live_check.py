"""W01/W03 live check: at most 3 real Gemini sends. Run only with the lead's approval.

    .venv/bin/python scripts/live_check.py

Send 1   plain request, no tool use expected (W01 desensitised test).
Send 2-3 one tool-call round trip; the tool returns a SYNTHETIC fixture, no real
         company data is sent or fetched.

Uses a throwaway local job DB (tmp/live_check.sqlite3); nothing touches Supabase.
Prints usage per send and the gap between our token estimate and provider usage.
The API key is read from .env and never printed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from google.genai import types  # noqa: E402

from agents.budget import BudgetExceeded, BudgetGate, BudgetLimits, ProjectQuota, estimate_tokens  # noqa: E402
from agents.contract import validate_job_request  # noqa: E402
from agents.provider import GeminiAdapter, make_client  # noqa: E402
from agents.store import JobStore  # noqa: E402
from agents.tools import register_tool  # noqa: E402

SYSTEM = "You are a test harness for a research agent. Answer in Traditional Chinese, one short sentence."
PROMPT_1 = "連線測試：請只回覆「連線正常」，不要呼叫任何工具。"
PROMPT_2 = ("請呼叫 get_price_window 取得 2330 截至 2026-09-25T13:30:00+08:00 的 5 個交易日收盤價，"
            "然後用一句話說明工具回傳的資料是否標示為合成資料。")


def synthetic_price_window(args: dict) -> dict:
    return {
        "status": "ok",
        "tool": "get_price_window",
        "data": {
            "synthetic_fixture": True,
            "note": "合成測試資料，非真實股價",
            "ticker": args["ticker"],
            "basis": "raw_close",
            "closes": [{"session": i, "close": 100 + i} for i in range(1, 6)],
        },
    }


def main() -> None:
    baseline = json.loads((ROOT / "handoff" / "quota-baseline.json").read_text(encoding="utf-8"))
    quota = ProjectQuota.from_baseline(baseline)
    model_id = os.getenv("GEMINI_MODEL")
    if model_id != quota.model_id:
        sys.exit(f"GEMINI_MODEL={model_id} 與 quota-baseline.json 的 {quota.model_id} 不一致，停止。")

    db = ROOT / "tmp" / "live_check.sqlite3"
    store = JobStore(db)
    req = validate_job_request({
        "ticker": "2330", "mode": "single", "cutoff_at": "2026-09-25T13:30:00+08:00",
        "source_snapshot_id": "synthetic-live-check", "idempotency_key": f"live-check-{os.getpid()}",
    })
    job, _ = store.create_job(req, model_id)
    claimed = store.claim_next("live-check")
    if not claimed or claimed[0]["job_id"] != job["job_id"]:
        sys.exit("有其他 job 正在執行或排隊，停止。")
    _, token = claimed

    # Hard cap for this check: 3 sends total, retries included.
    gate = BudgetGate(store=store, job=store.get_job(job["job_id"]), quota=quota,
                      limits=BudgetLimits(max_calls=3, max_retries=0),
                      persist=lambda ch: store.update_job(job["job_id"], "live-check", token, ch))
    adapter = GeminiAdapter(make_client(), model_id, gate, prompt_version="live-check-v1")
    register_tool("get_price_window", synthetic_price_window)

    print(f"model={model_id} job={job['job_id']}")
    resp = adapter.send("reviewer", [types.Content(role="user", parts=[types.Part.from_text(text=PROMPT_1)])], SYSTEM)
    print("send 1 text:", resp.text)

    try:
        out = adapter.run_tool_roundtrip("researcher", PROMPT_2, SYSTEM)
        print("send 2-3 text:", out["text"])
        if len(out["contents"]) > 1:
            sig = any(getattr(p, "thought_signature", None) for p in out["contents"][1].parts)
            print("thought_signature echoed back:", sig)
        else:
            print("model did not call the tool")
    except BudgetExceeded as exc:
        print("stopped by 3-send cap:", exc)

    for u in store.list_usage(job["job_id"]):
        print(json.dumps({k: u[k] for k in ("usage_id", "role", "model_id", "prompt_version", "reserved_tokens",
                                             "total_tokens", "outcome")}, ensure_ascii=False))
    for e in store.list_events(job["job_id"]):
        if e["event_type"] in ("model_call", "model_error", "tool_call"):
            print(e["event_seq"], e["event_type"], json.dumps(e["detail"], ensure_ascii=False))
    est = estimate_tokens(SYSTEM + PROMPT_1)
    print(f"estimate check (send 1 input only): estimated≥{est} tokens before JSON wrapping")
    final = store.update_job(job["job_id"], "live-check", token,
                             {"status": "succeeded", "stage": "finished", "stop_reason": "live_check_done"})
    print("calls_used:", final["calls_used"], "tokens_observed:", final["tokens_observed"])


if __name__ == "__main__":
    main()
