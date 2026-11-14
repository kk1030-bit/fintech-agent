"""W09-A: record the short, version-labelled operation clip for E (demo/sample-w09.mp4). Playwright, Chromium.

    python scripts/w09_record_sample.py --base http://127.0.0.1:5109 --out tmp/w09-video --marks tmp/w09-video/marks.json

Real screen of the local app (this commit), not a mock-up: a MOCK job (no model call), two REPLAYs of recorded
Agent v2 runs, and a locally approved MOCK acceptance version with its PDF buttons
(headless Chromium has no PDF viewer; the PDF pages are in the screenshots). Nothing here is LIVE; the caption bar
added afterwards by ffmpeg says so on every frame. Segment start times are written to --marks.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--marks", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    marks: list[dict] = []
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(out),
                             record_video_size={"width": 1280, "height": 720})
        pg = ctx.new_page()
        t0 = time.monotonic()
        mark = lambda text: marks.append({"t": round(time.monotonic() - t0, 2), "text": text})  # noqa: E731
        slow = lambda sel: pg.locator(sel).first.scroll_into_view_if_needed()  # noqa: E731

        def show(sel: str, ms: int) -> None:
            pg.evaluate("s => { const el = document.querySelector(s); const y = el.getBoundingClientRect().top"
                        " + scrollY - 8; window.scrollTo({ top: y, behavior: 'smooth' }); }", sel)
            pg.wait_for_timeout(ms)

        mark("研究工作台（S07 儀表板）：已發布清單＝本機核准的 MOCK 驗收版本")
        pg.goto(a.base + "/research")
        pg.wait_for_timeout(3500)
        slow("#reportList")
        pg.wait_for_timeout(3000)

        mark("MOCK job：送出研究，狀態與預算計數（不呼叫模型）")
        pg.evaluate("window.scrollTo(0,0)")
        pg.select_option("#scenario", "revise_then_pass")
        pg.wait_for_timeout(1000)
        pg.click("#submitJob")
        show("#jobPanel", 4500)
        mark("job 恢復：執行中重新整理頁面，同一 job 從資料庫讀回")
        pg.reload()
        pg.wait_for_timeout(1200)
        show("#jobPanel", 8000)
        mark("MOCK job 結束：覆核第 1 輪要求修正 → 補查 → 第 2 輪通過；未經人工核准不會發布")
        show("#reviewSection", 5000)

        mark("REPLAY（Agent v2）：紀錄版本、prompt 版本與條件標在最上方")
        pg.evaluate("window.scrollTo(0,0)")
        pg.select_option("#replaySelect", "calib-v2-dual-day3:CASE-15")
        pg.wait_for_timeout(800)
        pg.click("#replayOpen")
        pg.wait_for_timeout(1500)
        show("#jobPanel", 5000)
        mark("REPLAY（Agent v2）：Reviewer 要求補查 → Researcher 補查改稿 → 第二輪仍不足而停止")
        show("#reviewSection", 7000)

        mark("REPLAY（Agent v2）：關鍵證據在 cutoff 之後 → 資料不足，不下結論")
        pg.evaluate("window.scrollTo(0,0)")
        pg.select_option("#replaySelect", "calib-v2-dual-rerun-1112:CASE-18")
        pg.wait_for_timeout(800)
        pg.click("#replayOpen")
        pg.wait_for_timeout(1500)
        show("#jobPanel", 6000)
        show("#reviewSection", 4000)

        mark("已核准報告（本機 MOCK 驗收版）：來源抽屜與 PDF")
        pg.locator("[data-open-report]").first.scroll_into_view_if_needed()
        pg.wait_for_timeout(800)
        pg.locator("[data-open-report]").first.click()
        pg.wait_for_timeout(3000)
        ev = pg.locator("[data-evidence]").first
        ev.scroll_into_view_if_needed()
        pg.wait_for_timeout(1000)
        ev.click()
        pg.wait_for_timeout(4000)
        pg.click("#drawerClose")
        pg.wait_for_timeout(800)
        mark("報告的 PDF 預覽／下載按鈕（同一 report_version_id；PDF 內容另見截圖）")
        pdf = pg.locator("#reportPanel a[href$='.pdf']").first
        pdf.scroll_into_view_if_needed()
        pdf.hover()
        pg.wait_for_timeout(4000)
        mark("end")
        ctx.close()
        br.close()
    Path(a.marks).write_text(json.dumps(marks, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()


# Caption bar (run after recording):
#   python -c "import scripts.w09_record_sample as m; m.caption('tmp/w09-video', 'demo/sample-w09.mp4', HEADER)"
def caption(video_dir: str, out: str, header: str,
            font: str = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc") -> None:
    """Pad an 80 px bar on top: line 1 = where/when/which version/label (every frame), line 2 = current segment."""
    import glob
    import subprocess

    d = Path(video_dir)
    src = glob.glob(str(d / "*.webm"))[0]
    marks = json.loads((d / "marks.json").read_text(encoding="utf-8"))
    (d / "head.txt").write_text(header, encoding="utf-8")
    vf = ["pad=1280:800:0:80:color=0x1f2328",
          f"drawtext=fontfile={font}:textfile={d / 'head.txt'}:fontsize=22:fontcolor=white:x=16:y=10"]
    for i, m in enumerate(marks[:-1]):
        end = marks[i + 1]["t"]
        (d / f"seg{i}.txt").write_text(f"{i + 1}. {m['text']}", encoding="utf-8")
        vf.append(f"drawtext=fontfile={font}:textfile={d / f'seg{i}.txt'}:fontsize=22:fontcolor=0xffd75e"
                  f":x=16:y=46:enable='between(t,{m['t']},{end + 30 if marks[i + 1]['text'] == 'end' else end})'")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", ",".join(vf), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "26", "-movflags", "+faststart", "-an", out], check=True)
