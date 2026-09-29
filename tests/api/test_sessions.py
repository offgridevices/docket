def test_new_session_starts_from_a_seeded_policy(client):
    s = client.post("/api/session", json={"source": "new"}).json()
    assert s["id"] and s["source"] == "new"
    ids = client.get(f"/api/session/{s['id']}/episodes").json()
    assert ids["episodes"] == []
    pol = client.get(f"/api/session/{s['id']}/object/pol-default").json()
    assert pol["object"]["type"] == "Policy" and pol["authorType"] == "human"


def test_demo_a_is_copied_not_mutated(client, demo_a_present):
    before = (demo_a_present / "manifest.json").read_bytes()
    s = client.post("/api/session", json={"source": "demo-a"}).json()
    eps = client.get(f"/api/session/{s['id']}/episodes").json()["episodes"]
    assert eps and eps[0]["lifecycleState"]
    # writing through the session must not touch the committed fixture
    assert (demo_a_present / "manifest.json").read_bytes() == before


def test_unknown_session_is_404_and_unknown_object_is_404(client):
    assert client.get("/api/session/nope/episodes").status_code == 404
    s = client.post("/api/session", json={"source": "new"}).json()
    assert client.get(f"/api/session/{s['id']}/object/nope").status_code == 404


def test_object_view_marks_slots(client, demo_a_present):
    s = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    eps = client.get(f"/api/session/{s}/episodes").json()["episodes"]
    ep = client.get(f"/api/session/{s}/episode/{eps[0]['id']}").json()
    assert ep["gateLadder"][0]["state"] and "checks" in ep["gateLadder"][0]


def test_unknown_demo_source_is_409_not_built(client, monkeypatch, tmp_path):
    """A known demo source whose store is not built must degrade gracefully rather than
    500 or silently succeed with an empty graph. The demos root is redirected to an
    empty directory so the test holds whether or not Demo B is built on this machine."""
    monkeypatch.setenv("DOCKET_DEMOS_DIR", str(tmp_path / "no-demos"))
    r = client.post("/api/session", json={"source": "demo-b"})
    assert r.status_code == 409
    assert r.json()["error"] == "demo-not-built"


def test_bad_source_is_400_not_500(client):
    r = client.post("/api/session", json={"source": "not-a-real-source"})
    assert r.status_code == 400


def test_sessions_list_and_delete(client):
    s = client.post("/api/session", json={"source": "new"}).json()["id"]
    assert any(row["id"] == s for row in client.get("/api/sessions").json()["sessions"])
    assert client.delete(f"/api/session/{s}").status_code == 200
    assert client.get(f"/api/session/{s}/episodes").status_code == 404


def test_object_revision_is_addressable_and_not_leaking_key(client):
    s = client.post("/api/session", json={"source": "new"}).json()["id"]
    pol = client.get(f"/api/session/{s}/object/pol-default?rev=1").json()
    assert pol["rev"] == 1 and pol["revisions"] == [1]


def test_sections_route_reports_render_sections(client):
    b = client.get("/api/sections").json()
    assert isinstance(b["sections"], list)
    if b["sections"]:
        assert set(b["sections"][0]) == {"key", "title"}


def test_gate_ladder_checks_carry_what_would_satisfy(client, demo_a_present):
    """The ladder prints the gate's own sentence, the one `kernel.queue` already gives the
    Needs queue — so a reader on the Plan view and a reader on the queue can never be
    told two different things about the same predicate."""
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    body = client.get(f"/api/session/{sid}/episode/ep-cbo-2013").json()
    rung = next(r for r in body["gateLadder"] if r["to"] == "PLAN_APPROVED")
    assert {c["name"] for c in rung["checks"]} == {
        "plan-present", "plan-approved-by-human", "plan-steps-have-authority",
        "policy-method-matches"}
    assert all(c["whatWouldSatisfy"] for c in rung["checks"])
