# tests/kernel/test_evaluate.py
import pytest

from docket import KERNEL_ACTOR
from docket.canon import content_hash
from docket.errors import ValidationError
from docket.kernel.evaluate import evaluate, rank, score, value_of
from docket.store import Graph
from tests.kernel.conftest import (
    H,
    alternative,
    assert_history_honest,
    charter,
    drs,
    episode,
    evidence,
    gap,
    obj,
    plan_approved,
    policy,
    put_all,
)
from tests.kernel.conftest import (
    eval_model as model,
)
from tests.kernel.conftest import (
    eval_observation as observation,
)


def test_value_of_direction_and_functions():
    m = {"metric": {"direction": "min"}, "valueFunction": {"kind": "linear", "lo": 0, "hi": 10}}
    assert value_of(m, 0) == 1.0 and value_of(m, 10) == 0.0 and value_of(m, 5) == 0.5
    assert value_of({"metric": {"direction": "max"}}, 7.5) == 7.5
    b = {"metric": {"direction": "max"}, "valueFunction": {"kind": "binary", "threshold": 9}}
    assert value_of(b, 9) == 1.0 and value_of(b, 8) == 0.0


def test_score_and_rank():
    s = score({"a": {"m": 1.0, "n": 0.0}, "b": {"m": 0.0, "n": 1.0}}, {"m": 0.7, "n": 0.3})
    assert s == {"a": 0.7, "b": 0.3} and rank(s) == ["a", "b"]
    assert rank({"z": 1.0, "y": 1.0}) == ["y", "z"]


def test_evaluate_creates_sealed_run_and_results(two_alt_graph):
    g = two_alt_graph
    assert_history_honest(g)
    runs = evaluate(g, "pl-1", seed=7, now="2026-09-04T00:00:00Z")
    assert len(runs) == 1
    run = runs[0]
    assert run["id"] == "run-pl-1-s1" and run["sealedBy"] == "kernel" and run["seed"] == 7
    assert g.get(run["id"])["createdBy"] == KERNEL_ACTOR
    assert run["ranking"] == ["alt-y", "alt-x"]  # y: 0.5*0 + 0.5*30 = 15 ; x: 5
    agg = g.get("res-run-pl-1-s1-alt-y")
    assert agg["aggregate"] is True and agg["value"] == 15.0
    assert agg["uncertainty"] == {"lo": 10.0, "hi": 20.0}
    assert len(run["outputs"]) == 2 + 4 and len(run["outputHashes"]) == 6
    assert run["runRecordHash"] and run["inputsHash"]


def test_evaluate_is_deterministic(two_alt_graph):
    import copy

    from docket.canon import canonical_json
    g1 = two_alt_graph
    g2 = copy.deepcopy(two_alt_graph)
    r1 = evaluate(g1, "pl-1", seed=1, now="2026-09-04T00:00:00Z")[0]
    r2 = evaluate(g2, "pl-1", seed=1, now="2026-09-04T00:00:00Z")[0]
    assert canonical_json(r1) == canonical_json(r2)
    out1 = [canonical_json(g1.get(i)) for i in r1["outputs"]]
    out2 = [canonical_json(g2.get(i)) for i in r2["outputs"]]
    assert out1 == out2


def test_missing_observation_raises(two_alt_graph):
    g = two_alt_graph
    old_step = g.get("pl-1")["steps"][0]
    new_step = {**old_step, "alternatives": ["alt-x", "alt-y", "alt-z"]}
    put_all(g, alternative("alt-z", order=3),
            {**g.get("pl-1"), "rev": 2, "steps": [new_step]})
    with pytest.raises(ValidationError):
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")


def test_weights_must_sum_to_one(two_alt_graph):
    g = two_alt_graph
    put_all(g, {**g.get("ws-1"), "rev": 2, "weights": {"m-a": 0.5, "m-b": 0.4}})
    with pytest.raises(ValidationError):
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")


def test_sealing_hashes_recompute_from_stored_objects(two_alt_graph):
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")[0]
    for oid, h in zip(run["outputs"], run["outputHashes"], strict=True):
        assert h == content_hash(g.get(oid))
    stored = g.get(run["id"])
    recomputed = content_hash({k: v for k, v in stored.items() if k != "runRecordHash"})
    assert stored["runRecordHash"] == recomputed


def test_min_direction_identity_ranks_lower_raw_first(base_graph):
    g = base_graph
    put_all(
        g,
        obj("obj-2", "Objective", name="o2", priority="primary", provenance="ev-doc",
            measures=["m-c"]),
        obj("m-c", "Measure", objective="obj-2", task="t", attribute="a", measure="m-c",
            metric={"units": "kg", "direction": "min"}, criteria={"threshold": 1}),
        gap("gap-v", confirmed=True), model(),
        alternative("alt-p", order=1), alternative("alt-q", order=2),
        observation("ob-p", "alt-p", "m-c", 5), observation("ob-q", "alt-q", "m-c", 2),
        obj("ws-2", "WeightSet", name="w2", method="stated",
            weights={"m-c": 1.0}, provenance="ev-doc"),
        obj("pl-2", "Plan", episode="ep-1", policyBasis="pol-1",
            approvedBy={"actorId": "fixture", "date": "2026"},
            steps=[{"id": "s1", "evaluator": "mdl-1", "method": "mavt",
                    "alternatives": ["alt-p", "alt-q"],
                    "measures": ["m-c"], "weightSet": "ws-2",
                    "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}]),
        {**episode(), "rev": 2, **plan_approved(), "alternatives": ["alt-p", "alt-q"],
         "observations": ["ob-p", "ob-q"], "weightSets": ["ws-2"], "models": ["mdl-1"],
         "plan": "pl-2", "objectives": ["obj-2"]},
    )
    assert_history_honest(g)
    run = evaluate(g, "pl-2", seed=1, now="2026-09-04T00:00:00Z")[0]
    assert run["ranking"] == ["alt-q", "alt-p"]  # lower raw (2) beats higher raw (5) under min
    rp = g.get("res-run-pl-2-s1-alt-p-m-c")
    rq = g.get("res-run-pl-2-s1-alt-q-m-c")
    assert rp["value"] == -5.0 and rp["raw"] == 5.0 and rp["rawUnits"] == "kg"
    assert rq["value"] == -2.0 and rq["raw"] == 2.0 and rq["rawUnits"] == "kg"


def test_non_mavt_method_refused(two_alt_graph):
    g = two_alt_graph
    old_step = g.get("pl-1")["steps"][0]
    put_all(g, {**g.get("pl-1"), "rev": 2, "steps": [{**old_step, "method": "ahp"}]})
    with pytest.raises(ValidationError):
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")


def test_missing_weight_for_step_measure_refused(two_alt_graph):
    g = two_alt_graph
    put_all(g, {**g.get("ws-1"), "rev": 2, "weights": {"m-a": 1.0}})
    with pytest.raises(ValidationError):
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")


def test_duplicate_observation_refused(two_alt_graph):
    g = two_alt_graph
    put_all(
        g,
        observation("ob-xa2", "alt-x", "m-a", 999),
        {**g.get("ep-1"), "rev": 3,
         "observations": ["ob-xa", "ob-xb", "ob-ya", "ob-yb", "ob-xa2"]},
    )
    with pytest.raises(ValidationError):
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")


def test_evaluate_writes_nothing_when_a_later_step_fails(two_alt_graph):
    g = two_alt_graph
    old_step = g.get("pl-1")["steps"][0]
    put_all(
        g,
        obj("ws-bad", "WeightSet", name="bad", method="stated",
            weights={"m-a": 0.5, "m-b": 0.4}, provenance="ev-doc"),
        {**g.get("pl-1"), "rev": 2,
         "steps": [old_step, {**old_step, "id": "s2", "weightSet": "ws-bad"}]},
    )
    before = g.snapshot_hash()
    with pytest.raises(ValidationError):
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")
    assert g.snapshot_hash() == before


def test_value_of_raises_validation_error_never_keyerror():
    max_dir = {"metric": {"direction": "max"}}
    with pytest.raises(ValidationError):
        value_of({**max_dir, "valueFunction": {"kind": "linear", "lo": 0}}, 5)
    with pytest.raises(ValidationError):
        value_of({**max_dir, "valueFunction": {"kind": "linear", "lo": 5, "hi": 5}}, 5)
    with pytest.raises(ValidationError):
        value_of({**max_dir, "valueFunction": {"kind": "binary"}}, 5)
    with pytest.raises(ValidationError):
        value_of({**max_dir, "valueFunction": {"kind": "bogus"}}, 5)
    with pytest.raises(ValidationError):
        value_of({"metric": {}}, 5)


def test_negative_zero_normalised_to_positive_zero():
    import json

    v = value_of({"metric": {"direction": "min"}}, 0)
    assert v == 0.0 and json.dumps(v) == "0.0"


def _fresh_base_graph():
    """A standalone copy of the `base_graph` fixture's body, callable more than once
    per test — needed to build two independent graphs to compare rankings across."""
    g = Graph()
    for o in (policy(), evidence("ev-doc"), drs(), charter(), episode()):
        g.put(o, H)
    return g


def _band_graph(with_band: bool) -> Graph:
    g = _fresh_base_graph()
    ob_r = obj("ob-r", "Observation", alternative="alt-r", measure="m-d", value=10,
               evidence="ev-doc")
    if with_band:
        ob_r["uncertainty"] = "unc-1"
    extra = [obj("unc-1", "Uncertainty", kind="interval", spec={"lo": 0, "hi": 100})]
    put_all(
        g,
        obj("obj-3", "Objective", name="o3", priority="primary", provenance="ev-doc",
            measures=["m-d"]),
        obj("m-d", "Measure", objective="obj-3", task="t", attribute="a", measure="m-d",
            metric={"units": "kg", "direction": "max"}, criteria={"threshold": 1}),
        gap("gap-v", confirmed=True), model(),
        *(extra if with_band else []),
        alternative("alt-r", order=1), alternative("alt-s", order=2),
        ob_r, observation("ob-s", "alt-s", "m-d", 3),
        obj("ws-3", "WeightSet", name="w3", method="stated",
            weights={"m-d": 1.0}, provenance="ev-doc"),
        obj("pl-3", "Plan", episode="ep-1", policyBasis="pol-1",
            approvedBy={"actorId": "fixture", "date": "2026"},
            steps=[{"id": "s1", "evaluator": "mdl-1", "method": "mavt",
                    "alternatives": ["alt-r", "alt-s"],
                    "measures": ["m-d"], "weightSet": "ws-3",
                    "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}]),
        {**episode(), "rev": 2, **plan_approved(), "alternatives": ["alt-r", "alt-s"],
         "observations": ["ob-r", "ob-s"], "weightSets": ["ws-3"], "models": ["mdl-1"],
         "plan": "pl-3", "objectives": ["obj-3"]},
    )
    return g


def test_interval_band_on_point_observation_does_not_replace_the_point():
    g = _band_graph(with_band=True)
    assert_history_honest(g)
    md = g.get("m-d")
    run = evaluate(g, "pl-3", seed=1, now="2026-09-04T00:00:00Z")[0]
    rr = g.get("res-run-pl-3-s1-alt-r-m-d")
    assert rr["value"] == value_of(md, 10) == 10.0
    assert rr["raw"] == 10.0
    assert rr["uncertainty"] == {"lo": 0.0, "hi": 100.0}

    g_nb = _band_graph(with_band=False)
    run_nb = evaluate(g_nb, "pl-3", seed=1, now="2026-09-04T00:00:00Z")[0]
    assert run["ranking"] == run_nb["ranking"]


def test_interval_uncertainty_spec_missing_bounds_refused():
    g = _band_graph(with_band=True)
    put_all(g, {**g.get("unc-1"), "rev": 2, "spec": {"lo": 0}})
    with pytest.raises(ValidationError):
        evaluate(g, "pl-3", seed=1, now="2026-09-04T00:00:00Z")


def test_duplicate_step_id_across_plan_refused(two_alt_graph):
    g = two_alt_graph
    old_step = g.get("pl-1")["steps"][0]
    put_all(g, {**g.get("pl-1"), "rev": 2, "steps": [old_step, old_step]})
    before = g.snapshot_hash()
    with pytest.raises(ValidationError):
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")
    assert g.snapshot_hash() == before


def test_value_of_rejects_non_dict_valuefunction_and_non_numeric_raw():
    with pytest.raises(ValidationError):
        value_of({"metric": {"direction": "max"}, "valueFunction": "not-a-dict"}, 5)
    with pytest.raises(ValidationError):
        value_of({"metric": {"direction": "max"}}, "not-a-number")
    with pytest.raises(ValidationError):
        value_of({"metric": {"direction": "max"}}, None)


def test_evaluate_refuses_ids_already_present_in_the_graph(two_alt_graph):
    """The cross-step pre-check compares prepared ids against each other; it must also
    compare them against the store. A human object already sitting at a step-2 Result id
    would otherwise let step 1's run and Results be written, then blow up on step 2's
    first put — leaving a sealed run no episode references."""
    g = two_alt_graph
    old_step = g.get("pl-1")["steps"][0]
    put_all(
        g,
        obj("res-run-pl-1-s2-alt-x-m-a", "Rationale", text="squatter", author="a"),
        {**g.get("pl-1"), "rev": 2, "steps": [old_step, {**old_step, "id": "s2"}]},
    )
    before_log = len(g.log())
    before_hash = g.snapshot_hash()
    with pytest.raises(ValidationError) as exc:
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")
    assert "already present in the graph" in str(exc.value)
    assert g.has("run-pl-1-s1") is False
    assert len(g.log()) == before_log
    assert g.snapshot_hash() == before_hash


def test_evaluate_refuses_when_the_episode_names_a_different_plan(two_alt_graph):
    g = two_alt_graph
    put_all(g, {**g.get("pl-1"), "id": "pl-other", "rev": 1})
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "plan": "pl-other"})
    with pytest.raises(ValidationError) as exc:
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")
    assert "names a different plan" in str(exc.value)


def test_evaluate_allows_an_episode_with_no_plan_named(two_alt_graph):
    """`None`/gap on `episode.plan` stays allowed in kernel 0.1.0 — 03b's lifecycle gate
    is where the plan becomes mandatory, not the evaluator."""
    g = two_alt_graph
    ep = {k: v for k, v in g.get("ep-1").items() if k != "plan"}
    put_all(g, {**ep, "rev": ep["rev"] + 1})
    runs = evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")
    assert runs[0]["id"] == "run-pl-1-s1"


def test_inputs_hash_changes_when_measure_valuefunction_changes(two_alt_graph):
    import copy

    g1 = two_alt_graph
    g2 = copy.deepcopy(two_alt_graph)
    put_all(g2, {**g2.get("m-a"), "rev": 2,
                 "valueFunction": {"kind": "linear", "lo": 0, "hi": 100}})
    r1 = evaluate(g1, "pl-1", seed=1, now="2026-09-04T00:00:00Z")[0]
    r2 = evaluate(g2, "pl-1", seed=1, now="2026-09-04T00:00:00Z")[0]
    assert r1["inputsHash"] != r2["inputsHash"]


def test_score_sums_in_measure_id_order_not_dict_insertion_order():
    """Float addition is not associative, so the sum order has to be fixed by the code
    rather than inherited from however the WeightSet's keys were written."""
    values = {"a": {"m-1": 0.1, "m-2": 0.2, "m-3": 0.3}}
    forwards = {"m-1": 0.2, "m-2": 0.3, "m-3": 0.5}
    backwards = {k: forwards[k] for k in reversed(list(forwards))}
    assert score(values, forwards) == score(values, backwards)
    assert list(score({"z": {"m": 1.0}, "a": {"m": 1.0}}, {"m": 1.0})) == ["a", "z"]


# ---- G2 is enforced in the kernel, not only at the gate -------------------------------


def test_evaluate_refuses_an_unknown_plan_id_by_name_not_keyerror():
    """A CLI or agent caller passing a typo'd plan id gets a named refusal, not a
    bare `KeyError` out of `Graph.get` — the same contract every other refusal in
    this function already gives."""
    with pytest.raises(ValidationError) as exc:
        evaluate(Graph(), "pl-missing", seed=0, now="2026-09-04T00:00:00Z")
    assert "pl-missing" in str(exc.value)


def test_evaluate_refuses_a_plan_no_human_approved(two_alt_graph):
    """`docket evaluate` must not be a way round the plan gate. Nothing is computed
    until a human has approved the plan — the numeric path refuses for itself."""
    g = two_alt_graph
    plan = {k: v for k, v in g.get("pl-1").items() if k != "approvedBy"}
    put_all(g, {**plan, "rev": plan["rev"] + 1})
    before = g.snapshot_hash()
    with pytest.raises(ValidationError) as exc:
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")
    assert "has not been approved" in str(exc.value)
    assert g.snapshot_hash() == before


def test_evaluate_refuses_an_episode_that_has_not_reached_plan_approved(two_alt_graph):
    g = two_alt_graph
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "lifecycleState": "DRAFT", "transitions": []})
    with pytest.raises(ValidationError) as exc:
        evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")
    assert "'DRAFT'" in str(exc.value)


def test_evaluate_refuses_a_voided_or_superseded_episode(two_alt_graph):
    g = two_alt_graph
    for state in ("SUSPECT", "SUPERSEDED", "VOID"):
        ep = g.get("ep-1")
        put_all(g, {**ep, "rev": ep["rev"] + 1, "lifecycleState": state})
        with pytest.raises(ValidationError) as exc:
            evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")
        assert state in str(exc.value)


def test_every_lifecycle_state_is_either_computable_or_not_by_a_decision():
    """A state added later must not fall through into "may compute" unexamined."""
    from docket.kernel.evaluate import G2_STATES, _require_plan_approval
    from docket.objects import LIFECYCLE_STATES

    plan = {"id": "pl-1", "approvedBy": {"actorId": "pm", "date": "2026"}}
    refused = set()
    for state in LIFECYCLE_STATES:
        try:
            _require_plan_approval(plan, {"id": "ep-1", "lifecycleState": state})
        except ValidationError:
            refused.add(state)
    assert refused == set(LIFECYCLE_STATES) - set(G2_STATES)
    assert refused == {"DRAFT", "MODEL_APPROVED", "SUSPECT", "SUPERSEDED", "VOID"}


def test_the_episode_revision_is_stamped_with_the_caller_s_now(two_alt_graph):
    """The episode revision `evaluate()` writes is written at `now`, not at whenever a
    human last revised the episode."""
    g = two_alt_graph
    assert g.get("ep-1")["createdAt"] == "2026-09-04T00:00:00Z"
    evaluate(g, "pl-1", seed=1, now="2026-11-30T12:00:00Z")
    ep = g.get("ep-1")
    assert ep["createdBy"] == KERNEL_ACTOR and ep["createdAt"] == "2026-11-30T12:00:00Z"
