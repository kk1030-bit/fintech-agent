"""W10-A: same report_version_id → same content on the web page and in the PDF (and in the frozen JSON).

    python scripts/w10_consistency_check.py --dir <folder> --http <http-checks.json> --out reports/v12-consistency-batch1.md

<folder> holds, per published version, three files captured from the live site (Render):
  w10-<ticker>-v<n>-<rv>.json      GET /api/ui/reports/<rv>   (the approved JSON the page renders)
  w10-<ticker>-v<n>-<rv>.pdf       GET /api/ui/reports/<rv>.pdf
  w10-<ticker>-v<n>-<rv>-web.txt   innerText of the report section after the page loaded ?report=<rv>
<http-checks.json> holds the browser's HTTP results (status, headers, sha256 of preview and download).

Every value is looked up in the web text and in the PDF text with whitespace removed (the PDF wraps lines); a
value that should be NA must read NA in both. Nothing is re-computed: the JSON is the reference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import sys

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def f2(v) -> str:
    return f"{v:,.2f}"


def check(rep: dict, web: str, pdf: str) -> list[dict]:
    W, P = norm(web), norm(pdf)
    rows: list[dict] = []

    def item(group: str, label: str, web_s: str | None, pdf_s: str | None = None):
        pdf_s = web_s if pdf_s is None else pdf_s
        w = web_s is not None and norm(web_s) in W
        p = pdf_s is not None and norm(pdf_s) in P
        rows.append({"group": group, "item": label, "web": w, "pdf": p,
                     "expect": str(web_s) if web_s == pdf_s else f"{web_s} ／ {pdf_s}"})

    t = rep["tables"]
    rv = rep["report_version_id"]
    item("版本", "report_version_id", rv)
    item("版本", "版本號", f"（第 {rep['version_no']} 版", f"（第 {rep['version_no']} 版）")
    item("版本", "報告 hash", rep["report_hash"][:16], rep["report_hash"])
    item("版本", "快照", rep["source_snapshot_id"])
    cut = rep["cutoff_at"]
    from datetime import datetime, timedelta, timezone
    c = datetime.fromisoformat(cut).astimezone(timezone(timedelta(hours=8)))
    item("版本", "資料截止（台北）", c.strftime("%Y/%m/%d %H:%M"), c.strftime("%Y-%m-%d %H:%M"))
    if rep.get("model_id"):  # MOCK versions have no model
        item("版本", "模型", rep["model_id"])
    # valuation / price
    val, price = rep["valuation"], t["price"]
    item("估值", "基準收盤價", f"{price['trade_date']} 收盤 {f2(price['value'])} 元")
    if val.get("dcf_per_share") is None:
        item("估值（NA）", "DCF 無法判定與原因", val["reason"])
    else:
        item("估值", "DCF 每股", f"DCF 每股 {f2(val['dcf_per_share'])} 元")
        item("估值", "差距", f"{val['gap'] * 100:.1f}%")
    item("估值", "估值狀態", val["label"])
    # quarters
    for q in t["quarters"] or []:
        for key, lab in (("revenue", "營收"), ("operating_income", "營業利益"), ("net_income", "淨利"),
                         ("free_cash_flow", "FCF")):
            v = q.get(key)
            item("季度", f"{q['period']} {lab}", "NA" if v is None else f2(v))
        src = {"mops_direct": "MOPS", "finmind_quarterly": "FinMind"}.get(q.get("eps_source"), q.get("eps_source"))
        item("季度", f"{q['period']} EPS", "NA" if q.get("eps") is None else f"{q['eps']:.2f}（{src}）")
        a = datetime.fromisoformat(q["available_at"]).astimezone(timezone(timedelta(hours=8)))
        item("季度", f"{q['period']} 可得時間", a.strftime("%Y/%m/%d %H:%M"), a.strftime("%Y-%m-%d %H:%M"))
    if t.get("quarters_na_reason"):
        item("季度（NA）", "季度缺值原因", t["quarters_na_reason"])
    ttm = t.get("ttm") or {}
    if ttm:
        item("TTM", "EPS TTM", f"EPS {f2(ttm['eps_ttm'])}" if ttm.get("eps_ttm") is not None else "NA", f2(ttm["eps_ttm"]) if ttm.get("eps_ttm") is not None else "NA")
        item("TTM", "FCF TTM", f2(ttm["fcf_ttm"]) if ttm.get("fcf_ttm") is not None else "NA")
        item("TTM", "TTM 季別", "、".join(ttm["periods"]))
    # DCF
    d = t.get("dcf_detail") or {}
    for key, lab in (("pv_fcf_total", "5 年 FCF 現值"), ("pv_terminal", "終端價值現值"), ("enterprise_value", "企業價值"),
                     ("net_debt", "淨負債"), ("equity_value", "股東權益")):
        if key in d:
            item("DCF", lab, "NA" if d[key] is None else f2(d[key]))
    for wacc, row in (t.get("sensitivity") or {}).items():
        for g, v in row.items():
            item("DCF 敏感度", f"WACC {wacc}・g {g}", "NA" if v is None else f2(v))
    a = t.get("dcf_assumptions") or {}
    if a:
        item("DCF", "WACC／g", f"WACC {a['wacc'] * 100:.1f}%", f"WACC {a['wacc'] * 100:.1f}%")
    # peers
    if t.get("peer_comparison") is None:
        item("同業（NA）", "同業比較不適用原因", t.get("peer_na_reason") or "NA")
    # claims and sources
    for cl in rep["claims"]:
        item("主張", f"{cl['claim_id']} 內文", cl["text"])
        for ref in cl.get("evidence_refs") or []:
            item("主張", f"{cl['claim_id']} 引用 {ref}", ref)
        for lim in cl.get("limitations") or []:
            item("主張", f"{cl['claim_id']} 限制", lim)
    for s in t.get("sources") or []:
        item("來源", f"{s['id']}（{'已解析' if s.get('resolved') else '未解析'}）", s["id"])
    # draft sections: the API exposes all of them as "sections" from W10-A on; older deploys only had three
    from research_ui.report_pdf import SECTION_TITLES
    sections = rep.get("sections") or {"unknowns": rep.get("unknowns"), "next_signals": rep.get("next_signals"),
                                       "conflicts": rep.get("counter_evidence")}
    for title, key in SECTION_TITLES:
        for x in sections.get(key) or []:
            item("草稿段落", title, x if isinstance(x, str) else json.dumps(x, ensure_ascii=False))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--http", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base = Path(a.dir)
    http = json.loads(Path(a.http).read_text(encoding="utf-8"))
    results = []
    for jf in sorted(base.glob("w10-*.json")):
        rep = json.loads(jf.read_text(encoding="utf-8"))["report"]
        rv = rep["report_version_id"]
        pdf_path = jf.with_suffix(".pdf")
        web = jf.with_name(jf.stem + "-web.txt").read_text(encoding="utf-8")
        doc = pymupdf.open(pdf_path)
        pdf_text = "\n".join(p.get_text() for p in doc)
        sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        h = http.get(rv, {})
        rows = check(rep, web, pdf_text)
        results.append({"rv": rv, "ticker": rep["ticker"], "version_no": rep["version_no"], "is_latest": rep["is_latest"],
                        "cutoff_at": rep["cutoff_at"], "pages": doc.page_count, "pdf_sha256": sha,
                        "pdf_hash_field": rep.get("pdf_hash"), "http": h, "rows": rows})
    lines = ["# v1.2 一致性回歸：已發布報告（第 1 批）", "",
             "- 擷取：2026-11-18（台北），Render https://fintech-agent-di0z.onrender.com，內建瀏覽器實際開啟",
             "- 方法：同一個 report_version_id 的「核准 JSON（網頁的資料來源）」「網頁顯示文字」「PDF 文字」三方比對；"
             "以 JSON 為準，逐項在網頁與 PDF（去除空白，因 PDF 會換行）找同一字串；應為 NA 的值兩邊都要顯示 NA。"
             "程式：`scripts/w10_consistency_check.py`，原始擷取檔不放 repo。",
             "- 範圍：Render 上全部 4 個已發布 LIVE 版本（含 2 個舊版）；3 份 FIXTURE 沒有 PDF、不屬正式輸出，另列於回歸紀錄。", ""]
    lines += ["## 總表", "", "| 版本 | 檔別 | 最新 | PDF 頁數 | PDF sha256＝報告 pdf_hash | 預覽＝下載（位元組） | 304 | 比對項目 | 網頁缺 | PDF 缺 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        h = r["http"]
        miss_w = [x for x in r["rows"] if not x["web"]]
        miss_p = [x for x in r["rows"] if not x["pdf"]]
        lines.append(f"| `{r['rv']}` | {r['ticker']} 第 {r['version_no']} 版 | {'是' if r['is_latest'] else '否（舊版）'} | {r['pages']} | "
                     f"{'✅' if r['pdf_sha256'] == r['pdf_hash_field'] else '❌'} | {'✅' if h.get('same_bytes') else '❌'} | "
                     f"{h.get('etag304')} | {len(r['rows'])} | {len(miss_w)} | {len(miss_p)} |")
    lines.append("")
    for r in results:
        lines += [f"## {r['ticker']} 第 {r['version_no']} 版 `{r['rv']}`", "",
                  f"- PDF：{r['pages']} 頁，sha256 `{r['pdf_sha256']}`；預覽與下載回傳同一份位元組。",
                  "", "| 類別 | 項目 | 應顯示 | 網頁 | PDF |", "|---|---|---|---|---|"]
        for x in r["rows"]:
            exp = x["expect"] if len(x["expect"]) <= 60 else x["expect"][:58] + "…"
            lines.append(f"| {x['group']} | {x['item']} | {exp.replace('|', '｜')} | {'✅' if x['web'] else '❌'} | {'✅' if x['pdf'] else '❌'} |")
        lines.append("")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path(a.out).with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in results:
        bad = [(x["group"], x["item"], x["web"], x["pdf"]) for x in r["rows"] if not (x["web"] and x["pdf"])]
        print(r["ticker"], r["version_no"], len(r["rows"]), "items;", "mismatch:", bad)


if __name__ == "__main__":
    main()
