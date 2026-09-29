# tests/kernel/test_policy_rules.py
from docket import KERNEL_VERSION
from docket.kernel.policy_rules import _episodes
from docket.kernel.validate import validate
from tests.kernel.conftest import (
    alternative,
    bias_check,
    charter,
    claim,
    episode,
    evidence,
    gap,
    measure,
    model,
    obj,
    objective,
    observation,
    policy,
    put_all,
)


def rules(g, pol_id="pol-1"):
    return {f.rule for f in validate(g, g.get(pol_id))}


def test_baseline_present(base_graph):
    g = base_graph
    put_all(g, alternative("alt-a"), {**episode(), "rev": 2, "alternatives": ["alt-a"]})
    assert "baseline-present" in rules(g)
    put_all(g, alternative("alt-b", baseline=True),
            {**episode(), "rev": 3, "alternatives": ["alt-a", "alt-b"]})
    assert "baseline-present" not in rules(g)


def test_linchpin_unevidenced_is_blocking(base_graph):
    g = base_graph
    put_all(g, gap("gap-1", impact="blocking"),
            obj("as-1", "Assumption", statement="s", linchpin=True, rationale="r",
                evidence={"$gap": "gap-1"}, implicationsIfWrong="i",
                indicatorsThatWouldAlter=["x"], variedInSensitivity=False),
            {**episode(), "rev": 2, "assumptions": ["as-1"]})
    f = [x for x in validate(g, g.get("pol-1")) if x.rule == "linchpin-unevidenced"]
    assert f and f[0].severity == "blocking" and f[0].objects == ("as-1",)


def test_silent_omission_and_exclusion_resolves_it(base_graph):
    g = base_graph
    put_all(g, evidence("ev-known"),
            {**episode(), "rev": 2, "evidenceRegister": ["ev-known"]})
    assert "silent-omission" in rules(g)
    put_all(g, obj("ex-1", "Exclusion",
                   target={"kind": "Evidence", "id": "ev-known", "label": "known"},
                   reasonType="security-withheld", reason="r",
                   authority={"who": "w", "role": "r", "date": "2023"},
                   retainedInStructure=True))
    assert "silent-omission" not in rules(g)


def test_prohibited_exclusion_reason_label_only_and_measure_target(base_graph):
    g = base_graph
    # Label-only target — no id at all. Cannot be attributed to any one episode, so it is
    # in scope for every policy (fail-safe).
    put_all(g, obj("ex-1", "Exclusion", target={"kind": "Study", "label": "x"},
                   reasonType="time-or-resource", reason="no time",
                   authority={"who": "w", "role": "r", "date": "2023"},
                   retainedInStructure=True))
    # Measure-target — reachable only via Objective -> Measure, not evidenceRegister or
    # alternatives directly, so this exercises the general scope_ids reachability path.
    put_all(g, objective("obj-1", measures=["m-1"]), measure("m-1", "obj-1"),
            {**episode(), "rev": 2, "objectives": ["obj-1"]},
            obj("ex-2", "Exclusion", target={"kind": "Measure", "id": "m-1", "label": "m"},
                reasonType="time-or-resource", reason="no time",
                authority={"who": "w", "role": "r", "date": "2023"},
                retainedInStructure=True))
    findings = [x for x in validate(g, g.get("pol-1")) if x.rule == "exclusion-prohibited-reason"]
    flagged = {x.objects[0] for x in findings}
    assert {"ex-1", "ex-2"} <= flagged


def test_value_conflict_across_and_within_evidence(base_graph):
    g = base_graph
    a = evidence("ev-a", assertions=[
        {"subject": "omfv-mta-total", "field": "costM", "value": 1348, "locator": "p.141"},
        {"subject": "omfv-mta-total", "field": "costM", "value": 1384, "locator": "p.310"},
    ])
    b = evidence("ev-b", assertions=[
        {"subject": "omfv-mta-total", "field": "costM", "value": 1330, "locator": "p.215"},
    ])
    put_all(g, a, b, {**episode(), "rev": 2, "evidenceRegister": ["ev-a", "ev-b"]})
    r = rules(g)
    assert "value-conflict-internal" in r and "value-conflict" in r


def test_value_conflict_same_document_only_yields_internal_finding_only(base_graph):
    g = base_graph
    a = evidence("ev-a", assertions=[
        {"subject": "omfv-mta-total", "field": "costM", "value": 1348, "locator": "p.141"},
        {"subject": "omfv-mta-total", "field": "costM", "value": 1384, "locator": "p.310"},
    ])
    put_all(g, a, {**episode(), "rev": 2, "evidenceRegister": ["ev-a"]})
    r = rules(g)
    assert "value-conflict-internal" in r and "value-conflict" not in r


def test_value_conflict_normalises_numeric_types(base_graph):
    g = base_graph
    a = evidence("ev-a", assertions=[
        {"subject": "omfv-mta-total", "field": "costM", "value": 1348, "locator": "p.141"},
    ])
    b = evidence("ev-b", assertions=[
        {"subject": "omfv-mta-total", "field": "costM", "value": 1348.0, "locator": "p.215"},
    ])
    put_all(g, a, b, {**episode(), "rev": 2, "evidenceRegister": ["ev-a", "ev-b"]})
    r = rules(g)
    assert "value-conflict" not in r and "value-conflict-internal" not in r


def test_gap_unconfirmed_and_definition_missing(base_graph):
    g = base_graph
    put_all(g, gap("gap-u", confirmed=False),
            {**charter(), "rev": 2,
             "definitions": [{"term": "force structure", "text": {"$gap": "gap-u"}}]})
    r = rules(g)
    assert {"gap-unconfirmed", "definition-missing"} <= r


def test_vva_rules(base_graph):
    g = base_graph
    put_all(g,
            obj("vva-1", "VVARecord", problemStatement="ch-1",
                requirementsAndAcceptabilityCriteria="r",
                assumptionsCapabilitiesLimitationsRisks={
                    "assumptions": ["a"], "capabilities": ["c"],
                    "limitations": ["l"], "risks": ["r"],
                },
                methodology="m",
                accreditationDecision={"authority": "PM", "date": "2021-06", "scope": "s",
                                        "basis": "interview"},
                sections=[{"name": "Problem Statement", "content": "x"}]),
            obj("mdl-1", "Model", name="m",
                definition={"kind": "simulation", "version": "1"}, intendedUse="u",
                questionClass="other", vvaRecord="vva-1", qualificationStatus="validated"),
            {**episode(), "rev": 2, "models": ["mdl-1"]})
    assert "vva-verbal" in rules(g) and "model-vva" not in rules(g)


def test_alternative_status_unreasoned(base_graph):
    g = base_graph
    put_all(g, alternative("alt-a", status="screened-out"),
            {**episode(), "rev": 2, "alternatives": ["alt-a"]})
    assert "alternative-status-unreasoned" in rules(g)
    put_all(g, obj("ex-1", "Exclusion",
                   target={"kind": "Alternative", "id": "alt-a", "label": "alt-a"},
                   reasonType="dominated", reason="r",
                   authority={"who": "w", "role": "r", "date": "2023"},
                   retainedInStructure=True))
    put_all(g, {**alternative("alt-a", status="screened-out"), "rev": 2,
                "statusReason": "ex-1"})
    assert "alternative-status-unreasoned" not in rules(g)


def test_objective_measured(base_graph):
    g = base_graph
    put_all(g, objective("obj-1"), {**episode(), "rev": 2, "objectives": ["obj-1"]})
    assert "objective-measured" in rules(g)
    put_all(g, measure("m-1", "obj-1"), {**objective("obj-1"), "rev": 2, "measures": ["m-1"]})
    assert "objective-measured" not in rules(g)


def test_bias_check_missing(base_graph):
    g = base_graph
    put_all(g, {**policy(), "rev": 2, "requiredBiasChecks": ["premortem"]})
    assert "bias-check-missing" in rules(g)
    put_all(g, bias_check("bc-1", "premortem"),
            {**episode(), "rev": 2, "biasChecks": ["bc-1"]})
    assert "bias-check-missing" not in rules(g)


def test_bias_check_evidence_gap_is_a_warning_not_missing(base_graph):
    g = base_graph
    put_all(g, {**policy(), "rev": 2, "requiredBiasChecks": ["premortem"]})
    put_all(g, gap("gap-bc"),
            bias_check("bc-2", "premortem", producedEvidence={"$gap": "gap-bc"}),
            {**episode(), "rev": 2, "biasChecks": ["bc-2"]})
    r = rules(g)
    assert "bias-check-evidence-gap" in r and "bias-check-missing" not in r


def test_lexicon_mixed_per_episode(base_graph):
    g = base_graph
    put_all(g,
            obj("u-a", "Uncertainty", kind="interval", spec={}, lexicon="A"),
            obj("u-b", "Uncertainty", kind="interval", spec={}, lexicon="B"),
            obj("risk-a", "Risk", statement="s", kind="other", consequence="c", owner="o",
                status="open", uncertainty="u-a"),
            obj("risk-b", "Risk", statement="s", kind="other", consequence="c", owner="o",
                status="open", uncertainty="u-b"),
            {**episode(), "rev": 2, "risks": ["risk-a", "risk-b"]})
    assert "lexicon-mixed" in rules(g)
    put_all(g, obj("u-b", "Uncertainty", kind="interval", spec={}, lexicon="A", rev=2))
    assert "lexicon-mixed" not in rules(g)


def test_claim_unsupported(base_graph):
    g = base_graph
    put_all(g, claim("cl-1", []), {**episode(), "rev": 2, "claims": ["cl-1"]})
    assert "claim-unsupported" in rules(g)
    put_all(g, {**claim("cl-1", ["ev-doc"]), "rev": 2})
    assert "claim-unsupported" not in rules(g)


def test_claim_on_gap(base_graph):
    g = base_graph
    put_all(g, gap("gap-c"),
            claim("cl-2", [], supportedBy={"$gap": "gap-c"}),
            {**episode(), "rev": 2, "claims": ["cl-2"]})
    assert "claim-on-gap" in rules(g)
    put_all(g, {**claim("cl-2", ["ev-doc"]), "rev": 2})
    assert "claim-on-gap" not in rules(g)


def test_claim_on_exclusion(base_graph):
    g = base_graph
    put_all(g, obj("ex-cl", "Exclusion", target={"kind": "Evidence", "label": "x"},
                   reasonType="dominated", reason="r",
                   authority={"who": "w", "role": "r", "date": "2023"},
                   retainedInStructure=True),
            claim("cl-4", [], supportedBy={"$exclusion": "ex-cl"}),
            {**episode(), "rev": 2, "claims": ["cl-4"]})
    assert "claim-on-exclusion" in rules(g)
    put_all(g, {**claim("cl-4", ["ev-doc"]), "rev": 2})
    assert "claim-on-exclusion" not in rules(g)


def test_inclusion_reason_missing(base_graph):
    g = base_graph
    put_all(g, evidence("ev-i"), claim("cl-3", ["ev-i"]),
            {**episode(), "rev": 2, "claims": ["cl-3"]})
    assert "inclusion-reason-missing" in rules(g)
    put_all(g, {**evidence("ev-i"), "rev": 2, "inclusionReason": "why"})
    assert "inclusion-reason-missing" not in rules(g)


def test_inclusion_reason_missing_names_the_claim_and_the_episode(base_graph):
    """The finding names the episode, the claim and the evidence — in that order.

    The rule does not fire on an object sitting in a register; it fires because a claim
    of a particular episode cited it. Naming the evidence alone left every consumer that
    scopes findings by the objects they mention unable to say whose claim did the citing,
    so a second episode sharing the same evidence register reported the finding too. Here
    two episodes share `ev-i` and only one of them cites it.
    """
    g = base_graph
    put_all(g,
            evidence("ev-i"),
            claim("cl-3", ["ev-i"]),
            {**episode(), "rev": 2, "claims": ["cl-3"], "evidenceRegister": ["ev-i"]},
            # A second episode holding the same evidence in its register and citing
            # nothing. Nothing here is that episode's finding.
            {**episode("ep-2"), "evidenceRegister": ["ev-i"]})
    hits = [f for f in validate(g, g.get("pol-1"))
            if f.rule == "inclusion-reason-missing"]
    assert len(hits) == 1, hits
    assert hits[0].objects == ("ep-1", "cl-3", "ev-i")
    assert "cl-3" in hits[0].message and "ep-1" in hits[0].message
    # The episode id is the scoping key, so it comes first — as in `silent-omission`.
    assert hits[0].objects[0] == "ep-1"


def test_assumption_conflict(base_graph):
    g = base_graph
    put_all(g,
            obj("as-x", "Assumption", statement="s", linchpin=False, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            obj("as-y", "Assumption", statement="s2", linchpin=False, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False, conflictsWith=["as-x"]),
            {**episode(), "rev": 2, "assumptions": ["as-x", "as-y"]})
    assert "assumption-conflict" in rules(g)
    put_all(g, obj("as-y", "Assumption", statement="s2", linchpin=False, rationale="r",
                   evidence="ev-doc", implicationsIfWrong="i",
                   indicatorsThatWouldAlter=["x"], variedInSensitivity=False,
                   conflictsWith=[], rev=2))
    assert "assumption-conflict" not in rules(g)


def test_assumption_conflict_out_of_scope_is_not_reported(base_graph):
    g = base_graph
    put_all(g,
            obj("as-p", "Assumption", statement="s", linchpin=False, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            obj("as-q", "Assumption", statement="s2", linchpin=False, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False, conflictsWith=["as-p"]))
    # Neither assumption is referenced by any episode: out of scope for pol-1.
    assert "assumption-conflict" not in rules(g)


def test_model_vva_positive_case_gap_is_blocking(base_graph):
    g = base_graph
    put_all(g, gap("gap-vva"), model("mdl-2", vva={"$gap": "gap-vva"}),
            {**episode(), "rev": 2, "models": ["mdl-2"]})
    f = [x for x in validate(g, g.get("pol-1")) if x.rule == "model-vva"]
    assert f and f[0].severity == "blocking"
    put_all(g, obj("vva-2", "VVARecord", problemStatement="ch-1",
                   requirementsAndAcceptabilityCriteria="r",
                   assumptionsCapabilitiesLimitationsRisks={
                       "assumptions": ["a"], "capabilities": ["c"],
                       "limitations": ["l"], "risks": ["r"],
                   },
                   methodology="m",
                   accreditationDecision={"authority": "PM", "date": "2021-06", "scope": "s",
                                          "basis": "document"},
                   sections=[{"name": "Problem Statement", "content": "x"}]),
            model("mdl-2", vva="vva-2", rev=2))
    assert "model-vva" not in rules(g)


def test_scoping_isolates_findings_between_two_policies(base_graph):
    g = base_graph
    put_all(g, policy("pol-2"), charter("ch-2", decisionClassPolicy="pol-2"),
            episode("ep-2", charter="ch-2"))
    put_all(g, gap("gap-only-2", confirmed=False),
            obj("as-2", "Assumption", statement="s", linchpin=False, rationale="r",
                evidence={"$gap": "gap-only-2"}, implicationsIfWrong="i",
                indicatorsThatWouldAlter=["x"], variedInSensitivity=False),
            {**episode("ep-2", charter="ch-2"), "rev": 2, "assumptions": ["as-2"]})
    assert "gap-unconfirmed" not in rules(g, "pol-1")
    assert "gap-unconfirmed" in rules(g, "pol-2")


def test_policy_rules_tolerate_a_malformed_exclusion_missing_target(base_graph):
    g = base_graph
    put_all(g, obj("ex-bad", "Exclusion", target={"kind": "Study", "label": "x"},
                   reasonType="time-or-resource", reason="r",
                   authority={"who": "w", "role": "r", "date": "2023"},
                   retainedInStructure=True))
    g._latest["ex-bad"].pop("target", None)
    g._history["ex-bad"][1].pop("target", None)
    findings = validate(g, g.get("pol-1"))
    assert "schema" in {f.rule for f in findings}


def test_policy_rules_tolerate_a_malformed_assumption_missing_linchpin(base_graph):
    g = base_graph
    put_all(g,
            obj("as-bad", "Assumption", statement="s", linchpin=True, rationale="r",
                evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            {**episode(), "rev": 2, "assumptions": ["as-bad"]})
    g._latest["as-bad"].pop("linchpin", None)
    g._history["as-bad"][1].pop("linchpin", None)
    findings = validate(g, g.get("pol-1"))
    assert "schema" in {f.rule for f in findings}


def test_policy_rules_tolerate_a_malformed_episode_missing_charter(base_graph):
    g = base_graph
    g._latest["ep-1"].pop("charter", None)
    g._history["ep-1"][1].pop("charter", None)
    findings = validate(g, g.get("pol-1"))
    assert "schema" in {f.rule for f in findings}


def test_silent_omission_excluded_set_is_scoped_to_the_policy(base_graph):
    """An Exclusion reachable only from another policy's episode must not clear a
    silent-omission finding for this policy: excluded/registered isolation matters as
    much for suppressing a finding as it does for raising one."""
    g = base_graph
    put_all(g, evidence("ev-a"), {**episode(), "rev": 2, "evidenceRegister": ["ev-a"]})
    put_all(g, policy("pol-2"), charter("ch-2", decisionClassPolicy="pol-2"),
            alternative("alt-b"),
            {**episode("ep-2", charter="ch-2"), "alternatives": ["alt-b"]})
    put_all(g, obj("ex-b", "Exclusion",
                   target={"kind": "Alternative", "id": "alt-b", "label": "b"},
                   reasonType="dominated", reason="r",
                   authority={"who": "w", "role": "r", "date": "2023"},
                   retainedInStructure=True))
    # ex-b is reachable from pol-2's episode (via alt-b) and targets something entirely
    # unrelated to pol-1's evidence register: it must not affect pol-1's evaluation.
    assert "silent-omission" in rules(g, "pol-1")


def test_policy_rules_tolerate_unhashable_domain_values(base_graph):
    """lexicon, reasonType, prohibitedExclusionReasons items, and assertion values can
    all be malformed (a $gap marker, a nested list) without validate() raising."""
    g = base_graph
    put_all(g,
            obj("risk-bad", "Risk", statement="s", kind="other", consequence="c",
                owner="o", status="open", uncertainty="u-bad"),
            {**episode(), "rev": 2, "evidenceRegister": ["ev-bad"], "risks": ["risk-bad"]})

    bad_policy = {**policy(), "rev": 2,
                  "prohibitedExclusionReasons": ["time-or-resource", ["x"]]}
    g._latest["pol-1"] = bad_policy
    g._history["pol-1"][2] = bad_policy

    u_bad = obj("u-bad", "Uncertainty", kind="interval", spec={}, lexicon={"$gap": "g"})
    g._latest["u-bad"] = u_bad
    g._history["u-bad"][1] = u_bad

    ex_bad = obj("ex-bad", "Exclusion", target={"kind": "Study", "label": "x"},
                 reasonType={"$gap": "g"}, reason="r",
                 authority={"who": "w", "role": "r", "date": "2023"},
                 retainedInStructure=True)
    g._latest["ex-bad"] = ex_bad
    g._history["ex-bad"][1] = ex_bad

    ev_bad = evidence("ev-bad", assertions=[
        {"subject": "s", "field": "f", "value": ["x"], "locator": "p.1"},
    ])
    g._latest["ev-bad"] = ev_bad
    g._history["ev-bad"][1] = ev_bad

    findings = validate(g, g.get("pol-1"))
    assert "schema" in {f.rule for f in findings}


def test_observation_duplicate_fires_and_clears(base_graph):
    g = base_graph
    put_all(g, objective("obj-1", measures=["m-1"]), measure("m-1", "obj-1"),
            alternative("alt-a"),
            observation("ob-1", "alt-a", "m-1", 1), observation("ob-2", "alt-a", "m-1", 2),
            {**episode(), "rev": 2, "objectives": ["obj-1"], "alternatives": ["alt-a"],
             "observations": ["ob-1", "ob-2"]})
    f = [x for x in validate(g, g.get("pol-1")) if x.rule == "observation-duplicate"]
    assert f and f[0].severity == "blocking" and f[0].objects == ("ob-1", "ob-2")

    put_all(g, {**episode(), "rev": 3, "objectives": ["obj-1"], "alternatives": ["alt-a"],
                "observations": ["ob-1"]})
    assert "observation-duplicate" not in rules(g)


# ---- kernel hygiene: _episodes with no real Policy id --------------------------------


def test_episodes_with_no_policy_id_selects_every_episode_in_the_graph(base_graph):
    """`_episodes(g, policy)` with a `policy` that names no `id` at all — `None`, `{}`,
    or any other dict without one — is not "select no episodes": it means the caller has
    no real Policy to read a *field* from, so the structure-only rules run over every
    episode in the graph regardless of what its own charter names. Two episodes with two
    different, both resolvable, policies are both selected either way."""
    g = base_graph
    put_all(g, policy("pol-2"), charter("ch-2", decisionClassPolicy="pol-2"),
            episode("ep-2", charter="ch-2"))
    ep_ids = {"ep-1", "ep-2"}
    assert {e["id"] for e in _episodes(g, None)} == ep_ids
    assert {e["id"] for e in _episodes(g, {})} == ep_ids
    assert {e["id"] for e in _episodes(g, {"notId": "x"})} == ep_ids


def test_episodes_with_a_real_policy_id_still_scopes_by_charter(base_graph):
    """The widening above must not touch the case that already worked: a Policy with a
    real `id` still selects only the episodes whose charter names that id."""
    g = base_graph
    put_all(g, policy("pol-2"), charter("ch-2", decisionClassPolicy="pol-2"),
            episode("ep-2", charter="ch-2"))
    assert {e["id"] for e in _episodes(g, g.get("pol-1"))} == {"ep-1"}
    assert {e["id"] for e in _episodes(g, g.get("pol-2"))} == {"ep-2"}


def test_an_unresolvable_policy_no_longer_silences_the_structure_only_rules(base_graph):
    """The N1 fix, exercised directly at this module's level: a caller that has nothing
    but `{}` to pass in (readiness.py's stand-in for a `decisionClassPolicy` that could
    not be read as a Policy) still gets `baseline-present` — the structure-only rule
    that reads no policy field — for a record with a dropped baseline. Before this fix,
    `_episodes(g, {})` matched only episodes whose charter set no
    `decisionClassPolicy` at all, which silently dropped this episode (its charter
    names `pol-1`) instead."""
    g = base_graph
    put_all(g, alternative("alt-a"), {**episode(), "rev": 2, "alternatives": ["alt-a"]})
    assert "baseline-present" in {f.rule for f in validate(g, {})}


# ---- linchpin-not-varied (Policy.requireAllLinchpinsVaried, design §7.1/§7.3) --------

_NOW = "2026-09-04T00:00:00Z"


def _run(oid="run-1", **over):
    """A minimal, schema-shaped EvaluationRun — sealed the way `evaluate()` seals one,
    so `_has_sealed_run` finds it exactly as it would find a real one."""
    base = dict(plan="pl-1", step="s1", evaluator="mdl-1", evaluatorVersion="1",
                method="mavt", inputsHash="a" * 32, parameterBindings={}, seed=1,
                kernelVersion="0.1.0", outputs=[], outputHashes=[], ranking=[],
                sealedAt=_NOW, sealedBy="kernel", runRecordHash="a" * 64)
    base.update(over)
    return obj(oid, "EvaluationRun", **base)


def _flip(oid, assumption_id, run_id="run-1", **over):
    base = dict(run=run_id, parameter={"kind": "weight", "target": "t", "label": "l"},
                assumption=assumption_id, currentValue=0.5,
                range={"lo": 0.0, "hi": 1.0, "source": "default"},
                flipThreshold=0.7, flipDistance=0.2, direction="up",
                rankingBefore=[], rankingAfter=[], kernelVersion=KERNEL_VERSION)
    base.update(over)
    return obj(oid, "FlipAnalysis", **base)


def _linchpin(oid="as-lp", **over):
    base = dict(statement="s", linchpin=True, rationale="r", evidence="ev-doc",
                implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=True)
    base.update(over)
    return obj(oid, "Assumption", **base)


def test_linchpin_not_varied_fires_when_required_and_run_exists_but_no_flip(base_graph):
    g = base_graph
    put_all(g, _run("run-1"), _linchpin("as-lp"),
            {**episode(), "rev": 2, "assumptions": ["as-lp"], "runs": ["run-1"]})
    f = [x for x in validate(g, g.get("pol-1")) if x.rule == "linchpin-not-varied"]
    assert f and f[0].severity == "blocking" and f[0].objects == ("ep-1", "as-lp")


def test_linchpin_not_varied_clears_once_a_flip_names_the_assumption(base_graph):
    g = base_graph
    put_all(g, _run("run-1"), _linchpin("as-lp"), _flip("fa-1", "as-lp"),
            {**episode(), "rev": 2, "assumptions": ["as-lp"], "runs": ["run-1"],
             "flipAnalyses": ["fa-1"]})
    assert "linchpin-not-varied" not in rules(g)


def test_linchpin_not_varied_silent_when_policy_does_not_require_it(base_graph):
    """DES-6's softer states already score an unvaried linchpin when the policy has no
    opinion; this rule must add nothing on top of that."""
    g = base_graph
    put_all(g, {**policy(), "rev": 2, "requireAllLinchpinsVaried": False})
    put_all(g, _run("run-1"), _linchpin("as-lp"),
            {**episode(), "rev": 2, "assumptions": ["as-lp"], "runs": ["run-1"]})
    assert "linchpin-not-varied" not in rules(g)


def test_linchpin_not_varied_silent_with_no_runs_yet(base_graph):
    """Nothing has been computed yet for a FlipAnalysis to vary against, so the record
    is not faulted for lacking one before the first evaluation exists."""
    g = base_graph
    put_all(g, _linchpin("as-lp"), {**episode(), "rev": 2, "assumptions": ["as-lp"]})
    assert "linchpin-not-varied" not in rules(g)


def test_linchpin_not_varied_tolerates_garbage_runs_and_flips(base_graph):
    """A dangling run id, a non-string run id, and a FlipAnalysis missing its
    `assumption` field must not crash the rule -- and must not count as coverage."""
    g = base_graph
    bad_flip = obj("fa-bad", "FlipAnalysis", run="run-1",
                   parameter={"kind": "weight", "target": "t", "label": "l"},
                   currentValue=0.5, range={"lo": 0.0, "hi": 1.0, "source": "default"},
                   flipThreshold=0.7, flipDistance=0.2, direction="up",
                   rankingBefore=[], rankingAfter=[], kernelVersion=KERNEL_VERSION)
    bad_flip.pop("assumption", None)
    put_all(g, _run("run-1"), _linchpin("as-lp"), bad_flip,
            {**episode(), "rev": 2, "assumptions": ["as-lp"],
             "runs": ["run-1", "run-missing"],
             "flipAnalyses": ["fa-bad"]})
    # A non-string entry cannot survive `g.put`'s own schema check, so it is added by
    # hand, the same way `test_run_seal_tolerates_a_garbage_run` exercises a
    # hand-edited store elsewhere in this suite.
    ep = g.get("ep-1")
    hand_edited = {**ep, "runs": [*ep["runs"], 42]}
    g._latest["ep-1"] = hand_edited
    g._history["ep-1"][ep["rev"]] = hand_edited
    findings = validate(g, g.get("pol-1"))
    f = [x for x in findings if x.rule == "linchpin-not-varied"]
    assert f and f[0].objects == ("ep-1", "as-lp")


def test_value_conflict_message_is_stable_across_hash_seeds():
    """`value_conflicts` joins one row per evidence object into the finding's `message`.
    Iterating the register as a `set` made that text depend on `PYTHONHASHSEED`, which is
    randomised per process, so one graph produced a different message — and a different
    sort position inside `validate` — in every run. Two calls inside one interpreter
    share one seed and cannot see it; two subprocesses can."""
    import os
    import subprocess
    import sys
    import textwrap

    child = textwrap.dedent("""
        from docket.kernel.policy_rules import value_conflicts
        from tests.kernel.conftest import Graph, charter, drs, episode, evidence, policy, put_all

        g = Graph()
        put_all(g, policy(), drs(), charter())
        ids = [f"ev-{i:02d}" for i in range(12)]
        put_all(g, *[
            evidence(i, assertions=[{"subject": "s", "field": "f",
                                     "value": n, "locator": f"p.{n}"}])
            for n, i in enumerate(ids)])
        put_all(g, {**episode(), "evidenceRegister": ids})
        print([f.message for f in value_conflicts(g, g.get("pol-1"))][0])
    """)
    messages = {
        subprocess.run(
            [sys.executable, "-c", child], capture_output=True, text=True, check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        ).stdout
        for seed in ("1", "2")
    }
    assert len(messages) == 1, messages
