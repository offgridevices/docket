"""Run the GAO-15-548 positive control: gates, readiness, the standards assessment.

    uv run python -m demos.control_gao_15_548.run [out_dir]

Nothing here reads a clock, a network or an environment variable. `NOW` and `SEED` are
constants, so two runs produce byte-identical output; `tests/demos` asserts it.

The record stops at `PLAN_APPROVED`, and that is the honest stopping point. Five of the
study's six analyses are qualitative and GAO publishes no per-alternative numbers, so
there is nothing for the kernel to compute: `runs: []`, the `EVALUATED` gate's
`every-step-has-run` check would refuse, and it is not asked. The one blocker in the
readiness report — `objective-run-coverage` — is the same fact said again, and it is a
true statement about a narrative study, not a defect in the fixture.

`out/` holds four things: the saved store (`graph/`), the full decision package
(`package-full.md`), the machine-readable summary the tests and the README read
(`control.json`), and a short human-readable run report (`report.md`).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

from demos.control_gao_15_548.build import EPISODE, NOW, SRC, H, build
from docket.eval.agreement import agreement, cohen_kappa, label_from_state, majority_baseline
from docket.kernel.lifecycle import transition
from docket.kernel.readiness import readiness_report
from docket.standard import load_standard

SEED = 15548
HERE = Path(__file__).parent
OUT = HERE / "out"
EXPECTED = HERE / "expected.yaml"
TAILORING = "gao-15-548"

# The machine-readable summary this demo publishes, declared rather than remembered.
# Demo A writes `results.json` and `validation_gao_21_460` writes `agreement.json`
# alongside its own; plan 05 Task 8's `run_all` reads each demo's declared file, so each
# demo has to name one. Named here and repeated in the README.
RESULTS_FILE = "control.json"

# GAO published no per-question ratings for this study and does not grade on objectivity,
# validity and reliability at all. Repeated here because this string is written into
# every artefact `run()` produces, so no artefact can be read without it.
OURS = (
    "Every per-question state and every dimension verdict below is OURS. GAO-15-548 "
    "published neither: printed p. 24 (PDF p. 27), \"we determined that qualitative "
    "assessment ratings provide the best explanation of the nuances of the analysis and "
    "findings, rather than numeric ratings for each individual standard.\" The "
    "objectivity/validity/reliability frame comes from Section 234(d) of the FY2022 NDAA "
    "by way of GAO-23-106549, not from GAO-15-548."
)


def _measured(rr: dict, sa: dict) -> dict:
    """The per-question states, the dimension verdicts and the blockers, as measured."""
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    rules = {r["questionId"]: r["rule"] for r in sa["ratings"]}
    return {
        "source": SRC,
        "tailoring": sa["tailoring"],
        "kernel": sa["kernelVersion"],
        "now": NOW,
        "seed": SEED,
        "aggregationK": sa["k"],
        "aggregationRule": sa["aggregationRule"],
        "note": OURS,
        "states": states,
        "rules": rules,
        "dimensions": {d: v["verdict"] for d, v in sa["dimensionVerdicts"].items()},
        "dimensionQualifiers": {d: v["qualifier"] for d, v in sa["dimensionVerdicts"].items()},
        "des_4_state": states.get("DES-4"),
        "ready": rr["ready"],
        "blockers": [{"rule": b["rule"], "objects": b["objects"], "message": b["message"]}
                     for b in rr["blockers"]],
        "warnings": sorted({w["rule"] for w in rr["warnings"]}),
        "openGaps": rr["openGaps"],
        "openExclusions": rr["openExclusions"],
        "computedBiasRisks": rr["computedBiasRisks"],
        "lifecycleState": "PLAN_APPROVED",
    }


def _agreement(states: dict[str, int | None]) -> dict:
    """Measure this run against `expected.yaml`'s recorded per-question table.

    `expected.yaml` is a **measurement target**, not a published answer key — GAO
    published none for this study — and its per-question table was recorded from a run of
    this file, not hand-written. So the number below is a regression check: it says the
    fixture still scores what it scored when the table was recorded. It is not evidence
    about GAO, and the README says so in as many words.

    Absent an `expected.yaml` (the first, bootstrapping run), every statistic is `None`
    rather than a fabricated 1.0.
    """
    if not EXPECTED.exists():
        return {"available": False, "agreement": None, "kappa": None,
                "majority_baseline": None, "n": 0, "disagreements": {}}
    exp = yaml.safe_load(EXPECTED.read_text(encoding="utf-8"))
    target = exp.get("per_question_states") or {}
    truth = {q: label_from_state(s) for q, s in target.items() if s is not None}
    pred = {q: label_from_state(s) for q, s in states.items() if s is not None}
    shared = sorted(set(pred) & set(truth))
    return {
        "available": True,
        "against": ("demos/control_gao_15_548/expected.yaml — OUR measurement target, "
                    "recorded from a run of this file; GAO published no per-question key"),
        "agreement": agreement(pred, truth),
        "kappa": cohen_kappa(pred, truth),
        "majority_baseline": majority_baseline(truth),
        "n": len(shared),
        "state_agreement": (
            sum(1 for q in shared if states.get(q) == target.get(q)) / len(shared)
            if shared else None),
        "disagreements": {q: {"measured": states.get(q), "target": target.get(q)}
                          for q in shared if states.get(q) != target.get(q)},
    }


def _report(control: dict, agree: dict) -> str:
    """A short run report. Every number in it is read out of `control`."""
    standard = load_standard()
    canonical = {q["id"]: q["canonical"] for q in standard["questions"]}
    bands = {q["id"]: q["band"] for q in standard["questions"]}
    lines = [
        "# GAO-15-548 positive control — run report",
        "",
        f"Source: `{control['source']}` (printed page + 3 = PDF page).",
        f"Tailoring `{control['tailoring']}`, kernel {control['kernel']}, "
        f"seed {control['seed']}, asOf/now `{control['now']}`, "
        f"aggregation k = {control['aggregationK']}.",
        "",
        "> " + OURS.replace("\n", " "),
        "",
        "GAO's own published verdict, printed p. 7: the Army's combat vehicle industrial "
        "base study's approach — \"including its design, execution, and presentation of "
        "results — was both reasonable and sound for its intended purposes\". GAO assessed "
        "the reasonableness of the study's *methods* (printed p. 2); it did not assess or "
        "verify the study's underlying analytical work, and neither does this record.",
        "",
        "## Dimension verdicts (ours)",
        "",
        "| dimension | verdict | qualifier |",
        "|---|---|---|",
    ]
    for dim in ("objectivity", "validity", "reliability"):
        lines.append(f"| {dim} | `{control['dimensions'][dim]}` | "
                     f"{control['dimensionQualifiers'][dim] or '—'} |")
    lines += [
        "",
        "## Per-question states (ours)",
        "",
        "| question | band | state | firing clause | question |",
        "|---|---|---|---|---|",
    ]
    for qid in sorted(control["states"], key=lambda q: (q.split("-")[0], int(q.split("-")[1]))):
        state = control["states"][qid]
        lines.append(f"| {qid} | {bands.get(qid, '—')} | "
                     f"{'—' if state is None else state} | `{control['rules'][qid]}` | "
                     f"{canonical.get(qid, '')} |")
    lines += [
        "",
        f"Applicable questions: {sum(1 for s in control['states'].values() if s is not None)} "
        f"of {len(control['states'])}. States present among them: "
        f"{sorted({s for s in control['states'].values() if s is not None})}.",
        "",
        "## Readiness",
        "",
        f"`ready`: **{control['ready']}**.",
        "",
    ]
    if control["blockers"]:
        lines.append("| blocker | objects | why |")
        lines.append("|---|---|---|")
        for b in control["blockers"]:
            lines.append(f"| `{b['rule']}` | {', '.join(b['objects'])} | {b['message']} |")
    else:
        lines.append("No blockers.")
    lines += [
        "",
        f"Warnings raised: {', '.join(f'`{w}`' for w in control['warnings']) or 'none'}.",
        f"Open gaps: {', '.join(f'`{g}`' for g in control['openGaps']) or 'none'}.",
        f"Open exclusions: {', '.join(f'`{x}`' for x in control['openExclusions']) or 'none'}.",
        "",
        "## Agreement with the measurement target",
        "",
    ]
    if agree["available"]:
        lines += [
            f"Measured against {agree['against']}.",
            "",
            f"- label agreement (`assessed` / `unable_to_assess`): "
            f"**{agree['agreement']:.3f}** over {agree['n']} shared questions",
            f"- exact-state agreement: **{agree['state_agreement']:.3f}**",
            f"- majority baseline on the target labels: {agree['majority_baseline']:.3f}",
            f"- Cohen's kappa: {agree['kappa']:.3f} — the target carries one label only, so "
            "kappa is undefined in substance and reads 0.0; it carries no information here",
            "",
            f"Disagreements: {agree['disagreements'] or 'none'}.",
            "",
            "This is a regression check on the fixture, not a comparison against GAO. "
            "GAO-15-548 published no per-question ratings (printed p. 24), so there is no "
            "external key for this case; the only external comparison available is against "
            "GAO's published qualitative verdict, quoted above.",
        ]
    else:
        lines.append("No `expected.yaml` present — this is a bootstrapping run.")
    lines.append("")
    return "\n".join(lines)


def run(out_dir: Path = OUT) -> dict:
    """Build, drive G1 and G2, score, render, save. Returns the summary."""
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    g = build()

    # G1 and G2. Both are human-only edges; both record every check they ran. There is no
    # `EVALUATED` transition: the study has no evaluation run and none is invented, so the
    # gate that asks for one is not driven.
    transition(g, EPISODE, "MODEL_APPROVED", H, now=NOW)
    transition(g, EPISODE, "PLAN_APPROVED", H, now=NOW)

    rr = readiness_report(g, EPISODE, seed=SEED, now=NOW)
    sa = g.get(rr["standardsAssessment"])

    control = _measured(rr, sa)
    agree = _agreement(control["states"])
    control["agreement"] = agree

    # Imported here rather than at module scope: `render.py` is under active revision by
    # another task, and nothing this control asserts depends on the package's bytes.
    from docket.kernel.render import build_package
    pkg, _ = build_package(g, EPISODE, rendering="full", now=NOW, out_dir=out_dir)
    control["package"] = {"hash": pkg["hash"], "path": pkg["path"]}

    g.save(out_dir / "graph")
    (out_dir / RESULTS_FILE).write_text(
        json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "report.md").write_text(
        _report(control, agree), encoding="utf-8", newline="\n")

    return {**control, "graph": g, "readiness": rr, "standardsAssessment": sa,
            "outDir": str(out_dir)}


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else OUT
    outcome = run(out_dir)
    print(json.dumps({
        "tailoring": outcome["tailoring"],
        "dimensions": outcome["dimensions"],
        "des_4_state": outcome["des_4_state"],
        "states": outcome["states"],
        "ready": outcome["ready"],
        "blockers": [b["rule"] for b in outcome["blockers"]],
        "agreement": outcome["agreement"]["agreement"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
