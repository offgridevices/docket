# tests/kernel/test_scope.py
from docket.kernel.scope import LEVELS, check_scope, level_rank
from tests.kernel.conftest import episode, evidence, obj, put_all


def mk_claim(oid, ev, qc="force-structure", level="U", justify=False):
    sb = [{"evidence": ev, **({"reuseJustification": {"text": "j", "authority": "a"}}
                               if justify else {})}]
    return obj(oid, "Claim", text="c", questionClass=qc, assessableAt={"level": level},
               supportedBy=sb)


def mk_vva(oid, date, **over):
    base = dict(problemStatement="ch-1", requirementsAndAcceptabilityCriteria="r",
                assumptionsCapabilitiesLimitationsRisks={
                    "assumptions": ["a"], "capabilities": ["c"], "limitations": ["l"],
                    "risks": ["r"]},
                methodology="m",
                accreditationDecision={"authority": "PM", "date": date, "scope": "s",
                                       "basis": "document"},
                sections=[{"name": "Problem Statement", "content": "x"}])
    base.update(over)
    return obj(oid, "VVARecord", **base)


def mk_model(oid, vva, qc="other", **over):
    base = dict(name="m", definition={"kind": "simulation", "version": "1"}, intendedUse="u",
                questionClass=qc, vvaRecord=vva, qualificationStatus="validated")
    base.update(over)
    return obj(oid, "Model", **base)


def rules(g):
    return {f.rule for f in check_scope(g, "ep-1")}


def test_reuse_past_purpose_and_justification(base_graph):
    g = base_graph
    put_all(g, evidence("ev-trac", scopeOfValidity={
                "builtToAnswer": "desired characteristics",
                "questionClass": "desired-characteristics", "intendedUse": "u"}),
            mk_claim("cl-1", "ev-trac"),
            {**episode(), "rev": 2, "claims": ["cl-1"], "evidenceRegister": ["ev-trac"]})
    f = [x for x in check_scope(g, "ep-1") if x.rule == "ReusePastPurpose"]
    assert f and f[0].severity == "blocking" and f[0].objects == ("cl-1", "ev-trac")
    put_all(g, {**mk_claim("cl-1", "ev-trac", justify=True), "rev": 2})
    assert "ReusePastPurpose" not in rules(g) and "reuse-justified" in rules(g)


def test_not_assessable_when_metadata_above_level_or_missing(base_graph):
    g = base_graph
    put_all(g, evidence("ev-s", classification={"level": "S", "metadataLevel": "S"}),
            mk_claim("cl-1", "ev-s", qc="other"), {**episode(), "rev": 2, "claims": ["cl-1"]})
    assert "NotAssessableAtLevel" in rules(g)
    put_all(g, {**evidence("ev-s", classification={"level": "S", "metadataLevel": "U"}),
                "rev": 2})
    r = rules(g)
    assert "NotAssessableAtLevel" not in r and "assessable-with-classified-value" in r
    put_all(g, {**evidence("ev-s", classification={"level": "S", "metadataLevel": "U"},
                           pointer={"$gap": "gap-p"}), "rev": 3},
            obj("gap-p", "InsufficientEvidence", sought="s", whereLookedFor=["x"],
                whyNotFound="w", impact="blocking", indicatorsThatWouldResolve=[]))
    f = [x for x in check_scope(g, "ep-1") if x.rule == "NotAssessableAtLevel"]
    assert f and "pointer" in f[0].message


def test_lapsed_and_model_use_and_reaccreditation(base_graph):
    """Two different model defects, two different rules. Using a model outside its
    intended question class is ¶4-2i(1) — EXE-3's own subject — and is reported as
    `ModelUsePastPurpose`; an accreditation older than three years is ¶4-2i(3) and stays
    `ReaccreditationRequired`. Collapsing them into one rule made an EXE-3 downgrade
    unattributable to the defect that caused it."""
    g = base_graph
    put_all(
        g,
        evidence("ev-old", scopeOfValidity={"builtToAnswer": "q", "questionClass": "other",
                                             "intendedUse": "u", "validUntil": "2020-01-01"}),
        mk_claim("cl-1", "ev-old", qc="other"),
        mk_vva("vva-1", "2019-05-01"),
        mk_model("mdl-1", "vva-1", qc="desired-characteristics"),
        {**episode(), "rev": 2, "claims": ["cl-1"], "models": ["mdl-1"]})
    r = check_scope(g, "ep-1")
    names = {x.rule for x in r}
    assert {"scope-lapsed", "ModelUsePastPurpose", "ReaccreditationRequired"} <= names

    use = [x for x in r if x.rule == "ModelUsePastPurpose"]
    assert len(use) == 1 and use[0].severity == "warning" and use[0].objects == ("mdl-1",)
    assert "4-2i(1)" in use[0].message and "F1" in use[0].message

    reacc = [x for x in r if x.rule == "ReaccreditationRequired"]
    assert len(reacc) == 1 and reacc[0].objects == ("mdl-1", "vva-1")
    assert "4-2i(3)" in reacc[0].message and "4-2i(1)" not in reacc[0].message


def test_model_with_exclusion_vva_record_yields_scope_unknown(base_graph):
    """Symmetric with the gap branch: a typed exclusion in place of a VV&A record must
    be reported, not silently skipped."""
    g = base_graph
    put_all(g,
            obj("ex-vva", "Exclusion", target={"kind": "Study", "label": "VV&A"},
                reasonType="data-unavailable", reason="never produced",
                authority={"who": "w", "role": "r", "date": "2024-01-01"},
                retainedInStructure=True),
            mk_model("mdl-1", {"$exclusion": "ex-vva"}),
            {**episode(), "rev": 2, "models": ["mdl-1"]})
    f = [x for x in check_scope(g, "ep-1")
         if x.rule == "scope-unknown" and x.objects == ("mdl-1",)]
    assert f and "typed exclusion" in f[0].message


def test_date_comparisons_use_day_resolution(base_graph):
    """A validUntil in the same month as asOf, but an earlier day, must still lapse:
    comparing by (year, month) alone would call these two dates equal and miss it."""
    g = base_graph
    put_all(g, evidence("ev-old", scopeOfValidity={
                "builtToAnswer": "q", "questionClass": "other", "intendedUse": "u",
                "validUntil": "2026-09-01"}),
            mk_claim("cl-1", "ev-old", qc="other"),
            {**episode(), "rev": 2, "claims": ["cl-1"]})  # episode() asOf is 2026-09-04
    assert "scope-lapsed" in rules(g)


def test_reaccreditation_day_resolution_and_exact_three_years_is_silent(base_graph):
    g = base_graph
    put_all(g, mk_vva("vva-1", "2023-09-01"), mk_model("mdl-1", "vva-1"),
            {**episode(), "rev": 2, "models": ["mdl-1"]})  # episode() asOf is 2026-09-04
    r = [x for x in check_scope(g, "ep-1")
         if x.rule == "ReaccreditationRequired" and "4-2i(3)" in x.message]
    assert r

    put_all(g, mk_vva("vva-2", "2023-09-04"), mk_model("mdl-2", "vva-2"),
            {**episode(), "rev": 3, "models": ["mdl-2"]})  # exactly 3 years before asOf
    r2 = [x for x in check_scope(g, "ep-1")
          if x.rule == "ReaccreditationRequired" and x.objects[0] == "mdl-2"]
    assert not r2


def test_year_only_dates_still_parse(base_graph):
    g = base_graph
    put_all(g, evidence("ev-old", scopeOfValidity={
                "builtToAnswer": "q", "questionClass": "other", "intendedUse": "u",
                "validUntil": "2020"}),
            mk_claim("cl-1", "ev-old", qc="other"),
            {**episode(), "rev": 2, "claims": ["cl-1"]})
    findings = check_scope(g, "ep-1")
    assert "scope-lapsed" in {x.rule for x in findings}
    assert not any(x.rule == "scope-unknown" and "ev-old" in x.objects for x in findings)


def test_claim_on_rejected_evidence(base_graph):
    g = base_graph
    put_all(g, evidence("ev-r", reviewStatus="rejected"),
            mk_claim("cl-1", "ev-r", qc="other"),
            {**episode(), "rev": 2, "claims": ["cl-1"]})
    f = [x for x in check_scope(g, "ep-1") if x.rule == "claim-on-rejected-evidence"]
    assert (f and f[0].severity == "blocking" and f[0].objects == ("cl-1", "ev-r")
            and f[0].message == "claim rests on evidence a reviewer rejected")


def test_non_dict_scope_of_validity_is_scope_unknown(base_graph):
    """A scopeOfValidity that is present (not a gap/exclusion) but the wrong shape must
    be reported, not silently skipped."""
    g = base_graph
    put_all(g, evidence("ev-x"), mk_claim("cl-1", "ev-x", qc="other"),
            {**episode(), "rev": 2, "claims": ["cl-1"]})
    bad_ev = {**g.get("ev-x"), "scopeOfValidity": ["not", "a", "dict"]}
    g._latest["ev-x"] = bad_ev
    g._history["ev-x"][bad_ev["rev"]] = bad_ev
    f = [x for x in check_scope(g, "ep-1")
         if x.rule == "scope-unknown" and x.objects == ("cl-1", "ev-x")]
    assert f


def test_condition_mismatch_fires_and_is_silent_without_scenarios(base_graph):
    g = base_graph
    put_all(g, evidence("ev-c", scopeOfValidity={
                "builtToAnswer": "q", "questionClass": "other", "intendedUse": "u",
                "conditions": ["jungle"]}),
            mk_claim("cl-1", "ev-c", qc="other"),
            obj("scn-1", "Scenario", name="s", description="d", rationale="r",
                conditions=["desert"], source="ev-doc"),
            {**episode(), "rev": 2, "claims": ["cl-1"], "scenarios": ["scn-1"]})
    assert "condition-mismatch" in rules(g)

    put_all(g, {**episode(), "rev": 3, "claims": ["cl-1"], "scenarios": []})
    assert "condition-mismatch" not in rules(g)


def test_model_with_gap_vva_record_yields_scope_unknown(base_graph):
    g = base_graph
    put_all(g, mk_model("mdl-1", {"$gap": "gap-vva"}),
            obj("gap-vva", "InsufficientEvidence", sought="s", whereLookedFor=["x"],
                whyNotFound="w", impact="blocking", indicatorsThatWouldResolve=[]),
            {**episode(), "rev": 2, "models": ["mdl-1"]})
    f = [x for x in check_scope(g, "ep-1")
         if x.rule == "scope-unknown" and x.objects == ("mdl-1",)]
    assert f


def test_level_rank_orders_classification_levels():
    assert LEVELS == ["U", "CUI", "C", "S", "TS"]
    assert level_rank("U") < level_rank("CUI") < level_rank("C") < level_rank("S") \
        < level_rank("TS")


def test_check_scope_tolerates_malformed_and_dangling_references(base_graph):
    """No malformed field or dangling reference may raise. Catalogue fields are read
    with .get() and defaults; a supportedBy/vvaRecord/claims/models entry whose id does
    not resolve in the graph is skipped (ref-integrity's job, not this checker's); and
    an unparsable date is reported as scope-unknown rather than raising or silently
    passing/failing the lapsed/reaccreditation check that depends on it.
    """
    g = base_graph
    put_all(
        g,
        evidence("ev-a"),
        evidence("ev-bad-date", scopeOfValidity={
            "builtToAnswer": "q", "questionClass": "other", "intendedUse": "u",
            "validUntil": "2020-01-01"}),
        mk_claim("cl-1", "ev-a", qc="other"),
        mk_claim("cl-ok-level", "ev-a", qc="other"),
        mk_claim("cl-bad-date", "ev-bad-date", qc="other"),
        obj("mdl-1", "Model", name="m", definition={"kind": "simulation", "version": "1"},
            intendedUse="u", questionClass="other", vvaRecord="vva-missing",
            qualificationStatus="validated"),
        {**episode(), "rev": 2,
         "claims": ["cl-1", "cl-ok-level", "cl-bad-date", "cl-missing"],
         "models": ["mdl-1", "mdl-missing"]})

    # From here on, mutate the store directly rather than through put(): every shape
    # below (a non-string asOf/validUntil, a non-dict classification, a supportedBy
    # entry with no matching Evidence) would be rejected by schema validation, but a
    # store written by an older/buggier version of docket, or hand-edited, is not
    # guaranteed to be schema-clean — this checker must not raise on it regardless.
    bad_ep = {**g.get("ep-1"), "asOf": 20260904}
    g._latest["ep-1"] = bad_ep
    g._history["ep-1"][bad_ep["rev"]] = bad_ep

    bad_date_ev = {**g.get("ev-bad-date")}
    bad_date_ev["scopeOfValidity"] = {**bad_date_ev["scopeOfValidity"], "validUntil": 20200101}
    g._latest["ev-bad-date"] = bad_date_ev
    g._history["ev-bad-date"][bad_date_ev["rev"]] = bad_date_ev

    # Corrupt cl-1 in place: no assessableAt, no questionClass, and a supportedBy
    # entry pointing at an evidence id that was never written.
    bad_claim = {**g.get("cl-1"),
                 "supportedBy": [{"evidence": "ev-missing"}, {"evidence": "ev-a"}]}
    bad_claim.pop("assessableAt", None)
    bad_claim.pop("questionClass", None)
    g._latest["cl-1"] = bad_claim
    g._history["cl-1"][bad_claim["rev"]] = bad_claim

    # Corrupt ev-a's classification into a non-dict shape.
    bad_ev = {**g.get("ev-a"), "classification": "not-a-dict"}
    g._latest["ev-a"] = bad_ev
    g._history["ev-a"][bad_ev["rev"]] = bad_ev

    findings = check_scope(g, "ep-1")  # must not raise
    assert isinstance(findings, list) and all(isinstance(f, object) for f in findings)

    # cl-1's questionClass is unreadable, so the reuse comparison against ev-a must be
    # skipped rather than compared against None and misreported as a purpose mismatch.
    assert not any(x.rule == "ReusePastPurpose" and "cl-1" in x.objects for x in findings)

    rule_names = {f.rule for f in findings}
    assert "scope-unknown" in rule_names
    unknown_msgs = " ".join(f.message for f in findings if f.rule == "scope-unknown")
    assert "asOf" in unknown_msgs
    assert "validUntil" in unknown_msgs
