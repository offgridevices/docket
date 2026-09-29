"""Plan 07 Task 6: `GET /api/sources` (the Intake screen's source picker and the
committed request it can load), and the one thing recorded mode must mean.

Two subjects, both small:

1. `GET /api/sources` lists `sources/` — one entry per `.source.md` provenance stub, the
   artefact it documents, and that stub's own first heading. Public data only; the route
   reads no other directory.
2. `routes.agent._settings_for` — when the server is in recorded mode, the *backend* is
   the recorded one, not merely the header chip. The Intake screen's "Switch to recorded"
   button (`PUT /api/settings/mode`) is worth nothing if a live provider keeps being
   called behind a chip that says `RECORDED`.
"""
from __future__ import annotations

import json
from pathlib import Path

from docket.agent.backend import recording_key
from docket.agent.elicit import ELICITATION_SCHEMA, USER_TEMPLATE
from docket.agent.prompts import system_prompt
from docket.api.routes.agent import _settings_for
from docket.api.routes.session import (
    RECORDED_REQUEST_ARTIFACT,
    RECORDED_REQUEST_PATH,
    RECORDED_REQUEST_POLICY,
)

REPO = Path(__file__).resolve().parents[2]


# ---- GET /api/sources ---------------------------------------------------------------


def test_sources_lists_a_stub_with_its_artifact_and_title(client):
    body = client.get("/api/sources").json()
    names = {s["name"] for s in body["sources"]}
    assert "army-2020-02-25-omfv-characteristics-for-industry-comment" in names, names
    entry = next(s for s in body["sources"]
                 if s["name"] == "army-2020-02-25-omfv-characteristics-for-industry-comment")
    # The artefact string is what a caller passes as `sourceArtifact` to `/elicit`;
    # `sources/<file>` is the convention every committed object's
    # `ingestionProvenance.sourceArtifact` already uses.
    assert entry["artifact"].startswith("sources/")
    # Downloaded documents are not committed, so a fresh clone has only the note.
    local = [p for p in (REPO / "sources").glob(f"{entry['name']}.*")
             if not p.name.endswith(".source.md")]
    assert entry["hasLocalCopy"] is bool(local)
    assert entry["title"], "the stub's first heading is the picker's only title"


def test_sources_includes_a_stub_with_no_redistributable_copy(client):
    """Several entries in `sources/` document a cited document that is not in the tree
    (`gao-23-106059.source.md` has no companion). A picker built from the PDFs alone
    would silently drop exactly those, so the listing is keyed on the stubs."""
    body = client.get("/api/sources").json()
    stubs_only = [s for s in body["sources"] if not s["hasLocalCopy"]]
    assert stubs_only, "expected at least one source stub with no local artefact"
    # A note that names its document's file lists that file even with no local copy
    # (downloaded documents are not committed); a note with no document stays itself.
    notes_only = [s for s in stubs_only if s["artifact"].endswith(".source.md")]
    assert any(s["name"] == "gao-23-106059" for s in notes_only), notes_only
    for s in stubs_only:
        if not s["artifact"].endswith(".source.md"):
            note = (REPO / "sources" / f"{s['name']}.source.md").read_text(encoding="utf-8")
            assert f"| Local file | `{s['artifact'].removeprefix('sources/')}`" in note


def test_sources_reads_only_the_sources_directory(client, tmp_path, monkeypatch):
    monkeypatch.setenv("DOCKET_SOURCES_DIR", str(tmp_path / "elsewhere"))
    assert client.get("/api/sources").json()["sources"] == []


# ---- the committed request, and whether it can actually be answered -----------------


def test_recorded_request_names_the_three_arguments_the_recording_answers(client):
    rr = client.get("/api/sources").json()["recordedRequest"]
    assert rr["path"] == RECORDED_REQUEST_PATH
    assert rr["sourceArtifact"] == RECORDED_REQUEST_ARTIFACT
    assert rr["policyId"] == RECORDED_REQUEST_POLICY
    assert rr["text"] == (REPO / RECORDED_REQUEST_PATH).read_text()


def test_recorded_request_says_answer_absent_against_the_default_recording(client):
    """`DOCKET_LLM_RECORDING` is unset in the API test environment, so the resolved
    recording is `tests/fixtures/recorded/default.json` — committed empty on purpose
    (`tests/fixtures/recorded/README.md`, ruling N3). The picker must say so rather than
    offer a button that 503s."""
    rr = client.get("/api/sources").json()["recordedRequest"]
    assert rr["answerRecorded"] is False
    assert rr["recording"].endswith("default.json")


def test_recorded_request_says_answer_present_against_the_committed_elicit_fixture(
    client, monkeypatch,
):
    monkeypatch.setenv("DOCKET_LLM_RECORDING",
                       str(REPO / "tests" / "fixtures" / "recorded" / "elicit.json"))
    rr = client.get("/api/sources").json()["recordedRequest"]
    assert rr["answerRecorded"] is True


def test_recorded_request_arguments_are_the_ones_the_fixture_was_recorded_under(client):
    """The three strings above are only useful if they really are the ones the committed
    response answers — recompute the fixture key the way `RecordedBackend` does and look
    it up. This is the test that fails if `elicit`'s prompt template, its schema, or the
    system prompt changes and the route's constants are not updated with them."""
    rr = client.get("/api/sources").json()["recordedRequest"]
    user = USER_TEMPLATE.format(source_artifact=rr["sourceArtifact"],
                                request_text=rr["text"], policy_id=rr["policyId"])
    key = recording_key(system_prompt(), user, ELICITATION_SCHEMA)
    fixture = json.loads(
        (REPO / "tests" / "fixtures" / "recorded" / "elicit.json").read_text()
    )
    assert key in fixture, (
        "tests/fixtures/recorded/elicit.json holds no response for the request, source "
        "artefact and policy id GET /api/sources advertises"
    )


# ---- recorded mode means the recorded backend --------------------------------------


def _request_with(app):
    class _Req:
        pass

    r = _Req()
    r.app = app
    return r


def test_recorded_mode_forces_the_recorded_provider(client, monkeypatch):
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DOCKET_LLM_MODEL", "some-local-model")
    monkeypatch.setenv("DOCKET_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    client.app.state.mode_override = "recorded"
    assert _settings_for(_request_with(client.app)).provider == "recorded"


def test_live_mode_leaves_a_configured_provider_alone(client, monkeypatch):
    """"live" means "do not fall back", not "override my configured provider" — and a
    deliberately-chosen `recorded` provider must stay recorded under it."""
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    client.app.state.mode_override = "live"
    assert _settings_for(_request_with(client.app)).provider == "recorded"


def test_switching_the_mode_route_to_recorded_switches_the_backend(client, monkeypatch):
    """The Intake screen's one-click switch, end to end: `PUT /api/settings/mode` is the
    only thing it does, so that call alone must change which backend an agent route
    resolves."""
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DOCKET_LLM_MODEL", "some-local-model")
    monkeypatch.setenv("DOCKET_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    assert _settings_for(_request_with(client.app)).provider == "openai-compatible"

    assert client.put("/api/settings/mode", json={"mode": "recorded"}).status_code == 200
    assert _settings_for(_request_with(client.app)).provider == "recorded"
    assert client.get("/api/health").json()["mode"] == "recorded"
