from docket.objects import (
    AGENT_FORBIDDEN_TYPES,
    SLOTS,
    TYPES,
    is_content,
    is_exclusion_ref,
    is_gap_ref,
    iter_refs,
    iter_slots,
    marker_target,
)

ENV = {
    "id": "x", "rev": 1,
    "createdBy": {"actorType": "human", "actorId": "t"},
    "createdAt": "2026-09-04",
}


def test_types_count_and_forbidden_subset():
    assert len(TYPES) == 39
    assert AGENT_FORBIDDEN_TYPES <= TYPES
    assert len(AGENT_FORBIDDEN_TYPES) == 10
    assert {"EvaluationRun", "Result", "Commitment", "ReadinessReport",
            "Policy"} <= AGENT_FORBIDDEN_TYPES


def test_iter_refs_tolerates_an_object_with_no_type():
    assert list(iter_refs({"id": "x"})) == []


def test_markers():
    assert is_exclusion_ref({"$exclusion": "ex-1"}) and not is_gap_ref({"$exclusion": "ex-1"})
    assert is_gap_ref({"$gap": "g"}) and marker_target({"$gap": "g"}) == "g"
    assert marker_target("plain") is None
    for empty in (None, "", [], {}):
        assert not is_content(empty)
    assert is_content(0) and is_content("s") and is_content([1]) and not is_content({"$gap": "g"})


def test_slots_from_catalogue():
    assert SLOTS["Charter"] == ("question", "decisionToBeMade", "consequencesOfErroneousOutput")
    assert "evidence" in SLOTS["Assumption"] and "provenance" in SLOTS["Objective"]


def test_iter_refs_and_slots_walk_nested_and_variants():
    ev = {**ENV, "type": "Evidence", "title": "t", "evidenceType": "MSStudy",
          "pointer": {"$gap": "gap-p"}, "classification": {"level": "U", "metadataLevel": "U"},
          "scopeOfValidity": {"builtToAnswer": "q", "questionClass": "other", "intendedUse": "u"},
          "reviewStatus": "draft", "reliabilitySteps": ["drs-1", "drs-2"],
          "model": "m-1", "scenarios": {"$exclusion": "ex-s"}, "vvaRecord": {"$gap": "gap-v"}}
    refs = dict(iter_refs(ev))
    assert refs["pointer"] == "gap-p" and refs["reliabilitySteps/0"] == "drs-1"
    assert refs["model"] == "m-1" and refs["scenarios"] == "ex-s"
    assert refs["vvaRecord"] == "gap-v"
    slots = dict(iter_slots(ev))
    expected_slots = {
        "pointer", "scopeOfValidity", "reliabilitySteps", "model", "scenarios", "vvaRecord",
    }
    assert set(slots) >= expected_slots


def test_iter_slots_reaches_vva_sections():
    v = {
        **ENV, "type": "VVARecord", "problemStatement": "ch",
        "requirementsAndAcceptabilityCriteria": "r",
        "assumptionsCapabilitiesLimitationsRisks": {
            "assumptions": ["a"], "capabilities": {"$gap": "g1"},
            "limitations": ["l"], "risks": ["r"],
        },
        "methodology": "m", "accreditationDecision": {"$gap": "g2"},
        "sections": [
            {"name": "Problem Statement", "content": "c"},
            {"name": "Issues", "content": {"$exclusion": "ex-1"}},
        ],
    }
    slots = dict(iter_slots(v))
    assert slots["assumptionsCapabilitiesLimitationsRisks/capabilities"] == {"$gap": "g1"}
    assert slots["sections/1/content"] == {"$exclusion": "ex-1"}
    assert ("sections/1/content", "ex-1") in list(iter_refs(v))
