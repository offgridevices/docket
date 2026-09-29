# tests/kernel/test_flip.py
import copy
import math

import pytest

from docket import KERNEL_ACTOR
from docket.canon import canonical_json, round6
from docket.errors import ValidationError
from docket.kernel.evaluate import evaluate, rank, score, value_of
from docket.kernel.flip import find_flip, flip_analysis, flip_summary, perturb_weights
from docket.kernel.validate import validate
from tests.kernel.conftest import (
    H,
    alternative,
    assert_history_honest,
    gap,
    measure,
    model,
    obj,
    objective,
    observation,
    plan_approved,
    put_all,
)

NOW = "2026-09-04T00:00:00Z"


def test_perturb_weights_rescales_others():
    w = perturb_weights({"a": 0.5, "b": 0.3, "c": 0.2}, "a", 0.8)
    assert abs(sum(w.values()) - 1) < 1e-9
    assert abs(w["b"] - 0.12) < 1e-9
    assert abs(w["c"] - 0.08) < 1e-9


def test_find_flip_bisection():
    f = lambda x: "A" if x < 0.3 else "B"  # noqa: E731
    thr, direction = find_flip(f, 0.0, 1.0, 0.1)
    assert abs(thr - 0.3) < 1e-4 and direction == "up"
    assert find_flip(lambda x: "A", 0.0, 1.0, 0.5) == (None, "none")


def test_flip_analysis_on_two_alt_graph(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    put_all(g, obj("as-w", "Assumption", statement="weight on m-b is right", linchpin=True,
                   rationale="r", evidence="ev-doc", implicationsIfWrong="i",
                   indicatorsThatWouldAlter=["x"], variedInSensitivity=True,
                   parameterBinding={"kind": "weight", "target": "ws-1:m-b"}),
            {**g.get("ep-1"), "rev": g.get("ep-1")["rev"] + 1, "assumptions": ["as-w"]})
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    flips = flip_analysis(g, run["id"], seed=3, now=NOW)
    by_target = {f["parameter"]["target"]: f for f in flips}
    # x wins only when the weight on m-a dominates: x = 10*w_a ; y = 30*(1-w_a)
    # -> flip at w_a = 0.75
    fa = by_target["ws-1:m-a"]
    assert abs(fa["flipThreshold"] - 0.75) < 1e-3 and fa["direction"] == "up"
    assert abs(fa["flipDistance"] - 0.25) < 1e-3
    assert by_target["ws-1:m-b"]["assumption"] == "as-w"
    assert g.get("ep-1")["flipAnalyses"] == [f["id"] for f in flips]
    s = flip_summary(g, run["id"], seed=3, now=NOW)
    assert abs(sum(s["simplexRobustness"].values()) - 1) < 1e-9
    assert s["ranked"][0] == fa["id"]
    s2 = flip_summary(g, run["id"], seed=3, now=NOW)
    assert s == s2


# ---- Important #1: bound to the sealed run's own inputs, not live graph state -----


def test_flip_analysis_ignores_weightset_revision_when_sealed(two_alt_graph):  # noqa: F811
    """A run's own sealed weights ground the analysis. A WeightSet revised after
    sealing must not silently change flip_analysis's output for that run."""
    g1 = two_alt_graph
    run = evaluate(g1, "pl-1", seed=1, now=NOW)[0]
    g2 = copy.deepcopy(g1)
    put_all(g2, {**g2.get("ws-1"), "rev": 2, "weights": {"m-a": 0.9, "m-b": 0.1}})
    flips1 = flip_analysis(g1, run["id"], seed=1, now=NOW)
    flips2 = flip_analysis(g2, run["id"], seed=1, now=NOW)
    assert [f["flipThreshold"] for f in flips1] == [f["flipThreshold"] for f in flips2]


def test_flip_analysis_raises_when_fallback_weights_diverge_from_sealed_ranking(
    two_alt_graph,  # noqa: F811
):
    """A run whose own parameterBindings lack a sealed weights snapshot (a
    pre-kernel-0.1.0 shape) falls back to the live WeightSet. If that WeightSet has
    since been revised, flip_analysis must refuse rather than silently analyse a
    mismatched baseline.

    Which guard fires depends on what the run still carries: this run keeps its
    `inputsHash`, so the refusal comes from the inputs check in `_run_inputs` (the
    fallback weights no longer reproduce the sealed hash), not from the ranking check
    further down. The ranking check has its own test below."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    put_all(g, {**g.get("ws-1"), "rev": 2, "weights": {"m-a": 0.9, "m-b": 0.1}})
    legacy_pb = {k: v for k, v in run["parameterBindings"].items() if k != "weights"}
    g.put({**run, "id": "run-legacy-1", "parameterBindings": legacy_pb}, KERNEL_ACTOR)
    with pytest.raises(ValidationError):
        flip_analysis(g, "run-legacy-1", seed=1, now=NOW)


def test_flip_analysis_raises_on_duplicate_observation_in_run_inputs(
    two_alt_graph,  # noqa: F811
):
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    put_all(g, observation("ob-xa-dup", "alt-x", "m-a", 11))
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": KERNEL_ACTOR,
           "observations": ep["observations"] + ["ob-xa-dup"]}, KERNEL_ACTOR)
    legacy_pb = {k: v for k, v in run["parameterBindings"].items() if k != "observationIds"}
    g.put({**run, "id": "run-legacy-dup", "parameterBindings": legacy_pb}, KERNEL_ACTOR)
    with pytest.raises(ValidationError):
        flip_analysis(g, "run-legacy-dup", seed=1, now=NOW)


def test_flip_analysis_raises_on_distribution_uncertainty_for_swept_observation(
    two_alt_graph,  # noqa: F811
):
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    put_all(
        g,
        obj("unc-dist", "Uncertainty", kind="distribution",
            spec={"distribution": "normal", "mean": 10, "sd": 1}),
        {**g.get("ob-xa"), "rev": g.get("ob-xa")["rev"] + 1,
         "uncertainty": "unc-dist", "variedInSensitivity": True},
    )
    with pytest.raises(ValidationError):
        flip_analysis(g, run["id"], seed=1, now=NOW)


def test_flip_analysis_raises_on_scenario_set_uncertainty_for_swept_observation(
    two_alt_graph,  # noqa: F811
):
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    put_all(
        g,
        obj("unc-scen", "Uncertainty", kind="scenarioSet",
            spec={"scenarios": [{"label": "low", "value": 5}, {"label": "high", "value": 15}]}),
        {**g.get("ob-xa"), "rev": g.get("ob-xa")["rev"] + 1,
         "uncertainty": "unc-scen", "variedInSensitivity": True},
    )
    with pytest.raises(ValidationError):
        flip_analysis(g, run["id"], seed=1, now=NOW)


def test_flip_analysis_widens_range_to_include_point(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    put_all(
        g,
        obj("unc-widen", "Uncertainty", kind="interval", spec={"lo": 50, "hi": 60}),
        {**g.get("ob-xa"), "rev": g.get("ob-xa")["rev"] + 1,
         "uncertainty": "unc-widen", "variedInSensitivity": True},
    )
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    flips = flip_analysis(g, run["id"], seed=1, now=NOW)
    by_target = {f["parameter"]["target"]: f for f in flips}
    assert by_target["ob-xa"]["range"] == {"lo": 10.0, "hi": 60.0, "source": "uncertainty"}


def test_flip_analysis_observation_default_ranges_and_no_flip(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    put_all(
        g,
        {**g.get("ob-xa"), "rev": g.get("ob-xa")["rev"] + 1, "variedInSensitivity": True},
        {**g.get("ob-ya"), "rev": g.get("ob-ya")["rev"] + 1, "variedInSensitivity": True},
    )
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    flips = flip_analysis(g, run["id"], seed=1, now=NOW)
    by_target = {f["parameter"]["target"]: f for f in flips}
    xa = by_target["ob-xa"]
    assert xa["range"] == {"lo": 5.0, "hi": 15.0, "source": "default"}  # 10 ± 50%
    assert xa["flipThreshold"] is None
    assert xa["flipDistance"] is None
    assert xa["direction"] == "none"
    assert xa["rankingAfter"] is None
    ya = by_target["ob-ya"]
    assert ya["range"] == {"lo": -1.0, "hi": 1.0, "source": "default"}  # 0 ± 1


def test_flip_analysis_weight_sweep_explicit_range(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    put_all(
        g,
        {**g.get("pl-1"), "rev": g.get("pl-1")["rev"] + 1,
         "steps": [{**g.get("pl-1")["steps"][0],
                    "sensitivitySweeps": [
                        {"kind": "weight", "target": "ws-1:m-a", "range": {"lo": 0.2, "hi": 0.8}},
                    ]}]},
    )
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    flips = flip_analysis(g, run["id"], seed=1, now=NOW)
    by_target = {f["parameter"]["target"]: f for f in flips}
    assert by_target["ws-1:m-a"]["range"] == {"lo": 0.2, "hi": 0.8, "source": "sweep"}
    assert by_target["ws-1:m-b"]["range"] == {"lo": 0.0, "hi": 1.0, "source": "default"}


# ---- Important #2: the observation half of the parameter sweep --------------------


def _step_authority():
    return {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}


def test_flip_analysis_observation_interval_uncertainty(base_graph):
    g = base_graph
    put_all(
        g,
        objective("obj-a", measures=["m1"]),
        measure("m1", "obj-a", metric={"units": "u", "direction": "max"}),
        alternative("alt-1", order=1), alternative("alt-2", order=2),
        gap("gap-vva-a", confirmed=True),
        model("mdl-a", vva={"$gap": "gap-vva-a"}),
        obj("unc-1", "Uncertainty", kind="interval", spec={"lo": 0, "hi": 20}),
        observation("obs-1", "alt-1", "m1", 12, uncertainty="unc-1", variedInSensitivity=True),
        observation("obs-2", "alt-2", "m1", 10),
        obj("ws-a", "WeightSet", name="w", method="stated", weights={"m1": 1.0},
            provenance="ev-doc"),
        obj("pl-a", "Plan", episode="ep-1", policyBasis="pol-1",
            approvedBy={"actorId": "fixture", "date": "2026"},
            steps=[{"id": "s1", "evaluator": "mdl-a", "method": "mavt",
                    "alternatives": ["alt-1", "alt-2"], "measures": ["m1"],
                    "weightSet": "ws-a", "authority": _step_authority()}]),
        {**g.get("ep-1"), "rev": g.get("ep-1")["rev"] + 1, **plan_approved(),
         "alternatives": ["alt-1", "alt-2"], "observations": ["obs-1", "obs-2"],
         "weightSets": ["ws-a"], "models": ["mdl-a"], "plan": "pl-a", "objectives": ["obj-a"]},
    )
    assert_history_honest(g)
    run = evaluate(g, "pl-a", seed=1, now=NOW)[0]
    assert run["ranking"] == ["alt-1", "alt-2"]  # 12 > 10
    flips = flip_analysis(g, run["id"], seed=1, now=NOW)
    # A single-weight WeightSet has nothing to rescale into: no weight FlipAnalysis.
    assert all(f["parameter"]["kind"] != "weight" for f in flips)
    fa = flips[0]
    assert fa["range"] == {"lo": 0.0, "hi": 20.0, "source": "uncertainty"}
    assert fa["flipThreshold"] is not None
    assert abs(fa["flipThreshold"] - 10.0) < 1e-3 and fa["direction"] == "down"
    assert abs(fa["flipDistance"] - 0.1) < 1e-3


def test_flip_analysis_observation_plan_sweep_and_assumption_binding(base_graph):
    g = base_graph
    put_all(
        g,
        objective("obj-b", measures=["m2"]),
        measure("m2", "obj-b", metric={"units": "u", "direction": "max"}),
        alternative("alt-3", order=1), alternative("alt-4", order=2),
        gap("gap-vva-b", confirmed=True),
        model("mdl-b", vva={"$gap": "gap-vva-b"}),
        observation("obs-3", "alt-3", "m2", 15),
        observation("obs-4", "alt-4", "m2", 10),
        obj("ws-b", "WeightSet", name="w", method="stated", weights={"m2": 1.0},
            provenance="ev-doc"),
        obj("as-obs", "Assumption", statement="m2 on alt-3 is right", linchpin=True,
            rationale="r", evidence="ev-doc", implicationsIfWrong="i",
            indicatorsThatWouldAlter=["x"], variedInSensitivity=True,
            parameterBinding={"kind": "observation", "target": "obs-3"}),
        obj("pl-b", "Plan", episode="ep-1", policyBasis="pol-1",
            approvedBy={"actorId": "fixture", "date": "2026"},
            steps=[{"id": "s1", "evaluator": "mdl-b", "method": "mavt",
                    "alternatives": ["alt-3", "alt-4"], "measures": ["m2"],
                    "weightSet": "ws-b",
                    "sensitivitySweeps": [
                        {"kind": "observation", "target": "obs-3", "range": {"lo": 0, "hi": 30}},
                    ],
                    "authority": _step_authority()}]),
        {**g.get("ep-1"), "rev": g.get("ep-1")["rev"] + 1, **plan_approved(),
         "alternatives": ["alt-3", "alt-4"], "observations": ["obs-3", "obs-4"],
         "weightSets": ["ws-b"], "models": ["mdl-b"], "plan": "pl-b", "objectives": ["obj-b"],
         "assumptions": ["as-obs"]},
    )
    assert_history_honest(g)
    run = evaluate(g, "pl-b", seed=1, now=NOW)[0]
    flips = flip_analysis(g, run["id"], seed=1, now=NOW)
    assert len(flips) == 1  # obs-4 is never varied/bound/swept; obs-3 alone qualifies
    fa = flips[0]
    assert fa["range"] == {"lo": 0.0, "hi": 30.0, "source": "sweep"}
    assert abs(fa["flipThreshold"] - 10.0) < 1e-3 and fa["direction"] == "down"
    assert abs(fa["flipDistance"] - (5 / 30)) < 1e-3
    assert fa["assumption"] == "as-obs"


def test_flip_analysis_observation_min_direction_sweep(base_graph):
    g = base_graph
    put_all(
        g,
        objective("obj-c", measures=["m3"]),
        measure("m3", "obj-c", metric={"units": "u", "direction": "min"}),
        alternative("alt-5", order=1), alternative("alt-6", order=2),
        gap("gap-vva-c", confirmed=True),
        model("mdl-c", vva={"$gap": "gap-vva-c"}),
        observation("obs-5", "alt-5", "m3", 10),
        observation("obs-6", "alt-6", "m3", 8),
        obj("ws-c", "WeightSet", name="w", method="stated", weights={"m3": 1.0},
            provenance="ev-doc"),
        obj("pl-c", "Plan", episode="ep-1", policyBasis="pol-1",
            approvedBy={"actorId": "fixture", "date": "2026"},
            steps=[{"id": "s1", "evaluator": "mdl-c", "method": "mavt",
                    "alternatives": ["alt-5", "alt-6"], "measures": ["m3"],
                    "weightSet": "ws-c",
                    "sensitivitySweeps": [
                        {"kind": "observation", "target": "obs-5", "range": {"lo": 0, "hi": 20}},
                    ],
                    "authority": _step_authority()}]),
        {**g.get("ep-1"), "rev": g.get("ep-1")["rev"] + 1, **plan_approved(),
         "alternatives": ["alt-5", "alt-6"], "observations": ["obs-5", "obs-6"],
         "weightSets": ["ws-c"], "models": ["mdl-c"], "plan": "pl-c", "objectives": ["obj-c"]},
    )
    assert_history_honest(g)
    run = evaluate(g, "pl-c", seed=1, now=NOW)[0]
    assert run["ranking"] == ["alt-6", "alt-5"]  # min direction: -10 < -8
    flips = flip_analysis(g, run["id"], seed=1, now=NOW)
    fa = flips[0]
    assert abs(fa["flipThreshold"] - 8.0) < 1e-3 and fa["direction"] == "down"
    assert abs(fa["flipDistance"] - 0.1) < 1e-3


def test_flip_analysis_no_params_skips_episode_revision(base_graph):
    g = base_graph
    put_all(
        g,
        objective("obj-d", measures=["m4"]),
        measure("m4", "obj-d", metric={"units": "u", "direction": "max"}),
        alternative("alt-7", order=1), alternative("alt-8", order=2),
        gap("gap-vva-d", confirmed=True),
        model("mdl-d", vva={"$gap": "gap-vva-d"}),
        observation("obs-7", "alt-7", "m4", 5),
        observation("obs-8", "alt-8", "m4", 3),
        obj("ws-d", "WeightSet", name="w", method="stated", weights={"m4": 1.0},
            provenance="ev-doc"),
        obj("pl-d", "Plan", episode="ep-1", policyBasis="pol-1",
            approvedBy={"actorId": "fixture", "date": "2026"},
            steps=[{"id": "s1", "evaluator": "mdl-d", "method": "mavt",
                    "alternatives": ["alt-7", "alt-8"], "measures": ["m4"],
                    "weightSet": "ws-d", "authority": _step_authority()}]),
        {**g.get("ep-1"), "rev": g.get("ep-1")["rev"] + 1, **plan_approved(),
         "alternatives": ["alt-7", "alt-8"], "observations": ["obs-7", "obs-8"],
         "weightSets": ["ws-d"], "models": ["mdl-d"], "plan": "pl-d", "objectives": ["obj-d"]},
    )
    assert_history_honest(g)
    run = evaluate(g, "pl-d", seed=1, now=NOW)[0]
    ep_before = g.get("ep-1")
    flips = flip_analysis(g, run["id"], seed=1, now=NOW)
    assert flips == []
    assert g.get("ep-1") == ep_before  # no episode revision written


# ---- Minors -------------------------------------------------------------------


def test_clean_normalises_signed_zero():
    from docket.kernel.evaluate import _clean
    cleaned = _clean(round6(-1e-9))
    assert cleaned == 0.0
    assert math.copysign(1.0, cleaned) == 1.0


def test_flip_summary_nsimplex_default_and_zero_validation(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    flip_analysis(g, run["id"], seed=1, now=NOW)
    s = flip_summary(g, run["id"], seed=1, now=NOW, n_simplex=None)
    assert s["nSimplex"] == g.get("pol-1")["nSimplex"]
    with pytest.raises(ValidationError):
        flip_summary(g, run["id"], seed=1, now=NOW, n_simplex=0)


# ---- final wave, item 1: flip_summary is bound to the sealed run -------------------


def _revise(g, oid, actor, **fields):
    o = g.get(oid)
    return put_all(g, {**o, "rev": o["rev"] + 1, "createdBy": actor, **fields})


def test_flip_summary_ignores_observations_added_after_sealing(two_alt_graph):  # noqa: F811
    """A run's simplex robustness is drawn over the run's *own* bound observations. An
    Observation a human adds to the episode register after sealing was never an input to
    this run, so the figure printed next to the run must not move (nor may the register
    scan blow up over the resulting duplicate — `observation-duplicate` is the rule that
    reports that, at validate() time)."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    flip_analysis(g, run["id"], seed=3, now=NOW)
    before = flip_summary(g, run["id"], seed=3, now=NOW)

    put_all(g, observation("ob-xa-late", "alt-x", "m-a", 900))
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H,
                "observations": ep["observations"] + ["ob-xa-late"]})

    after = flip_summary(g, run["id"], seed=3, now=NOW)
    assert canonical_json(after) == canonical_json(before)


def test_flip_summary_raises_when_a_revision_breaks_the_sealed_ranking(
    two_alt_graph,  # noqa: F811
):
    """An Observation revised after sealing so that the sealed weights no longer produce
    the run's recorded ranking: refuse rather than publish a robustness figure that
    contradicts the run it is attached to."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    assert run["ranking"] == ["alt-y", "alt-x"]
    _revise(g, "ob-xa", H, value=100)
    with pytest.raises(ValidationError) as exc:
        flip_summary(g, run["id"], seed=3, now=NOW)
    assert "inputsHash mismatch" in str(exc.value)


def test_flip_summary_raises_when_the_run_ranking_was_rewritten(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    _revise(g, run["id"], H, ranking=list(reversed(run["ranking"])))
    with pytest.raises(ValidationError):
        flip_summary(g, run["id"], seed=3, now=NOW)


def test_flip_analysis_on_a_normal_run_raises_when_a_revision_breaks_the_ranking(
    two_alt_graph,  # noqa: F811
):
    """The T3 carry: the observation-revision refusal, on an ordinary sealed run rather
    than on the constructed legacy shape."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    _revise(g, "ob-xa", H, value=100)
    with pytest.raises(ValidationError):
        flip_analysis(g, run["id"], seed=3, now=NOW)


def test_flip_analysis_ignores_a_duplicate_observation_added_after_sealing(
    two_alt_graph,  # noqa: F811
):
    """A duplicate added to the register afterwards is not one of the run's inputs, so
    the analysis is unmoved by it — and `observation-duplicate` reports it separately."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    g2 = copy.deepcopy(g)
    flips_before = flip_analysis(g, run["id"], seed=3, now=NOW)

    put_all(g2, observation("ob-xa-late", "alt-x", "m-a", 900))
    ep = g2.get("ep-1")
    put_all(g2, {**ep, "rev": ep["rev"] + 1, "createdBy": H,
                 "observations": ep["observations"] + ["ob-xa-late"]})
    flips_after = flip_analysis(g2, run["id"], seed=3, now=NOW)
    assert ([f["flipThreshold"] for f in flips_before]
            == [f["flipThreshold"] for f in flips_after])
    findings = validate(g2, g2.get("pol-1"))
    assert any(f.rule == "observation-duplicate" for f in findings)


# ---- final wave, item 8 minors -----------------------------------------------------


def test_perturb_weights_refuses_a_single_weight():
    with pytest.raises(ValidationError):
        perturb_weights({"m": 1.0}, "m", 0.5)


def test_bisection_lands_on_the_exact_threshold_not_a_ragged_digit(base_graph):
    """tol 1e-9 against a `round6` store: a flip that is exactly at 0.75 must be stored
    as 0.75, not as the 0.749999 a 1e-6 bisection leaves behind."""
    g = base_graph
    put_all(
        g,
        objective("obj-e", measures=["m-e1", "m-e2"]),
        measure("m-e1", "obj-e", metric={"units": "u", "direction": "max"}),
        measure("m-e2", "obj-e", metric={"units": "u", "direction": "max"}),
        alternative("alt-e1", order=1), alternative("alt-e2", order=2),
        gap("gap-vva-e", confirmed=True),
        model("mdl-e", vva={"$gap": "gap-vva-e"}),
        observation("obs-e11", "alt-e1", "m-e1", 10),
        observation("obs-e12", "alt-e1", "m-e2", 0),
        observation("obs-e21", "alt-e2", "m-e1", 0),
        observation("obs-e22", "alt-e2", "m-e2", 30),
        obj("ws-e", "WeightSet", name="w", method="stated",
            weights={"m-e1": 1.0, "m-e2": 0.0}, provenance="ev-doc"),
        obj("pl-e", "Plan", episode="ep-1", policyBasis="pol-1",
            approvedBy={"actorId": "fixture", "date": "2026"},
            steps=[{"id": "s1", "evaluator": "mdl-e", "method": "mavt",
                    "alternatives": ["alt-e1", "alt-e2"], "measures": ["m-e1", "m-e2"],
                    "weightSet": "ws-e", "authority": _step_authority()}]),
        {**g.get("ep-1"), "rev": g.get("ep-1")["rev"] + 1, **plan_approved(),
         "alternatives": ["alt-e1", "alt-e2"],
         "observations": ["obs-e11", "obs-e12", "obs-e21", "obs-e22"],
         "weightSets": ["ws-e"], "models": ["mdl-e"], "plan": "pl-e",
         "objectives": ["obj-e"]},
    )
    assert_history_honest(g)
    run = evaluate(g, "pl-e", seed=1, now=NOW)[0]
    flips = flip_analysis(g, run["id"], seed=1, now=NOW)
    by_target = {f["parameter"]["target"]: f["flipThreshold"] for f in flips}
    assert by_target["ws-e:m-e1"] == 0.75
    assert by_target["ws-e:m-e2"] == 0.25


# ---- follow-up A: bound to the run's inputsHash, not only to its observation ids -----


def test_a_rank_preserving_observation_revision_refuses_both_analyses(
    two_alt_graph,  # noqa: F811
):
    """The silent case. Revising a bound Observation from 10 to 25 leaves the sealed
    ranking exactly where it was, so the ranking check alone would let it through — and
    the published simplex robustness would then describe inputs the run never used. The
    sealed `inputsHash` catches it because the observation's own content hash is in it."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    flip_analysis(g, run["id"], seed=3, now=NOW)
    _revise(g, "ob-xa", H, value=25)

    # The ranking is genuinely unchanged: this is not the rank-breaking case in disguise.
    assert rank(score({a: {m: value_of(g.get(m), v) for m, v in row.items()}
                       for a, row in {"alt-x": {"m-a": 25, "m-b": 0},
                                      "alt-y": {"m-a": 0, "m-b": 30}}.items()},
                      {"m-a": 0.5, "m-b": 0.5})) == run["ranking"]

    for fn in (flip_summary, flip_analysis):
        with pytest.raises(ValidationError) as exc:
            fn(g, run["id"], seed=3, now=NOW)
        assert "inputsHash mismatch" in str(exc.value)


def test_a_revised_value_function_refuses_both_analyses(two_alt_graph):  # noqa: F811
    """Measure definitions are in the sealed hash: re-scaling a value function after the
    run was sealed changes what the numbers mean, whether or not it moves the order."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    flip_analysis(g, run["id"], seed=3, now=NOW)
    _revise(g, "m-a", H, valueFunction={"kind": "linear", "lo": 0, "hi": 100})
    for fn in (flip_summary, flip_analysis):
        with pytest.raises(ValidationError) as exc:
            fn(g, run["id"], seed=3, now=NOW)
        assert "inputsHash mismatch" in str(exc.value)


def test_an_observation_outside_the_step_leaves_both_analyses_byte_identical(
    two_alt_graph,  # noqa: F811
):
    """The other side of the same coin: an Observation for an alternative the step never
    evaluated is not one of this run's inputs, so registering it must move nothing."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    flips_before = flip_analysis(g, run["id"], seed=3, now=NOW)
    summary_before = flip_summary(g, run["id"], seed=3, now=NOW)

    g2 = copy.deepcopy(g)
    put_all(g2, alternative("alt-z", order=3),
            observation("ob-za", "alt-z", "m-a", 55),
            observation("ob-zb", "alt-z", "m-b", 5))
    ep = g2.get("ep-1")
    put_all(g2, {**ep, "rev": ep["rev"] + 1, "createdBy": H,
                 "observations": ep["observations"] + ["ob-za", "ob-zb"]})

    assert canonical_json(flip_summary(g2, run["id"], seed=3, now=NOW)) == canonical_json(
        summary_before)
    g3 = copy.deepcopy(g2)
    for f in flips_before:  # re-running flip_analysis needs the flips absent
        g3._latest.pop(f["id"], None)
    ep3 = g3.get("ep-1")
    put_all(g3, {**ep3, "rev": ep3["rev"] + 1, "createdBy": H, "flipAnalyses": []})
    flips_after = flip_analysis(g3, run["id"], seed=3, now=NOW)
    assert canonical_json(flips_after) == canonical_json(flips_before)


# ---- round 2: the baseline check and the no-inputsHash fallback ---------------------


def test_flip_analysis_raises_when_the_run_ranking_was_rewritten(two_alt_graph):  # noqa: F811
    """The `flip_analysis` twin of the flip_summary case. Rewriting the run's `ranking`
    leaves its inputs untouched, so the inputs check passes and the baseline check is the
    one that has to catch it — otherwise every flip would be reported against an order
    the run never produced."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    _revise(g, run["id"], H, ranking=list(reversed(run["ranking"])))
    with pytest.raises(ValidationError) as exc:
        flip_analysis(g, run["id"], seed=3, now=NOW)
    assert "baseline does not reproduce the sealed run ranking" in str(exc.value)


def _legacy_run_without_inputs_hash(g, run, new_id, observation_ids):
    """A pre-kernel-0.1.0 shape: no `inputsHash` at all. The catalogue requires the field,
    so the store would refuse it — which is the point: only a hand-edited or older store
    can hold one, and that is exactly what the fallback path exists for."""
    legacy = {k: v for k, v in g.get(run["id"]).items() if k != "inputsHash"}
    legacy["id"] = new_id
    legacy["parameterBindings"] = {**run["parameterBindings"],
                                   "observationIds": observation_ids}
    g._latest[new_id] = legacy
    g._history[new_id][legacy["rev"]] = legacy
    return legacy


def test_a_legacy_run_with_a_short_observation_list_refuses_by_name(two_alt_graph):  # noqa: F811
    """Without a sealed hash there is nothing to compare against, so the ids have to be
    resolved on their own account: an id list missing a pair used to surface as a bare
    `KeyError` from inside the sweep."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    _legacy_run_without_inputs_hash(g, run, "run-legacy-short", ["ob-xa", "ob-xb", "ob-ya"])
    for fn in (flip_analysis, flip_summary):
        with pytest.raises(ValidationError) as exc:
            fn(g, "run-legacy-short", seed=3, now=NOW)
        assert "no Observation for alternative alt-y on measure m-b" in str(exc.value)


def test_a_legacy_run_with_a_duplicated_observation_pair_refuses_by_name(
    two_alt_graph,  # noqa: F811
):
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    put_all(g, observation("ob-xa-twin", "alt-x", "m-a", 12))
    _legacy_run_without_inputs_hash(
        g, run, "run-legacy-dupe",
        ["ob-xa", "ob-xa-twin", "ob-xb", "ob-ya", "ob-yb"])
    for fn in (flip_analysis, flip_summary):
        with pytest.raises(ValidationError) as exc:
            fn(g, "run-legacy-dupe", seed=3, now=NOW)
        assert "multiple Observations for alternative alt-x measure m-a" in str(exc.value)


def test_a_legacy_run_with_a_complete_observation_list_still_works(two_alt_graph):  # noqa: F811
    """The fallback must stay usable: a legacy run whose ids do cover the step still
    analyses, and matches what the same run produces with its hash intact."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    expected = flip_analysis(g, run["id"], seed=3, now=NOW)
    _legacy_run_without_inputs_hash(g, run, "run-legacy-ok",
                                    list(run["parameterBindings"]["observationIds"]))
    got = flip_analysis(g, "run-legacy-ok", seed=3, now=NOW)
    assert [f["flipThreshold"] for f in got] == [f["flipThreshold"] for f in expected]


def test_the_episode_revision_is_stamped_with_the_caller_s_now(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=3, now=NOW)[0]
    put_all(g, obj("as-w", "Assumption", statement="weight on m-b is right", linchpin=True,
                   rationale="r", evidence="ev-doc", implicationsIfWrong="i",
                   indicatorsThatWouldAlter=["x"], variedInSensitivity=True,
                   parameterBinding={"kind": "weight", "target": "ws-1:m-b"}),
            {**g.get("ep-1"), "rev": g.get("ep-1")["rev"] + 1, "createdBy": H,
             "assumptions": ["as-w"]})
    later = "2026-11-30T12:00:00Z"
    assert g.get("ep-1")["createdAt"] != later
    flips = flip_analysis(g, run["id"], seed=3, now=later)
    assert flips and g.get("ep-1")["createdAt"] == later
