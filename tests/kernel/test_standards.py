# tests/kernel/test_standards.py
import pytest

from docket import KERNEL_VERSION
from docket.kernel.evaluate import evaluate
from docket.kernel.findings import Finding
from docket.kernel.scope import check_scope
from docket.kernel.standards import (
    PREDICATES,
    STATE2_REASONS,
    Context,
    build_context,
    dimension_verdicts,
    score_question,
    score_standards,
)
from docket.kernel.validate import validate
from docket.standard import load_rules, question_ids
from tests.kernel.conftest import (
    COMPLETE_NOW,
    H,
    bias_check,
    charter,
    claim,
    complete_graph,
    episode,
    evidence,
    gap,
    model,
    obj,
    objective,
    policy,
    put_all,
    revise,
)

NOW = "2026-09-04T00:00:00Z"

_VVA_BASE = dict(
    problemStatement="ch-1", requirementsAndAcceptabilityCriteria="r",
    assumptionsCapabilitiesLimitationsRisks={"assumptions": ["a"], "capabilities": ["c"],
                                              "limitations": ["l"], "risks": ["r"]},
    methodology="m",
)


def _vva(oid, sections, **acc_over):
    acc = {"authority": "PM", "date": "2026-01-01", "scope": "s", "basis": "document"}
    acc.update(acc_over)
    return obj(oid, "VVARecord", accreditationDecision=acc, sections=sections, **_VVA_BASE)


def test_every_question_has_a_rule_and_every_predicate_exists():
    rules = {r["question"]: r for r in load_rules()}
    assert set(rules) == set(question_ids())
    for r in rules.values():
        assert r["clauses"][-1]["when"] == "always"
        for c in r["clauses"]:
            assert c["when"] in PREDICATES, c["when"]
            assert c["state"] in (1, 2, 3, 4)


def test_empty_episode_scores_mostly_state_4(base_graph):
    sa = score_standards(base_graph, "ep-1", "published-21", k=1, now="2026-09-04T00:00:00Z")
    states = {r["questionId"]: r["state"] for r in sa["ratings"] if r["applicable"]}
    # The base graph's charter is complete but there is no plan: DES-1 falls through
    # charter_complete_and_plan_approved to charter_complete, scoring 2, not 4.
    assert len(states) == 21 and states["DES-1"] == 2 and states["EXE-5"] == 4
    assert sa["dimensionVerdicts"]["reliability"]["verdict"] == "insufficient_to_conclude"
    inapplicable = [r for r in sa["ratings"] if not r["applicable"]]
    assert len(inapplicable) == 15
    assert all(r["tailoringReason"] for r in inapplicable)
    assert all(r["state"] is None for r in inapplicable)


def test_charter_drives_des_2_and_des_3(base_graph):
    g = base_graph
    put_all(g, {**charter(), "rev": 2,
                "definitions": [{"term": "force structure",
                                 "text": "the number and type of units"}]})
    sa = score_standards(g, "ep-1", "published-21", k=1, now="2026-09-04T00:00:00Z")
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["DES-2"] == 1 and states["DES-3"] == 1


def test_dimension_rule_generally_x_and_qualifier():
    ratings = [{"questionId": q, "applicable": True, "state": 1}
               for q in ["DES-2", "DES-4", "DES-7", "EXE-1", "EXE-2", "PRE-3", "PRE-4"]]
    ratings[1]["state"] = 2  # DES-4 some concerns
    dv = dimension_verdicts(ratings, k=1)
    assert dv["objectivity"]["verdict"] == "generally_objective"
    assert "DES-4" in dv["objectivity"]["qualifier"]
    ratings[2]["state"] = 2  # two state-2 > k
    assert dimension_verdicts(ratings, k=1)["objectivity"]["verdict"] == "not_objective"
    ratings[2]["state"] = 4
    assert dimension_verdicts(ratings, k=1)["objectivity"]["verdict"] == "insufficient_to_conclude"


def test_predicates_return_justification_ids(base_graph):
    ctx = build_context(base_graph, "ep-1")
    ok, ids = PREDICATES["charter_complete"](base_graph, base_graph.get("ep-1"), ctx)
    assert ok and ids == ["ch-1"]


def test_pre2_no_claims_scores_4(base_graph):
    sa = score_standards(base_graph, "ep-1", "published-21", k=1, now="2026-09-04T00:00:00Z")
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["PRE-2"] == 4


def test_pre1_and_pre2_with_supported_claim_and_no_runs(base_graph):
    """A claim resting on reviewed evidence that carries reliability steps (base_graph's
    ev-doc) is enough for claims_all_supported: PRE-1 scores 2 with no runs at all, and
    PRE-2 (no silence, no blocking gaps reachable from the episode) scores <= 2."""
    g = base_graph
    put_all(g, claim("cl-1", ["ev-doc"]), {**episode(), "rev": 2, "claims": ["cl-1"]})
    sa = score_standards(g, "ep-1", "published-21", k=1, now="2026-09-04T00:00:00Z")
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["PRE-1"] == 2
    assert states["PRE-2"] <= 2


def test_predicates_tolerate_a_garbage_episode(base_graph):
    """Every predicate but `always` must survive a completely malformed `ep` — an empty
    dict has none of the list/dict fields any predicate expects — and answer (False, [])
    rather than raising (KeyError/TypeError/AttributeError)."""
    ctx = build_context(base_graph, "ep-1")
    garbage: dict = {}
    for name, fn in PREDICATES.items():
        if name == "always":
            continue
        ok, ids = fn(base_graph, garbage, ctx)
        assert (ok, ids) == (False, []), name


def test_context_is_a_dataclass_with_expected_fields(base_graph):
    ctx = build_context(base_graph, "ep-1")
    assert isinstance(ctx, Context)
    assert ctx.policy["id"] == "pol-1"
    assert isinstance(ctx.findings, list) and isinstance(ctx.scope, list)


def test_score_question_raises_for_a_bogus_question_id(base_graph):
    ctx = build_context(base_graph, "ep-1")
    ep = base_graph.get("ep-1")
    bogus_rule = {"question": "ZZZ-1", "clauses": [{"when": "assumptions_listed", "state": 1}]}
    try:
        score_question(base_graph, ep, ctx, "ZZZ-1", {"ZZZ-1": bogus_rule})
        raised = False
    except AssertionError:
        raised = True
    assert raised


def test_score_standards_puts_a_standards_assessment_and_id_increments(base_graph):
    sa1 = score_standards(base_graph, "ep-1", "published-21", k=1, now="2026-09-04T00:00:00Z")
    assert sa1["id"] == "sa-ep-1-published-21-1"
    assert base_graph.has(sa1["id"])
    sa2 = score_standards(base_graph, "ep-1", "published-21", k=1, now="2026-09-04T00:00:01Z")
    assert sa2["id"] == "sa-ep-1-published-21-2"


# ---- fix round 1 -------------------------------------------------------------------

def test_dangling_assumption_id_is_not_all_evidenced_and_leaves_no_ref_integrity_finding(
    base_graph,
):
    """DES-4's state-1 clause is `assumptions_all_have_rationale`. An episode that lists
    an assumption id the store cannot find must not score state 1 for it (a dangling
    reference cannot be judged "all" anything), and the resulting StandardsAssessment
    must not itself carry a dangling justification id — `validate()` walks
    `ratings[].justification[]` as refs, so a stray one would show up as `ref-integrity`
    on the assessment."""
    g = base_graph
    put_all(g, {**episode(), "rev": 2, "assumptions": ["as-missing"]})
    sa = score_standards(g, "ep-1", "published-21", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["DES-4"] != 1
    findings = validate(g, g.get("pol-1"))
    assert not any(f.rule == "ref-integrity" and sa["id"] in f.objects for f in findings)


def test_dimension_with_no_mapped_applicable_questions_is_insufficient_to_conclude():
    dv = dimension_verdicts([], k=1)
    for dim in ("objectivity", "validity", "reliability"):
        assert dv[dim]["verdict"] == "insufficient_to_conclude"
        assert dv[dim]["mapped"] == []
        assert dv[dim]["states"] == []


# ---- DES-6 fidelity ladder -----------------------------------------------------------

def _flip(oid, assumption_id):
    return obj(oid, "FlipAnalysis", run="run-x",
               parameter={"kind": "weight", "target": "t", "label": "l"},
               assumption=assumption_id, currentValue=0.5,
               range={"lo": 0.0, "hi": 1.0, "source": "default"},
               flipThreshold=0.7, flipDistance=0.2, direction="up",
               rankingBefore=[], rankingAfter=[], kernelVersion=KERNEL_VERSION)


def _des6_all_linchpins_flipped(g):
    put_all(g,
            obj("as-1", "Assumption", statement="s", linchpin=True, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            _flip("fa-1", "as-1"),
            {**episode(), "rev": 2, "assumptions": ["as-1"], "flipAnalyses": ["fa-1"]})


def _des6_some_linchpins_flipped(g):
    put_all(g,
            obj("as-1", "Assumption", statement="s1", linchpin=True, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            obj("as-2", "Assumption", statement="s2", linchpin=True, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            _flip("fa-1", "as-1"),
            {**episode(), "rev": 2, "assumptions": ["as-1", "as-2"], "flipAnalyses": ["fa-1"]})


def _des6_any_assumption_varied(g):
    put_all(g,
            obj("as-1", "Assumption", statement="s1", linchpin=False, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=True),
            {**episode(), "rev": 2, "assumptions": ["as-1"]})


def _des6_assumptions_listed_only(g):
    put_all(g,
            obj("as-1", "Assumption", statement="s1", linchpin=False, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            {**episode(), "rev": 2, "assumptions": ["as-1"]})


def _des6_none(g):
    pass  # base_graph already has no assumptions


@pytest.mark.parametrize(("build", "expected"), [
    (_des6_all_linchpins_flipped, 1),
    (_des6_some_linchpins_flipped, 2),
    (_des6_any_assumption_varied, 2),
    (_des6_assumptions_listed_only, 3),
    (_des6_none, 4),
], ids=["all-flipped", "some-flipped", "any-varied", "listed-only", "none"])
def test_des6_fidelity_ladder(base_graph, build, expected):
    build(base_graph)
    sa = score_standards(base_graph, "ep-1", "published-21", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["DES-6"] == expected


# ---- EXE-3 fidelity ladder -----------------------------------------------------------

def _ms_study(oid, **over):
    """An `MSStudy` Evidence: the catalogue requires model/scenarios/vvaRecord for that
    discriminator and has no use for the Document variant's publisher/published."""
    ev = evidence(oid, evidenceType="MSStudy", **over)
    ev.pop("publisher", None)
    ev.pop("published", None)
    return ev


def _clean_model(g, mid="mdl-1", vva_id="vva-1", **over):
    """A model with a signed, in-date VV&A record whose questionClass matches the
    charter's — the shape EXE-3 has no concerns about."""
    put_all(g, _vva(vva_id, [{"name": "Problem Statement", "content": "x"}],
                     document="ev-doc"),
            model(mid, vva=vva_id, **over))


def _exe3_clean_model(g):
    _clean_model(g)
    put_all(g, {**episode(), "rev": 2, "models": ["mdl-1"]})


def _exe3_document_reuse_only(g):
    """A Document reused past its purpose is EXE-4's business (data scope), not EXE-3's:
    attributing a document's reuse to a *model* question is a fidelity error against
    GAO-16-820 App. I 'Models'."""
    _clean_model(g)
    put_all(g,
            evidence("ev-other", scopeOfValidity={"builtToAnswer": "q2",
                                                   "questionClass": "force-structure",
                                                   "intendedUse": "u"}),
            claim("cl-1", ["ev-other"]),
            {**episode(), "rev": 2, "models": ["mdl-1"], "claims": ["cl-1"]})


def _exe3_model_use_past_purpose(g):
    _clean_model(g, questionClass="force-structure")  # charter questionClass is "other"
    put_all(g, {**episode(), "rev": 2, "models": ["mdl-1"]})


def _exe3_ms_study_reuse(g):
    """The F1 shape: the reused artefact is an M&S study, so the model question is
    the one that degrades."""
    _clean_model(g)
    put_all(g,
            _vva("vva-ms", [{"name": "Problem Statement", "content": "x"}], document="ev-doc"),
            model("mdl-ms", vva="vva-ms"),
            obj("scn-ms", "Scenario", name="s", description="d", rationale="r",
                conditions=["desert"], source="ev-doc"),
            _ms_study("ev-ms", model="mdl-ms", scenarios=["scn-ms"], vvaRecord="vva-ms",
                      scopeOfValidity={"builtToAnswer": "q2",
                                       "questionClass": "force-structure",
                                       "intendedUse": "u"}),
            claim("cl-1", ["ev-ms"]),
            {**episode(), "rev": 2, "models": ["mdl-1", "mdl-ms"], "claims": ["cl-1"]})


def _exe3_reaccreditation_required(g):
    put_all(g, _vva("vva-1", [{"name": "Problem Statement", "content": "x"}],
                     document="ev-doc", date="2019-01-01"),
            model("mdl-1", vva="vva-1"),
            {**episode(), "rev": 2, "models": ["mdl-1"]})


def _exe3_no_models(g):
    pass  # base_graph already has no models


@pytest.mark.parametrize(("build", "expected"), [
    (_exe3_clean_model, 1),
    (_exe3_document_reuse_only, 1),
    (_exe3_model_use_past_purpose, 3),
    (_exe3_ms_study_reuse, 3),
    (_exe3_reaccreditation_required, 2),
    (_exe3_no_models, 4),
], ids=["clean-vva", "document-reuse-only", "model-use-past-purpose", "ms-study-reuse",
        "reaccreditation-required", "no-models"])
def test_exe3_fidelity_ladder(base_graph, build, expected):
    build(base_graph)
    sa = score_standards(base_graph, "ep-1", "full-36", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["EXE-3"] == expected


def test_exe3_document_reuse_degrades_exe4_not_exe3(base_graph):
    """The separation, stated as its own assertion: a Document reused past its purpose
    moves EXE-4 off state 1 and leaves EXE-3 alone."""
    _exe3_document_reuse_only(base_graph)
    sa = score_standards(base_graph, "ep-1", "full-36", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["EXE-3"] == 1 and states["EXE-4"] != 1


def test_exe3_model_use_past_purpose_justifies_with_the_model_id(base_graph):
    _exe3_model_use_past_purpose(base_graph)
    sa = score_standards(base_graph, "ep-1", "full-36", k=1, now=NOW)
    rating = next(r for r in sa["ratings"] if r["questionId"] == "EXE-3")
    assert rating["justification"] == ["mdl-1"]
    assert rating["rule"].startswith("findings_present")


def test_exe3_ms_study_reuse_justifies_with_the_study_and_the_claim(base_graph):
    _exe3_ms_study_reuse(base_graph)
    sa = score_standards(base_graph, "ep-1", "full-36", k=1, now=NOW)
    rating = next(r for r in sa["ratings"] if r["questionId"] == "EXE-3")
    assert rating["justification"] == ["cl-1", "ev-ms"]


# ---- EXE-8 fidelity ladder -----------------------------------------------------------

def _exe8_all_content(g):
    put_all(g, _vva("vva-1", [{"name": "A", "content": "real content"},
                               {"name": "B", "content": "more content"}], document="ev-doc"),
            model("mdl-1", vva="vva-1"),
            {**episode(), "rev": 2, "models": ["mdl-1"]})


def _exe8_all_exclusion(g):
    put_all(g,
            obj("ex-1", "Exclusion", target={"kind": "Study", "label": "x"},
                reasonType="data-unavailable", reason="not available",
                authority={"who": "w", "role": "r", "date": "2023"},
                retainedInStructure=True),
            _vva("vva-1", [{"name": "A", "content": {"$exclusion": "ex-1"}}], document="ev-doc"),
            model("mdl-1", vva="vva-1"),
            {**episode(), "rev": 2, "models": ["mdl-1"]})


def _exe8_mixed_gap_content(g):
    put_all(g,
            gap("gap-1", impact="informational"),
            _vva("vva-1", [{"name": "A", "content": "real content"},
                           {"name": "B", "content": {"$gap": "gap-1"}}], document="ev-doc"),
            model("mdl-1", vva="vva-1"),
            {**episode(), "rev": 2, "models": ["mdl-1"]})


def _exe8_empty(g):
    pass  # no models at all


@pytest.mark.parametrize(("build", "expected"), [
    (_exe8_all_content, 1),
    (_exe8_all_exclusion, 2),
    (_exe8_mixed_gap_content, 3),
    (_exe8_empty, 4),
], ids=["all-content", "all-exclusion", "mixed-gap-content", "empty"])
def test_exe8_fidelity_ladder(base_graph, build, expected):
    build(base_graph)
    sa = score_standards(base_graph, "ep-1", "published-21", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["EXE-8"] == expected


# ---- EXE-14 fidelity ladder ----------------------------------------------------------

def _exe14_document_signed(g):
    put_all(g, _vva("vva-1", [{"name": "A", "content": "x"}], document="ev-doc"),
            model("mdl-1", vva="vva-1"),
            {**episode(), "rev": 2, "models": ["mdl-1"]})


def _exe14_interview_basis(g):
    put_all(g, _vva("vva-1", [{"name": "A", "content": "x"}], basis="interview"),
            model("mdl-1", vva="vva-1"),
            {**episode(), "rev": 2, "models": ["mdl-1"]})


def _exe14_document_no_ref(g):
    put_all(g, _vva("vva-1", [{"name": "A", "content": "x"}]),  # basis document, no document ref
            model("mdl-1", vva="vva-1"),
            {**episode(), "rev": 2, "models": ["mdl-1"]})


def _exe14_no_models(g):
    pass  # no models -> no accreditation at all


@pytest.mark.parametrize(("build", "expected"), [
    (_exe14_document_signed, 1),
    (_exe14_interview_basis, 3),
    (_exe14_document_no_ref, 3),
    (_exe14_no_models, 4),
], ids=["document-signed", "interview-basis", "document-no-ref", "no-models"])
def test_exe14_fidelity_ladder(base_graph, build, expected):
    build(base_graph)
    # EXE-14 is outside the published-21 subset; score against the full 36 to reach it.
    sa = score_standards(base_graph, "ep-1", "full-36", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["EXE-14"] == expected


# ---- DES-14: a performed BiasCheck, not just listed assumptions ----------------------

def _des14_performed_check_no_risks(g):
    put_all(g,
            obj("as-1", "Assumption", statement="s", linchpin=False, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            bias_check("bc-1", "premortem", status="performed"),
            {**episode(), "rev": 2, "assumptions": ["as-1"], "biasChecks": ["bc-1"]})


def _des14_no_performed_check(g):
    put_all(g,
            obj("as-1", "Assumption", statement="s", linchpin=False, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            {**episode(), "rev": 2, "assumptions": ["as-1"]})


@pytest.mark.parametrize(("build", "expected"), [
    (_des14_performed_check_no_risks, 1),
    (_des14_no_performed_check, 2),
], ids=["performed-check", "assumptions-only-no-performed-check"])
def test_des14_requires_a_performed_bias_check(base_graph, build, expected):
    build(base_graph)
    # DES-14 is outside the published-21 subset; score against the full 36 to reach it.
    sa = score_standards(base_graph, "ep-1", "full-36", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["DES-14"] == expected


# ---- episode scoping of findings ------------------------------------------------------

def test_findings_on_another_episode_do_not_leak_into_this_episodes_pre_band(
    two_alt_graph,  # noqa: F811
):
    """`rule_silence` and the policy rules run over the whole store, not one episode at a
    time. An empty-content charter belonging to an unrelated second episode (its own
    policy, so no policy-rule cross-talk either) must not change ep-1's PRE-2 or PRE-3
    once build_context scopes findings to what ep-1 can actually reach."""
    g = two_alt_graph
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    ep = g.get("ep-1")  # evaluate() re-wrote ep-1 as KERNEL_ACTOR; this edit is human.
    put_all(g, claim("cl-1", ["ev-doc"], derivedFrom=run["id"]))
    put_all(g, {**ep, "createdBy": H, "rev": ep["rev"] + 1, "claims": ["cl-1"]})

    sa_before = score_standards(g, "ep-1", "published-21", k=1, now=NOW)
    before = {r["questionId"]: r["state"] for r in sa_before["ratings"]}

    put_all(g, policy("pol-2"),
            charter("ch-2", question="", decisionClassPolicy="pol-2"),
            episode("ep-2", charter="ch-2"))
    ctx = build_context(g, "ep-1")
    assert any(f.rule == "silence" and "ch-2" in f.objects for f in ctx.findings)

    sa_after = score_standards(g, "ep-1", "published-21", k=1,
                                now="2026-09-04T00:00:01Z")
    after = {r["questionId"]: r["state"] for r in sa_after["ratings"]}
    assert before["PRE-2"] == after["PRE-2"]
    assert before["PRE-3"] == after["PRE-3"]


# ---- PRE-4: the record can fail it ---------------------------------------------------


def _run_and_claim(g, *, result_ref=None, with_claim=True):
    """Evaluate `pl-1` on the two-alternative graph, then (optionally) add a human Claim
    that states one of the run's own numbers."""
    run = evaluate(g, "pl-1", seed=1, now=NOW)[0]
    if with_claim:
        ref = run["outputs"][0] if result_ref is None else result_ref
        ep = g.get("ep-1")
        put_all(g, claim("cl-1", ["ev-doc"], derivedFrom=run["id"], resultRef=ref))
        put_all(g, {**ep, "createdBy": H, "rev": ep["rev"] + 1, "claims": ["cl-1"]})
    return run


def test_pre4_runs_with_no_claims_is_state_2_not_1(two_alt_graph):  # noqa: F811
    """A run whose numbers no Claim ever states is not "results presented clearly" — the
    kernel wrote the units itself, so state 1 there would be the scorer grading its own
    output."""
    g = two_alt_graph
    _run_and_claim(g, with_claim=False)
    sa = score_standards(g, "ep-1", "full-36", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["PRE-4"] == 2


def test_pre4_claim_derived_from_a_run_with_a_matching_result_ref_is_state_1(
    two_alt_graph,  # noqa: F811
):
    g = two_alt_graph
    run = _run_and_claim(g)
    sa = score_standards(g, "ep-1", "full-36", k=1, now=NOW)
    rating = next(r for r in sa["ratings"] if r["questionId"] == "PRE-4")
    assert rating["state"] == 1
    assert rating["justification"] == sorted({"cl-1", run["id"]})


def test_pre4_result_ref_belonging_to_another_run_is_not_state_1(two_alt_graph):  # noqa: F811
    """A Claim that cites a Result the run it names never produced is a broken trace, not
    a clear presentation."""
    g = two_alt_graph
    old_step = g.get("pl-1")["steps"][0]
    put_all(g, {**g.get("pl-1"), "rev": 2, "steps": [old_step, {**old_step, "id": "s2"}]})
    runs = evaluate(g, "pl-1", seed=1, now=NOW)
    ep = g.get("ep-1")
    put_all(g, claim("cl-1", ["ev-doc"], derivedFrom=runs[0]["id"],
                     resultRef=runs[1]["outputs"][0]))
    put_all(g, {**ep, "createdBy": H, "rev": ep["rev"] + 1, "claims": ["cl-1"]})
    sa = score_standards(g, "ep-1", "full-36", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["PRE-4"] != 1


def test_pre4_fails_when_a_per_measure_result_loses_its_raw_units(two_alt_graph):  # noqa: F811
    """The half of the bar the record can break without touching a Claim: a per-measure
    Result stripped of the unit its raw value was measured in."""
    g = two_alt_graph
    run = _run_and_claim(g)
    per_measure = next(i for i in run["outputs"] if not g.get(i)["aggregate"])
    stripped = {k: v for k, v in g.get(per_measure).items() if k != "rawUnits"}
    g._latest[per_measure] = stripped
    g._history[per_measure][stripped["rev"]] = stripped
    sa = score_standards(g, "ep-1", "full-36", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["PRE-4"] != 1


# ---- the complete episode, and the degradations that move exactly one question -------


def _states(g, tailoring="full-36"):
    sa = score_standards(g, "ep-1", tailoring, k=1, now=COMPLETE_NOW)
    return {r["questionId"]: r["state"] for r in sa["ratings"]}


def _mark(g, gid="gap-x"):
    """A recorded gap, which is how this record empties a slot: silence would be a
    finding of its own and would confound the degradation under test."""
    if not g.has(gid):
        put_all(g, gap(gid, impact="informational"))
    return {"$gap": gid}


def test_complete_episode_scores_state_1_on_every_question(complete_episode):
    """One whole, well-formed record — charter through commitment — scores "no concerns"
    on all 36 questions. This is the fixture the degraded variants below are cut from: if
    a predicate could not be satisfied by a real record, that would be a defect in the
    predicate, not a stricter standard."""
    g = complete_episode
    sa = score_standards(g, "ep-1", "full-36", k=1, now=COMPLETE_NOW)
    off = {r["questionId"]: (r["state"], r["rule"]) for r in sa["ratings"] if r["state"] != 1}
    assert off == {}
    assert len(sa["ratings"]) == 36
    for r in sa["ratings"]:
        for i in r["justification"]:
            assert g.has(i), (r["questionId"], i)
    assert {d: v["verdict"] for d, v in sa["dimensionVerdicts"].items()} == {
        "objectivity": "generally_objective", "validity": "generally_valid",
        "reliability": "generally_reliable"}


def test_complete_episode_has_no_findings_at_all(complete_episode):
    assert validate(complete_episode, complete_episode.get("pol-1")) == []
    assert check_scope(complete_episode, "ep-1") == []


# Each entry: a single edit to the complete record, and every rating state it moves.
# The right-hand side is exhaustive — a degradation that quietly moved a second question
# would fail here, which is the point of scoring the whole 36 rather than one id.
DEGRADATIONS: dict[str, tuple] = {}


def _degradation(*, moves):
    def deco(fn):
        DEGRADATIONS[fn.__name__] = (fn, moves)
        return fn
    return deco


@_degradation(moves={"PRE-5": 4})
def _no_commitment(g):
    revise(g, "ep-1", drop=("commitment",))


@_degradation(moves={"PRE-5": 3})
def _commitment_off_the_ranking(g):
    revise(g, "cm-1", selected="alt-b")


@_degradation(moves={"EXE-11": 4, "EXE-12": 4, "PRE-3": 2, "PRE-6": 2})
def _no_baseline(g):
    revise(g, "alt-base", baselineFlag=False)


# PRE-3 moves too: the policy requires every linchpin varied, so the un-varied one is a
# blocking `linchpin-not-varied` finding, and `conclusions_sound` fails on any blocker.
@_degradation(moves={"DES-6": 2, "PRE-3": 2})
def _a_linchpin_nobody_varied(g):
    put_all(g, obj("as-3", "Assumption", statement="The threat set is stable.",
                   linchpin=True, rationale="Stated in the threat analysis.",
                   evidence="ev-doc", implicationsIfWrong="The ranking could reverse.",
                   indicatorsThatWouldAlter=["a revised threat analysis"],
                   variedInSensitivity=False))
    revise(g, "ep-1", assumptions=["as-1", "as-2", "as-3"])


@_degradation(moves={"DES-6": 2})
def _no_linchpins_but_something_varied(g):
    revise(g, "as-1", linchpin=False)
    revise(g, "as-2", linchpin=False)


@_degradation(moves={"PRE-3": 2})
def _an_evidence_item_back_to_draft(g):
    """Unreviewed evidence is not assessable at the claim's level, which is a blocking
    scope finding — so it lands on PRE-3 ("are the conclusions sound?"), not on PRE-1 or
    PRE-2, neither of which reads review status."""
    revise(g, "ev-doc", reviewStatus="draft")


@_degradation(moves={"DES-14": 2})
def _an_open_bias_risk(g):
    revise(g, "rk-1", status="open")


@_degradation(moves={"DES-1": 3})
def _charter_states_only_the_question(g):
    m = _mark(g)
    revise(g, "ch-1", decisionToBeMade=m, consequencesOfErroneousOutput=m)


@_degradation(moves={"DES-2": 2, "DES-3": 2})
def _a_scope_term_left_undefined(g):
    revise(g, "ch-1", definitions=[{"term": "configuration", "text": _mark(g)}])


@_degradation(moves={"DES-7": 2})
def _a_constraint_listed_but_not_discussed(g):
    revise(g, "con-1", implications=_mark(g))


@_degradation(moves={"DES-8": 2, "DES-9": 2})
def _scenarios_without_rationale_or_coverage(g):
    revise(g, "scn-desert", rationale=_mark(g))
    revise(g, "scn-urban", conditions=["desert"])


@_degradation(moves={"DES-10": 3, "EXE-9": 3, "EXE-11": 2, "PRE-1": 2, "PRE-3": 2,
                     "PRE-4": 2, "PRE-5": 3})
def _the_plan_was_never_run(g):
    """PRE-3 lands at 2, not 4 (pre-R2 expectation): the episode's `runs` list is empty,
    so conclusions_sound/runs_exist are false, but the record's claims (cl-1, cl-2,
    cl-bias) are untouched and no `silence` finding is raised — R2's
    `claims_exist_no_silence` clause.
    See docs/decisions/2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md.
    Review note (M2): `cl-1` still carries `derivedFrom`/`resultRef` naming the run this
    edit un-lists from the episode (`conftest.py`'s `complete_graph`), so the record R2
    now scores "narrative-only" is in fact internally inconsistent, not narrative-free.
    That inconsistency predates R2 — PRE-1 already scored this fixture 2 via
    `claims_all_supported` before this task — so PRE-3's move to 2 is an accurate ripple
    of an existing fixture property, not evidence that a dangling `derivedFrom` is
    benign."""
    revise(g, "ep-1", runs=[])


@_degradation(moves={"PRE-1": 2, "PRE-3": 3, "PRE-4": 2})
def _no_claim_derived_from_the_run(g):
    revise(g, "cl-1", drop=("derivedFrom", "resultRef"))


@_degradation(moves={"DES-11": 3})
def _the_plan_says_nothing_about_deviations(g):
    """DES-11 must not answer "no concerns" from an absent field. An explicit empty
    `deviations` list is the human saying "followed as written"; dropping the field
    leaves the question unanswered."""
    revise(g, "pl-1", drop=("deviations",))


@_degradation(moves={"DES-12": 2})
def _a_mandate_element_only_partly_met(g):
    revise(g, "me-1", status="partial", drop=("satisfiedBy",))


@_degradation(moves={"DES-13": 2})
def _a_limitation_with_no_mitigation(g):
    revise(g, "ch-1", limitations=[{"statement": "Urban results are modelled.",
                                    "mitigation": _mark(g)}])


@_degradation(moves={"EXE-2": 2})
def _a_primary_objective_no_claim_addresses(g):
    put_all(g, objective("obj-2", measures=["m-1"], name="Sustain the fleet",
                          provenance="ev-doc"))
    revise(g, "ep-1", objectives=["obj-1", "obj-2"])


@_degradation(moves={"EXE-4": 2, "PRE-3": 2})
def _evidence_with_no_scope_of_validity(g):
    revise(g, "ev-doc", scopeOfValidity=_mark(g))


@_degradation(moves={"EXE-5": 2})
def _evidence_with_no_reliability_steps(g):
    revise(g, "ev-doc", reliabilitySteps=_mark(g))


@_degradation(moves={"EXE-6": 2})
def _evidence_with_no_stated_limitations(g):
    revise(g, "ev-doc", drop=("limitations",))


@_degradation(moves={"EXE-7": 2})
def _a_model_limitation_left_unjustified(g):
    revise(g, "mdl-1", limitations=[{"statement": "No interaction terms.",
                                     "justification": _mark(g)}])


@_degradation(moves={"EXE-8": 2})
def _a_vva_section_retained_as_an_exclusion(g):
    put_all(g, obj("ex-sec", "Exclusion", target={"kind": "Section", "label": "Validation"},
                    reasonType="not-applicable", reason="the model has no field data to "
                                                        "validate against",
                    authority={"who": "chief engineer", "role": "accreditor",
                               "date": "2026-01-15"},
                    retainedInStructure=True))
    revise(g, "vva-1", sections=[{"name": "Validation",
                                  "content": {"$exclusion": "ex-sec"}}])


@_degradation(moves={"EXE-8": 3})
def _a_vva_section_left_as_a_gap(g):
    revise(g, "vva-1", sections=[{"name": "Verification", "content": "hand-checked"},
                                 {"name": "Validation", "content": _mark(g)}])


@_degradation(moves={"EXE-10": 2})
def _an_observation_with_no_evidence(g):
    revise(g, "ob-b-m1", evidence=_mark(g))


@_degradation(moves={"EXE-14": 3})
def _accreditation_asserted_in_an_interview(g):
    acc = {k: v for k, v in g.get("vva-1")["accreditationDecision"].items() if k != "document"}
    revise(g, "vva-1", accreditationDecision={**acc, "basis": "interview"})


@_degradation(moves={"EXE-15": 2})
def _a_measure_with_no_criteria(g):
    revise(g, "m-1", criteria=_mark(g))


@_degradation(moves={"EXE-3": 3})
def _a_model_used_outside_its_question_class(g):
    revise(g, "mdl-1", questionClass="cost")


@_degradation(moves={"EXE-3": 3, "EXE-4": 2, "PRE-3": 2})
def _a_prior_ms_study_reused_without_justification(g):
    ev = _ms_study("ev-ms", title="Prior M&S study", model="mdl-1",
                   scenarios=["scn-desert"], vvaRecord="vva-1",
                   pointer={"uri": "file://studies/prior.pdf", "custodian": "study centre"},
                   classification={"level": "U", "metadataLevel": "U"},
                   reviewStatus="reviewed", reliabilitySteps=["drs-1"],
                   inclusionReason="It is the only prior study of this configuration.",
                   limitations=[{"statement": "Older threat set.",
                                 "impact": "Capability scores may be optimistic."}],
                   scopeOfValidity={"builtToAnswer": "a force-structure question",
                                    "questionClass": "force-structure",
                                    "conditions": ["desert"], "intendedUse": "u"})
    put_all(g, ev, claim("cl-ms", ["ev-ms"], text="The prior study supports A.",
                          questionClass="other"))
    ep = g.get("ep-1")
    revise(g, "ep-1", claims=ep["claims"] + ["cl-ms"],
           evidenceRegister=ep["evidenceRegister"] + ["ev-ms"])


@_degradation(moves={"DES-5": 2, "PRE-3": 2})
def _an_assumption_with_no_evidence(g):
    revise(g, "as-1", evidence=_mark(g))


@_degradation(moves={"DES-5": 2, "PRE-2": 2, "PRE-3": 2})
def _a_blocking_gap_the_episode_reaches(g):
    put_all(g, gap("gap-block", impact="blocking"))
    revise(g, "as-1", evidence={"$gap": "gap-block"})


@pytest.mark.parametrize("name", sorted(DEGRADATIONS), ids=sorted(DEGRADATIONS))
def test_one_degradation_moves_exactly_the_expected_questions(name):
    build, moves = DEGRADATIONS[name]
    before = _states(complete_graph())
    g = complete_graph()
    build(g)
    after = _states(g)
    assert {q: after[q] for q in after if after[q] != before[q]} == moves


def test_predicate_positive_coverage():
    """Every predicate the scoring rules name must return True at least once across the
    complete record and its degraded variants. A predicate whose positive branch is never
    exercised is an untested claim about what "no concerns" means."""
    wanted = {c["when"] for r in load_rules() for c in r["clauses"]} - {"always"}
    fired: set[str] = set()
    original = dict(PREDICATES)

    def wrap(name, fn):
        def inner(g, ep, ctx):
            ok, ids = fn(g, ep, ctx)
            if ok:
                fired.add(name)
            return ok, ids
        return inner

    try:
        for n, f in original.items():
            PREDICATES[n] = wrap(n, f)
        _states(complete_graph())
        for build, _moves in DEGRADATIONS.values():
            g = complete_graph()
            build(g)
            _states(g)
    finally:
        PREDICATES.clear()
        PREDICATES.update(original)

    assert wanted <= fired, f"never returned True: {sorted(wanted - fired)}"


# ---- item 9: store-integrity findings, over-credit, and pinned justifications --------


def test_a_tampered_log_on_an_unrelated_object_still_blocks_pre3(complete_episode):
    """Store integrity is store-wide. The episode-reach filter keeps *another episode's*
    problems out of this one's ratings, but a broken audit chain is not another episode's
    problem — it invalidates every reading of the store, so "are the conclusions sound?"
    must not stay at "no concerns" over a log that is provably tampered with."""
    g = complete_episode
    assert _states(g)["PRE-3"] == 1
    put_all(g, obj("r-far", "Rationale", text="unrelated to this episode", author="someone"))
    assert "r-far" not in g.reachable_from("ep-1", reverse=False)

    g._log[-1]["prevHash"] = "0" * 64  # a hand-edited store is the case this guards
    findings = validate(g)
    assert any(f.rule == "log-chain" and f.objects == ("r-far",) for f in findings)
    assert _states(g)["PRE-3"] == 2


def test_findings_present_is_scoped_to_the_episode_but_not_for_store_integrity(
    complete_episode,
):
    """The generic YAML hook takes the same scoping as every other findings-reading
    predicate — with the same store-integrity exemption."""
    g = complete_episode
    ep = g.get("ep-1")
    ctx = build_context(g, "ep-1")
    elsewhere = Finding("ReusePastPurpose", "blocking", ("r-elsewhere",), "another episode")
    ctx.findings = ctx.findings + [elsewhere]
    ctx.args = {"rule": "ReusePastPurpose"}
    assert PREDICATES["findings_present"](g, ep, ctx)[0] is False

    ctx.findings = ctx.findings + [Finding("log-chain", "blocking", ("r-elsewhere",), "broken")]
    ctx.args = {"rule": "log-chain"}
    assert PREDICATES["findings_present"](g, ep, ctx)[0] is True


def test_a_second_episodes_reuse_finding_does_not_move_this_episodes_exe3(complete_episode):
    g = complete_episode
    before = _states(g)
    put_all(
        g,
        policy("pol-2", requiredBiasChecks=[]),
        charter("ch-2", decisionClassPolicy="pol-2"),
        evidence("ev-far", scopeOfValidity={"builtToAnswer": "q", "intendedUse": "u",
                                             "questionClass": "force-structure"}),
        claim("cl-far", ["ev-far"]),
        episode("ep-2", charter="ch-2", claims=["cl-far"], evidenceRegister=["ev-far"]),
    )
    assert any(f.rule == "ReusePastPurpose" for f in check_scope(g, "ep-2"))
    assert _states(g)["EXE-3"] == before["EXE-3"] == 1


def test_one_resolvable_assumption_plus_one_dangling_id_is_not_state_1(base_graph):
    """The over-credit half of `_all`: a listed assumption the store cannot find cannot
    be judged "all" anything, so DES-4 must not read state 1 off the one that resolves."""
    g = base_graph
    put_all(g,
            obj("as-1", "Assumption", statement="s", linchpin=False, rationale="stated",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            {**episode(), "rev": 2, "assumptions": ["as-1", "as-missing"]})
    sa = score_standards(g, "ep-1", "published-21", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["DES-4"] != 1


def test_des6_state_1_names_both_the_flips_and_the_linchpins(complete_episode):
    g = complete_episode
    flip_ids = sorted(f["id"] for f in g.all("FlipAnalysis") if f.get("assumption"))
    assert len(flip_ids) == 2
    ok, ids = PREDICATES["all_linchpins_have_flip"](g, g.get("ep-1"), build_context(g, "ep-1"))
    assert ok and ids == flip_ids + ["as-1", "as-2"]
    sa = score_standards(g, "ep-1", "full-36", k=1, now=COMPLETE_NOW)
    rating = next(r for r in sa["ratings"] if r["questionId"] == "DES-6")
    assert rating["state"] == 1
    assert rating["justification"] == sorted(flip_ids + ["as-1", "as-2"])


def test_pre4_state_1_names_the_claim_and_the_run(complete_episode):
    g = complete_episode
    sa = score_standards(g, "ep-1", "full-36", k=1, now=COMPLETE_NOW)
    rating = next(r for r in sa["ratings"] if r["questionId"] == "PRE-4")
    assert rating["state"] == 1
    assert rating["justification"] == ["cl-1", "run-pl-1-s1"]


# ---- item 8 minors -------------------------------------------------------------------


def test_dimension_verdicts_treats_a_non_int_state_as_insufficient():
    """An applicable rating whose state is missing or not an integer is the
    "insufficient information" case, not "no concerns" — `dimension_verdicts` is called
    directly with hand-built rating lists, so it cannot assume score_standards' shape."""
    for bad in (None, "1", True):
        dv = dimension_verdicts([{"questionId": "DES-2", "applicable": True, "state": bad}],
                                 k=1)
        assert dv["objectivity"]["verdict"] == "insufficient_to_conclude", bad
        assert dv["objectivity"]["states"] == [4]
    dv = dimension_verdicts([{"questionId": "DES-2", "applicable": True}], k=1)
    assert dv["objectivity"]["verdict"] == "insufficient_to_conclude"


def test_score_standards_counter_tolerates_an_assessment_without_an_episode(base_graph):
    """The id counter reads a field off every StandardsAssessment in the store; a
    hand-edited one missing `episode` must not KeyError out of a module whose whole
    docstring promises tolerance."""
    g = base_graph
    sa1 = score_standards(g, "ep-1", "published-21", k=1, now=NOW)
    stripped = {k: v for k, v in g.get(sa1["id"]).items() if k != "episode"}
    g._latest[sa1["id"]] = stripped
    g._history[sa1["id"]][stripped["rev"]] = stripped
    sa2 = score_standards(g, "ep-1", "full-36", k=1, now="2026-09-04T00:00:01Z")
    assert sa2["id"] == "sa-ep-1-full-36-1"  # the stripped one no longer counts


# ---- PRE-3/PRE-4: narrative-only records (R2, 2026-09-05) ----------------------------
# docs/decisions/2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md


def test_narrative_only_record_scores_two_not_four_on_pre3_and_pre4(base_graph):
    """R2: a reconstruction that presents a claim supported by cited, reviewed evidence
    (base_graph's ev-doc, which carries reliabilitySteps) but has no evaluation run at
    all scores PRE-3 == PRE-4 == 2 — 'generally, with concerns: not reproducible from
    runs in the record' — never 1 (that still requires conclusions_sound/results_clear,
    which need a run) and never 4 (that would read as 'insufficient information', which
    a record that states its conclusions is not)."""
    g = base_graph
    put_all(g, claim("cl-1", ["ev-doc"]), {**episode(), "rev": 2, "claims": ["cl-1"]})
    sa = score_standards(g, "ep-1", "published-21", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["PRE-3"] == 2
    assert states["PRE-4"] == 2


def test_narrative_only_record_with_silence_drops_pre3_not_pre4(base_graph):
    """A `silence` finding reachable from the episode (here: the episode's own charter
    left with an empty required slot) drops PRE-3 back to 4 (its new clause reads
    `claims_exist_no_silence`) while leaving PRE-4 at 2. Review note (I2): in *this*
    fixture PRE-4's 2 is still earned by the pre-existing `claims_all_supported→2`
    clause, not the new `claims_exist` one — `ev-doc`'s `reliabilitySteps` are untouched,
    so `claims_all_supported` is still true and fires first. The combination where the
    new `claims_exist` clause is what fires *under silence* is
    `test_narrative_only_record_with_silence_and_gapped_reliability_steps_is_insufficient_everywhere`
    below."""
    g = base_graph
    put_all(g, claim("cl-1", ["ev-doc"]), {**episode(), "rev": 2, "claims": ["cl-1"]})
    revise(g, "ch-1", consequencesOfErroneousOutput="")
    ctx = build_context(g, "ep-1")
    assert any(f.rule == "silence" and "ch-1" in f.objects for f in ctx.findings)
    sa = score_standards(g, "ep-1", "published-21", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    rules = {r["questionId"]: r["rule"] for r in sa["ratings"]}
    assert states["PRE-3"] == 4
    assert states["PRE-4"] == 2
    assert rules["PRE-4"] == "claims_all_supported→2"


def test_pre4_claims_exist_is_load_bearing_when_reliability_steps_are_gapped(base_graph):
    """The situation R2's DECISION NEEDED 2 was actually about: a claim cites evidence
    whose reliabilitySteps is a recorded gap, not content (Demo B's F8 shape), so
    `claims_all_supported` is false and PRE-4's only remaining path to state 2 is the new
    `claims_exist` clause, not the pre-existing `claims_all_supported` one."""
    g = base_graph
    put_all(
        g,
        gap("gap-rs", impact="informational"),
        evidence("ev-narrative", reliabilitySteps={"$gap": "gap-rs"}),
        claim("cl-1", ["ev-narrative"]),
        {**episode(), "rev": 2, "claims": ["cl-1"]},
    )
    ctx = build_context(g, "ep-1")
    assert PREDICATES["claims_all_supported"](g, g.get("ep-1"), ctx)[0] is False
    sa = score_standards(g, "ep-1", "published-21", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    rules = {r["questionId"]: r["rule"] for r in sa["ratings"]}
    assert states["PRE-4"] == 2
    assert rules["PRE-4"] == "claims_exist→2"


def test_narrative_only_record_with_silence_and_gapped_reliability_steps_is_insufficient_everywhere(
    base_graph,
):
    """Review (I2), the fourth cell of the {silence, gapped reliabilitySteps} grid: a
    record that both raises a `silence` finding *and* cites evidence whose
    `reliabilitySteps` is a recorded gap. Before this task's diff this was PRE-3 = 4,
    PRE-4 = 4 (no path to state 2 at all). After it, PRE-4 = 2 via the new `claims_exist`
    clause specifically — this is the one fixture where that clause is load-bearing
    *and* the record is otherwise as thin as a record with claims can be. PRE-3 stays at
    4 (silence blocks its clause), and because PRE-3 is mapped to all three dimensions,
    every dimension verdict still reads `insufficient_to_conclude` regardless of PRE-4's
    2 — the new clause cannot manufacture a passing verdict here."""
    g = base_graph
    put_all(
        g,
        gap("gap-rs", impact="informational"),
        evidence("ev-narrative", reliabilitySteps={"$gap": "gap-rs"}),
        claim("cl-1", ["ev-narrative"]),
        {**episode(), "rev": 2, "claims": ["cl-1"]},
    )
    revise(g, "ch-1", consequencesOfErroneousOutput="")
    ctx = build_context(g, "ep-1")
    assert any(f.rule == "silence" and "ch-1" in f.objects for f in ctx.findings)
    assert PREDICATES["claims_all_supported"](g, g.get("ep-1"), ctx)[0] is False
    sa = score_standards(g, "ep-1", "published-21", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    rules = {r["questionId"]: r["rule"] for r in sa["ratings"]}
    assert states["PRE-3"] == 4
    assert states["PRE-4"] == 2
    assert rules["PRE-4"] == "claims_exist→2"
    dv = dimension_verdicts(sa["ratings"], k=1)
    assert {d: v["verdict"] for d, v in dv.items()} == {
        "objectivity": "insufficient_to_conclude",
        "validity": "insufficient_to_conclude",
        "reliability": "insufficient_to_conclude",
    }


def test_r2_leaves_a_record_with_no_claims_at_four(base_graph):
    """The GAO-21-460 case (per Figure 6, all four presentation questions are 'unable to
    assess' because the study's final report did not exist yet): no claims at all means
    `claims_exist` and `claims_exist_no_silence` are both false, so R2 cannot move this
    record and every presentation question stays at 4."""
    sa = score_standards(base_graph, "ep-1", "published-21", k=1, now=NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert [states[q] for q in ("PRE-1", "PRE-2", "PRE-3", "PRE-4")] == [4, 4, 4, 4]


def test_r2_does_not_soften_a_record_that_has_runs(complete_episode):
    """A complete record still reaches state 1 on PRE-3/PRE-4 through the run-based
    clauses (`conclusions_sound`, `results_clear`), which sit before the new
    narrative-only clauses in the ladder and fire first; the new clauses are unreachable
    here."""
    g = complete_episode
    sa = score_standards(g, "ep-1", "full-36", k=1, now=COMPLETE_NOW)
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["PRE-3"] == 1
    assert states["PRE-4"] == 1


# ---- kernel hygiene: reason-aware qualifier -------------------------------------------


def test_every_state_two_predicate_has_a_reason():
    """`dimension_verdicts`'s qualifier looks up a state-2 rating's fired predicate in
    `STATE2_REASONS`; a predicate rules.yaml can fire at a `state: 2` clause but this
    mapping has no entry for would silently fall back to the default phrase. Derive the
    full set of state-2 predicates straight from the YAML — the source of truth for what
    can actually fire — so a new state-2 clause that forgets a reason fails here, not in
    a rendered report."""
    state2_predicates = {
        clause["when"]
        for rule in load_rules()
        for clause in rule["clauses"]
        if clause.get("state") == 2
    }
    assert state2_predicates  # the set itself must not be accidentally empty
    missing = state2_predicates - STATE2_REASONS.keys()
    assert not missing, f"STATE2_REASONS is missing an entry for: {sorted(missing)}"


def test_dimension_verdicts_qualifier_names_the_fired_rules_reason():
    """The qualifier for a single state-2 question names that question's id and the
    reason phrase for the predicate that actually fired — not a generic 'does not
    thoroughly describe' — and the format is exactly 'generally X, with concerns: Q
    (reason)', byte-stable."""
    ratings = [{"questionId": q, "applicable": True, "state": 1, "rule": "always→1"}
               for q in ["DES-2", "DES-4", "DES-7", "EXE-1", "EXE-2", "PRE-3", "PRE-4"]]
    ratings[1] = {**ratings[1], "state": 2, "rule": "assumptions_listed→2"}
    dv = dimension_verdicts(ratings, k=1)
    assert dv["objectivity"]["verdict"] == "generally_objective"
    assert dv["objectivity"]["qualifier"] == (
        "generally objective, with concerns: "
        "DES-4 (assumptions are listed without rationale)"
    )


def test_dimension_verdicts_qualifier_names_every_state2_question_in_order():
    """Two state-2 questions in one dimension both appear, each with its own reason,
    joined by '; ' in the dimension's own question order."""
    ratings = [{"questionId": q, "applicable": True, "state": 1, "rule": "always→1"}
               for q in ["DES-2", "DES-4", "DES-7", "EXE-1", "EXE-2", "PRE-3", "PRE-4"]]
    ratings[5] = {**ratings[5], "state": 2, "rule": "claims_exist_no_silence→2"}
    ratings[6] = {**ratings[6], "state": 2, "rule": "claims_all_supported→2"}
    dv = dimension_verdicts(ratings, k=2)
    assert dv["objectivity"]["qualifier"] == (
        "generally objective, with concerns: "
        "PRE-3 (claims are presented but no evaluation run exists in the record); "
        "PRE-4 (claims are backed by evidence but not tied to a run's sealed results)"
    )


def test_dimension_verdicts_qualifier_falls_back_to_the_default_reason():
    """A hand-built rating list without a `rule` key at all (dimension_verdicts is
    called directly by tests and cannot assume score_standards' shape) still produces a
    qualifier — the default reason, not a KeyError or an empty parenthetical."""
    ratings = [{"questionId": q, "applicable": True, "state": 1}
               for q in ["DES-2", "DES-4", "DES-7", "EXE-1", "EXE-2", "PRE-3", "PRE-4"]]
    ratings[1] = {**ratings[1], "state": 2}
    dv = dimension_verdicts(ratings, k=1)
    assert dv["objectivity"]["qualifier"] == (
        "generally objective, with concerns: "
        "DES-4 (the record does not thoroughly describe this item)"
    )
