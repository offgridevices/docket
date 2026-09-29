"""Demonstration A: the kernel reproduces CBO's published GCV comparison, exactly.

Every number asserted here is printed in CBO, *The Army's Ground Combat Vehicle Program
and Alternatives* (April 2013), Table 2-2 (p. 21) and Table A-3 (p. 35). The tolerance is
0.6 of a percentage point, which is CBO's own rounding of its published overall figures
to whole percent — not slack for the kernel: the kernel's arithmetic is exact and the
recomputed values are asserted to six decimals below.
"""

import json
import shutil
from pathlib import Path

import pytest

from demos.a_cbo_gcv_2013.build import build
from demos.a_cbo_gcv_2013.run import NOW, OUT, run
from docket.kernel.render import render_package
from docket.kernel.validate import validate
from docket.store import Graph
from tests.kernel.conftest import assert_history_honest

# CBO Table 2-2, p. 21: "Overall Improvement in Combat Vehicle Capability Relative to the
# Current Bradley IFV (Percent)", as printed.
CBO_PRIMARY = {"alt-gcv": 16, "alt-namer": 6, "alt-upgraded-bradley": 32,
               "alt-puma": 45, "alt-retain-bradley": 0}
CBO_SECONDARY = {"alt-gcv": 36, "alt-namer": 25, "alt-upgraded-bradley": 25,
                 "alt-puma": 38, "alt-retain-bradley": 0}
# The same figures before CBO rounded them, recomputed by hand from Table 2-2's category
# scores and Table A-3's weights. These are what the kernel must produce exactly.
EXACT_PRIMARY = {"alt-gcv": 16.4, "alt-namer": 6.1, "alt-upgraded-bradley": 31.8,
                 "alt-puma": 45.1, "alt-retain-bradley": 0.0}
EXACT_SECONDARY = {"alt-gcv": 36.0, "alt-namer": 25.25, "alt-upgraded-bradley": 25.5,
                   "alt-puma": 38.25, "alt-retain-bradley": 0.0}

# Analytic flip points on the secondary metric, worked out by hand from Table 2-2 with
# the other three weights rescaled to (1 - x)/3 each.
#   squad:     100x + 44(1-x)/3  = 0x + 153(1-x)/3  → x = 36.3333…/136.3333… (the ledger's
#              check for plan 03b)
#   lethality: -7x + 151(1-x)/3  = 103x + 50(1-x)/3 → x = 33.6667…/143.6667…
SQUAD_FLIP = (153 - 44) / 3 / (100 + (153 - 44) / 3)
LETHALITY_FLIP = (151 - 50) / 3 / (103 + 7 + (151 - 50) / 3)
# ruling R3 (plan 06 task 1): `build_package` now writes all six exports next to each
# `package-{rendering}.md`, so the two-run byte-identity check and the staleness check
# below must cover them too, or a genuinely non-deterministic export would pass unnoticed.
OUTPUT_FILES = (
    "package-full.md", "package-unclassified.md", "results.json",
    "export-prov-full.json", "export-prov-unclassified.json",
    "export-gsn-full.json", "export-gsn-unclassified.json",
    "export-dmn-full.xml", "export-dmn-unclassified.xml",
    "export-milstd3022-full.md", "export-milstd3022-unclassified.md",
    "export-madr-full.md", "export-madr-unclassified.md",
    "export-rtvm-full.csv", "export-rtvm-unclassified.csv",
)


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    """One run of the demo, shared by every test that only reads it."""
    return run(tmp_path_factory.mktemp("demo-a"))


def test_reproduces_cbo_published_overall_improvement(demo):
    res = demo["results"]
    for alt, published in CBO_PRIMARY.items():
        assert abs(res["primary"][alt] - published) <= 0.6, (alt, res["primary"][alt])
        assert res["primary"][alt] == pytest.approx(EXACT_PRIMARY[alt])
    for alt, published in CBO_SECONDARY.items():
        assert abs(res["secondary"][alt] - published) <= 0.6, (alt, res["secondary"][alt])
        assert res["secondary"][alt] == pytest.approx(EXACT_SECONDARY[alt])


def test_reproduces_cbo_rankings(demo):
    res = demo["results"]
    assert res["ranking"]["primary"] == [
        "alt-puma", "alt-upgraded-bradley", "alt-gcv", "alt-namer", "alt-retain-bradley"]
    # CBO p. 4: the Puma stays ahead of the GCV under the secondary metric, and the Namer
    # is "equal to the upgraded Bradley" (25.25 vs 25.5 before rounding).
    assert res["ranking"]["secondary"] == [
        "alt-puma", "alt-gcv", "alt-upgraded-bradley", "alt-namer", "alt-retain-bradley"]


def test_squad_weight_flip_matches_the_analytic_value(demo):
    squad = demo["results"]["flip"]["secondary"]["ws-secondary:m-squad"]
    assert squad["flipThreshold"] == pytest.approx(SQUAD_FLIP, abs=1e-6)
    assert squad["direction"] == "up"
    assert squad["flipDistance"] < 0.02
    assert squad["rankingAfter"][0] == "alt-gcv"
    # CBO's published secondary weighting (0.25) sits just short of the flip point, not
    # either side of it: the Puma leads on both of CBO's metrics, and 0.0165 more weight
    # on the full squad would have reversed that.
    assert 0.25 < squad["flipThreshold"] < 0.27


def test_the_shortest_flip_on_the_secondary_metric_is_named_honestly(demo):
    """The squad weight is not the shortest flip — the lethality weight is, barely.

    The brief expected `ws-secondary:m-squad`. Recomputed: the GCV overtakes the Puma at
    a lethality weight of 33.6667/143.6667 = 0.23433 (distance 0.01567) against the squad
    weight's 0.26650 (distance 0.01650). The record prints both, in order.
    """
    res = demo["results"]
    assert res["flip"]["secondary_shortest"] == "ws-secondary:m-leth"
    leth = res["flip"]["secondary"]["ws-secondary:m-leth"]
    assert leth["flipThreshold"] == pytest.approx(LETHALITY_FLIP, abs=1e-6)
    assert leth["flipDistance"] < res["flip"]["secondary"]["ws-secondary:m-squad"][
        "flipDistance"]
    assert leth["rankingAfter"][0] == "alt-gcv"


def test_the_record_is_ready_and_validates(demo):
    rr = demo["readiness"]
    assert rr["ready"] is True, rr["blockers"]
    assert rr["blockers"] == []
    g = demo["graph"]
    assert [f for f in validate(g, g.get("pol-cbo")) if f.severity == "blocking"] == []
    # Ready for the right reasons, not because nothing was checked: every gap and every
    # exclusion the record reaches is listed, and the standards scorer ran.
    assert set(rr["openGaps"]) == {"gap-aoa-report", "gap-sim-model", "gap-sim-vva",
                                   "gap-squad-reliability", "gap-survey-n"}
    assert "ex-no-thresholds" in rr["openExclusions"]
    assert g.get(rr["standardsAssessment"])["tailoring"] == "published-21"


def test_the_reuse_justified_path_is_exercised(demo):
    """Evidence reused past its purpose, three times, justified every time.

    `ReusePastPurpose` is checked across `blockers + warnings`, not warnings alone: it is a
    blocking finding, so asserting its absence from `warnings` would pass even on a record
    that had it.
    """
    rr = demo["readiness"]
    reuse = {tuple(f["objects"]) for f in rr["warnings"] if f["rule"] == "reuse-justified"}
    assert ("cl-primary", "ev-army-expert-estimates") in reuse
    assert ("cl-weights", "ev-soldier-survey") in reuse
    assert ("cl-squad-rationale", "ev-cbo-2013") in reuse
    assert not any(f["rule"] == "ReusePastPurpose" for f in rr["blockers"] + rr["warnings"])


def test_transition_history_is_honest(demo):
    assert_history_honest(demo["graph"], "ep-cbo-2013")
    states = [t["to"] for t in demo["graph"].get("ep-cbo-2013")["transitions"]]
    assert states == ["MODEL_APPROVED", "PLAN_APPROVED", "EVALUATED", "PENDING_SIGNATURE"]
    assert demo["graph"].get("ep-cbo-2013")["lifecycleState"] == "PENDING_SIGNATURE"


def test_the_saved_store_loads_and_still_validates(demo, tmp_path):
    loaded = Graph.load(Path(demo["outDir"]) / "graph")
    blocking = [f for f in validate(loaded, loaded.get("pol-cbo")) if f.severity == "blocking"]
    assert blocking == []
    assert loaded.snapshot_hash() == demo["graph"].snapshot_hash()


def test_two_runs_are_byte_identical(tmp_path):
    a, b = run(tmp_path / "a"), run(tmp_path / "b")
    for name in OUTPUT_FILES:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name
    for name in ("log.jsonl", "manifest.json"):
        assert ((tmp_path / "a" / "graph" / name).read_bytes()
                == (tmp_path / "b" / "graph" / name).read_bytes()), name
    assert a["packages"] == b["packages"]


@pytest.mark.parametrize("committed", [False, True])
def test_no_absolute_paths_in_any_output(demo, committed):
    """A package that named the machine it was built on could not be byte-identical
    anywhere else, and would leak a home directory into a deliverable."""
    out = OUT if committed else Path(demo["outDir"])
    checked = 0
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert str(out) not in text, path
        assert "/Users/" not in text, path
        assert "/home/" not in text, path
        assert "/tmp/" not in text, path
        checked += 1
    assert checked > 100, f"expected the whole store under {out}, saw {checked} files"


def test_the_readme_flip_table_matches_the_run():
    """The README quotes four flip thresholds and four distances in prose. Prose goes
    stale in silence, so every one of them is read back out of the committed
    `out/results.json` and matched against the line that prints it."""
    readme = (OUT.parent / "README.md").read_text(encoding="utf-8")
    flips = json.loads((OUT / "results.json").read_text())["flip"]["secondary"]
    assert len(flips) == 4
    for target, f in flips.items():
        row = [ln for ln in readme.splitlines() if ln.startswith(f"| `{target}`")]
        assert len(row) == 1, f"{target}: expected exactly one README row, got {len(row)}"
        cells = [c.strip() for c in row[0].strip("|").split("|")]
        assert cells[1] == "0.25", (target, cells)
        assert cells[2] == f"{f['flipThreshold']:.6f}", (target, cells)
        assert cells[3] == f"{f['flipDistance']:.6f}", (target, cells)
        leader = {"alt-gcv": "GCV", "alt-namer": "Namer"}[f["rankingAfter"][0]]
        assert cells[4] == f"{leader} overtakes the Puma", (target, cells)


def test_committed_output_is_current(tmp_path):
    fresh = run(tmp_path / "fresh")
    for name in OUTPUT_FILES:
        assert (OUT / name).read_bytes() == (tmp_path / "fresh" / name).read_bytes(), (
            f"{name} is stale — re-run: uv run python -m demos.a_cbo_gcv_2013.run")
    assert (OUT / "graph" / "manifest.json").read_bytes() == (
        tmp_path / "fresh" / "graph" / "manifest.json").read_bytes()
    assert fresh["packages"] == json.loads((OUT / "results.json").read_text())["packages"]


def test_unclassified_rendering_withholds_a_classified_value():
    """The withholding mechanism, demonstrated without lying about the record.

    Nothing in Demonstration A is classified: every source is public, so the two
    renderings withhold nothing and differ only in their headers. To show that the
    mechanism works, this test marks one evidence item CUI in a throwaway copy of the
    graph — a hypothetical, never written to `out/` — and checks that the unclassified
    rendering hides the values that rest on it and says so.
    """
    g = build()
    human = {"actorType": "human", "actorId": "shreyash"}
    ev = g.get("ev-army-aoa-2011")
    g.put({**ev, "rev": ev["rev"] + 1, "createdBy": human,
           "classification": {"level": "CUI", "metadataLevel": "CUI",
                              "controlledBy": "Department of the Army"}}, human)

    unclassified = render_package(g, "ep-cbo-2013", rendering="unclassified", now=NOW)
    full = render_package(g, "ep-cbo-2013", rendering="full", now=NOW)

    assert "[withheld: CUI]" in unclassified
    assert "| ob-upgraded-bradley-prot | alt-upgraded-bradley | m-prot | [withheld: CUI] |" \
        in unclassified
    assert "| ob-upgraded-bradley-prot | alt-upgraded-bradley | m-prot | 27 |" in full
    assert "[withheld" not in full


def test_the_two_committed_renderings_withhold_nothing():
    """...because every source in this record is public. Said out loud, not assumed."""
    for name in ("package-unclassified.md", "package-full.md"):
        assert "[withheld" not in (OUT / name).read_text(encoding="utf-8"), name


def test_run_writes_only_into_its_out_dir(tmp_path):
    target = tmp_path / "nested" / "out"
    run(target)
    # ruling R3: every export sits next to package-{rendering}.md in the same out/ dir.
    assert sorted(p.name for p in target.iterdir()) == sorted(
        [*OUTPUT_FILES, "graph"]
    )
    shutil.rmtree(target)
