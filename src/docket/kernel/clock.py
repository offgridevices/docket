"""The clock: when is it due, where has the time gone, who has it been waiting on.

Everything here is derived from timestamps the record already keeps — the episode's
first revision, its recorded transitions, and the `createdAt` of the object revision
each log entry names (the log itself carries no time) — plus two optional policy
fields: `Charter.neededBy` (a deadline) and `Policy.expectedDaysByState` (an expected
time per stage, which flags a stage when overrun and never blocks anything). Pure: `now`
is an argument; nothing is written.
"""
from __future__ import annotations

from datetime import UTC, datetime

from docket.kernel.render import latest_package
from docket.kernel.validate import orphan_gaps
from docket.objects import is_content
from docket.store import Graph

STAGE_ORDER: tuple[str, ...] = (
    "DRAFT", "MODEL_APPROVED", "PLAN_APPROVED", "EVALUATED", "PENDING_SIGNATURE", "SIGNED",
)

#: The kernel default when a Policy carries no `expectedDaysByState` (spec §3).
DEFAULT_EXPECTED_DAYS: dict[str, int] = {
    "DRAFT": 10, "MODEL_APPROVED": 5, "PLAN_APPROVED": 3, "EVALUATED": 7,
    "PENDING_SIGNATURE": 7,
}

#: The plain-language name of each state, as the queue and the clock print it.
STAGE_PLAIN: dict[str, str] = {
    "DRAFT": "drafting the model", "MODEL_APPROVED": "planning",
    "PLAN_APPROVED": "computing", "EVALUATED": "scoring",
    "PENDING_SIGNATURE": "pending signature", "SIGNED": "signed",
    "SUSPECT": "suspect", "SUPERSEDED": "superseded", "VOID": "void",
}

#: The states after which nothing is owed: a record here is neither late nor waiting on
#: anyone, so the clock reports no deadline pressure for it (review ruling, T2 fix round).
TERMINAL_STATES: frozenset[str] = frozenset({"SIGNED", "SUPERSEDED", "VOID"})

#: What passing a gate is called, keyed by the state it leads to.
GATE_VERB: dict[str, str] = {
    "MODEL_APPROVED": "approve the model", "PLAN_APPROVED": "approve the plan",
    "EVALUATED": "send it to be computed", "PENDING_SIGNATURE": "score the record",
    "SIGNED": "sign the package", "SUSPECT": "mark the episode suspect",
    "SUPERSEDED": "supersede the episode", "VOID": "abandon the episode",
}


def plain_state(state: object) -> str:
    return STAGE_PLAIN.get(str(state), str(state).lower().replace("_", " "))


def parse_timestamp(value: object) -> datetime | None:
    """`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS[.f]Z` → an aware UTC datetime; else None."""
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def days_between(start: object, end: object) -> int | None:
    a, b = parse_timestamp(start), parse_timestamp(end)
    if a is None or b is None:
        return None
    return (b.date() - a.date()).days


def _obj(g: Graph, ref: object) -> dict | None:
    if not isinstance(ref, str) or not g.has(ref):
        return None
    o = g.get(ref)
    return o if isinstance(o, dict) else None


def _episode(g: Graph, episode_id: str) -> dict:
    ep = _obj(g, episode_id)
    if ep is None or ep.get("type") != "DecisionEpisode":
        raise KeyError(episode_id)
    return ep


def _reach(g: Graph, episode_id: str) -> set[str]:
    return {episode_id} | g.reachable_from(episode_id, reverse=False) | orphan_gaps(g)


def expected_days(g: Graph, episode: dict) -> tuple[dict[str, int], str]:
    """The expected days per state and where they came from (`"policy"` / `"default"`)."""
    charter = _obj(g, episode.get("charter"))
    policy = _obj(g, charter.get("decisionClassPolicy")) if charter else None
    field = policy.get("expectedDaysByState") if policy else None
    out = dict(DEFAULT_EXPECTED_DAYS)
    if not isinstance(field, dict) or not field:
        return out, "default"
    for state, days in field.items():
        if isinstance(days, int) and not isinstance(days, bool) and days >= 0:
            out[state] = days
    return out, "policy"


def opened_at(g: Graph, episode_id: str) -> str | None:
    """The episode's first revision's `createdAt`: every later `put` rewrites the field."""
    try:
        first = g.get(episode_id, 1)
    except KeyError:
        return None
    value = first.get("createdAt")
    return value if isinstance(value, str) else None


def stage_entries(g: Graph, episode: dict) -> list[dict]:
    """`[{state, enteredAt}]` — DRAFT at the first revision, then every passed transition."""
    entries = [{"state": "DRAFT", "enteredAt": opened_at(g, episode["id"])}]
    for record in episode.get("transitions") or []:
        if not isinstance(record, dict) or record.get("refused"):
            continue
        entries.append({"state": str(record.get("to")), "enteredAt": record.get("at")})
    return entries


# ---- the plain-language map the Activity view and the clock share ----------------------


def _previous(g: Graph, oid: str, rev: object) -> dict | None:
    if not isinstance(rev, int) or rev <= 1:
        return None
    try:
        return g.get(oid, rev - 1)
    except KeyError:
        return None


def _refused_signature(obj: dict) -> bool:
    """Does this episode revision's newest transition record a refused SIGNED attempt?"""
    records = obj.get("transitions")
    last = records[-1] if isinstance(records, list) and records else None
    return isinstance(last, dict) and last.get("to") == "SIGNED" and bool(last.get("refused"))


def _grew(prev: dict | None, obj: dict, field: str) -> bool:
    before = prev.get(field) if prev else None
    after = obj.get(field)
    n_before = len(before) if isinstance(before, list) else 0
    return isinstance(after, list) and len(after) > n_before


def _what(g: Graph, obj: dict, prev: dict | None, layer: str) -> tuple[str, bool]:
    t, oid, rev = obj.get("type"), obj.get("id"), obj.get("rev")
    if t == "DecisionEpisode":
        if rev == 1:
            return ("opened the episode", False)
        if _grew(prev, obj, "transitions"):
            last = obj["transitions"][-1]
            verb = GATE_VERB.get(str(last.get("to")), f"move to {plain_state(last.get('to'))}")
            if last.get("refused"):
                names = ", ".join(str(n) for n in last.get("checksUnsatisfied") or [])
                return (f"attempted to {verb} — refused: {names}", True)
            return (f"moved the decision to {plain_state(last.get('to'))}", False)
        for field, text in (("readiness", "recorded the readiness report"),
                            ("plan", "attached the plan")):
            if (prev or {}).get(field) != obj.get(field):
                return (text, False)
        # `commitment` moving is two different acts, and only the transition beside it
        # says which. Absent -> set is a signature being recorded. The other direction —
        # dropped, or put back to the commitment that stood before — is `commit.sign`
        # undoing its own pointer on the revision immediately after the SIGNED gate
        # refused (see `kernel/commit.py`), and calling that "recorded the commitment"
        # told a reader that the person the gate had just stopped had taken the decision
        # one row later.
        before, after = (prev or {}).get("commitment"), obj.get("commitment")
        if before != after:
            if before is not None and _refused_signature(obj):
                return ("withdrew the refused signature's commitment pointer", False)
            return ("recorded the commitment", False)
        for field, text in (("weightSets", "added a weight set"),
                            ("narratives", "added a narrative"),
                            ("runs", "attached sealed calculations"),
                            ("flipAnalyses", "attached what would change the answer")):
            if _grew(prev, obj, field):
                return (text, False)
        return ("revised the episode", False)
    if t == "Charter":
        return (("wrote the charter" if layer == "human" else "drafted the charter")
                if rev == 1 else "revised the charter", False)
    if t == "InsufficientEvidence":
        if is_content(obj.get("confirmedBy")) and not is_content((prev or {}).get("confirmedBy")):
            return (f"confirmed the recorded absence {oid}", False)
        return ("recorded an absence" if rev == 1 else f"revised the absence {oid}", False)
    if t == "Exclusion":
        target = obj.get("target") if isinstance(obj.get("target"), dict) else {}
        return (f"left out {target.get('label', oid)} ({obj.get('reasonType')})", False)
    if t == "Plan":
        if is_content(obj.get("approvedBy")) and not is_content((prev or {}).get("approvedBy")):
            return ("approved the plan", False)
        return ("proposed the plan" if rev == 1 else "revised the plan", False)
    if t == "WeightSet":
        return ("wrote the weights" if rev == 1 else "revised the weights", False)
    if t == "EvaluationRun":
        return (f"sealed a calculation ({oid})", False)
    if t == "Result":
        return ("recorded a result", False)
    if t == "FlipAnalysis":
        return ("computed what would change the answer", False)
    if t == "ReadinessReport":
        n = len(obj.get("blockers") or [])
        return (f"scored the record: {'ready' if obj.get('ready') else 'not ready'}, "
                f"{n} blocking", False)
    if t == "StandardsAssessment":
        return ("rated the record against the standard", False)
    if t == "MandateScorecard":
        return ("scored the mandate", False)
    if t == "DecisionPackage":
        return (f"rendered the package ({obj.get('rendering')})", False)
    if t == "Commitment":
        return ("signed the package", False)
    if t == "RefreshTrigger":
        if obj.get("kind") == "signer-return":
            return (f"sent the package back: {obj.get('description')}", False)
        return (f"filed a reason to look again ({obj.get('kind')})", False)
    if t == "EpisodeDiff":
        return (f"compared {obj.get('from')} with {obj.get('to')}", False)
    if t == "DecisionProgram":
        return ("opened the programme" if rev == 1 else "updated the programme", False)
    if t == "Policy":
        return ("set the policy", False)
    if t == "Narrative":
        return (f"drafted a narrative for {obj.get('section')}", False)
    if rev == 1:
        return ((f"drafted {t} {oid}" if layer == "agent" else f"wrote {t} {oid}"), False)
    if layer == "human":
        return (f"agreed with {t} {oid}", False)
    return (f"revised {t} {oid}", False)


def describe_log_entry(g: Graph, entry: dict) -> dict:
    """One log entry as a person reads it. `at` is the named revision's own `createdAt`."""
    oid, rev = entry.get("id"), entry.get("rev")
    actor = entry.get("actor") if isinstance(entry.get("actor"), dict) else {}
    layer = str(actor.get("actorType") or "kernel")
    try:
        obj = g.get(oid, rev) if isinstance(oid, str) else {}
    except KeyError:
        obj = {}
    what, refused = _what(g, obj, _previous(g, oid, rev), layer) if obj else \
        (f"wrote {entry.get('type')} {oid}", False)
    return {
        "seq": entry.get("seq"), "id": oid, "type": entry.get("type"), "rev": rev,
        "at": obj.get("createdAt") if isinstance(obj.get("createdAt"), str) else None,
        "layer": layer, "actorId": str(actor.get("actorId") or ""),
        "what": what, "refused": refused,
    }


def last_human_act(g: Graph, episode_id: str) -> dict | None:
    """The newest log entry by a human that touched the episode or anything it reaches."""
    reach = _reach(g, episode_id)
    for entry in reversed(g.log()):
        actor = entry.get("actor") if isinstance(entry.get("actor"), dict) else {}
        if actor.get("actorType") != "human" or entry.get("id") not in reach:
            continue
        d = describe_log_entry(g, entry)
        if d["at"] is None:
            continue
        return {"at": d["at"], "actorId": d["actorId"], "what": d["what"],
                "id": d["id"], "rev": d["rev"]}
    return None


# ---- the three record facts the flags and the queue both read -----------------------------


def unconfirmed_gaps(g: Graph, episode_id: str) -> list[str]:
    out = []
    for oid in sorted(_reach(g, episode_id)):
        o = _obj(g, oid)
        if o is not None and o.get("type") == "InsufficientEvidence" \
                and not is_content(o.get("confirmedBy")):
            out.append(oid)
    return out


def programmes_of(g: Graph, episode_id: str) -> list[dict]:
    ep = _obj(g, episode_id) or {}
    found: dict[str, dict] = {}
    named = _obj(g, ep.get("program"))
    if named is not None and named.get("type") == "DecisionProgram":
        found[named["id"]] = named
    for prog in g.all("DecisionProgram"):
        if episode_id in (prog.get("episodes") or []):
            found[prog["id"]] = prog
    return [found[k] for k in sorted(found)]


def unopened_triggers(g: Graph, episode_id: str) -> list[str]:
    """Filed `RefreshTrigger`s on the episode's programme(s) no episode has opened."""
    opened = {e.get("refreshedBecause") for e in g.all("DecisionEpisode")}
    out: list[str] = []
    for prog in programmes_of(g, episode_id):
        for tid in prog.get("refreshTriggers") or []:
            t = _obj(g, tid)
            if t is None or tid in opened or t.get("kind") == "signer-return":
                continue
            out.append(tid)
    return sorted(set(out))


def stored_blockers(g: Graph, episode_id: str) -> list[dict]:
    ep = _obj(g, episode_id) or {}
    rr = _obj(g, ep.get("readiness"))
    if rr is None or rr.get("episode") != episode_id:
        return []
    return [b for b in (rr.get("blockers") or []) if isinstance(b, dict)]


def signed_return_triggers(g: Graph, episode_id: str) -> list[dict]:
    """Send-backs newer than the latest full package, not yet opened as a refresh.

    Both timestamps are parsed before they are compared (`parse_timestamp`), never
    compared as strings. The record writes two stamp forms — `YYYY-MM-DD` and
    `YYYY-MM-DDTHH:MM:SSZ` — and string order puts a date-only send-back *before* a
    package rendered at midnight the same day, which would hide exactly the send-back a
    signer had just filed. A package with no readable `renderedAt` is treated as no
    package at all rather than as a cut-off: `latest_package` tolerates a hand-edited
    store, and the string form of a missing value sorts above every year this record
    uses, so reading it as a cut-off dropped every send-back silently [T4].

    With a package present, a send-back whose own `createdAt` will not parse is left
    out: nothing in the record then says it is newer than the package it is supposedly
    returning.
    """
    opened = {e.get("refreshedBecause") for e in g.all("DecisionEpisode")}
    pkg = latest_package(g, episode_id, rendering="full")
    since = parse_timestamp(pkg.get("renderedAt")) if pkg else None
    out = []
    for t in g.all("RefreshTrigger"):
        if t.get("kind") != "signer-return" or episode_id not in (t.get("affected") or []):
            continue
        if t["id"] in opened:
            continue
        if since is not None:
            filed = parse_timestamp(t.get("createdAt"))
            if filed is None or filed < since:
                continue
        out.append(t)
    return out


# ---- the programme's clock: how long each episode lived, and how long since the last ------


#: AR 5-11 ¶4-2i(3): an accreditation older than three years is stale — the same rule
#: `agent.refresh_watch` files as an `elapsed-time` trigger. Kept here in months because
#: the timeline speaks in months.
ACCREDITATION_MONTHS = 36

#: The states at which the programme stops counting an episode's life. `TERMINAL_STATES`
#: (the states after which nothing is owed) is the base and is reused rather than retyped,
#: so the two can never drift; `SUSPECT` is added on top of it because the two questions
#: are different ones. A suspect episode is still owed something — the clock keeps running
#: on its deadline, which is why `SUSPECT` is not terminal there — but the programme's
#: timeline is asking when the episode stopped being the live answer, and being marked
#: suspect is exactly that date.
_CLOSED_STATES: frozenset[str] = TERMINAL_STATES | {"SUSPECT"}


def months_between(start: object, end: object) -> int | None:
    """Whole calendar months from `start` to `end` — never a division of days.

    "Three years since the last accreditation" is a calendar statement, and 36 × 30 days
    is not the same date as three years later. `None` on either stamp is `None`, the same
    answer `days_between` gives, and never a zero anyone could mistake for a measurement.
    """
    a, b = parse_timestamp(start), parse_timestamp(end)
    if a is None or b is None:
        return None
    months = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        months -= 1
    return max(months, 0)


def closed_at(g: Graph, episode_id: str) -> str | None:
    """The `createdAt` of the first revision at which the episode reached a state the
    programme treats as closed, or None while it is still open."""
    ep = g.get(episode_id)
    for rev in range(1, int(ep.get("rev", 1)) + 1):
        obj = g.get(episode_id, rev)
        if obj.get("lifecycleState") in _CLOSED_STATES:
            return obj.get("createdAt")
    return None


def programme_timing(g: Graph, program_id: str, *, now: str) -> dict | None:
    """Every number the programme timeline prints, computed here so no browser computes
    one: the days each episode lived, the whole months between consecutive episodes, the
    months since the latest one, and whether that exceeds the re-accreditation clock."""
    if not g.has(program_id) or g.get(program_id).get("type") != "DecisionProgram":
        return None
    prog = g.get(program_id)
    ids = [e for e in (prog.get("episodes") or []) if isinstance(e, str) and g.has(e)]
    episodes = []
    for eid in ids:
        opened = opened_at(g, eid)
        closed = closed_at(g, eid)
        episodes.append({"id": eid, "openedAt": opened, "closedAt": closed,
                         "days": days_between(opened, closed or now),
                         "endState": g.get(eid).get("lifecycleState")})
    between = [{"from": a["id"], "to": b["id"],
                "months": months_between(a["openedAt"], b["openedAt"])}
               for a, b in zip(episodes, episodes[1:], strict=False)]
    since = None
    if episodes:
        last = episodes[-1]
        since = {"from": last["id"], "months": months_between(last["openedAt"], now)}
    overdue = bool(since and since["months"] is not None
                   and since["months"] > ACCREDITATION_MONTHS)
    return {"program": program_id, "episodes": episodes, "between": between,
            "sinceLast": since, "accreditationMonths": ACCREDITATION_MONTHS,
            "overdue": overdue}


# ---- the clock ----------------------------------------------------------------------------


def _tone(days: int, expected: int) -> str:
    if not expected or days <= expected:
        return "ok"
    return "wait" if days < expected * 1.5 else "stop"


def clock(g: Graph, episode_id: str, *, now: str) -> dict:
    """The whole clock for one episode, computed from the record and `now`.

    `dueIn`, `spanDays` and `remainingDays` are all `int | None`, and all three are
    `None` together when the charter names no `neededBy`: with no deadline there is no
    honest number for "how much time is left", and nothing this returns may be an
    estimate (review ruling, T2 fix round). A client draws the open-ended case as a
    strip that runs to today rather than to a guessed end.

    An episode in a `TERMINAL_STATES` state is never late and never stuck: its `tone` is
    `"ok"` and it carries neither an `overdue` nor a `stuck` flag. `dueIn` is still
    reported for it — the date the record was owed by is a fact about the record, and
    a signature after it is exactly what a reader may want to see.
    """
    ep = _episode(g, episode_id)
    expected, source = expected_days(g, ep)
    entries = stage_entries(g, ep)
    opened = entries[0]["enteredAt"] or now
    charter = _obj(g, ep.get("charter")) or {}
    deadline = charter.get("neededBy") if parse_timestamp(charter.get("neededBy")) else None

    stages: list[dict] = []
    for i, entry in enumerate(entries):
        start = entry["enteredAt"] or opened
        running = i == len(entries) - 1
        end = now if running else (entries[i + 1]["enteredAt"] or now)
        days = max(0, days_between(start, end) or 0)
        exp = expected.get(entry["state"], 0)
        stages.append({"state": entry["state"], "plain": plain_state(entry["state"]),
                       "enteredAt": start, "days": days, "expected": exp,
                       "running": running, "tone": _tone(days, exp)})
    current = stages[-1]
    total = max(0, days_between(opened, now) or 0)
    due_in = days_between(now, deadline) if deadline else None
    remaining = None if deadline is None else max(0, due_in or 0)
    span = None if remaining is None else max(1, total + remaining)

    act = last_human_act(g, episode_id)
    last = None
    if act is not None:
        last = {**act, "daysAgo": max(0, days_between(act["at"], now) or 0)}
        del last["id"], last["rev"]

    # "Where the record is now" is the last recorded transition, the same source every
    # other field here reads — not `lifecycleState`, which is the same state by any
    # route that wrote it.
    finished = current["state"] in TERMINAL_STATES
    overdue = not finished and due_in is not None and due_in < 0
    over_expected = bool(current["expected"]) and current["days"] > current["expected"]
    near_expected = bool(current["expected"]) and current["days"] >= 0.7 * current["expected"]
    tone = "ok"
    if finished:
        tone = "ok"
    elif overdue or over_expected:
        tone = "stop"
    elif (span is not None and total >= 0.7 * span) or near_expected:
        tone = "wait"

    flags: list[dict] = []
    if overdue:
        flags.append({"kind": "overdue", "severity": "stop",
                      "text": f"Overdue by {-due_in} days", "route": "/"})
    if last is not None and last["daysAgo"] > 0 and not finished:
        sev = "stop" if current["expected"] and last["daysAgo"] > current["expected"] else "wait"
        flags.append({"kind": "stuck", "severity": sev,
                      "text": f"No one has acted for {last['daysAgo']} days", "route": "/"})
    n_block = len(stored_blockers(g, episode_id))
    if n_block:
        flags.append({"kind": "blocking", "severity": "stop", "route": "/readiness",
                      "text": f"{n_block} "
                              f"{'finding stops' if n_block == 1 else 'findings stop'} "
                              "sign-off"})
    n_gaps = len(unconfirmed_gaps(g, episode_id))
    if n_gaps:
        flags.append({"kind": "absences", "severity": "wait", "route": "/",
                      "text": f"{n_gaps} {'absence' if n_gaps == 1 else 'absences'} unconfirmed"})
    if unopened_triggers(g, episode_id):
        flags.append({"kind": "refresh", "severity": "wait", "route": "/timeline",
                      "text": "A refresh trigger is filed and not opened"})
    if deadline is None:
        flags.append({"kind": "no-deadline", "severity": "ok", "route": "/request",
                      "text": "No deadline set"})

    return {
        "episode": episode_id, "now": now, "openedAt": opened, "deadline": deadline,
        "expectedSource": source, "stages": stages,
        "current": {"state": current["state"], "plain": current["plain"],
                    "days": current["days"], "expected": current["expected"]},
        "lastHumanAct": last, "dueIn": due_in, "spanDays": span, "remainingDays": remaining,
        "tone": tone, "flags": flags,
    }


__all__ = [
    "ACCREDITATION_MONTHS", "DEFAULT_EXPECTED_DAYS", "GATE_VERB", "STAGE_ORDER",
    "STAGE_PLAIN", "TERMINAL_STATES",
    "clock", "closed_at",
    "days_between", "describe_log_entry", "expected_days", "last_human_act",
    "months_between", "opened_at", "parse_timestamp", "plain_state", "programme_timing",
    "programmes_of",
    "signed_return_triggers", "stage_entries", "stored_blockers", "unconfirmed_gaps",
    "unopened_triggers",
]
