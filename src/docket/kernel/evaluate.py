"""MAVT evaluator (design §7.2). Pure; seeded; creates sealed EvaluationRun + Result objects."""

from __future__ import annotations

import math

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.canon import content_hash, round6
from docket.errors import ValidationError
from docket.objects import is_content
from docket.store import Graph

Interval = tuple[float, float]
Triple = tuple[float, float, float]  # (point, lo, hi)


def _clean(x: float) -> float:
    """Normalise -0.0 to 0.0 so canonical JSON never encodes a signed zero."""
    x = float(x)
    return 0.0 if x == 0.0 else x


def _as_float(x, ctx: str) -> float:
    """Coerce x to a finite float or raise ValidationError — never AttributeError/ValueError."""
    if isinstance(x, bool) or not isinstance(x, int | float):
        raise ValidationError([f"{ctx}: expected a number, got {type(x).__name__}"])
    f = float(x)
    if not math.isfinite(f):
        raise ValidationError([f"{ctx}: must be finite, got {f}"])
    return f


def value_of(measure: dict, raw: float) -> float:
    mid = measure.get("id", "?")
    vf = measure.get("valueFunction") or {"kind": "identity"}
    if not isinstance(vf, dict):
        raise ValidationError(
            [f"measure {mid}: valueFunction must be an object, got {type(vf).__name__}"]
        )
    metric = measure.get("metric") or {}
    direction = metric.get("direction")
    if direction not in ("max", "min"):
        raise ValidationError(
            [f"measure {mid}: metric.direction must be 'max' or 'min', got {direction!r}"]
        )
    raw_f = _as_float(raw, f"measure {mid}: raw value")
    kind = vf.get("kind", "identity")
    if kind == "identity":
        return _clean(raw_f if direction == "max" else -raw_f)
    if kind == "linear":
        if "lo" not in vf or "hi" not in vf:
            raise ValidationError([f"measure {mid}: linear valueFunction requires lo and hi"])
        lo = _as_float(vf["lo"], f"measure {mid}: valueFunction.lo")
        hi = _as_float(vf["hi"], f"measure {mid}: valueFunction.hi")
        if lo == hi:
            raise ValidationError([f"measure {mid}: linear valueFunction lo must not equal hi"])
        v = min(1.0, max(0.0, (raw_f - lo) / (hi - lo)))
        return _clean(v if direction == "max" else 1.0 - v)
    if kind in ("binary", "step"):
        if "threshold" not in vf:
            raise ValidationError([f"measure {mid}: {kind} valueFunction requires threshold"])
        threshold = _as_float(vf["threshold"], f"measure {mid}: valueFunction.threshold")
        v = 1.0 if raw_f >= threshold else 0.0
        return _clean(v if direction == "max" else 1.0 - v)
    raise ValidationError([f"measure {mid}: unknown valueFunction kind {kind!r}"])


def score(values: dict[str, dict[str, float]], weights: dict[str, float]) -> dict[str, float]:
    """Additive value, summed in measure-id order.

    Floating addition is not associative, so summing in `weights`' own insertion order
    would make the result depend on the order the measures happened to be written into
    the WeightSet. `round6` hides that difference almost always — but "almost always" is
    not what a reproducibility claim means, so the order is fixed here rather than left
    to the caller's dict.
    """
    return {
        alt: _clean(round6(sum(weights[m] * values[alt][m] for m in sorted(weights))))
        for alt in sorted(values)
    }


def rank(scores: dict[str, float]) -> list[str]:
    return [a for a, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


def _resolve_uncertainty(g: Graph, o: dict) -> dict | None:
    """Validates o['uncertainty'] if present and returns the referenced Uncertainty object.

    Kernel 0.1.0 supports only interval propagation; distribution and scenarioSet
    uncertainties are refused, never silently ignored or misread as intervals.
    """
    u_id = o.get("uncertainty")
    if u_id is None:
        return None
    if not g.has(u_id):
        raise ValidationError([f"Observation {o['id']}: uncertainty {u_id} not found"])
    u = g.get(u_id)
    kind = u.get("kind")
    if kind == "distribution":
        raise ValidationError(["distribution propagation not implemented in kernel 0.1.0"])
    if kind == "scenarioSet":
        raise ValidationError(["scenarioSet propagation not implemented in kernel 0.1.0"])
    if kind != "interval":
        raise ValidationError([f"Observation {o['id']}: unknown uncertainty kind {kind!r}"])
    return u


def _triple_for(o: dict, uncertainty: dict | None) -> Triple:
    """The (point, lo, hi) to use for one Observation.

    A band never overwrites the point:
    - Observation.value is itself {lo, hi}: point = midpoint of that interval, and
      (lo, hi) = the interval itself.
    - Observation.value is a point with an interval-kind Uncertainty: the point stays
      the Observation's own value; (lo, hi) come from the Uncertainty's spec, purely
      as a band around that point.
    - Observation.value is a point with no Uncertainty: (lo, hi) = (point, point).
    """
    v = o["value"]
    oid = o.get("id", "?")
    if isinstance(v, dict):
        lo = _as_float(v.get("lo"), f"Observation {oid}: value.lo")
        hi = _as_float(v.get("hi"), f"Observation {oid}: value.hi")
        return (lo + hi) / 2, lo, hi
    point = _as_float(v, f"Observation {oid}: value")
    if uncertainty is None:
        return point, point, point
    spec = uncertainty.get("spec") or {}
    if "lo" not in spec or "hi" not in spec:
        raise ValidationError(
            [f"Observation {oid}: interval uncertainty spec requires lo and hi"]
        )
    lo = _as_float(spec["lo"], f"Observation {oid}: uncertainty spec.lo")
    hi = _as_float(spec["hi"], f"Observation {oid}: uncertainty spec.hi")
    return point, lo, hi


def _raw_field(o: dict) -> float | dict:
    """The Result.raw value: the Observation's own value, untouched by any band."""
    v = o["value"]
    oid = o.get("id", "?")
    if isinstance(v, dict):
        return {
            "lo": _clean(_as_float(v.get("lo"), f"Observation {oid}: value.lo")),
            "hi": _clean(_as_float(v.get("hi"), f"Observation {oid}: value.hi")),
        }
    return _clean(_as_float(v, f"Observation {oid}: value"))


def _lookup_observations(
    g: Graph, episode: dict, alternatives: list[str], measures: list[str]
) -> dict[str, dict[str, dict]]:
    """dict[alt][measure] -> Observation object.

    Raises ValidationError if an (alternative, measure) pair has zero or more than
    one Observation in the episode's register — a silent last-write-wins pick is
    exactly the failure mode this guards against.
    """
    by_key: dict[tuple[str, str], list[str]] = {}
    for oid in episode["observations"]:
        o = g.get(oid)
        by_key.setdefault((o["alternative"], o["measure"]), []).append(oid)
    out: dict[str, dict[str, dict]] = {}
    for a in alternatives:
        out[a] = {}
        for m in measures:
            ids = by_key.get((a, m), [])
            if not ids:
                raise ValidationError([f"no Observation for alternative {a} on measure {m}"])
            if len(ids) > 1:
                dupes = ", ".join(sorted(ids))
                raise ValidationError(
                    [f"multiple Observations for alternative {a} measure {m}: {dupes}"]
                )
            out[a][m] = g.get(ids[0])
    return out


def _observations_for_ids(
    g: Graph, obs_ids: list[str], alternatives: list[str], measures: list[str]
) -> dict[str, dict[str, dict]]:
    """dict[alt][measure] -> Observation object, from an explicit id list.

    The register-scanning sibling of `_lookup_observations`, for callers holding a run's
    sealed `observationIds` rather than an episode. Ids outside the given alternatives
    and measures are skipped; the same zero-or-many refusals apply to everything else, so
    a sealed id list that no longer covers its own step is a loud failure.
    """
    out: dict[str, dict[str, dict]] = {a: {} for a in alternatives}
    for oid in obs_ids:
        if not isinstance(oid, str) or not g.has(oid):
            raise ValidationError([f"Observation {oid!r} is not in the graph"])
        o = g.get(oid)
        a, m = o.get("alternative"), o.get("measure")
        if a not in out or m not in measures:
            continue
        if m in out[a]:
            dupes = ", ".join(sorted([out[a][m]["id"], oid]))
            raise ValidationError(
                [f"multiple Observations for alternative {a} measure {m}: {dupes}"]
            )
        out[a][m] = o
    for a in alternatives:
        for m in measures:
            if m not in out[a]:
                raise ValidationError([f"no Observation for alternative {a} on measure {m}"])
    return out


def _triples_from(g: Graph, obs: dict[str, dict[str, dict]]) -> dict[str, dict[str, Triple]]:
    return {
        a: {m: _triple_for(o, _resolve_uncertainty(g, o)) for m, o in row.items()}
        for a, row in obs.items()
    }


def collect_inputs(
    g: Graph, episode: dict, alternatives: list[str], measures: list[str]
) -> dict[str, dict[str, Triple]]:
    return _triples_from(g, _lookup_observations(g, episode, alternatives, measures))


def _points_and_bands(
    measures: dict[str, dict], triples: dict[str, dict[str, Triple]]
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, Interval]]]:
    """The valued point per (alt, measure), and the min/max-ordered valued band."""
    points: dict[str, dict[str, float]] = {}
    bands: dict[str, dict[str, Interval]] = {}
    for a, row in triples.items():
        points[a] = {}
        bands[a] = {}
        for m, (point, lo, hi) in row.items():
            lo_v, hi_v = value_of(measures[m], lo), value_of(measures[m], hi)
            points[a][m] = value_of(measures[m], point)
            bands[a][m] = (min(lo_v, hi_v), max(lo_v, hi_v))
    return points, bands


def inputs_hash_for(
    g: Graph, step: dict, weights: dict[str, float], obs_ids: list[str]
) -> str:
    """The `inputsHash` for one step, computed from the graph as it stands now.

    Everything a run's numbers depend on: the weights, the valued points and bands, the
    alternatives and measures, the identity *and content* of every Observation, and the
    measure definitions that turned raw values into value. Sealing it is what makes the
    run's inputs checkable later — recompute it and any change to a bound observation, a
    value function or a weight shows up, not just a change that happens to move the
    ranking.
    """
    measures = {m: g.get(m) for m in step["measures"]}
    obs = _observations_for_ids(g, obs_ids, step["alternatives"], step["measures"])
    points, bands = _points_and_bands(measures, _triples_from(g, obs))
    sorted_alts = sorted(step["alternatives"])
    sorted_measures = sorted(step["measures"])
    observation_ids = sorted({o["id"] for row in obs.values() for o in row.values()})
    return content_hash({
        "weights": weights,
        "points": {a: dict(points[a]) for a in sorted_alts},
        "bands": {a: {m: list(bands[a][m]) for m in bands[a]} for a in sorted_alts},
        "measures": sorted_measures,
        "alternatives": sorted_alts,
        "observations": [[oid, content_hash(g.get(oid))] for oid in observation_ids],
        "measureDefinitions": {
            m: {"metric": measures[m].get("metric"),
                "valueFunction": measures[m].get("valueFunction")}
            for m in sorted_measures
        },
    })


def check_weights(weights: dict, measures: list[str]) -> None:
    """The one rule for "is this a valid weight assignment over this exact set of ids":
    every id in `measures` present exactly once, no extras, every value a non-negative
    finite real, and the values sum to 1 within `1e-6`.

    Public (no leading underscore) so `agent.plan.author_weight_set` — the human route
    that authors a `WeightSet` before `propose_plan` has one to build a step from — can
    reuse this exact function rather than keep a second copy of the rule [plan 07
    Task weights]. `measures` is named for `evaluate_step`'s own caller below, where the
    ids really are measure ids; `author_weight_set` calls this with the episode's
    *objective* ids instead — the check is generic over "the reference id set", not
    measure-specific, so the parameter name is the only place that still says
    "measures" and the error messages below still say "measures" verbatim even when the
    caller means objectives, on purpose: one rule, one wording, never forked per caller.
    """
    if not isinstance(weights, dict):
        raise ValidationError(["weights must be an object"])
    extra = set(weights) - set(measures)
    if extra:
        raise ValidationError([f"weights name measures not in the step: {sorted(extra)}"])
    missing = set(measures) - set(weights)
    if missing:
        raise ValidationError([f"step measures without a weight: {sorted(missing)}"])
    bad = sorted(
        m for m, w in weights.items()
        if isinstance(w, bool) or not isinstance(w, int | float)
        or not math.isfinite(w) or w < 0
    )
    if bad:
        raise ValidationError([f"weights must be non-negative real numbers: {bad}"])
    total = sum(float(w) for w in weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValidationError([f"weights sum to {total}, not 1"])


def evaluate_step(
    g: Graph, plan_id: str, episode: dict, step: dict, *, seed: int, now: str
) -> tuple[dict, list[dict]]:
    """Validates and computes one step. Returns (run, results); writes nothing."""
    if step["method"] != "mavt":
        raise ValidationError(
            [f"method {step['method']} is not implemented in kernel {KERNEL_VERSION}; MAVT only"]
        )
    measures = {m: g.get(m) for m in step["measures"]}
    weights = g.get(step["weightSet"])["weights"]
    check_weights(weights, step["measures"])
    obs = _lookup_observations(g, episode, step["alternatives"], step["measures"])
    # One definition of "collect the inputs": the (point, lo, hi) triples come from
    # collect_inputs — the plan's published interface — rather than from a second,
    # drifting inline copy of the same resolve-uncertainty/triple logic. `obs` is read
    # alongside it only for the Observation ids and the untouched raw values a Result
    # records, neither of which is part of a triple.
    triples = collect_inputs(g, episode, step["alternatives"], step["measures"])
    points, bands = _points_and_bands(measures, triples)
    raw_fields: dict[str, dict[str, float | dict]] = {
        a: {m: _raw_field(o) for m, o in row.items()} for a, row in obs.items()
    }
    observation_ids = sorted({o["id"] for row in obs.values() for o in row.values()})

    # The point estimate never sees the band: ranking and the aggregate "value" are
    # Σ w·value_of(point) alone. The band only ever feeds the "uncertainty" fields.
    point_scores = score(points, weights)
    lo_scores = score(
        {a: {m: band[0] for m, band in row.items()} for a, row in bands.items()}, weights
    )
    hi_scores = score(
        {a: {m: band[1] for m, band in row.items()} for a, row in bands.items()}, weights
    )
    agg_bands = {a: (lo_scores[a], hi_scores[a]) for a in point_scores}

    run_id = f"run-{plan_id}-{step['id']}"
    sorted_alts = sorted(step["alternatives"])
    sorted_measures = sorted(step["measures"])
    inputs_hash = inputs_hash_for(g, step, weights, observation_ids)

    results: list[dict] = []
    for a in sorted_alts:
        for m in sorted_measures:
            lo_v, hi_v = bands[a][m]
            r = {
                "id": f"res-{run_id}-{a}-{m}", "type": "Result", "rev": 1,
                "createdBy": KERNEL_ACTOR, "createdAt": now,
                "run": run_id, "alternative": a, "measure": m, "aggregate": False,
                "value": _clean(round6(points[a][m])), "units": "value",
                "raw": raw_fields[a][m], "rawUnits": measures[m]["metric"]["units"],
                "method": "value-function",
            }
            if lo_v != hi_v:
                r["uncertainty"] = {"lo": _clean(round6(lo_v)), "hi": _clean(round6(hi_v))}
            results.append(r)
        lo_a, hi_a = agg_bands[a]
        agg = {
            "id": f"res-{run_id}-{a}", "type": "Result", "rev": 1,
            "createdBy": KERNEL_ACTOR, "createdAt": now,
            "run": run_id, "alternative": a, "aggregate": True,
            "value": _clean(point_scores[a]),
            "units": "weighted value", "method": "mavt-additive",
        }
        if lo_a != hi_a:
            agg["uncertainty"] = {"lo": _clean(round6(lo_a)), "hi": _clean(round6(hi_a))}
        results.append(agg)

    ids = [r["id"] for r in results]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValidationError([f"duplicate Result ids in step {step['id']}: {dupes}"])

    run = {
        "id": run_id, "type": "EvaluationRun", "rev": 1, "createdBy": KERNEL_ACTOR,
        "createdAt": now,
        "plan": plan_id, "step": step["id"], "evaluator": step["evaluator"],
        "evaluatorVersion": g.get(step["evaluator"])["definition"]["version"],
        "method": step["method"],
        "inputsHash": inputs_hash,
        "parameterBindings": {
            "weightSet": step["weightSet"], "weights": weights,
            "observationIds": observation_ids,
        },
        "seed": seed, "kernelVersion": KERNEL_VERSION, "outputs": ids,
        "outputHashes": [content_hash(r) for r in results],
        "ranking": rank(point_scores), "sealedAt": now, "sealedBy": "kernel",
    }
    run["runRecordHash"] = content_hash(run)
    return run, results


# The episode states in which computing against an approved plan is legitimate: the plan
# has passed G2, and the record has not since been voided, superseded or marked suspect.
G2_STATES = ("PLAN_APPROVED", "EVALUATED", "PENDING_SIGNATURE", "SIGNED")


def _require_plan_approval(plan: dict, episode: dict) -> None:
    """G2, enforced in the kernel and not only at the gate.

    `lifecycle.transition` is the gate a human drives, but nothing stopped a caller —
    `docket evaluate`, a script, the agent layer's dispatcher — from calling `evaluate()`
    straight past it. "Nothing is computed until a human approves the plan" is the
    load-bearing claim of the whole architecture, so the numeric path refuses for itself
    rather than trusting that someone else checked.
    """
    if not is_content(plan.get("approvedBy")):
        raise ValidationError(
            [f"plan {plan.get('id')!r} has not been approved: G2 requires a human "
             f"approval on Plan.approvedBy before anything is computed"]
        )
    state = episode.get("lifecycleState")
    if state not in G2_STATES:
        raise ValidationError(
            [f"episode {episode.get('id')!r} is at lifecycleState {state!r}; evaluation "
             f"requires one of {', '.join(G2_STATES)}"]
        )


def _require_store_integrity(g: Graph) -> None:
    """Nothing is computed on a store whose own integrity is in question.

    The gates consult `WHOLE_STORE_RULES` on every edge; `evaluate()` is the other way
    into the numeric path — `docket evaluate`, the dispatcher, a script — and a claim
    that a forged authorship line "holds every gate shut" is worth nothing if the
    computation the gates guard can still be run around them [T9 review C1]. A broken
    log chain or an authorship line the store cannot vouch for refuses evaluation here,
    naming what it found.

    Imported inside the function: `kernel.validate` imports `inputs_hash_for` from this
    module, so a module-level import would be a cycle.
    """
    from docket.kernel.lifecycle import whole_store_blockers

    blockers = whole_store_blockers(g)
    if blockers:
        raise ValidationError(
            ["the store does not vouch for itself, so nothing may be computed from it: "
             + "; ".join(blockers)]
        )


def evaluate(g: Graph, plan_id: str, *, seed: int, now: str) -> list[dict]:
    if not isinstance(plan_id, str) or not g.has(plan_id):
        raise ValidationError([f"plan {plan_id!r} is not in the graph"])
    plan = g.get(plan_id)
    episode_id = plan.get("episode")
    if not isinstance(episode_id, str) or not g.has(episode_id):
        raise ValidationError(
            [f"plan {plan_id!r} names episode {episode_id!r}, which is not in the graph"]
        )
    episode = g.get(episode_id)
    _require_plan_approval(plan, episode)
    _require_store_integrity(g)

    # The plan names the episode; the episode must not name a *different* plan. A
    # missing or gapped `episode.plan` is still allowed in kernel 0.1.0 (03b's
    # lifecycle gate is where the plan becomes mandatory), but a contradiction
    # between the two is a refusal: appending runs to an episode that disowns the
    # plan they came from would leave the record self-inconsistent.
    named_plan = episode.get("plan")
    if is_content(named_plan) and named_plan != plan_id:
        raise ValidationError(
            [f"episode {episode['id']} names a different plan: {named_plan!r}, not {plan_id!r}"]
        )

    # Validate and compute every step before writing anything: a failure on step N
    # must never leave step 1..N-1's Results or run half-written into the graph.
    prepared = [
        evaluate_step(g, plan_id, episode, step, seed=seed, now=now)
        for step in plan["steps"]
    ]

    # A single step's own Result ids are checked for collisions inside evaluate_step,
    # above. That does not catch two *different* steps generating the same ids (e.g.
    # a Plan with a repeated step id) — check the union across every prepared step
    # before any write, so a cross-step collision is a named refusal, not a partial
    # write followed by the store rejecting the second step's revision-1 objects.
    all_ids: list[str] = []
    for run, results in prepared:
        all_ids.append(run["id"])
        all_ids.extend(r["id"] for r in results)
    if len(all_ids) != len(set(all_ids)):
        dupes = sorted({i for i in all_ids if all_ids.count(i) > 1})
        raise ValidationError([f"duplicate ids across plan steps: {dupes}"])

    # ...and the third check the other two do not make: an id this run would write
    # that something else already occupies. Without it, step 1's run and Results are
    # written, step 2's first `put` is rejected by the store's append-only rule, and
    # the episode revision that would have listed the runs never happens — leaving a
    # sealed run in the store that no episode references.
    existing = sorted(i for i in all_ids if g.has(i))
    if existing:
        raise ValidationError([f"ids already present in the graph: {existing}"])

    runs: list[dict] = []
    for run, results in prepared:
        for r in results:
            g.put(r, KERNEL_ACTOR)
        g.put(run, KERNEL_ACTOR)
        runs.append(run)
    ep = g.get(episode["id"])
    ep_new = {**ep, "rev": ep["rev"] + 1, "createdBy": KERNEL_ACTOR, "createdAt": now,
              "runs": ep["runs"] + [r["id"] for r in runs]}
    g.put(ep_new, KERNEL_ACTOR)
    return runs
