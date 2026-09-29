"""Plan 07 Task 4: the authority rail's numbers. The rail is the visible form of
"the agent never sits in the numeric path" (CLAUDE.md) — these numbers are computed
server-side (`docket.api.authority.authority_counts`), never summed by the browser.
"""
from __future__ import annotations


def _demo_a_session(client):
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    eps = client.get(f"/api/session/{sid}/episodes").json()["episodes"]
    return sid, eps[0]["id"]


def test_agent_numerals_are_always_zero_on_an_unforged_store(client, demo_a_present):
    sid, ep = _demo_a_session(client)
    b = client.get(f"/api/session/{sid}/episode/{ep}/authority").json()
    assert b["episode"] == ep
    assert b["numerals"]["agent"] == 0
    assert b["numerals"]["kernel"] > 0
    assert b["objects"]["kernel"] > 0
    assert b["objects"]["human"] > 0
    assert b["agentForbiddenWrites"] == 0
    assert b["kernelVersion"]
    assert "explanation" in b and b["explanation"]


def test_kernel_authored_result_values_are_counted_not_zero(client, demo_a_present):
    """Plan 07 Task 7 review, Observation 2: the T7 review's live probe of the rendered
    Compute screen saw `NUMBERS AUTHORED BY MODEL: 0 · BY KERNEL: 0` while roughly 40
    kernel numerals were on the page, and asked whether the counter or its label was
    wrong. Traced directly against `authority_counts` (bypassing the UI entirely): on
    Demo A's full episode, `Result` objects alone (50 of them, `createdBy` kernel)
    contribute 90 numeric leaves (`value`, and `raw` on the 36 non-aggregate rows), and
    the counter's own total is well above that floor — so the counter is not the
    defect. `Result.value` is counted, byte for byte, as a kernel numeral; a future
    change to `_numeric_leaves`/`_EXCLUDED_TOP_LEVEL_FIELDS` that stopped counting it
    would fail this test specifically, not just the pre-existing `> 0` check above.

    The rail actually reading 0/0 in the browser traces to a different, T6-owned bug:
    `ui/src/App.tsx` never passes `episode`/`sessionId` to `<AppShell>`, so
    `AuthorityRail` never receives an `episodeId` and falls back to its zero
    placeholder on every screen, regardless of what this counter computes. That wiring
    gap is explicitly out of this task's scope (plan 07 Task 7 fix round instructions);
    this test exists to pin down that the counter itself already answers correctly, so
    the fix, when T6 lands it, is purely the wiring.
    """
    sid, ep = _demo_a_session(client)
    b = client.get(f"/api/session/{sid}/episode/{ep}/authority").json()

    session = client.app.state.sessions.get(sid)
    g = session.graph
    reach = {ep} | g.reachable_from(ep, reverse=False)
    results = [g.get(oid) for oid in reach if g.has(oid) and g.get(oid)["type"] == "Result"]
    assert results, "Demo A must have at least one sealed Result to test the counter against"
    assert all(r["createdBy"]["actorType"] == "kernel" for r in results)

    # A floor, not an exact count: every Result contributes at least its own `value`
    # (one numeral each), so the kernel total must be at least that many — well above
    # zero, and specifically attributable to Result values, not some other object type
    # alone carrying the whole count.
    assert b["numerals"]["kernel"] >= len(results)
    assert b["numerals"]["kernel"] > 0


def test_authority_route_returns_not_found_on_an_unknown_episode(client):
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    assert client.get(f"/api/session/{sid}/episode/nope/authority").status_code == 404


def test_a_forged_agent_authored_result_is_caught_by_the_live_recheck(client, demo_a_present):
    """`Graph.put` refuses this write in process (`AGENT_FORBIDDEN_TYPES`); a saved
    store can be hand-edited, so `authority_counts` re-derives the boundary from the
    store itself (`kernel.validate.rule_authority`) rather than trusting that every
    object it reaches was written honestly.

    No API-layer forgery fixture exists yet (plan 04 Task 9's helper had not landed at
    this task's dispatch — see the plan's own note under Task 4 Step 1, "verify at
    dispatch"). This forges the same way `tests/kernel/test_validate_structural.py`
    does at the kernel layer: editing a live `Graph`'s private `_latest` directly, the
    in-memory equivalent of hand-editing the store on disk before `Graph.load()` reads
    it back. `client.app` is the same `FastAPI` instance `create_app()` built in the
    `client` fixture, so this reaches the exact `Session.graph` the route below reads.
    """
    sid, ep = _demo_a_session(client)
    session = client.app.state.sessions.get(sid)
    g = session.graph
    results = g.all("Result")
    assert results, "Demo A must have at least one sealed Result to forge"
    rid = results[0]["id"]
    forged = {**g.get(rid), "createdBy": {"actorType": "agent", "actorId": "forger"}}
    g._latest[rid] = forged

    b = client.get(f"/api/session/{sid}/episode/{ep}/authority").json()
    assert b["agentForbiddenWrites"] > 0
    # The forged Result's own numeric leaves (value, uncertainty lo/hi, ...) now read as
    # the agent's — which is exactly why the rail has to be a live re-check, not a
    # cached "0" from whenever the store was last known-good.
    assert b["numerals"]["agent"] > 0
