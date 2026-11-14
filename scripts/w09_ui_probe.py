"""W09-A: browser check of job recovery, PDF and mobile layout on the local app (Playwright, Chromium).

    python scripts/w09_ui_probe.py --base http://127.0.0.1:5109 --out design/w09/ui-probe.json

Needs RESEARCH_UI_MOCK=1 and a report store with at least one published version (scripts/w07_demo_store.py).
Each check records what it saw and pass/fail; nothing is retried to make it pass.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright

OVERFLOW = """() => { const w = innerWidth; return [...document.querySelectorAll('body *')].filter(e => {
  const r = e.getBoundingClientRect(); return r.right > w + 1 && r.width > 0 && getComputedStyle(e).position !== 'fixed'
  && !e.closest('[hidden]') && !e.closest('.sens-wrap'); }).slice(0, 6).map(e => e.tagName + '.' + e.className); }"""
UNCOVERED = """el => { const r = el.getBoundingClientRect(); const hit = document.elementFromPoint(r.left + r.width / 2,
  r.top + r.height / 2); return !!hit && (hit === el || el.contains(hit)); }"""


def head(url: str, extra: dict | None = None) -> dict:
    req = Request(url, headers=extra or {})
    try:
        with urlopen(req) as r:
            body = r.read()
            return {"status": r.status, "type": r.headers.get("Content-Type"), "disp": r.headers.get("Content-Disposition"),
                    "etag": r.headers.get("ETag"), "magic": body[:5].decode("latin1"), "bytes": len(body)}
    except Exception as exc:  # 304 raises in urllib
        return {"status": getattr(exc, "code", None)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    checks: list[dict] = []
    add = lambda name, ok, seen: checks.append({"check": name, "pass": bool(ok), "seen": seen})  # noqa: E731
    with sync_playwright() as p:
        br = p.chromium.launch()
        for w, h in ((1440, 900), (390, 844)):
            mobile = w < 768
            pg = br.new_page(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile)
            errs: list[str] = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(a.base + "/research")
            pg.wait_for_timeout(1500)
            add(f"{w}: no horizontal overflow on load", not pg.evaluate(OVERFLOW), pg.evaluate(OVERFLOW))

            # job recovery 1: reload while running keeps the same job and it keeps progressing
            pg.select_option("#scenario", "revise_then_pass")
            pg.click("#submitJob")
            pg.wait_for_timeout(1500)
            job_url = pg.url
            pg.reload()
            pg.wait_for_timeout(1000)
            after = pg.inner_text("#jobPanel")
            jid = job_url.split("job=")[-1]
            add(f"{w}: reload keeps ?job= and shows the same job", jid in pg.url and jid in after, after[:80])
            pg.wait_for_timeout(15000)
            done = pg.inner_text("#jobPanel")
            add(f"{w}: job finishes after reload (no restart from zero)", "review_pass" in done, done[:60])

            # job recovery 2: network drop while polling → keeps last state, retries, recovers
            pg.select_option("#scenario", "succeeded")
            pg.click("#submitJob")
            pg.wait_for_timeout(1500)
            pg.route("**/api/ui/jobs/**", lambda r: r.abort())
            pg.wait_for_timeout(5000)
            dropped = pg.inner_text("#jobPanel")
            add(f"{w}: connection drop keeps last state and says it will retry", "連線中斷" in dropped and "job_id" in dropped,
                dropped[:80])
            pg.unroute("**/api/ui/jobs/**")
            pg.wait_for_timeout(12000)
            add(f"{w}: polling recovers after the drop", "連線中斷" not in pg.inner_text("#jobPanel"),
                pg.inner_text("#jobPanel")[:60])

            # job recovery 3: unknown job id → clear message, not stuck on loading
            pg.goto(a.base + "/research?job=nonexistent-w09")
            pg.wait_for_timeout(1500)
            t = pg.inner_text("#jobPanel")
            add(f"{w}: unknown job shows a message", "找不到" in t, t[:60])

            # quota: paused_quota shows state, reason and counters
            pg.goto(a.base + "/research")
            pg.wait_for_timeout(1200)
            pg.select_option("#scenario", "paused_quota")
            pg.click("#submitJob")
            pg.wait_for_timeout(9000)
            t = pg.inner_text("#jobPanel")
            add(f"{w}: paused_quota readable (state, reason, counters)",
                all(s in t for s in ("暫停：配額", "daily_quota", "模型請求", "/8")), t[:120])

            # report + drawer + PDF buttons
            pg.goto(a.base + "/research")
            pg.wait_for_timeout(1500)
            pg.locator("[data-open-report]").first.click()
            pg.wait_for_timeout(2500)
            add(f"{w}: no overflow with a report open", not pg.evaluate(OVERFLOW), pg.evaluate(OVERFLOW))
            btns = pg.locator("#reportPanel a[href$='.pdf'], #reportPanel a[href$='/download']")
            seen = []
            for i in range(btns.count()):
                b = btns.nth(i)
                b.scroll_into_view_if_needed()
                box = b.bounding_box()
                seen.append([b.inner_text(), round(box["height"]), b.evaluate(UNCOVERED)])
            # touch target height only matters on a phone (first run applied it to desktop too: 34 px there)
            min_h = 40 if mobile else 0
            add(f"{w}: PDF buttons visible, not covered" + (", ≥40 px tall" if mobile else ""),
                seen and all(s[1] >= min_h and s[2] for s in seen), seen)
            ev = pg.locator("#reportPanel [data-evidence]").first
            ev.scroll_into_view_if_needed()
            ev.click()
            pg.wait_for_timeout(1500)
            box = pg.locator("#drawer").bounding_box()
            add(f"{w}: source drawer opens within the screen", box["width"] <= w + 1, box)
            pg.click("#drawerClose")
            add(f"{w}: no page errors", not errs, errs)
            pg.close()
        br.close()
    rv = json.loads(urlopen(a.base + "/api/ui/published").read())["reports"][0]["report_version_id"]
    pv = head(f"{a.base}/api/ui/reports/{rv}.pdf")
    dl = head(f"{a.base}/api/ui/reports/{rv}/download")
    add("PDF preview inline, application/pdf, %PDF", pv["status"] == 200 and pv["magic"] == "%PDF-"
        and pv["disp"].startswith("inline"), pv)
    add("PDF download attachment, same bytes", dl["status"] == 200 and dl["disp"].startswith("attachment")
        and dl["bytes"] == pv["bytes"], dl)
    add("PDF ETag → 304", head(f"{a.base}/api/ui/reports/{rv}.pdf", {"If-None-Match": pv["etag"]})["status"] == 304, pv["etag"])
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"base": a.base, "checks": checks,
                                       "passed": sum(c["pass"] for c in checks), "total": len(checks)},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{sum(c['pass'] for c in checks)}/{len(checks)} passed")
    for c in checks:
        if not c["pass"]:
            print("FAIL", c["check"], c["seen"])


if __name__ == "__main__":
    main()
