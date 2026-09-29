"""Ablations over Demo B's force-structure and combat-effectiveness sub-episodes
(design §9.2 step 5; plan 05 Task 7).

    uv run python -m demos.ablation.run [out_dir]

Re-runs `-fs` and `-ce` under `docket.eval.ablation.run_ablations`: once as built, once
with the scope checker turned off, once with every `Exclusion` object dropped, once with
every `InsufficientEvidence` object collapsed, once with the `silence` structural rule
turned off, and once with gaps collapsed *and* silence off together. Every transform and
context manager lives in `docket.eval.ablation`; this module only supplies the graph
(`_build_graph`) and the reading (`_score`), and renders the comparison.

Nothing here reads a clock or the network. `NOW4` and `SEED` are Demo B's own constants
(imported, not restated), so two runs of this module are byte-identical.

**Why `-dc` is not scored here.** The brief that corrected this task's Step 1 measures
losses on the force-structure and combat-effectiveness sections specifically —
`scope-off` losing `ReusePastPurpose` (F1, on `-fs`) and `NotAssessableAtLevel` (F4, on
`-ce`) is asserted as structurally certain because only `check_scope` emits either rule.
Nothing about the harness is specific to those two sections; a caller wanting `-dc` as
well only has to add its id to `EPISODE_IDS`.

**Why the graph is rebuilt through Demo B's own helpers rather than reimplemented.**
`_build_the_record` (episodes 1-4) and `build_sub_episodes` (the three March 2023
sections) are Demo B's own fixture construction; duplicating them here would be a second
copy of the honesty-rules-laden reconstruction work that plan 05 Task 5 already did and
had reviewed. This module only adds the two gate transitions Demo B's own `_score_
sections` also does, and stops short of calling `readiness_report` on the sub-episodes
itself — that call is `score_fn`'s job, once per variant, so the graph `run_ablations`
receives from `_build_graph` is gated but not yet scored.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from demos.b_omfv_2019_2023.build import NOW4, SUB_EPISODES, H, build, build_sub_episodes
from demos.b_omfv_2019_2023.run import SEED, _build_the_record
from docket.eval.ablation import run_ablations
from docket.kernel.lifecycle import transition
from docket.kernel.readiness import readiness_report
from docket.store import Graph

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
RESULTS_FILE = "ablation.json"

GRID_TAILORING = "gao-23-106549"

# The two sections the brief's corrected hypotheses measure. See the module docstring.
EPISODE_IDS = [SUB_EPISODES["fs"], SUB_EPISODES["ce"]]

SECTION_NAMES = {SUB_EPISODES["fs"]: "force structure designs and operational concepts",
                 SUB_EPISODES["ce"]: "combat effectiveness"}

# Plain-English loss, keyed by the variant substring that produced it (see
# `run_ablations`'s substring dispatch). Written once, read by `_render_markdown` for
# every variant whose name contains the key — not a per-variant literal table, so a
# combined variant like `gaps-collapsed-silence-off` picks up both sentences.
LOSS_BY_MECHANISM = {
    "scope-off": ("the record no longer says whether evidence built to answer one "
                  "question was reused to answer another, or whether a claim's "
                  "evidence carries the metadata its classification level requires — "
                  "only that a claim exists"),
    "no-exclusions": ("the record no longer states *why* a study or a measure was left "
                       "out; whatever silence that omission was covering is no longer "
                       "distinguishable from an omission nobody explained"),
    "gaps-collapsed": ("the record no longer says what was sought, where it was looked "
                        "for, why it was not found, or what would resolve it — the "
                        "questions a linchpin's rating still shows were asked, with "
                        "every trace of the asking removed"),
    "silence-off": ("an empty required field is no longer reported at all — the "
                     "record can go quiet on a slot the schema requires and nothing "
                     "downstream of the structural rules will say so"),
}


def _build_graph() -> Graph:
    """Demo B's graph, gated through `PLAN_APPROVED` on the three March 2023
    sub-episodes, not yet scored."""
    g = build()
    _build_the_record(g)
    build_sub_episodes(g)
    for ep_id in SUB_EPISODES.values():
        transition(g, ep_id, "MODEL_APPROVED", H, now=NOW4)
        transition(g, ep_id, "PLAN_APPROVED", H, now=NOW4)
    return g


def _score(g: Graph, episode_id: str) -> dict:
    """One episode's reading: the readiness report's own findings, ratings and
    verdicts, reduced to the shape `docket.eval.ablation._compare` reads."""
    rr = readiness_report(g, episode_id, tailoring=GRID_TAILORING, seed=SEED, now=NOW4)
    findings: dict[str, list[list[str]]] = {}
    for f in rr["blockers"] + rr["warnings"]:
        findings.setdefault(f["rule"], []).append(f["objects"])
    sa = g.get(rr["standardsAssessment"])
    ratings = {r["questionId"]: r["state"] for r in sa["ratings"] if r["applicable"]}
    verdicts = {dim: v["verdict"] for dim, v in sa["dimensionVerdicts"].items()}
    return {"findings": findings, "ratings": ratings, "verdicts": verdicts,
            "gaps": rr["openGaps"], "exclusions": rr["openExclusions"]}


def _present(rule: str, baseline_rules: set[str], variant: dict) -> str:
    """`lost` if every occurrence vanished, `gained` if the rule is new, `yes (+)` if a
    rule already present at baseline picked up an additional occurrence (`_compare`'s
    per-occurrence `gained_findings` catches this — `no-exclusions` does not introduce
    the rule `silent-omission`, it adds one new occurrence of it on `ev-234-report`),
    `yes` if unchanged, `—` if absent throughout."""
    if rule in variant.get("lost_findings", ()):
        return "lost"
    gained_new_occurrence = any(rule in bucket
                                for bucket in variant.get("gained_findings", {}).values())
    if rule in baseline_rules:
        return "yes (+)" if gained_new_occurrence else "yes"
    return "gained" if gained_new_occurrence else "—"


def _rated(qid: str, baseline_ratings: dict, variant: dict) -> str:
    changed = variant.get("ratings_changed", {})
    if qid in changed:
        before, after = changed[qid]
        return f"{before} → {after}"
    state = baseline_ratings.get(qid)
    return "—" if state is None else str(state)


def _verdict(dim: str, baseline_verdicts: dict, variant: dict) -> str:
    changed = variant.get("verdicts_changed", {})
    if dim in changed:
        before, after = changed[dim]
        return f"{before} → {after}"
    return baseline_verdicts.get(dim, "—")


def _section_markdown(ep_id: str, section: dict) -> str:
    baseline = section["baseline"]
    variants = [v for v in section if v != "baseline"]
    baseline_rules = set(baseline.get("findings", {}))
    all_rules = sorted(
        baseline_rules | {r for v in variants
                          for bucket in section[v].get("gained_findings", {}).values()
                          for r in bucket})
    all_qids = sorted(baseline.get("ratings", {}))
    all_dims = sorted(baseline.get("verdicts", {}))

    lines = [f"### {ep_id} — {SECTION_NAMES.get(ep_id, ep_id)}", "",
             "One table: every finding rule or question id this section's baseline "
             "carries, or that some variant gained, against every variant. `yes`/`—`"
             " is a finding present/absent; a rating or verdict cell shows `before →"
             " after` where a variant changed it and the baseline value otherwise.", "",
             "| item | kind | baseline | " + " | ".join(variants) + " |",
             "|---" * (3 + len(variants)) + "|"]
    for rule in all_rules:
        row = [f"`{rule}`", "finding", "yes" if rule in baseline_rules else "—"]
        row += [_present(rule, baseline_rules, section[v]) for v in variants]
        lines.append("| " + " | ".join(row) + " |")
    for qid in all_qids:
        row = [qid, "rating", str(baseline["ratings"][qid])]
        row += [_rated(qid, baseline["ratings"], section[v]) for v in variants]
        lines.append("| " + " | ".join(row) + " |")
    for dim in all_dims:
        row = [dim, "verdict", baseline["verdicts"][dim]]
        row += [_verdict(dim, baseline["verdicts"], section[v]) for v in variants]
        lines.append("| " + " | ".join(row) + " |")

    lines += ["", "Gained findings, bucketed (ruling R9 — a `schema` or `silence` "
                  "finding produced by emptying a slot is never counted as evidence "
                  "that the exclusion or gap object itself mattered), and the "
                  "substitution count:", "",
              "| variant | schema | silence | other | substitutions |",
              "|---|---|---|---|---|"]
    for v in variants:
        g = section[v]["gained_findings"]
        lines.append(
            f"| {v} | {len(g['schema'])} | {len(g['silence'])} | {len(g['other'])} | "
            f"{len(section[v]['substitutions'])} |")

    lines += ["", "What each variant's loss means, in plain English:", ""]
    for v in variants:
        sentences = [text for key, text in LOSS_BY_MECHANISM.items() if key in v]
        gaps_lost = section[v]["gaps_lost"]
        exclusions_lost = section[v]["exclusions_lost"]
        detail = "; ".join(sentences) if sentences else "no mechanism-specific note"
        extra = []
        if gaps_lost:
            extra.append(f"gap objects lost: {', '.join(gaps_lost)}")
        if exclusions_lost:
            extra.append(f"exclusion objects lost: {', '.join(exclusions_lost)}")
        if extra:
            detail += " (" + "; ".join(extra) + ")"
        lines.append(f"- **{v}**: {detail}")
    lines.append("")
    return "\n".join(lines)


def _render_markdown(results: dict) -> str:
    header = [
        "# Ablations — what Demo B's readiness reading loses per mechanism",
        "",
        "Generated from `ablation.json` by `demos/ablation/run.py`; nothing below is "
        "typed by hand. Per GAO-23-106549's own scope limit (footnote 7; Appendix I), "
        "none of this speaks to whether the Army's underlying analysis was right — "
        "only to which representation failures a reading can still detect once a "
        "mechanism is removed.", "",
    ]
    body = [_section_markdown(ep_id, results[ep_id]) for ep_id in results]
    return "\n".join(header + body)


def run(out_dir: Path = OUT) -> dict:
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = run_ablations(_build_graph, _score, EPISODE_IDS)

    (out_dir / RESULTS_FILE).write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")
    (out_dir / "ablation.md").write_text(_render_markdown(results), encoding="utf-8",
                                         newline="\n")
    return results


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else OUT
    results = run(out_dir)
    print(json.dumps(
        {ep: {v: (d if v == "baseline" else d["lost_findings"])
              for v, d in section.items()}
         for ep, section in results.items()},
        indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
