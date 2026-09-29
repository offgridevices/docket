# tests/kernel/test_determinism.py
"""Property tests for the kernel's determinism claim (design §7).

The design says every kernel function is property-tested for determinism — same input,
identical bytes — in CI. The example tests elsewhere pin particular graphs; these draw
the graph instead, so the claim is made against inputs nobody chose by hand: value
functions of every supported kind, either direction, bands or no bands, weights that may
put zero on a measure, and values spanning six orders of magnitude either side of zero.

`derandomize=True` keeps CI stable: the same examples are drawn every run, so a failure
is reproducible from the test name alone.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from docket.canon import canonical_json
from docket.kernel.evaluate import evaluate, score, value_of
from docket.kernel.flip import flip_analysis
from docket.store import Graph
from tests.kernel.conftest import (
    alternative,
    assert_history_honest,
    charter,
    drs,
    episode,
    evidence,
    gap,
    measure,
    model,
    obj,
    objective,
    observation,
    plan_approved,
    policy,
    put_all,
)

NOW = "2026-09-04T00:00:00Z"
SEED = 5

_finite = dict(allow_nan=False, allow_infinity=False, allow_subnormal=False)


@st.composite
def value_functions(draw):
    kind = draw(st.sampled_from(["identity", "linear", "binary", "step"]))
    if kind == "identity":
        return {"kind": "identity"}
    if kind == "linear":
        lo = draw(st.integers(-1000, 1000))
        hi = draw(st.integers(-1000, 1000).filter(lambda h: h != lo))
        return {"kind": "linear", "lo": lo, "hi": hi}
    return {"kind": kind, "threshold": draw(st.integers(-1000, 1000))}


@st.composite
def specs(draw):
    """One drawn evaluation problem: alternatives, measures, value functions, weights
    that sum to 1, an observation per pair, and optional symmetric bands."""
    n_alt = draw(st.integers(min_value=2, max_value=4))
    n_measure = draw(st.integers(min_value=1, max_value=3))
    alts = [f"alt-{i}" for i in range(n_alt)]
    measures = [f"m-{j}" for j in range(n_measure)]

    shares = draw(
        st.lists(st.integers(0, 100), min_size=n_measure, max_size=n_measure)
        .filter(lambda xs: sum(xs) > 0)
    )
    total = float(sum(shares))
    weights = {m: s / total for m, s in zip(measures, shares, strict=True)}

    definitions = {}
    for m in measures:
        definitions[m] = {
            "direction": draw(st.sampled_from(["max", "min"])),
            "valueFunction": draw(value_functions()),
        }

    values, bands = {}, {}
    for a in alts:
        for m in measures:
            values[(a, m)] = draw(st.floats(min_value=-1e6, max_value=1e6, **_finite))
            bands[(a, m)] = draw(
                st.one_of(st.none(), st.floats(min_value=0.0, max_value=1000.0, **_finite))
            )
    return {"alternatives": alts, "measures": measures, "weights": weights,
            "definitions": definitions, "values": values, "bands": bands}


def graph_from(spec: dict) -> Graph:
    """Build a fresh, schema-valid graph from a drawn spec. Called twice per example, so
    that "the same input" means two independent builds rather than one shared object."""
    g = Graph()
    put_all(g, policy(), evidence("ev-doc"), drs(), charter(),
            objective("obj-1", measures=spec["measures"]),
            gap("gap-vva", confirmed=True),
            model("mdl-1", vva={"$gap": "gap-vva"}),
            episode())
    for m in spec["measures"]:
        d = spec["definitions"][m]
        put_all(g, measure(m, "obj-1",
                           metric={"units": "u", "direction": d["direction"]},
                           valueFunction=d["valueFunction"]))
    for i, a in enumerate(spec["alternatives"], start=1):
        put_all(g, alternative(a, baseline=(i == 1), order=i))

    observation_ids = []
    first = True
    for a in spec["alternatives"]:
        for m in spec["measures"]:
            oid = f"ob-{a}-{m}"
            half = spec["bands"][(a, m)]
            extra = {}
            if half is not None:
                v = spec["values"][(a, m)]
                unc_id = f"unc-{a}-{m}"
                put_all(g, obj(unc_id, "Uncertainty", kind="interval",
                               spec={"lo": v - half, "hi": v + half}))
                extra["uncertainty"] = unc_id
            if first:
                # One swept observation is enough to exercise the observation half of the
                # flip search; sweeping all of them multiplies the bisection cost by the
                # size of the drawn problem for no extra coverage.
                extra["variedInSensitivity"] = True
                first = False
            put_all(g, observation(oid, a, m, spec["values"][(a, m)], **extra))
            observation_ids.append(oid)

    put_all(
        g,
        obj("ws-1", "WeightSet", name="w", method="stated", weights=spec["weights"],
            provenance="ev-doc"),
        obj("pl-1", "Plan", episode="ep-1", policyBasis="pol-1",
            approvedBy={"actorId": "fixture", "date": "2026"},
            steps=[{"id": "s1", "evaluator": "mdl-1", "method": "mavt",
                    "alternatives": spec["alternatives"], "measures": spec["measures"],
                    "weightSet": "ws-1",
                    "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}]),
        {**g.get("ep-1"), "rev": 2, **plan_approved(),
         "alternatives": spec["alternatives"],
         "observations": observation_ids, "weightSets": ["ws-1"], "models": ["mdl-1"],
         "plan": "pl-1", "objectives": ["obj-1"]},
    )
    return g


@given(spec=specs())
@settings(max_examples=60, deadline=None, derandomize=True,
          suppress_health_check=[HealthCheck.too_slow])
def test_evaluate_is_byte_identical_across_two_independent_builds(spec):
    g_a, g_b = graph_from(spec), graph_from(spec)
    runs_a = evaluate(g_a, "pl-1", seed=SEED, now=NOW)
    runs_b = evaluate(g_b, "pl-1", seed=SEED, now=NOW)
    assert canonical_json(runs_a) == canonical_json(runs_b)
    assert g_a.snapshot_hash() == g_b.snapshot_hash()


@given(spec=specs())
@settings(max_examples=60, deadline=None, derandomize=True,
          suppress_health_check=[HealthCheck.too_slow])
def test_flip_analysis_is_byte_identical_across_two_independent_builds(spec):
    g_a, g_b = graph_from(spec), graph_from(spec)
    run_a = evaluate(g_a, "pl-1", seed=SEED, now=NOW)[0]
    run_b = evaluate(g_b, "pl-1", seed=SEED, now=NOW)[0]
    flips_a = flip_analysis(g_a, run_a["id"], seed=SEED, now=NOW)
    flips_b = flip_analysis(g_b, run_b["id"], seed=SEED, now=NOW)
    assert canonical_json(flips_a) == canonical_json(flips_b)
    assert g_a.snapshot_hash() == g_b.snapshot_hash()


@st.composite
def scoring_problems(draw):
    """values[alt][measure] and matching weights, plus a permutation of the measure keys
    to re-insert them in a different order."""
    n_alt = draw(st.integers(min_value=2, max_value=4))
    n_measure = draw(st.integers(min_value=1, max_value=4))
    alts = [f"alt-{i}" for i in range(n_alt)]
    measures = [f"m-{j}" for j in range(n_measure)]
    shares = draw(
        st.lists(st.integers(0, 100), min_size=n_measure, max_size=n_measure)
        .filter(lambda xs: sum(xs) > 0)
    )
    total = float(sum(shares))
    weights = {m: s / total for m, s in zip(measures, shares, strict=True)}
    values = {a: {m: draw(st.floats(min_value=-1e3, max_value=1e3, **_finite))
                  for m in measures} for a in alts}
    order = draw(st.permutations(measures))
    return values, weights, list(order)


@given(problem=scoring_problems())
@settings(max_examples=60, deadline=None, derandomize=True)
def test_score_is_invariant_to_the_key_order_of_weights_and_measures(problem):
    values, weights, order = problem
    shuffled_weights = {m: weights[m] for m in order}
    shuffled_values = {a: {m: row[m] for m in order} for a, row in values.items()}
    assert score(values, weights) == score(shuffled_values, shuffled_weights)


@given(
    raw=st.floats(min_value=-1e6, max_value=1e6, **_finite),
    direction=st.sampled_from(["max", "min"]),
    vf=value_functions(),
)
@settings(max_examples=60, deadline=None, derandomize=True)
def test_value_of_is_invariant_to_the_key_order_of_the_measure_dict(raw, direction, vf):
    forwards = {"id": "m-1", "metric": {"units": "u", "direction": direction},
                "valueFunction": vf}
    backwards = {k: forwards[k] for k in reversed(list(forwards))}
    assert value_of(forwards, raw) == value_of(backwards, raw)


def test_the_strategy_actually_builds_a_scorable_graph():
    """A guard on the generator itself: if `graph_from` silently stopped producing a
    runnable plan, the property tests above would pass vacuously."""
    spec = {"alternatives": ["alt-0", "alt-1"], "measures": ["m-0"],
            "weights": {"m-0": 1.0},
            "definitions": {"m-0": {"direction": "max", "valueFunction": {"kind": "identity"}}},
            "values": {("alt-0", "m-0"): 2.0, ("alt-1", "m-0"): 1.0},
            "bands": {("alt-0", "m-0"): None, ("alt-1", "m-0"): None}}
    g = graph_from(spec)
    assert_history_honest(g)
    run = evaluate(g, "pl-1", seed=SEED, now=NOW)[0]
    assert run["ranking"] == ["alt-0", "alt-1"]
    assert g.get("ep-1")["createdBy"]["actorType"] == "kernel"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
