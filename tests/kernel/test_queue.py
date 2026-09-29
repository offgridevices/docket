"""kernel/queue.py — what needs a person, derived from the record and nothing else."""
from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.kernel.queue import MAP_ROUTES, needs
from docket.store import Graph
from tests.kernel.conftest import (
    NOW,
    H,
    assumption_,
    charter,
    complete_graph,
    drs,
    episode,
    evidence,
    gap,
    obj,
    policy,
    put_all,
)

TODAY = "2026-09-11T00:00:00Z"


def _draft_graph() -> Graph:
    """A DRAFT episode with one unread linchpin, one unconfirmed gap hanging off the
    charter's consequences field, and an agent-authored charter."""
    agent = {"actorType": "agent", "actorId": "agent:test"}
    g = Graph()
    put_all(g, policy(), evidence("ev-doc"), drs())
    g.put({**charter(consequencesOfErroneousOutput={"$gap": "gap-1"}), "createdBy": agent,
           "createdAt": "2026-09-01T00:00:00Z"}, agent)
    g.put({**gap("gap-1", confirmed=False), "createdBy": agent,
           "createdAt": "2026-09-01T00:00:00Z"}, agent)
    g.put({**assumption_("as-1", linchpin=True), "createdBy": agent,
           "createdAt": "2026-09-03T00:00:00Z"}, agent)
    put_all(g, episode(assumptions=["as-1"], createdAt="2026-09-01T00:00:00Z"))
    return g


def test_draft_queue_lists_the_three_reviewable_items_in_order():
    q = needs(_draft_graph(), "ep-1", now=TODAY)
    kinds = [i["kind"] for i in q["items"] if i["actionable"]]
    assert kinds == ["linchpin-unreviewed", "gap-unconfirmed", "charter-field-empty"]
    linchpin, gap_item, charter_item = [i for i in q["items"] if i["actionable"]]
    assert linchpin["route"] == "/review/as-1" and linchpin["objectId"] == "as-1"
    assert linchpin["ageDays"] == 8
    assert gap_item["route"] == "/review/gap-1" and "silence is real" in gap_item["text"]
    assert charter_item["route"] == "/model" and charter_item["objectId"] == "ch-1"
    assert "what happens if this is wrong" in charter_item["text"]
    assert q["count"] == 3


def test_draft_queue_lists_later_stages_as_not_yet_actionable():
    q = needs(_draft_graph(), "ep-1", now=TODAY)
    later = [i for i in q["items"] if not i["actionable"]]
    assert [i["kind"] for i in later] == ["weights-unsaved", "dispatch", "readiness", "signature"]
    assert all(i["unlocksAfter"] for i in later)
    assert later[0]["unlocksAfter"] == "the model is approved"


def test_gate_1_item_appears_only_when_every_check_is_satisfied(base_graph):
    q = needs(base_graph, "ep-1", now=TODAY)
    assert [i["kind"] for i in q["items"] if i["actionable"]] == ["gate-1"]
    assert q["items"][0]["text"] == "The model is ready to approve."
    assert q["blocking"]["count"] == 0


def test_blocking_lists_unmet_gate_checks_by_name():
    q = needs(_draft_graph(), "ep-1", now=TODAY)
    rules = {b["rule"] for b in q["blocking"]["items"]}
    assert {"charter-three-fields", "charter-human-accepted", "gaps-confirmed",
            "linchpins-human"} <= rules
    assert all(b["severity"] == "gate" and b["route"] == "/model" for b in q["blocking"]["items"])
    assert all(b["message"] for b in q["blocking"]["items"])


def test_a_complete_signed_episode_needs_nobody():
    """`complete_graph()` stops at PLAN_APPROVED with its calculations already sealed, so
    nothing in it needs a person; the rows it still carries are the later stages, marked
    not yet actionable. Signing it leaves no rows at all."""
    g = complete_graph()
    q = needs(g, "ep-1", now=TODAY)
    assert q["count"] == 0
    assert [i["kind"] for i in q["items"] if i["actionable"]] == []
    assert all(i["unlocksAfter"] for i in q["items"])
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "lifecycleState": "SIGNED"}, H)
    signed = needs(g, "ep-1", now=TODAY)
    assert signed["count"] == 0
    assert [i["kind"] for i in signed["items"]] == []


def test_a_superseded_episode_asks_nobody_for_anything(base_graph):
    """A record in a terminal state has no pending human act (the ruling the clock reads
    through `TERMINAL_STATES`): the trigger that superseded it is the successor's work,
    not this episode's, so it lists nothing at all."""
    g = base_graph
    put_all(
        g,
        obj("rt-1", "RefreshTrigger", kind="evidence-changed", source="a later report",
            description="The cost figure has been restated.", detectedAt="2026-09-05",
            affected=["ep-1"]),
        obj("prg-1", "DecisionProgram", name="p", charter="ch-1", episodes=["ep-1"],
            refreshTriggers=["rt-1"], diffs=[]),
    )
    live = needs(g, "ep-1", now=TODAY)
    assert "refresh-proposed" in [i["kind"] for i in live["items"] if i["actionable"]]

    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "lifecycleState": "SUPERSEDED"}, H)
    q = needs(g, "ep-1", now=TODAY)
    assert q["count"] == 0
    assert q["items"] == []


def _readiness_graph(blockers) -> Graph:
    """An EVALUATED episode carrying a kernel-written readiness report with `blockers`."""
    g = Graph()
    put_all(g, policy(), evidence("ev-doc"), drs(), charter(), episode())
    for o in (
        {"id": "sa-1", "type": "StandardsAssessment", "rev": 1, "createdAt": NOW,
         "episode": "ep-1", "tailoring": "published-21", "ratings": [],
         "dimensionVerdicts": {}, "aggregationRule": "k-of-n", "k": 1,
         "kernelVersion": KERNEL_VERSION},
        {"id": "ms-1", "type": "MandateScorecard", "rev": 1, "createdAt": NOW,
         "episode": "ep-1", "rows": [], "kernelVersion": KERNEL_VERSION},
        {"id": "rr-1", "type": "ReadinessReport", "rev": 1, "createdAt": NOW,
         "episode": "ep-1", "standardsAssessment": "sa-1", "mandateScorecard": "ms-1",
         "blockers": blockers, "warnings": [], "openGaps": [], "openExclusions": [],
         "flipSummary": {}, "biasChecksStatus": [], "computedBiasRisks": [],
         "ready": not blockers, "policyVersion": "0.1",
         "kernelVersion": KERNEL_VERSION, "seed": 1},
    ):
        g.put({**o, "createdBy": KERNEL_ACTOR}, KERNEL_ACTOR)
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "lifecycleState": "EVALUATED", "readiness": "rr-1"}, H)
    return g


def test_a_promoted_warning_still_stops_sign_off():
    """`Policy.blockingRules` can promote a finding into `blockers` while it keeps its own
    `warning` severity; readiness computes `ready` as exactly "no blockers", so the queue
    reads membership of that list and never severity. Findings group one row per rule."""
    g = _readiness_graph([
        {"rule": "evidence-review-status", "severity": "blocking", "objects": ["ev-doc"],
         "message": "Evidence ev-doc has not been reviewed."},
        {"rule": "evidence-review-status", "severity": "blocking", "objects": ["ev-two"],
         "message": "Evidence ev-two has not been reviewed."},
        {"rule": "linchpin-not-varied", "severity": "warning", "objects": ["as-1"],
         "message": "A linchpin was never varied.", "promotedBy": "policy.blockingRules"},
    ])
    q = needs(g, "ep-1", now=TODAY)
    findings = [i for i in q["items"] if i["kind"] == "blocking-finding"]
    assert [i["id"] for i in findings] == ["blocking-finding:evidence-review-status",
                                           "blocking-finding:linchpin-not-varied"]
    assert [i["count"] for i in findings] == [2, 1]
    assert all(i["objectId"] is None and i["route"] == "/readiness" for i in findings)
    rows = {b["rule"]: b for b in q["blocking"]["items"]}
    assert rows["linchpin-not-varied"]["severity"] == "blocking"
    assert rows["linchpin-not-varied"]["count"] == 1
    assert rows["evidence-review-status"]["objects"] == ["ev-doc", "ev-two"]
    # EVALUATED sits at no gate, so the header number is the three stored findings —
    # grouping the rows does not change it.
    assert q["blocking"]["count"] == 3
    assert sum(i["count"] for i in findings) == 3


def _pending_signature_graph() -> Graph:
    """`complete_graph()` with the commitment cut out and the state wound back to the one
    a signature is asked for. It carries no `ReadinessReport`, so the SIGNED gate's
    `readiness-ready` is genuinely unmet — which is what makes it the right fixture for
    asking which of that gate's checks the queue counts."""
    g = complete_graph()
    ep = g.get("ep-1")
    g.put({**{k: v for k, v in ep.items() if k != "commitment"}, "rev": ep["rev"] + 1,
           "createdBy": H, "createdAt": NOW, "lifecycleState": "PENDING_SIGNATURE"}, H)
    return g


def test_pending_signature_needs_the_signer():
    q = needs(_pending_signature_graph(), "ep-1", now=TODAY)
    assert [i["kind"] for i in q["items"] if i["actionable"]] == ["signature"]
    assert q["items"][0]["waitingOn"] == "the decision authority"


def test_the_signature_gate_never_counts_the_checks_the_signature_itself_satisfies():
    """`commitment-present` and `commitment-package-hash` are both satisfied by the one
    act the queue is already asking for, so counting them would tell a reader that two
    things stop the very act they are being asked to perform [controller ruling, final
    fix round]. Every other unmet check of that same gate still counts."""
    q = needs(_pending_signature_graph(), "ep-1", now=TODAY)
    assert [b["rule"] for b in q["blocking"]["items"]] == ["readiness-ready"]
    assert q["blocking"]["count"] == 1


def _sent_back_graph() -> Graph:
    g = _pending_signature_graph()
    put_all(g, obj("rt-return-ep-1-1", "RefreshTrigger", kind="signer-return",
                   source="the signer", description="The cost basis needs a source.",
                   detectedAt="2026-09-10", affected=["ep-1"],
                   createdAt="2026-09-10T00:00:00Z"))
    return g


def test_a_send_back_lists_the_signature_as_waiting_and_stops_counting_it():
    """`commit.sign` refuses while a send-back stands, so the queue may not call the
    signature available: it is listed, greyed, and named as waiting on the return — and
    it is out of the count and out of `byRoute` [controller ruling, final fix round]."""
    q = needs(_sent_back_graph(), "ep-1", now=TODAY)
    assert [i["kind"] for i in q["items"] if i["actionable"]] == ["sent-back"]
    signature = next(i for i in q["items"] if i["kind"] == "signature")
    assert signature["actionable"] is False
    assert signature["unlocksAfter"] == "the send-back is answered"
    assert q["count"] == 1
    assert q["byRoute"]["/package"] == 1


def test_the_send_back_is_listed_before_the_signature_it_holds_up():
    kinds = [i["kind"] for i in needs(_sent_back_graph(), "ep-1", now=TODAY)["items"]]
    assert kinds.index("sent-back") < kinds.index("signature")


def test_by_route_counts_the_actionable_items_of_each_map_row():
    """One number per view, computed here, so the map prints a server value like every
    other numeral on screen. A `/review/{id}` item belongs to the Model row."""
    q = needs(_draft_graph(), "ep-1", now=TODAY)
    assert set(q["byRoute"]) == set(MAP_ROUTES)
    assert q["byRoute"]["/model"] == 3
    assert q["byRoute"]["/package"] == 0
    assert sum(q["byRoute"].values()) == q["count"]


def test_a_terminal_episode_reports_a_route_map_of_zeroes():
    g = complete_graph()
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "lifecycleState": "SIGNED"}, H)
    q = needs(g, "ep-1", now=TODAY)
    assert q["byRoute"] == dict.fromkeys(MAP_ROUTES, 0)
