"""W09-A: replay list shows Agent v2 runs, labelled by version, for the three demo paths.

Before this change the replay list only had pre-v1 development runs (researcher-v1.2.0/1.2.1), all stopped at
insufficient evidence, with no version label: the "Reviewer asks for more evidence, Researcher revises" demo path
had no recorded run to show, and nothing told a viewer which Agent version a run came from.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research_ui.replays import TRACE_FILES, V2, list_replays

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ui(tmp_path, clock):
    from test_research_ui import make_app
    return make_app(tmp_path, clock).test_client()


def _researcher_minor(row) -> int:
    return int(row["prompt_versions"]["researcher"].rsplit(".", 1)[1])


def test_every_replay_carries_its_agent_version_and_run_condition(ui):
    rows = ui.get("/api/ui/replays").get_json()["replays"]
    assert rows and all(r["agent_version"] and r["condition"] and r["prompt_versions"] for r in rows)
    v2 = [r for r in rows if r["agent_version"] == V2]
    other = [r for r in rows if r["agent_version"] != V2]
    assert v2, "Agent v2 runs must be available for the demo"
    # v2 = researcher-v1.2.3 and later (handoff/agent-version-changes.md); development runs predate v1 (1.2.2).
    assert all(_researcher_minor(r) >= 3 for r in v2)
    assert all(_researcher_minor(r) < 2 for r in other)


def test_versions_are_listed_as_separate_groups_newest_first():
    rows = list_replays()
    order = list(dict.fromkeys(r["agent_version"] for r in rows))
    assert order[0] == V2
    # each version forms one contiguous block, so the dropdown's <optgroup>s never interleave
    assert len(order) == len({v["agent_version"] for v in TRACE_FILES.values()})
    blocks = [r["agent_version"] for r in rows]
    assert all(blocks.index(v) + blocks.count(v) - 1 == len(blocks) - 1 - blocks[::-1].index(v) for v in order)
    js = (ROOT / "static" / "research.js").read_text(encoding="utf-8")
    assert "<optgroup label=" in js


def test_revise_path_has_a_recorded_v2_run_with_two_review_rounds(ui):
    rows = {r["replay_id"]: r for r in ui.get("/api/ui/replays").get_json()["replays"]}
    rid = "calib-v2-dual-day3:CASE-15"
    assert rows[rid]["review_rounds"] == 2
    r = ui.get(f"/api/ui/replays/{rid}").get_json()
    rounds = r["review_view"]["rounds"]
    assert rounds[0]["final_decision"] == "revise" and rounds[1]["final_decision"] == "insufficient"
    # recorded as it happened: this run ends at insufficient evidence, not a pass
    assert r["job"]["status"] == "insufficient_evidence"
    assert r["source"]["agent_version"] == V2 and r["label"] == "REPLAY"


def test_v2_replays_show_the_frozen_dev_case_cutoff_and_snapshot(ui):
    r = ui.get("/api/ui/replays/calib-v2-dual-day3:CASE-15").get_json()
    assert r["job"]["cutoff_at"] == "2026-08-05T17:00:00+08:00"
    assert r["job"]["source_snapshot_id"] == "snap-dev-case-15"
    old = ui.get("/api/ui/replays/dev-v14-batch1:CASE-15").get_json()
    assert old["job"]["cutoff_at"] is None and old["job"]["source_snapshot_id"] is None  # pre-freeze: not guessed


def test_case04_misjudged_by_the_since_fixed_rule_is_annotated_and_nothing_else_is(ui):
    rows = ui.get("/api/ui/replays").get_json()["replays"]
    noted = [r["replay_id"] for r in rows if r["record_note"]]
    assert noted == ["calib-v2-dual-postprice-1112:CASE-04"]
    r = ui.get("/api/ui/replays/calib-v2-dual-postprice-1112:CASE-04").get_json()
    assert "第 28 節" in r["case"]["record_note"]["note"]


def test_replays_never_read_the_sealed_holdout():
    assert all("holdout" not in rel and rel.startswith("agent/") for rel in TRACE_FILES)
