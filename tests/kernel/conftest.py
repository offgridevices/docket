# tests/kernel/conftest.py
"""Builders for minimal, valid graphs. All ids are deterministic strings."""
from pathlib import Path

import pytest

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.kernel.evaluate import evaluate
from docket.kernel.lifecycle import transition
from docket.store import Graph

H = {"actorType": "human", "actorId": "fixture"}
NOW = "2026-09-04T00:00:00Z"


def obj(oid, t, **fields):
    return {"id": oid, "type": t, "rev": 1, "createdBy": H, "createdAt": NOW, **fields}


def policy(oid="pol-1", **over):
    base = dict(name="test", version="0.1", decisionClass="trade-study", method="mavt",
                tailoring="published-21", aggregationK=1, requiredBiasChecks=[],
                requireAllLinchpinsVaried=True, prohibitedExclusionReasons=["time-or-resource"],
                blockingRules=[], nSimplex=200)
    base.update(over)
    return obj(oid, "Policy", **base)


def evidence(oid, **over):
    base = dict(title=oid, evidenceType="Document", publisher="p", published="2020",
                pointer={"uri": "u", "custodian": "c"},
                classification={"level": "U", "metadataLevel": "U"},
                scopeOfValidity={"builtToAnswer": "q", "questionClass": "other",
                                 "intendedUse": "u"},
                reviewStatus="reviewed", reliabilitySteps=["drs-1"])
    base.update(over)
    return obj(oid, "Evidence", **base)


def drs(oid="drs-1", **over):
    base = dict(description="d", method="source-review", performedBy="x",
                documentation="ev-doc")
    base.update(over)
    return obj(oid, "DataReliabilityStep", **base)


def charter(oid="ch-1", **over):
    base = dict(question="q", decisionToBeMade="d", consequencesOfErroneousOutput="c",
                questionClass="other",
                scope={"included": ["a"], "excluded": []}, authority={"signer": "s"},
                decisionClassPolicy="pol-1")
    base.update(over)
    return obj(oid, "Charter", **base)


def episode(oid="ep-1", **over):
    base = dict(sequence=1, charter="ch-1", lifecycleState="DRAFT", transitions=[],
                objectives=[], alternatives=[],
                groundRules=[], constraints=[], assumptions=[], evidenceRegister=[],
                scenarios=[], claims=[],
                risks=[], biasChecks=[], mandateElements=[], observations=[], weightSets=[],
                models=[], runs=[],
                flipAnalyses=[], narratives=[], asOf="2026-09-04")
    base.update(over)
    return obj(oid, "DecisionEpisode", **base)


def gate_checks(to_state):
    """The names of the checks `kernel.lifecycle` runs for `to_state`.

    Read from the gate itself rather than copied, so a fixture's recorded transition
    history says what the gate actually asked, not what it asked when the fixture was
    written.
    """
    from docket.kernel.lifecycle import CHECKS

    return [name for name, _ in CHECKS[to_state]]


def transition_record(frm, to, at=NOW, actor=None, policy_version="0.1"):
    """One passing transition record, shaped exactly as `kernel.lifecycle` writes it."""
    return {"from": frm, "to": to, "actor": dict(actor or H), "at": at,
            "policyVersion": policy_version, "checksSatisfied": gate_checks(to),
            "checksUnsatisfied": [], "refused": False}


def plan_approved(at_g1="2026-08-20T00:00:00Z", at_g2="2026-08-27T00:00:00Z", **over):
    """Lifecycle fields for an episode that has passed G1 and G2.

    Splat into an episode revision that is about to be evaluated: `evaluate()` refuses a
    plan whose episode has not passed G2, so a fixture that computes has to have been
    approved, and has to carry the history that says by whom and when.
    """
    fields = {
        "lifecycleState": "PLAN_APPROVED",
        "transitions": [transition_record("DRAFT", "MODEL_APPROVED", at=at_g1),
                        transition_record("MODEL_APPROVED", "PLAN_APPROVED", at=at_g2)],
    }
    fields.update(over)
    return fields


def assert_history_honest(g, episode_id="ep-1"):
    """Every check an episode's recorded transitions claim was satisfied really is.

    A fixture that hand-writes an approval history is asserting that the gate would have
    let this record through. When that is false — a dangling `vvaRecord` makes
    `no-blocking-structural` a lie, say — the fixture is exercising the kernel over a
    record the product would have refused, and whatever the test then proves is about a
    graph that could not exist. Call it once per fixture family, straight after the
    fixture is built and before the test degrades anything on purpose.
    """
    from docket.kernel.lifecycle import CHECKS

    ep = g.get(episode_id)
    lies = []
    for record in ep.get("transitions") or []:
        checks = dict(CHECKS.get(record.get("to"), []))
        for name in record.get("checksSatisfied") or []:
            if name not in checks or not checks[name](g, ep):
                lies.append((record.get("to"), name))
    assert lies == [], f"{episode_id} records checks it does not satisfy: {lies}"


def alternative(oid, baseline=False, order=1, status="evaluated", **over):
    base = dict(name=oid, description=oid, status=status, baselineFlag=baseline,
                enteredOrder=order)
    base.update(over)
    return obj(oid, "Alternative", **base)


def gap(oid, impact="degrading", confirmed=True, **over):
    base = dict(sought="s", whereLookedFor=["x"], whyNotFound="w", impact=impact,
                indicatorsThatWouldResolve=[])
    base.update(over)
    o = obj(oid, "InsufficientEvidence", **base)
    if confirmed:
        o["confirmedBy"] = {"actorId": "fixture", "date": "2026-09-04"}
    return o


def assumption_(oid, linchpin=False, **over):
    """An Assumption at the shape `elicit` writes — `evidence` may be a gap marker."""
    base = dict(statement=f"assumption {oid}", linchpin=linchpin, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False)
    base.update(over)
    return obj(oid, "Assumption", **base)


def program_(oid="prg-1", **over):
    base = dict(name="p", charter="ch-1", episodes=["ep-1"], refreshTriggers=[], diffs=[])
    base.update(over)
    return obj(oid, "DecisionProgram", **base)


def claim(oid, evidence_ids, **over):
    base = dict(text=oid, questionClass="other", assessableAt={"level": "U"},
                supportedBy=[{"evidence": e} for e in evidence_ids])
    base.update(over)
    return obj(oid, "Claim", **base)


def objective(oid, measures=(), **over):
    base = dict(name=oid, priority="primary", provenance="ev-doc", measures=list(measures))
    base.update(over)
    return obj(oid, "Objective", **base)


def measure(oid, objective, **over):
    base = dict(objective=objective, task="t", attribute="a", measure="m",
                metric={"units": "u", "direction": "max"}, criteria={"threshold": 1})
    base.update(over)
    return obj(oid, "Measure", **base)


def observation(oid, alt, measure, value, evidence="ev-doc", **over):
    base = dict(alternative=alt, measure=measure, value=value, evidence=evidence)
    base.update(over)
    return obj(oid, "Observation", **base)


def model(oid, vva=None, **over):
    base = dict(name=oid, definition={"kind": "simulation", "version": "1"}, intendedUse="u",
                questionClass="other", vvaRecord=vva if vva is not None else f"{oid}-vva",
                qualificationStatus="validated")
    base.update(over)
    return obj(oid, "Model", **base)


def bias_check(oid, check_type, status="performed", evidence="ev-doc", **over):
    base = dict(checkType=check_type, requiredBy="pol-1", producedEvidence=evidence,
                status=status)
    base.update(over)
    return obj(oid, "BiasCheck", **base)


@pytest.fixture
def base_graph():
    g = Graph()
    for o in (policy(), evidence("ev-doc"), drs(), charter(), episode()):
        g.put(o, H)
    return g


def put_all(g, *objs):
    for o in objs:
        g.put(o, H)
    return g


# ---------------------------------------------------------------------------------
# A complete episode: one record that scores state 1 on every question of `full-36`.
#
# Most of the fixtures above build the *minimum* graph a single predicate needs, which
# leaves the positive branch of the other sixty-odd predicates unexercised. This one
# goes the other way: a whole, well-formed decision record, from charter through
# commitment, that a reviewer could read as an example of what "no concerns" looks
# like. It is also the base the degraded variants are cut down from — each of those
# removes exactly one thing and names the question that notices.
# ---------------------------------------------------------------------------------

COMPLETE_NOW = "2026-09-04T00:00:00Z"
COMPLETE_SEED = 11
COMPLETE_RUN_ID = "run-pl-1-s1"


def _complete_charter():
    return charter(
        question="Which of the three candidate configurations best meets the stated need?",
        decisionToBeMade="Select one configuration to carry into the next phase.",
        consequencesOfErroneousOutput="A configuration is carried forward that cannot meet "
                                      "the need, and the error is found only after test.",
        questionClass="other",
        scope={"included": ["the three candidate configurations", "unit cost"],
               "excluded": ["sustainment beyond ten years"]},
        definitions=[{"term": "configuration", "text": "a vehicle build state with a fixed "
                                                       "set of subsystems"},
                     {"term": "unit cost", "text": "average procurement unit cost in "
                                                   "then-year dollars"}],
        conditionsOfInterest=["desert", "urban"],
        limitations=[{"statement": "Only two of the three configurations have been tested "
                                   "in the urban condition.",
                      "mitigation": "The untested configuration is scored from modelled "
                                    "results and flagged in the evidence register."}],
        authority={"signer": "programme manager", "board": "configuration steering group"},
        successCriteria=["a signed selection with recorded conditions"],
        decisionClassPolicy="pol-1",
    )


def _complete_evidence():
    """Three evidence items, all reviewed, all with a reliability step, an explained
    limitation, a scope of validity in the charter's question class and a recorded reason
    for being in the register at all (GAO-23-106549 F3)."""
    shared = dict(
        classification={"level": "U", "metadataLevel": "U"},
        reviewStatus="reviewed",
        reviewers=[{"name": "reviewer", "role": "analyst", "date": "2026-08-10"}],
        scopeOfValidity={"builtToAnswer": "configuration comparison",
                         "questionClass": "other", "conditions": ["desert", "urban"],
                         "intendedUse": "scoring the three configurations",
                         "validUntil": "2028-01-01"},
    )
    return [
        evidence("ev-doc", title="Configuration comparison report", **shared,
                 pointer={"uri": "file://reports/comparison.pdf", "custodian": "PM office"},
                 publisher="programme office", published="2026-06-01",
                 reliabilitySteps=["drs-1"],
                 limitations=[{"statement": "Urban results are modelled, not tested.",
                               "impact": "Urban scores carry wider bands."}],
                 inclusionReason="It is the only side-by-side comparison of all three."),
        _dataset_evidence(shared),
        evidence("ev-bias", title="Premortem and outside-view memo", **shared,
                 pointer={"uri": "file://memos/premortem.pdf", "custodian": "PM office"},
                 publisher="programme office", published="2026-07-15",
                 reliabilitySteps=["drs-3"],
                 limitations=[{"statement": "One participant could not attend.",
                               "impact": "The logistics view is under-represented."}],
                 inclusionReason="It records the bias checks the policy requires."),
    ]


def _dataset_evidence(shared):
    ev = evidence("ev-test", title="Instrumented test dataset", evidenceType="Dataset",
                  custodian="test centre", schemaRef="test-schema-v3", **shared,
                  pointer={"uri": "file://data/test-runs.csv", "custodian": "test centre"},
                  reliabilitySteps=["drs-2"],
                  limitations=[{"statement": "Two runs were voided for instrumentation "
                                             "faults.",
                                "impact": "The affected condition has four runs, not six."}],
                  inclusionReason="It is the measured source behind every observation.")
    # The Dataset variant has no publisher/published; the builder's Document defaults
    # would fail the catalogue's discriminator.
    ev.pop("publisher", None)
    ev.pop("published", None)
    return ev


def _complete_vva():
    return obj(
        "vva-1", "VVARecord",
        problemStatement="ch-1",
        requirementsAndAcceptabilityCriteria="Scores must be reproducible to six decimals "
                                             "and traceable to a measured observation.",
        assumptionsCapabilitiesLimitationsRisks={
            "assumptions": ["Weights are stated, not derived."],
            "capabilities": ["Additive value over two measures."],
            "limitations": ["No interaction terms between measures."],
            "risks": ["Weight elicitation may anchor on the first configuration seen."]},
        methodology="Deterministic additive value model, verified against hand calculation.",
        accreditationDecision={"authority": "chief engineer", "date": "2025-01-15",
                               "scope": "configuration comparison, desert and urban",
                               "basis": "document", "document": "ev-doc"},
        issues=["None outstanding."],
        lessonsLearned="Record the weight elicitation session, not just its result.",
        sections=[{"name": "Verification", "content": "Hand-checked against two worked "
                                                      "examples."},
                  {"name": "Validation", "content": "Compared with the instrumented test "
                                                    "dataset."},
                  {"name": "Accreditation", "content": "Accredited for this question class."}],
    )


def _complete_observations():
    """Every (alternative, measure) pair, each evidence-backed; two carry interval bands."""
    return [
        observation("ob-a-m1", "alt-a", "m-1", 80, evidence="ev-test",
                    uncertainty="unc-a-m1", variedInSensitivity=True),
        observation("ob-a-m2", "alt-a", "m-2", 50, evidence="ev-test",
                    uncertainty="unc-a-m2"),
        observation("ob-b-m1", "alt-b", "m-1", 60, evidence="ev-test"),
        observation("ob-b-m2", "alt-b", "m-2", 40, evidence="ev-test"),
        observation("ob-base-m1", "alt-base", "m-1", 40, evidence="ev-test"),
        observation("ob-base-m2", "alt-base", "m-2", 30, evidence="ev-test"),
    ]


def _complete_pre_run_objects():
    """Everything the evaluator needs, in dependency-agnostic order (references are
    checked by `validate`, not by `put`)."""
    linear = {"kind": "linear", "lo": 0, "hi": 100}
    return [
        policy(requiredBiasChecks=["premortem", "outside-view"], tailoring="full-36"),
        *_complete_evidence(),
        drs("drs-1", description="Traced twelve figures back to the test log.",
            method="tracing", performedBy="analyst", date="2026-06-20"),
        drs("drs-2", description="Electronic checks for range and completeness.",
            method="electronic-testing", performedBy="data engineer", date="2026-06-22"),
        drs("drs-3", description="Corroborated the memo against the session notes.",
            method="corroboration", performedBy="analyst", date="2026-07-16"),
        _complete_charter(),
        obj("gr-1", "GroundRule", statement="Costs are in then-year dollars.",
            source="ev-doc"),
        obj("con-1", "Constraint", statement="Unit cost may not exceed the programme cap.",
            kind="programmatic", source="ev-doc",
            implications="Configurations above the cap are scored but cannot be selected."),
        obj("as-1", "Assumption",
            statement="The stated weight on capability reflects the sponsor's priorities.",
            linchpin=True, rationale="Elicited in the weighting session and minuted.",
            evidence="ev-doc",
            implicationsIfWrong="The ranking could reverse in favour of the cheaper option.",
            indicatorsThatWouldAlter=["a revised priority statement from the sponsor"],
            variedInSensitivity=True,
            parameterBinding={"kind": "weight", "target": "ws-1:m-1"}),
        obj("as-2", "Assumption",
            statement="Configuration A's unit cost holds at the quoted figure.",
            linchpin=True, rationale="Quoted in the comparison report and not yet contracted.",
            evidence="ev-doc",
            implicationsIfWrong="A cost growth of forty per cent would change the ranking.",
            indicatorsThatWouldAlter=["a contract award above the quoted figure"],
            variedInSensitivity=True,
            parameterBinding={"kind": "observation", "target": "ob-a-m2"}),
        obj("scn-desert", "Scenario", name="Desert", description="Open terrain, high heat.",
            rationale="The condition the sponsor named first.", conditions=["desert"],
            source="ev-doc"),
        obj("scn-urban", "Scenario", name="Urban", description="Dense terrain, short lines.",
            rationale="The condition the capability gap is written against.",
            conditions=["urban"], source="ev-doc"),
        obj("act-1", "Action", description="Re-run the weighting session with the sponsor.",
            owner="analyst", dueDate="2026-10-01", status="open"),
        obj("act-2", "Action", description="Confirm the quoted unit cost at contract award.",
            owner="programme manager", dueDate="2026-12-01", status="open"),
        obj("rk-1", "Risk", statement="The weighting session anchored on the first "
                                      "configuration presented.",
            kind="bias-anchoring", consequence="The ranking would favour that configuration.",
            owner="analyst", mitigation=["act-1"],
            monitor="Compare against the outside-view memo.",
            acceptanceCriteria="Weights reproduced in a second session.",
            status="mitigated", evidence=["ev-bias"]),
        bias_check("bc-1", "premortem", evidence="ev-bias", performedBy="analyst",
                   performedAt="2026-07-15"),
        bias_check("bc-2", "outside-view", evidence="ev-bias", performedBy="analyst",
                   performedAt="2026-07-15"),
        obj("me-1", "MandateElement",
            text="State the cost of each configuration considered.",
            source="tasking memo ¶3", status="satisfied", satisfiedBy=["cl-1"]),
        objective("obj-1", measures=["m-1", "m-2"], name="Meet the stated need at cost",
                  description="Capability against unit cost.", provenance="ev-doc"),
        measure("m-1", "obj-1", task="Close the capability gap", attribute="Capability",
                measure="Composite capability score",
                metric={"units": "score", "direction": "max"},
                criteria={"threshold": 50, "objective": 80}, conditions=["desert", "urban"],
                valueFunction=linear),
        measure("m-2", "obj-1", task="Stay within the cost cap", attribute="Cost",
                measure="Average procurement unit cost",
                metric={"units": "usd-millions", "direction": "min"},
                criteria={"threshold": 60, "objective": 35}, conditions=["desert", "urban"],
                valueFunction=linear),
        alternative("alt-a", order=1, status="evaluated", name="Configuration A",
                    description="Highest capability, highest cost."),
        alternative("alt-b", order=2, status="evaluated", name="Configuration B",
                    description="Middle capability, middle cost."),
        alternative("alt-base", baseline=True, order=3, status="evaluated",
                    name="Current fleet", description="The status quo, carried as baseline."),
        obj("unc-a-m1", "Uncertainty", kind="interval", spec={"lo": 70, "hi": 90},
            lexiconBand="likely", lexicon="A"),
        obj("unc-a-m2", "Uncertainty", kind="interval", spec={"lo": 20, "hi": 90},
            lexiconBand="roughly-even-chance", lexicon="A"),
        *_complete_observations(),
        obj("ws-1", "WeightSet", name="Sponsor-stated weights", method="stated",
            weights={"m-1": 0.6, "m-2": 0.4}, provenance="ev-doc"),
        _complete_vva(),
        obj("mdl-1", "Model", name="Additive value model",
            definition={"kind": "code", "version": "1.2.0"},
            intendedUse="Rank configurations on capability and cost.",
            questionClass="other", vvaRecord="vva-1", qualificationStatus="qualified",
            inputs=["m-1", "m-2"],
            limitations=[{"statement": "No interaction between capability and cost.",
                          "justification": "The sponsor's value model is additive by "
                                           "construction; recorded in the VV&A."}]),
        obj("pl-1", "Plan", episode="ep-1", policyBasis="pol-1",
            approvedBy={"actorId": "programme manager", "date": "2026-08-27"},
            # An explicit empty list, not an absent field: the record states that the
            # plan was followed as written, rather than saying nothing about it.
            deviations=[],
            steps=[{"id": "s1", "evaluator": "mdl-1", "method": "mavt",
                    "alternatives": ["alt-a", "alt-b", "alt-base"],
                    "measures": ["m-1", "m-2"], "weightSet": "ws-1",
                    "biasChecks": ["bc-1", "bc-2"],
                    "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}]),
        episode(
            **plan_approved(),
            objectives=["obj-1"], alternatives=["alt-a", "alt-b", "alt-base"],
            groundRules=["gr-1"], constraints=["con-1"], assumptions=["as-1", "as-2"],
            evidenceRegister=["ev-doc", "ev-test", "ev-bias"],
            scenarios=["scn-desert", "scn-urban"], risks=["rk-1"],
            biasChecks=["bc-1", "bc-2"], mandateElements=["me-1"],
            observations=[o["id"] for o in _complete_observations()],
            weightSets=["ws-1"], models=["mdl-1"], plan="pl-1",
            distribution=[{"to": "configuration steering group", "date": "2026-09-04"}],
            asOf="2026-09-04"),
    ]


def complete_graph(**episode_over):
    """A whole decision record: charter, plan, evaluation run, flips, claims, commitment.

    `episode_over` is applied to the final (human) episode revision, so a caller can cut
    exactly one thing out and see which question notices. It cannot retroactively change
    what the baked-in Commitment's `packageHash` names, below, since that package is
    necessarily built (and its hash fixed) one revision earlier than `episode_over` is
    applied — a package cannot embed the hash of a commitment that will point back at
    it. No current caller passes `episode_over`, so this never bites in practice.
    """
    from docket.kernel.evaluate import evaluate
    from docket.kernel.flip import flip_analysis
    from docket.kernel.render import build_package

    g = Graph()
    put_all(g, *_complete_pre_run_objects())

    run = evaluate(g, "pl-1", seed=COMPLETE_SEED, now=COMPLETE_NOW)[0]
    flip_analysis(g, run["id"], seed=COMPLETE_SEED, now=COMPLETE_NOW)

    aggregate = f"res-{run['id']}-{run['ranking'][0]}"
    put_all(
        g,
        claim("cl-1", ["ev-doc"],
              text="Configuration A ranks first on the sponsor's stated weights.",
              section="evaluation-results", derivedFrom=run["id"], resultRef=aggregate,
              addresses=["obj-1"], mandateElements=["me-1"]),
        claim("cl-2", ["ev-test"],
              text="Every configuration was scored from the instrumented test dataset.",
              section="evidence-register", addresses=["obj-1"]),
        claim("cl-bias", ["ev-bias"],
              text="A premortem and an outside-view review were performed before scoring.",
              section="bias-checks"),
        obj("nar-1", "Narrative", episode="ep-1", section="evaluation-results",
            sentences=[{"text": "Configuration A ranks first under the stated weights.",
                        "cites": ["cl-1", run["id"]]}]),
    )
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H,
                "claims": ["cl-1", "cl-2", "cl-bias"], "narratives": ["nar-1"]})

    # G4 (kernel.lifecycle.c_commitment_hash) requires the signed Commitment's
    # packageHash to equal the graph's own latest built package for this episode — a
    # placeholder string cannot satisfy that once the record reaches SIGNED
    # (test_readiness.test_a_ready_report_is_what_unlocks_the_signature_gate does).
    # Build the real package from the record as it stands right here — before the
    # Commitment exists to be rendered by it — and commit to that hash.
    pkg, _ = build_package(g, "ep-1", rendering="full", now=COMPLETE_NOW, out_dir=None)
    put_all(
        g,
        obj("cm-1", "Commitment", episode="ep-1", selected=run["ranking"][0],
            signer={"identity": "programme manager", "role": "decision authority"},
            signedAt="2026-09-04",
            conditions=[{"text": "Confirm the quoted unit cost at contract award.",
                         "verifyBy": "act-2", "dueDate": "2026-12-01"}],
            stopRules=["Reopen if the awarded unit cost exceeds the quoted figure by 20%."],
            packageHash=pkg["hash"]),
    )
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "commitment": "cm-1",
                **episode_over})
    return g


@pytest.fixture
def complete_episode():
    return complete_graph()


def revise(g, oid, *, drop=(), actor=None, **over):
    """Write the next revision of an existing object as a human edit.

    `drop` removes keys outright (a field set to `None` would fail schema validation),
    which is what a degraded-variant fixture needs when the point is that something is
    *absent* rather than empty.
    """
    current = g.get(oid)
    body = {k: v for k, v in current.items() if k not in drop}
    who = H if actor is None else actor
    g.put({**body, "rev": current["rev"] + 1, "createdBy": who, **over}, who)
    return g


# ---- the two committed demo stores, as graphs (Task 15) --------------------------------
# The API suite's `demo_a_present` (tests/api/conftest.py) is the model, including the skip
# when a store is not built. `Graph.load` reads a copy into memory; nothing here may write
# to demos/*/out.

REPO = Path(__file__).resolve().parents[2]


def _demo_graph(name: str):
    p = REPO / "demos" / name / "out" / "graph"
    if not (p / "log.jsonl").is_file():
        pytest.skip(f"{name} store not built yet")
    return Graph.load(p)


@pytest.fixture
def demo_a_graph():
    return _demo_graph("a_cbo_gcv_2013")


@pytest.fixture
def demo_b_graph():
    return _demo_graph("b_omfv_2019_2023")


# ---- a two-alternative, plan-approved graph, and the walk to PENDING_SIGNATURE ---------
# Shared by the evaluate, flip, standards, lifecycle and commit suites (moved here from
# `test_evaluate.py`/`test_lifecycle.py`, Task 15 fix round 1, so no test module imports a
# fixture or a private helper from a sibling test module).


def eval_measure(oid, direction="max", vf=None):
    m = obj(oid, "Measure", objective="obj-1", task="t", attribute="a", measure=oid,
            metric={"units": "pct", "direction": direction}, criteria={"$exclusion": "ex-crit"})
    if vf:
        m["valueFunction"] = vf
    return m


def eval_observation(oid, alt, m, value, ev="ev-doc"):
    return obj(oid, "Observation", alternative=alt, measure=m, value=value, evidence=ev)


def eval_model(oid="mdl-1"):
    return obj(oid, "Model", name="mavt",
               definition={"kind": "code", "version": "0.1.0"}, intendedUse="u",
               questionClass="other", vvaRecord={"$gap": "gap-v"},
               qualificationStatus="validated")


@pytest.fixture
def two_alt_graph(base_graph):
    g = base_graph
    put_all(g,
            obj("ex-crit", "Exclusion",
                target={"kind": "Measure", "label": "thresholds"},
                reasonType="data-unavailable",
                reason="none published",
                authority={"who": "w", "role": "r", "date": "2013"},
                retainedInStructure=True),
            obj("gap-v", "InsufficientEvidence", sought="s", whereLookedFor=["x"],
                whyNotFound="w", impact="informational",
                indicatorsThatWouldResolve=[],
                confirmedBy={"actorId": "fixture", "date": "2026"}),
            obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
                measures=["m-a", "m-b"]),
            eval_measure("m-a"), eval_measure("m-b"), eval_model(),
            alternative("alt-x", order=1), alternative("alt-y", baseline=True, order=2),
            eval_observation("ob-xa", "alt-x", "m-a", 10),
            eval_observation("ob-xb", "alt-x", "m-b", 0),
            eval_observation("ob-ya", "alt-y", "m-a", 0),
            eval_observation("ob-yb", "alt-y", "m-b", {"lo": 20, "hi": 40}),
            obj("ws-1", "WeightSet", name="w", method="stated",
                weights={"m-a": 0.5, "m-b": 0.5}, provenance="ev-doc"),
            obj("pl-1", "Plan", episode="ep-1", policyBasis="pol-1",
                approvedBy={"actorId": "fixture", "date": "2026"},
                steps=[{"id": "s1", "evaluator": "mdl-1", "method": "mavt",
                        "alternatives": ["alt-x", "alt-y"],
                        "measures": ["m-a", "m-b"], "weightSet": "ws-1",
                        "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}]),
            {**episode(), "rev": 2, **plan_approved(),
             "alternatives": ["alt-x", "alt-y"],
             "observations": ["ob-xa", "ob-xb", "ob-ya", "ob-yb"],
             "weightSets": ["ws-1"], "models": ["mdl-1"], "plan": "pl-1",
             "objectives": ["obj-1"]})
    return g


def kernel_put(g, o):
    """Write a kernel-authored object. Computed objects are the kernel's to write."""
    return g.put({**o, "createdBy": KERNEL_ACTOR, "createdAt": NOW}, KERNEL_ACTOR)


def readiness_report(g, *, ready=True, n=1):
    """A readiness report `rr-{n}` (with its assessment and scorecard) for `ep-1`, and the
    episode revision that names it. `n` lets a test file a second report after a first."""
    kernel_put(g, {"id": f"sa-{n}", "type": "StandardsAssessment", "rev": 1, "episode": "ep-1",
                   "tailoring": "published-21", "ratings": [], "dimensionVerdicts": {},
                   "aggregationRule": "k-of-n", "k": 1, "kernelVersion": KERNEL_VERSION})
    kernel_put(g, {"id": f"ms-{n}", "type": "MandateScorecard", "rev": 1, "episode": "ep-1",
                   "rows": [], "kernelVersion": KERNEL_VERSION})
    kernel_put(g, {"id": f"rr-{n}", "type": "ReadinessReport", "rev": 1, "episode": "ep-1",
                   "standardsAssessment": f"sa-{n}", "mandateScorecard": f"ms-{n}",
                   "blockers": [], "warnings": [], "openGaps": [], "openExclusions": [],
                   "flipSummary": {}, "biasChecksStatus": [], "computedBiasRisks": [],
                   "ready": ready, "policyVersion": "0.1", "kernelVersion": KERNEL_VERSION,
                   "seed": 1})
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "readiness": f"rr-{n}"})
    return g


def pending_signature_and_ready(g, *, ready=True):
    """Carry `two_alt_graph` through EVALUATED and a readiness report to PENDING_SIGNATURE,
    so a test can attach its own Commitment and probe the G3 checks directly. `ready=False`
    files a report the SIGNED gate's `readiness-ready` will refuse."""
    evaluate(g, "pl-1", seed=1, now=NOW)
    transition(g, "ep-1", "EVALUATED", H, now=NOW)
    readiness_report(g, ready=ready)
    transition(g, "ep-1", "PENDING_SIGNATURE", H, now=NOW)
    return g
