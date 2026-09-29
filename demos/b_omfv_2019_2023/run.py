"""Run Demonstration B end to end: five episodes, three sections, the F1-F9 matrix.

    uv run python -m demos.b_omfv_2019_2023.run [out_dir]

Nothing here reads a clock, a network or an environment variable. Every `now` and the
seed are constants, so two runs produce byte-identical output.

The order below is the record's own order:

* each episode's model is approved (G1) before anything is scored, and its plan approved
  (G2) where the record has a plan at all — episodes 1 and 2 do not, because in February
  and December 2020 the public record is a requirements notice and a briefing slide;
* every episode is driven at least to `MODEL_APPROVED` before the next refresh opens,
  because `open_refresh` refuses a `DRAFT` prior;
* readiness is computed for each episode *at its own date*, before the next refresh, so
  an episode is scored against the record as it stood when it was current;
* the three March 2023 sub-episodes are scored twice — once under `gao-23-106549` for the
  grid, once under `published-21-plus-vva` for EXE-14, which is the only question that
  can express GAO's F5;
* the counterfactual repair runs against a **separate graph copy** and never touches the
  main store.

Two things this file computes that the kernel does not, and both are labelled as ours.

**Attribution.** Kernel findings are graph-global: `validate()` runs over the whole store
and `readiness_report` keeps any finding that names an object the episode can reach.
Because a `DecisionEpisode` references its `DecisionProgram`, which references every other
episode, "reachable" is very nearly "everything". So the matrix decides for itself which
episode a finding belongs to, from the episode's own reference lists — see
`_attributable`. That is this demonstration's reading, not the kernel's, and the run
measures the difference between the two scopings rather than asserting there is none
(`cross_fires_suppressed_by_our_attribution` in `out/findings_matrix.json`).

**The grid comparison.** GAO publishes nine section-by-dimension verdicts **in prose** —
three section headings, each followed by an Objectivity / Validity / Reliability
paragraph, printed pp. 8-14 — and no per-question labels. Arranging those nine as a 3x3
grid is ours; the verdicts in it are GAO's, and they are what is compared. The
per-question states underneath them are ours and are reported, never presented as GAO's.

**And the run says what the nine cells rest on.** Two scorer decisions taken during this
same plan — ruling R2's narrative-only PRE-3/PRE-4 clauses and `pol-omfv.aggregationK =
21` — are load-bearing on objectivity. `_grid_counterfactuals` re-scores the record with
each of them withdrawn, on a throwaway copy of the store, and the measured result goes
into `out/grid.json` and `out/report.md`. Without that, "9 of 9, measured" would read as
the output of an untouched scorer.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

from demos.b_omfv_2019_2023.build import (
    CHARTER,
    EPISODE_1,
    EPISODE_2,
    EPISODE_3,
    EPISODE_4,
    EPISODE_5,
    MAIN_CHAIN,
    NOW1,
    NOW2,
    NOW3,
    NOW4,
    NOW5,
    POLICY,
    PROGRAM,
    SECTION_TITLES,
    SUB_EPISODES,
    H,
    build,
    build_sub_episodes,
    file_gao_grading_trigger,
    file_signature_management_correction,
    repair_ce,
    revise_r2,
    revise_r3,
    revise_r4,
    revise_r5,
    trigger_r3,
    trigger_r4,
    trigger_r5,
)
from docket.kernel import standards
from docket.kernel.lifecycle import transition
from docket.kernel.readiness import readiness_report
from docket.kernel.refresh import affected_episodes, diff_episodes, open_refresh, supersede
from docket.kernel.scope import check_scope
from docket.kernel.validate import validate
from docket.store import Graph

SEED = 20230627
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
RESULTS_FILE = "results.json"
GROUND_TRUTH = HERE / "gao_23_106549_ground_truth.yaml"

GRID_TAILORING = "gao-23-106549"
VVA_TAILORING = "published-21-plus-vva"

# The episode's own reference lists. Attribution walks these and stops at any other
# episode or at the programme, which is what keeps "this episode's findings" from
# meaning "every finding in the store".
REF_LISTS = ("objectives", "alternatives", "groundRules", "constraints", "assumptions",
             "evidenceRegister", "scenarios", "claims", "risks", "biasChecks",
             "mandateElements", "observations", "weightSets", "models", "runs",
             "flipAnalyses")


def _own_ids(g: Graph, ep: dict) -> set[str]:
    """The episode's own model: its reference lists, its charter and its plan, plus
    everything those reach — stopping at any `DecisionProgram` or other
    `DecisionEpisode`.

    Forward reachability alone will not do. `DecisionEpisode.program` points at the
    programme, the programme lists every episode, and so every episode reaches every
    other episode's evidence. Stopping the walk at those two types is what makes
    "belongs to this episode" mean something.
    """
    seen = {ep["id"]}
    frontier = [i for k in REF_LISTS for i in (ep.get(k) or []) if isinstance(i, str)]
    frontier += [x for x in (ep.get("charter"), ep.get("plan")) if isinstance(x, str)]
    while frontier:
        cur = frontier.pop()
        if cur in seen or not g.has(cur):
            continue
        obj = g.get(cur)
        if obj["type"] in ("DecisionProgram", "DecisionEpisode"):
            continue
        seen.add(cur)
        frontier.extend(g.refs_from(cur))
    return seen


def _reach_ids(g: Graph, ep: dict) -> set[str]:
    """The kernel's own scoping: the episode plus everything reachable forward from it.

    This is exactly what `readiness._counts_for_episode` keeps a finding for. It is here
    only so the matrix can *measure* the difference between the kernel's scoping and
    ours, rather than assert there is none — see `cross_fires_suppressed_by_our_attribution`.
    """
    return {ep["id"]} | g.reachable_from(ep["id"], reverse=False)


def _attributable(g: Graph, ep: dict, finding) -> bool:
    """Whether `finding` is this episode's own. Ours, not the kernel's.

    Two cases, in order:

    1. A finding that names a `DecisionEpisode` belongs to the episode it names —
       `silent-omission`, `bias-check-missing` and `inclusion-reason-missing` are all
       shaped that way.
    2. Everything else belongs to the episode whose own model contains every object the
       finding names.

    There used to be a third case. `inclusion-reason-missing` named only the evidence
    object, so this function had to work out for itself which episode's claim had done
    the citing. The kernel rule now names the episode and the claim as well
    (`policy_rules.inclusion_reason_missing`), and case 1 covers it.
    """
    named_episodes = [o for o in finding.objects
                      if g.has(o) and g.get(o)["type"] == "DecisionEpisode"]
    if named_episodes:
        return ep["id"] in named_episodes
    if not finding.objects:
        return False
    return set(finding.objects) <= _own_ids(g, ep)


def _episode_findings(g: Graph, episode_id: str, policy: dict, *,
                      scoping: str = "ours") -> list:
    """Every finding this episode owns, from the validator and the scope checker.

    `scoping="ours"` uses `_attributable`. `scoping="kernel-reach"` uses the rule
    `readiness_report` itself applies — keep a finding if it names anything the episode
    can reach. The second exists so the matrix can measure what the first suppresses
    rather than assert it suppresses nothing.
    """
    ep = g.get(episode_id)
    everything = validate(g, policy) + check_scope(g, episode_id)
    if scoping == "kernel-reach":
        reach = _reach_ids(g, ep)

        def keep(f):
            return bool(set(f.objects) & reach)
    else:
        def keep(f):
            return _attributable(g, ep, f)
    return [f for f in sorted(set(everything)) if keep(f)]


def _states(g: Graph, assessment_id: str) -> dict[str, int | None]:
    return {r["questionId"]: r["state"]
            for r in g.get(assessment_id)["ratings"] if r["applicable"]}


def _build_the_record(g: Graph) -> dict[str, dict]:
    """Drive the whole chain, scoring each episode at its own date.

    Returns `{episode_id: readiness report}` for the five main-chain episodes.
    """
    readiness: dict[str, dict] = {}

    # Episode 1, February 2020. No Plan: the public record at this date is a
    # requirements notice, not an analysis plan. `MODEL_APPROVED` is all it can honestly
    # reach, and all `open_refresh` needs.
    transition(g, EPISODE_1, "MODEL_APPROVED", H, now=NOW1)
    readiness[EPISODE_1] = readiness_report(g, EPISODE_1, seed=SEED, now=NOW1)

    # Episode 2, December 2020. Three replacements go through the refresh engine.
    open_refresh(g, PROGRAM, "rt-con-update-2020-12", actor=H, now=NOW2,
                 replacements={"as-manning-feb": "as-manning-dec",
                               "obj-survivability": "obj-survivability-dec",
                               "obj-manning": "obj-manning-dec"})
    revise_r2(g)
    transition(g, EPISODE_2, "MODEL_APPROVED", H, now=NOW2)
    readiness[EPISODE_2] = readiness_report(g, EPISODE_2, seed=SEED, now=NOW2)

    # Episode 3, September 2021. Nothing is replaced; the evidence under the
    # characteristics changes, not the characteristics.
    trigger_r3(g)
    open_refresh(g, PROGRAM, "rt-phase2-efforts", actor=H, now=NOW3, replacements={})
    revise_r3(g)
    transition(g, EPISODE_3, "MODEL_APPROVED", H, now=NOW3)
    transition(g, EPISODE_3, "PLAN_APPROVED", H, now=NOW3)
    readiness[EPISODE_3] = readiness_report(g, EPISODE_3, seed=SEED, now=NOW3)

    # October 2022, before the report: the attachment correction, filed, opening nothing.
    file_signature_management_correction(g)

    # Episode 4, March 2023 — the Section 234 report.
    trigger_r4(g)
    open_refresh(g, PROGRAM, "rt-234-report", actor=H, now=NOW4, replacements={})
    revise_r4(g)
    transition(g, EPISODE_4, "MODEL_APPROVED", H, now=NOW4)
    transition(g, EPISODE_4, "PLAN_APPROVED", H, now=NOW4)
    readiness[EPISODE_4] = readiness_report(g, EPISODE_4, seed=SEED, now=NOW4)
    return readiness


def _score_sections(g: Graph) -> tuple[dict, dict, dict]:
    """Build the three sub-episodes, drive both gates, and score each one twice.

    `published-21-plus-vva` first, `gao-23-106549` last, so the readiness report the
    episode ends up carrying is the one the grid is read from.
    """
    build_sub_episodes(g)
    grid_reports, vva_states, grid_states = {}, {}, {}
    for key, ep_id in SUB_EPISODES.items():
        transition(g, ep_id, "MODEL_APPROVED", H, now=NOW4)
        transition(g, ep_id, "PLAN_APPROVED", H, now=NOW4)
        vva = readiness_report(g, ep_id, tailoring=VVA_TAILORING, seed=SEED, now=NOW4)
        vva_states[key] = _states(g, vva["standardsAssessment"])
        rr = readiness_report(g, ep_id, tailoring=GRID_TAILORING, seed=SEED, now=NOW4)
        grid_reports[key] = rr
        grid_states[key] = _states(g, rr["standardsAssessment"])
    return grid_reports, grid_states, vva_states


def _grid(g: Graph, grid_reports: dict, truth: dict) -> tuple[dict, int]:
    """The nine verdicts as measured, in our 3x3 arrangement, and how many match GAO."""
    verdict_map = truth["ours"]["verdict_map"]
    measured, matched = {}, 0
    for key, rr in grid_reports.items():
        verdicts = g.get(rr["standardsAssessment"])["dimensionVerdicts"]
        row = {d: verdicts[d]["verdict"] for d in ("objectivity", "validity",
                                                   "reliability")}
        measured[key] = row
        for dimension, published in truth["transcribed"]["grid"][key].items():
            if row[dimension] == verdict_map[published]:
                matched += 1
    return measured, matched


# The values of `pol-omfv.aggregationK` the run re-scores at, so the report can print
# what the grid would have been at each. 1 is the kernel default; 21 is the policy's.
K_PROBE = (1, 3, 4, 5, 21)

# The two clauses ruling R2 added to `src/docket/standard/rules.yaml` during this plan
# (commit 5ca1686), as `(question, when)` pairs. The counterfactual below drops exactly
# these and re-scores.
R2_CLAUSES = (("PRE-3", "claims_exist_no_silence"), ("PRE-4", "claims_exist"))

R2_DECISION = ("docs/decisions/"
               "2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md")
K_DECISION = "docs/decisions/2026-09-05-aggregation-k-is-a-policy-parameter.md"


def _pristine_copy(g: Graph, out_dir: Path) -> Graph:
    """A save-and-load round trip through a scratch directory, removed again at once.

    The counterfactual probes below re-score the three sections, and every
    `readiness_report` call writes a `ReadinessReport` and a `StandardsAssessment` into
    the store it is given. Running them against the published graph would put the
    probes' own artefacts into `out/graph`, so they run against a copy that is never
    saved and never returned.
    """
    scratch = out_dir / ".probe"
    shutil.rmtree(scratch, ignore_errors=True)
    g.save(scratch)
    copy = Graph.load(scratch)
    shutil.rmtree(scratch)
    return copy


def _score_grid(g: Graph, truth: dict,
                *, k: int | None = None) -> tuple[dict, int, dict]:
    """Re-score the three sections and read the grid off them, at an explicit `k`."""
    verdict_map = truth["ours"]["verdict_map"]
    measured, matched, states = {}, 0, {}
    for key, ep_id in SUB_EPISODES.items():
        rr = readiness_report(g, ep_id, tailoring=GRID_TAILORING, seed=SEED, now=NOW4,
                              k=k)
        verdicts = g.get(rr["standardsAssessment"])["dimensionVerdicts"]
        row = {d: verdicts[d]["verdict"] for d in ("objectivity", "validity",
                                                   "reliability")}
        measured[key] = row
        states[key] = _states(g, rr["standardsAssessment"])
        for dimension, published in truth["transcribed"]["grid"][key].items():
            if row[dimension] == verdict_map[published]:
                matched += 1
    return measured, matched, states


def _grid_counterfactuals(g: Graph, truth: dict) -> dict:
    """What the grid measures without each of the two scorer decisions this plan took.

    Ruling R2 added a state-2 clause to PRE-3 and PRE-4 for a record that presents claims
    but carries no evaluation run; ruling R3 set `pol-omfv.aggregationK = 21`. Both were
    taken during plan 05, both are on the human sign-off list, and 9 of 9 is not
    reachable without both. Printing what the grid measures with each withdrawn is the
    only thing that stops "9 of 9, measured" reading as the output of an untouched
    scorer.

    The R2 probe patches `standards.load_rules` for the duration of three scoring calls
    and restores it in a `finally`. That is a test-shaped move inside a demonstration
    runner, and it is here deliberately: the alternative is a number in prose that
    nothing re-checks.
    """
    rows = []
    for k in K_PROBE:
        grid, matched, _ = _score_grid(g, truth, k=k)
        rows.append({"k": k, "grid_match": matched,
                     "objectivity": {key: grid[key]["objectivity"] for key in grid}})

    original = standards.load_rules

    def without_r2() -> list[dict]:
        rules = original()
        for rule in rules:
            question = rule.get("question")
            rule["clauses"] = [c for c in rule.get("clauses", [])
                               if (question, c.get("when")) not in R2_CLAUSES]
        return rules

    standards.load_rules = without_r2
    try:
        grid, matched, states = _score_grid(g, truth)
    finally:
        standards.load_rules = original

    return {
        "k": rows,
        "k_decision": K_DECISION,
        "r2_decision": R2_DECISION,
        "r2_clauses_withdrawn": {
            "clauses": [f"{q}: {when}" for q, when in R2_CLAUSES],
            "grid_match": matched,
            "grid": grid,
            "objectivity": {key: grid[key]["objectivity"] for key in grid},
            "pre_3": {key: states[key].get("PRE-3") for key in states},
            "pre_4": {key: states[key].get("PRE-4") for key in states},
        },
        "note": (
            "Measured on every run, on a throwaway copy of the store. Only OBJECTIVITY "
            "moves: validity and reliability read `insufficient_to_conclude` from "
            "PRE-1 = 4 and EXE-5 = 4, both of which come from GAO's F8 (every cited "
            "evidence item's `reliabilitySteps` is the `gap-reliability-steps` object). "
            "Six of the nine cells are immovable under either counterfactual."),
    }


def _sections_firing(g: Graph, section_findings: dict, rule: str,
                     hints: list[str]) -> tuple[list[str], list[str]]:
    """The sections a rule fires on, and the object ids it named there."""
    hit, objects = [], set()
    for key in SUB_EPISODES:
        matched = [f for f in section_findings[key]
                   if f.rule == rule and (not hints or set(f.objects) & set(hints))]
        if matched:
            hit.append(key)
            objects |= {o for f in matched for o in f.objects}
    return hit, sorted(objects)


def _findings_matrix(g: Graph, section_findings: dict, kernel_reach_findings: dict,
                     grid_states: dict, vva_states: dict, main_findings: dict,
                     truth: dict, ce_selection_risks: list[str]) -> dict:
    """F1-F9, each measured on the sub-episode GAO attributed it to.

    "Detected somewhere in the graph" is not the claim. For each finding the matrix asks
    whether the named mechanism fires on **every** section GAO attributed it to, and it
    records separately every section it fires on that GAO did not.

    Two of the nine — F7 and F8 — are detected by a **rating**, not by a rule: EXE-8 and
    EXE-5 reaching state 4. The ground-truth file says so under `ours.findings`, and
    `detected_by` in each row says which kind of mechanism carried it.
    """
    matrix: dict[str, dict] = {}
    cross_fires: dict[str, list[str]] = {}
    suppressed: dict[str, list[str]] = {}
    gao = truth["transcribed"]["findings"]

    for fid, spec in sorted(truth["ours"]["findings"].items()):
        published = gao[fid]
        attributed = list(published["attributed_to"])
        hints = list(spec["object_hint"])
        rating = spec.get("rating")
        if rating is not None:
            question, want = rating["question"], rating["state"]
            fired = [k for k in SUB_EPISODES if grid_states[k].get(question) == want]
            by = [f"{question} state {want}"]
            objects = hints
            mechanism, detected_by = f"{question} state {want}", "rating"
        else:
            mechanism, detected_by = spec["rule"], "rule"
            fired, objects = _sections_firing(g, section_findings, mechanism, hints)
            by = [mechanism]
            if fid == "F1":
                # EXE-3's half of F1: the rating the reused MSStudy drives.
                by.append(f"EXE-3 state {grid_states['fs'].get('EXE-3')} via "
                          "model_evidence_reuse_past_purpose (ev-trac-aoa)")
            if fid == "F5":
                by.append("EXE-14 state "
                          f"{vva_states['dc'].get('EXE-14')} under {VVA_TAILORING}")
            if fid == "F3":
                by.append("Risk kind bias-selection "
                          f"({', '.join(ce_selection_risks)})")
            # What the kernel's own scoping would have reported and our attribution rule
            # does not. Measured, not assumed: the cross-fire table above is the list
            # after one correction of ours, and this is the size of that correction.
            by_reach, _ = _sections_firing(g, kernel_reach_findings, mechanism, hints)
            hidden = [k for k in by_reach if k not in fired]
            if hidden:
                suppressed[mechanism] = hidden
        extra = [k for k in fired if k not in attributed]
        if extra:
            cross_fires[mechanism] = extra
        matrix[fid] = {
            "detected": all(k in fired for k in attributed),
            "detected_by": detected_by,
            "by": by,
            "objects": objects,
            "sub_episode": sorted(fired),
            "attributed_to": attributed,
            "page": published["page"],
            "cross_fired_on": extra,
        }

    matrix["cross_fires"] = cross_fires
    matrix["cross_fires_suppressed_by_our_attribution"] = suppressed
    matrix["cross_fires_suppressed_by_our_attribution_note"] = (
        "Sections on which the kernel's own scoping would report a mechanism and our "
        "attribution rule does not — measured on every run, not asserted. "
        "`readiness._counts_for_episode` keeps a finding if it names ANYTHING the "
        "episode can reach, so on `inclusion-reason-missing` it keeps the "
        "combat-effectiveness finding for `dc` and `fs` too: all three sections share one "
        "evidence register and the three studies sit in it. Our rule reads the episode "
        "the finding names — `policy_rules.inclusion_reason_missing` now names the "
        "episode and the claim as well as the evidence, so `_attributable` needs no "
        "special case for it — and only the section whose claim did the citing owns it. "
        "The cross-fire table above is therefore the list after this one correction of "
        "ours, and this key is the size of the correction.")
    matrix["earlier_episode_silent_omissions"] = {
        ep_id: len([f for f in findings if f.rule == "silent-omission"])
        for ep_id, findings in main_findings.items()
    }
    matrix["earlier_episode_silent_omissions_reason"] = (
        truth["ours"]["expected_cross_fires"]["earlier_episodes"].strip())
    return matrix


def _counterfactual(g: Graph, out_dir: Path, grid_row_before: dict) -> dict:
    """Apply the repair to a separate copy of the store and re-score `-ce`.

    The copy is a real save-and-load round trip, so the repaired graph shares no object
    with the main one and the main one cannot be reached from here at all.

    The repair is re-scored **twice**: once under `published-21-plus-vva`, which is the
    only tailoring that carries EXE-14 and therefore the only one that can show the VV&A
    half of the repair, and once under the grid tailoring, because the repair moves
    EXE-5 from 4 to 2 and that flips GAO's *reliability* verdict on this section. The
    second reading is not a side effect worth burying: one described reliability step on
    one dataset is enough to move a GAO cell, which is a stronger result than "a pointer
    makes a withheld dataset locatable" and a much larger claim than the README used to
    make.
    """
    ce = SUB_EPISODES["ce"]
    cf_dir = out_dir / "counterfactual"
    g.save(cf_dir / "graph")
    cf = Graph.load(cf_dir / "graph")

    def _scope_rules() -> dict[str, list[str]]:
        return {f.rule: sorted(f.objects) for f in check_scope(cf, ce)
                if "ev-ce-metrics" in f.objects}

    def _score(tailoring: str) -> tuple[dict, dict]:
        rr = readiness_report(cf, ce, tailoring=tailoring, seed=SEED,
                              now="2026-09-06T00:00:00Z")
        sa = cf.get(rr["standardsAssessment"])
        return ({r["questionId"]: r["state"] for r in sa["ratings"] if r["applicable"]},
                {d: v["verdict"] for d, v in sa["dimensionVerdicts"].items()})

    before_rules = _scope_rules()
    before_states, _ = _score(VVA_TAILORING)

    repair_ce(cf)

    after_rules = _scope_rules()
    after_states, _ = _score(VVA_TAILORING)
    after_grid_states, after_grid_row = _score(GRID_TAILORING)
    cf.save(cf_dir / "graph")

    before = "NotAssessableAtLevel" if "NotAssessableAtLevel" in before_rules else None
    after = ("assessable-with-classified-value"
             if "assessable-with-classified-value" in after_rules else None)
    repair = {
        "before": before,
        "after": after,
        "exe14_before": before_states.get("EXE-14"),
        "exe14_after": after_states.get("EXE-14"),
        # The third thing the repair changes. `cf-drs-ce-metrics` gives `ev-ce-metrics` a
        # content `reliabilitySteps`, which is exactly the F8 silence GAO found, so EXE-5
        # rises from 4 to 2 — on this one dataset, not on the record as a whole.
        "exe5_before": before_states.get("EXE-5"),
        "exe5_after": after_states.get("EXE-5"),
        "ce_row_before": dict(grid_row_before),
        "ce_row_after": after_grid_row,
        "exe5_after_under_grid_tailoring": after_grid_states.get("EXE-5"),
        "classification_level": cf.get("ev-ce-metrics")["classification"]["level"],
        "note": ("A counterfactual. It shows what the record would have to contain, not "
                 "anything about what the Army did. The classification level stays S: "
                 "the value is still withheld, and that is the point."),
        "reliability_note": (
            "Re-scored under the grid tailoring, the repair also moves EXE-5 from 4 to 2 "
            "and with it GAO's reliability verdict on the combat-effectiveness section, "
            "from `insufficient_to_conclude` to `generally_reliable`. That is the whole "
            "of it: one described reliability step on one dataset. Validity does not "
            "move, because PRE-1 still reads 4 — every other cited evidence item's "
            "`reliabilitySteps` is still the `gap-reliability-steps` object, which is "
            "GAO's F8 stated once."),
    }
    (out_dir / "ce-before.json").write_text(
        json.dumps({"scopeFindings": before_rules, "states": before_states,
                    "tailoring": VVA_TAILORING,
                    "gridTailoringRow": dict(grid_row_before)},
                   indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "ce-after.json").write_text(
        json.dumps({"scopeFindings": after_rules, "states": after_states,
                    "tailoring": VVA_TAILORING,
                    "gridTailoringStates": after_grid_states,
                    "gridTailoringRow": after_grid_row},
                   indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "repair.json").write_text(
        json.dumps(repair, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")
    return repair


def _report(results: dict, truth: dict) -> str:
    """A short human-readable summary of what the run measured."""
    counterfactuals = results["grid_counterfactuals"]
    repair = results["repair"]
    lines = [
        "# Demonstration B — OMFV requirements programme, 2020-2023",
        "",
        "Measured by `demos/b_omfv_2019_2023/run.py`. Every number here came out of a "
        "run; none was chosen in advance.",
        "",
        "## GAO's nine verdicts, reproduced",
        "",
        "| section | objectivity | validity | reliability |",
        "|---|---|---|---|",
    ]
    for key, row in results["grid"].items():
        lines.append(f"| `{key}` — {SECTION_TITLES[key]} | {row['objectivity']} | "
                     f"{row['validity']} | {row['reliability']} |")
    lines += [
        "",
        f"**{results['grid_match']} of GAO's 9 verdicts match.**",
        "",
        "GAO publishes those nine verdicts **in prose** — three section headings, each "
        "with an Objectivity / Validity / Reliability paragraph, printed pp. 8-14 — and "
        "**no per-question labels**. Arranging them as a 3x3 grid is ours, and so are "
        "the per-question states beneath it.",
        "",
        "### What the nine cells rest on",
        "",
        "Two scorer decisions taken during this same plan are load-bearing on "
        "**objectivity**, and both are named here so the headline number cannot be read "
        "as the output of an untouched scorer:",
        "",
        "* the narrative-only presentation clauses added to PRE-3 and PRE-4 "
        f"(`{counterfactuals['r2_decision']}`) — withdraw them and PRE-3 and PRE-4 both "
        "read 4 on all three sections, objectivity falls to "
        f"`{counterfactuals['r2_clauses_withdrawn']['objectivity']['dc']}`, and the "
        f"measured grid is **{counterfactuals['r2_clauses_withdrawn']['grid_match']} of "
        "9**;",
        f"* `pol-omfv.aggregationK = 21` (`{counterfactuals['k_decision']}`) — at the "
        "kernel default `k = 1` the measured grid is "
        f"**{counterfactuals['k'][0]['grid_match']} of 9**.",
        "",
        "Measured at several values of `k`: "
        + "; ".join(f"k={row['k']} → {row['grid_match']}/9"
                    for row in counterfactuals["k"]) + ".",
        "",
        "**Objectivity is the only dimension either decision reaches.** Validity and "
        "reliability read `insufficient_to_conclude` from PRE-1 = 4 and EXE-5 = 4, and "
        "both of those come from GAO's own F8 — every cited evidence item's "
        "`reliabilitySteps` is the `gap-reliability-steps` object. Six of the nine cells "
        "do not move under either counterfactual.",
        "",
        "## The nine findings",
        "",
        "Seven are detected by a named kernel rule. **F7 and F8 are detected by a "
        "rating** — EXE-8 and EXE-5 reaching state 4 — which is not a rule; the "
        "`detected_by` column in `findings_matrix.json` says which is which.",
        "",
        "| finding | detected | by | on | GAO attributes it to | also fires on | page |",
        "|---|---|---|---|---|---|---|",
    ]
    for fid in sorted(k for k in results["findings"] if k.startswith("F")):
        row = results["findings"][fid]
        lines.append(
            f"| {fid} | {'yes' if row['detected'] else 'NO'} | {row['detected_by']} | "
            f"{', '.join(row['sub_episode']) or '-'} | "
            f"{', '.join(row['attributed_to'])} | "
            f"{', '.join(row['cross_fired_on']) or '-'} | {row['page']} |")
    lines += [
        "",
        "## The counterfactual repair, in full",
        "",
        "| | before | after |",
        "|---|---|---|",
        f"| scope finding on `ev-ce-metrics` | `{repair['before']}` | "
        f"`{repair['after']}` |",
        f"| EXE-14 (`{VVA_TAILORING}`) | {repair['exe14_before']} | "
        f"{repair['exe14_after']} |",
        f"| EXE-5 | {repair['exe5_before']} | {repair['exe5_after']} |",
        "| combat-effectiveness row (grid tailoring) | "
        + " / ".join(repair["ce_row_before"][d]
                     for d in ("objectivity", "validity", "reliability")) + " | "
        + " / ".join(repair["ce_row_after"][d]
                     for d in ("objectivity", "validity", "reliability")) + " |",
        f"| `ev-ce-metrics` classification level | {repair['classification_level']} | "
        f"{repair['classification_level']} |",
        "",
        repair["reliability_note"],
        "",
        "## Readiness",
        "",
        "| episode | ready | blocking rules |",
        "|---|---|---|",
    ]
    for ep_id, ready in results["ready"].items():
        rules = ", ".join(results["blockers"][ep_id]) or "-"
        lines.append(f"| `{ep_id}` | {ready} | {rules} |")
    lines += [
        "",
        "## Honesty",
        "",
        "**There is no evaluation run anywhere in this demonstration.** No number is "
        "computed, no ranking is produced, no flip analysis exists. Every question that "
        "needs a run (PRE-1, EXE-5's ladder, `objective-run-coverage`) reads accordingly. "
        "Nothing here is evidence that the numeric path works — that is Demonstration "
        "A's job.",
        "",
        truth["transcribed"]["quotations"]["scope_limit"].strip(),
        "",
        truth["ours"]["glosses"]["scope_limit"].strip(),
        "",
        truth["transcribed"]["quotations"]["sensitivity_credit"].strip(),
        "",
        truth["ours"]["glosses"]["sensitivity_credit"].strip(),
        "",
        truth["ours"]["what_gao_published"].strip(),
        "",
        truth["ours"]["enumeration"].strip(),
        "",
    ]
    return "\n".join(lines)


def run(out_dir: Path = OUT) -> dict:
    """Build the programme, score it, measure the grid and the matrix, render, save."""
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    truth = yaml.safe_load(GROUND_TRUTH.read_text(encoding="utf-8"))

    g = build()
    readiness = _build_the_record(g)
    grid_reports, grid_states, vva_states = _score_sections(g)

    # Episode 5, 26 June 2023. GAO published on the 27th, so the downselect comes first.
    trigger_r5(g)
    open_refresh(g, PROGRAM, "rt-downselect", actor=H, now=NOW5,
                 replacements={"alt-omfv-concept": "alt-xm30-gdls"})
    revise_r5(g)
    transition(g, EPISODE_5, "MODEL_APPROVED", H, now=NOW5)
    transition(g, EPISODE_5, "PLAN_APPROVED", H, now=NOW5)
    readiness[EPISODE_5] = readiness_report(g, EPISODE_5, seed=SEED, now=NOW5)

    # GAO's own report, 27 June 2023, filed as a trigger that opens no episode.
    file_gao_grading_trigger(g)
    graded = sorted(SUB_EPISODES.values())
    affected = {
        "trigger": "rt-gao-grading",
        "episodes": sorted(affected_episodes(g, "rt-gao-grading")),
        "gradedSections": graded,
        "note": ("`affected_episodes` is transitive reverse reachability. The trigger is "
                 "filed on `prg-omfv`, and every main-chain episode references the "
                 "programme through `DecisionEpisode.program`, so the raw set is the "
                 "whole programme, not only the three sections GAO graded. The three "
                 "sections are the episodes whose own `claims` list holds one of the "
                 "claims the trigger names; `gradedSections` is that subset, and it is "
                 "ours, not the kernel's."),
    }

    policy = g.get(POLICY)
    main_findings = {ep_id: _episode_findings(g, ep_id, policy) for ep_id in MAIN_CHAIN}
    section_findings = {key: _episode_findings(g, ep_id, policy)
                        for key, ep_id in SUB_EPISODES.items()}
    # The same findings under the kernel's own scoping, so the matrix can measure what
    # our attribution rule suppresses instead of asserting it suppresses nothing.
    kernel_reach_findings = {
        key: _episode_findings(g, ep_id, policy, scoping="kernel-reach")
        for key, ep_id in SUB_EPISODES.items()}

    grid, grid_match = _grid(g, grid_reports, truth)
    # The bias-selection Risk on the combat-effectiveness section. `episode.risks` is the
    # right place to read it since `open_refresh` stopped carrying computed bias
    # indicators forward and `build_sub_episodes` stopped copying `-r4`'s: the list now
    # holds this section's own indicator and nothing else. `computedBiasRisks` from the
    # readiness call agrees, and a test asserts that it does.
    ce_selection_risks = sorted(
        r for r in g.get(SUB_EPISODES["ce"])["risks"]
        if g.has(r) and g.get(r)["kind"] == "bias-selection")
    matrix = _findings_matrix(g, section_findings, kernel_reach_findings, grid_states,
                              vva_states, main_findings, truth, ce_selection_risks)

    # Diffs between consecutive main-chain episodes only. The sub-episodes are three
    # readings of one episode, not a chain.
    diffs = {}
    for before, after in zip(MAIN_CHAIN, MAIN_CHAIN[1:], strict=False):
        d = diff_episodes(g, before, after, now=NOW5)
        diffs[f"{before}→{after}"] = {
            k: d[k] for k in ("changed", "added", "removed", "judgmentsChanged",
                              "judgmentsConsistent", "ratingsChanged", "pairing",
                              "because")}

    for ep_id in MAIN_CHAIN[:-1]:
        supersede(g, ep_id, now=NOW5)

    # What the grid measures without each of the two scorer decisions this plan took.
    # On a throwaway copy: the probes score, and scoring writes.
    grid_counterfactuals = _grid_counterfactuals(_pristine_copy(g, out_dir), truth)

    repair = _counterfactual(g, out_dir, grid["ce"])

    from docket.kernel.render import build_package
    packages = {}
    episode_ids = MAIN_CHAIN + [SUB_EPISODES[k] for k in ("dc", "fs", "ce")]
    for ep_id in episode_ids:
        renderings = ("full", "unclassified") if ep_id == SUB_EPISODES["ce"] else ("full",)
        for rendering in renderings:
            pkg, _ = build_package(g, ep_id, rendering=rendering, now=NOW5,
                                   out_dir=out_dir / "packages" / ep_id)
            packages[f"{ep_id}:{rendering}"] = pkg["hash"]

    results = {
        "episodes": [EPISODE_1, EPISODE_2, EPISODE_3, EPISODE_4,
                     SUB_EPISODES["dc"], SUB_EPISODES["fs"], SUB_EPISODES["ce"],
                     EPISODE_5],
        "grid": grid,
        "grid_match": grid_match,
        "grid_counterfactuals": grid_counterfactuals,
        "findings": matrix,
        "states": grid_states,
        "vva_states": vva_states,
        "diffs": diffs,
        "repair": repair,
        "des6_ce_state": grid_states["ce"].get("DES-6"),
        "ready": {ep_id: rr["ready"] for ep_id, rr in readiness.items()}
        | {SUB_EPISODES[k]: grid_reports[k]["ready"] for k in SUB_EPISODES},
        "blockers": {ep_id: sorted({b["rule"] for b in rr["blockers"]})
                     for ep_id, rr in readiness.items()}
        | {SUB_EPISODES[k]: sorted({b["rule"] for b in grid_reports[k]["blockers"]})
           for k in SUB_EPISODES},
        "affectedByGaoGrading": affected,
        "sectionTitles": dict(SECTION_TITLES),
        "kernel": grid_reports["dc"]["kernelVersion"],
        "seed": SEED,
        "charter": CHARTER,
        "policy": POLICY,
    }
    results["blocker_rules"] = sorted({r for rules in results["blockers"].values()
                                       for r in rules})

    g.save(out_dir / "graph")
    (out_dir / RESULTS_FILE).write_text(
        json.dumps({k: v for k, v in results.items()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    for name, payload in (("grid.json", {"grid": grid, "grid_match": grid_match,
                                         "counterfactuals": grid_counterfactuals}),
                          ("findings_matrix.json", matrix),
                          ("diffs.json", diffs),
                          ("affected_by_gao.json", affected)):
        (out_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8",
            newline="\n")
    (out_dir / "report.md").write_text(_report(results, truth), encoding="utf-8",
                                       newline="\n")

    return {**results, "graph": g, "readiness": readiness,
            "sectionReadiness": grid_reports, "packages": packages,
            "outDir": str(out_dir)}


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else OUT
    outcome = run(out_dir)
    print(json.dumps({
        "grid": outcome["grid"],
        "grid_match": outcome["grid_match"],
        "findings": {k: v["detected"] for k, v in outcome["findings"].items()
                     if k.startswith("F")},
        "cross_fires": outcome["findings"]["cross_fires"],
        "cross_fires_suppressed_by_our_attribution":
            outcome["findings"]["cross_fires_suppressed_by_our_attribution"],
        "grid_counterfactuals": {
            "r2_clauses_withdrawn":
                outcome["grid_counterfactuals"]["r2_clauses_withdrawn"]["grid_match"],
            "by_k": {row["k"]: row["grid_match"]
                     for row in outcome["grid_counterfactuals"]["k"]},
        },
        "ready": outcome["ready"],
        "repair": outcome["repair"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
