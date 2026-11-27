"""決策 49、50：把最後沒有成功的 run 分類，並逐份比對停止原因與執行紀錄是否一致。

分類規則見 evaluation/d-drafts/insufficient-categories-v1.md（v1 定稿）。只讀程式紀錄，不讀草稿、主張或覆核的文字：
- 執行紀錄每一列：狀態、停止代碼、預算計數（發送、工具、token、補查輪次、主動時間）。
- 資料庫 job_events：事件種類，以及 detail 裡 KEEP 列出的代碼欄位（工具狀態、結束原因、錯誤代碼、草稿狀態與
  主張數、覆核決定、critical 指到的 claim_id、stop_facts 的停止代碼）。decision_summary、facts、reason、problems、
  errors 這些文字欄位不取出、不輸出。
- 資料庫 model_usage：每次發送的角色與結果代碼。
- 裁決後的標註（--claims、--refusals）與案例的 allow_insufficient：只在補細分時用。

    .venv/bin/python scripts/classify_runs.py --dev       # 開發集（Agent v2）紀錄試跑，印在終端
    .venv/bin/python scripts/classify_runs.py --formal    # 正式實驗；公開對照表（export_for_scoring.py --reveal）前拒絕執行
    .venv/bin/python scripts/classify_runs.py --formal --claims 主張標註.csv --refusals 拒答.csv   # 裁決後補細分

--claims：每條主張一列，欄位 answer_id、claim_id、kind（fact／inference／unknown）、label（supported／unsupported／unknown）。
--refusals：每份答卷一列，欄位 answer_id、explained_gap（是／否）。answer_id 是盲評答卷的編號，由 key.json 對回 run。
正式實驗的輸出：evaluation/formal/classification-v2.csv（每個計畫 run 一列）、classification-v2.md（各模式各類的數量）。
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import formal_reruns as frr  # noqa: E402
import formal_runs as fr  # noqa: E402
from agents.budget import BudgetLimits  # noqa: E402

LIMITS = BudgetLimits()
INITIAL = {"single": 8, "dual": 4, "workflow": 1}  # 初次研究可用的發送次數（agents/research_graph.py make_research_handler）
MODES = ("single", "dual", "workflow")
SCORING = ROOT / "evaluation" / "formal" / "scoring-v2"
OUT_CSV = ROOT / "evaluation" / "formal" / "classification-v2.csv"
OUT_MD = ROOT / "evaluation" / "formal" / "classification-v2.md"
DEV_TRACES = "agent/calib-v2-*.json"
DEV_DBS = ("tmp/calib_v2.sqlite3", "tmp/calib_v2_task.sqlite3")
DEV_CASES = ROOT / "evaluation" / "dev-cases.json"

# 只取這些代碼欄位；其他欄位（含所有文字）不取出
KEEP = {"model_call": ("call_number", "finish_reason", "function_calls"),
        "model_error": ("call_number", "code"),
        "tool_call": ("status",),
        "draft": ("status", "claims"),
        "review": ("round", "model_decision", "rules_decision", "final_decision", "critical"),
        "rules_check": ("rules_decision", "critical"),
        "stop_facts": ("stop_reason",)}

FAIL_STATUSES = {"failed", "runner_error", "timed_out", "cancelled"}
BUDGET_STOPS = {"call_limit", "token_limit", "input_too_large", "reserved_for_review"}
REVIEW_STOPS = {"review_insufficient", "unresolved_critical", "supplement_limit"}
SUCCESS_STOPS = {"review_pass": "dual", "draft_without_review": "single", "workflow_draft_without_review": "workflow"}
FINISH_STOPS = {"researcher_insufficient", "review_insufficient", "unresolved_critical", "no_draft_on_final_turn",
                "no_review_on_final_turn", "workflow_invalid_draft"}  # 由 finish() 結束，會留下 stop_facts
RAISED_STOPS = {"call_limit", "token_limit", "input_too_large", "reserved_for_review", "supplement_limit",
                "tool_limit", "duplicate_tool_call"}  # 預算檢查直接中止，不經 finish()
DUAL_ONLY = {"review_pass", "review_insufficient", "unresolved_critical", "supplement_limit", "no_review_on_final_turn"}

# 拆解表的列（類別、細分），照分類規則第二節的順序
TABLE_ROWS = [("未執行", ""), ("執行失敗", "供應商錯誤"), ("執行失敗", "其他"),
              ("格式失敗", "截斷"), ("格式失敗", "格式不符"), ("格式失敗", "沒交"),
              ("預算用盡", ""),
              ("覆核擋下", "無法判斷（沒有事實主張）"), ("覆核擋下", "可能誤擋"), ("覆核擋下", "擋得對"),
              ("覆核擋下", "無法判斷（指到別條）"), ("覆核擋下", "待裁決標註"),
              ("Researcher 判定不足", "工具失敗後停止"), ("Researcher 判定不足", "合理拒答"),
              ("Researcher 判定不足", "沒說明缺口"), ("Researcher 判定不足", "該答未答"),
              ("Researcher 判定不足", "待裁決標註"), ("規則沒涵蓋", "")]


@dataclass
class Event:
    role: str | None
    type: str
    tool: str | None
    d: dict = field(default_factory=dict)


@dataclass
class Run:
    run_id: str
    case_id: str
    mode: str
    status: str | None
    stop_reason: str | None
    budget: dict
    events: list[Event]
    sends: list[tuple[str, str]]  # (role, outcome)，依發送順序
    attempts: int = 1


def stop_code(stop: str | None) -> str:
    """worker_error 後面接的是例外訊息，只留代碼。"""
    return "worker_error" if (stop or "").startswith("worker_error") else (stop or "")


def read_job(con: sqlite3.Connection, job_id: str) -> tuple[list[Event], list[tuple[str, str]]]:
    events = []
    for role, etype, tool, detail in con.execute(
            "select role, event_type, tool_name, detail from job_events where job_id=? order by event_seq", (job_id,)):
        keep = KEEP.get(etype, ())
        try:
            raw = json.loads(detail) if keep and detail else {}
        except json.JSONDecodeError:
            raw = {}
        events.append(Event(role, etype, tool, {k: raw[k] for k in keep if k in raw}))
    sends = [(r, o) for r, o in con.execute(
        "select role, outcome from model_usage where job_id=? order by usage_id", (job_id,))]
    return events, sends


# -- 分類（決策 49） -------------------------------------------------------------
def last_call(run: Run, role: str) -> tuple[Event | None, list[Event]]:
    """這個角色最後一次模型發送，以及之後同一角色的事件。"""
    for i in range(len(run.events) - 1, -1, -1):
        e = run.events[i]
        if e.type == "model_call" and e.role == role:
            return e, [x for x in run.events[i + 1:] if x.role == role]
    return None, []


def role_tail(run: Run, role: str) -> list[Event]:
    """這個角色最後一次模型發送，加上之後同一角色的事件。"""
    call, after = last_call(run, role)
    return ([call] if call else []) + after


def truncated(call: Event | None) -> bool:
    return call is not None and "MAX_TOKENS" in str(call.d.get("finish_reason") or "")


def format_failure(run: Run) -> str | None:
    stop = stop_code(run.stop_reason)
    if stop in ("no_draft_on_final_turn", "no_review_on_final_turn"):
        return "沒交"
    for role, invalid in (("researcher", "draft_invalid"), ("reviewer", "review_invalid")):
        call, after = last_call(run, role)
        if call is not None and any(e.type == invalid for e in after):  # 最後一次輸出沒過格式檢查，之後也沒有重送成功
            return "截斷" if truncated(call) else "格式不符"
    if stop == "workflow_invalid_draft":
        return "截斷" if truncated(last_call(run, "researcher")[0]) else "格式不符"
    if stop == "researcher_insufficient" and truncated(last_call(run, "researcher")[0]):
        return "截斷"  # handoff/v12-freeze.md 已知限制第 3 點：截斷可能被記成 researcher_insufficient，以結束原因為準
    return None


def tool_failed(run: Run) -> bool:
    return any(e.type == "tool_call" and e.role == "researcher" and e.d.get("status") == "tool_error" for e in run.events)


def classify(run: Run | None) -> tuple[str, str]:
    """(類別, 細分)。成功的 run 不分類；需要裁決標註的細分先留空，由 refine() 補。"""
    if run is None:
        return "未執行", ""
    if run.status == "succeeded":
        return "成功", ""
    if frr.provider_error(run.sends[-1][1] if run.sends else None):
        return "執行失敗", "供應商錯誤"  # 決策 47：不論停止代碼
    if run.status in FAIL_STATUSES:
        return "執行失敗", "其他"
    fmt = format_failure(run)
    if fmt:
        return "格式失敗", fmt
    stop = stop_code(run.stop_reason)
    if stop in BUDGET_STOPS:
        return "預算用盡", stop
    if stop in REVIEW_STOPS:
        return "覆核擋下", ""
    if stop == "researcher_insufficient":
        return "Researcher 判定不足", "工具失敗後停止" if tool_failed(run) else ""
    return "規則沒涵蓋", stop


def last_critical(run: Run) -> list[str]:
    reviews = [e for e in run.events if e.type == "review"]
    return list(reviews[-1].d.get("critical") or []) if reviews else []


def refine(category: str, sub: str, run: Run | None, claims: list[dict] | None, gap: bool | None,
           allow: bool | None) -> tuple[str, str]:
    """用裁決後的標註補細分。回傳 (細分, 備註)。"""
    if category == "覆核擋下":
        if claims is None:
            return "待裁決標註", ""
        facts = [c for c in claims if c["kind"] == "fact"]
        if not facts:
            return "無法判斷（沒有事實主張）", ""
        if all(c["label"] == "supported" for c in facts):
            return "可能誤擋", ""
        bad = {c["claim_id"] for c in claims if c["label"] in ("unsupported", "unknown")}
        if bad & set(last_critical(run)):
            return "擋得對", ""
        return "無法判斷（指到別條）", "" if bad else "草稿沒有被標為 unsupported／unknown 的主張，請檢查標註"
    if category == "Researcher 判定不足" and sub != "工具失敗後停止":
        if allow is None:
            return "待裁決標註", "沒有案例的 allow_insufficient"
        if not allow:
            return "該答未答", ""
        if gap is None:
            return "待裁決標註", ""
        return ("合理拒答" if gap else "沒說明缺口"), ""
    return sub, ""


# -- 停止原因比對（決策 50） ------------------------------------------------------
def expected_status(stop: str) -> str | None:
    if stop in SUCCESS_STOPS:
        return "succeeded"
    if stop in FINISH_STOPS | RAISED_STOPS:
        return "insufficient_evidence"
    return {"active_time": "timed_out", "worker_error": "failed", "cancel_requested": "cancelled"}.get(stop)


def check_stop(run: Run) -> tuple[str, list[str]]:
    """('一致'|'不一致'|'無法核對', 說明)。只用代碼與計數，不用任何文字。"""
    stop = stop_code(run.stop_reason)
    want = expected_status(stop)
    if want is None:
        return "無法核對", [f"沒有比對規則的停止代碼 {stop or '（空）'}"]
    bad: list[str] = []
    unclear: list[str] = []
    reviews = [e for e in run.events if e.type == "review"]
    drafts = [i for i, e in enumerate(run.events) if e.type == "draft"]
    facts = [e for e in run.events if e.type == "stop_facts"]
    last_review = reviews[-1].d if reviews else {}
    last_draft = run.events[drafts[-1]].d if drafts else {}
    b = run.budget or {}
    n_sends = len(run.sends)
    r_sends = sum(1 for role, _ in run.sends if role == "researcher")

    if run.status != want:
        bad.append(f"狀態 {run.status} 應為 {want}")
    if (stop in SUCCESS_STOPS and run.mode != SUCCESS_STOPS[stop]) or (stop in DUAL_ONLY and run.mode != "dual") \
            or (stop == "workflow_invalid_draft" and run.mode != "workflow") \
            or (stop == "reserved_for_review" and run.mode == "single"):
        bad.append(f"{stop} 不會出現在 {run.mode} 模式")
    if b.get("calls_used") is not None and b["calls_used"] != n_sends:
        bad.append(f"發送計數 {b['calls_used']} 與發送紀錄 {n_sends} 筆不符")
    if stop in FINISH_STOPS:
        if not facts:
            bad.append("沒有 stop_facts 事件")
        elif facts[-1].d.get("stop_reason") != stop:
            bad.append("stop_facts 記的停止代碼不同")
    elif facts and stop in RAISED_STOPS | {"active_time"}:
        bad.append("預算中止卻有 stop_facts 事件")

    if stop == "review_pass":
        if last_review.get("final_decision") != "pass":
            bad.append("最後一輪覆核不是 pass")
        if last_draft.get("status") == "insufficient":
            bad.append("最後草稿是 insufficient")
    elif stop == "review_insufficient" and last_review.get("final_decision") != "insufficient":
        bad.append("最後一輪覆核不是 insufficient")
    elif stop == "unresolved_critical":
        if last_review.get("final_decision") != "revise":
            bad.append("最後一輪覆核不是 revise")
        used = b.get("calls_used", n_sends) or 0
        if (b.get("supplement_rounds") or 0) < LIMITS.max_supplement_rounds and LIMITS.max_calls - used >= 2:
            bad.append("補查輪次與發送次數都還有剩")
    elif stop == "supplement_limit" and (b.get("supplement_rounds") or 0) < LIMITS.max_supplement_rounds:
        bad.append("補查輪次沒有用完")
    elif stop in ("draft_without_review", "workflow_draft_without_review"):
        if reviews:
            bad.append("有覆核紀錄")
        if last_draft.get("status") in (None, "insufficient"):
            bad.append("最後沒有可交出的草稿")
        if stop == "workflow_draft_without_review" and r_sends != 1:
            bad.append(f"固定流程的撰稿發送是 {r_sends} 次，不是 1 次")
    elif stop == "workflow_invalid_draft" and not any(e.type == "draft_invalid" for e in run.events):
        bad.append("沒有草稿格式檢查失敗的紀錄")
    elif stop == "researcher_insufficient":
        if last_draft.get("status") != "insufficient":
            bad.append("最後草稿不是 insufficient")
        elif any(e.type == "review" for e in run.events[drafts[-1] + 1:]):
            bad.append("insufficient 草稿之後還有模型覆核")
    elif stop in ("no_draft_on_final_turn", "no_review_on_final_turn"):
        role = "researcher" if stop == "no_draft_on_final_turn" else "reviewer"
        if not any(e.type == "tools_refused" for e in role_tail(run, role)):
            bad.append("最後一回沒有「要求工具被拒」的紀錄")
    elif stop == "call_limit" and n_sends < LIMITS.max_calls:
        bad.append(f"發送只有 {n_sends} 次，未達 {LIMITS.max_calls} 次")
    elif stop == "reserved_for_review":
        if r_sends < INITIAL.get(run.mode, LIMITS.initial_research_calls):
            bad.append(f"Researcher 只發送 {r_sends} 次，還沒用完初次研究的次數")
        if reviews:
            bad.append("已經進入覆核")
    elif stop == "token_limit" and (b.get("tokens_observed") or 0) <= \
            LIMITS.job_token_budget - LIMITS.max_input_tokens - LIMITS.max_output_tokens:
        bad.append("已用 token 離上限還很遠")
    elif stop == "input_too_large":
        unclear.append("輸入估計值沒有記在執行紀錄，無法核對")
    elif stop == "active_time" and (b.get("active_seconds") or 0) < LIMITS.max_active_seconds:
        bad.append(f"主動時間未達 {LIMITS.max_active_seconds:.0f} 秒")
    elif stop == "worker_error":
        last = run.sends[-1][1] if run.sends else None
        if frr.provider_error(last):
            code = int(last[len("error_"):])
            if not any(e.type == "model_error" and e.d.get("code") == code for e in run.events):
                bad.append("最後一次發送是供應商錯誤，卻沒有對應的錯誤事件")
        else:
            unclear.append("不是供應商錯誤的程式錯誤，紀錄裡沒有可比對的事件")
    elif stop == "tool_limit" and (b.get("tool_calls_used") or 0) < LIMITS.max_tool_calls:
        bad.append("工具呼叫未達上限")
    if bad:
        return "不一致", bad
    if unclear:
        return "無法核對", unclear
    return "一致", []



# -- 資料來源 --------------------------------------------------------------------
def dev_runs() -> list[Run]:
    """開發集 Agent v2 的 live 紀錄（不是保留集）。"""
    cons = [sqlite3.connect(f"file:{ROOT / p}?mode=ro", uri=True) for p in DEV_DBS if (ROOT / p).exists()]
    out = []
    for f in sorted(ROOT.glob(DEV_TRACES)):
        for c in json.loads(f.read_text(encoding="utf-8"))["cases"]:
            lives = c.get("live_by_mode") or ({"dual": c["live"]} if c.get("live") else {})
            for mode, live in lives.items():
                job = (live or {}).get("job_id")
                con = next((x for x in cons if job and x.execute(
                    "select 1 from job_events where job_id=? limit 1", (job,)).fetchone()), None)
                if con is None:
                    continue
                events, sends = read_job(con, job)
                out.append(Run(f"{f.stem}:{c['case_id']}:{mode}", c["case_id"], mode, live.get("status"),
                               live.get("stop_reason"), live.get("budget") or {}, events, sends))
    return out


def formal_runs(con: sqlite3.Connection) -> list[tuple[dict, Run | None, list[dict]]]:
    """每個計畫 run：(計畫列, 分析用的最新一次, 所有嘗試)。"""
    plan = json.loads(fr.PLAN.read_text(encoding="utf-8"))
    done = fr.done_runs()
    out = []
    for p in plan["runs"]:
        rows = frr.attempts(done, p["run_id"])
        run = None
        if rows:
            row = rows[-1]
            events, sends = read_job(con, row["job_id"]) if row.get("job_id") else ([], [])
            run = Run(p["run_id"], p["case_id"], p["mode"], row.get("status"), row.get("stop_reason"),
                      row.get("budget") or {}, events, sends, attempts=len(rows))
        out.append((p, run, rows))
    return out


def paused(con: sqlite3.Connection, p: dict) -> bool:
    """沒有紀錄的 run 是不是已開始、停在配額暫停（只讀 research_jobs 的鍵與狀態欄）。"""
    key = f"{p['case_id']}-{fr.EXPERIMENT}" if p["mode"] == "dual" else f"{p['case_id']}-{p['mode']}-{fr.EXPERIMENT}"
    try:
        row = con.execute("select status from research_jobs where idempotency_key=?", (key,)).fetchone()
    except sqlite3.OperationalError:
        return False
    return bool(row and row[0] == "paused_quota")


def yes(value: str | None) -> bool | None:
    v = (value or "").strip().lower()
    return True if v in ("是", "yes", "y", "true", "1") else False if v in ("否", "no", "n", "false", "0") else None


def load_labels(claims_csv: Path | None, refusals_csv: Path | None, key_map: dict[str, str]):
    """裁決後的標註，依 key.json 由 answer_id 對回計畫 run。沒有列在主張標註裡的答卷，視為沒有主張。"""
    claims: dict[str, list[dict]] = {}
    gaps: dict[str, bool | None] = {}

    def run_of(answer_id: str) -> str:
        if answer_id.strip() not in key_map:
            sys.exit(f"{answer_id} 不在對照表 key.json 裡，停止")
        return key_map[answer_id.strip()]

    if claims_csv:
        with claims_csv.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                run_id = run_of(r["answer_id"])
                claims.setdefault(run_id, []).append({"claim_id": r["claim_id"].strip(), "kind": r["kind"].strip(),
                                                      "label": r["label"].strip()})
    if refusals_csv:
        with refusals_csv.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                gaps[run_of(r["answer_id"])] = yes(r.get("explained_gap"))
    return claims, gaps


def key_map() -> dict[str, str]:
    key = json.loads((SCORING / "key.json").read_text(encoding="utf-8"))
    return {k["answer_id"]: k.get("rerun_of") or k["run_id"] for k in key["key"]}


def allow_flags(path: Path) -> dict[str, bool]:
    """案例的 allow_insufficient（只取這個欄位）。"""
    cases = json.loads(path.read_text(encoding="utf-8"))
    cases = cases["cases"] if isinstance(cases, dict) else cases
    return {c["case_id"]: bool(c.get("allow_insufficient")) for c in cases}


# -- 輸出 ------------------------------------------------------------------------
def tally(rows: list[dict]) -> dict[tuple[str, str], Counter]:
    t: dict[tuple[str, str], Counter] = {}
    for r in rows:
        key = (r["category"], r["subcategory"] if r["category"] not in ("未執行", "預算用盡", "規則沒涵蓋") else "")
        t.setdefault(key, Counter())[r["mode"]] += 1
    return t


def render_md(rows: list[dict], reruns: list[dict], labelled: bool) -> str:
    n = Counter(r["mode"] for r in rows)
    t = tally(rows)
    head = "| 類別 | 細分 | " + " | ".join(MODES) + " |"
    out = ["# 正式實驗 formal-v2：沒有成功的 run 的分類與停止原因比對", "",
           f"- 產生時間：{datetime.now(timezone.utc).isoformat(timespec='seconds')}；規則：決策 49（分類）、50（停止原因比對）；"
           "每個 run 用最新一次（決策 47、48）。",
           "- 細分" + ("已用裁決後的標註。" if labelled else "中需要裁決標註的部分還沒補（標「待裁決標註」）。"),
           "- 數量寫成分數，分母是該模式的計畫 run 數。", "", "## 一、各模式各類的數量", "", head,
           "|" + "---|" * (2 + len(MODES)),
           f"| 成功（不分類） |  | " + " | ".join(f"{t.get(('成功', ''), Counter())[m]}／{n[m]}" for m in MODES) + " |"]
    for cat, sub in TABLE_ROWS:
        c = t.get((cat, sub), Counter())
        if cat in ("覆核擋下", "Researcher 判定不足") and sub == "待裁決標註" and not sum(c.values()):
            continue
        out.append(f"| {cat} | {sub} | " + " | ".join(f"{c[m]}／{n[m]}" for m in MODES) + " |")
    budget = Counter(r["subcategory"] for r in rows if r["category"] == "預算用盡")
    if budget:
        out += ["", "預算用盡的停止代碼：" + "、".join(f"{k} {v}" for k, v in sorted(budget.items()))]
    out += ["", "## 二、重跑（決策 47、48）", "",
            f"- 重跑的 run：{len(reruns)} 個；重跑總次數：{sum(r['reruns'] for r in reruns)} 次。原紀錄與中間的重跑不分類。", ""]
    if reruns:
        out += ["| run | 模式 | 原紀錄的狀態與停止代碼 | 重跑次數 | 最新一次 |", "|---|---|---|---|---|"]
        out += [f"| {r['run_id']} | {r['mode']} | {r['original']} | {r['reruns']} | {r['latest']} |" for r in reruns]
    checks = Counter((r["mode"], r["stop_check"]) for r in rows if r["stop_check"])
    out += ["", "## 三、停止原因與執行紀錄是否一致（決策 50，B、D 抽查）", "",
            "| 結果 | " + " | ".join(MODES) + " |", "|" + "---|" * (1 + len(MODES))]
    for res in ("一致", "不一致", "無法核對"):
        out.append(f"| {res} | " + " | ".join(f"{checks[(m, res)]}／{n[m]}" for m in MODES) + " |")
    odd = [r for r in rows if r["stop_check"] in ("不一致", "無法核對")]
    if odd:
        out += ["", "| run | 模式 | 停止代碼 | 結果 | 說明 |", "|---|---|---|---|---|"]
        out += [f"| {r['run_id']} | {r['mode']} | {r['stop_code']} | {r['stop_check']} | {r['stop_check_detail']} |"
                for r in odd]
    return "\n".join(out) + "\n"


FIELDS = ["run_id", "case_id", "mode", "attempts", "status", "stop_code", "category", "subcategory", "note",
          "stop_check", "stop_check_detail"]


def row_for(p: dict, run: Run | None, claims, gaps, allow, con) -> dict:
    cat, sub = classify(run)
    note = ""
    if run is None and con is not None and paused(con, p):
        note = "已開始、暫停"
    if cat in ("覆核擋下", "Researcher 判定不足"):
        sub, note = refine(cat, sub, run, claims.get(p["run_id"], []) if claims is not None else None,
                           gaps.get(p["run_id"]) if gaps is not None else None,
                           allow.get(p["case_id"]) if allow is not None else None)
    check, detail = check_stop(run) if run else ("", [])
    return {"run_id": p["run_id"], "case_id": p["case_id"], "mode": p["mode"], "attempts": run.attempts if run else 0,
            "status": run.status if run else "", "stop_code": stop_code(run.stop_reason) if run else "",
            "category": cat, "subcategory": sub, "note": note, "stop_check": check,
            "stop_check_detail": "；".join(detail)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dev", action="store_true", help="用開發集（Agent v2）紀錄試跑")
    g.add_argument("--formal", action="store_true", help="正式實驗（公開對照表之後）")
    ap.add_argument("--claims", type=Path, help="裁決後的主張標註 CSV（answer_id, claim_id, kind, label）")
    ap.add_argument("--refusals", type=Path, help="裁決後的拒答欄位 CSV（answer_id, explained_gap）")
    args = ap.parse_args(argv)

    if args.dev:
        runs = dev_runs()
        allow = allow_flags(DEV_CASES)
        rows = [row_for({"run_id": r.run_id, "case_id": r.case_id, "mode": r.mode}, r, None, None, allow, None)
                for r in runs]
        cat = Counter((r["mode"], r["category"], r["subcategory"]) for r in rows)
        print(f"開發集（Agent v2）{len(rows)} 個 run：" + "、".join(f"{m} {sum(1 for r in rows if r['mode'] == m)}" for m in MODES))
        for (m, c, s), k in sorted(cat.items()):
            print(f"  {m}\t{c}\t{s or '—'}\t{k}")
        chk = Counter(r["stop_check"] for r in rows)
        print("停止原因比對：" + "、".join(f"{k} {v}" for k, v in chk.items()))
        for r in rows:
            if r["stop_check"] != "一致" or r["category"] == "規則沒涵蓋":
                print(f"  {r['run_id']}\t{r['stop_code']}\t{r['stop_check']}\t{r['stop_check_detail']}")
        return 0

    if not (SCORING / "key.json").exists():
        sys.exit("公開對照表（export_for_scoring.py --reveal）之前不能跑正式實驗：各 run 的類別會透露模式（決策 49、50）")
    if not fr.DB.exists():
        sys.exit(f"找不到 {fr.DB}")
    con = sqlite3.connect(f"file:{fr.DB}?mode=ro", uri=True)
    labelled = bool(args.claims or args.refusals)
    claims = gaps = allow = None
    if labelled:
        km = key_map()
        claims, gaps = load_labels(args.claims, args.refusals, km)
        claims = claims if args.claims else None
        gaps = gaps if args.refusals else None
        allow = allow_flags(fr.SEALED)
    rows, reruns = [], []
    for p, run, attempts in formal_runs(con):
        rows.append(row_for(p, run, claims, gaps, allow, con))
        if len(attempts) > 1:
            first, last = attempts[0], attempts[-1]
            reruns.append({"run_id": p["run_id"], "mode": p["mode"], "reruns": len(attempts) - 1,
                           "original": f"{first.get('status')} {stop_code(first.get('stop_reason'))}",
                           "latest": f"{last.get('status')} {stop_code(last.get('stop_reason'))}"})
    con.close()
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    OUT_MD.write_text(render_md(rows, reruns, labelled), encoding="utf-8")
    show = lambda path: path.relative_to(ROOT) if path.is_relative_to(ROOT) else path  # noqa: E731
    print(f"已寫入 {show(OUT_CSV)}（{len(rows)} 列）與 {show(OUT_MD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
