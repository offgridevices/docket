"""'What flips the decision' (design §7.3): one-at-a-time sweeps with bisection, plus
weight-simplex robustness."""

from __future__ import annotations

import random
from collections.abc import Callable

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.canon import round6
from docket.errors import ValidationError
from docket.kernel.evaluate import (
    _clean,
    _observations_for_ids,
    _resolve_uncertainty,
    inputs_hash_for,
    rank,
    score,
    value_of,
)
from docket.store import Graph


def perturb_weights(weights: dict[str, float], target: str, x: float) -> dict[str, float]:
    # A single-weight WeightSet has nothing to rescale into: moving the one weight away
    # from 1.0 cannot be compensated anywhere, so the result would not sum to 1.
    # flip_analysis already skips these; refusing here keeps the public function from
    # handing a caller a silently non-normalised vector.
    if len(weights) < 2:
        raise ValidationError(
            ["perturb_weights needs at least two weights: a single weight cannot be rescaled"]
        )
    rest = 1.0 - weights[target]
    out = {}
    for m, w in weights.items():
        if m == target:
            out[m] = x
        else:
            out[m] = (w / rest) * (1.0 - x) if rest > 0 else (1.0 - x) / (len(weights) - 1)
    return out


def find_flip(
    f: Callable[[float], str], lo: float, hi: float, current: float,
    *, grid: int = 1000, tol: float = 1e-9,
) -> tuple[float | None, str]:
    """Bisect to the flip point. The tolerance is three orders finer than the `round6`
    the stored threshold is rounded to, so a threshold that is exactly 0.75 stores as
    0.75 rather than as the ragged 0.749999 a 1e-6 bisection leaves behind."""
    base = f(current)
    best: tuple[float | None, str] = (None, "none")
    for direction, end in (("up", hi), ("down", lo)):
        if end == current:
            continue
        step = (end - current) / grid
        prev = current
        found = None
        for i in range(1, grid + 1):
            x = current + step * i
            if f(x) != base:
                found = (prev, x)
                break
            prev = x
        if found is None:
            continue
        a, b = found
        while abs(b - a) > tol:
            mid = (a + b) / 2
            if f(mid) == base:
                a = mid
            else:
                b = mid
        thr = b
        if best[0] is None or abs(thr - current) < abs(best[0] - current):
            best = (thr, direction)
    return best


def _values_for_ids(
    g: Graph, obs_ids: list[str], step: dict,
) -> tuple[dict[str, dict[str, float]], dict[str, dict], dict[str, str]]:
    """values[alt][measure] (midpoints), measures, and obs id lookup for exactly the
    given observation ids, restricted to the step's alternatives/measures.

    Raises ValidationError on two ids landing on the same (alternative, measure) pair
    — a silent last-write-wins pick is exactly the failure mode this guards against,
    mirroring evaluate._lookup_observations' own duplicate check.
    """
    measures = {m: g.get(m) for m in step["measures"]}
    values: dict[str, dict[str, float]] = {a: {} for a in step["alternatives"]}
    obs_lookup: dict[str, str] = {}
    seen: dict[tuple[str, str], str] = {}
    for oid in obs_ids:
        o = g.get(oid)
        if o["alternative"] not in values or o["measure"] not in measures:
            continue
        key = (o["alternative"], o["measure"])
        if key in seen:
            raise ValidationError([
                f"multiple Observations for alternative {key[0]} measure {key[1]} "
                f"among run inputs: {seen[key]}, {oid}",
            ])
        seen[key] = oid
        v = o["value"]
        raw = (v["lo"] + v["hi"]) / 2 if isinstance(v, dict) else float(v)
        values[o["alternative"]][o["measure"]] = raw
        obs_lookup[f"{o['alternative']}|{o['measure']}"] = oid
    return values, measures, obs_lookup


def _run_inputs(g: Graph, run: dict, step: dict, episode: dict) -> tuple[dict, list[str]]:
    """The weights and Observation ids a sealed run was grounded in.

    The run's own bindings are the source of truth, not whatever the WeightSet or the
    episode register happen to say now: a WeightSet revised after sealing, or an
    Observation added to the register afterwards, must not silently change what an
    analysis attached to that run is grounded in. Only a run that itself lacks a
    binding (a pre-kernel-0.1.0 shape) falls back to live state. Every consumer —
    flip_analysis and flip_summary alike — reads its inputs through here, so there is
    one definition of "what this run was computed from".

    Binding the *ids* is not enough on its own: they resolve against the graph as it
    stands now, so a human revising an Observation's value after sealing would move the
    analysis without moving an id. The run's `inputsHash` is recomputed here and any
    difference refuses outright — that covers a revised observation, a revised value
    function and a revised weight alike, including the revisions that leave the ranking
    where it was and would otherwise pass unnoticed.
    """
    pb = run.get("parameterBindings") or {}
    sealed_weights = pb.get("weights")
    if sealed_weights is not None:
        weights = dict(sealed_weights)
    else:
        weights = dict(g.get(step["weightSet"])["weights"])
    sealed_obs_ids = pb.get("observationIds")
    obs_ids = list(sealed_obs_ids) if sealed_obs_ids is not None else list(episode["observations"])

    sealed_inputs_hash = run.get("inputsHash")
    if isinstance(sealed_inputs_hash, str):
        if inputs_hash_for(g, step, weights, obs_ids) != sealed_inputs_hash:
            raise ValidationError(
                ["sealed run inputs have changed since sealing (inputsHash mismatch)"]
            )
    else:
        # No sealed hash to check against (a pre-kernel-0.1.0 run). Resolve the ids
        # through the same helper the hash path uses anyway, so an id list that is short
        # of a pair, or names two Observations for one, is a named refusal here rather
        # than a KeyError out of the middle of the sweep. This is the only route left
        # into the analysis that the hash guard does not cover.
        _observations_for_ids(g, obs_ids, step["alternatives"], step["measures"])
    return weights, obs_ids


def _top(values_raw, measures, weights) -> str:
    valued = {
        a: {m: value_of(measures[m], r) for m, r in row.items()} for a, row in values_raw.items()
    }
    return rank(score(valued, weights))[0]


def _ranking(values_raw, measures, weights) -> list[str]:
    valued = {
        a: {m: value_of(measures[m], r) for m, r in row.items()} for a, row in values_raw.items()
    }
    return rank(score(valued, weights))


def _obs_range(g: Graph, o: dict, step: dict) -> tuple[float, float, str]:
    v = o["value"]
    if isinstance(v, dict):
        return float(v["lo"]), float(v["hi"]), "uncertainty"
    # Reuses evaluate._resolve_uncertainty so a distribution/scenarioSet Uncertainty on
    # a swept observation refuses loudly, exactly as it would inside evaluate() itself,
    # rather than being silently skipped in favour of a sweep/default range.
    u = _resolve_uncertainty(g, o)
    if u is not None:
        return float(u["spec"]["lo"]), float(u["spec"]["hi"]), "uncertainty"
    for sw in step.get("sensitivitySweeps", []) or []:
        if sw["kind"] == "observation" and sw["target"] == o["id"] and sw.get("range"):
            return float(sw["range"]["lo"]), float(sw["range"]["hi"]), "sweep"
    x = float(v)
    half = abs(x) * 0.5 if x != 0 else 1.0
    return x - half, x + half, "default"


def _weight_range(step: dict, target: str) -> tuple[float, float, str]:
    for sw in step.get("sensitivitySweeps", []) or []:
        if sw["kind"] == "weight" and sw["target"] == target and sw.get("range"):
            return float(sw["range"]["lo"]), float(sw["range"]["hi"]), "sweep"
    return 0.0, 1.0, "default"


def flip_analysis(g: Graph, run_id: str, *, seed: int, now: str) -> list[dict]:
    run = g.get(run_id)
    plan = g.get(run["plan"])
    step = next(s for s in plan["steps"] if s["id"] == run["step"])
    episode = g.get(plan["episode"])

    weights, obs_ids = _run_inputs(g, run, step, episode)

    values, measures, obs_lookup = _values_for_ids(g, obs_ids, step)

    base_rank = _ranking(values, measures, weights)
    if base_rank != run["ranking"]:
        raise ValidationError(["flip analysis baseline does not reproduce the sealed run ranking"])

    bindings = {}
    for aid in episode["assumptions"]:
        a = g.get(aid)
        pbind = a.get("parameterBinding")
        if pbind:
            bindings[pbind["target"]] = aid

    params: list[dict] = []
    for m in step["measures"]:
        # A single-weight WeightSet has nothing to rescale into: perturbing the one
        # weight away from 1.0 cannot be compensated by any other weight, so there is
        # no meaningful flip to analyse.
        if m in weights and len(weights) > 1:
            target = f"{step['weightSet']}:{m}"
            lo, hi, wsrc = _weight_range(step, target)
            params.append({
                "kind": "weight", "target": target,
                "label": f"weight on {measures[m]['measure']}",
                "current": weights[m], "lo": lo, "hi": hi, "source": wsrc, "measure": m,
            })
    for oid in obs_ids:
        o = g.get(oid)
        key = f"{o['alternative']}|{o['measure']}"
        if key not in obs_lookup or o["measure"] not in measures:
            continue
        bound = oid in bindings
        swept = any(
            sw["kind"] == "observation" and sw["target"] == oid
            for sw in step.get("sensitivitySweeps", []) or []
        )
        if o.get("variedInSensitivity") or bound or swept:
            lo, hi, src = _obs_range(g, o, step)
            current = values[o["alternative"]][o["measure"]]
            # A recorded range that doesn't bracket the observation's own current
            # value would hand find_flip a search interval that excludes its own
            # starting point; widen to include it, without relabelling its source.
            lo, hi = min(lo, current), max(hi, current)
            params.append({
                "kind": "observation", "target": oid,
                "label": f"{o['alternative']} on {measures[o['measure']]['measure']}",
                "current": current, "lo": lo, "hi": hi,
                "source": src, "alt": o["alternative"], "measure": o["measure"],
            })
    flips = []
    for n, p in enumerate(params, start=1):
        if p["kind"] == "weight":
            def f(x, p=p):
                return _top(values, measures, perturb_weights(weights, p["measure"], x))
        else:
            def f(x, p=p):
                v2 = {a: dict(r) for a, r in values.items()}
                v2[p["alt"]][p["measure"]] = x
                return _top(v2, measures, weights)
        thr, direction = find_flip(f, p["lo"], p["hi"], p["current"])
        after = None
        if thr is not None:
            if p["kind"] == "weight":
                after = _ranking(values, measures, perturb_weights(weights, p["measure"], thr))
            else:
                v2 = {a: dict(r) for a, r in values.items()}
                v2[p["alt"]][p["measure"]] = thr
                after = _ranking(v2, measures, weights)
        span = p["hi"] - p["lo"]
        fa = {
            "id": f"flip-{run_id}-{n}", "type": "FlipAnalysis", "rev": 1,
            "createdBy": KERNEL_ACTOR, "createdAt": now,
            "run": run_id,
            "parameter": {"kind": p["kind"], "target": p["target"], "label": p["label"]},
            "currentValue": _clean(round6(p["current"])),
            "range": {
                "lo": _clean(round6(p["lo"])), "hi": _clean(round6(p["hi"])),
                "source": p["source"],
            },
            "flipThreshold": None if thr is None else _clean(round6(thr)),
            "flipDistance": (
                None if thr is None or span == 0
                else _clean(round6(abs(thr - p["current"]) / span))
            ),
            "direction": direction, "rankingBefore": base_rank, "rankingAfter": after,
            "kernelVersion": KERNEL_VERSION,
        }
        if p["target"] in bindings:
            fa["assumption"] = bindings[p["target"]]
        g.put(fa, KERNEL_ACTOR)
        flips.append(fa)
    if flips:
        ep = g.get(episode["id"])
        g.put({
            **ep, "rev": ep["rev"] + 1, "createdBy": KERNEL_ACTOR, "createdAt": now,
            "flipAnalyses": ep["flipAnalyses"] + [f["id"] for f in flips],
        }, KERNEL_ACTOR)
    return flips


def flip_summary(
    g: Graph, run_id: str, *, seed: int, now: str, n_simplex: int | None = None,
) -> dict:
    run = g.get(run_id)
    plan = g.get(run["plan"])
    step = next(s for s in plan["steps"] if s["id"] == run["step"])
    episode = g.get(plan["episode"])
    policy = g.get(g.get(episode["charter"])["decisionClassPolicy"])
    n = policy["nSimplex"] if n_simplex is None else n_simplex
    if n < 1:
        raise ValidationError(["nSimplex must be ≥ 1"])
    # The simplex draws are attached to this run and printed next to it, so they must
    # be drawn over the run's own bound inputs — not over whatever the episode's
    # observation register holds now — and the baseline at the sealed weights must
    # still reproduce the run's recorded ranking. A robustness figure computed from
    # inputs the run never used would contradict the run it is presented with.
    weights, obs_ids = _run_inputs(g, run, step, episode)
    values, measures, _ = _values_for_ids(g, obs_ids, step)
    if _ranking(values, measures, weights) != run["ranking"]:
        raise ValidationError(
            ["sealed run ranking cannot be reproduced from its bound observations"]
        )
    ms = list(step["measures"])
    rng = random.Random(seed)
    counts = {a: 0 for a in step["alternatives"]}
    for _ in range(n):
        draws = [rng.expovariate(1.0) for _ in ms]
        tot = sum(draws)
        w = {m: d / tot for m, d in zip(ms, draws, strict=True)}
        counts[_top(values, measures, w)] += 1
    all_flips = (g.get(i) for i in g.get(episode["id"])["flipAnalyses"])
    flips = [f for f in all_flips if f["run"] == run_id]
    ranked = sorted(
        flips,
        key=lambda f: (
            f["flipDistance"] is None,
            f["flipDistance"] if f["flipDistance"] is not None else 0.0,
            f["id"],
        ),
    )
    return {
        "run": run_id, "ranked": [f["id"] for f in ranked],
        "simplexRobustness": {a: _clean(round6(c / n)) for a, c in sorted(counts.items())},
        "nSimplex": n, "seed": seed,
    }
