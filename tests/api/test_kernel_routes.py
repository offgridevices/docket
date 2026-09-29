"""Plan 07 Task 4: readiness, the evidence register, packages and the determinism
affordance (`/verify`), and `/export`.

A real, cross-module defect was found and fixed *during* this task, live, by the
concurrent agent re-reviewing `render.py`/`docket.exports` (plan 06 Task 1): before the
fix, `docket.exports.prov.to_prov` enumerated every `DecisionPackage` for the episode
already in the graph (including one just sealed), and `docket.exports.madr.to_madr`
embedded `kernel.render.latest_package(...)`'s hash — both self-referential the moment
the package being re-rendered was itself already sealed into the graph, which it always
is by the time `/verify` runs. That made `identical` false for *any* already-built
package, on a store this task never touched. Confirmed fixed: `prov.py` now excludes
`DecisionPackage` from PROV entities entirely, and `madr.py` prints
`content_snapshot_hash(g)` instead of a package's own hash. See the task report's
"Defects found" section for the full trace (file:line, byte diff, timestamps).
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def demo_a_session(client, demo_a_present):
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    eps = client.get(f"/api/session/{sid}/episodes").json()["episodes"]
    return sid, eps[0]["id"], None


# ---- readiness -------------------------------------------------------------------


def test_readiness_get_reads_the_stored_report_and_does_not_recompute(client, demo_a_session):
    s, ep, _ = demo_a_session
    first = client.post(f"/api/session/{s}/episode/{ep}/readiness", json={"seed": 0}).json()
    again = client.get(f"/api/session/{s}/episode/{ep}/readiness").json()
    assert again["id"] == first["id"]
    assert again["standardsAssessment"]["dimensionVerdicts"].keys() >= {
        "objectivity", "validity", "reliability"}


def test_readiness_post_resolves_standards_assessment_and_mandate_scorecard(
    client, demo_a_session,
):
    s, ep, _ = demo_a_session
    b = client.post(f"/api/session/{s}/episode/{ep}/readiness", json={"seed": 0}).json()
    assert isinstance(b["standardsAssessment"], dict)
    assert b["standardsAssessment"]["type"] == "StandardsAssessment"
    assert isinstance(b["mandateScorecard"], dict)
    assert b["mandateScorecard"]["type"] == "MandateScorecard"


def test_readiness_get_before_any_post_is_404_not_500(client):
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.get(f"/api/session/{sid}/episode/nope/readiness")
    assert r.status_code == 404


# ---- fix round 1: standardsCaptions, applicableQuestions/totalQuestions, readyText,
# tailoring, k, createdAt (C1/I2/I5, plan 07 Task 7 review's Q7 answer) ----------------


def test_readiness_view_carries_the_renderers_own_captions_and_counts(client, demo_a_session):
    from docket.kernel.render import rating_scale_legend

    s, ep, _ = demo_a_session
    b = client.post(f"/api/session/{s}/episode/{ep}/readiness", json={"seed": 0}).json()

    assert b["standardsCaptions"]["ratingScale"] == rating_scale_legend()
    # Demo A is scored under `published-21`, which has no tailoring note.
    assert b["standardsCaptions"]["tailoringNote"] is None
    ratings = b["standardsAssessment"]["ratings"]
    assert b["totalQuestions"] == len(ratings) == 36
    assert b["applicableQuestions"] == sum(1 for r in ratings if r["applicable"])
    assert b["tailoring"] == b["standardsAssessment"]["tailoring"]
    assert b["k"] == b["standardsAssessment"]["k"]
    # `rr["createdAt"]` restated at the top level, unchanged — the report's own field.
    assert isinstance(b["createdAt"], str) and b["createdAt"]
    # `readyText` is the renderer's own `str()` form (`True`/`False`), byte-identical
    # to what the three committed demo packages print for "Ready (no blocking
    # findings)", never the browser's own `String(bool)` on a JSON boolean.
    assert b["readyText"] in ("True", "False") or "unavailable" in b["readyText"]
    assert b["readyText"] == str(b["ready"])


def test_readiness_view_on_get_matches_post(client, demo_a_session):
    """The same fields, whether freshly computed or read back — `GET` never
    recomputes, but the view wrapper (`_readiness_view`) runs on both paths."""
    s, ep, _ = demo_a_session
    posted = client.post(f"/api/session/{s}/episode/{ep}/readiness", json={"seed": 0}).json()
    got = client.get(f"/api/session/{s}/episode/{ep}/readiness").json()
    assert got["standardsCaptions"] == posted["standardsCaptions"]
    assert got["readyText"] == posted["readyText"]
    assert got["tailoring"] == posted["tailoring"]
    assert got["k"] == posted["k"]


def test_readiness_view_carries_the_scored_tailorings_own_note_on_demo_b(client, demo_b_present):
    """C1: GAO-23-106549 publishes a 3×3 verdict grid and nine findings, not
    per-question labels — `standard/tailorings/gao-23-106549.yaml`'s own `note`, and
    every episode in Demo B is scored under that tailoring. The Readiness screen must
    print the kernel's own string, never a second hand-typed copy."""
    from docket.kernel.render import tailoring_note

    sid = client.post("/api/session", json={"source": "demo-b"}).json()["id"]
    eps = client.get(f"/api/session/{sid}/episodes").json()["episodes"]
    ep = max(eps, key=lambda e: e["sequence"])["id"]

    b = client.get(f"/api/session/{sid}/episode/{ep}/readiness").json()
    assert b["standardsCaptions"]["tailoringNote"] == tailoring_note("gao-23-106549")
    assert b["standardsCaptions"]["tailoringNote"]  # non-empty, not just non-None
    assert b["tailoring"] == "gao-23-106549"


# ---- evidence register ---------------------------------------------------------------


def test_evidence_register_resolves_items_and_scope_findings(client, demo_a_session):
    s, ep, _ = demo_a_session
    b = client.get(f"/api/session/{s}/episode/{ep}/evidence").json()
    assert b["episode"] == ep
    assert isinstance(b["items"], list) and b["items"]
    item = b["items"][0]
    assert item["type"] == "Evidence"
    assert "classification" in item["object"]
    assert "scopeFindings" in item
    assert isinstance(b["findings"], list)


def test_evidence_register_rejects_an_unknown_rendering_value(client, demo_a_session):
    s, ep, _ = demo_a_session
    r = client.get(f"/api/session/{s}/episode/{ep}/evidence?rendering=classified")
    assert r.status_code == 400


def test_evidence_register_withholds_fields_above_u_under_unclassified(
    client, demo_a_present,
):
    """Fix round 1, I1: `_evidence_register_row` (render.py:545-561) withholds
    `pointer`/`scopeOfValidity`/`reliabilitySteps`/`reviewStatus` behind
    `[withheld: <level>]` whenever `rendering != "full"` and `metadataLevel` is above
    `U`. Every Demo A item is `"U"` (moot in practice), so this adds one item at
    metadataLevel `S` — a real evidence object copied from the fixture's own
    `ev-cbo-2013`, not a fabricated shape — to exercise the withholding path.
    """
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    session = client.app.state.sessions.get(sid)
    g = session.graph
    actor = {"actorType": "human", "actorId": "tester"}
    classified = {
        **g.get("ev-cbo-2013"), "id": "ev-test-classified", "rev": 1, "createdBy": actor,
        "classification": {"level": "S", "metadataLevel": "S"},
    }
    g.put(classified, actor)
    ep = g.get("ep-cbo-2013")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": actor,
           "evidenceRegister": [*ep["evidenceRegister"], "ev-test-classified"]}, actor)

    full = client.get(
        f"/api/session/{sid}/episode/ep-cbo-2013/evidence?rendering=full").json()
    item = next(i for i in full["items"] if i["id"] == "ev-test-classified")
    assert item["object"]["pointer"] == classified["pointer"]
    assert item["object"]["scopeOfValidity"] == classified["scopeOfValidity"]

    withheld = client.get(
        f"/api/session/{sid}/episode/ep-cbo-2013/evidence?rendering=unclassified").json()
    item = next(i for i in withheld["items"] if i["id"] == "ev-test-classified")
    assert item["object"]["pointer"] == "[withheld: S]"
    assert item["object"]["scopeOfValidity"] == "[withheld: S]"
    assert item["object"]["reliabilitySteps"] == "[withheld: S]"
    assert item["object"]["reviewStatus"] == "[withheld: S]"
    # classification is never withheld — it's the reason the rest of the row is hidden
    assert item["object"]["classification"] == {"level": "S", "metadataLevel": "S"}
    # the P3 slot resolver must not leak a $gap/$exclusion target for a withheld field
    assert not any(
        s["path"] in ("pointer", "scopeOfValidity", "reliabilitySteps")
        for s in item["slots"]
    )


def test_evidence_register_resolves_cited_by_with_reuse_justification(
    client, demo_a_session,
):
    """Fix round 1, I2: `reuseJustification`/`assessableAt` live on `Claim.supportedBy[]`
    and `Claim.assessableAt`, not on `Evidence` — `citedBy` is how the evidence register
    surfaces them anyway. Checked against whichever evidence items `check_scope` itself
    currently flags `reuse-justified` on Demo A, rather than a hardcoded count/id list,
    since that set has already drifted once during this plan from unrelated concurrent
    fixture edits (see the Task 4 report's Deviations)."""
    s, ep, _ = demo_a_session
    b = client.get(f"/api/session/{s}/episode/{ep}/evidence").json()
    by_id = {item["id"]: item for item in b["items"]}
    reuse_justified_ids = {
        f["objects"][1] for f in b["findings"]
        if f["rule"] == "reuse-justified" and len(f["objects"]) > 1
    }
    assert reuse_justified_ids, "Demo A must have at least one reuse-justified evidence item"
    for eid in reuse_justified_ids:
        item = by_id[eid]
        assert item["citedBy"], f"{eid} should be cited by at least one claim"
        assert any(c["reuseJustification"] and c["assessableAt"] for c in item["citedBy"])


# ---- package -----------------------------------------------------------------------


def test_two_renders_of_one_graph_have_the_same_hash(client, demo_a_session, monkeypatch):
    """The Cover section prints `now` verbatim ("Rendered: {now}"), so two real HTTP
    round trips landing in different wall-clock seconds legitimately produce different
    bytes — that is not a determinism defect, it is two renders at two different
    `now`s. Pinning the route's clock isolates the actual claim under test ("given the
    same `now`, an unchanged graph re-renders identically no matter how many packages
    already sit in it") from real-clock flakiness that has nothing to do with it.
    """
    monkeypatch.setattr("docket.api.routes.kernel._now", lambda: "2030-01-01T00:00:00Z")
    s, ep, _ = demo_a_session
    a = client.post(f"/api/session/{s}/episode/{ep}/package?rendering=full").json()
    b = client.post(f"/api/session/{s}/episode/{ep}/package?rendering=full").json()
    assert a["id"] != b["id"] and a["hash"] == b["hash"]


def test_package_rejects_an_unknown_rendering_value(client, demo_a_session):
    s, ep, _ = demo_a_session
    r = client.post(f"/api/session/{s}/episode/{ep}/package?rendering=classified")
    assert r.status_code == 400


def test_package_text_route_returns_markdown(client, demo_a_session):
    s, ep, _ = demo_a_session
    pkg = client.post(f"/api/session/{s}/episode/{ep}/package?rendering=unclassified").json()
    r = client.get(f"/api/session/{s}/package/{pkg['id']}/text")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.text.startswith("# Decision Package")


# ---- verify --------------------------------------------------------------------------


def test_verify_uses_the_kernels_own_latest_package_hash(client, demo_a_session):
    from docket.kernel.render import latest_package_hash

    s, ep, _ = demo_a_session
    client.post(f"/api/session/{s}/episode/{ep}/package?rendering=full")
    v = client.post(f"/api/session/{s}/episode/{ep}/verify", json={"rendering": "full"}).json()
    assert v["identical"] is True and v["scope"].startswith("kernel rendering only")
    g = client.app.state.sessions.get(s).graph
    assert v["priorHash"] == latest_package_hash(g, ep, rendering="full")


def test_verify_with_no_body_defaults_to_full_rendering(client, demo_a_session):
    s, ep, _ = demo_a_session
    client.post(f"/api/session/{s}/episode/{ep}/package?rendering=full")
    r = client.post(f"/api/session/{s}/episode/{ep}/verify")
    assert r.status_code == 200 and r.json()["identical"] is True


def test_verify_before_any_package_is_409_not_500(client, demo_a_present):
    """Demo A's own committed build already ships a `full`-rendering package (built by
    `demos/a_cbo_gcv_2013/build.py`), so a freshly copied session is not, in fact, a
    graph with "no package built yet" — the plan's own example test implicitly assumes
    one. Reconciled here (see the task report's Defects section) by deleting the
    pre-built `DecisionPackage` objects from this session's in-memory copy before
    calling verify, so `latest_package_hash` genuinely finds none and the 409 path is
    actually exercised rather than skipped straight past.
    """
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    session = client.app.state.sessions.get(sid)
    g = session.graph
    for pkg in g.all("DecisionPackage"):
        del g._latest[pkg["id"]]
    ep = g.all("DecisionEpisode")[0]["id"]

    r = client.post(f"/api/session/{sid}/episode/{ep}/verify")
    assert r.status_code == 409
    assert r.json()["error"] == "no-package"


def test_verify_404s_on_an_unknown_episode(client):
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    assert client.post(f"/api/session/{sid}/episode/nope/verify").status_code == 404


# ---- verify: recordUnchanged / reason (fix round 1, I3) -------------------------------


def test_verify_reason_is_identical_when_the_bytes_match(client, demo_a_session):
    s, ep, _ = demo_a_session
    client.post(f"/api/session/{s}/episode/{ep}/package?rendering=full")
    v = client.post(f"/api/session/{s}/episode/{ep}/verify").json()
    assert v["identical"] is True
    assert v["recordUnchanged"] is True
    assert v["reason"] == "identical"


def test_verify_reason_is_record_unchanged_rendering_changed_on_demo_as_own_package(
    client, demo_a_present,
):
    """Reproduces the exact real finding from the Task 4 report: verifying Demo A's own
    pre-built, never-touched-by-this-session package. The record's content genuinely has
    not changed (`graphSnapshotHash == priorGraphSnapshotHash`); the fixture just
    pre-dates the newer per-export-hash Machine-annex format, so the bytes differ. If
    the fixture is rebuilt after this report (out of this task's scope — see the report),
    `identical` may now be `true`, in which case there is nothing left to reproduce here.
    """
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    eps = client.get(f"/api/session/{sid}/episodes").json()["episodes"]
    ep = eps[0]["id"]
    v = client.post(f"/api/session/{sid}/episode/{ep}/verify").json()
    assert v["graphSnapshotHash"] == v["priorGraphSnapshotHash"]
    assert v["recordUnchanged"] is True
    if v["identical"]:
        pytest.skip("Demo A's fixture has been rebuilt since; nothing left to reproduce")
    assert v["reason"] == "record unchanged; rendering changed"


def test_verify_reason_is_record_changed_after_a_second_readiness_run(
    client, demo_a_session,
):
    s, ep, _ = demo_a_session
    client.post(f"/api/session/{s}/episode/{ep}/package?rendering=full")
    # A second readiness run adds new ReadinessReport/StandardsAssessment/
    # MandateScorecard objects and repoints episode["readiness"] at them — genuine
    # content drift, not a rendering-format artefact.
    client.post(f"/api/session/{s}/episode/{ep}/readiness", json={"seed": 1})
    v = client.post(f"/api/session/{s}/episode/{ep}/verify").json()
    assert v["recordUnchanged"] is False
    assert v["identical"] is False
    assert v["reason"] == "record changed"


def test_latest_package_agrees_with_latest_package_hash(demo_a_present):
    """`api.verify.verify_determinism` reads `renderedAt`/`graphSnapshotHash` off
    `kernel.render.latest_package` and the comparison hash off
    `kernel.render.latest_package_hash` — this is the assumption that the two always
    name the same object (documented on `latest_package_hash` itself: "The hash of
    `latest_package(...)`, or None")."""
    from docket.kernel.render import latest_package, latest_package_hash
    from docket.store import Graph

    g = Graph.load(demo_a_present)
    ep = g.all("DecisionEpisode")[0]["id"]
    obj = latest_package(g, ep, rendering="full")
    assert obj is not None
    assert obj["hash"] == latest_package_hash(g, ep, rendering="full")


# ---- export (plan 06) -----------------------------------------------------------------


def test_export_prov_returns_json(client, demo_a_session):
    """`docket.exports` landed during this task (plan 06 Task 1, concurrent with plan
    07 Task 4); the route calls it directly rather than staying permanently 501 against
    a module that now exists — see the route's own docstring."""
    s, ep, _ = demo_a_session
    r = client.get(f"/api/session/{s}/episode/{ep}/export?format=prov")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    import json

    body = json.loads(r.text)
    assert set(body) == {"bundle", "prefix"}  # PROV-JSON's top-level shape


def test_export_rejects_an_unknown_format(client, demo_a_session):
    s, ep, _ = demo_a_session
    r = client.get(f"/api/session/{s}/episode/{ep}/export?format=not-a-real-format")
    assert r.status_code == 400


def test_export_404s_on_an_unknown_episode(client):
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.get(f"/api/session/{sid}/episode/nope/export")
    assert r.status_code == 404
