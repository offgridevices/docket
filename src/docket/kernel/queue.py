"""What needs a person, derived from the record (spec §8).

Every item is a fact the store already holds — an unread linchpin, an unconfirmed gap,
an empty charter field, a gate whose checks all pass, a plan nobody approved, a package
nobody signed, a send-back, a filed trigger nobody opened. Nothing here is a to-do list
anyone typed; it drains as the record changes. Pure: `now` is an argument (for
`ageDays`), nothing is written, and the same graph always yields the same list.
"""
from __future__ import annotations

from docket.kernel.clock import (
    TERMINAL_STATES,
    days_between,
    opened_at,
    signed_return_triggers,
    stage_entries,
    stored_blockers,
    unconfirmed_gaps,
    unopened_triggers,
)
from docket.kernel.lifecycle import AR_5_11_FIELDS, CHECKS
from docket.kernel.render import latest_package
from docket.objects import is_content
from docket.store import Graph

#: The gate an episode sits at, by state, and the view that gate lives on.
NEXT_GATE: dict[str, tuple[str, str]] = {
    "DRAFT": ("MODEL_APPROVED", "/model"),
    "MODEL_APPROVED": ("PLAN_APPROVED", "/plan"),
    "PENDING_SIGNATURE": ("SIGNED", "/package"),
}

#: The routes the client's map has a row for (`ui/src/routes.ts`'s `VIEWS`), in map order.
#: Every one is a key of `needs.byRoute`, present at zero when nothing waits there, so the
#: map prints a server value for each of its rows and filters no list of its own.
MAP_ROUTES: tuple[str, ...] = (
    "/", "/request", "/model", "/plan", "/compute", "/readiness", "/package",
    "/evidence", "/timeline", "/activity",
)

#: Per state, the checks of the gate ahead whose satisfaction *is* the act this queue
#: already lists — so `blocking` does not count them [controller ruling, final fix round].
#: At PENDING_SIGNATURE the SIGNED gate wants `commitment-present` and
#: `commitment-package-hash`, and both are satisfied by the one act — signing — that the
#: queue lists as its `signature` item. Counting them told a reader that two things stop
#: the very act they were being asked to perform. Every other unmet check of that gate
#: still counts, and the gate ladder still reports all three: not counted is not hidden.
SELF_SATISFIED_CHECKS: dict[str, frozenset[str]] = {
    "PENDING_SIGNATURE": frozenset({"commitment-present", "commitment-package-hash"}),
}

#: The plain names of the three AR 5-11 charter fields.
CHARTER_FIELD_PLAIN: dict[str, str] = {
    "question": "the question being decided",
    "decisionToBeMade": "the decision to be made",
    "consequencesOfErroneousOutput": "what happens if this is wrong",
}

#: One "waiting for an earlier step" row per stage after the current one.
LATER: list[tuple[str, str, str, str, str]] = [
    # (state that unlocks it, kind, route, text, unlocksAfter)
    ("MODEL_APPROVED", "weights-unsaved", "/plan",
     "Write the weights, and approve the plan", "the model is approved"),
    ("PLAN_APPROVED", "dispatch", "/compute",
     "Send the record to be computed", "the plan is approved"),
    ("EVALUATED", "readiness", "/readiness",
     "Score the record and clear what stops sign-off", "the calculations are sealed"),
    ("PENDING_SIGNATURE", "signature", "/package",
     "Sign the package, or send it back with a reason", "a package is rendered"),
]
STATE_INDEX = {s: i for i, s in enumerate(
    ("DRAFT", "MODEL_APPROVED", "PLAN_APPROVED", "EVALUATED", "PENDING_SIGNATURE", "SIGNED"))}


def what_would_satisfy(check, name: str | None = None, state: str | None = None) -> str:
    """The gate's own words for what this check wants — the one definition in the repo.

    `lifecycle._tolerant` wraps every check with `functools.wraps`, so the predicate's
    docstring survives; its first line states the requirement, which is exactly "what
    would satisfy it". Taking it from there rather than writing a parallel table means the
    remedy cannot drift from the check. `agent.review` prints this same text on the G1
    sheet. A check with no docstring at all falls back to naming itself, so no caller ever
    renders a blank line; pass `name` and `state` so that fallback can say which check.
    """
    doc = getattr(check, "__doc__", None)
    first = (doc or "").strip().split("\n")[0].strip()
    return first or f"see kernel.lifecycle.CHECKS[{state!r}] entry {name!r}"


def _obj(g: Graph, ref: object) -> dict | None:
    if not isinstance(ref, str) or not g.has(ref):
        return None
    o = g.get(ref)
    return o if isinstance(o, dict) else None


def _actor(obj: dict | None) -> str | None:
    by = obj.get("createdBy") if isinstance(obj, dict) else None
    return by.get("actorType") if isinstance(by, dict) else None


def _age(created: object, now: str) -> int | None:
    d = days_between(created, now)
    return max(0, d) if d is not None else None


def _item(kind: str, text: str, *, route: str, waiting: str, now: str,
          created: object = None, object_id: str | None = None, count: int | None = None,
          item_id: str | None = None) -> dict:
    return {
        "id": item_id or (f"{kind}:{object_id}" if object_id else kind), "kind": kind,
        "text": text, "waitingOn": waiting, "route": route, "objectId": object_id,
        "ageDays": _age(created, now), "actionable": True, "count": count,
        "unlocksAfter": None,
    }


def _by_route(items: list[dict]) -> dict[str, int]:
    """How many actionable items each row of the map stands for.

    The reviewing routes (`/review/{id}`) fold into `/model`, which is where the map draws
    the model's own review work: the fold happens here so no browser has to know that a
    linchpin card belongs to the Model row. Every map route is a key even at zero, and a
    route the map has no row for is still counted under its own key rather than dropped —
    `sum(byRoute.values()) == count` is the invariant, and a silently lost item would
    break it where a reader could not see.
    """
    out = dict.fromkeys(MAP_ROUTES, 0)
    for i in items:
        if not i["actionable"]:
            continue
        route = str(i["route"])
        key = "/model" if route.startswith("/review/") else route
        out[key] = out.get(key, 0) + 1
    return out


def _stage_entered(g: Graph, ep: dict) -> object:
    entries = stage_entries(g, ep)
    return entries[-1]["enteredAt"] if entries else opened_at(g, ep["id"])


def _gate_checks(g: Graph, ep: dict, to_state: str) -> list[dict]:
    return [{"name": name, "satisfied": bool(check(g, ep)),
             "whatWouldSatisfy": what_would_satisfy(check, name, to_state)}
            for name, check in CHECKS.get(to_state, [])]


def _grouped_blockers(g: Graph, episode_id: str) -> list[dict]:
    """The stored findings that stop sign-off, one row per rule, in first-seen order.

    *Every* entry of a `ReadinessReport.blockers` stops sign-off: `readiness` computes
    `ready` as exactly "no blockers", and a finding the policy's `blockingRules` promoted
    is in that list while keeping its own `warning` or `info` severity (it carries
    `promotedBy` instead). Reading `severity` here would silently drop precisely the
    findings a policy went out of its way to make binding, so membership of the list is
    the whole test [controller ruling, T3 fix round].

    A row carries the number of findings under its rule, the union of their objects in
    first-seen order, and the first one's message.
    """
    groups: dict[str, dict] = {}
    for b in stored_blockers(g, episode_id):
        rule = str(b.get("rule"))
        row = groups.get(rule)
        if row is None:
            row = {"rule": rule, "count": 0, "objects": [],
                   "message": str(b.get("message"))}
            groups[rule] = row
        row["count"] += 1
        for o in b.get("objects") or []:
            if isinstance(o, str) and o not in row["objects"]:
                row["objects"].append(o)
    return list(groups.values())


def blocking(g: Graph, ep: dict) -> list[dict]:
    """What stops this episode moving on: `[{rule, severity, count, objects, message, route}]`.

    First the unmet checks of the gate the episode sits at — one row per check, `count` 1,
    severity `"gate"` — then the stored readiness findings, one row per rule, `count` the
    number of findings under it and `objects` the union of theirs. The header's single
    number is `blocking.count`, which is the sum of every row's `count`: one per unmet
    check plus one per stored finding, so grouping the rows never changes the number a
    reader is shown [controller ruling, T3 fix round].

    A check whose satisfaction is the act the queue already lists is left out
    (`SELF_SATISFIED_CHECKS`): an act cannot be its own obstruction.
    """
    out: list[dict] = []
    state = str(ep.get("lifecycleState"))
    self_satisfied = SELF_SATISFIED_CHECKS.get(state, frozenset())
    gate = NEXT_GATE.get(state)
    if gate:
        to_state, route = gate
        for c in _gate_checks(g, ep, to_state):
            if not c["satisfied"] and c["name"] not in self_satisfied:
                out.append({"rule": c["name"], "severity": "gate", "count": 1,
                            "objects": [], "message": c["whatWouldSatisfy"], "route": route})
    for row in _grouped_blockers(g, ep["id"]):
        out.append({**row, "severity": "blocking", "route": "/readiness"})
    return out


def needs(g: Graph, episode_id: str, *, now: str) -> dict:
    ep = _obj(g, episode_id)
    if ep is None or ep.get("type") != "DecisionEpisode":
        raise KeyError(episode_id)
    state = str(ep.get("lifecycleState"))
    # An episode in a terminal state has no pending human act (review ruling, T2 fix
    # round — the same `TERMINAL_STATES` the clock reads): signed, superseded or void,
    # there is nothing left for anyone to do on *this* record, and a successor carries
    # whatever work remains. The blocking list is still reported, for the same reason the
    # clock still reports `dueIn` for a signed record: those findings are facts about the
    # record, not acts anyone is being asked to perform.
    if state in TERMINAL_STATES:
        block = blocking(g, ep)
        return {"episode": episode_id, "count": 0, "items": [],
                "byRoute": dict.fromkeys(MAP_ROUTES, 0),
                "blocking": {"count": sum(b["count"] for b in block), "items": block}}
    items: list[dict] = []
    stage_at = _stage_entered(g, ep)

    if state == "DRAFT":
        for aid in ep.get("assumptions") or []:
            a = _obj(g, aid)
            if a is not None and a.get("linchpin") is True and _actor(a) != "human":
                items.append(_item(
                    "linchpin-unreviewed",
                    "An assumption the answer depends on has never been read by a person. "
                    "If it is wrong the ranking does not shift, it inverts.",
                    route=f"/review/{aid}", waiting="you, as the reviewer", now=now,
                    created=a.get("createdAt"), object_id=aid))
        for gid in unconfirmed_gaps(g, episode_id):
            gap = _obj(g, gid) or {}
            items.append(_item(
                "gap-unconfirmed",
                f"The record says the source never states {gap.get('sought', gid)}; "
                "a person has to confirm the silence is real.",
                route=f"/review/{gid}", waiting="you, as the reviewer", now=now,
                created=gap.get("createdAt"), object_id=gid))
        charter = _obj(g, ep.get("charter"))
        if charter is not None:
            for key in AR_5_11_FIELDS:
                if not is_content(charter.get(key)):
                    items.append(_item(
                        "charter-field-empty",
                        "One of the three fields the charter must hold is empty: "
                        f"{CHARTER_FIELD_PLAIN[key]}. The source never says it, so you must.",
                        route="/model", waiting="you, as the study lead", now=now,
                        created=charter.get("createdAt"), object_id=charter["id"],
                        item_id=f"charter-field-empty:{key}"))
        if all(c["satisfied"] for c in _gate_checks(g, ep, "MODEL_APPROVED")):
            items.append(_item("gate-1", "The model is ready to approve.", route="/model",
                               waiting="you — only a person may pass this gate", now=now,
                               created=stage_at))

    if state == "MODEL_APPROVED":
        human_ws = [w for w in (ep.get("weightSets") or []) if _actor(_obj(g, w)) == "human"]
        plan = _obj(g, ep.get("plan"))
        if not human_ws:
            items.append(_item("weights-unsaved",
                               "Weights are a value judgement a person types.",
                               route="/plan", waiting="you, as the study lead", now=now,
                               created=stage_at))
        elif plan is None:
            items.append(_item("plan-unproposed",
                               "No plan has been proposed. The AI proposes; you approve.",
                               route="/plan", waiting="you ask; the AI proposes", now=now,
                               created=stage_at))
        elif not is_content(plan.get("approvedBy")):
            items.append(_item("plan-unapproved",
                               "The AI has proposed how the comparison should be evaluated, "
                               "citing the authority it read it in. Nothing runs until a "
                               "person approves it.",
                               route="/plan", waiting="you, as the study lead", now=now,
                               created=plan.get("createdAt"), object_id=plan["id"]))
        if all(c["satisfied"] for c in _gate_checks(g, ep, "PLAN_APPROVED")):
            items.append(_item("gate-2", "The plan is approved; move the decision on so the "
                               "kernel can run.", route="/plan",
                               waiting="you — only a person may pass this gate", now=now,
                               created=stage_at))

    if state == "PLAN_APPROVED" and not ep.get("runs"):
        items.append(_item("dispatch", "Send the approved plan to the kernel.",
                           route="/compute", waiting="you press it; the kernel does it",
                           now=now, created=stage_at))

    if state == "EVALUATED" and _obj(g, ep.get("readiness")) is None:
        items.append(_item("readiness", "Score the record against the standard.",
                           route="/readiness", waiting="you press it; the kernel scores it",
                           now=now, created=stage_at))

    # One row per rule, standing for every finding under it, so `objectId` stays empty:
    # the row is about a set of objects, and the route is the readiness view that lists
    # them [controller ruling, T3 fix round].
    for row in _grouped_blockers(g, episode_id):
        items.append(_item("blocking-finding", row["message"],
                           route="/readiness", waiting="you, as the study lead", now=now,
                           created=(_obj(g, ep.get("readiness")) or {}).get("createdAt"),
                           count=row["count"], item_id=f"blocking-finding:{row['rule']}"))

    if state in ("EVALUATED", "PENDING_SIGNATURE") and _obj(g, ep.get("readiness")) \
            and latest_package(g, episode_id, rendering="full") is None:
        items.append(_item("package-unrendered", "Render the decision package.",
                           route="/package", waiting="you press it; the kernel renders it",
                           now=now, created=stage_at))

    # The send-back comes before the signature it holds up, and the signature is not
    # available while it stands: `commit.sign` refuses on exactly this predicate, so a
    # queue that called signing available would be promising an act the kernel will
    # refuse [controller ruling, final fix round]. The row is still listed — greyed, and
    # naming what unlocks it — and it is out of `count` and out of `byRoute`, like every
    # other row a person cannot act on.
    returns = signed_return_triggers(g, episode_id)
    for t in returns:
        items.append(_item("sent-back", f"Sent back by {t.get('source')}: {t.get('description')}",
                           route="/package", waiting="the analyst", now=now,
                           created=t.get("createdAt"), object_id=t["id"]))

    if state == "PENDING_SIGNATURE" and latest_package(g, episode_id, rendering="full") \
            and _obj(g, ep.get("commitment")) is None:
        signature = _item("signature",
                          "A package is rendered and nobody has taken the decision. Signing "
                          "is where a person commits, with conditions and stop rules — or "
                          "sends it back.",
                          route="/package", waiting="the decision authority", now=now,
                          created=stage_at)
        if returns:
            signature = {**signature, "actionable": False, "waitingOn": "an earlier step",
                         "unlocksAfter": "the send-back is answered"}
        items.append(signature)

    for tid in unopened_triggers(g, episode_id):
        t = _obj(g, tid) or {}
        items.append(_item("refresh-proposed",
                           "A reason to look again is filed and not opened: "
                           f"{t.get('description')}",
                           route="/timeline", waiting="the programme office", now=now,
                           created=t.get("createdAt"), object_id=tid))

    # Actionable rows only. Every row appended above is actionable but one — the signature
    # a send-back has closed — and the "waiting for an earlier step" rows below never were.
    count = sum(1 for i in items if i["actionable"])
    here = STATE_INDEX.get(state)
    if here is not None:
        for unlock_state, kind, route, text, after in LATER:
            if STATE_INDEX[unlock_state] > here:
                items.append({"id": f"later:{kind}", "kind": kind, "text": text,
                              "waitingOn": "an earlier step", "route": route, "objectId": None,
                              "ageDays": None, "actionable": False, "count": None,
                              "unlocksAfter": after})

    block = blocking(g, ep)
    return {"episode": episode_id, "count": count, "items": items,
            "byRoute": _by_route(items),
            "blocking": {"count": sum(b["count"] for b in block), "items": block}}


__all__ = ["CHARTER_FIELD_PLAIN", "MAP_ROUTES", "NEXT_GATE", "SELF_SATISFIED_CHECKS",
           "blocking", "needs", "what_would_satisfy"]
