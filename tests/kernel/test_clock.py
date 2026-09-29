"""kernel/clock.py — when is it due, where did the time go, who is it waiting on."""
import pytest

from docket.errors import TransitionRefused
from docket.kernel.clock import (
    DEFAULT_EXPECTED_DAYS,
    clock,
    days_between,
    describe_log_entry,
    expected_days,
    last_human_act,
    parse_timestamp,
    signed_return_triggers,
)
from docket.kernel.lifecycle import transition
from tests.kernel.conftest import H, charter, episode, gap, obj, policy, put_all

NOW = "2026-09-11T12:00:00Z"


def test_parse_timestamp_accepts_date_and_datetime_and_rejects_junk():
    assert parse_timestamp("2026-09-11").isoformat() == "2026-09-11T00:00:00+00:00"
    assert parse_timestamp("2026-09-11T12:00:00Z").hour == 12
    assert parse_timestamp("2026-09-11T12:00:00.5Z") is not None
    assert parse_timestamp("soon") is None
    assert parse_timestamp(None) is None


def test_days_between_is_whole_days_and_none_on_junk():
    assert days_between("2026-09-01", "2026-09-11T23:00:00Z") == 10
    assert days_between("2026-09-11", "2026-09-01") == -10
    assert days_between("x", NOW) is None


def test_expected_days_falls_back_to_the_kernel_default(base_graph):
    ep = base_graph.get("ep-1")
    expected, source = expected_days(base_graph, ep)
    assert expected == DEFAULT_EXPECTED_DAYS and source == "default"


def test_expected_days_reads_the_policy_field_when_present():
    g = put_all(
        __import__("docket.store", fromlist=["Graph"]).Graph(),
        policy(expectedDaysByState={"DRAFT": 2, "SIGNED": 0}),
        charter(), episode(),
    )
    expected, source = expected_days(g, g.get("ep-1"))
    assert source == "policy"
    assert expected["DRAFT"] == 2
    assert expected["MODEL_APPROVED"] == DEFAULT_EXPECTED_DAYS["MODEL_APPROVED"]


def test_clock_on_a_draft_episode_with_no_deadline(base_graph):
    c = clock(base_graph, "ep-1", now=NOW)
    assert c["openedAt"] == "2026-09-04T00:00:00Z"
    assert c["deadline"] is None and c["dueIn"] is None
    assert [s["state"] for s in c["stages"]] == ["DRAFT"]
    assert c["stages"][0]["running"] is True
    assert c["current"] == {"state": "DRAFT", "plain": "drafting the model",
                            "days": 7, "expected": 10}
    assert c["tone"] == "wait"          # 7 of 10 days: past 70 %
    kinds = [f["kind"] for f in c["flags"]]
    assert "no-deadline" in kinds and "stuck" in kinds
    assert c["lastHumanAct"]["daysAgo"] == 7
    # No deadline, so no honest number for how long the whole thing runs: both are null
    # rather than an estimate, and the client draws an open-ended strip to today.
    assert c["spanDays"] is None and c["remainingDays"] is None


def test_clock_stage_days_come_from_transitions_and_the_deadline_from_the_charter():
    from docket.store import Graph

    g = put_all(Graph(), policy(), charter(neededBy="2026-09-20"), episode())
    ep = g.get("ep-1")
    # A hand-written passing transition record, at the shape lifecycle writes.
    record = {"from": "DRAFT", "to": "MODEL_APPROVED", "actor": H,
              "at": "2026-09-07T00:00:00Z", "policyVersion": "0.1",
              "checksSatisfied": [], "checksUnsatisfied": [], "refused": False}
    g.put({**ep, "rev": 2, "createdBy": H, "createdAt": "2026-09-07T00:00:00Z",
           "lifecycleState": "MODEL_APPROVED", "transitions": [record]}, H)
    c = clock(g, "ep-1", now=NOW)
    assert [(s["state"], s["days"], s["running"]) for s in c["stages"]] == [
        ("DRAFT", 3, False), ("MODEL_APPROVED", 4, True)]
    assert c["deadline"] == "2026-09-20" and c["dueIn"] == 9
    assert c["stages"][0]["tone"] == "ok"
    assert "no-deadline" not in [f["kind"] for f in c["flags"]]
    assert c["spanDays"] == 16


def test_clock_overdue_is_stop_and_flagged():
    from docket.store import Graph

    g = put_all(Graph(), policy(), charter(neededBy="2026-09-01"), episode())
    c = clock(g, "ep-1", now=NOW)
    assert c["dueIn"] == -10 and c["tone"] == "stop"
    overdue = next(f for f in c["flags"] if f["kind"] == "overdue")
    assert overdue["severity"] == "stop" and "10" in overdue["text"]


def test_clock_on_a_signed_episode_is_never_late_or_stuck():
    """A signed record owes nothing: the date it was owed by is still reported, but it
    is not overdue, not stuck, and not coloured as a problem."""
    from docket.store import Graph

    g = put_all(Graph(), policy(), charter(neededBy="2026-09-01"), episode())
    ep = g.get("ep-1")
    record = {"from": "PENDING_SIGNATURE", "to": "SIGNED", "actor": H,
              "at": "2026-09-05T00:00:00Z", "policyVersion": "0.1",
              "checksSatisfied": [], "checksUnsatisfied": [], "refused": False}
    g.put({**ep, "rev": 2, "createdBy": H, "createdAt": "2026-09-05T00:00:00Z",
           "lifecycleState": "SIGNED", "transitions": [record]}, H)
    c = clock(g, "ep-1", now=NOW)
    assert c["current"]["state"] == "SIGNED"
    assert c["dueIn"] == -10                     # the date it was owed by is still a fact
    assert c["tone"] == "ok"
    kinds = [f["kind"] for f in c["flags"]]
    assert "overdue" not in kinds and "stuck" not in kinds


def test_clock_flags_unconfirmed_absences(base_graph):
    put_all(base_graph, gap("gap-1", confirmed=False),
            {**episode(), "rev": 2, "createdAt": NOW,
             "assumptions": []})
    g = base_graph
    ep = g.get("ep-1")
    # Hang the gap off the charter's consequences slot so it is in reach.
    ch = g.get("ch-1")
    g.put({**ch, "rev": 2, "createdBy": H, "createdAt": NOW,
           "consequencesOfErroneousOutput": {"$gap": "gap-1"}}, H)
    c = clock(g, ep["id"], now=NOW)
    absences = next(f for f in c["flags"] if f["kind"] == "absences")
    assert absences["severity"] == "wait" and absences["route"] == "/"


def test_last_human_act_names_the_newest_human_revision_in_reach(base_graph):
    act = last_human_act(base_graph, "ep-1")
    assert act["actorId"] == "fixture" and act["at"] == "2026-09-04T00:00:00Z"
    assert act["id"] == "ep-1"


def test_describe_log_entry_names_a_refused_gate_attempt(base_graph):
    g = base_graph
    # `base_graph` on its own passes every G1 check, so the gate has to be given
    # something real to refuse: an unconfirmed absence, which `orphan_gaps` puts in
    # scope for every episode and `gaps-confirmed` then fails on.
    put_all(g, gap("gap-1", confirmed=False))
    try:
        transition(g, "ep-1", "MODEL_APPROVED", H, now=NOW)
    except Exception:  # TransitionRefused — the refusal is recorded either way
        pass
    entry = g.log()[-1]
    d = describe_log_entry(g, entry)
    assert d["refused"] is True and d["layer"] == "human" and d["at"] == NOW
    assert d["what"].startswith("attempted to approve the model — refused:")
    assert "gaps-confirmed" in d["what"]
    assert "charter-human-accepted" not in d["what"]


# ---- plan 2026-09-11: send-backs are found by instant, not by string order -------------


def _sent_back(g, created, oid="rt-return-ep-1-1", affected="ep-1"):
    return put_all(g, obj(oid, "RefreshTrigger", kind="signer-return", source="fixture",
                          description="the conditions are not specific enough to check",
                          detectedAt=created, affected=[affected], createdAt=created))


def test_a_send_back_filed_the_day_the_package_rendered_is_still_listed():
    """A date-only stamp sorts *before* the same day's package as a string, level as an
    instant — the record writes both forms, so only the instant comparison is honest."""
    from tests.kernel.conftest import COMPLETE_NOW, complete_graph

    g = complete_graph()
    assert COMPLETE_NOW == "2026-09-04T00:00:00Z"
    _sent_back(g, created="2026-09-04")
    assert [t["id"] for t in signed_return_triggers(g, "ep-1")] == ["rt-return-ep-1-1"]


def test_a_package_with_no_readable_rendered_at_is_treated_as_no_package(monkeypatch):
    """`latest_package` tolerates a hand-edited store, so it can return a package with no
    `renderedAt`. Reading that as a cut-off would drop every send-back ever filed."""
    from tests.kernel.conftest import complete_graph

    g = complete_graph()
    _sent_back(g, created="2013-01-01")
    monkeypatch.setattr("docket.kernel.clock.latest_package",
                        lambda *a, **k: {"id": "pkg-hand-edited", "rendering": "full"})
    assert [t["id"] for t in signed_return_triggers(g, "ep-1")] == ["rt-return-ep-1-1"]


def test_a_send_back_older_than_the_latest_package_is_not_listed():
    """The cut-off's exclusion side: a return filed against a package that has since been
    re-rendered is answered by that newer package, not still outstanding."""
    from tests.kernel.conftest import complete_graph

    g = complete_graph()                       # its full package renders at 2026-09-04
    _sent_back(g, created="2026-09-03")
    assert signed_return_triggers(g, "ep-1") == []


def test_a_send_back_whose_own_stamp_will_not_parse_is_not_listed():
    """`2026-02-30` satisfies the envelope's timestamp *pattern* and is not a date, so a
    hand-edited store can hold one. Nothing in the record then says it is newer than the
    package it is returning, so it is left out rather than assumed outstanding."""
    from docket.kernel.clock import parse_timestamp as _parse
    from tests.kernel.conftest import complete_graph

    g = complete_graph()
    _sent_back(g, created="2026-02-30")
    assert _parse("2026-02-30") is None
    assert signed_return_triggers(g, "ep-1") == []


# ---- the programme's own clock: episodes, the months between, re-accreditation ---------


def test_programme_timing_on_demo_b(demo_b_graph):
    from docket.kernel.clock import ACCREDITATION_MONTHS, programme_timing

    t = programme_timing(demo_b_graph, "prg-omfv", now="2026-09-11T00:00:00Z")
    ids = [e["id"] for e in t["episodes"]]
    assert ids[0] == "ep-omfv-2020-02" and ids[-1] == "ep-omfv-2020-02-r5"
    assert all(isinstance(e["days"], int) and e["days"] >= 0 for e in t["episodes"])
    assert len(t["between"]) == len(ids) - 1
    assert all(b["months"] >= 0 for b in t["between"])
    assert t["accreditationMonths"] == ACCREDITATION_MONTHS == 36
    assert t["sinceLast"]["from"] == "ep-omfv-2020-02-r5"
    assert t["overdue"] == (t["sinceLast"]["months"] > 36)


def test_programme_timing_months_are_whole_calendar_months():
    from docket.kernel.clock import months_between

    assert months_between("2020-02-10T00:00:00Z", "2023-07-09T00:00:00Z") == 40
    assert months_between("2020-02-10T00:00:00Z", "2023-07-10T00:00:00Z") == 41
    assert months_between("junk", "2023-07-10T00:00:00Z") is None


def test_programme_timing_pins_each_episode_span_on_demo_b(demo_b_graph):
    """The closing rule against the committed store, not against itself: the first
    episode closed at the revision that made it SUPERSEDED (2020-12-09) — not at its own
    latest `createdAt`, which is three revisions and two and a half years later — and the
    live one has no closing date at all, so its days run to `now`."""
    from docket.kernel.clock import closed_at, programme_timing

    now = "2026-09-11T00:00:00Z"
    t = programme_timing(demo_b_graph, "prg-omfv", now=now)
    first, last = t["episodes"][0], t["episodes"][-1]

    assert first["openedAt"] == "2020-02-25T00:00:00Z"
    assert first["closedAt"] == "2020-12-09T00:00:00Z"
    assert first["days"] == 288
    assert first["endState"] == "SUPERSEDED"
    # The same episode was revised again long after it closed; the closing date is the
    # earlier revision's, and nothing later moves it.
    assert demo_b_graph.get("ep-omfv-2020-02")["createdAt"] == "2023-06-26T00:00:00Z"
    assert closed_at(demo_b_graph, "ep-omfv-2020-02") == "2020-12-09T00:00:00Z"

    assert last["id"] == "ep-omfv-2020-02-r5"
    assert last["closedAt"] is None
    assert last["days"] == days_between(last["openedAt"], now)

    # Whole calendar months between consecutive openings, from the committed dates:
    # 2020-02-25 → 2020-12-09 → 2021-09-30 → 2023-03-31 → 2023-06-26.
    assert [b["months"] for b in t["between"]] == [9, 9, 18, 2]


def test_the_programme_closes_an_episode_at_the_revision_that_went_suspect():
    """`SUSPECT` closes an episode for the programme although it is not one of
    `TERMINAL_STATES` — the deadline clock still runs on a suspect episode, but it has
    stopped being the live answer. A later revision does not move the closing date."""
    from docket.kernel.clock import closed_at, programme_timing
    from docket.store import Graph
    from tests.kernel.conftest import program_

    g = put_all(Graph(), policy(), charter(), episode(createdAt="2020-01-01T00:00:00Z"))
    put_all(g, {**episode(), "rev": 2, "lifecycleState": "SUSPECT",
                "createdAt": "2021-03-05T00:00:00Z"})
    put_all(g, {**episode(), "rev": 3, "lifecycleState": "SUSPECT",
                "createdAt": "2022-07-09T00:00:00Z"})
    put_all(g, program_(episodes=["ep-1"]))

    assert closed_at(g, "ep-1") == "2021-03-05T00:00:00Z"
    t = programme_timing(g, "prg-1", now=NOW)
    assert t["episodes"][0]["closedAt"] == "2021-03-05T00:00:00Z"
    assert t["episodes"][0]["days"] == days_between("2020-01-01", "2021-03-05")
    assert t["episodes"][0]["days"] != days_between("2020-01-01", NOW)


def test_an_episode_still_open_has_no_closing_date_and_lives_until_now():
    from docket.kernel.clock import closed_at, programme_timing
    from docket.store import Graph
    from tests.kernel.conftest import program_

    g = put_all(Graph(), policy(), charter(), episode(createdAt="2026-08-04T00:00:00Z"))
    put_all(g, program_(episodes=["ep-1"]))

    assert closed_at(g, "ep-1") is None
    t = programme_timing(g, "prg-1", now=NOW)
    assert t["episodes"][0]["closedAt"] is None
    assert t["episodes"][0]["days"] == days_between("2026-08-04", NOW)


def test_overdue_turns_over_at_the_accreditation_clock_and_not_before(demo_b_graph):
    """`ep-omfv-2020-02-r5` opened 2023-06-26. Exactly three years later the record is
    as old as the rule allows and is not yet stale; a month later it is."""
    from docket.kernel.clock import programme_timing

    at_36 = programme_timing(demo_b_graph, "prg-omfv", now="2026-06-26T00:00:00Z")
    at_37 = programme_timing(demo_b_graph, "prg-omfv", now="2026-07-26T00:00:00Z")
    assert at_36["sinceLast"]["months"] == 36 and at_36["overdue"] is False
    assert at_37["sinceLast"]["months"] == 37 and at_37["overdue"] is True


def test_programme_timing_is_none_for_an_id_that_is_not_a_programme(demo_b_graph):
    """The route's empty branch: an id that resolves to something else, or to nothing,
    has no programme clock — and that is not an error."""
    from docket.kernel.clock import programme_timing

    assert programme_timing(demo_b_graph, "ep-omfv-2020-02", now=NOW) is None
    assert programme_timing(demo_b_graph, "prg-not-a-thing", now=NOW) is None


# ---- the refused signature, as the Activity log reads it (plan 2026-09-11 Task 18) ------


def test_a_withdrawn_commitment_pointer_never_reads_as_a_recorded_commitment(
    two_alt_graph, tmp_path,
):
    """`commit.sign` writes THREE episode revisions when the SIGNED gate refuses: the
    commitment pointer going on, the refused attempt itself, and the pointer coming back
    off again. The last of those is a withdrawal, and the log has to say so — reading it
    as "recorded the commitment" told a reader that the person the gate had just stopped
    had taken the decision one row later.

    The refusal is provoked exactly as `tests/kernel/test_commit.py` provokes it, with a
    readiness report that says the record is not ready (`readiness-ready`); the gate that
    refuses does not change what the three revisions are or what they must read as.
    """
    from docket.kernel.commit import sign
    from docket.kernel.render import build_package
    from tests.kernel.conftest import pending_signature_and_ready

    g = pending_signature_and_ready(two_alt_graph, ready=False)
    build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path)
    with pytest.raises(TransitionRefused):
        sign(g, "ep-1", actor=H, now=NOW, selected="alt-x", role="MDA",
             stop_rules=["stop if the unit cost exceeds the ceiling"])

    said = [describe_log_entry(g, e)["what"] for e in g.log() if e.get("id") == "ep-1"]
    assert said[-3:] == [
        "recorded the commitment",
        "attempted to sign the package — refused: readiness-ready",
        "withdrew the refused signature's commitment pointer",
    ]
    assert said.count("recorded the commitment") == 1

    # The refusal is the only row in red: withdrawing the pointer is housekeeping the
    # kernel's own module does, not a second refusal.
    refused = [describe_log_entry(g, e) for e in g.log() if e.get("id") == "ep-1"][-3:]
    assert [d["refused"] for d in refused] == [False, True, False]

    # And the clock's "who acted last" reads the same sentence, not the wrong one.
    assert last_human_act(g, "ep-1")["what"] == \
        "withdrew the refused signature's commitment pointer"
