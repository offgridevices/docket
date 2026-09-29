# tests/kernel/test_lifecycle.py
"""Gates G1–G4 as recorded lifecycle transitions (design §5.2, §8.2)."""
import pytest

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.errors import AuthorityViolation, TransitionRefused, ValidationError
from docket.kernel.evaluate import evaluate
from docket.kernel.lifecycle import CHECKS, EDGES, HUMAN_ONLY, KERNEL_ONLY, transition
from docket.kernel.render import build_package
from docket.kernel.validate import validate
from docket.objects import LIFECYCLE_STATES
from tests.kernel.conftest import (
    H,
    alternative,
    charter,
    episode,
    gap,
    measure,
    model,
    obj,
    objective,
    observation,
    policy,
    put_all,
)
from tests.kernel.conftest import (
    pending_signature_and_ready as _pending_signature_and_ready,
)
from tests.kernel.conftest import (
    readiness_report as _readiness,
)

NOW = "2026-09-04T00:00:00Z"
AGENT = {"actorType": "agent", "actorId": "agent:test"}


def audit(g):
    """The findings a recorded transition must never introduce.

    A transition writes a new episode revision, so the record it appends has to satisfy
    the DecisionEpisode schema and the agent-authority audit — otherwise the gate would
    be producing exactly the kind of unverifiable object it exists to prevent.
    """
    return [f for f in validate(g) if f.rule in ("schema", "authority")]


def aput(g, o):
    """Write an object as the agent. Charters and Assumptions are the agent's to elicit;
    what it may never do is put a human's name on one."""
    return g.put({**o, "createdBy": AGENT}, AGENT)


def last(g, episode_id="ep-1"):
    return g.get(episode_id)["transitions"][-1]


class Bag:
    """A graph stand-in holding object shapes `Graph.put` would refuse to write.

    A saved store can be hand-edited into any shape at all, and a gate that raises
    `KeyError`/`TypeError` on one is a gate that cannot be run on the store it is meant
    to audit. These are the shapes the real store cannot produce.
    """

    def __init__(self, objs):
        self._objs = dict(objs)

    def has(self, oid):
        return oid in self._objs

    def get(self, oid):
        return self._objs[oid]

    def reachable_from(self, oid, reverse=True):
        return set(self._objs) - {oid}


# ---- the shape of the machine --------------------------------------------------------


def test_every_state_but_draft_has_a_gate_and_every_state_has_edges():
    """A new lifecycle state must not be able to appear without someone deciding what
    entering it requires. DRAFT is the only state nothing transitions *to*."""
    assert set(EDGES) == set(LIFECYCLE_STATES)
    assert set(CHECKS) == set(LIFECYCLE_STATES) - {"DRAFT"}
    assert HUMAN_ONLY & KERNEL_ONLY == set()
    assert (HUMAN_ONLY | KERNEL_ONLY) <= set(LIFECYCLE_STATES)


# ---- G1: approval of the model -------------------------------------------------------


def test_g1_refused_then_recorded_then_passes(base_graph):
    g = base_graph
    put_all(g, gap("gap-1", confirmed=False),
            obj("as-1", "Assumption", statement="s", linchpin=True, rationale="r",
                evidence={"$gap": "gap-1"}, implicationsIfWrong="i",
                indicatorsThatWouldAlter=["x"], variedInSensitivity=False),
            {**episode(), "rev": 2, "assumptions": ["as-1"]})
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert "gaps-confirmed" in e.value.unsatisfied
    ep = g.get("ep-1")
    assert ep["lifecycleState"] == "DRAFT" and ep["transitions"][-1]["refused"] is True
    assert audit(g) == []

    put_all(g, {**gap("gap-1", confirmed=True), "rev": 2})
    ep = transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert ep["lifecycleState"] == "MODEL_APPROVED" and ep["transitions"][-1]["refused"] is False
    assert "charter-three-fields" in ep["transitions"][-1]["checksSatisfied"]
    assert audit(g) == []


def test_g1_refuses_a_charter_no_human_ever_authored(base_graph):
    """Design §8.2: the three AR 5-11 fields must be human-authored or human-accepted.
    Present-and-elicited is not accepted."""
    g = base_graph
    aput(g, {**g.get("ch-1"), "rev": 2})
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert "charter-human-accepted" in e.value.unsatisfied
    # The fields are all there — only the authorship is missing.
    assert "charter-three-fields" in last(g)["checksSatisfied"]

    put_all(g, {**g.get("ch-1"), "rev": 3, "createdBy": H})
    ep = transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert ep["lifecycleState"] == "MODEL_APPROVED"


def test_g1_refuses_an_empty_ar_5_11_field_without_blaming_the_human(base_graph):
    """The two charter checks answer two different questions. A human who wrote a
    charter with a gapped field has still accepted it, and a refusal that said otherwise
    would send a reviewer looking for the wrong problem."""
    g = base_graph
    put_all(g, {**g.get("ch-1"), "rev": 2, "consequencesOfErroneousOutput": {"$gap": "gap-c"}},
            gap("gap-c", confirmed=True))
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert e.value.unsatisfied == ["charter-three-fields"]
    assert "charter-human-accepted" in last(g)["checksSatisfied"]


def test_g1_refuses_an_agent_authored_linchpin(base_graph):
    g = base_graph
    aput(g, obj("as-1", "Assumption", statement="s", linchpin=True, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i",
                indicatorsThatWouldAlter=["x"], variedInSensitivity=False))
    put_all(g, {**episode(), "rev": 2, "assumptions": ["as-1"]})
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert "linchpins-human" in e.value.unsatisfied
    # A non-linchpin assumption the agent elicited is not the gate's business.
    aput(g, {**g.get("as-1"), "rev": 2, "linchpin": False})
    ep = transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert ep["lifecycleState"] == "MODEL_APPROVED"


def test_g1_refuses_a_blocking_structural_finding_the_episode_can_reach(base_graph):
    g = base_graph
    put_all(g, objective("obj-1", provenance="ev-missing"),
            {**episode(), "rev": 2, "objectives": ["obj-1"]})
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert "no-blocking-structural" in e.value.unsatisfied


def test_g1_ignores_a_blocking_finding_another_episode_owns(base_graph):
    """`validate` runs over the whole store. The gate is on one episode's model, so a
    second episode's broken charter must not hold this one's gate shut."""
    g = base_graph
    put_all(g, policy("pol-2"), charter("ch-2", question="", decisionClassPolicy="pol-2"),
            episode("ep-2", charter="ch-2"))
    assert any(f.rule == "silence" and "ch-2" in f.objects for f in validate(g))
    ep = transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert ep["lifecycleState"] == "MODEL_APPROVED"


def test_only_blocking_findings_hold_the_model_gate_shut(two_alt_graph):  # noqa: F811
    """`run-inputs-changed` is a warning — re-run before you rely on this, not a breach
    of the record's integrity. A warning must not hold a gate shut."""
    g = two_alt_graph
    evaluate(g, "pl-1", seed=1, now=NOW)
    put_all(g, {**g.get("ob-xa"), "rev": 2, "value": 11})
    findings = validate(g)
    assert [f.rule for f in findings] == ["run-inputs-changed"]
    assert findings[0].severity == "warning"
    check = dict(CHECKS["MODEL_APPROVED"])["no-blocking-structural"]
    assert check(g, g.get("ep-1")) is True


# ---- who may drive which edge --------------------------------------------------------


def test_kernel_cannot_pass_human_gates(base_graph):
    with pytest.raises(TransitionRefused) as e:
        transition(base_graph, "ep-1", "MODEL_APPROVED", KERNEL_ACTOR, now=NOW)
    assert "human-actor" in e.value.unsatisfied
    assert base_graph.get("ep-1")["lifecycleState"] == "DRAFT"
    assert last(base_graph)["actor"] == KERNEL_ACTOR
    assert audit(base_graph) == []


def test_an_agent_may_not_transition_at_all_and_leaves_no_trace(base_graph):
    """The store refuses the write before the record lands: an agent cannot move the
    lifecycle, and cannot leave its own attempt in the episode's history either."""
    g = base_graph
    before = g.snapshot_hash()
    with pytest.raises(AuthorityViolation):
        transition(g, "ep-1", "MODEL_APPROVED", AGENT, now=NOW)
    assert g.snapshot_hash() == before
    assert g.get("ep-1")["transitions"] == []


def test_a_human_may_not_mark_an_episode_suspect(two_alt_graph):  # noqa: F811
    """SUSPECT and SUPERSEDED are what the refresh engine (G4) does to a record when its
    inputs move. They are kernel findings, not human opinions."""
    g = two_alt_graph
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "SUSPECT", H, now=NOW)
    assert "kernel-actor" in e.value.unsatisfied
    ep = transition(g, "ep-1", "SUSPECT", KERNEL_ACTOR, now=NOW)
    assert ep["lifecycleState"] == "SUSPECT"
    ep = transition(g, "ep-1", "SUPERSEDED", KERNEL_ACTOR, now=NOW)
    assert ep["lifecycleState"] == "SUPERSEDED"
    assert audit(g) == []


def test_illegal_edge(base_graph):
    with pytest.raises(TransitionRefused) as e:
        transition(base_graph, "ep-1", "SIGNED", H, now=NOW)
    assert "edge-DRAFT-to-SIGNED" in e.value.unsatisfied


def test_an_unknown_target_state_is_refused_not_recorded_as_progress(base_graph):
    with pytest.raises(TransitionRefused) as e:
        transition(base_graph, "ep-1", "APPROVED-ISH", H, now=NOW)
    assert "edge-DRAFT-to-APPROVED-ISH" in e.value.unsatisfied
    assert base_graph.get("ep-1")["lifecycleState"] == "DRAFT"


def test_void_is_reachable_from_anywhere_by_a_human_and_is_terminal(base_graph):
    g = base_graph
    ep = transition(g, "ep-1", "VOID", H, now=NOW)
    assert ep["lifecycleState"] == "VOID"
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert "edge-VOID-to-MODEL_APPROVED" in e.value.unsatisfied
    assert audit(g) == []


def test_an_unknown_episode_is_a_validation_error_not_a_key_error(base_graph):
    with pytest.raises(ValidationError) as e:
        transition(base_graph, "ep-nope", "VOID", H, now=NOW)
    assert "ep-nope" in str(e.value)


# ---- G2: approval of the plan --------------------------------------------------------


def _model_approved(g):
    """Carry `base_graph` through G1 and hang the pieces an evaluation plan needs on it."""
    put_all(g, gap("gap-v", confirmed=True), objective("obj-1", measures=["m-a"]),
            measure("m-a", "obj-1"), model("mdl-1", vva={"$gap": "gap-v"}),
            alternative("alt-x", order=1), alternative("alt-y", baseline=True, order=2),
            observation("ob-x", "alt-x", "m-a", 10), observation("ob-y", "alt-y", "m-a", 4),
            obj("ws-1", "WeightSet", name="w", method="stated", weights={"m-a": 1.0},
                provenance="ev-doc"),
            {**episode(), "rev": 2, "objectives": ["obj-1"],
             "alternatives": ["alt-x", "alt-y"], "observations": ["ob-x", "ob-y"],
             "weightSets": ["ws-1"], "models": ["mdl-1"]})
    transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    return g


def _attach_plan(g, *, approved=True, method="mavt"):
    plan = obj("pl-1", "Plan", episode="ep-1", policyBasis="pol-1",
               steps=[{"id": "s1", "evaluator": "mdl-1", "method": method,
                       "alternatives": ["alt-x", "alt-y"], "measures": ["m-a"],
                       "weightSet": "ws-1",
                       "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}])
    if approved:
        plan["approvedBy"] = {"actorId": "programme manager", "date": "2026-08-27"}
    g.put(plan, H)
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "plan": "pl-1"})
    return g


def test_g2_refuses_an_episode_with_no_plan(base_graph):
    g = _model_approved(base_graph)
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "PLAN_APPROVED", H, now=NOW)
    assert set(e.value.unsatisfied) == {"plan-present", "plan-approved-by-human",
                                        "plan-steps-have-authority", "policy-method-matches"}
    assert audit(g) == []


def test_g2_refuses_an_unapproved_plan_then_passes_once_approved(base_graph):
    g = _attach_plan(_model_approved(base_graph), approved=False)
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "PLAN_APPROVED", H, now=NOW)
    assert e.value.unsatisfied == ["plan-approved-by-human"]
    put_all(g, {**g.get("pl-1"), "rev": 2,
                "approvedBy": {"actorId": "programme manager", "date": "2026-08-27"}})
    ep = transition(g, "ep-1", "PLAN_APPROVED", H, now=NOW)
    assert ep["lifecycleState"] == "PLAN_APPROVED"
    assert ep["transitions"][-1]["checksUnsatisfied"] == []
    assert audit(g) == []


def test_g2_refuses_a_step_whose_method_is_not_the_policys(base_graph):
    g = _attach_plan(_model_approved(base_graph), method="ahp")
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "PLAN_APPROVED", H, now=NOW)
    assert e.value.unsatisfied == ["policy-method-matches"]


def test_g2_refuses_a_plan_no_human_authored(base_graph):
    """A hand-edited store can hold an agent-authored Plan carrying `approvedBy`; the
    store's write path cannot. The gate re-derives it rather than trusting the field."""
    g = _model_approved(base_graph)
    plan = obj("pl-1", "Plan", episode="ep-1", policyBasis="pol-1",
               approvedBy={"actorId": "programme manager", "date": "2026-08-27"},
               steps=[{"id": "s1", "evaluator": "mdl-1", "method": "mavt",
                       "alternatives": ["alt-x", "alt-y"], "measures": ["m-a"],
                       "weightSet": "ws-1",
                       "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}])
    with pytest.raises(AuthorityViolation):
        g.put({**plan, "createdBy": AGENT}, AGENT)
    bag = Bag({"ep-1": {"id": "ep-1", "plan": "pl-1", "charter": "ch-1"},
               "ch-1": {"decisionClassPolicy": "pol-1"},
               "pol-1": {"method": "mavt"},
               "pl-1": {**plan, "createdBy": AGENT}})
    names = dict(CHECKS["PLAN_APPROVED"])
    assert names["plan-present"](bag, bag.get("ep-1")) is True
    assert names["plan-approved-by-human"](bag, bag.get("ep-1")) is False


def test_g2_refuses_a_step_with_no_authority_citation():
    """`Plan.steps[].authority` is schema-required, so only a hand-edited store can drop
    it — which is exactly the store the gate has to be able to refuse."""
    bag = Bag({"ep-1": {"id": "ep-1", "plan": "pl-1", "charter": "ch-1"},
               "ch-1": {"decisionClassPolicy": "pol-1"},
               "pol-1": {"method": "mavt"},
               "pl-1": {"createdBy": H, "approvedBy": {"actorId": "pm", "date": "2026"},
                        "steps": [{"id": "s1", "method": "mavt"}]}})
    names = dict(CHECKS["PLAN_APPROVED"])
    assert names["plan-steps-have-authority"](bag, bag.get("ep-1")) is False


# ---- EVALUATED, PENDING_SIGNATURE, G3 SIGNED -----------------------------------------


def test_evaluated_requires_a_run_for_every_planned_step(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "EVALUATED", H, now=NOW)
    assert e.value.unsatisfied == ["every-step-has-run"]
    evaluate(g, "pl-1", seed=1, now=NOW)
    ep = transition(g, "ep-1", "EVALUATED", H, now=NOW)
    assert ep["lifecycleState"] == "EVALUATED"
    assert audit(g) == []


def test_evaluated_refuses_when_a_second_step_has_no_run(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    evaluate(g, "pl-1", seed=1, now=NOW)
    old_step = g.get("pl-1")["steps"][0]
    put_all(g, {**g.get("pl-1"), "rev": 2, "steps": [old_step, {**old_step, "id": "s2"}]})
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "EVALUATED", H, now=NOW)
    assert e.value.unsatisfied == ["every-step-has-run"]


def kput(g, o):
    """Write a kernel-authored object. Computed objects are the kernel's to write."""
    return g.put({**o, "createdBy": KERNEL_ACTOR}, KERNEL_ACTOR)


def _computed(g, oid, type_name, **fields):
    kput(g, {"id": oid, "type": type_name, "rev": 1, "createdAt": NOW, **fields})
    return g


def test_pending_signature_requires_a_readiness_report(two_alt_graph):  # noqa: F811
    g = two_alt_graph
    evaluate(g, "pl-1", seed=1, now=NOW)
    transition(g, "ep-1", "EVALUATED", H, now=NOW)
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "PENDING_SIGNATURE", H, now=NOW)
    assert e.value.unsatisfied == ["readiness-present"]
    _readiness(g, ready=False)
    ep = transition(g, "ep-1", "PENDING_SIGNATURE", H, now=NOW)
    assert ep["lifecycleState"] == "PENDING_SIGNATURE"
    assert audit(g) == []


def test_g3_refuses_a_signature_on_a_record_that_is_not_ready(two_alt_graph, tmp_path):  # noqa: F811
    """PENDING_SIGNATURE only asks that the readiness report exist — a signer is entitled
    to read a "not ready". Signing one is what G3 refuses."""
    g = two_alt_graph
    evaluate(g, "pl-1", seed=1, now=NOW)
    transition(g, "ep-1", "EVALUATED", H, now=NOW)
    _readiness(g, ready=False)
    transition(g, "ep-1", "PENDING_SIGNATURE", H, now=NOW)
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "SIGNED", H, now=NOW)
    assert set(e.value.unsatisfied) == {"commitment-present", "readiness-ready",
                                        "commitment-package-hash"}

    kput(g, {**g.get("rr-1"), "rev": 2, "ready": True})
    _computed(g, "cm-1", "Commitment", episode="ep-1", selected="alt-x",
              signer={"identity": "pm", "role": "decision authority"}, signedAt=NOW,
              conditions=[], stopRules=[], packageHash="")
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "commitment": "cm-1"})
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "SIGNED", H, now=NOW)
    assert e.value.unsatisfied == ["commitment-package-hash"]

    # G4 binds the signature to the actual latest package, not to any non-empty string —
    # build one for real and commit to its hash.
    pkg, _ = build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path)
    kput(g, {**g.get("cm-1"), "rev": 2, "packageHash": pkg["hash"]})
    ep = transition(g, "ep-1", "SIGNED", H, now=NOW)
    assert ep["lifecycleState"] == "SIGNED"
    assert audit(g) == []


def test_the_whole_walk_draft_to_signed_is_one_readable_history(two_alt_graph, tmp_path):  # noqa: F811
    """The record a reviewer reads: who moved this episode, when, under which policy
    version, and what each gate checked."""
    g = two_alt_graph
    evaluate(g, "pl-1", seed=1, now=NOW)
    transition(g, "ep-1", "EVALUATED", H, now=NOW)
    _readiness(g, ready=True)
    transition(g, "ep-1", "PENDING_SIGNATURE", H, now=NOW)
    pkg, _ = build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path)
    _computed(g, "cm-1", "Commitment", episode="ep-1", selected="alt-x",
              signer={"identity": "pm", "role": "decision authority"}, signedAt=NOW,
              conditions=[], stopRules=[], packageHash=pkg["hash"])
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "commitment": "cm-1"})
    ep = transition(g, "ep-1", "SIGNED", H, now=NOW)

    walked = [(t["from"], t["to"]) for t in ep["transitions"]]
    assert walked[-3:] == [("PLAN_APPROVED", "EVALUATED"),
                           ("EVALUATED", "PENDING_SIGNATURE"),
                           ("PENDING_SIGNATURE", "SIGNED")]
    assert all(t["refused"] is False for t in ep["transitions"])
    assert all(t["policyVersion"] == "0.1" for t in ep["transitions"])
    assert audit(g) == []


# ---- G4: the signature binds to the actual latest package ---------------------------


def _commit(g, package_hash):
    _computed(g, "cm-1", "Commitment", episode="ep-1", selected="alt-x",
              signer={"identity": "pm", "role": "decision authority"}, signedAt=NOW,
              conditions=[], stopRules=[], packageHash=package_hash)
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "commitment": "cm-1"})
    return g


def test_commitment_hash_matching_the_latest_package_satisfies_the_check(
    two_alt_graph, tmp_path,  # noqa: F811
):
    g = _pending_signature_and_ready(two_alt_graph)
    pkg, _ = build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path)
    _commit(g, pkg["hash"])

    check = dict(CHECKS["SIGNED"])["commitment-package-hash"]
    assert check(g, g.get("ep-1")) is True
    ep = transition(g, "ep-1", "SIGNED", H, now=NOW)
    assert ep["lifecycleState"] == "SIGNED"
    assert audit(g) == []


def test_commitment_hash_stale_after_a_re_render_with_changed_content_is_unsatisfied(
    two_alt_graph, tmp_path,  # noqa: F811
):
    """The commitment binds to *the* package, not *a* package: a hash that verified
    against an earlier build must not still satisfy the check once the record has
    changed and been re-rendered — named by the same `commitment-package-hash` a
    missing package fails under, since the transition record names the check that
    failed, not why."""
    g = _pending_signature_and_ready(two_alt_graph)
    stale_pkg, _ = build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path / "v1")

    # Change the record after that build: a new Risk changes the rendered "11. Risks"
    # section, so a re-render at the same `now` produces different bytes and a
    # different hash.
    put_all(g, obj("risk-late", "Risk", statement="added after the package was built",
                   kind="other", consequence="discovered late", owner="analyst",
                   status="open"))
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "risks": ["risk-late"]})
    fresh_pkg, _ = build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path / "v2")
    assert stale_pkg["hash"] != fresh_pkg["hash"]

    _commit(g, stale_pkg["hash"])
    check = dict(CHECKS["SIGNED"])["commitment-package-hash"]
    assert check(g, g.get("ep-1")) is False
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "SIGNED", H, now=NOW)
    assert "commitment-package-hash" in e.value.unsatisfied


def test_commitment_hash_with_no_package_ever_built_is_unsatisfied(two_alt_graph):  # noqa: F811
    g = _pending_signature_and_ready(two_alt_graph)
    _commit(g, "a" * 64)  # a well-formed hash, but no DecisionPackage exists to match it

    check = dict(CHECKS["SIGNED"])["commitment-package-hash"]
    assert check(g, g.get("ep-1")) is False
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "SIGNED", H, now=NOW)
    assert "commitment-package-hash" in e.value.unsatisfied


# ---- what a record says --------------------------------------------------------------


def test_the_record_names_the_actor_the_time_and_both_check_lists(base_graph):
    g = base_graph
    ep = transition(g, "ep-1", "MODEL_APPROVED", H, now="2026-10-01T09:00:00Z")
    rec = ep["transitions"][-1]
    assert rec == {"from": "DRAFT", "to": "MODEL_APPROVED", "actor": H,
                   "at": "2026-10-01T09:00:00Z", "policyVersion": "0.1",
                   "checksSatisfied": [name for name, _ in CHECKS["MODEL_APPROVED"]],
                   "checksUnsatisfied": [], "refused": False}
    assert ep["createdBy"] == H and ep["createdAt"] == "2026-10-01T09:00:00Z"


def test_a_refusal_is_written_by_the_actor_who_was_refused(base_graph):
    g = base_graph
    other = {"actorType": "human", "actorId": "someone-else"}
    with pytest.raises(TransitionRefused):
        transition(g, "ep-1", "SIGNED", other, now=NOW)
    ep = g.get("ep-1")
    assert ep["createdBy"] == other and ep["transitions"][-1]["actor"] == other
    assert ep["rev"] == 2 and ep["lifecycleState"] == "DRAFT"


def test_refusals_accumulate_rather_than_overwrite(base_graph):
    g = base_graph
    for _ in range(3):
        with pytest.raises(TransitionRefused):
            transition(g, "ep-1", "SIGNED", H, now=NOW)
    assert [t["refused"] for t in g.get("ep-1")["transitions"]] == [True, True, True]
    assert audit(g) == []


# ---- tolerance: a gate must run on a store it did not write --------------------------


def test_a_malformed_episode_is_refused_not_crashed(base_graph):
    g = base_graph
    put_all(g, {**episode(), "rev": 2, "charter": "ch-missing",
                "assumptions": ["as-missing"]})
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert set(e.value.unsatisfied) >= {"charter-three-fields", "charter-human-accepted",
                                        "no-blocking-structural", "linchpins-human"}
    assert last(g)["policyVersion"] == "unknown"


def test_no_check_raises_on_garbage(base_graph):
    """Every check, on every state, against object shapes of the wrong type throughout."""
    junk = {"id": "ep-1", "charter": 7, "assumptions": "not-a-list", "plan": ["nope"],
            "runs": None, "readiness": 3, "commitment": {"x": 1},
            "lifecycleState": "DRAFT", "transitions": []}
    bag = Bag({"ep-1": junk, "ch-1": "not-an-object", "pl-1": 12})
    for state, checks in CHECKS.items():
        for name, check in checks:
            assert check(bag, junk) in (True, False), (state, name)
            assert check(base_graph, {"id": "ep-1"}) in (True, False), (state, name)
            assert check(base_graph, {}) in (True, False), (state, name)
    # Everything the junk episode is actually asked about fails closed. `gaps-confirmed`
    # is the one honest exception: a bag holding no readable gap has no unconfirmed one.
    named = {name: check for checks in CHECKS.values() for name, check in checks}
    false_on_junk = {n for n, c in named.items() if c(bag, junk) is False}
    assert false_on_junk == set(named) - {"gaps-confirmed"}


def test_a_dangling_gap_reference_does_not_crash_the_gap_check(base_graph):
    g = base_graph
    put_all(g, obj("as-1", "Assumption", statement="s", linchpin=False, rationale="r",
                   evidence={"$gap": "gap-missing"}, implicationsIfWrong="i",
                   indicatorsThatWouldAlter=["x"], variedInSensitivity=False),
            {**episode(), "rev": 2, "assumptions": ["as-1"]})
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert e.value.unsatisfied == ["no-blocking-structural"]


# ---- G2 and the kernel agree ---------------------------------------------------------


def test_the_kernel_refuses_to_compute_until_the_gate_has_passed(base_graph):
    """The gate and the evaluator are two independent enforcements of one rule. Calling
    `evaluate()` round the side of `transition()` gets the same refusal."""
    g = _attach_plan(_model_approved(base_graph))
    with pytest.raises(ValidationError) as e:
        evaluate(g, "pl-1", seed=1, now=NOW)
    assert "MODEL_APPROVED" in str(e.value)
    transition(g, "ep-1", "PLAN_APPROVED", H, now=NOW)
    runs = evaluate(g, "pl-1", seed=1, now=NOW)
    assert runs[0]["id"] == "run-pl-1-s1"
    assert audit(g) == []


# ---- fix round 1 ---------------------------------------------------------------------


def test_g3_refuses_another_episodes_readiness_report_and_commitment(two_alt_graph):  # noqa: F811
    """The sign-swap. No hand-editing needed — only crossed wiring — and the store audits
    clean either way, so the gate is the only thing standing between a signature and a
    readiness report that was never computed for this record."""
    g = two_alt_graph
    evaluate(g, "pl-1", seed=1, now=NOW)
    transition(g, "ep-1", "EVALUATED", H, now=NOW)

    put_all(g, charter("ch-2"), episode("ep-2", charter="ch-2"))
    _computed(g, "sa-2", "StandardsAssessment", episode="ep-2", tailoring="published-21",
              ratings=[], dimensionVerdicts={}, aggregationRule="k-of-n", k=1,
              kernelVersion=KERNEL_VERSION)
    _computed(g, "ms-2", "MandateScorecard", episode="ep-2", rows=[],
              kernelVersion=KERNEL_VERSION)
    _computed(g, "rr-2", "ReadinessReport", episode="ep-2", standardsAssessment="sa-2",
              mandateScorecard="ms-2", blockers=[], warnings=[], openGaps=[],
              openExclusions=[], flipSummary={}, biasChecksStatus=[], computedBiasRisks=[],
              ready=True, policyVersion="0.1", kernelVersion=KERNEL_VERSION, seed=1)
    _computed(g, "cm-2", "Commitment", episode="ep-2", selected="alt-x",
              signer={"identity": "pm", "role": "decision authority"}, signedAt=NOW,
              conditions=[], stopRules=[], packageHash="f" * 64)
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H,
                "readiness": "rr-2", "commitment": "cm-2"})

    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "PENDING_SIGNATURE", H, now=NOW)
    assert e.value.unsatisfied == ["readiness-present"]
    assert audit(g) == []

    # And the same borrowed objects cannot carry it through G3 either.
    _readiness(g, ready=True)
    transition(g, "ep-1", "PENDING_SIGNATURE", H, now=NOW)
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "commitment": "cm-2"})
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "SIGNED", H, now=NOW)
    assert set(e.value.unsatisfied) == {"commitment-present", "commitment-package-hash"}


def test_a_broken_log_chain_anywhere_holds_the_model_gate_shut(base_graph):
    """A tampered log is not another episode's problem. `rule_log_chain` names whichever
    object sat at the broken sequence number, which may be nothing this episode reaches —
    but a store whose chain does not verify cannot be read at all, this record included."""
    g = base_graph
    put_all(g, obj("r-far", "Rationale", text="nothing to do with ep-1", author="someone"))
    assert "r-far" not in g.reachable_from("ep-1", reverse=False)
    g._log[-1]["prevHash"] = "0" * 64  # a hand-edited store is the case this guards
    findings = validate(g)
    assert any(f.rule == "log-chain" and f.objects == ("r-far",) for f in findings)
    check = dict(CHECKS["MODEL_APPROVED"])["no-blocking-structural"]
    assert check(g, g.get("ep-1")) is False


def test_transition_tolerates_a_hand_edited_transitions_field(base_graph):
    """`Graph.load` verifies hashes and the chain, not the schema, so a re-chained store
    can hold `transitions: 7`. That must refuse or record — never `TypeError`."""
    g = base_graph
    g._latest["ep-1"] = {**g.get("ep-1"), "transitions": 7}

    # G1 refuses, because the corrupt field is itself a blocking schema finding — but it
    # refuses, records and raises, rather than dying on `7 + [record]`.
    with pytest.raises(TransitionRefused) as e:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    assert e.value.unsatisfied == ["no-blocking-structural"]
    assert [t["to"] for t in g.get("ep-1")["transitions"]] == ["MODEL_APPROVED"]

    # And on the gateless abandon edge it goes through, with a readable history again.
    g._latest["ep-1"] = {**g.get("ep-1"), "transitions": 7}
    ep = transition(g, "ep-1", "VOID", H, now=NOW)
    assert ep["lifecycleState"] == "VOID"
    assert [t["to"] for t in ep["transitions"]] == ["VOID"]


def test_a_citation_is_a_document_and_a_paragraph():
    """`Plan.steps[].authority` and `Plan.approvedBy` are schema-shaped on the write path.
    On a hand-edited store the gate has to insist on the shape itself, or the check names
    something stronger than it asks."""
    names = dict(CHECKS["PLAN_APPROVED"])
    base = {"ch-1": {"decisionClassPolicy": "pol-1"}, "pol-1": {"method": "mavt"},
            "ep-1": {"id": "ep-1", "plan": "pl-1", "charter": "ch-1"}}

    def bag_with(**plan_over):
        plan = {"createdBy": H, "approvedBy": {"actorId": "pm", "date": "2026-08-27"},
                "steps": [{"id": "s1", "method": "mavt",
                           "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}]}
        return Bag({**base, "pl-1": {**plan, **plan_over}})

    good = bag_with()
    assert names["plan-steps-have-authority"](good, good.get("ep-1")) is True
    assert names["plan-approved-by-human"](good, good.get("ep-1")) is True

    for authority in ({"note": "not a citation"}, "see the memo",
                      {"document": "DoDI 5000.84"}, {"paragraph": "§4.2.i"},
                      {"document": "", "paragraph": "§4.2.i"}):
        bag = bag_with(steps=[{"id": "s1", "method": "mavt", "authority": authority}])
        assert names["plan-steps-have-authority"](bag, bag.get("ep-1")) is False, authority

    for approved_by in ({"unrelated": 1}, "the boss said so", {"actorId": "pm"},
                        {"date": "2026-08-27"}, {"actorId": "", "date": "2026-08-27"}):
        bag = bag_with(approvedBy=approved_by)
        assert names["plan-approved-by-human"](bag, bag.get("ep-1")) is False, approved_by
