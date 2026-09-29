"""Run Demonstration A end to end: gates, evaluation, flips, readiness, two packages.

    uv run python -m demos.a_cbo_gcv_2013.run [out_dir]

Nothing here reads a clock, a network or an environment variable. `NOW` and `SEED` are
constants, so two runs of this file produce byte-identical output — which is the point of
the demonstration as much as the numbers are, and is asserted in `tests/demos`.

The order below is the record's own order, and it is not decoration:

* the model is approved (G1) before anything is computed;
* the plan is approved by a named human (G2) before the evaluator is allowed to run — and
  `evaluate()` refuses again on its own account if it is not;
* claims are written only after the runs they rest on exist, and they name the run and
  the result they came from;
* readiness is computed before the record is put up for signature (G3's input);
* the episode stops at PENDING_SIGNATURE, because CBO made no recommendation and no
  decision was taken in the source document.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from demos.a_cbo_gcv_2013.build import NOW, SRC, H, build, cited
from docket.kernel.evaluate import evaluate
from docket.kernel.flip import flip_analysis
from docket.kernel.lifecycle import transition
from docket.kernel.readiness import readiness_report
from docket.kernel.render import build_package
from docket.store import Graph

SEED = 20130430
OUT = Path(__file__).parent / "out"
EPISODE = "ep-cbo-2013"
PLAN = "pl-cbo"


def _claims(by_run: dict[str, dict]) -> list[dict]:
    """The five statements this record asserts, each naming what it rests on.

    `ev-army-sim-2010` and `ev-army-aoa-2011` are deliberately *not* cited by any claim.
    Both are Army files that are not public: their `pointer` is a recorded gap, and the
    scope checker is right to refuse a claim that says "assessable at U" while resting on
    evidence whose metadata nobody outside the Army can see. They stay in the record as
    the evidence behind the observations, where what is being asserted is only "CBO
    reports this number from that source", which is checkable on CBO's page.
    """
    primary, secondary = by_run["primary"], by_run["secondary"]
    return [
        cited(
            "cl-primary", "Claim", "pp. 3, 21",
            text=("Under CBO's primary metric the Puma is the most capable of the five "
                  "vehicles, followed by the upgraded Bradley IFV, the notional GCV and the "
                  "Namer."),
            questionClass="requirements-tradeoff", assessableAt={"level": "U"},
            supportedBy=[
                {"evidence": "ev-cbo-2013"},
                {"evidence": "ev-army-expert-estimates",
                 "reuseJustification": {
                     "text": ("The Namer's and the Puma's protection and lethality are Army "
                              "analysts' estimates, made because the technical data were "
                              "insufficient to simulate those vehicles; CBO placed them "
                              "beside the GCV's simulated scores and said so (p. 20 fn 4)."),
                     "authority": "Congressional Budget Office"}},
                {"evidence": "ev-army-mobility-data"}],
            derivedFrom=primary["id"], resultRef=f"res-{primary['id']}-{primary['ranking'][0]}",
            addresses=["obj-capability"], section="evaluation-results"),
        cited(
            "cl-secondary", "Claim", "p. 4; p. 21 (Table 2-2)",
            text=("Under CBO's secondary metric, which scores the nine-member squad all or "
                  "nothing, the Puma stays slightly ahead of the GCV, and the Namer and the "
                  "upgraded Bradley are within a quarter-point of each other — CBO printed "
                  "both as 25."),
            questionClass="requirements-tradeoff", assessableAt={"level": "U"},
            supportedBy=[{"evidence": "ev-cbo-2013"}],
            derivedFrom=secondary["id"],
            resultRef=f"res-{secondary['id']}-{secondary['ranking'][0]}",
            addresses=["obj-capability"], section="evaluation-results"),
        cited(
            "cl-cost", "Claim", "p. 3",
            text=("Fielding Pumas or upgraded Bradleys would cost $14 billion and $9 billion "
                  "less, respectively, than the Army's GCV program over 2014 through 2030."),
            questionClass="cost", assessableAt={"level": "U"},
            supportedBy=[{"evidence": "ev-cbo-cost-estimate"}], addresses=["obj-cost"],
            section="evaluation-results"),
        cited(
            "cl-weights", "Claim", "pp. 33–34",
            text=("CBO's primary-metric weights are the Army's category weights for the "
                  "four categories CBO could assess, renormalised to sum to one (CBO writes "
                  "'based on'; Table A-1's figures make it an exact renormalisation); the "
                  "Army derived those from rankings given by soldiers who had deployed with "
                  "combat brigades."),
            questionClass="requirements-tradeoff", assessableAt={"level": "U"},
            supportedBy=[
                {"evidence": "ev-cbo-2013"},
                {"evidence": "ev-soldier-survey",
                 "reuseJustification": {
                     "text": ("The ranking was collected to find out which characteristics "
                              "matter most to deployed soldiers; CBO reused it as the "
                              "weighting for a requirements trade-off and states that "
                              "derivation in its methodology appendix (pp. 33–34)."),
                     "authority": "Congressional Budget Office"}}],
            addresses=["obj-capability"], section="objectives-and-measures"),
        cited(
            "cl-squad-rationale", "Claim", "p. 6 (Box 1-1)",
            text=("The Army's stated reason for carrying a full nine-member squad in one "
                  "vehicle is that a squad split between vehicles is hard to organise and "
                  "direct in the moments after the soldiers dismount."),
            questionClass="operational-concept", assessableAt={"level": "U"},
            supportedBy=[
                {"evidence": "ev-army-squad-2011"},
                {"evidence": "ev-cbo-2013",
                 "reuseJustification": {
                     "text": ("The sentence is read off CBO's Box 1-1, which restates the "
                              "Army's operational concept for the squad inside a "
                              "requirements trade-off study and cites the Army's own "
                              "document for it (p. 6 and fn 2/fn 4)."),
                     "authority": "Congressional Budget Office"}}],
            addresses=["obj-capability"], section="grca"),
    ]


def _narratives(g: Graph, by_run: dict[str, dict], flips: list[dict]) -> list[dict]:
    """Two short narratives whose every numeral is taken from the object it cites.

    The numerals are formatted from the stored values rather than typed in, so the
    renderer's citation check is testing the record and not this file's spelling. A
    sentence with a number nothing backs would refuse the whole package.
    """
    primary = by_run["primary"]["id"]
    puma = g.get(f"res-{primary}-alt-puma")["value"]
    gcv = g.get(f"res-{primary}-alt-gcv")["value"]
    by_target = {f["parameter"]["target"]: f for f in flips}
    squad, leth = by_target["ws-secondary:m-squad"], by_target["ws-secondary:m-leth"]
    return [
        cited(
            "nar-results", "Narrative", "p. 21 (Table 2-2)", confidence="inferred",
            episode=EPISODE, section="evaluation-results",
            sentences=[{
                "text": (f"On CBO's primary metric the kernel scores the Puma at {puma} "
                         f"percent and the notional GCV at {gcv} percent improvement over "
                         f"the current Bradley IFV, which CBO printed as {puma:.0f} and "
                         f"{gcv:.0f}."),
                "cites": [f"res-{primary}-alt-puma", f"res-{primary}-alt-gcv"]}]),
        cited(
            "nar-flip", "Narrative", "p. 35 (Table A-3)", confidence="inferred",
            episode=EPISODE, section="what-flips",
            sentences=[
                {"text": (f"Raising the weight on the full-squad criterion from "
                          f"{squad['currentValue']} to {squad['flipThreshold']:.4f} makes the "
                          f"Ground Combat Vehicle the top-ranked vehicle on CBO's secondary "
                          f"metric — {squad['flipDistance']:.4f} of weight away from the "
                          f"weighting CBO itself published."),
                 "cites": [squad["id"]]},
                {"text": (f"The weight on lethality reaches the same reversal marginally "
                          f"sooner, at {leth['flipThreshold']:.4f} rather than "
                          f"{leth['currentValue']}."),
                 "cites": [leth["id"]]}]),
    ]


def _results(g: Graph, by_run: dict, flips: list[dict], rr: dict, packages: dict) -> dict:
    """The machine-readable summary the tests and the README read."""

    def aggregate(step: str) -> dict[str, float]:
        run_id = by_run[step]["id"]
        return {alt: g.get(f"res-{run_id}-{alt}")["value"] for alt in by_run[step]["ranking"]}

    def flips_for(step: str) -> dict[str, dict]:
        run_id = by_run[step]["id"]
        return {
            f["parameter"]["target"]: {
                "flipThreshold": f["flipThreshold"], "flipDistance": f["flipDistance"],
                "direction": f["direction"], "rankingAfter": f["rankingAfter"],
                "assumption": f.get("assumption"),
            }
            for f in flips if f["run"] == run_id
        }

    def shortest(step: str) -> str | None:
        run_id = by_run[step]["id"]
        measured = [f for f in flips
                    if f["run"] == run_id and f["flipDistance"] is not None]
        if not measured:
            return None
        return min(measured, key=lambda f: (f["flipDistance"], f["id"]))["parameter"]["target"]

    standards = g.get(rr["standardsAssessment"])
    return {
        "source": SRC,
        "kernel": rr["kernelVersion"],
        "now": NOW,
        "seed": SEED,
        "primary": aggregate("primary"),
        "secondary": aggregate("secondary"),
        "ranking": {step: run["ranking"] for step, run in by_run.items()},
        "flip": {
            "primary": flips_for("primary"),
            "secondary": flips_for("secondary"),
            "primary_shortest": shortest("primary"),
            "secondary_shortest": shortest("secondary"),
        },
        "simplex": rr["flipSummary"].get("simplexRobustness", {}),
        "ready": rr["ready"],
        "blockers": [b["rule"] for b in rr["blockers"]],
        "warnings": sorted({w["rule"] for w in rr["warnings"]}),
        "openGaps": rr["openGaps"],
        "openExclusions": rr["openExclusions"],
        "dimensions": {d: v["verdict"] for d, v in standards["dimensionVerdicts"].items()},
        "packages": packages,
    }


def run(out_dir: Path = OUT) -> dict:
    """Build, gate, evaluate, analyse, render. Returns the graph and the summary."""
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    g = build()

    # G1 and G2. Both are human-only edges; both record every check they ran.
    transition(g, EPISODE, "MODEL_APPROVED", H, now=NOW)
    transition(g, EPISODE, "PLAN_APPROVED", H, now=NOW)

    runs = evaluate(g, PLAN, seed=SEED, now=NOW)
    by_run = {r["step"]: r for r in runs}
    flips: list[dict] = []
    for r in runs:
        flips += flip_analysis(g, r["id"], seed=SEED, now=NOW)

    claims = _claims(by_run)
    narratives = _narratives(g, by_run, flips)
    for obj in claims + narratives:
        g.put(obj, H)
    ep = g.get(EPISODE)
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "claims": [c["id"] for c in claims],
           "narratives": [n["id"] for n in narratives]}, H)

    transition(g, EPISODE, "EVALUATED", H, now=NOW)
    rr = readiness_report(g, EPISODE, seed=SEED, now=NOW)
    transition(g, EPISODE, "PENDING_SIGNATURE", H, now=NOW)

    packages = {}
    for rendering in ("unclassified", "full"):
        pkg, _ = build_package(g, EPISODE, rendering=rendering, now=NOW, out_dir=out_dir)
        packages[rendering] = pkg["hash"]

    g.save(out_dir / "graph")
    results = _results(g, by_run, flips, rr, packages)
    (out_dir / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"graph": g, "runs": runs, "flips": flips, "readiness": rr, "packages": packages,
            "results": results, "outDir": str(out_dir)}


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else OUT
    outcome = run(out_dir)
    print(json.dumps({
        "ready": outcome["readiness"]["ready"],
        "blockers": outcome["results"]["blockers"],
        "ranking": outcome["results"]["ranking"],
        "packages": outcome["packages"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
