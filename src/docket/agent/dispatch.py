# src/docket/agent/dispatch.py
"""Stage X: the agent hands an approved Plan to the kernel and reads results back by id.

`dispatch()` calls `kernel.evaluate.evaluate()` and `kernel.flip.flip_analysis()` and
returns exactly what they hand back: object ids and the dicts the kernel itself sealed.
`read_back()` copies stored fields into a flat dict for a caller (plan 07's API, and
`docket agent narrate`) that wants a run's results and flips without knowing the graph's
shape. Neither function does any arithmetic — a reviewer can confirm that claim by
reading this file; `tests/agent/test_dispatch.py` confirms it mechanically too, by
parsing the module for arithmetic operators.

G2 is enforced twice on purpose, and only once in the kernel. `kernel.evaluate.
_require_plan_approval` refuses inside `evaluate()` itself [ruling R12] — `docket
evaluate`, a script, and this module are all callers, and "nothing is computed until a
human approves the plan" cannot depend on any one of them remembering to check first.
This module keeps its own check anyway, ahead of the kernel's, purely because it can give
the clearer error: it knows it is the agent path, and it can name the gate (G2) rather
than a schema field. `G2_STATES` is imported from `kernel.evaluate` rather than restated,
so if 03b ever changes the tuple this function follows without edit.

The `actor` this module is called with is never written anywhere. `evaluate()` and
`flip_analysis()` write every EvaluationRun, Result and FlipAnalysis as `KERNEL_ACTOR`
regardless of who asked for the computation, and `dispatch`/`read_back` write nothing of
their own — they only call the kernel and copy back what it returns. An agent actor is
allowed to call `dispatch`: asking the kernel to compute is not itself a numeric act, and
the kernel's own authority boundary (`Graph.put` refusing an agent revision that carries
`approvedBy` or changes `lifecycleState`) is what actually keeps a number from entering
the record without a human behind it. `actor` is accepted only so a caller (the CLI, or
plan 07's API) has someone to name in a log line.

`dispatch()` runs the kernel but never transitions the episode to `EVALUATED`.
`kernel.lifecycle.EVALUATED` sits on neither `HUMAN_ONLY` nor `KERNEL_ONLY`, but
`Graph.put` refuses an agent revision that changes `lifecycleState` at all, so the move is
always a human's (or, if a later plan makes it one, the kernel's) to drive — never this
module's. Plan 07's stage flow must call `kernel.lifecycle.transition(g, episode_id,
"EVALUATED", <human actor>, now=...)` itself after a successful dispatch, or the
Readiness screen sits behind a gate nobody drove.
"""

from __future__ import annotations

import logging

from docket.errors import AuthorityViolation, ValidationError
from docket.kernel.evaluate import G2_STATES, evaluate
from docket.kernel.flip import flip_analysis
from docket.objects import is_content
from docket.store import Graph

__all__ = ["dispatch", "read_back"]

log = logging.getLogger("docket.agent.dispatch")


def dispatch(g: Graph, plan_id: str, *, actor: dict, seed: int, now: str) -> dict:
    """Hand an approved Plan to the kernel; return its sealed runs and flip analyses.

    Returns `{"runs": [<EvaluationRun>, ...], "flips": [<FlipAnalysis>, ...]}` — the
    stored objects exactly as the kernel wrote them, not `list[dict]` [pre-flight
    defect 8]. Refuses (`AuthorityViolation`) before calling the kernel at all if the
    named plan has not been approved by a human, or if the episode has not passed G2.
    """
    if not isinstance(actor, dict) or actor.get("actorType") not in ("agent", "human") \
            or not is_content(actor.get("actorId")):
        raise ValidationError(
            [f"dispatch: actor must be an agent or human actor with an actorId, got {actor!r}"]
        )
    plan = g.get(plan_id)
    episode = g.get(plan["episode"])
    if not is_content(plan.get("approvedBy")):
        raise AuthorityViolation(
            f"plan {plan_id!r} has not been approved: G2 requires a human approval on "
            f"Plan.approvedBy before the agent may dispatch anything to the kernel"
        )
    if episode.get("lifecycleState") not in G2_STATES:
        raise AuthorityViolation(
            f"episode {episode['id']!r} is at lifecycleState "
            f"{episode.get('lifecycleState')!r}; the agent may dispatch only after G2 "
            f"(one of {', '.join(G2_STATES)})"
        )
    log.info("actor %r dispatching plan %r (seed=%r)", actor.get("actorId"), plan_id, seed)
    runs = evaluate(g, plan_id, seed=seed, now=now)
    flips: list[dict] = []
    for r in runs:
        flips.extend(flip_analysis(g, r["id"], seed=seed, now=now))
    return {"runs": runs, "flips": flips}


def read_back(g: Graph, run_id: str) -> dict:
    """Object ids and copied kernel values for one sealed EvaluationRun.

    Every value here is read straight off the stored object it names — `g.get(result_id)
    ["value"]` and so on — never rounded, scaled, reformatted or aggregated again. The
    flip label lives at `parameter.label`, not at the top level [pre-flight defect 9].
    """
    run = g.get(run_id)

    results: dict[str, dict] = {}
    for rid in run["outputs"]:
        r = g.get(rid)
        entry = {"alternative": r["alternative"], "value": r["value"], "units": r["units"]}
        if r.get("measure"):
            entry["measure"] = r["measure"]
        entry["aggregate"] = r["aggregate"]
        # `valueText`: the exact string `kernel.render` already prints for this same
        # value (`f"{res.get('value')} {res.get('units')}"` — plain `str()`, no
        # formatting) — plan 07 Task 7 fix round, I2: a `JSON.parse`d float re-strung by
        # the browser turns `36.0` into `"36"`; a canonical text form copied from here
        # means `<Num>` never has to reparse-and-restring a number the kernel already
        # rendered once. Not arithmetic on the value — `str()` is a plain type
        # conversion, the same thing an f-string already does implicitly.
        entry["valueText"] = str(r["value"])
        results[rid] = entry

    episode = g.get(g.get(run["plan"])["episode"])
    flips = []
    for fid in episode["flipAnalyses"]:
        fa = g.get(fid)
        if fa["run"] != run_id:
            continue
        flips.append({
            "id": fid,
            "label": fa["parameter"]["label"],
            "kind": fa["parameter"]["kind"],
            "target": fa["parameter"]["target"],
            "flipThreshold": fa["flipThreshold"],
            "flipDistance": fa["flipDistance"],
            "direction": fa["direction"],
        })
    flips.sort(key=lambda f: f["id"])

    return {
        "run": run_id,
        "ranking": list(run["ranking"]),
        "results": results,
        "flips": flips,
        "seed": run["seed"],
        "kernelVersion": run["kernelVersion"],
    }
