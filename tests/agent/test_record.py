# tests/agent/test_record.py
"""`docket.agent.record` — the maintainer-only re-recording helper. Every test here
passes a fake, in-process backend by dependency injection [ruling R9]: nothing in this
file constructs a live backend or resolves settings toward one, so it never touches the
network.
"""

import json

import pytest

from docket.agent.backend import JsonBackendBase, recording_key
from docket.agent.record import CASES, Case, RecordingConflict, main, record_case
from docket.errors import RecordingMissing


class FakeBackend(JsonBackendBase):
    """A `Backend` that returns a fixed, schema-valid response without any I/O."""

    name = "fake-live"
    model_id = "fake-model"

    def __init__(self, response: dict):
        self.response = response
        self.calls: list[tuple[str, str, dict]] = []

    def _raw(self, system, user, schema, budget=None):
        self.calls.append((system, user, schema))
        return json.dumps(self.response)


SCHEMA = {"type": "object", "properties": {"n": {"type": "integer"}},
          "required": ["n"], "additionalProperties": False}


def test_record_case_writes_a_replayable_fixture(tmp_path):
    path = tmp_path / "recording.json"
    backend = FakeBackend({"n": 7})
    case = Case(system="sys", user="usr", schema=SCHEMA, note="a test case")

    key = record_case(backend, path, case)

    assert key == recording_key("sys", "usr", SCHEMA)
    data = json.loads(path.read_text())
    assert data[key]["response"] == '{"n":7}'
    assert data[key]["note"] == "a test case"

    # a RecordedBackend built against this file would replay the same value
    from docket.agent.backend import RecordedBackend

    replay = RecordedBackend(path)
    assert replay.complete_json(system="sys", user="usr", schema=SCHEMA) == {"n": 7}


def test_record_case_refuses_a_response_that_never_validates(tmp_path):
    path = tmp_path / "recording.json"
    backend = FakeBackend({"wrong": "shape"})
    case = Case(system="sys", user="usr", schema=SCHEMA, note="")
    from docket.errors import BackendError

    with pytest.raises(BackendError):
        record_case(backend, path, case)
    assert not path.exists()


# ---- [fix round 1, issue M4] refuse / force / identical -----------------------------


def test_record_case_refuses_to_overwrite_a_differing_response_without_force(tmp_path):
    path = tmp_path / "recording.json"
    case = Case(system="sys", user="usr", schema=SCHEMA, note="")
    record_case(FakeBackend({"n": 1}), path, case)
    before = path.read_text()

    with pytest.raises(RecordingConflict) as exc:
        record_case(FakeBackend({"n": 2}), path, case)

    assert path.read_text() == before, "a refused overwrite must not touch the file"
    assert exc.value.key == recording_key("sys", "usr", SCHEMA)
    # the one-line diff summary names the key and both responses' sha256
    assert exc.value.key in str(exc.value)
    assert exc.value.old_sha256 in str(exc.value) and exc.value.new_sha256 in str(exc.value)
    assert exc.value.old_sha256 != exc.value.new_sha256


def test_record_case_force_overwrites_a_differing_response(tmp_path, capsys):
    path = tmp_path / "recording.json"
    case = Case(system="sys", user="usr", schema=SCHEMA, note="")
    record_case(FakeBackend({"n": 1}), path, case)

    key = record_case(FakeBackend({"n": 2}), path, case, force=True)

    data = json.loads(path.read_text())
    assert data[key]["response"] == '{"n":2}'
    err = capsys.readouterr().err
    assert "overwriting" in err and key in err


def test_record_case_identical_rerecording_is_a_noop(tmp_path):
    path = tmp_path / "recording.json"
    case = Case(system="sys", user="usr", schema=SCHEMA, note="first note")
    record_case(FakeBackend({"n": 1}), path, case)
    before = path.read_text()

    # the response is identical; the note differs and must NOT land, proving this is a
    # genuine no-op (the file is not rewritten) rather than a write that happens to
    # produce the same response text.
    key = record_case(
        FakeBackend({"n": 1}), path,
        Case(system="sys", user="usr", schema=SCHEMA, note="a different note"),
    )

    assert key == recording_key("sys", "usr", SCHEMA)
    assert path.read_text() == before


ELICIT_RESPONSE_A = {
    "charter": {
        "question": {"value": None, "confidence": "absent", "locator": ""},
        "decisionToBeMade": {"value": None, "confidence": "absent", "locator": ""},
        "consequencesOfErroneousOutput": {"value": None, "confidence": "absent",
                                          "locator": ""},
        "questionClass": "other", "scopeIncluded": [], "scopeExcluded": [],
    },
    "objectives": [], "alternatives": [], "groundRules": [], "constraints": [],
    "assumptions": [], "evidence": [], "gaps": [],
}
ELICIT_RESPONSE_B = {**ELICIT_RESPONSE_A,
                     "charter": {**ELICIT_RESPONSE_A["charter"],
                                 "scopeIncluded": ["a different response"]}}


def test_main_refuses_to_overwrite_a_differing_response_without_force(tmp_path, capsys):
    path = tmp_path / "recording.json"
    main(["prog", str(path)], backend=FakeBackend(ELICIT_RESPONSE_A))
    before = path.read_text()

    rc = main(["prog", str(path)], backend=FakeBackend(ELICIT_RESPONSE_B))

    assert rc == 1
    assert path.read_text() == before, "a refused overwrite must not touch the file"
    assert "refusing" in capsys.readouterr().err


def test_main_force_flag_overwrites_a_differing_response(tmp_path, capsys):
    path = tmp_path / "recording.json"
    main(["prog", str(path)], backend=FakeBackend(ELICIT_RESPONSE_A))

    rc = main(["prog", str(path), "--force"], backend=FakeBackend(ELICIT_RESPONSE_B))

    assert rc == 0
    data = json.loads(path.read_text())
    assert "a different response" in json.dumps(data)
    assert "overwriting" in capsys.readouterr().err


def test_main_identical_rerecording_is_a_noop(tmp_path, capsys):
    path = tmp_path / "recording.json"
    main(["prog", str(path)], backend=FakeBackend(ELICIT_RESPONSE_A))
    before = path.read_text()

    rc = main(["prog", str(path)], backend=FakeBackend(ELICIT_RESPONSE_A))

    assert rc == 0
    assert path.read_text() == before
    assert "refusing" not in capsys.readouterr().err


def test_main_usage_accepts_only_a_trailing_force_flag():
    assert main(["prog", "a.json", "--not-force"]) == 2


def test_main_requires_exactly_one_argument():
    assert main(["prog"]) == 2
    assert main(["prog", "a.json", "b.json"]) == 2


def test_main_refuses_a_recorded_backend_by_name(tmp_path, capsys):
    path = tmp_path / "recording.json"
    backend = FakeBackend({"n": 1})
    backend.name = "recorded"

    rc = main(["prog", str(path)], backend=backend)

    assert rc == 1
    assert "refusing" in capsys.readouterr().err
    assert not path.exists()


def test_main_refuses_when_settings_resolve_to_recorded(tmp_path, monkeypatch, capsys):
    for var in ("DOCKET_LLM_PROVIDER", "DOCKET_LLM_MODEL", "DOCKET_LLM_BASE_URL",
                "DOCKET_LLM_CONFIG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DOCKET_LLM_CONFIG", str(tmp_path / "no-such-config.json"))
    path = tmp_path / "recording.json"

    rc = main(["prog", str(path)])

    assert rc == 1
    assert "refusing" in capsys.readouterr().err
    assert not path.exists()


def test_main_records_every_case_against_an_injected_backend(tmp_path, capsys):
    path = tmp_path / "recording.json"
    backend = FakeBackend({
        "charter": {
            "question": {"value": None, "confidence": "absent", "locator": ""},
            "decisionToBeMade": {"value": None, "confidence": "absent", "locator": ""},
            "consequencesOfErroneousOutput": {"value": None, "confidence": "absent",
                                              "locator": ""},
            "questionClass": "other", "scopeIncluded": [], "scopeExcluded": [],
        },
        "objectives": [], "alternatives": [], "groundRules": [], "constraints": [],
        "assumptions": [], "evidence": [], "gaps": [],
    })

    rc = main(["prog", str(path)], backend=backend)

    assert rc == 0
    err = capsys.readouterr().err
    assert "WARNING" in err
    data = json.loads(path.read_text())
    assert len(data) == len(CASES)
    for name in CASES:
        assert f"recorded {name} ->" in err


def test_recorded_backend_refuses_a_fixture_record_case_never_wrote(tmp_path):
    # Sanity check on the replay side of record_case: a RecordedBackend built against a
    # path nothing has recorded into yet refuses by name, matching the message
    # docket.agent.record's own module docstring quotes.
    with pytest.raises(RecordingMissing):
        from docket.agent.backend import RecordedBackend

        RecordedBackend(tmp_path / "never-written.json")
