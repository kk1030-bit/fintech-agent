"""W10-A: the web page shows the same draft sections and source list as the PDF of the same report_version_id.

Before: the PDF printed 總經觀察／基本面觀察／估值情境／負面因素／正面因素／未知事項 and the full source list, the web
page did not (found on Render 11/18: the unknowns of all four published versions and one extra source of each
older version were only in the PDF).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from research_ui import OBSERVATION_KEYS
from research_ui.report_pdf import SECTION_TITLES

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "research.js").read_text(encoding="utf-8")


def test_web_and_pdf_list_the_same_sections_with_the_same_titles_in_the_same_order():
    block = re.search(r"const SECTION_TITLES = (\[.*?\]\]);", JS, re.S).group(1)
    web = [tuple(x) for x in ast.literal_eval(block)]
    assert web == [tuple(x) for x in SECTION_TITLES]
    assert tuple(k for _, k in SECTION_TITLES) == OBSERVATION_KEYS


def test_report_detail_carries_every_section_and_the_page_renders_the_source_list(tmp_path, clock):
    from test_obs_trace import fact, make_job, READ
    from test_research_ui import make_app

    app = make_app(tmp_path, clock)
    store = app.extensions["report_store"]
    job = make_job([READ], [fact("c1", ["obs-1"])])
    job["draft"].update(unknowns=["缺少完整四季 EPS"], fundamental_observations=["營收年增"],
                        positive_channels=["需求維持"], next_signals=["正式季報"])
    job.update(job_id="job-w10", status="succeeded", review={"decision": "pass"}, mode="dual", question_version="q",
               model_id="m")
    v = store.create_version(job, [])
    store.approve(v["report_version_id"], v["report_hash"], "test")
    store.publish(v["report_version_id"])
    rep = app.test_client().get(f"/api/ui/reports/{v['report_version_id']}").get_json()["report"]
    assert set(rep["sections"]) == set(OBSERVATION_KEYS)
    assert rep["sections"]["unknowns"] == ["缺少完整四季 EPS"]
    assert rep["sections"]["fundamental_observations"] == ["營收年增"]
    assert [s["id"] for s in rep["tables"]["sources"]] == ["obs-1"]
    assert "sourcesHtml(r.tables.sources" in JS and "sectionsHtml(r.sections" in JS
