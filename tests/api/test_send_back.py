"""`POST …/send-back` — the signer's named return, a human write through the store."""
from __future__ import annotations


def _demo_a(client):
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    return sid, "ep-cbo-2013"


def test_send_back_files_a_signer_return_trigger_and_the_queue_shows_it(client, demo_a_present):
    sid, ep = _demo_a(client)
    r = client.post(f"/api/session/{sid}/episode/{ep}/send-back",
                    json={"reason": "the conditions and stop rules are not specific enough"})
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["type"] == "RefreshTrigger" and view["authorType"] == "human"
    assert view["authorId"] == "tester"
    assert view["object"]["kind"] == "signer-return" and view["object"]["affected"] == [ep]
    assert view["object"]["description"].startswith("the conditions")

    q = client.get(f"/api/session/{sid}/episode/{ep}/needs").json()
    sent = [i for i in q["items"] if i["kind"] == "sent-back"]
    assert len(sent) == 1
    assert sent[0]["text"] == ("Sent back by tester: the conditions and stop rules are "
                               "not specific enough")
    timeline = client.get(f"/api/session/{sid}/program/prg-gcv-2013/timeline").json()
    assert view["id"] in {t["id"] for t in timeline["refreshTriggers"]}


def test_send_back_is_persisted_and_history_is_unchanged(client, demo_a_present):
    from docket.store import Graph

    sid, ep = _demo_a(client)
    session = client.app.state.sessions.get(sid)
    before = session.graph.get(ep)
    client.post(f"/api/session/{sid}/episode/{ep}/send-back", json={"reason": "r"})
    assert session.graph.get(ep) == before             # the episode is untouched
    reloaded = Graph.load(session.path / "graph")
    assert reloaded.has("rt-return-ep-cbo-2013-1")


def test_a_second_send_back_gets_its_own_id(client, demo_a_present):
    """Nothing is rewritten: the first return stays exactly where it was filed."""
    sid, ep = _demo_a(client)
    first = client.post(f"/api/session/{sid}/episode/{ep}/send-back",
                        json={"reason": "the stop rules are not specific enough"}).json()
    second = client.post(f"/api/session/{sid}/episode/{ep}/send-back",
                         json={"reason": "and neither is the cost condition"}).json()
    assert first["id"] == "rt-return-ep-cbo-2013-1"
    assert second["id"] == "rt-return-ep-cbo-2013-2"
    program = client.get(f"/api/session/{sid}/program/prg-gcv-2013/timeline").json()["program"]
    assert program["refreshTriggers"] == [first["id"], second["id"]]
    q = client.get(f"/api/session/{sid}/episode/{ep}/needs").json()
    assert [i["objectId"] for i in q["items"] if i["kind"] == "sent-back"] == \
        [first["id"], second["id"]]


def test_send_back_refuses_a_blank_reason_with_422(client, demo_a_present):
    sid, ep = _demo_a(client)
    r = client.post(f"/api/session/{sid}/episode/{ep}/send-back", json={"reason": "  "})
    assert r.status_code == 422


def test_send_back_on_an_unknown_episode_is_not_found(client, demo_a_present):
    sid, _ = _demo_a(client)
    r = client.post(f"/api/session/{sid}/episode/nope/send-back", json={"reason": "r"})
    assert r.status_code == 404


def test_send_back_refuses_an_episode_not_awaiting_a_signature_with_409(client, demo_b_present):
    sid = client.post("/api/session", json={"source": "demo-b"}).json()["id"]
    r = client.post(f"/api/session/{sid}/episode/ep-omfv-2020-02-r5/send-back",
                    json={"reason": "r"})
    assert r.status_code == 409
    assert r.json()["error"] == "not-pending-signature"


def test_send_back_refuses_a_non_human_actor_even_under_a_simulated_regression(
    client, demo_a_present, monkeypatch,
):
    sid, ep = _demo_a(client)
    monkeypatch.setattr("docket.api.routes.workspace.human_actor",
                        lambda: {"actorType": "agent", "actorId": "agent:sneaky"})
    r = client.post(f"/api/session/{sid}/episode/{ep}/send-back", json={"reason": "r"})
    assert r.status_code == 403
    assert not client.app.state.sessions.get(sid).graph.has("rt-return-ep-cbo-2013-1")
