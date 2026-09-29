"""`GET …/needs` — the queue and the blocking list, read from the record."""
from __future__ import annotations

from docket.kernel.clock import stored_blockers


def test_demo_a_needs_exactly_its_signature(client, demo_a_present):
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    r = client.get(f"/api/session/{sid}/episode/ep-cbo-2013/needs")
    assert r.status_code == 200, r.text
    q = r.json()
    actionable = [i for i in q["items"] if i["actionable"]]
    assert [i["kind"] for i in actionable] == ["signature"]
    assert q["count"] == 1
    assert actionable[0]["route"] == "/package"
    assert actionable[0]["ageDays"] > 4000
    # Nothing stops this decision. The stored report names no blocker, and the two SIGNED
    # checks still unmet — `commitment-present` and `commitment-package-hash` — are both
    # satisfied by the signature the queue is already asking for, so the queue does not
    # count the act against itself [controller ruling, final fix round].
    assert q["blocking"]["items"] == []
    assert q["blocking"]["count"] == 0
    # One number per view of the map, from the server: the signature is the Package row's.
    assert q["byRoute"]["/package"] == 1
    assert sum(q["byRoute"].values()) == q["count"]


def test_the_signature_gate_checks_are_still_named_on_the_ladder(client, demo_a_present):
    """Not counted is not hidden: the episode's own gate ladder still reports both checks
    as unsatisfied, because they are — it is the blocking *count* that refuses to hold an
    act against itself, not the record."""
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    ep = client.get(f"/api/session/{sid}/episode/ep-cbo-2013").json()
    rung = next(r for r in ep["gateLadder"] if r["to"] == "SIGNED")
    unmet = {c["name"] for c in rung["checks"] if not c["satisfied"]}
    assert {"commitment-present", "commitment-package-hash"} <= unmet


def test_demo_b_live_episode_needs_dispatch_and_names_its_blockers(client, demo_b_present):
    sid = client.post("/api/session", json={"source": "demo-b"}).json()["id"]
    r = client.get(f"/api/session/{sid}/episode/ep-omfv-2020-02-r5/needs")
    assert r.status_code == 200, r.text
    q = r.json()
    kinds = [i["kind"] for i in q["items"] if i["actionable"]]
    assert kinds[0] == "dispatch"
    assert "refresh-proposed" in kinds
    findings = [i for i in q["items"] if i["kind"] == "blocking-finding"]
    assert findings and all(i["count"] >= 1 for i in findings)
    assert len({i["id"] for i in findings}) == len(findings)
    unopened = [i for i in q["items"] if i["kind"] == "refresh-proposed"]
    assert {i["objectId"] for i in unopened} == {"rt-gao-grading", "rt-sigmgmt-correction"}
    # The map's own numbers, one per view: five grouped findings on Readiness, the two
    # unopened triggers on Timeline, the dispatch on Compute — and nothing left over.
    assert q["byRoute"]["/readiness"] == len(findings) == 5
    assert q["byRoute"]["/timeline"] == 2
    assert q["byRoute"]["/compute"] == 1
    assert sum(q["byRoute"].values()) == q["count"]
    # Every stored finding is carried: the grouped rows' counts sum to the whole list
    # (severity is not the test — a policy-promoted warning is a blocker too), and the
    # header's single number is that same total, since PLAN_APPROVED sits at no gate.
    stored = stored_blockers(client.app.state.sessions.get(sid).graph, "ep-omfv-2020-02-r5")
    assert sum(i["count"] for i in findings) == len(stored)
    assert q["blocking"]["count"] == len(stored)
    assert len(q["blocking"]["items"]) < len(stored)
    assert all(b["severity"] == "blocking" for b in q["blocking"]["items"])


def test_needs_writes_nothing(client, demo_a_present):
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    g = client.app.state.sessions.get(sid).graph
    head = g.log()[-1]["entryHash"]
    client.get(f"/api/session/{sid}/episode/ep-cbo-2013/needs")
    assert g.log()[-1]["entryHash"] == head


def test_needs_404s_on_an_unknown_episode(client):
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    assert client.get(f"/api/session/{sid}/episode/nope/needs").status_code == 404
