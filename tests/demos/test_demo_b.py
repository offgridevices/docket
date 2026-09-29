"""Demonstration B: GAO's grid reproduced, and its nine findings detected where GAO put them.

Every number here was **measured** from a run of `demos/b_omfv_2019_2023/run.py` and then
written down. What is asserted in advance is only the shape the demonstration exists to
hold: nine of nine grid cells, F1-F9 each firing on the section GAO attributed it to, the
cross-fires recorded rather than filtered out, and nothing ready anywhere.

Nothing here asserts on the *wording* of a dimension qualifier, which belongs to a module
under active revision. The bytes of every committed file under `out/` — packages and
export files included — are checked against a fresh run, because a stale rendered package
in a deliverable is worse than a test that fails when the renderer changes.

GAO-23-106549 published nine section-by-dimension verdicts IN PROSE and nine findings, and
no per-question labels. Arranging the nine as a 3x3 grid is OURS, cutting GAO's prose into
nine findings is OUR enumeration, and every per-question state below is OURS.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest
import yaml

from demos.b_omfv_2019_2023 import build as B
from demos.b_omfv_2019_2023.run import GROUND_TRUTH, OUT, RESULTS_FILE, run
from docket.kernel.validate import orphan_gaps, validate
from docket.store import Graph
from tests.kernel.conftest import assert_history_honest

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "demos" / "b_omfv_2019_2023"
STUB = REPO / "sources" / "army-2023-06-26-omfv-phase-3-4-award.source.md"

# The out/ files that depend only on the kernel's scoring, never on the renderer.
SCORING_FILES = (RESULTS_FILE, "grid.json", "findings_matrix.json", "diffs.json",
                 "repair.json", "ce-before.json", "ce-after.json",
                 "affected_by_gao.json", "report.md")


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    """One run of the demonstration, shared by every test that only reads it."""
    return run(tmp_path_factory.mktemp("demo-b"))


@pytest.fixture(scope="module")
def truth() -> dict:
    return yaml.safe_load(GROUND_TRUTH.read_text(encoding="utf-8"))


# ---- the demonstration's own claims --------------------------------------------------
def test_demo_b_grid_and_findings(demo):
    assert demo["grid_match"] == 9, demo["grid"]
    findings = {k: v for k, v in demo["findings"].items() if k.startswith("F")}
    assert len(findings) == 9
    assert all(v["detected"] for v in findings.values()), \
        {k: v for k, v in findings.items() if not v["detected"]}
    # Ruling R5: the ids `open_refresh` actually produces.
    assert demo["episodes"] == [
        "ep-omfv-2020-02", "ep-omfv-2020-02-r2", "ep-omfv-2020-02-r3",
        "ep-omfv-2020-02-r4", "ep-omfv-2020-02-r4-dc", "ep-omfv-2020-02-r4-fs",
        "ep-omfv-2020-02-r4-ce", "ep-omfv-2020-02-r5"]
    assert demo["repair"]["before"] == "NotAssessableAtLevel"
    assert demo["repair"]["after"] == "assessable-with-classified-value"
    assert demo["repair"]["classification_level"] == "S"
    assert (demo["repair"]["exe14_before"], demo["repair"]["exe14_after"]) == (3, 1)
    # The sensitivity credit GAO gave stands: DES-6 is not 3 or 4 on combat effectiveness.
    assert demo["des6_ce_state"] in (1, 2)


# ---- C1: what the nine cells rest on -------------------------------------------------
def test_nine_of_nine_is_unreachable_without_the_narrative_only_clauses(demo):
    """Ruling R2 added `{PRE-3: claims_exist_no_silence}` and `{PRE-4: claims_exist}` to
    `rules.yaml` during this same plan. Withdraw them and the measured grid is 6 of 9.

    This is the non-vacuity evidence for the headline number. Without it a reviewer who
    diffs plan 05's commits finds that the presentation ladder moved after a pre-flight
    recorded the target as unreachable, and reads "9 of 9, measured" as fitted. The run
    itself measures this on every invocation; the test pins the number.
    """
    withdrawn = demo["grid_counterfactuals"]["r2_clauses_withdrawn"]
    assert withdrawn["grid_match"] == 6
    assert withdrawn["clauses"] == ["PRE-3: claims_exist_no_silence",
                                    "PRE-4: claims_exist"]
    for section in ("dc", "fs", "ce"):
        assert withdrawn["pre_3"][section] == 4
        assert withdrawn["pre_4"][section] == 4
        assert withdrawn["objectivity"][section] == "insufficient_to_conclude"
        # Only objectivity moves. Validity and reliability were already at
        # insufficient_to_conclude and stay there.
        assert withdrawn["grid"][section]["validity"] == "insufficient_to_conclude"
        assert withdrawn["grid"][section]["reliability"] == "insufficient_to_conclude"
    assert demo["grid_counterfactuals"]["r2_decision"].endswith(
        "2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md")


def test_nine_of_nine_is_unreachable_at_the_kernel_default_k(demo):
    """Ruling R3 set `pol-omfv.aggregationK = 21`. At the kernel default 1 it is 6 of 9.

    Measured across the dial, so the reader can see where the number turns over rather
    than take 21 on trust: 1 → 6, 3 → 6, 4 → 8, 5 → 9, 21 → 9.
    """
    by_k = {row["k"]: row["grid_match"] for row in demo["grid_counterfactuals"]["k"]}
    assert by_k == {1: 6, 3: 6, 4: 8, 5: 9, 21: 9}
    at_one = next(r for r in demo["grid_counterfactuals"]["k"] if r["k"] == 1)
    assert set(at_one["objectivity"].values()) == {"not_objective"}
    assert demo["grid_counterfactuals"]["k_decision"].endswith(
        "2026-09-05-aggregation-k-is-a-policy-parameter.md")


def test_six_of_the_nine_cells_move_under_neither_counterfactual(demo):
    """The true and stronger story: validity and reliability are immovable.

    Both read `insufficient_to_conclude` from PRE-1 = 4 and EXE-5 = 4, and PRE-1 is 4
    because `claims_all_supported` requires every cited evidence item to carry a content
    `reliabilitySteps` and every one of them is the `gap-reliability-steps` object — GAO's
    F8. No scorer dial reaches it.
    """
    for section in ("dc", "fs", "ce"):
        assert demo["states"][section]["PRE-1"] == 4
        assert demo["states"][section]["EXE-5"] == 4
    # Six cells — validity and reliability on three sections — are the floor of every
    # counterfactual the run measures.
    floors = [row["grid_match"] for row in demo["grid_counterfactuals"]["k"]]
    floors.append(demo["grid_counterfactuals"]["r2_clauses_withdrawn"]["grid_match"])
    assert min(floors) == 6, floors
    for row in demo["grid_counterfactuals"]["k"]:
        for section in ("dc", "fs", "ce"):
            assert row["objectivity"][section] in ("not_objective",
                                                   "generally_objective")


def test_the_report_and_the_readme_name_both_scorer_decisions(demo):
    report = (Path(demo["outDir"]) / "report.md").read_text(encoding="utf-8")
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    for text in (report, readme):
        assert "2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md" in text
        assert "2026-09-05-aggregation-k-is-a-policy-parameter.md" in text
        assert "6 of 9" in text
    # M3: the caveat the README carries must be in the generated artefact too.
    assert "no evaluation run anywhere in this demonstration" in report
    # M1: nothing in Demo B calls the 3x3 arrangement GAO's. GAO publishes nine verdicts
    # in prose; Figure 3 (printed p. 7) is the standards figure, not a verdict grid.
    attributes_the_grid_to_gao = re.compile(
        r"GAO(?:'s)?\s+published\s+(?:a\s+)?(?:3|grid)|published\s+3.3\s+(?:verdict\s+)?grid",
        re.IGNORECASE)
    sources = {name: (HERE / name).read_text(encoding="utf-8")
               for name in ("README.md", "run.py", "build.py",
                            "gao_23_106549_ground_truth.yaml")}
    sources["out/report.md"] = report
    for name, text in sources.items():
        hit = attributes_the_grid_to_gao.search(text)
        assert hit is None, (name, hit.group(0) if hit else None)


def test_the_counterfactual_repair_reports_the_reliability_cell_it_flips(demo):
    """C2: the repair moves EXE-5 from 4 to 2 and with it GAO's reliability verdict.

    `cf-drs-ce-metrics` gives `ev-ce-metrics` a content `reliabilitySteps`, which is
    exactly the F8 silence. Re-scored under the grid tailoring the combat-effectiveness
    row reads `generally_reliable`. That is a bigger claim than the three-row table used
    to make, and the demonstration now makes it out loud instead of hiding it inside a
    repair described as being about locatability.
    """
    repair = demo["repair"]
    assert (repair["exe5_before"], repair["exe5_after"]) == (4, 2)
    assert repair["ce_row_before"] == {"objectivity": "generally_objective",
                                       "validity": "insufficient_to_conclude",
                                       "reliability": "insufficient_to_conclude"}
    assert repair["ce_row_after"] == {"objectivity": "generally_objective",
                                      "validity": "insufficient_to_conclude",
                                      "reliability": "generally_reliable"}
    after = json.loads(
        (Path(demo["outDir"]) / "ce-after.json").read_text(encoding="utf-8"))
    assert after["gridTailoringStates"]["EXE-5"] == 2
    # Validity does not move: PRE-1 is still 4, because every OTHER cited evidence item's
    # reliabilitySteps is still the gap.
    assert after["gridTailoringStates"]["PRE-1"] == 4
    report = (Path(demo["outDir"]) / "report.md").read_text(encoding="utf-8")
    assert "generally_reliable" in report
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    assert "generally reliable" in readme


def test_the_grid_matches_gao_cell_for_cell(demo, truth):
    verdict_map = truth["ours"]["verdict_map"]
    for section, row in truth["transcribed"]["grid"].items():
        for dimension, published in row.items():
            assert demo["grid"][section][dimension] == verdict_map[published], \
                (section, dimension)


def test_the_ground_truth_file_separates_gaos_words_from_ours(truth):
    """I3: the file's job is that separation, so its own shape has to hold it.

    `transcribed:` is GAO's words and GAO's attribution. `ours:` is the reading: the
    kernel mechanisms, the object ids, the expected cross-fires, the translation into the
    kernel's verdict enum, the glosses and the count of nine. An earlier version of this
    file said "Nothing in this file is our reading" on line 1, which was false of three
    of its own fields.
    """
    assert set(truth) == {"source", "transcribed", "ours"}
    assert set(truth["transcribed"]) == {"grid", "quotations", "findings"}
    assert set(truth["ours"]) == {"enumeration", "what_gao_published", "verdict_map",
                                  "glosses", "findings", "expected_cross_fires"}
    # Nothing under `transcribed:` names a kernel rule, an object id or a question id.
    blob = yaml.safe_dump(truth["transcribed"])
    for ours in ("mechanism", "object_hint", "ev-trac", "gap-", "EXE-", "PRE-", "DES-",
                 "generally_objective", "insufficient_to_conclude"):
        assert ours not in blob, ours
    assert set(truth["transcribed"]["findings"]) == set(truth["ours"]["findings"])
    for fid, spec in truth["ours"]["findings"].items():
        assert ("rule" in spec) ^ ("rating" in spec), fid


def test_each_finding_is_attributed_to_the_sub_episode_gao_named(demo, truth):
    """Ruling R7: detected somewhere in the graph is not enough."""
    for fid, spec in truth["transcribed"]["findings"].items():
        measured = demo["findings"][fid]
        for section in spec["attributed_to"]:
            assert section in measured["sub_episode"], (fid, measured)
        assert measured["attributed_to"] == list(spec["attributed_to"])


def test_f7_and_f8_are_detected_by_a_rating_not_a_rule(demo, truth):
    """M2. The other seven are rules; these two are EXE-8 and EXE-5 reaching state 4."""
    kinds = {fid: demo["findings"][fid]["detected_by"]
             for fid in truth["ours"]["findings"]}
    assert kinds == {"F1": "rule", "F2": "rule", "F3": "rule", "F4": "rule",
                     "F5": "rule", "F6": "rule", "F7": "rating", "F8": "rating",
                     "F9": "rule"}
    for section in ("dc", "fs", "ce"):
        assert demo["states"][section]["EXE-8"] == 4
        assert demo["states"][section]["EXE-5"] == 4


def test_the_cross_fires_are_recorded_not_suppressed(demo, truth):
    """Three findings fire on sections GAO did not attribute them to. Say so."""
    measured = demo["findings"]["cross_fires"]
    expected = {k: v for k, v in truth["ours"]["expected_cross_fires"].items()
                if isinstance(v, list)}
    assert measured == expected, (measured, expected)
    assert measured["definition-missing"] == ["dc", "ce"]
    assert measured["silent-omission"] == ["dc", "ce"]


def test_what_our_attribution_rule_suppresses_is_measured_and_reported(demo):
    """I4: the cross-fire table is the list after one correction of ours.

    `readiness._counts_for_episode` keeps a finding for an episode if the finding names
    anything that episode can reach, and all three sections share one evidence register —
    so the kernel's own scoping puts `inclusion-reason-missing` on `dc` and `fs` as well.
    Our rule is right (only the section whose claim did the citing owns it), but the
    difference has to be printed rather than assumed away.
    """
    suppressed = demo["findings"]["cross_fires_suppressed_by_our_attribution"]
    assert suppressed == {"inclusion-reason-missing": ["dc", "fs"]}
    assert demo["findings"]["F3"]["sub_episode"] == ["ce"]
    note = demo["findings"]["cross_fires_suppressed_by_our_attribution_note"]
    assert "shared" in note or "share one evidence register" in note


def test_earlier_episodes_silently_omit_because_they_have_no_claims(demo):
    counts = demo["findings"]["earlier_episode_silent_omissions"]
    assert set(counts) == set(B.MAIN_CHAIN)
    # Measured: every register entry of every main-chain episode is uncited, because no
    # main-chain episode has a claim at all.
    assert counts == {"ep-omfv-2020-02": 3, "ep-omfv-2020-02-r2": 7,
                      "ep-omfv-2020-02-r3": 21, "ep-omfv-2020-02-r4": 21,
                      "ep-omfv-2020-02-r5": 21}
    for ep_id in B.MAIN_CHAIN:
        assert demo["graph"].get(ep_id)["claims"] == []
    assert "no claims" in demo["findings"]["earlier_episode_silent_omissions_reason"]


def test_nothing_is_ready_and_the_reasons_are_named(demo):
    assert not any(demo["ready"].values()), demo["ready"]
    assert set(demo["ready"]) == set(demo["episodes"])
    assert "bias-check-missing" in demo["blocker_rules"]
    assert "objective-measured" in demo["blocker_rules"]
    assert "linchpin-unevidenced" in demo["blocker_rules"]
    assert "silent-omission" in demo["blocker_rules"]
    assert "objective-run-coverage" in demo["blocker_rules"]
    # F4 and F1 are section-scoped, so they must NOT appear on every episode.
    assert "NotAssessableAtLevel" in demo["blockers"]["ep-omfv-2020-02-r4-ce"]
    assert "NotAssessableAtLevel" not in demo["blockers"]["ep-omfv-2020-02-r4-dc"]
    assert "ReusePastPurpose" in demo["blockers"]["ep-omfv-2020-02-r4-fs"]
    assert "ReusePastPurpose" not in demo["blockers"]["ep-omfv-2020-02-r4-ce"]


def test_eight_of_nine_characteristics_have_no_measure(demo):
    """The true statement: the record names nine characteristics and publishes one metric.

    The readiness report carries ten `objective-measured` blockers, not eight: it keeps
    any finding naming an object the episode can reach, and through the programme every
    episode reaches the two February objectives the December refresh superseded. Those
    two are somebody else's episode's findings. This asserts the eight that are this
    section's own, and that the extra two are exactly the superseded pair.
    """
    g = demo["graph"]
    with_measures = [o for o in B.NINE_AT_R4 if g.get(o).get("measures")]
    assert with_measures == ["obj-weight"]
    ce = g.get(B.SUB_EPISODES["ce"])
    assert len(ce["objectives"]) == 9

    named = {b["objects"][0] for b in demo["sectionReadiness"]["ce"]["blockers"]
             if b["rule"] == "objective-measured"}
    own = {o for o in ce["objectives"] if not g.get(o).get("measures")}
    assert len(own) == 8 and "obj-weight" not in own
    assert own <= named
    assert named - own == {"obj-survivability", "obj-manning"}


def test_no_episode_inherits_a_computed_bias_indicator(demo):
    """A bias indicator the kernel computed for episode N is a fact about episode N.

    `open_refresh` used to carry `risks` forward like any other reference list, so
    `ep-omfv-2020-02-r4-ce.risks` held five inherited `bias-selection` Risks, one per
    prior episode, and F3's evidence would have been five findings instead of one. The
    kernel now drops kernel-authored bias Risks on refresh (`is_computed_bias_risk`) and
    `build_sub_episodes` does the same when it copies `-r4`'s lists.
    """
    g = demo["graph"]
    for ep_id in demo["episodes"]:
        risks = g.get(ep_id)["risks"]
        assert risks == [f"risk-bias-{ep_id}-selection"], (ep_id, risks)
    # And what run.py reports for F3 is that one Risk, agreeing with the readiness
    # report's own `computedBiasRisks`.
    ce = B.SUB_EPISODES["ce"]
    assert demo["sectionReadiness"]["ce"]["computedBiasRisks"] == \
        [f"risk-bias-{ce}-selection"]
    assert any(f"risk-bias-{ce}-selection" in line
               for line in demo["findings"]["F3"]["by"])


# ---- the identifications that are ours -----------------------------------------------
def test_every_study_identification_that_is_ours_is_marked_inferred(demo):
    """I1. GAO names two TRAC studies and the December deck has two TRAC line items;
    mapping one onto the other is ours in both directions, and the deck's own schedule
    points the other way. Same for MBL1, HSI 1 and HSI 2.
    """
    g = demo["graph"]
    for oid in ("ev-trac-aoa", "ev-trac-oe", "ev-mbl-1", "ev-hsi-1", "ev-hsi-2"):
        assert g.get(oid)["confidence"] == "inferred", oid
        assert "OUR" in g.get(oid)["inclusionReason"].upper(), oid
    # `ev-trac-aoa.model` would assert that GAO's September 2021 study ran on the model
    # the deck calls TRAC OE. No source says that, so the slot is a gap.
    assert g.get("ev-trac-aoa")["model"] == {"$gap": "gap-trac-aoa-model"}
    assert g.get("gap-trac-aoa-model")["impact"] == "degrading"
    # The four unnamed analytical efforts are a gap, not an omission.
    assert g.has("gap-unnamed-efforts")
    charter = g.get(B.CHARTER)
    assert any(lim["mitigation"] == {"$gap": "gap-unnamed-efforts"}
               for lim in charter["limitations"])
    studies = [e for e in g.all("Evidence")
               if e.get("evidenceType") in ("MSStudy", "SoldierTouchpoint")]
    assert len(studies) == 7, sorted(e["id"] for e in studies)


def test_the_december_schedule_places_the_two_trac_items_where_the_readme_says():
    """The four schedule placements in README §7, re-derived from the deck.

    Label column positions on PDF p. 17 (slide footer 19), against that page's own month
    header row. They are approximate — a label on a Gantt row locates a bar, not a start
    date — and they point the other way from this record's identification, which is
    exactly why the README prints them.
    """
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext is not on PATH")
    text = subprocess.run(
        ["pdftotext", "-layout", "-f", "17", "-l", "17", str(REPO / B.SRC_BRIEFING), "-"],
        capture_output=True, text=True, check=True).stdout
    lines = text.split("\n")
    header = next(ln for ln in lines
                  if re.search(r"\bNov\b.*\bDec\b.*\bJan\b.*\bFeb\b", ln))
    order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
             "Nov", "Dec"]
    months, year, prev = [], 2020, None
    for m in re.finditer(r"[A-Z][a-z]{2}", header):
        idx = order.index(m.group())
        if prev is not None and idx < prev:
            year += 1
        prev = idx
        months.append((m.start(), m.group(), year))

    def nearest(label):
        col = min(ln.find(label) for ln in lines if label in ln)
        pos, month, yr = min(months, key=lambda t: abs(t[0] - col))
        return col, f"{month} {yr}"

    assert nearest("TRAC AoA") == (19, "Nov 2020")
    assert nearest("ARIES") == (43, "Feb 2021")
    assert nearest("MBL1") == (55, "Apr 2021")
    assert nearest("TRAC OE") == (83, "Sep 2021")
    assert nearest("HSI 1") == (117, "Feb 2022")
    assert nearest("HSI 2") == (117, "Feb 2022")
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    for row in ("| `TRAC AoA` | 19 | Nov 2020 |", "| `TRAC OE` | 83 | Sep 2021 |",
                "| `MBL1` | 55 | Apr 2021 |", "| `ARIES 1` | 43 | Feb 2021 |"):
        assert row in readme, row


def test_the_weight_claim_cites_the_notice_as_well_as_the_press(demo):
    """I2. The stated reason for citing the press article alone was mechanically false:
    `linchpin-unevidenced` reads the Assumption's own `evidence` field, never the Claim's
    `supportedBy`. Adding the notice changes no state and F6 still fires.
    """
    g = demo["graph"]
    claim = g.get("cl-weight-threshold")
    assert claim["confidence"] == "inferred"
    assert [e["evidence"] for e in claim["supportedBy"]] == ["ev-con-2020-02",
                                                             "ev-breaking-defense"]
    assert g.get("as-poland-bridges")["linchpin"] is True
    assert demo["findings"]["F6"]["objects"] == ["as-poland-bridges"]
    assert "dc" in demo["findings"]["F6"]["sub_episode"]
    # And the state table is the one recorded before the citation was added.
    assert demo["states"]["dc"]["DES-4"] == 1
    assert demo["states"]["dc"]["PRE-1"] == 4


# ---- the record's own integrity ------------------------------------------------------
def test_every_object_validates_and_nothing_dangles(demo):
    g = demo["graph"]
    structural = [f for f in validate(g) if f.severity == "blocking"]
    assert structural == [], [(f.rule, f.objects, f.message) for f in structural]
    assert orphan_gaps(g) == set()


def test_every_transition_history_is_honest(demo):
    for ep_id in demo["episodes"]:
        assert_history_honest(demo["graph"], ep_id)


def test_the_lifecycle_states_are_what_the_record_supports(demo):
    g = demo["graph"]
    # Episodes 1 and 2 stop at MODEL_APPROVED: no Plan, because the public record at
    # those dates is a notice and a slide. Everything from 3 on reaches PLAN_APPROVED.
    def states(ep_id):
        return [t["to"] for t in g.get(ep_id)["transitions"]]

    assert states("ep-omfv-2020-02")[:1] == ["MODEL_APPROVED"]
    assert states("ep-omfv-2020-02-r2")[:1] == ["MODEL_APPROVED"]
    assert "plan" not in g.get("ep-omfv-2020-02")
    assert "plan" not in g.get("ep-omfv-2020-02-r2")
    for ep_id in ("ep-omfv-2020-02-r3", "ep-omfv-2020-02-r4", "ep-omfv-2020-02-r5"):
        assert "PLAN_APPROVED" in states(ep_id)
        # Every episode has its own Plan: `open_refresh` does not carry one forward and
        # `Plan.episode` is a required ref.
        assert g.get(g.get(ep_id)["plan"])["episode"] == ep_id
    for key in ("dc", "fs", "ce"):
        ep_id = B.SUB_EPISODES[key]
        assert states(ep_id) == ["MODEL_APPROVED", "PLAN_APPROVED"]
        assert g.get(ep_id)["lifecycleState"] == "PLAN_APPROVED"
    # The four priors were superseded; episode 5 was not.
    for ep_id in B.MAIN_CHAIN[:-1]:
        assert g.get(ep_id)["lifecycleState"] == "SUPERSEDED"
    assert g.get("ep-omfv-2020-02-r5")["lifecycleState"] == "PLAN_APPROVED"


def test_the_sub_episodes_are_not_in_the_programme_chain(demo):
    """Ruling R5. If they were, episode 5 would be `ep-omfv-2020-02-r4-ce-r5`."""
    g = demo["graph"]
    programme = g.get(B.PROGRAM)
    assert programme["episodes"] == B.MAIN_CHAIN
    for ep_id in B.SUB_EPISODES.values():
        assert ep_id not in programme["episodes"]
        assert "program" not in g.get(ep_id)
        assert g.get(ep_id)["sequence"] == 4
        assert g.get(ep_id)["supersedes"] == "ep-omfv-2020-02-r4"
        assert g.get(ep_id)["refreshedBecause"] == "rt-234-report"


def test_diff_pairing_says_which_diffs_were_paired_from_replacements(demo):
    """`pairing` is `replacements` exactly where a refresh carried a replacements map.

    The brief asked for `pairing == "replacements"` on every diff. Episodes 3 and 4
    replaced nothing — the December characteristics are still the characteristics, and
    the March 2023 report restates them — so their refreshes carry an empty map and
    `diff_episodes` honestly reports `unknown`. Inventing replacements to make the
    string come out would be changing the record to satisfy a test.
    """
    g = demo["graph"]
    for key, d in demo["diffs"].items():
        to_id = key.split("→")[1]
        replacements = g.get(to_id).get("replacements") or {}
        assert d["pairing"] == ("replacements" if replacements else "unknown"), key
        assert d["judgmentsConsistent"] == [], key

    first = demo["diffs"]["ep-omfv-2020-02→ep-omfv-2020-02-r2"]
    assert first["pairing"] == "replacements"
    assert "as-manning-feb" in first["removed"] and "as-manning-dec" in first["added"]
    assert any(c["object"] == "as-manning-feb→as-manning-dec"
               for c in first["changed"])
    # The seven unchanged characteristics appear in neither list: that absence is how
    # the artefact records "retained".
    for oid in ("obj-mobility", "obj-growth", "obj-lethality", "obj-weight",
                "obj-logistics", "obj-transportability", "obj-training"):
        assert oid not in first["added"] and oid not in first["removed"]

    last = demo["diffs"]["ep-omfv-2020-02-r4→ep-omfv-2020-02-r5"]
    assert last["pairing"] == "replacements"
    # The second entry is the bias indicator the kernel computed for `-r4`, which
    # `open_refresh` no longer carries into `-r5`; `-r5` computes and adds its own.
    assert last["removed"] == ["alt-omfv-concept",
                               "risk-bias-ep-omfv-2020-02-r4-selection"]
    assert "risk-bias-ep-omfv-2020-02-r5-selection" in last["added"]
    # `replacements` is 1:1, so the one-to-two split is one replacement plus one addition.
    assert "alt-xm30-gdls" in last["added"] and "alt-xm30-rheinmetall" in last["added"]
    assert g.get("ep-omfv-2020-02-r5")["replacements"] == {
        "alt-omfv-concept": "alt-xm30-gdls"}


def test_the_two_filed_triggers_open_no_episode(demo):
    g = demo["graph"]
    programme = g.get(B.PROGRAM)
    for trigger in ("rt-sigmgmt-correction", "rt-gao-grading"):
        assert trigger in programme["refreshTriggers"]
        assert not any(ep.get("refreshedBecause") == trigger
                       for ep in g.all("DecisionEpisode"))
    assert g.get("rt-sigmgmt-correction")["detectedAt"] == "2022-10-25"
    assert g.get("rt-sigmgmt-correction")["kind"] == "artefact-version-changed"
    assert g.get("rt-sigmgmt-correction")["affected"] == ["obj-survivability-dec"]
    # R10: no such objective exists, and the record does not invent one.
    assert not g.has("obj-signature-management")
    # `RefreshTrigger.affected` is typed to Claims etc., never to episodes.
    assert g.get("rt-gao-grading")["affected"] == [
        "cl-nine-characteristics", "cl-force-structure-improves",
        "cl-concepts-outperform-m2a4"]


def test_affected_episodes_is_reported_raw_and_narrowed(demo):
    affected = demo["affectedByGaoGrading"]
    assert affected["gradedSections"] == sorted(B.SUB_EPISODES.values())
    # Reverse reachability is transitive and the trigger is filed on the programme, so
    # the raw answer is every episode. Recorded, with the reason, not quietly narrowed.
    assert set(affected["episodes"]) == set(demo["episodes"])
    assert "transitive" in affected["note"]


def test_the_award_source_stub_exists_and_asks_for_a_release_call(demo):
    assert STUB.exists()
    text = STUB.read_text(encoding="utf-8")
    assert "NOT CONFIRMED" in text
    assert "army-rdte-r2-fy2025-omfv-xm30-extract.pdf" in text
    # I5: the exhibit prints the month, not the day. Both the stub and the README say so
    # rather than carrying 26 June as if it were sourced.
    assert "Month sourced, day NOT sourced" in text
    assert "working date" in text
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    assert "working date" in readme
    assert "`Jun 2023`" in readme
    # The unselected vendors are named nowhere in the record.
    g = demo["graph"]
    exclusion = g.get("ex-phase2-concepts-not-selected")
    assert "id" not in exclusion["target"]
    assert exclusion["reasonType"] == "other"


def test_the_counterfactual_never_touches_the_main_store(demo):
    """The repair lives in its own store, and every object it writes says so."""
    g = demo["graph"]
    for oid in ("cf-ev-vva-accreditation", "cf-ev-ce-metrics-package",
                "cf-drs-ce-metrics"):
        assert not g.has(oid)
    assert g.get("ev-ce-metrics")["reviewStatus"] == "draft"
    assert g.get("vva-trac")["accreditationDecision"]["basis"] == "interview"

    cf = Graph.load(Path(demo["outDir"]) / "counterfactual" / "graph")
    for oid in ("cf-ev-vva-accreditation", "cf-ev-ce-metrics-package",
                "cf-drs-ce-metrics", "ev-ce-metrics", "vva-aries", "vva-trac"):
        obj = cf.get(oid)
        assert obj["confidence"] == "inferred", oid
        assert obj["ingestionProvenance"]["extractor"] == "counterfactual", oid
        assert obj["ingestionProvenance"]["locator"] == "counterfactual", oid
    # The value is still withheld. That is the point.
    assert cf.get("ev-ce-metrics")["classification"]["level"] == "S"
    assert cf.get("ev-ce-metrics")["reviewStatus"] == "reviewed"
    for vid in ("vva-aries", "vva-trac"):
        acc = cf.get(vid)["accreditationDecision"]
        assert acc["basis"] == "document" and acc["document"] == "cf-ev-vva-accreditation"


def test_the_saved_store_loads_and_still_validates(demo):
    loaded = Graph.load(Path(demo["outDir"]) / "graph")
    assert [f for f in validate(loaded) if f.severity == "blocking"] == []
    assert loaded.snapshot_hash() == demo["graph"].snapshot_hash()


# ---- determinism and hygiene ---------------------------------------------------------
def test_two_runs_are_byte_identical(tmp_path):
    a, b = run(tmp_path / "a"), run(tmp_path / "b")
    left, right = tmp_path / "a", tmp_path / "b"
    names = sorted(p.relative_to(left) for p in left.rglob("*") if p.is_file())
    assert names == sorted(p.relative_to(right) for p in right.rglob("*") if p.is_file())
    differing = [str(rel) for rel in names
                 if (left / rel).read_bytes() != (right / rel).read_bytes()]
    assert differing == [], differing
    assert a["packages"] == b["packages"]
    assert a["grid_match"] == b["grid_match"] == 9


@pytest.mark.parametrize("committed", [False, True])
def test_no_absolute_paths_in_any_output(demo, committed):
    """A package that named the machine it was built on could not be byte-identical
    anywhere else, and would leak a home directory into a deliverable."""
    out = OUT if committed else Path(demo["outDir"])
    if committed and not out.exists():
        pytest.skip("out/ has not been generated yet")
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
    assert checked > 50, f"expected the whole store under {out}, saw {checked} files"


def test_committed_scoring_output_is_current(tmp_path):
    """**Every** committed file under `out/` matches a fresh run — byte for byte.

    Packages and export files included. They were left out while `render.py` was in
    flight, on the ground that a demonstration should not fail because a heading moved;
    the cost of that was 63 committed files nothing checked. A stale rendered package in
    a deliverable is worse than a test that fails when the renderer changes, and the fix
    for the latter is one command.
    """
    if not (OUT / RESULTS_FILE).exists():
        pytest.skip("out/ has not been generated yet")
    fresh = tmp_path / "fresh"
    run(fresh)
    committed = sorted(p.relative_to(OUT) for p in OUT.rglob("*") if p.is_file())
    produced = sorted(p.relative_to(fresh) for p in fresh.rglob("*") if p.is_file())
    hint = " — re-run: uv run python -m demos.b_omfv_2019_2023.run"
    assert committed == produced, (
        f"the committed file list differs from a fresh run's{hint}")
    stale = [str(rel) for rel in committed
             if (OUT / rel).read_bytes() != (fresh / rel).read_bytes()]
    assert stale == [], f"{len(stale)} stale file(s): {stale[:10]}{hint}"
    # The scoring files are the ones a reviewer will look at first, so name them.
    for name in SCORING_FILES:
        assert (OUT / name).read_bytes() == (fresh / name).read_bytes(), (
            f"{name} is stale{hint}")
    assert len(committed) > 400, len(committed)


def test_run_writes_only_into_its_out_dir(tmp_path):
    target = tmp_path / "nested" / "out"
    run(target)
    assert sorted(p.name for p in target.iterdir()) == sorted([
        "affected_by_gao.json", "ce-after.json", "ce-before.json", "counterfactual",
        "diffs.json", "findings_matrix.json", "grid.json", "graph", "packages",
        "repair.json", "report.md", "results.json"])
    shutil.rmtree(target)


# ---- page attribution: the fixture's quotations really are on the pages it cites -----
def _normalise(s: str) -> str:
    """Alphanumerics only, lower-cased.

    The comparison has to survive typographic quotes and dashes in the fixture against
    `pdftotext`'s output, de-hyphenation across line breaks, and the two-column layouts
    in the GAO report. Stripping everything else makes it about the words.
    """
    s = unicodedata.normalize("NFKC", s)
    for a, b in (("’", "'"), ("“", '"'), ("”", '"'),
                 ("—", "-"), ("–", "-"), ("‘", "'")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _pdf_pages(relative: str) -> list[list[str]] | None:
    """The source's text layer, one list of normalised extractions per PDF page.

    Two extractions, because neither alone is enough. `-layout` preserves the two-column
    page and the Q&A table's columns but interleaves GAO's marginal section headings —
    and the Q&A's rationale column — into the body text, which cuts sentences in half.
    Plain extraction reads in flow order and joins them again but loses the tables. A
    quotation counts as present on a page if either extraction finds it there.
    """
    if shutil.which("pdftotext") is None:
        return None
    pdf = REPO / relative
    if not pdf.exists():
        return None
    extractions = []
    for flags in ([], ["-layout"]):
        text = subprocess.run(["pdftotext", *flags, str(pdf), "-"],
                              capture_output=True, text=True, check=True).stdout
        extractions.append([_normalise(page) for page in text.split("\f")])
    return [list(pair) for pair in zip(*extractions, strict=False)]


def _on_page(pages, index: int, quote: str) -> bool:
    """Whether `quote` appears on the page, in either extraction of it."""
    return any(_normalise(quote) in variant for variant in pages[index])


def _require_pdftotext(pages) -> None:
    if pages is None:
        pytest.skip(
            "pdftotext is not on PATH (or the source PDF is missing), so the page "
            "attributions cannot be checked against the source. Install poppler-utils "
            "(`brew install poppler`) and re-run; this test is the only thing standing "
            "between a cited page number and a wrong one.")


def test_gao_printed_page_is_pdf_page_minus_three():
    pages = _pdf_pages(B.SRC_GAO)
    _require_pdftotext(pages)
    for printed in (8, 9, 10, 11, 12, 13, 14, 17):
        assert _on_page(pages, printed + 3 - 1, f"Page {printed} GAO-23-106549"), printed


@pytest.mark.parametrize("printed,quote", [
    (8, "the Army conducted four vendor feedback events"),
    (8, "seven previously conducted analytical studies"),
    (9, "We did not independently assess or verify the analytical efforts supporting "
        "the report."),
    (9, "the report assumes that bridges in Poland are representative of those across "
        "Eastern Europe, but the Army does not identify the data and methods used to "
        "support this assumption"),
    (9, "the Army report did not clearly describe the methodology of these efforts; the "
        "steps it took to ensure data reliability; or the verification, validation, and "
        "accreditation of the models and simulations it used"),
    (10, "The Army's report did not clearly define, however, force structure or "
         "operational concepts."),
    (10, "Army officials told us that the models and simulations informing the 11 "
         "analytical efforts had gone through the Army's standard verification, "
         "validation, and accreditation process to ensure their reliability."),
    (11, "the July 2021 soldier touchpoint conducted by the Maneuver Battle Lab within "
         "the Maneuver Capabilities Development and Integration Directorate"),
    (11, "a September 2021 study conducted by the Army's Research and Analysis Center"),
    (11, "a second TRAC study expanded on the first, and added another scenario with "
         "different terrain and details from a vendor's concepts"),
    (11, "observations from this study were not included due to security concerns"),
    (12, "the first TRAC analysis found that a different force structure improved "
         "survivability and lethality, and the Maneuver Battle Lab analysis drew "
         "similar conclusions"),
    (12, "these analyses were not designed to draw conclusions on force structure "
         "alternatives"),
    (13, "a 2018 Bradley size, weight, power, and cooling growth study"),
    (13, "a study to support the program's market research in 2020"),
    (13, "a study to support concept design in 2021"),
    (13, "compared three government concepts for the OMFV with a modernized version of "
         "the M2A4 Bradley"),
    (14, "they did not include these metrics in the report due to security concerns"),
    (14, "engines with varying power or variance in the number of infantry soldiers it "
         "can transport"),
    (14, "The Army told us that they had no comments on the draft report."),
    (17, "we drew conclusions that the report was generally objective when available "
         "information presented in the report was consistent with our definition of "
         "objectivity but was missing information that would have addressed the "
         "generally accepted research standards"),
])
def test_gao_quotations_are_on_the_printed_pages_the_fixture_cites(printed, quote):
    pages = _pdf_pages(B.SRC_GAO)
    _require_pdftotext(pages)
    assert _on_page(pages, printed + 3 - 1, quote), (printed, quote[:60])


@pytest.mark.parametrize("pdf_page,footer,quote", [
    (5, 6, "The OMFV shall be survivable against modern direct fire, indirect fire, and "
           "blast threats."),
    (5, 6, "A platoon of OMFVs will transport 30 Soldiers that dismount from the "
           "vehicles."),
    (5, 6, "Each OMFV vehicle will be crewed by no more than two Soldiers who will be "
           "positioned in the hull."),
    (11, 13, "Generated using threat analysis, market research, and the ABCT operational "
             "concept."),
    (17, 19, "TRAC OE"),
    (17, 19, "MBL1"),
    (18, 20, "TRAC OE analyzes how well the concept design performs in a combat scenario"),
    (18, 20, "Highlights sensitivities between functional requirements in real time to "
             "inform the program."),
])
def test_december_2020_slide_footers_are_off_by_the_amount_the_locators_say(
        pdf_page, footer, quote):
    """Every locator into this deck reads `PDF p. N (slide footer M)`, never a bare
    slide number, because the two do not agree."""
    pages = _pdf_pages(B.SRC_BRIEFING)
    _require_pdftotext(pages)
    assert _on_page(pages, pdf_page - 1, quote), (pdf_page, quote[:50])
    # The footer the slide itself prints, which is not the PDF page index.
    assert any(variant.endswith(str(footer)) for variant in pages[pdf_page - 1]), \
        (pdf_page, footer)


def test_the_priority_order_is_the_april_narratives_not_the_february_notices():
    pages = _pdf_pages(B.SRC_NARRATIVE)
    _require_pdftotext(pages)
    assert _on_page(pages, 5, (
        "The OMFV Characteristics are prioritized in the following order: 1. "
        "Survivability 2. Mobility 3. Growth 4. Lethality 5. Weight 6. Logistics 7. "
        "Transportability 8. Manning 9. Training")), "April narrative p. 6, section 3.2"
    notice = (REPO / B.SRC_CON).read_text(encoding="utf-8")
    assert "prioritized" not in notice.lower(), (
        "the February notice states no priority order; if it now does, every Objective's "
        "locator needs re-reading")


def test_the_signature_management_q_and_a_is_a_correction_dated_october_2022():
    pages = _pdf_pages(B.SRC_QA)
    _require_pdftotext(pages)
    assert _on_page(pages, 4, (
        "Is it an error that the signature management requirements are being shown as "
        "P3 in column F?"))
    assert _on_page(pages, 4, "The latest rev of the requirements has these at P2.")
    assert _on_page(pages, 4, (
        "Attachment 0010 will be corrected to reflect signature management requirement "
        "P2 in column F."))


def test_the_june_2023_award_and_both_performers_are_in_a_committed_source():
    """Episode 5's facts come from a committed budget exhibit, not from the stub."""
    pages = _pdf_pages(B.SRC_R2_FY2025)
    _require_pdftotext(pages)
    # extract PDF p. 74. The performing-activity cell wraps across five lines with the
    # cost columns interleaved, so the two names are checked separately.
    assert _on_page(pages, 73, "General Dynamics")
    assert _on_page(pages, 73, "Rheinmetall")
    assert _on_page(pages, 73, "Jun 2023")
    assert _on_page(pages, 73, "Volume 3d - 201"), "the source-volume page in the footer"
