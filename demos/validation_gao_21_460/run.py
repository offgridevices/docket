"""Score the blinded GAO-21-460 reconstruction and compare it with Figure 6.

    uv run python -m demos.validation_gao_21_460.run [out_dir]

Blinding: `build.py` was written by an agent that never opened the GAO PDF, this
directory's `ground_truth.yaml`, `src/docket/standard/` (whose 36-question file carries a
per-product `usage` key naming GAO-21-460's seven "unable" questions outright), or
`library/`. **This module is the only one that reads the key.** The protocol, what leaked
anyway, and what the resulting number does and does not show are all in `README.md`.

Nothing here reads a clock, a network or an environment variable: `NOW` and `SEED` are
constants, so two runs produce byte-identical output, which `tests/demos` asserts.

The order is the record's own order — the model is approved (G1) and the plan is approved
by a named human (G2) before anything is scored — and the episode stops there, because
the Army's study had not reported when GAO's audit closed (printed p. 14). No claims, no
runs, no commitment; `ready` is false and the report says why.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

from demos.validation_gao_21_460.build import H, build
from docket.eval.agreement import (
    agreement,
    by_band,
    cohen_kappa,
    confusion,
    label_from_state,
    majority_baseline,
    precision_recall,
)
from docket.kernel.lifecycle import transition
from docket.kernel.readiness import readiness_report
from docket.kernel.render import build_package
from docket.standard import load_standard

NOW = "2021-05-01T00:00:00Z"
SEED = 21460
HERE = Path(__file__).parent
OUT = HERE / "out"
EPISODE = "ep-twv-2021"

# The two sentences inside the pages the blinded builder had to read that telegraph seven
# of the twenty-one labels. Disclosed rather than redacted: both are load-bearing for the
# fixture, so removing them would have produced a record that does not match the source.
LEAK = (
    "Presentation-band caveat: two sentences inside the pages the blinded builder had to "
    "read state that the study had not reported — printed p. 14, \"As the study is "
    "not yet complete, we were not able to examine the consistency and verifiability of "
    "data measurement as well as the description and documentation of the models used "
    "for the study\", and printed p. 35, \"The 2021 MDO TWV Study final report was not "
    "available during the time of our audit so we were able to assess only the design "
    "portion and portions of the execution of the study against the standards.\" Both are "
    "load-bearing (the first is why every VV&A section is a gap; the second is why the "
    "episode has no claims and no runs), so they were disclosed, not redacted. The "
    "presentation band is therefore close to deterministic given the visible text; the "
    "design and execution bands carry the information, which is why `by_band` is reported."
)


def run(out_dir: Path = OUT) -> dict:
    """Build blind, gate, score, compare with GAO's published key. Returns the summary."""
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    g = build()
    # build() already sets ep.plan = "pl-twv", so the G2 plan-present check finds it.
    transition(g, EPISODE, "MODEL_APPROVED", H, now=NOW)
    transition(g, EPISODE, "PLAN_APPROVED", H, now=NOW)
    rr = readiness_report(g, EPISODE, seed=SEED, now=NOW)
    sa = g.get(rr["standardsAssessment"])

    truth = yaml.safe_load((HERE / "ground_truth.yaml").read_text(encoding="utf-8"))["labels"]
    rating = {r["questionId"]: r for r in sa["ratings"] if r["applicable"]}
    pred = {qid: label_from_state(r["state"]) for qid, r in rating.items()}
    bands = {q["id"]: q["band"] for q in load_standard()["questions"]}
    p, r_ = precision_recall(pred, truth, "unable_to_assess")
    per_question = {
        q: {"band": bands[q], "state": rating[q]["state"], "rule": rating[q]["rule"],
            "justification": rating[q]["justification"],
            "pred": pred[q], "truth": truth[q], "match": pred[q] == truth[q]}
        for q in sorted(truth)
    }
    result = {
        "agreement": agreement(pred, truth),
        "kappa": cohen_kappa(pred, truth),
        "confusion": confusion(pred, truth),
        "precision_unable": p,
        "recall_unable": r_,
        "majority_baseline": majority_baseline(truth),
        "by_band": by_band(pred, truth, bands),
        "per_question": per_question,
        "dimensionVerdicts": {d: v["verdict"] for d, v in sa["dimensionVerdicts"].items()},
        # An assertion by this (unblinded) module, not a derived value: the protocol says a
        # denylisted read in the builder's transcript sets this false, and the transcript
        # audit is an agent-report control. What *is* mechanical is the grep gate over
        # build.py and study_description.txt in tests/demos, which is the floor under it.
        "blinded": True,
        "tailoring": sa["tailoring"],
        "kernel": sa["kernelVersion"],
        "ready": rr["ready"],
        "blockers": sorted({b["rule"] for b in rr["blockers"]}),
        "warnings": sorted({w["rule"] for w in rr["warnings"]}),
    }

    build_package(g, EPISODE, rendering="full", now=NOW, out_dir=out_dir)
    g.save(out_dir / "graph")
    (out_dir / "agreement.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    matched = sum(1 for v in per_question.values() if v["match"])
    misses = [q for q, v in per_question.items() if not v["match"]]
    lines = [
        "# GAO-21-460 validation — per-question agreement", "",
        "Blinded reconstruction of the Army's 2021 MDO TWV Study from GAO's description of "
        f"it; scored under tailoring `{sa['tailoring']}`, kernel {sa['kernelVersion']}.", "",
        "GAO-21-460 Figure 6 is the only per-question published key in the GAO record. GAO "
        "assessed the *study*, and this reconstruction is built from GAO's description of "
        "the study, not from the study's own documents.", "",
        f"- Agreement: **{result['agreement']:.3f}** ({matched}/{len(per_question)}) vs "
        f"majority baseline {result['majority_baseline']:.3f}",
        f"- Cohen's kappa: **{result['kappa']:.3f}**",
        f"- 'Unable to assess' precision/recall: {p:.2f} / {r_:.2f}",
        "- By band: " + ", ".join(f"{b} {v:.3f}" for b, v in sorted(result["by_band"].items())),
        f"- Disagreements: {', '.join(misses) if misses else 'none'}",
        f"- `ready`: {str(result['ready']).lower()} — blockers "
        f"{', '.join(result['blockers']) or 'none'}. A study that had not reported is not a "
        "signable record, and the report says so rather than hiding it.",
        f"- {LEAK}", "",
        "| question | band | kernel state | rule | kernel label | GAO label | match |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [f"| {q} | {v['band']} | {v['state']} | `{v['rule']}` | {v['pred']} | "
              f"{v['truth']} | {'yes' if v['match'] else 'NO'} |"
              for q, v in per_question.items()]
    (out_dir / "report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else OUT
    result = run(out_dir)
    print(json.dumps(
        {k: result[k] for k in ("agreement", "kappa", "by_band", "majority_baseline",
                                "blinded", "ready")},
        indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
