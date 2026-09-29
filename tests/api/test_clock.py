"""`GET …/clock` and `GET …/activity` — read-only, computed at request time."""
from __future__ import annotations


def _demo_a(client):
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    return sid, "ep-cbo-2013"


def test_clock_reads_demo_a_from_its_own_record(client, demo_a_present, monkeypatch):
    monkeypatch.setattr("docket.api.routes.workspace._now", lambda: "2026-09-11T00:00:00Z")
    sid, ep = _demo_a(client)
    r = client.get(f"/api/session/{sid}/episode/{ep}/clock")
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["episode"] == ep and c["openedAt"] == "2013-04-30T00:00:00Z"
    assert c["deadline"] is None and c["expectedSource"] == "default"
    assert [s["state"] for s in c["stages"]] == [
        "DRAFT", "MODEL_APPROVED", "PLAN_APPROVED", "EVALUATED", "PENDING_SIGNATURE"]
    assert c["current"]["state"] == "PENDING_SIGNATURE" and c["current"]["days"] > 4000
    assert c["tone"] == "stop"
    assert {f["kind"] for f in c["flags"]} == {"stuck", "no-deadline"}
    assert c["lastHumanAct"]["actorId"] == "shreyash"


def test_clock_is_a_read_and_writes_nothing(client, demo_a_present):
    sid, ep = _demo_a(client)
    g = client.app.state.sessions.get(sid).graph
    head = g.log()[-1]["entryHash"]
    for _ in range(3):
        assert client.get(f"/api/session/{sid}/episode/{ep}/clock").status_code == 200
    assert g.log()[-1]["entryHash"] == head


def test_clock_404s_on_an_unknown_episode(client):
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    assert client.get(f"/api/session/{sid}/episode/nope/clock").status_code == 404


def test_activity_lists_the_log_newest_first_with_layers(client, demo_a_present):
    sid, _ = _demo_a(client)
    r = client.get(f"/api/session/{sid}/activity")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert entries and entries[0]["seq"] > entries[-1]["seq"]
    assert {e["layer"] for e in entries} <= {"human", "agent", "kernel"}
    assert all(e["at"] and e["what"] for e in entries)
    kernel = [e for e in entries if e["layer"] == "kernel"]
    assert any(e["what"].startswith("rendered the package") for e in kernel)


def test_activity_can_be_filtered_to_one_episodes_reach(client, demo_a_present):
    """`?episode=` keeps the entries whose object the episode reaches, plus the episode
    itself — the filter the Activity view's "This episode only" toggle sends. Demo A's
    store holds objects outside that reach (its two rendered packages point AT the
    episode, and nothing points back), so the filtered log is a proper subset."""
    sid, ep = _demo_a(client)
    whole = client.get(f"/api/session/{sid}/activity").json()["entries"]
    filtered = client.get(f"/api/session/{sid}/activity?episode={ep}").json()["entries"]
    assert filtered and len(filtered) < len(whole)
    assert {e["seq"] for e in filtered} < {e["seq"] for e in whole}
    assert any(e["id"] == ep for e in filtered)
    assert filtered == [e for e in whole if e["seq"] in {f["seq"] for f in filtered}]


def test_activity_ignores_an_episode_that_is_not_in_the_record(client, demo_a_present):
    """An unknown (or empty) `?episode=` filters nothing rather than everything: a log
    with no rows would read as "nothing has happened", which is a claim about the record
    and not about the parameter."""
    sid, _ = _demo_a(client)
    whole = client.get(f"/api/session/{sid}/activity").json()["entries"]
    for query in ("?episode=ep-not-a-thing", "?episode="):
        assert client.get(f"/api/session/{sid}/activity{query}").json()["entries"] == whole
