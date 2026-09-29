"""Plan 07 Task 4: the timeline, `/watch` (routed to `agent.refresh_watch`, plan 07 Task 4
follow-up), and `/refresh`.

The `/watch` fixtures below build a minimal graph directly on a fresh (`source: "new"`)
session, reusing the same object builders `tests/agent/test_refresh_watch.py` already
exercises `detect()` against, rather than depending on Demo A having (or not having) any
proposals of its own.
"""
from __future__ import annotations

from tests.agent.conftest import assumption, program
from tests.kernel.conftest import charter, drs, episode, evidence, policy, put_all


def _seed_indicator_program(session) -> str:
    """One assumption whose indicator matches new Evidence's title -> exactly one
    `indicator-detected` proposal. Mirrors `tests/agent/conftest.py`'s
    `program_with_indicator` fixture."""
    g = session.graph
    put_all(g, policy(), evidence("ev-doc"), drs(), charter(), episode())
    put_all(
        g,
        assumption("as-1", ["fuel price volatility"]),
        evidence("ev-new", title="2026 Fuel Price Volatility Outlook", createdAt="2026-09-10"),
        {**episode(), "rev": 2, "assumptions": ["as-1"], "program": "prg-4"},
        program("prg-4"),
    )
    return "prg-4"


def _seed_boundary_program(session) -> str:
    """[I1, T8 review] indicator "rice" must not fire on the "rice" hiding inside
    "Price" (no letter boundary), but must fire on a real word bounded by a
    space/string-start or a hyphen. Mirrors `tests/agent/conftest.py`'s
    `program_with_boundary_indicator` fixture."""
    g = session.graph
    put_all(g, policy(), evidence("ev-doc"), drs(), charter(), episode())
    put_all(
        g,
        assumption("as-3", ["rice"]),
        evidence("ev-steel", title="2026 Steel Price Index Update", createdAt="2026-09-10"),
        evidence("ev-rice-word", title="Rice price index, 2026", createdAt="2026-09-11"),
        evidence("ev-rice-hyphen", title="rice-yield update", createdAt="2026-09-12"),
        {**episode(), "rev": 2, "assumptions": ["as-3"], "program": "prg-6"},
        program("prg-6"),
    )
    return "prg-6"


def test_timeline_without_a_programme_is_an_empty_200(client):
    s = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.get(f"/api/session/{s}/program/none/timeline")
    assert r.status_code == 200 and r.json()["episodes"] == []


def test_timeline_with_a_real_program_lists_its_episode(client, demo_a_present):
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    r = client.get(f"/api/session/{sid}/program/prg-gcv-2013/timeline")
    assert r.status_code == 200
    b = r.json()
    assert b["program"]["id"] == "prg-gcv-2013"
    assert len(b["episodes"]) == 1
    assert b["episodes"][0]["id"] == "ep-cbo-2013"
    assert b["diffs"] == [] and b["refreshTriggers"] == []


def test_timeline_carries_timing(client, demo_b_present):
    sid = client.post("/api/session", json={"source": "demo-b"}).json()["id"]
    body = client.get(f"/api/session/{sid}/program/prg-omfv/timeline").json()
    assert body["timing"]["accreditationMonths"] == 36
    assert [e["id"] for e in body["timing"]["episodes"]][:1] == ["ep-omfv-2020-02"]


def test_timeline_without_a_programme_carries_no_timing(client):
    """The empty branch answers the same shape, with `timing: None` — a client checks one
    field either way rather than two different response shapes."""
    s = client.post("/api/session", json={"source": "new"}).json()["id"]
    assert client.get(f"/api/session/{s}/program/none/timeline").json()["timing"] is None


def test_watch_file_false_returns_proposals_with_no_envelope_and_writes_nothing(client):
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    session = client.app.state.sessions.get(sid)
    prog = _seed_indicator_program(session)
    before = len(session.graph.log())

    r = client.post(f"/api/session/{sid}/program/{prog}/watch", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["filed"] == []
    assert len(body["proposals"]) == 1
    proposal = body["proposals"][0]
    assert proposal["kind"] == "indicator-detected"
    # "Detected, not filed": no envelope on a proposal.
    assert "id" not in proposal and "rev" not in proposal and "createdBy" not in proposal

    assert len(session.graph.log()) == before  # nothing was written


def test_watch_accepts_a_missing_body(client):
    """No JSON body at all (the plain `client.post(url)` shape), not just `json={}`."""
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    session = client.app.state.sessions.get(sid)
    prog = _seed_indicator_program(session)

    r = client.post(f"/api/session/{sid}/program/{prog}/watch")
    assert r.status_code == 200
    assert r.json()["filed"] == []


def test_watch_file_true_files_with_the_human_actor_and_the_timeline_shows_it(client):
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    session = client.app.state.sessions.get(sid)
    prog = _seed_indicator_program(session)

    r = client.post(f"/api/session/{sid}/program/{prog}/watch?file=true", json={})
    assert r.status_code == 200
    body = r.json()
    assert len(body["proposals"]) == 1
    assert len(body["filed"]) == 1
    trigger_id = body["filed"][0]
    assert isinstance(trigger_id, str) and trigger_id.startswith(f"rt-{prog}-")

    timeline = client.get(f"/api/session/{sid}/program/{prog}/timeline").json()
    filed = {t["id"]: t for t in timeline["refreshTriggers"]}
    assert trigger_id in filed
    # `DOCKET_UI_ACTOR=tester` (tests/api/conftest.py's `env` fixture) — the resolved UI
    # actor, human: the agent proposes, the human files.
    assert filed[trigger_id]["createdBy"] == {"actorType": "human", "actorId": "tester"}


def test_watch_unknown_program_matches_refreshs_validation_error(client):
    """`detect()` refuses an unknown `program_id` with `ValidationError`, exactly like
    `open_refresh` does for `/refresh` (`test_refresh_requires_a_known_trigger` above) —
    both map to 422 through the same app-wide handler, so `/watch` needs no separate
    404 case of its own for a program the session's graph does not have."""
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/program/nope/watch", json={})
    assert r.status_code == 422
    assert r.json()["error"] == "validation"


def test_watch_indicator_boundary_does_not_fire_rice_inside_price(client):
    """[I1, T8 review] The boundary case through the actual route, not just the
    underlying `detect()` unit test (`tests/agent/test_refresh_watch.py`'s
    `test_indicator_match_requires_a_non_letter_boundary`)."""
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    session = client.app.state.sessions.get(sid)
    prog = _seed_boundary_program(session)

    r = client.post(f"/api/session/{sid}/program/{prog}/watch", json={})
    assert r.status_code == 200
    sources = {p["source"] for p in r.json()["proposals"] if p["kind"] == "indicator-detected"}
    assert "ev-steel" not in sources               # "2026 Steel Price Index Update" — no match
    assert {"ev-rice-word", "ev-rice-hyphen"} <= sources


def test_refresh_requires_a_known_trigger(client, demo_a_present):
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    r = client.post(f"/api/session/{sid}/program/prg-gcv-2013/refresh",
                     json={"triggerId": "trg-does-not-exist"})
    assert r.status_code == 422


def test_refresh_opens_a_successor_episode_and_marks_the_prior_suspect(
    client, demo_a_present,
):
    """`open_refresh` itself enforces the human-actor boundary
    (`AuthorityViolation` on anything else); this route only ever passes
    `config.human_actor()`, so there is no *request* shape that could smuggle an agent
    actor through it. See
    `test_refresh_refuses_a_non_human_actor_even_under_a_simulated_regression` below for
    the defense-in-depth path (a hypothetical code regression, not a client request)."""
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    session = client.app.state.sessions.get(sid)
    g = session.graph
    actor = {"actorType": "human", "actorId": "tester"}
    trigger = {
        "id": "trg-test-1", "type": "RefreshTrigger", "rev": 1,
        "createdBy": actor, "createdAt": "2024-01-01T00:00:00Z",
        "kind": "assumption-changed", "source": "test harness",
        "description": "an assumption changed, for exercising the refresh route",
        "detectedAt": "2024-01-01T00:00:00Z", "affected": ["as-nine-squad"],
    }
    g.put(trigger, actor)

    r = client.post(f"/api/session/{sid}/program/prg-gcv-2013/refresh",
                     json={"triggerId": "trg-test-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["supersedes"] == "ep-cbo-2013"
    assert body["lifecycleState"] == "DRAFT"
    assert body["sequence"] == 2

    prior = client.get(f"/api/session/{sid}/episode/ep-cbo-2013").json()
    assert prior["lifecycleState"] == "SUSPECT"

    timeline = client.get(f"/api/session/{sid}/program/prg-gcv-2013/timeline").json()
    assert len(timeline["episodes"]) == 2
    assert {ep["id"] for ep in timeline["episodes"]} == {"ep-cbo-2013", body["id"]}


def test_refresh_refuses_a_non_human_actor_even_under_a_simulated_regression(
    client, demo_a_present, monkeypatch,
):
    """Fix round 1, M5: defense in depth for the human-actor boundary, regression-tested
    rather than only demonstrated by hand. `kernel.refresh.open_refresh` itself refuses
    a non-human actor (`AuthorityViolation`) — independent of, and behind,
    `routes/program.py` only ever passing `config.human_actor()`. Monkeypatching
    `human_actor` *in this module's imported namespace* (not the client request — there
    is still no request shape that could do this) simulates a future accidental edit
    that swapped in an agent actor, and confirms the kernel's own check is what actually
    stops it, not just today's call site.
    """
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    session = client.app.state.sessions.get(sid)
    g = session.graph
    actor = {"actorType": "human", "actorId": "tester"}
    trigger = {
        "id": "trg-test-agent", "type": "RefreshTrigger", "rev": 1,
        "createdBy": actor, "createdAt": "2024-01-01T00:00:00Z",
        "kind": "assumption-changed", "source": "test harness",
        "description": "an assumption changed, for exercising the actor boundary",
        "detectedAt": "2024-01-01T00:00:00Z", "affected": ["as-nine-squad"],
    }
    g.put(trigger, actor)

    monkeypatch.setattr(
        "docket.api.routes.program.human_actor",
        lambda: {"actorType": "agent", "actorId": "sneaky"},
    )
    r = client.post(f"/api/session/{sid}/program/prg-gcv-2013/refresh",
                     json={"triggerId": "trg-test-agent"})
    assert r.status_code == 403
    assert r.json()["error"] == "authority-violation"

    # `Graph.put` validates before it mutates anything, so a refused write leaves
    # nothing behind: the prior episode's state is exactly what it was before the call.
    prior = client.get(f"/api/session/{sid}/episode/ep-cbo-2013").json()
    assert prior["lifecycleState"] == "PENDING_SIGNATURE"
