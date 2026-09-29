# tests/agent/test_refresh_watch.py
import pytest

from docket.agent.refresh_watch import (
    FINDING_TO_KIND,
    REFRESH_AFFECTED_TYPES,
    VALID_KINDS,
    detect,
    file_all,
    file_trigger,
)
from docket.errors import ValidationError
from docket.store import Graph

A = {"actorType": "agent", "actorId": "agent:recorded"}
H = {"actorType": "human", "actorId": "fixture"}
NOW = "2026-09-04T00:00:00Z"


def test_finding_to_kind_maps_the_two_scope_findings_and_nothing_else():
    # [ruling R11] ModelUsePastPurpose is a G1-time defect, not a refresh trigger.
    assert FINDING_TO_KIND == {
        "ReaccreditationRequired": "elapsed-time",
        "scope-lapsed": "evidence-changed",
    }
    assert "ModelUsePastPurpose" not in FINDING_TO_KIND


def test_refresh_affected_types_and_valid_kinds_come_from_the_catalogue():
    assert REFRESH_AFFECTED_TYPES == {
        "Claim", "Assumption", "Evidence", "Objective", "Model", "Alternative",
        "DecisionEpisode",
    }
    assert VALID_KINDS == {
        "evidence-changed", "assumption-changed", "intended-use-changed",
        "artefact-version-changed", "elapsed-time", "indicator-detected",
        "signer-return",
        "external-finding",
    }


def test_elapsed_accreditation_becomes_an_elapsed_time_proposal(program_with_stale_model):
    g, prog = program_with_stale_model
    props = detect(g, prog, now=NOW)
    elapsed = [p for p in props if p["kind"] == "elapsed-time"]
    assert len(elapsed) == 1
    # [ruling R11] the wording comes from the kernel's finding, not a second copy of the rule
    assert "4-2i(3)" in elapsed[0]["description"]
    assert elapsed[0]["affected"] == ["mdl-1"]          # the VVARecord id is not an allowed ref
    assert "id" not in elapsed[0] and "createdBy" not in elapsed[0]
    assert elapsed[0]["detectedAt"] == NOW


def test_lapsed_scope_becomes_an_evidence_changed_proposal(program_with_lapsed_evidence):
    g, prog = program_with_lapsed_evidence
    props = detect(g, prog, now=NOW)
    kinds = {p["kind"] for p in props}
    assert "evidence-changed" in kinds
    lapsed = [p for p in props if p["kind"] == "evidence-changed"]
    assert lapsed[0]["affected"] == ["ev-lapsed"]


def test_model_use_past_purpose_is_not_a_refresh_trigger(program_with_wrong_class_model):
    # [ruling R11] it is a G1-time defect in the record, not a signal that the world moved
    g, prog = program_with_wrong_class_model
    assert detect(g, prog, now=NOW) == []


def test_indicator_match_on_new_evidence(program_with_indicator):
    g, prog = program_with_indicator
    props = [p for p in detect(g, prog, now=NOW) if p["kind"] == "indicator-detected"]
    assert len(props) == 1
    assert set(props[0]["affected"]) == {"as-1", "ev-new"}
    assert props[0]["source"] == "ev-new"
    assert "fuel price volatility" in props[0]["description"].lower()


def test_indicator_match_requires_a_non_letter_boundary(program_with_boundary_indicator):
    """[fix round 1, issue I1] "rice" must not match the "rice" inside "Price" (no
    boundary), but must match a real word bounded by a space/string-start or a hyphen."""
    g, prog = program_with_boundary_indicator
    props = [p for p in detect(g, prog, now=NOW) if p["kind"] == "indicator-detected"]
    sources = {p["source"] for p in props}
    assert "ev-steel" not in sources        # "2026 Steel Price Index Update" — no match
    assert "ev-rice-word" in sources        # "Rice price index, 2026"
    assert "ev-rice-hyphen" in sources      # "rice-yield update"


def test_indicator_slot_holding_a_gap_does_not_crash(program_with_gapped_indicators):
    # [pre-flight defect 15] indicatorsThatWouldAlter is a slot and may be {"$gap": ...}
    g, prog = program_with_gapped_indicators
    assert detect(g, prog, now=NOW) == []


def test_detect_is_deterministic(program_with_indicator):
    g, prog = program_with_indicator
    assert detect(g, prog, now=NOW) == detect(g, prog, now=NOW)


def test_detect_sorts_by_kind_source_and_affected(program_with_indicator):
    g, prog = program_with_indicator
    props = detect(g, prog, now=NOW)
    keys = [(p["kind"], p["source"], tuple(p["affected"])) for p in props]
    assert keys == sorted(keys)


def test_detect_refuses_an_unknown_program():
    g = Graph()
    with pytest.raises(ValidationError):
        detect(g, "prg-nope", now=NOW)


def test_detect_narrows_to_one_episode_when_episode_id_is_given(program_with_stale_model):
    g, prog = program_with_stale_model
    assert detect(g, prog, now=NOW, episode_id="ep-1") == detect(g, prog, now=NOW)
    with pytest.raises(ValidationError):
        detect(g, prog, now=NOW, episode_id="ep-nope")


def test_file_trigger_appends_to_the_program(program_with_stale_model):
    g, prog = program_with_stale_model
    t = file_trigger(g, prog, kind="elapsed-time", source="kernel.scope.check_scope",
                     description="accreditation older than three years",
                     detected_at=NOW, affected=["mdl-1"], actor=A, now=NOW)
    assert t["id"] == f"rt-{prog}-1" and t["createdBy"] == A
    assert t["id"] in g.get(prog)["refreshTriggers"]
    assert t["detectedAt"] == NOW and t["description"]


def test_file_trigger_by_a_human_actor_also_works(program_with_stale_model):
    g, prog = program_with_stale_model
    t = file_trigger(g, prog, kind="elapsed-time", source="s", description="d",
                     detected_at=NOW, affected=["mdl-1"], actor=H, now=NOW)
    assert t["createdBy"] == H


def test_file_trigger_numbers_ids_after_existing_triggers(program_with_stale_model):
    g, prog = program_with_stale_model
    t1 = file_trigger(g, prog, kind="elapsed-time", source="s", description="d",
                      detected_at=NOW, affected=["mdl-1"], actor=A, now=NOW)
    t2 = file_trigger(g, prog, kind="elapsed-time", source="s2", description="d2",
                      detected_at=NOW, affected=["mdl-1"], actor=A, now=NOW)
    assert t1["id"] == f"rt-{prog}-1" and t2["id"] == f"rt-{prog}-2"
    assert g.get(prog)["refreshTriggers"] == [t1["id"], t2["id"]]


def test_file_trigger_refuses_an_unknown_kind(program_with_stale_model):
    g, prog = program_with_stale_model
    with pytest.raises(ValidationError):
        file_trigger(g, prog, kind="vibes", source="s", description="d", detected_at=NOW,
                     affected=["mdl-1"], actor=A, now=NOW)
    # nothing was written
    assert g.get(prog)["refreshTriggers"] == []


def test_file_trigger_refuses_an_affected_id_of_the_wrong_type(program_with_stale_model):
    g, prog = program_with_stale_model
    with pytest.raises(ValidationError):
        file_trigger(g, prog, kind="elapsed-time", source="s", description="d",
                     detected_at=NOW, affected=["vva-1"], actor=A, now=NOW)


def test_file_trigger_refuses_a_dangling_affected_id(program_with_stale_model):
    g, prog = program_with_stale_model
    with pytest.raises(ValidationError):
        file_trigger(g, prog, kind="elapsed-time", source="s", description="d",
                     detected_at=NOW, affected=["mdl-nope"], actor=A, now=NOW)


def test_file_trigger_refuses_an_unknown_program(program_with_stale_model):
    g, _ = program_with_stale_model
    with pytest.raises(ValidationError):
        file_trigger(g, "prg-nope", kind="elapsed-time", source="s", description="d",
                     detected_at=NOW, affected=["mdl-1"], actor=A, now=NOW)


def test_file_all_files_every_proposal_in_order(program_with_stale_model):
    g, prog = program_with_stale_model
    proposals = detect(g, prog, now=NOW)
    filed = file_all(g, prog, proposals, actor=A, now=NOW)
    assert [t["kind"] for t in filed] == [p["kind"] for p in proposals]
    assert g.get(prog)["refreshTriggers"] == [t["id"] for t in filed]
