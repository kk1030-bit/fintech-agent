"""W10-A: capture what scripts/w10_consistency_check.py compares, from a server Playwright can reach (local app).

    python scripts/w10_capture.py --base http://127.0.0.1:5110 --out tmp/w10-local

For every published version (latest and older ones): the approved JSON (/api/ui/reports/<rv>), the preview PDF,
and the report section's text after loading /research?report=<rv> (collapsed parts opened), plus the HTTP checks
(sha256 of preview and download, 304 on If-None-Match). Read-only. Render was captured the same way in the
desktop app's browser, because this container cannot reach onrender.com.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright


def get(url: str, headers: dict | None = None):
    try:
        with urlopen(Request(url, headers=headers or {})) as r:
            return r.status, dict(r.headers), r.read()
    except Exception as exc:
        return getattr(exc, "code", None), {}, b""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pub = json.loads(get(a.base + "/api/ui/published")[2])["reports"]
    rvs = []
    for r in pub:
        if r.get("pdf_status") != "published":
            continue
        det = json.loads(get(f"{a.base}/api/ui/reports/{r['report_version_id']}")[2])["report"]
        rvs += [h["report_version_id"] for h in det.get("history") or []] or [r["report_version_id"]]
    http = {}
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": 1440, "height": 900})
        for rv in dict.fromkeys(rvs):
            _, _, body = get(f"{a.base}/api/ui/reports/{rv}")
            rep = json.loads(body)["report"]
            stem = f"w10-{rep['ticker']}-v{rep['version_no']}-{rv}"
            (out / f"{stem}.json").write_bytes(body)
            s1, h1, pdf = get(f"{a.base}/api/ui/reports/{rv}.pdf")
            s2, h2, dl = get(f"{a.base}/api/ui/reports/{rv}/download")
            s3, _, _ = get(f"{a.base}/api/ui/reports/{rv}.pdf", {"If-None-Match": h1.get("ETag", "")})
            (out / f"{stem}.pdf").write_bytes(pdf)
            http[rv] = {"preview": {"status": s1, "disp": h1.get("Content-Disposition")},
                        "download": {"status": s2, "disp": h2.get("Content-Disposition")}, "etag304": s3,
                        "same_bytes": hashlib.sha256(pdf).digest() == hashlib.sha256(dl).digest()}
            pg.goto(f"{a.base}/research?report={rv}")
            pg.wait_for_timeout(2500)
            pg.evaluate("() => document.querySelectorAll('#reportSection details').forEach(d => d.open = true)")
            (out / f"{stem}-web.txt").write_text(pg.inner_text("#reportSection"), encoding="utf-8")
        br.close()
    (out / "http.json").write_text(json.dumps(http, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(http)} versions captured into {out}")


if __name__ == "__main__":
    main()
