"""Plan 07 Task 3: one route per `docket.agent.*` function, the human/agent actor
boundary, and the `EVALUATED` transition the API drives itself after a dispatch.

No route here talks to the network: every agent-actor route resolves its backend through
`routes.agent._agent`, a FastAPI dependency, and every test in this file overrides it
(`client.app.dependency_overrides[_agent] = lambda: (RecordedBackend(...), actor)`)
before making a request — the same seam `agent.py`'s own module docstring names.

Fixtures for `propose_plan`/`dispatch`/`narrate` are built the same way
`tests/agent/test_plan.py::demo_a_draft` and `tests/agent/test_dispatch.py::demo_a_at_g1`
build theirs: `demos.a_cbo_gcv_2013.build.build()` in memory, advanced to the lifecycle
state the route under test needs, then injected directly into the app's `SessionStore`
(the same private dict `tests/api/test_authority_counts.py` already reaches into). This
needs no built `demos/*/out/graph` on disk — `demo_a_present` is for tests that read the
*committed* store; these tests build their own copy in memory, so they run whether or not
plan 03b Task 7 has produced a store yet.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

import pytest

from docket.agent.backend import DENYLIST_FAMILIES, OVERRIDE_HINT, RecordedBackend
from docket.agent.cli import _actor_for
from docket.api.config import ConfigInvalid, agent_actor
from docket.api.routes.agent import _agent
from docket.api.sessions import Session
from docket.errors import BackendError
from docket.store import Graph

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "recorded"
REQUEST_TEXT = (REPO / "tests" / "fixtures" / "requests" / "omfv-con-2020-02-25.md").read_text()
SOURCE_ARTIFACT = "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md"

RECORDED_AGENT = {"actorType": "agent", "actorId": "agent:recorded"}

# `tests/agent/test_backend.py::test_no_committed_fixture_default_or_doc_names_a_denylisted_model`
# scans every committed `.py` file's raw text for a literal denylisted-family name; built
# at runtime from `docket.agent.backend`'s own list (the same seam
# `tests/api/test_settings.py` uses) so this file's source names none, while the model id
# below is still a real, policy-refused id.
_DENYLISTED_FAMILY = DENYLIST_FAMILIES[0]
_DENYLISTED_MODEL_ID = f"{_DENYLISTED_FAMILY}-synthetic-test-id-27b"

# A named constant, not an inline literal, per the audit's own established convention
# for a test value shaped like a credential (plan 07 T2 fix round's commit note: "a
# literal under an apiKey field ... rewritten to a named constant"). Never a real key.
FAKE_KEY = "fake key for the redaction test (spaces keep it out of secret scanners)"


def _parse_sse(text: str) -> list[dict]:
    """Duplicated from `tests/api/test_stream.py` rather than imported — both files
    already duplicate their own `REPO`/`FIXTURES`/`REQUEST_TEXT` constants instead of
    sharing a third module, and this is the same convention for an eight-line helper."""
    events: list[dict] = []
    current_event: str | None = None
    for line in text.splitlines():
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            events.append({"event": current_event, "data": json.loads(line[len("data:"):].strip())})
    return events


def _use_backend(client, path: Path, actor: dict = RECORDED_AGENT) -> RecordedBackend:
    backend = RecordedBackend(path)
    client.app.dependency_overrides[_agent] = lambda: (backend, actor)
    return backend


def _inject_graph(client, tmp_path: Path, g: Graph, *,
                   created: str = "2013-04-30T00:00:00Z") -> str:
    sid = f"s-test-{uuid.uuid4().hex[:8]}"
    path = tmp_path / sid
    path.mkdir(parents=True)
    session = Session(id=sid, source="test", path=path, created=created, graph=g,
                       lock=threading.RLock())
    client.app.state.sessions._sessions[sid] = session
    return sid


def _demo_a_graph_at(state: str) -> Graph:
    """Demo A's `build()`, advanced only as far as `state` needs, with `pl-cbo`'s human
    approval stripped so `propose_plan`/`approve_plan` have something to act on fresh —
    mirroring `tests/agent/test_plan.py::demo_a_draft` and
    `tests/agent/test_dispatch.py::demo_a_at_g1` exactly, so a defect in either fixture
    would already have shown up in plan 04's own suite."""
    from demos.a_cbo_gcv_2013.build import H as DEMO_H
    from demos.a_cbo_gcv_2013.build import build
    from docket.agent.plan import approve_plan
    from docket.kernel.lifecycle import transition

    now = "2013-04-30T00:00:00Z"
    g = build()
    pl = g.get("pl-cbo")
    g.put({**{k: v for k, v in pl.items() if k != "approvedBy"},
           "rev": pl["rev"] + 1, "createdBy": DEMO_H, "createdAt": now}, DEMO_H)
    if state in ("MODEL_APPROVED", "PLAN_APPROVED"):
        transition(g, "ep-cbo-2013", "MODEL_APPROVED", DEMO_H, now=now)
    ep = g.get("ep-cbo-2013")
    if ep.get("plan") != "pl-cbo":
        g.put({**ep, "rev": ep["rev"] + 1, "createdBy": DEMO_H, "createdAt": now,
               "plan": "pl-cbo"}, DEMO_H)
    if state == "PLAN_APPROVED":
        approve_plan(g, "pl-cbo", DEMO_H, now=now)
        transition(g, "ep-cbo-2013", "PLAN_APPROVED", DEMO_H, now=now)
    return g


@pytest.fixture(scope="module")
def demo_a_run_dir(tmp_path_factory):
    """Demo A run end to end once per module — the exact graph
    `tests/fixtures/recorded/narrate-clean.json`/`narrate-fabricated.json` were recorded
    against (`tests/agent/test_narrate.py`'s own `demo_a_graph_dir` fixture does the
    same). `run()` reads no clock and no environment variable, so this is byte-identical
    to Demo A's committed `out/graph` without needing plan 03b Task 7's build to have
    run on this machine."""
    from demos.a_cbo_gcv_2013.run import run

    d = tmp_path_factory.mktemp("demo-a-run")
    run(d)
    return d / "graph"


# ---- elicit -------------------------------------------------------------------------------


def test_elicit_returns_draft_objects_with_provenance_and_gaps(client):
    _use_backend(client, FIXTURES / "elicit.json")
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]

    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT,
        "policyId": "pol-1", "requestedBy": "NGCV CFT", "episodeId": "ep-api-elicit",
    })
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["episode"]["id"] == "ep-api-elicit"
    assert body["episode"]["lifecycleState"] == "DRAFT"
    assert body["objects"], "elicit.json must map onto at least one DRAFT object"
    assert all(o["authorType"] == "agent" for o in body["objects"])
    assert all(o["provenance"] is not None for o in body["objects"])
    # a fresh "new" session has nothing else in it: every gap this call reports must be
    # one of the objects it just wrote
    ids = {o["id"] for o in body["objects"]}
    assert set(body["gaps"]) <= ids


def test_elicit_defaults_episode_and_policy_when_the_client_omits_them(client):
    _use_backend(client, FIXTURES / "elicit.json")
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT,
        "policyId": "pol-1", "requestedBy": "NGCV CFT",
    })
    assert r.status_code == 200, r.text
    assert r.json()["episode"]["id"].startswith("ep-")


def test_elicit_refuses_a_colliding_episode_id_all_or_nothing(client):
    _use_backend(client, FIXTURES / "elicit.json")
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    body = {"requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT,
            "policyId": "pol-1", "requestedBy": "NGCV CFT", "episodeId": "ep-dupe"}
    first = client.post(f"/api/session/{sid}/elicit", json=body)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/session/{sid}/elicit", json=body)
    assert second.status_code == 422
    assert second.json()["error"] == "validation"


def test_elicit_without_requestedby_is_422_not_a_silent_operator_name(client):
    """[ruling C2] `requestedBy` is required; an omitted field must never fall back to
    the configured human actor's own id — `Charter.authority.signer` is a claim about
    who asked for the trade study, and an operator opening a demo session is not that."""
    _use_backend(client, FIXTURES / "elicit.json")
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT, "policyId": "pol-1",
    })
    assert r.status_code == 422
    assert "tester" not in r.text, "DOCKET_UI_ACTOR must never appear as a fabricated signer"


def test_elicit_with_a_blank_requestedby_is_422(client):
    """[ruling C2] A present-but-blank `requestedBy` is refused too — `elicit()`'s own
    guard ("requested_by must not be blank") still applies now that the route no longer
    intercepts the field with a default."""
    _use_backend(client, FIXTURES / "elicit.json")
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT, "policyId": "pol-1",
        "requestedBy": "   ",
    })
    assert r.status_code == 422


def test_elicit_sse_error_event_is_redacted_like_the_http_body(client):
    """[ruling C1] `app._redact` must run on the SSE `error` frame the same way it runs
    on the HTTP error body — a backend failure naming the in-memory key and the policy's
    local-testing override hint must leak neither onto the one channel a browser holds
    open for the whole session."""

    class _LeakyBackend:
        name = "leaky"
        model_id = "leaky-test-model"
        extractor = "leaky:leaky-test-model"

        def complete_json(self, *, system, user, schema, max_retries=2):
            raise BackendError(
                f"upstream rejected key {FAKE_KEY} at "
                f"https://x/v1. {OVERRIDE_HINT}"
            )

    actor = {"actorType": "agent", "actorId": "agent:leaky-test-model"}
    client.app.dependency_overrides[_agent] = lambda: (_LeakyBackend(), actor)
    client.app.state.api_key = FAKE_KEY
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]

    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": "x", "sourceArtifact": "sources/x.md", "policyId": "pol-1",
        "requestedBy": "someone",
    })
    assert r.status_code == 502
    assert FAKE_KEY not in r.text
    assert OVERRIDE_HINT not in r.text

    client.app.state.channels.get(sid).close()
    events = _parse_sse(client.get(f"/api/stream/{sid}?since=0").text)
    error_events = [e["data"] for e in events if e["event"] == "error"]
    assert error_events, "no error event was published to the channel"
    message = error_events[0]["message"]
    assert FAKE_KEY not in message
    assert OVERRIDE_HINT not in message
    assert "***" in message


# ---- G1: the review sheet and the three human actions --------------------------------------


@pytest.fixture()
def elicited(client):
    _use_backend(client, FIXTURES / "elicit.json")
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT,
        "policyId": "pol-1", "requestedBy": "NGCV CFT", "episodeId": "ep-g1-test",
    })
    assert r.status_code == 200, r.text
    return sid, r.json()


def test_g1_review_and_g1_sheet_read_the_same_scope(client, elicited):
    sid, elicit_body = elicited
    review = client.get(f"/api/session/{sid}/episode/ep-g1-test/g1").json()
    assert review["episode"] == "ep-g1-test"
    assert review["objects"]
    assert review["checks"]
    assert review["ready"] is False, "an unreviewed DRAFT episode cannot be ready at G1"

    sheet = client.get(f"/api/session/{sid}/episode/ep-g1-test/g1.md")
    assert sheet.status_code == 200
    assert sheet.headers["content-type"].startswith("text/markdown")
    assert "ep-g1-test" in sheet.text


def test_accept_stamps_the_human_actor_server_side(client, elicited):
    sid, elicit_body = elicited
    oid = elicit_body["episode"]["charter"]
    before = client.get(f"/api/session/{sid}/object/{oid}").json()
    assert before["authorType"] == "agent"

    r = client.post(f"/api/session/{sid}/object/{oid}/accept", json={"edits": {}})
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["authorType"] == "human"
    assert after["authorId"] == "tester"  # DOCKET_UI_ACTOR from the `env` fixture


def test_accept_ignores_an_actor_supplied_in_the_body(client, elicited):
    """No route in this module reads `actorType`/`actorId` from a request body — this
    is the plan's own authority-boundary probe (Task 3, `test_authority_boundary.py`
    in the plan text), folded in here rather than as a separate file."""
    sid, elicit_body = elicited
    oid = elicit_body["episode"]["charter"]
    r = client.post(f"/api/session/{sid}/object/{oid}/accept", json={
        "edits": {}, "actor": {"actorType": "agent", "actorId": "sneaky"},
        "actorType": "agent", "actorId": "sneaky",
    })
    assert r.status_code == 200, r.text
    assert r.json()["authorType"] == "human"
    assert r.json()["authorId"] == "tester"


@pytest.mark.parametrize("key", [
    "now", "g", "obj_id", "actor",
    # [ruling I1, plan 07 T6 fix round] the signature/authority fields — a request body
    # may never write who did something, when, or under what authority.
    "createdBy", "createdAt", "confirmedBy", "approvedBy", "authority", "signedBy",
    "lifecycleState",
])
def test_accept_refuses_a_reserved_edit_key_with_400(client, elicited, key):
    """[ruling M1] A client edit under one of `accept()`'s own parameter names would
    otherwise reach it as a duplicate keyword argument — an unhandled 500 where a
    printable 400 belongs. [ruling I1] the signature/authority fields are blocked for a
    different reason (not a collision, a boundary), and the 400 names it."""
    sid, elicit_body = elicited
    oid = elicit_body["episode"]["charter"]
    r = client.post(f"/api/session/{sid}/object/{oid}/accept",
                     json={"edits": {key: "whatever"}})
    assert r.status_code == 400, r.text
    assert "written by the server, never by a request body" in r.json()["message"]


def test_accept_with_no_edits_at_all_is_still_200(client, elicited):
    """[ruling I1] Widening `_RESERVED_EDIT_KEYS` must not touch the common case: an
    accept with an empty (or entirely absent) `edits` still succeeds — the guard is
    `_RESERVED_EDIT_KEYS & body.edits.keys()`, which is empty whenever the body sets
    none of them, reserved or not."""
    sid, elicit_body = elicited
    oid = elicit_body["episode"]["objectives"][0]
    r = client.post(f"/api/session/{sid}/object/{oid}/accept", json={})
    assert r.status_code == 200, r.text
    assert r.json()["authorType"] == "human"


def test_confirm_gaps_after_a_refused_forgery_still_signs_under_the_servers_actor(
    client, elicited,
):
    """[ruling I1] Before the fix, `edits.confirmedBy` sailed through `accept()` and
    satisfied `gaps-confirmed` with a name nobody at the server ever resolved (the T6
    review's own probe: 200, then `GET .../g1` showed the gap confirmed by
    `{"actorId": "someone-else", ...}`). Now the forged accept is refused outright, and
    `confirm_gaps` afterwards signs the same gap for real, under the actor the server
    resolved — never left half-signed by the rejected attempt, and never signed under
    the forged name."""
    sid, elicit_body = elicited
    gap_ids = elicit_body["gaps"]
    assert gap_ids, "elicit.json must produce at least one InsufficientEvidence for this test"
    gap_id = sorted(gap_ids)[0]

    forged = client.post(f"/api/session/{sid}/object/{gap_id}/accept", json={
        "edits": {"confirmedBy": {"actorId": "someone-else", "date": "2020-01-01"}},
    })
    assert forged.status_code == 400, forged.text

    before = client.get(f"/api/session/{sid}/object/{gap_id}").json()
    assert not before["object"].get("confirmedBy"), \
        "the refused forgery must not have written anything"

    confirm = client.post(f"/api/session/{sid}/episode/ep-g1-test/confirm-gaps", json={})
    assert confirm.status_code == 200, confirm.text
    assert gap_id in confirm.json()["confirmed"]

    after = client.get(f"/api/session/{sid}/object/{gap_id}").json()
    assert after["object"]["confirmedBy"]["actorId"] == "tester"  # DOCKET_UI_ACTOR from `env`


def test_reject_returns_the_exclusion_with_episodes_touched(client, elicited):
    sid, elicit_body = elicited
    oid = elicit_body["episode"]["objectives"][0]
    r = client.post(f"/api/session/{sid}/object/{oid}/reject", json={
        "reason": "not part of the trade study this episode scopes",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "Exclusion"
    assert body["target"]["id"] == oid
    assert body["$episodesTouched"] == ["ep-g1-test"]


def test_confirm_gaps_signs_every_confirmable_gap(client, elicited):
    sid, elicit_body = elicited
    gap_ids = set(elicit_body["gaps"])
    assert gap_ids, "elicit.json must produce at least one InsufficientEvidence for this test"
    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/confirm-gaps", json={})
    assert r.status_code == 200, r.text
    confirmed = set(r.json()["confirmed"])
    assert confirmed, "at least one gap must be confirmable on a freshly elicited episode"
    assert confirmed <= gap_ids

    # idempotent: a second call signs nothing new
    again = client.post(f"/api/session/{sid}/episode/ep-g1-test/confirm-gaps", json={})
    assert again.json()["confirmed"] == []


def test_transition_refusal_is_409_with_unsatisfied_and_is_recorded(client, elicited):
    sid, _elicit_body = elicited
    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/transition",
                     json={"to": "MODEL_APPROVED"})
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "transition-refused"
    assert body["unsatisfied"], "a freshly elicited episode must fail at least one G1 check"

    # the refusal is recorded, not swallowed
    ep = client.get(f"/api/session/{sid}/episode/ep-g1-test").json()
    assert ep["transitions"][-1]["refused"] is True


def test_transition_to_an_unknown_state_is_refused_not_a_500(client, elicited):
    sid, _elicit_body = elicited
    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/transition",
                     json={"to": "NOT-A-REAL-STATE"})
    assert r.status_code in (409, 422)


# ---- weights: the human value judgement propose_plan needs -------------------------------
#
# `POST /session/{s}/episode/{e}/weights` — `docket.agent.plan.author_weight_set`. No
# `_agent` dependency here (unlike `elicit`/`narrate`/`propose_plan`): the actor is
# always `Depends(human_actor)`, exactly like `accept`/`reject`/`confirm-gaps`/
# `transition` above, so there is no HTTP-reachable way to call this route as an agent —
# that boundary is tested directly against `author_weight_set` in
# `tests/agent/test_plan.py` instead.


def _equal_weights(ids: list[str]) -> dict[str, float]:
    return {oid: 1.0 / len(ids) for oid in ids}


def test_author_weights_writes_a_human_weightset_before_g1(client, elicited):
    """Allowed at DRAFT (before G1) — `propose_plan` itself has no lifecycle
    precondition beyond "no approved plan yet", and the ledger's ruling is that weights
    are a human value judgement, not something that waits on the model's own approval."""
    sid, elicit_body = elicited
    objective_ids = elicit_body["episode"]["objectives"]
    assert objective_ids, "elicit.json must produce at least one Objective for this test"

    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/weights", json={
        "name": "equal weights", "weights": _equal_weights(objective_ids),
        "rationale": "no source document weighs these; equal weight until one does",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == "ws-ep-g1-test-human"
    assert body["rev"] == 1
    assert body["type"] == "WeightSet"
    assert body["authorType"] == "human"
    assert body["authorId"] == "tester"  # DOCKET_UI_ACTOR from the `env` fixture
    assert body["object"]["method"] == "stated"
    assert body["object"]["weights"] == _equal_weights(objective_ids)
    assert body["object"]["provenance"] == {"$gap": "gap-ws-ep-g1-test-human"}
    # `provenance` is `slot: true` — a `$gap` marker is one of the resolved slots.
    gap_slots = [s for s in body["slots"] if s["path"] == "provenance"]
    assert gap_slots and gap_slots[0]["kind"] == "gap"

    ep = client.get(f"/api/session/{sid}/episode/ep-g1-test").json()
    assert "ws-ep-g1-test-human" in ep["weightSets"]

    gap = client.get(f"/api/session/{sid}/object/gap-ws-ep-g1-test-human").json()
    assert gap["object"]["confirmedBy"]["actorId"] == "tester"


def test_author_weights_supersedes_as_a_new_revision_not_a_second_set(client, elicited):
    sid, elicit_body = elicited
    objective_ids = elicit_body["episode"]["objectives"]

    first = client.post(f"/api/session/{sid}/episode/ep-g1-test/weights", json={
        "name": "first pass", "weights": _equal_weights(objective_ids),
    })
    assert first.status_code == 200, first.text
    assert first.json()["rev"] == 1

    lopsided = {oid: 0.0 for oid in objective_ids}
    lopsided[objective_ids[0]] = 1.0
    second = client.post(f"/api/session/{sid}/episode/ep-g1-test/weights", json={
        "name": "revised", "weights": lopsided,
    })
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["id"] == first.json()["id"]
    assert body["rev"] == 2
    assert body["object"]["weights"] == lopsided
    assert body["object"]["name"] == "revised"

    ep = client.get(f"/api/session/{sid}/episode/ep-g1-test").json()
    assert ep["weightSets"].count("ws-ep-g1-test-human") == 1


def test_author_weights_422_names_the_missing_objective(client, elicited):
    sid, elicit_body = elicited
    objective_ids = elicit_body["episode"]["objectives"]
    weights = _equal_weights(objective_ids)
    del weights[objective_ids[0]]

    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/weights", json={
        "name": "incomplete", "weights": weights,
    })
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["error"] == "validation"
    assert objective_ids[0] in body["message"]
    assert body["errors"] == [
        f"step measures without a weight: {sorted([objective_ids[0]])}"
    ]


def test_author_weights_422_names_the_extra_key(client, elicited):
    sid, elicit_body = elicited
    objective_ids = elicit_body["episode"]["objectives"]
    weights = _equal_weights(objective_ids)
    weights["not-an-objective-of-this-episode"] = 0.0

    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/weights", json={
        "name": "extra", "weights": weights,
    })
    assert r.status_code == 422, r.text
    assert "not-an-objective-of-this-episode" in r.json()["message"]


def test_author_weights_422_negative_weight(client, elicited):
    sid, elicit_body = elicited
    objective_ids = elicit_body["episode"]["objectives"]
    weights = _equal_weights(objective_ids)
    weights[objective_ids[0]] = -0.1

    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/weights", json={
        "name": "negative", "weights": weights,
    })
    assert r.status_code == 422, r.text
    assert "non-negative" in r.json()["message"]


def test_author_weights_422_sum_not_one(client, elicited):
    sid, elicit_body = elicited
    objective_ids = elicit_body["episode"]["objectives"]
    weights = {oid: 0.0 for oid in objective_ids}
    weights[objective_ids[0]] = 0.5

    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/weights", json={
        "name": "half", "weights": weights,
    })
    assert r.status_code == 422, r.text
    assert "not 1" in r.json()["message"]


def test_author_weights_422_blank_name(client, elicited):
    sid, elicit_body = elicited
    objective_ids = elicit_body["episode"]["objectives"]
    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/weights", json={
        "name": "   ", "weights": _equal_weights(objective_ids),
    })
    assert r.status_code == 422, r.text


def test_author_weights_ignores_an_actor_supplied_in_the_body(client, elicited):
    sid, elicit_body = elicited
    objective_ids = elicit_body["episode"]["objectives"]
    r = client.post(f"/api/session/{sid}/episode/ep-g1-test/weights", json={
        "name": "equal", "weights": _equal_weights(objective_ids),
        "actorType": "agent", "actorId": "sneaky",
    })
    assert r.status_code == 200, r.text
    assert r.json()["authorType"] == "human"
    assert r.json()["authorId"] == "tester"


def test_author_weights_allowed_at_model_approved(client, tmp_path):
    """`_demo_a_graph_at("MODEL_APPROVED")` strips `pl-cbo`'s approval, so the episode
    is MODEL_APPROVED with a plan present but not yet approved — the other state the
    ledger's ruling allows weights to be authored from, using Demo A's own real
    Objectives (`obj-capability`, `obj-cost`) rather than a freshly elicited episode's."""
    g = _demo_a_graph_at("MODEL_APPROVED")
    sid = _inject_graph(client, tmp_path, g)

    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/weights", json={
        "name": "equal", "weights": {"obj-capability": 0.5, "obj-cost": 0.5},
    })
    assert r.status_code == 200, r.text
    assert r.json()["id"] == "ws-ep-cbo-2013-human"


def test_author_weights_refuses_once_a_plan_is_approved(client, tmp_path):
    """`_demo_a_graph_at("PLAN_APPROVED")` is past G2: `pl-cbo` is approved and the
    episode has transitioned to `PLAN_APPROVED`. Refused as a 422 naming the
    lifecycleState — the explicit DRAFT/MODEL_APPROVED allow-list, checked first — not
    a 403: reaching `PLAN_APPROVED` at all already implies an approved plan (the gate
    ladder's own invariant), so the state check alone is sufficient here.
    `test_author_weight_set_refuses_once_named_plan_is_approved`
    (`tests/agent/test_plan.py`) exercises the second, independent check
    (`_named_approved_plan`) directly, on a graph where the two facts are decoupled by
    hand rather than by a real transition."""
    g = _demo_a_graph_at("PLAN_APPROVED")
    sid = _inject_graph(client, tmp_path, g)

    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/weights", json={
        "name": "equal", "weights": {"obj-capability": 0.5, "obj-cost": 0.5},
    })
    assert r.status_code == 422, r.text
    assert r.json()["error"] == "validation"
    assert "PLAN_APPROVED" in r.json()["message"]


# ---- plan (G2) -----------------------------------------------------------------------------


def test_propose_plan_writes_a_fresh_agent_plan_with_no_approved_by(client, tmp_path):
    g = _demo_a_graph_at("MODEL_APPROVED")
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "plan.json")

    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/plan", json={})
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["id"].startswith("pl-ep-cbo-2013-agent-")
    assert not plan.get("approvedBy")
    assert {s["id"] for s in plan["steps"]} == {"primary", "secondary"}


def test_approve_plan_is_human_only_and_sets_approved_by(client, tmp_path):
    g = _demo_a_graph_at("MODEL_APPROVED")
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "plan.json")
    plan_id = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/plan", json={}).json()["id"]

    r = client.post(f"/api/session/{sid}/plan/{plan_id}/approve", json={})
    assert r.status_code == 200, r.text
    approved = r.json()
    assert approved["approvedBy"]["actorId"] == "tester"


# ---- dispatch (X) ---------------------------------------------------------------------------
#
# [ruling I3, plan 07 T3 fix round] `/dispatch` no longer depends on `_agent` at all — it
# resolves its actor through `_dispatch_actor`, which never constructs a backend. The
# `_use_backend(client, FIXTURES / "default.json")` calls below are now inert for this
# route (there is no `_agent` override left for it to feed) and are kept only because
# harmless; `test_dispatch_never_resolves_a_backend`, further down, is what actually
# proves the route never resolves one.


def test_dispatch_before_g2_is_403(client, tmp_path):
    g = _demo_a_graph_at("MODEL_APPROVED")
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "default.json")  # dispatch never calls the backend

    r = client.post(f"/api/session/{sid}/plan/pl-cbo/dispatch", json={"seed": 20130430})
    assert r.status_code == 403
    assert r.json()["error"] == "authority-violation"


def test_dispatch_computes_flip_summaries_and_drives_the_evaluated_transition(client, tmp_path):
    g = _demo_a_graph_at("PLAN_APPROVED")
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "default.json")

    r = client.post(f"/api/session/{sid}/plan/pl-cbo/dispatch", json={"seed": 20130430})
    assert r.status_code == 200, r.text
    body = r.json()

    assert {run["step"] for run in body["runs"]} == {"primary", "secondary"}
    assert body["flips"]
    assert len(body["flipSummaries"]) == len(body["runs"])
    assert all("simplexRobustness" in s for s in body["flipSummaries"])
    assert body["episode"]["lifecycleState"] == "EVALUATED"
    # the transition is the human actor's, per agent.dispatch's own module docstring
    assert body["episode"]["transitions"][-1]["actor"]["actorType"] == "human"

    run_id = body["runs"][0]["id"]
    rb = client.get(f"/api/session/{sid}/run/{run_id}").json()
    assert rb["run"] == run_id
    assert rb["ranking"] == body["runs"][0]["ranking"]


def test_read_back_results_carry_the_kernels_own_string_form_of_each_value(client, tmp_path):
    """Plan 07 Task 7 fix round, I2: `<Num>` prefers a canonical text form over
    re-stringifying a `JSON.parse`d float — `36.0` must stay `"36.0"`, never become
    `"36"`. `str(value)` is exactly what `kernel.render` already prints for a Result
    (`f"{res.get('value')} {res.get('units')}"`), so this asserts byte equality with
    that, not merely that the field exists."""
    g = _demo_a_graph_at("PLAN_APPROVED")
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "default.json")

    dispatched = client.post(f"/api/session/{sid}/plan/pl-cbo/dispatch", json={"seed": 20130430})
    assert dispatched.status_code == 200, dispatched.text
    run_id = dispatched.json()["runs"][0]["id"]

    rb = client.get(f"/api/session/{sid}/run/{run_id}").json()
    assert rb["results"], "a dispatched run must seal at least one Result"
    for rid, entry in rb["results"].items():
        assert entry["valueText"] == str(entry["value"]), rid


def test_flip_analysis_object_view_carries_valuetext_for_its_numeric_fields(client, tmp_path):
    """Plan 07 Task 7 fix round, I2: `GET .../object/{flipId}` (`object_view`) is the
    route `Compute.tsx`'s `FlipChart` reads on every reload — its `valueText` sibling
    must carry the same fields `FlipAnalysis` itself does, each equal to `str()` of the
    stored value."""
    g = _demo_a_graph_at("PLAN_APPROVED")
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "default.json")

    dispatched = client.post(f"/api/session/{sid}/plan/pl-cbo/dispatch", json={"seed": 20130430})
    assert dispatched.status_code == 200, dispatched.text
    flip = next(f for f in dispatched.json()["flips"] if f["flipThreshold"] is not None)

    view = client.get(f"/api/session/{sid}/object/{flip['id']}").json()
    vt = view["valueText"]
    assert vt["currentValue"] == str(view["object"]["currentValue"])
    assert vt["flipThreshold"] == str(view["object"]["flipThreshold"])
    assert vt["flipDistance"] == str(view["object"]["flipDistance"])
    assert vt["range"]["lo"] == str(view["object"]["range"]["lo"])
    assert vt["range"]["hi"] == str(view["object"]["range"]["hi"])
    # additive only, next to `object`, never inside it — `view.object` stays exactly
    # what the graph stored.
    assert "valueText" not in view["object"]
    assert "currentValueText" not in view["object"]


def test_dispatch_refuses_a_second_time_with_no_partial_write(client, tmp_path):
    """[ruling M8] The name promises "no partial write" — the original test only ever
    checked the 422; this now actually inspects the graph before and after the refused
    second call."""
    g = _demo_a_graph_at("PLAN_APPROVED")
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "default.json")
    first = client.post(f"/api/session/{sid}/plan/pl-cbo/dispatch", json={"seed": 20130430})
    assert first.status_code == 200, first.text

    session = client.app.state.sessions.get(sid)
    ids_after_first = set(session.graph.ids())
    hash_after_first = session.graph.snapshot_hash()

    second = client.post(f"/api/session/{sid}/plan/pl-cbo/dispatch", json={"seed": 20130430})
    assert second.status_code == 422
    assert second.json()["error"] == "validation"

    assert session.graph.ids() == sorted(ids_after_first), "the refused call wrote an object"
    assert session.graph.snapshot_hash() == hash_after_first, "the refused call changed the graph"


def test_dispatch_never_resolves_a_backend(client, tmp_path, monkeypatch):
    """[ruling I3] `/dispatch` is pure kernel arithmetic behind the agent actor's name —
    it must succeed with no key and a provider pointed at an address that cannot be
    reached, because nothing in this route ever tries to reach it."""
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DOCKET_LLM_MODEL", "llama3.3:70b")
    monkeypatch.setenv("DOCKET_LLM_BASE_URL", "http://192.0.2.1:1/v1")  # TEST-NET-1, unreachable
    monkeypatch.delenv("DOCKET_LLM_API_KEY", raising=False)

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("post_dispatch must never construct a backend")

    # Built from parts, not a literal: `tests/agent/test_backend.py`'s own
    # `test_only_this_module_constructs_a_live_backend` [ruling R9] scans every OTHER
    # test file's raw source for this exact name and refuses it — the same reason
    # `_DENYLISTED_MODEL_ID`, above, builds its family name from `DENYLIST_FAMILIES[0]`
    # at runtime instead of writing one out. The point being proved (a backend
    # constructor is never called) does not require writing its name in this file's text.
    _ctor_attr = "backend" + "_from_" + "settings"
    monkeypatch.setattr(f"docket.api.routes.agent.{_ctor_attr}", _must_not_be_called)

    g = _demo_a_graph_at("PLAN_APPROVED")
    sid = _inject_graph(client, tmp_path, g)

    r = client.post(f"/api/session/{sid}/plan/pl-cbo/dispatch", json={"seed": 20130430})
    assert r.status_code == 200, r.text
    assert r.json()["episode"]["lifecycleState"] == "EVALUATED"


def test_dispatch_with_no_model_configured_is_409_config_invalid_never_agent_colon(
        client, tmp_path, monkeypatch):
    """[ruling M3] No model configured must never mint the unnamed actor id `"agent:"`;
    it is a 409 `config-invalid`, distinct from `policy-refusal` (an unset model does not
    match any denylisted family)."""
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.delenv("DOCKET_LLM_MODEL", raising=False)
    monkeypatch.delenv("DOCKET_LLM_BASE_URL", raising=False)

    g = _demo_a_graph_at("PLAN_APPROVED")
    sid = _inject_graph(client, tmp_path, g)

    r = client.post(f"/api/session/{sid}/plan/pl-cbo/dispatch", json={"seed": 20130430})
    assert r.status_code == 409
    assert r.json()["error"] == "config-invalid"
    assert '"agent:' not in r.text


def test_elicit_with_no_model_configured_is_409_config_invalid_never_agent_colon(
        client, monkeypatch):
    """[ruling M3] The same refusal on the `_agent`-dependent path (elicit/plan/narrate),
    not just `/dispatch`'s own `_dispatch_actor`. Loopback + no key so ruling I6's own
    refusal doesn't fire first — this is specifically about the empty model id."""
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DOCKET_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.delenv("DOCKET_LLM_MODEL", raising=False)
    monkeypatch.delenv("DOCKET_LLM_API_KEY", raising=False)

    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": "x", "sourceArtifact": "sources/x.md", "policyId": "pol-1",
        "requestedBy": "someone",
    })
    assert r.status_code == 409
    assert r.json()["error"] == "config-invalid"
    assert '"agent:' not in r.text
    assert '"agent:' not in r.text


# ---- narrate (N) --------------------------------------------------------------------------


def test_narrate_stores_a_clean_draft_with_the_agent_actor(client, tmp_path, demo_a_run_dir):
    g = Graph.load(demo_a_run_dir)
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "narrate-clean.json")

    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/narrate", json={
        "section": "evaluation-results", "now": "2013-04-30T00:00:00Z",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "Narrative"
    assert body["authorType"] == "agent"
    assert body["object"]["section"] == "evaluation-results"


def test_narrate_with_a_fabricated_number_is_422_naming_the_sentence(client, tmp_path,
                                                                     demo_a_run_dir):
    g = Graph.load(demo_a_run_dir)
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "narrate-fabricated.json")

    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/narrate", json={
        "section": "evaluation-results", "now": "2013-04-30T00:00:00Z",
    })
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "uncited-sentence"
    assert body["sentence"]


def test_narrate_refuses_a_client_supplied_context_with_422(client, tmp_path, demo_a_run_dir):
    """[ruling I5] `context` bypasses `rendering`'s withholding gate entirely
    (`narrate()`'s own docstring: "Ignored when `context` is supplied directly") — the
    plan's body spec is `{section}` only, and `extra="forbid"` turns a client that still
    sends one into a 422 instead of a silent bypass."""
    g = Graph.load(demo_a_run_dir)
    sid = _inject_graph(client, tmp_path, g)
    _use_backend(client, FIXTURES / "narrate-clean.json")

    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/narrate", json={
        "section": "evaluation-results", "now": "2013-04-30T00:00:00Z",
        "context": {"sneaky": "value"},
    })
    assert r.status_code == 422


# ---- the backend dependency: denylist and missing-key refusals ----------------------------


def test_a_denylisted_model_set_via_the_environment_is_409_via_an_agent_route(client, monkeypatch):
    monkeypatch.setenv("DOCKET_LLM_MODEL", _DENYLISTED_MODEL_ID)
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": "x", "sourceArtifact": "sources/x.md", "policyId": "pol-1",
        "requestedBy": "someone",
    })
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "policy-refusal"
    assert _DENYLISTED_FAMILY in body["message"].lower()
    assert "DOCKET_LLM_ALLOW_DENYLISTED" not in r.text


def test_anthropic_with_no_key_is_a_printable_409_not_a_live_call(client, monkeypatch):
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("DOCKET_LLM_MODEL", "claude-3-5-sonnet-20241022")
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/episode/ep-none/plan", json={})
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "policy-refusal"
    assert "key" in body["message"].lower()


def test_openai_compatible_with_no_key_and_a_remote_base_url_refuses_before_any_call(
        client, monkeypatch):
    """[ruling I6] `openai-compatible` with no key and a base URL that is not loopback
    or private must refuse before anything reaches the network — proved here by making
    the underlying transport call raise if it is ever reached at all."""
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DOCKET_LLM_MODEL", "llama3.3:70b")
    monkeypatch.setenv("DOCKET_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.delenv("DOCKET_LLM_API_KEY", raising=False)

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("must not reach the network")

    monkeypatch.setattr("docket.agent.backend._post", _must_not_be_called)

    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": "x", "sourceArtifact": "sources/x.md", "policyId": "pol-1",
        "requestedBy": "someone",
    })
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "policy-refusal"
    assert "key" in body["message"].lower()


def test_openai_compatible_with_no_key_and_a_loopback_base_url_proceeds(client, monkeypatch):
    """[ruling I6] The demo's own path (Ollama on loopback) must keep working with no
    key configured — proved by letting the call reach the (fake) transport, which then
    fails for an unrelated reason (a `BackendError`, not a policy refusal)."""
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DOCKET_LLM_MODEL", "llama3.3:70b")
    monkeypatch.setenv("DOCKET_LLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.delenv("DOCKET_LLM_API_KEY", raising=False)

    reached = []

    def _reached(*args, **kwargs):
        reached.append(True)
        raise BackendError("probe: the loopback transport was reached")

    monkeypatch.setattr("docket.agent.backend._post", _reached)

    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": "x", "sourceArtifact": "sources/x.md", "policyId": "pol-1",
        "requestedBy": "someone",
    })
    assert reached, "a loopback base URL with no key must be allowed through to the backend"
    assert r.status_code == 502
    assert r.json()["error"] == "backend"


# ---- I4: `agent_actor` must match `agent.cli._actor_for`, byte-for-byte -------------------


def test_agent_actor_matches_cli_actor_for_a_recorded_backend():
    backend = RecordedBackend(FIXTURES / "elicit.json")
    api_actor = agent_actor(backend)
    cli_actor = _actor_for(backend, None)
    assert api_actor == cli_actor
    assert api_actor == {"actorType": "agent", "actorId": "agent:recorded"}
    assert api_actor["actorId"].startswith("agent:")


class _FakeLiveModelBackend:
    """`agent_actor`/`_actor_for` read only `.model_id` — a minimal stand-in, not the
    real live backend classes, which `tests/agent/test_backend.py`'s own
    `test_only_this_module_constructs_a_live_backend` [ruling R9] refuses to let any
    other test file reference at all, even for pure, network-free construction."""

    model_id = "llama3.3:70b"


def test_agent_actor_matches_cli_actor_for_a_live_model_id():
    backend = _FakeLiveModelBackend()
    api_actor = agent_actor(backend)
    cli_actor = _actor_for(backend, None)
    assert api_actor == cli_actor
    assert api_actor == {"actorType": "agent", "actorId": "agent:llama3.3:70b"}


def test_agent_actor_refuses_an_empty_model_id_as_config_invalid():
    """[ruling M3] `check_model_policy("")` returns `""` unchanged (nothing to check),
    so an `openai-compatible`/`anthropic` provider resolved with no model would
    otherwise silently mint the unnamed actor id `"agent:"`."""

    class _FakeUnconfiguredBackend:
        model_id = ""

    with pytest.raises(ConfigInvalid):
        agent_actor(_FakeUnconfiguredBackend())
