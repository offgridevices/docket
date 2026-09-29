import json

import pytest

from docket.schema import catalogue, load_schema, validate_object
from docket.schema.generate import OUT, build, generate

ENV = {
    "id": "x-1", "rev": 1,
    "createdBy": {"actorType": "human", "actorId": "t"},
    "createdAt": "2026-09-04T00:00:00Z",
}


def test_generated_files_are_current(tmp_path):
    cat = catalogue()
    for name, spec in cat["types"].items():
        on_disk = (OUT / f"{name}.schema.json").read_text()
        expected = json.dumps(build(name, spec, cat), indent=2, sort_keys=True) + "\n"
        stale_msg = f"{name}.schema.json is stale — run: uv run python -m docket.schema.generate"
        assert on_disk == expected, stale_msg


def test_build_rejects_unknown_ref_target():
    with pytest.raises(ValueError):
        build("Widget", {"fields": {"owner": {"ref": "Nope"}}}, catalogue())


def test_every_type_has_a_schema():
    on_disk = sorted(p.stem.replace(".schema", "") for p in OUT.glob("*.schema.json"))
    assert on_disk == sorted(catalogue()["types"])


def test_envelope_required():
    errs = validate_object({"type": "Rationale", "text": "t", "author": "a"})
    assert any("'id' is a required property" in e for e in errs)


def test_valid_rationale():
    assert validate_object({**ENV, "type": "Rationale", "text": "t", "author": "a"}) == []


def test_slot_accepts_content_exclusion_or_gap():
    base = {**ENV, "type": "GroundRule", "statement": "s"}
    assert validate_object({**base, "source": "ev-1"}) == []
    assert validate_object({**base, "source": {"$exclusion": "ex-1"}}) == []
    assert validate_object({**base, "source": {"$gap": "gap-1"}}) == []
    assert validate_object({**base, "source": None}) != []
    assert validate_object({**base, "source": {"$gap": "gap-1", "extra": 1}}) != []


def test_evidence_variant_requires_type_specific_fields():
    ev = {
        **ENV, "type": "Evidence", "title": "TP", "evidenceType": "SoldierTouchpoint",
        "pointer": {"$gap": "gap-1"},
        "classification": {"level": "U", "metadataLevel": "U"},
        "scopeOfValidity": {
            "builtToAnswer": "q", "questionClass": "desired-characteristics", "intendedUse": "u",
        },
        "reviewStatus": "draft", "reliabilitySteps": {"$gap": "gap-2"},
    }
    errs = validate_object(ev)
    assert any("'n' is a required property" in e for e in errs)
    ok = {**ev, "n": {"$gap": "gap-3"}, "selectionRule": {"$gap": "gap-3"}, "unit": "1/4 ABCT",
          "instrument": ["questionnaire"], "dates": "2021-07", "analysisMethod": {"$gap": "gap-3"}}
    assert validate_object(ok) == []


def test_unknown_field_rejected():
    errs = validate_object({**ENV, "type": "Rationale", "text": "t", "author": "a", "bogus": 1})
    assert errs and "bogus" in errs[0]


def test_unknown_type():
    assert validate_object({**ENV, "type": "Nope"}) == ["unknown type 'Nope'"]


def test_generate_is_idempotent(tmp_path, monkeypatch):
    import docket.schema.generate as g
    monkeypatch.setattr(g, "OUT", tmp_path)
    a = {p.name: p.read_bytes() for p in generate()}
    b = {p.name: p.read_bytes() for p in generate()}
    assert a == b and len(a) == 39


def test_catalogue_and_load_schema_hand_out_copies():
    """A caller that edits what it gets must not poison every later validation."""
    cat = catalogue()
    cat["types"]["Rationale"]["fields"]["text"] = "mutated"
    cat["types"].pop("Charter")
    assert catalogue()["types"]["Rationale"]["fields"]["text"] != "mutated"
    assert "Charter" in catalogue()["types"]

    schema = load_schema("Rationale")
    schema["properties"]["text"] = {"type": "integer"}
    assert load_schema("Rationale")["properties"]["text"] != {"type": "integer"}


# ---- plan 2026-09-11 (UI rebuild): the two optional fields and the signer-return kind ----

CHARTER_MIN = {
    **ENV, "type": "Charter", "question": "q", "decisionToBeMade": "d",
    "consequencesOfErroneousOutput": "c", "questionClass": "other",
    "scope": {"included": [], "excluded": []}, "authority": {"signer": "s"},
    "decisionClassPolicy": "pol-1",
}

POLICY_MIN = {
    **ENV, "type": "Policy", "name": "p", "version": "0.1", "decisionClass": "d",
    "method": "mavt", "tailoring": "published-21", "aggregationK": 1,
    "requiredBiasChecks": [], "requireAllLinchpinsVaried": False,
    "prohibitedExclusionReasons": [], "blockingRules": [], "nSimplex": 10,
}

TRIGGER_MIN = {
    **ENV, "type": "RefreshTrigger", "kind": "elapsed-time", "source": "s",
    "description": "d", "detectedAt": "2026-09-11", "affected": ["as-1"],
}


def test_charter_needed_by_is_optional_and_a_string():
    assert validate_object(CHARTER_MIN) == []
    assert validate_object({**CHARTER_MIN, "neededBy": "2026-09-30"}) == []
    assert validate_object({**CHARTER_MIN, "neededBy": 20260930}) != []


def test_policy_expected_days_by_state_is_optional_and_integer_valued():
    assert validate_object(POLICY_MIN) == []
    assert validate_object({**POLICY_MIN, "expectedDaysByState": {"DRAFT": 10}}) == []
    assert validate_object({**POLICY_MIN, "expectedDaysByState": {"DRAFT": "ten"}}) != []


def test_refresh_trigger_accepts_signer_return_naming_an_episode():
    assert validate_object(TRIGGER_MIN) == []
    assert validate_object({**TRIGGER_MIN, "kind": "signer-return",
                            "affected": ["ep-1"]}) == []
    assert validate_object({**TRIGGER_MIN, "kind": "not-a-kind"}) != []


def test_no_demo_record_sets_the_two_new_fields():
    """The two fields are optional and unset in every committed demo: the clock and the
    queue are computed at request time and never change a demo output."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "demos"
    for path in root.glob("*/out/graph/objects/*.json"):
        obj = json.loads(path.read_text())
        assert "neededBy" not in obj, path
        assert "expectedDaysByState" not in obj, path
