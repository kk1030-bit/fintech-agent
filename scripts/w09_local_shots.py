"""W09-A: local screenshots of what is not on Render yet (Agent v2 REPLAYs, this branch) or never is (MOCK jobs).

    python scripts/w09_local_shots.py --base http://127.0.0.1:5109 --out media/w09

Real screen of the local app (Playwright, Chromium); labelled MOCK / REPLAY and "本機" in the manifest.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch()
        for w, h in ((1440, 900), (390, 844)):
            mobile = w < 768
            pg = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=mobile,
                             has_touch=mobile)
            shot = lambda sel, name: pg.locator(sel).screenshot(path=str(out / f"{name}-{w}.png"))  # noqa: E731
            # REPLAY, Agent v2: revise round then stop (S03), and insufficient evidence (S05)
            for rid, name in (("calib-v2-dual-day3:CASE-15", "w09-l01-local-replay-v2-case15-revise"),
                              ("calib-v2-dual-rerun-1112:CASE-18", "w09-l02-local-replay-v2-case18-insufficient")):
                pg.goto(f"{a.base}/research?replay={rid}")
                pg.wait_for_timeout(2500)
                shot("section.o2", name + "-status")
                shot("#reviewSection", name + "-review")
            # MOCK job paused on quota (S02: state and quota readable)
            pg.goto(f"{a.base}/research")
            pg.wait_for_timeout(1500)
            pg.select_option("#scenario", "paused_quota")
            pg.click("#submitJob")
            pg.wait_for_timeout(9000)
            shot("section.o2", "w09-l03-local-mock-paused-quota")
            pg.close()
        br.close()


if __name__ == "__main__":
    main()
