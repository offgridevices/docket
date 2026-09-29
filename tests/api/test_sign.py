"""`POST /api/session/{s}/episode/{e}/sign` — a human act; the response carries the commitment."""


def _open(client, source):
    return client.post("/api/session", json={"source": source}).json()["id"]


def _first_alternative(client, sid):
    ep = client.get(f"/api/session/{sid}/episode/ep-cbo-2013").json()
    return ep["alternatives"][0]


def test_sign_renders_then_signs(client, demo_a_present):
    sid = _open(client, "demo-a")
    rendered = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/package?rendering=full")
    assert rendered.status_code == 200
    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/sign", json={
        "selected": _first_alternative(client, sid), "role": "Milestone Decision Authority",
        "stopRules": ["Stop if unit cost exceeds the ceiling."],
        "dissent": [{"who": "CBO", "text": "The cost estimate is optimistic."}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["episode"]["lifecycleState"] == "SIGNED"
    assert body["commitment"]["object"]["dissent"][0]["who"] == "CBO"
    assert body["commitment"]["object"]["createdBy"]["actorType"] == "human"
    assert body["commitment"]["authorId"] == "tester"


def test_sign_without_a_package_is_422(client, demo_a_present, monkeypatch):
    """Demo A's committed store already carries a full package, so "nothing rendered" is
    simulated at the one seam `sign` reads it through; the route maps the kernel's
    `ValidationError` to 422 and nothing is written."""
    sid = _open(client, "demo-a")
    monkeypatch.setattr("docket.kernel.commit.latest_package_hash", lambda *a, **k: None)
    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/sign", json={
        "selected": _first_alternative(client, sid), "role": "MDA", "stopRules": ["x"]})
    assert r.status_code == 422 and "rendered full package" in r.json()["message"]
    assert not client.app.state.sessions.get(sid).graph.has("cm-ep-cbo-2013-1")


def test_sign_wrong_state_is_422(client, demo_b_present):
    sid = _open(client, "demo-b")
    r = client.post(f"/api/session/{sid}/episode/ep-omfv-2020-02-r5/sign",
                    json={"selected": "x", "role": "MDA", "stopRules": ["x"]})
    assert r.status_code == 422


def test_sign_refused_by_the_gate_is_409_and_the_attempt_is_on_the_record(
    client, demo_a_present, monkeypatch,
):
    """A commitment bound to a hash that is not the latest full package's fails the
    gate's own `commitment-package-hash` check. The route answers with the same
    `transition-refused` body the transition route produces, and the record keeps both
    the commitment and the refused attempt — the state does not move."""
    sid = _open(client, "demo-a")
    monkeypatch.setattr("docket.kernel.commit.latest_package_hash", lambda *a, **k: "stale")
    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/sign", json={
        "selected": _first_alternative(client, sid), "role": "MDA", "stopRules": ["x"]})
    assert r.status_code == 409, r.text
    assert r.json()["error"] == "transition-refused"
    assert r.json()["unsatisfied"] == ["commitment-package-hash"]
    ep = client.get(f"/api/session/{sid}/episode/ep-cbo-2013").json()
    assert ep["lifecycleState"] == "PENDING_SIGNATURE"
    # The pointer is restored (fix round 1): the Commitment object stays, the episode does
    # not name it, and the queue still lists the signature as pending.
    assert ep.get("commitment") is None
    assert client.get(f"/api/session/{sid}/object/cm-ep-cbo-2013-1").status_code == 200
    assert ep["transitions"][-1]["to"] == "SIGNED" and ep["transitions"][-1]["refused"] is True
    q = client.get(f"/api/session/{sid}/episode/ep-cbo-2013/needs").json()
    assert [i["kind"] for i in q["items"] if i["kind"] == "signature"] == ["signature"]


def test_sign_refuses_a_non_human_actor_even_under_a_simulated_regression(
    client, demo_a_present, monkeypatch,
):
    sid = _open(client, "demo-a")
    monkeypatch.setattr("docket.api.routes.workspace.human_actor",
                        lambda: {"actorType": "agent", "actorId": "agent:sneaky"})
    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/sign", json={
        "selected": "alt-gcv", "role": "MDA", "stopRules": ["x"]})
    assert r.status_code == 403
    assert not client.app.state.sessions.get(sid).graph.has("cm-ep-cbo-2013-1")


def test_sign_after_a_send_back_is_422(client, demo_a_present):
    """The kernel's own rule, not only the view's: a standing send-back closes the gate."""
    sid = _open(client, "demo-a")
    rendered = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/package?rendering=full")
    assert rendered.status_code == 200
    assert client.post(f"/api/session/{sid}/episode/ep-cbo-2013/send-back",
                       json={"reason": "the cost section is stale"}).status_code == 200
    r = client.post(f"/api/session/{sid}/episode/ep-cbo-2013/sign", json={
        "selected": _first_alternative(client, sid), "role": "MDA", "stopRules": ["x"]})
    assert r.status_code == 422, r.text
    assert "sent back for rework" in r.json()["message"]
    assert not client.app.state.sessions.get(sid).graph.has("cm-ep-cbo-2013-1")


def test_sign_on_an_unknown_episode_is_404(client, demo_a_present):
    sid = _open(client, "demo-a")
    r = client.post(f"/api/session/{sid}/episode/nope/sign",
                    json={"selected": "x", "role": "MDA", "stopRules": ["x"]})
    assert r.status_code == 404
