"""正式評估 formal-v2：因供應商錯誤沒跑完的 run，重跑到跑完為止（決策 47、48，組長 2026-11-21、11-22）。

    .venv/bin/python scripts/formal_reruns.py --list                                   # 列出待重跑的 run（只看發送結果代碼）
    .venv/bin/python scripts/formal_reruns.py --live --max-runs 3 --j-exception 50      # 60 個計畫 run 都有紀錄後才可執行

規則（handoff/decisions-2026-10.md 第 47、48 節）
- 對象：計畫中的 run，最新一次嘗試（原 run 或最近一次重跑）沒有成功，而且最後一次模型發送的結果是供應商錯誤
  （5xx；408 是逾時與連線錯誤）。只讀 job 資料庫 model_usage 表的 outcome 欄位，不讀草稿、主張、覆核內容。
- 重跑到跑完為止（決策 48）：每次重跑開一個新的 job，run_id 依序加 -r1、-r2…；某一次因為供應商以外的原因結束
  （成功、證據不足、其他失敗都算）就不再重跑。
- 中途遇到錯誤、重試成功並跑完的 run 不重跑（手冊：每 job 8 次發送含重試）。
- 原紀錄與每一次重跑都保留在 evaluation/formal/runs-v2.jsonl，不刪不改；分析與盲評用最新一次。
- 不改被鎖定的程式：沿用 formal_runs 的案例讀取、嚴格核對與紀錄格式，以及 dev_traces.run（同一條 job 路徑）。
  job 標籤用 formal-v2-rN，只是為了建立新的 job（idempotency key 不同）；送給 Agent 的內容與正式 run 相同。
- J：重跑日可用 --j-exception 放寬當天的 job 數（組長決定，最多 floor(0.8 × RPD ÷ 8)）；每日 80% RPD 的發送上限照常由
  budget gate 檢查。配額用完時不寫紀錄，下一個配額日續跑同一個 job。每個 job 之間等 60 秒。
- 終端只印 run_id、狀態與停止代碼，不印任何內容。
"""

from __future__ import annotations

import argparse
import json
import math
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
from agents.budget import HEADROOM, QUOTA_DAY_TZ, ProjectQuota  # noqa: E402

RULE = "decisions 47-48"


def provider_error(outcome: str | None) -> bool:
    """error_5xx, or error_408 (agents/provider.py records timeouts and transport errors as 408)."""
    if not outcome or not outcome.startswith("error_"):
        return False
    code = outcome[len("error_"):]
    return code.isdigit() and (int(code) >= 500 or int(code) == 408)


def send_outcomes(con: sqlite3.Connection, job_id: str) -> list[str]:
    return [o for (o,) in con.execute("select outcome from model_usage where job_id = ? order by usage_id", (job_id,))]


def attempts(done: dict[str, dict], run_id: str) -> list[dict]:
    """The planned run's original row, then its reruns -r1, -r2, … in order."""
    out = [done[run_id]] if run_id in done else []
    n = 1
    while f"{run_id}-r{n}" in done:
        out.append(done[f"{run_id}-r{n}"])
        n += 1
    return out


def analysis_row(done: dict[str, dict], run_id: str) -> dict | None:
    """The row the analysis and the blind export use: the latest attempt (decisions 47-48)."""
    rows = attempts(done, run_id)
    return rows[-1] if rows else None


def eligible(plan: dict, done: dict[str, dict], con: sqlite3.Connection) -> list[tuple[dict, dict, str, int]]:
    """Planned runs whose latest attempt ended on a provider error: (plan run, latest row, last outcome, next attempt no.)."""
    if not con.execute("select 1 from sqlite_master where type = 'table' and name = 'model_usage'").fetchone():
        return []
    out = []
    for p in plan["runs"]:
        rows = attempts(done, p["run_id"])
        if not rows:
            continue
        latest = rows[-1]
        if latest.get("status") == "succeeded" or not latest.get("job_id"):
            continue
        outcomes = send_outcomes(con, latest["job_id"])
        if outcomes and provider_error(outcomes[-1]):
            out.append((p, latest, outcomes[-1], len(rows)))
    return out


def rerun_row(p: dict, replaced: dict, last_outcome: str, n: int, result: dict, model_id: str, commit: str,
              started: str) -> dict:
    row = fr.row_for({**p, "run_id": f"{p['run_id']}-r{n}"}, result, model_id, commit, started)
    row.update({"rerun_of": p["run_id"], "attempt": n, "replaces_job_id": replaced.get("job_id"),
                "rerun_reason": f"provider_error:{last_outcome}", "job_tag": f"{fr.EXPERIMENT}-r{n}", "rule": RULE})
    return row


def max_j_exception(quota: ProjectQuota) -> int:
    """Jobs per day the 80 % RPD cap allows at 8 sends per job (the handbook J formula without its cap of 6)."""
    return math.floor(max(0, math.floor(HEADROOM * (quota.rpd or 0)) - quota.other_daily_reserved) / 8)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-runs", type=int, default=3)
    ap.add_argument("--j-exception", type=int, help="rerun day only: jobs allowed today (lead decision 48)")
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
        print(f"{plan['experiment']}：計畫 run 未執行 {len(missing)} 個；已重跑 {len(reruns)} 次；待重跑 {len(todo)} 個")
        for p, row, last, n in todo:
            print("待重跑", p["run_id"], f"第 {n} 次", row.get("status"), last)
        for r in reruns:
            print("已重跑", r["run_id"], r.get("status"), r.get("stop_reason") or "")
        return 0

    if missing:
        print(f"還有 {len(missing)} 個計畫 run 未執行；重跑排在 60 個都跑完之後（決策 47）")
        return 1
    if not todo:
        print("沒有需要重跑的 run")
        return 0
    baseline = json.loads((ROOT / "handoff" / "quota-baseline.json").read_text(encoding="utf-8"))
    quota = ProjectQuota.from_baseline(baseline)
    if args.j_exception is not None:
        cap = max_j_exception(quota)
        if not 1 <= args.j_exception <= cap:
            sys.exit(f"--j-exception 必須介於 1 和 {cap}（80% RPD ÷ 每 job 8 次）之間，停止")
    if not fr.lock_ok():
        return 1
    from dev_traces import run  # same job path as the formal runs
    from agents.provider import make_client
    from agents.store import JobStore
    model_id = os.getenv("GEMINI_MODEL")
    if model_id != quota.model_id:
        sys.exit(f"GEMINI_MODEL={model_id} 與 quota-baseline.json 的 {quota.model_id} 不一致，停止")
    if args.j_exception is not None:  # one quota day only, like dev_traces --j-exception (decision 48)
        quota.j_exception = args.j_exception
        quota.j_exception_day = datetime.now(QUOTA_DAY_TZ).date().isoformat()
    cases = fr.load_holdout()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    store, client = JobStore(fr.DB), make_client()
    for i, (p, latest, last, n) in enumerate(todo[: args.max_runs]):
        if i:
            time.sleep(60)  # one minute between jobs: stay under 80 % of RPM, and do not hammer a busy server
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            result = run(store, cases[p["case_id"]], client, model_id, quota, f"{fr.EXPERIMENT}-r{n}", p["mode"])
        except Exception as exc:  # recorded, never retried silently
            result = {"status": "runner_error", "stop_reason": type(exc).__name__}
        if result.get("status") == "paused_quota":  # no row: the same job resumes next quota day
            print(f"{p['run_id']}-r{n}", "paused_quota", result.get("stop_reason") or "", "→ 配額已用完，下一個配額日續跑")
            break
        row = rerun_row(p, latest, last, n, result, model_id, commit, started)
        with fr.RUNS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(row["run_id"], row["status"], row["stop_reason"] or "", flush=True)
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
