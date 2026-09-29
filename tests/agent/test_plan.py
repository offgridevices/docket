import logging
from pathlib import Path

import pytest

from docket.agent.backend import RecordedBackend
from docket.agent.plan import (
    AUTHORITY_CATALOGUE,
    approve_plan,
    author_weight_set,
    propose_plan,
    step_rationale,
)
from docket.errors import AuthorityViolation, BackendError, ValidationError
from docket.kernel.lifecycle import CHECKS

A = {"actorType": "agent", "actorId": "agent:recorded"}
H = {"actorType": "human", "actorId": "shreyash"}
NOW = "2026-09-04T00:00:00Z"


@pytest.fixture
def demo_a_draft():
    """Demo A's hand-built record, with its hand-approved plan's approval stripped.

    `build()` already carries a fully human-approved `pl-cbo`
    (`approvedBy={"actorId": "shreyash", ...}`, written by a human actor at rev 1) — Demo
    A's own purpose is to reproduce CBO's published rankings end to end, including through
    G2, so its plan is approved from the moment it is built. This task's tests are about
    the AGENT's proposal path instead: `propose_plan` refuses (by design) to write into an
    episode that already names an approved plan, and `propose_plan` always mints a fresh,
    non-colliding plan id (`pl-{episode}-agent-{n}`), so it would never touch or replace
    `pl-cbo` itself even if allowed to run.

    So this fixture puts one human revision of `pl-cbo` that drops `approvedBy` (optional
    at the schema's Plan level) before returning the graph — leaving `ep-cbo-2013.plan`
    pointed at a plan that is present but not yet approved, the state the tests below are
    actually about. `demos/a_cbo_gcv_2013/build.py` itself is untouched.
    """
    from demos.a_cbo_gcv_2013.build import H as DEMO_H
    from demos.a_cbo_gcv_2013.build import build

    g = build()
    pl = g.get("pl-cbo")
    stripped = {k: v for k, v in pl.items() if k != "approvedBy"}
    stripped["rev"] = pl["rev"] + 1
    stripped["createdBy"] = DEMO_H
    g.put(stripped, DEMO_H)
    return g


def test_propose_plan_builds_one_step_per_weight_set_with_a_doctrine_citation(demo_a_draft):
    g = demo_a_draft
    b = RecordedBackend(Path("tests/fixtures/recorded/plan.json"))
    plan = propose_plan(b, g, "ep-cbo-2013", actor=A, now=NOW)
    steps = {s["id"]: s for s in plan["steps"]}
    assert set(steps) == {"primary", "secondary"}
    assert steps["primary"]["weightSet"] == "ws-primary"
    assert steps["secondary"]["weightSet"] == "ws-secondary"
    assert steps["primary"]["measures"] == ["m-leth", "m-mob", "m-pax", "m-prot"]
    assert steps["secondary"]["measures"] == ["m-leth", "m-mob", "m-prot", "m-squad"]
    # [pre-flight defect 7] the evaluator is sourced, not invented
    assert all(s["evaluator"] == "mdl-cbo-metric" for s in plan["steps"])
    assert all(s["method"] == "mavt" for s in plan["steps"])
    # exact dict: no `range` key, so flip.py falls back to 0..1
    assert {"kind": "weight", "target": "ws-secondary:m-squad"} in \
        steps["secondary"]["sensitivitySweeps"]
    # the non-linchpin ws-primary:m-prot binding is not swept
    assert steps["primary"].get("sensitivitySweeps", []) == []
    for s in plan["steps"]:
        assert s["authority"]["document"] and s["authority"]["paragraph"]
        assert s["authority"]["document"] in {v["document"] for v in AUTHORITY_CATALOGUE.values()}
    # BiasCheck.checkType, not .type
    assert steps["primary"]["biasChecks"] == ["bc-structured"]
    # the agent may not approve
    assert "approvedBy" not in plan
    assert g.get("ep-cbo-2013")["plan"] == plan["id"]
    assert g.get(plan["id"])["createdBy"] == A


def test_rationale_is_persisted_as_its_own_object(demo_a_draft):
    # [pre-flight defect 6] Plan.steps[] is additionalProperties:false and has no rationale
    g = demo_a_draft
    b = RecordedBackend(Path("tests/fixtures/recorded/plan.json"))
    plan = propose_plan(b, g, "ep-cbo-2013", actor=A, now=NOW)
    for s in plan["steps"]:
        assert "rationale" not in s
        r = step_rationale(g, plan["id"], s["id"])
        assert r and r["type"] == "Rationale" and r["text"]
        assert r["author"].startswith("recorded")


def test_no_backend_still_produces_a_valid_plan(demo_a_draft):
    g = demo_a_draft
    plan = propose_plan(None, g, "ep-cbo-2013", actor=A, now=NOW)
    assert all(s["authority"]["paragraph"] == AUTHORITY_CATALOGUE["sensitivity"]["paragraph"]
               for s in plan["steps"])
    assert step_rationale(g, plan["id"], "primary") is None


def test_only_a_human_may_approve(demo_a_draft):
    g = demo_a_draft
    plan = propose_plan(None, g, "ep-cbo-2013", actor=A, now=NOW)
    with pytest.raises(AuthorityViolation):
        approve_plan(g, plan["id"], A, now=NOW)
    assert "approvedBy" not in g.get(plan["id"])
    approved = approve_plan(g, plan["id"], H, now=NOW)
    assert approved["approvedBy"]["actorId"] == "shreyash"
    assert "plan-approved-by-human" in [n for n, _ in CHECKS["PLAN_APPROVED"]]


def test_propose_plan_will_not_replace_an_approved_plan(demo_a_draft):
    g = demo_a_draft
    plan = propose_plan(None, g, "ep-cbo-2013", actor=A, now=NOW)
    approve_plan(g, plan["id"], H, now=NOW)
    with pytest.raises(AuthorityViolation):
        propose_plan(None, g, "ep-cbo-2013", actor=A, now=NOW)


# ---- author_weight_set -------------------------------------------------------------------


def test_author_weight_set_writes_a_weightset_and_links_it_to_the_episode(demo_a_draft):
    g = demo_a_draft
    ws = author_weight_set(g, "ep-cbo-2013", H, now=NOW, name="equal",
                           weights={"obj-capability": 0.5, "obj-cost": 0.5},
                           rationale="no source weighs these; equal until one does")
    assert ws["id"] == "ws-ep-cbo-2013-human"
    assert ws["rev"] == 1
    assert ws["method"] == "stated"
    assert ws["createdBy"] == H
    assert ws["provenance"] == {"$gap": "gap-ws-ep-cbo-2013-human"}

    gap = g.get("gap-ws-ep-cbo-2013-human")
    assert gap["type"] == "InsufficientEvidence"
    assert gap["confirmedBy"]["actorId"] == "shreyash"
    assert gap["whyNotFound"] == "no source weighs these; equal until one does"

    ep = g.get("ep-cbo-2013")
    assert "ws-ep-cbo-2013-human" in ep["weightSets"]
    # Demo A's own two hand-built weight sets are untouched, not replaced.
    assert {"ws-primary", "ws-secondary"} <= set(ep["weightSets"])


def test_author_weight_set_defaults_the_gaps_reason_when_no_rationale_given(demo_a_draft):
    g = demo_a_draft
    author_weight_set(g, "ep-cbo-2013", H, now=NOW, name="equal",
                      weights={"obj-capability": 0.5, "obj-cost": 0.5})
    gap = g.get("gap-ws-ep-cbo-2013-human")
    assert "authored these weights directly" in gap["whyNotFound"]


def test_author_weight_set_supersedes_as_a_new_revision_not_a_second_set(demo_a_draft):
    g = demo_a_draft
    first = author_weight_set(g, "ep-cbo-2013", H, now=NOW,
                              name="first", weights={"obj-capability": 0.5, "obj-cost": 0.5})
    second = author_weight_set(g, "ep-cbo-2013", H, now="2026-09-05T00:00:00Z",
                               name="second", weights={"obj-capability": 0.7, "obj-cost": 0.3})
    assert second["id"] == first["id"]
    assert second["rev"] == 2
    assert second["name"] == "second"
    ep = g.get("ep-cbo-2013")
    assert ep["weightSets"].count("ws-ep-cbo-2013-human") == 1
    # The gap behind it is revised too, not left stale or duplicated.
    assert g.get("gap-ws-ep-cbo-2013-human")["rev"] == 2


def test_author_weight_set_validation_failures_reuse_check_weights(demo_a_draft):
    """No second copy of the rule: the message is `kernel.evaluate.check_weights`'s
    own wording, naming the missing objective by id."""
    g = demo_a_draft
    with pytest.raises(ValidationError) as exc:
        author_weight_set(g, "ep-cbo-2013", H, now=NOW, name="x",
                          weights={"obj-capability": 1.0})
    assert "obj-cost" in str(exc.value)
    assert "step measures without a weight" in str(exc.value)


def test_author_weight_set_needs_a_name(demo_a_draft):
    g = demo_a_draft
    with pytest.raises(ValidationError):
        author_weight_set(g, "ep-cbo-2013", H, now=NOW, name="   ",
                          weights={"obj-capability": 0.5, "obj-cost": 0.5})


def test_author_weight_set_refuses_a_non_human_actor(demo_a_draft):
    """The approval gate sits on the model, and weights are the same kind of human
    value judgement — the agent may not author its own evaluation basis any more than
    it may approve the Plan that uses it."""
    g = demo_a_draft
    with pytest.raises(AuthorityViolation):
        author_weight_set(g, "ep-cbo-2013", A, now=NOW, name="x",
                          weights={"obj-capability": 0.5, "obj-cost": 0.5})


def test_author_weight_set_refuses_a_lifecyclestate_outside_draft_or_model_approved(
    demo_a_draft,
):
    g = demo_a_draft
    ep = g.get("ep-cbo-2013")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "lifecycleState": "EVALUATED"}, H)
    with pytest.raises(ValidationError) as exc:
        author_weight_set(g, "ep-cbo-2013", H, now=NOW, name="x",
                          weights={"obj-capability": 0.5, "obj-cost": 0.5})
    assert "EVALUATED" in str(exc.value)
    assert "DRAFT or MODEL_APPROVED" in str(exc.value)


def test_author_weight_set_refuses_once_named_plan_is_approved():
    """Decoupled from `lifecycleState` on purpose (an otherwise-valid graph a real
    transition would never produce): the episode is left at `MODEL_APPROVED` while
    `pl-cbo` already carries a human `approvedBy`, from `build()` itself. This is the
    fact `_named_approved_plan` derives directly from the graph rather than trusting
    the state label — the same defensive posture `kernel.lifecycle.c_plan_approved`
    takes, and the second, independent guard
    `test_author_weights_refuses_once_a_plan_is_approved`
    (`tests/api/test_agent_routes.py`) cannot exercise on its own, because reaching
    `PLAN_APPROVED` through a real transition always trips the lifecycleState check
    first."""
    from demos.a_cbo_gcv_2013.build import H as DEMO_H
    from demos.a_cbo_gcv_2013.build import build
    from docket.kernel.lifecycle import transition

    g = build()  # pl-cbo is approved exactly as build() leaves it
    transition(g, "ep-cbo-2013", "MODEL_APPROVED", DEMO_H, now=NOW)
    with pytest.raises(AuthorityViolation) as exc:
        author_weight_set(g, "ep-cbo-2013", H, now=NOW, name="x",
                          weights={"obj-capability": 0.5, "obj-cost": 0.5})
    assert "pl-cbo" in str(exc.value)


def test_evaluator_refusal_names_the_ambiguity(demo_a_draft):
    g = demo_a_draft
    ep = g.get("ep-cbo-2013")
    second = {**g.get("mdl-cbo-metric"), "id": "mdl-other", "rev": 1, "createdBy": H,
              "inputs": ["m-prot", "m-leth", "m-mob", "m-pax", "m-squad"]}
    g.put(second, H)
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H,
           "models": ["mdl-cbo-metric", "mdl-other"]}, H)
    with pytest.raises(ValidationError) as exc:
        propose_plan(None, g, "ep-cbo-2013", actor=A, now=NOW)
    assert "mdl-other" in str(exc.value) and "will not pick between models" in str(exc.value)


def test_propose_plan_refuses_an_unknown_episode(demo_a_draft):
    g = demo_a_draft
    with pytest.raises(ValidationError):
        propose_plan(None, g, "ep-does-not-exist", actor=A, now=NOW)


def test_propose_plan_refuses_a_caller_supplied_plan_id_already_in_the_graph(demo_a_draft):
    """I1 probe A: `plan_id` is a public parameter a frontend route maps onto; a caller
    reusing an existing id (here, the human-authored `pl-cbo` itself) is plain API misuse
    and must be refused, named, before anything is written — not silently adopted, and not
    partially written into and then rejected by the store's own append-only check."""
    g = demo_a_draft
    log_len_before = len(g.log())
    with pytest.raises(ValidationError) as exc:
        propose_plan(None, g, "ep-cbo-2013", actor=A, now=NOW, plan_id="pl-cbo")
    assert "pl-cbo" in str(exc.value)
    assert len(g.log()) == log_len_before
    assert step_rationale(g, "pl-cbo", "primary") is None
    # the episode still names the pre-existing pl-cbo; nothing was touched
    assert g.get("ep-cbo-2013")["plan"] == "pl-cbo"


def test_propose_plan_orphans_no_rationale_when_the_plan_write_itself_fails(demo_a_draft):
    """I1 probe B: force the Plan `put` to fail — a hand-edited Policy whose `method` is
    outside `Plan.steps[].method`'s enum, the same probe the review used — and confirm
    nothing survives the failed call: not a Rationale object under the plan id that would
    have been minted, and not the plan id itself, so a retry does not silently re-adopt a
    half-written id. Rationale objects are written only after the Plan `put` succeeds, so a
    Plan failure orphans nothing [pre-flight defect 6 / I1]."""
    g = demo_a_draft
    g._latest["pol-cbo"] = {**g.get("pol-cbo"), "method": "not-a-real-method"}
    log_len_before = len(g.log())
    b = RecordedBackend(Path("tests/fixtures/recorded/plan.json"))
    with pytest.raises(ValidationError):
        propose_plan(b, g, "ep-cbo-2013", actor=A, now=NOW)
    assert len(g.log()) == log_len_before
    assert not g.has("pl-ep-cbo-2013-agent-1")
    assert step_rationale(g, "pl-ep-cbo-2013-agent-1", "primary") is None


def test_weight_sweep_requires_the_measure_to_be_in_the_steps_measures(demo_a_draft, caplog):
    """M2: a linchpin binding whose weight-set id matches a step, but whose measure that
    step does not weight (`ws-primary:m-squad` — `m-squad` is not one of `ws-primary`'s
    measures), is not emitted as a sweep on that step. [M3] the drop is logged, since a
    linchpin assumption quietly losing its sweep is the more consequential silent failure."""
    g = demo_a_draft
    ep = g.get("ep-cbo-2013")
    bad_binding = {
        "id": "as-bad-binding", "type": "Assumption", "rev": 1, "createdBy": H,
        "createdAt": NOW,
        "statement": "A linchpin bound to a measure its weight set does not weight.",
        "linchpin": True, "rationale": "test probe for M2",
        "evidence": "ev-cbo-2013",
        "implicationsIfWrong": "none — this assumption exists only to probe the sweep match",
        "indicatorsThatWouldAlter": ["n/a"],
        "variedInSensitivity": True,
        "parameterBinding": {"kind": "weight", "target": "ws-primary:m-squad"},
    }
    g.put(bad_binding, H)
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H,
           "assumptions": [*ep["assumptions"], "as-bad-binding"]}, H)

    caplog.set_level(logging.WARNING, logger="docket.agent.plan")
    plan = propose_plan(None, g, "ep-cbo-2013", actor=A, now=NOW)
    bad_sweep = {"kind": "weight", "target": "ws-primary:m-squad"}
    for s in plan["steps"]:
        assert bad_sweep not in s["sensitivitySweeps"]
    assert any("claimed by no plan step" in r.message for r in caplog.records)


def test_a_weight_set_ref_the_graph_does_not_have_is_skipped_and_logged(demo_a_draft, caplog):
    """M3: an episode naming a weight set that is not in the graph must not raise and must
    not silently vanish from the record — the skip is logged, and the other weight sets
    still produce their steps normally."""
    g = demo_a_draft
    ep = g.get("ep-cbo-2013")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H,
           "weightSets": ["ws-primary", "ws-does-not-exist", "ws-secondary"]}, H)

    caplog.set_level(logging.WARNING, logger="docket.agent.plan")
    plan = propose_plan(None, g, "ep-cbo-2013", actor=A, now=NOW)
    assert {s["id"] for s in plan["steps"]} == {"primary", "secondary"}
    assert any("ws-does-not-exist" in r.message for r in caplog.records)


def test_backend_naming_an_unknown_step_id_is_ignored(demo_a_draft, caplog):
    """I4: a backend response naming a step id the skeleton does not have is ignored (and
    logged) rather than silently accepted or crashing; the real steps still get a real
    citation from the response, not the default."""
    g = demo_a_draft
    b = RecordedBackend(Path("tests/fixtures/recorded/plan-unknown-step.json"))
    caplog.set_level(logging.WARNING, logger="docket.agent.plan")
    plan = propose_plan(b, g, "ep-cbo-2013", actor=A, now=NOW)
    steps = {s["id"]: s for s in plan["steps"]}
    assert steps["primary"]["authority"]["paragraph"] == \
        AUTHORITY_CATALOGUE["cba-decmat"]["paragraph"]
    assert steps["secondary"]["authority"]["paragraph"] == \
        AUTHORITY_CATALOGUE["oas-4-10"]["paragraph"]
    assert any("phantom" in r.message for r in caplog.records)


def test_backend_omitting_a_step_defaults_to_sensitivity_and_logs(demo_a_draft, caplog):
    """I4: a backend response that omits a step defaults that step's authority to
    `sensitivity` — the dangerous path, since it silently substitutes a citation the model
    never chose, so it must be logged and the default value must be exactly right."""
    g = demo_a_draft
    b = RecordedBackend(Path("tests/fixtures/recorded/plan-omitted-step.json"))
    caplog.set_level(logging.WARNING, logger="docket.agent.plan")
    plan = propose_plan(b, g, "ep-cbo-2013", actor=A, now=NOW)
    steps = {s["id"]: s for s in plan["steps"]}
    assert steps["primary"]["authority"]["paragraph"] == \
        AUTHORITY_CATALOGUE["oas-4-10"]["paragraph"]
    assert steps["secondary"]["authority"]["paragraph"] == \
        AUTHORITY_CATALOGUE["sensitivity"]["paragraph"]
    assert step_rationale(g, plan["id"], "secondary") is None
    assert any("secondary" in r.message and "sensitivity" in r.message
               for r in caplog.records)


def test_schema_invalid_response_raises_backend_error_and_writes_nothing(demo_a_draft):
    """I4/R10: a response that never validates (every retry prompt recorded, so the
    failure is `BackendError` and not `RecordingMissing`) exhausts `complete_json`'s
    retries and writes nothing — no Plan, no Rationale, no episode revision."""
    g = demo_a_draft
    ids_before = set(g.ids())
    log_len_before = len(g.log())
    b = RecordedBackend(Path("tests/fixtures/recorded/plan-invalid.json"))
    with pytest.raises(BackendError) as exc:
        propose_plan(b, g, "ep-cbo-2013", actor=A, now=NOW)
    # not RecordingMissing (a BackendError subclass and the trap this test guards against):
    # the failure must be complete_json exhausting its retries, not a fixture gap.
    assert type(exc.value) is BackendError
    assert set(g.ids()) == ids_before
    assert len(g.log()) == log_len_before
    assert g.get("ep-cbo-2013")["plan"] == "pl-cbo"


def test_proposed_plan_and_episode_revision_validate_clean(demo_a_draft):
    """The agent's write must not introduce any NEW blocking finding into the whole store.

    Demo A's bare `build()` (before `run()` ever attaches a Claim to every evidence item)
    already carries two pre-existing `silent-omission` findings of its own — that is a
    property of the record before this stage runs, not something `propose_plan` can or
    should fix, so the assertion is a before/after diff rather than an absolute zero.
    """
    from docket.kernel.validate import validate

    g = demo_a_draft

    def blocking():
        return {(f.rule, f.objects) for f in validate(g, g.get("pol-cbo"))
                if f.severity == "blocking"}

    before = blocking()
    b = RecordedBackend(Path("tests/fixtures/recorded/plan.json"))
    propose_plan(b, g, "ep-cbo-2013", actor=A, now=NOW)
    assert blocking() == before


def test_proposed_plan_reaches_plan_approved_and_evaluate_reproduces_demo_a_rankings(
    demo_a_draft,
):
    """End to end: propose, approve (human), transition through G1/G2, and evaluate() —
    naming the same measures/weights/alternatives as CBO's own hand-built `pl-cbo` must
    reproduce the same ranking, because a ranking is a property of the numbers, not of who
    authored the Plan object naming them."""
    from demos.a_cbo_gcv_2013.build import H as DEMO_H
    from demos.a_cbo_gcv_2013.build import build
    from docket.kernel.evaluate import evaluate
    from docket.kernel.lifecycle import transition

    g = demo_a_draft
    plan = propose_plan(None, g, "ep-cbo-2013", actor=A, now=NOW)
    approve_plan(g, plan["id"], H, now=NOW)
    transition(g, "ep-cbo-2013", "MODEL_APPROVED", DEMO_H, now=NOW)
    ep = transition(g, "ep-cbo-2013", "PLAN_APPROVED", DEMO_H, now=NOW)
    assert ep["lifecycleState"] == "PLAN_APPROVED"

    agent_runs = {r["step"]: r for r in evaluate(g, plan["id"], seed=1, now=NOW)}

    # CBO's own hand-built plan, on an independent copy of the same record.
    g2 = build()
    transition(g2, "ep-cbo-2013", "MODEL_APPROVED", DEMO_H, now=NOW)
    transition(g2, "ep-cbo-2013", "PLAN_APPROVED", DEMO_H, now=NOW)
    hand_runs = {r["step"]: r for r in evaluate(g2, "pl-cbo", seed=1, now=NOW)}

    for step_id in ("primary", "secondary"):
        assert agent_runs[step_id]["ranking"] == hand_runs[step_id]["ranking"]
