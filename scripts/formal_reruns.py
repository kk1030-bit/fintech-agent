"""正式評估 formal-v2：供應商錯誤的 run 重跑一次（決策 47，組長 2026-11-21）。

    .venv/bin/python scripts/formal_reruns.py --list                # 列出符合重跑規則的 run（只看發送結果代碼）
    .venv/bin/python scripts/formal_reruns.py --live [--max-runs 6]  # 60 個計畫 run 都有紀錄後才可執行（排在 11/26）

規則（handoff/decisions-2026-10.md 第 47 節）
- 對象：計畫中已記錄、沒有成功，而且最後一次模型發送的結果是供應商錯誤（5xx；408 是逾時與連線錯誤）的 run。
  只讀 job 資料庫 model_usage 表的 outcome 欄位，不讀草稿、主張、覆核內容。
- 中途遇到錯誤、重試成功並跑完的 run 不重跑（手冊：每 job 8 次發送含重試）。
- 每個 run 只重跑一次：重跑的 run_id 是原 run_id 加 -r1；已有 -r1 紀錄的不再跑；重跑又遇到供應商錯誤照實記錄。
- 原紀錄不動。重跑結果另寫一列到 evaluation/formal/runs-v2.jsonl，帶 rerun_of、rerun_reason。
- 不改被鎖定的程式：沿用 formal_runs 的案例讀取、嚴格核對與紀錄格式，以及 dev_traces.run（同一條 job 路徑）。
  job 標籤用 formal-v2-r1，只是為了建立新的 job（idempotency key 不同）；送給 Agent 的內容與正式 run 相同。
- 每個配額日仍受 J=6 限制（budget gate 檢查）；配額用完時不寫紀錄，下一個配額日續跑同一個 job。
- 終端只印 run_id、狀態與停止代碼，不印任何內容。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import formal_runs as fr  # noqa: E402  被鎖定的 runner：只匯入、不修改

RERUN_SUFFIX = "-r1"
RERUN_TAG = f"{fr.EXPERIMENT}-r1"


def provider_error(outcome: str | None) -> bool:
    """error_5xx, or error_408 (agents/provider.py records timeouts and transport errors as 408)."""
    if not outcome or not outcome.startswith("error_"):
        return False
    code = outcome[len("error_"):]
    return code.isdigit() and (int(code) >= 500 or int(code) == 408)


def send_outcomes(con: sqlite3.Connection, job_id: str) -> list[str]:
    return [o for (o,) in con.execute("select outcome from model_usage where job_id = ? order by usage_id", (job_id,))]


def eligible(plan: dict, done: dict[str, dict], con: sqlite3.Connection) -> list[tuple[dict, dict, str]]:
    """Planned runs that ended on a provider error and have no rerun yet: (plan run, original row, last outcome)."""
    if not con.execute("select 1 from sqlite_master where type = 'table' and name = 'model_usage'").fetchone():
        return []
    out = []
    for p in plan["runs"]:
        row = done.get(p["run_id"])
        if not row or not row.get("job_id") or row.get("status") == "succeeded" or done.get(p["run_id"] + RERUN_SUFFIX):
            continue
        outcomes = send_outcomes(con, row["job_id"])
        if outcomes and provider_error(outcomes[-1]):
            out.append((p, row, outcomes[-1]))
    return out


def analysis_row(done: dict[str, dict], run_id: str) -> dict | None:
    """The row the analysis and the blind export use: the rerun (-r1) when there is one (decision 47)."""
    return done.get(run_id + RERUN_SUFFIX) or done.get(run_id)


def rerun_row(p: dict, original: dict, last_outcome: str, result: dict, model_id: str, commit: str, started: str) -> dict:
    row = fr.row_for({**p, "run_id": p["run_id"] + RERUN_SUFFIX}, result, model_id, commit, started)
    row.update({"rerun_of": p["run_id"], "rerun_of_job_id": original.get("job_id"),
                "rerun_reason": f"provider_error:{last_outcome}", "job_tag": RERUN_TAG, "rule": "decision 47"})
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-runs", type=int, default=6)
    args = ap.parse_args(argv)

    plan = json.loads(fr.PLAN.read_text(encoding="utf-8"))
    done = fr.done_runs()
    if not Path(fr.DB).exists():
        print("沒有正式實驗資料庫，不需要重跑")
        return 0
    with closing(sqlite3.connect(f"file:{fr.DB}?mode=ro", uri=True)) as con:
        todo = eligible(plan, done, con)
    missing = [p["run_id"] for p in plan["runs"] if p["run_id"] not in done]
    reruns = [r for r in done.values() if r.get("rerun_of")]

    if not args.live:
        print(f"{plan['experiment']}：計畫 run 未執行 {len(missing)} 個；已重跑 {len(reruns)} 個；待重跑 {len(todo)} 個")
        for p, row, last in todo:
            print("待重跑", p["run_id"], row.get("status"), last)
        for r in reruns:
            print("已重跑", r["run_id"], r.get("status"), r.get("stop_reason") or "")
        return 0

    if missing:
        print(f"還有 {len(missing)} 個計畫 run 未執行；重跑排在 60 個都跑完之後（決策 47）")
        return 1
    if not todo:
        print("沒有需要重跑的 run")
        return 0
    if not fr.lock_ok():
        return 1
    from dev_traces import run  # same job path as the formal runs
    from agents.budget import ProjectQuota
    from agents.provider import make_client
    from agents.store import JobStore
    baseline = json.loads((ROOT / "handoff" / "quota-baseline.json").read_text(encoding="utf-8"))
    quota = ProjectQuota.from_baseline(baseline)
    model_id = os.getenv("GEMINI_MODEL")
    if model_id != quota.model_id:
        sys.exit(f"GEMINI_MODEL={model_id} 與 quota-baseline.json 的 {quota.model_id} 不一致，停止")
    cases = fr.load_holdout()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    store, client = JobStore(fr.DB), make_client()
    for i, (p, original, last) in enumerate(todo[: args.max_runs]):
        if i:
            time.sleep(60)  # stay under 80 % of RPM between jobs, as formal_runs does
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            result = run(store, cases[p["case_id"]], client, model_id, quota, RERUN_TAG, p["mode"])
        except Exception as exc:  # recorded, never retried silently
            result = {"status": "runner_error", "stop_reason": type(exc).__name__}
        if result.get("status") == "paused_quota":  # no row: the same job resumes next quota day
            print(p["run_id"] + RERUN_SUFFIX, "paused_quota", result.get("stop_reason") or "", "→ 下一個配額日續跑")
            break
        row = rerun_row(p, original, last, result, model_id, commit, started)
        with fr.RUNS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(row["run_id"], row["status"], row["stop_reason"] or "", flush=True)
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
