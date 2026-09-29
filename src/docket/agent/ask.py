"""Ask about this decision (spec §7): answers and navigates, never writes.

Nine intents are answered deterministically from the same code paths the queue, the
clock, the readiness report and the flip summary already use — the same numbers, never
a second computation. A question no intent matches may be sent to the configured model
(the route decides whether one is reachable); its reply must cite object ids and pass
the renderer's own citation check, or it is replaced by `FALLBACK_SENTENCE`. Nothing
in this module calls the store's write path.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from docket.canon import canonical_json
from docket.errors import BackendError, PolicyRefusal
from docket.kernel.clock import (
    _reach,
    clock,
    describe_log_entry,
    parse_timestamp,
    plain_state,
    unconfirmed_gaps,
)
from docket.kernel.queue import needs
from docket.kernel.render import check_citations
from docket.objects import is_content
from docket.store import Graph

SUGGESTED_QUESTIONS: tuple[str, ...] = (
    "What is blocking this right now?",
    "Was the consequences field filled in?",
    "What changed since yesterday?",
    "Where do I approve the plan?",
    "What would change the answer?",
    "Explain “an assumption the answer depends on”",
    "How long has this been sitting?",
    "When is this due?",
    "Why is it late?",
)

FALLBACK_SENTENCE = "I can only answer from this decision's record; try one of these."

#: Keyword rules, tried in order; the first match wins.
INTENT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("why-late", re.compile(r"\blate\b|\bslow\b|why.*(long|delay)|where.*time", re.I)),
    ("how-long", re.compile(r"how long|sitting|stuck|waited|time in stage", re.I)),
    ("due", re.compile(r"\bdue\b|deadline|by when|when is (this|it)", re.I)),
    ("blocking", re.compile(r"block|\bstop|refus|holding|in the way|what.*(need|wait)", re.I)),
    ("consequences", re.compile(r"consequence|charter field|three fields|filled in", re.I)),
    ("changed", re.compile(r"chang.*(since|yesterday|last)|what.*new|what happened"
                           r"|anything happened", re.I)),
    ("where-approve", re.compile(r"where.*(approve|sign|do i)|approve the plan"
                                 r"|how do i approve", re.I)),
    ("what-flips", re.compile(r"change the answer|flip|sensitiv|what if", re.I)),
    ("explain-linchpin", re.compile(r"assumption the answer depends|linchpin|explain", re.I)),
)

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["paragraphs", "cites"],
    "properties": {
        "paragraphs": {"type": "array", "minItems": 1,
                       "items": {"type": "string", "minLength": 1}},
        "cites": {"type": "array", "minItems": 1,
                  "items": {"type": "string", "minLength": 1}},
    },
}

_SYSTEM = (
    "You read one decision record and answer questions about it. You may only state "
    "what the context holds. Every numeral you write must appear as a value inside an "
    "object you cite. Cite object ids in `cites`. You never propose a number, a rating, "
    "a run, a commitment or a lifecycle state, and you never claim to have changed "
    "anything. Answer in short plain paragraphs. Return only JSON."
)


def route_intent(question: str) -> str | None:
    text = question.strip()
    for name, pattern in INTENT_RULES:
        if pattern.search(text):
            return name
    return None


def _obj(g: Graph, ref: object) -> dict | None:
    if not isinstance(ref, str) or not g.has(ref):
        return None
    o = g.get(ref)
    return o if isinstance(o, dict) else None


def _act(label: str, route: str) -> dict:
    return {"label": label, "route": route}


def _answer(paragraphs: list[str], cites: list[str], actions: list[dict]) -> dict:
    return {"paragraphs": paragraphs, "cites": sorted(set(cites)), "actions": actions}


def fallback() -> dict:
    # The chip's own text is the query value, so it has to be percent-encoded: every
    # suggested question carries spaces and most carry a `?` or a curly quote, and an
    # unencoded one truncates the link at the first `?` or breaks it at the first space.
    return {"paragraphs": [FALLBACK_SENTENCE], "cites": [],
            "actions": [_act(q, f"/ask?q={quote(q)}") for q in SUGGESTED_QUESTIONS[:4]]}


# ---- the nine intents -------------------------------------------------------------------


def _blocking(g: Graph, eid: str, now: str) -> dict:
    """The header's `blocking` counter, in a sentence.

    The number printed is `blocking.count` — the findings and checks that stop this
    decision — and never `len(items)`, which is the number of *rows* after grouping: five
    rules can stand for a hundred and forty-six findings, and the chat and the counter must
    not disagree about how many things stop the same decision [controller ruling, final fix
    round]. The wording follows the counter's own: findings and checks.
    """
    q = needs(g, eid, now=now)
    items = q["blocking"]["items"]
    if not items:
        n = q["count"]
        return _answer([f"Nothing is blocking this decision. {n} "
                        f"thing{'' if n == 1 else 's'} {'is' if n == 1 else 'are'} "
                        "waiting on a person."],
                       [eid], [_act("Open what needs you", "/")])
    lines = [f"{b['message']} ({b['rule']})" for b in items]
    cites = [o for b in items for o in b["objects"]] or [eid]
    return _answer([f"{q['blocking']['count']} findings and checks stop this decision "
                    "moving on right now:", *lines],
                   cites, [_act("Go to the first one", items[0]["route"]),
                           _act("Open what needs you", "/")])


def _consequences(g: Graph, eid: str, now: str) -> dict:
    ep = g.get(eid)
    ch = _obj(g, ep.get("charter"))
    if ch is None:
        return _answer(["This episode names no charter."], [eid],
                       [_act("File the request", "/request")])
    value = ch.get("consequencesOfErroneousOutput")
    cites = [ch["id"]]
    if is_content(value):
        return _answer(["Yes. The charter's field for what happens if the answer is wrong "
                        "holds text a person wrote, so the model gate no longer refuses on "
                        "charter-three-fields."],
                       cites, [_act("Open the charter", "/model"),
                               _act("Open the stored object", f"/model?raw={ch['id']}")])
    if isinstance(value, dict) and isinstance(value.get("$gap"), str):
        cites.append(value["$gap"])
    return _answer(["No. Of the charter's three fields, the one asking what happens if the "
                    "answer is wrong is empty. The record holds an absence saying the source "
                    "never states it, so a person has to write it at the gate."],
                   cites, [_act("Write the field", f"/review/{ch['id']}")])


#: How many log entries the "what changed" answer prints.
_CHANGED_ENTRIES = 4


def _changed(g: Graph, eid: str, now: str, since: str | None = None) -> dict:
    """The newest entries in *this episode's* history, optionally only those since a date.

    The log is session-wide and a session may hold several episodes, so the entries are
    filtered through the same reachability `clock.last_human_act` uses before they are
    sliced — otherwise a five-episode session answers "what changed here?" with another
    decision's work. `since`, when the caller supplies one, is compared as a parsed
    timestamp and never as a string: the record writes both `YYYY-MM-DD` and
    `YYYY-MM-DDTHH:MM:SSZ`, and string order puts a date-only stamp before a stamp at
    midnight the same day. An entry whose revision carries no readable timestamp cannot
    be shown to be newer than `since`, so it is left out whenever a cut-off is in force.
    """
    reach = _reach(g, eid)
    cut = parse_timestamp(since) if since else None
    described = []
    for entry in g.log():
        if entry.get("id") not in reach:
            continue
        d = describe_log_entry(g, entry)
        if cut is not None:
            at = parse_timestamp(d["at"])
            if at is None or at < cut:
                continue
        described.append(d)
    recent = described[-_CHANGED_ENTRIES:][::-1]
    if not recent:
        text = ("Nothing has happened on this decision since then." if since
                else "Nothing has happened on this decision yet.")
        return _answer([text], [eid], [_act("File the request", "/request")])
    lines = [f"{d['at'] or '—'} · {d['actorId']} — {d['what']}" for d in recent]
    cites = [d["id"] for d in recent if g.has(d["id"])] or [eid]
    # No count in the heading: how many entries this answer shows is a choice this
    # function made, not a value the record holds, and every numeral an answer prints
    # has to be one a cited object (or the clock) can be checked against.
    return _answer(["The most recent entries on this decision, newest first:", *lines],
                   cites, [_act("Open the activity log", "/activity")])


def _where_approve(g: Graph, eid: str, now: str, question: str) -> dict:
    ep = g.get(eid)
    if re.search(r"sign", question, re.I) or ep.get("lifecycleState") == "PENDING_SIGNATURE":
        return _answer(["Signing happens on the Package view, at the bottom, where the "
                        "commitment block is. It is the last human act on this decision, and "
                        "sending it back with a named reason sits beside it."],
                       [eid], [_act("Open the package", "/package")])
    note = ""
    if ep.get("lifecycleState") == "DRAFT":
        state = plain_state(ep.get("lifecycleState"))
        note = (f" It is not open yet: the decision is still {state}, and the model gate "
                "comes first.")
    return _answer(["On the Plan view. You write the weights with a reason on each, read the "
                    "steps the AI proposed, and the gate-two checklist there passes the "
                    "decision to PLAN_APPROVED." + note],
                   [eid], [_act("Open the plan", "/plan")])


def _what_flips(g: Graph, eid: str, now: str) -> dict:
    ep = g.get(eid)
    rr = _obj(g, ep.get("readiness"))
    ranked = (rr or {}).get("flipSummary", {}).get("ranked") or []
    flip = _obj(g, ranked[0]) if ranked else None
    if flip is None:
        return _answer(["Nothing has been computed yet, so there is nothing that could change "
                        "the answer. The model gate and the plan gate come first."],
                       [eid], [_act("Open what needs you", "/")])
    label = flip.get("parameter", {}).get("label", flip["id"])
    cites = [flip["id"], str(flip.get("run"))]
    # `flipThreshold` and `flipDistance` are both nullable, and `flip.flip_summary` ranks
    # a null distance last rather than dropping it — so when every flip is null the top
    # of the ranking is one. There is then no threshold and no distance to state, and
    # printing the literal `None` would read as a value. `render.py`'s flip table prints
    # `—` for the same two nulls; an answer says it in words instead.
    if flip.get("flipDistance") is None or flip.get("flipThreshold") is None:
        return _answer([f"Nothing the record puts a range on changes which option comes "
                        f"first. The closest input is {label}, and within the range the "
                        f"record holds for it the ranking never turns over, so there is no "
                        f"threshold to name."],
                       [*cites, eid],
                       [_act("Open what would change the answer", "/compute")])
    parts = [f"The input closest to changing which option comes first is {label}: it stands "
             f"at {flip.get('currentValue')} and the ranking would change at "
             f"{flip.get('flipThreshold')} ({flip.get('direction')}) — a distance of "
             f"{flip.get('flipDistance')}."]
    if isinstance(flip.get("assumption"), str):
        parts.append(f"That input is bound to the assumption {flip['assumption']}.")
        cites.append(flip["assumption"])
    return _answer(parts, cites, [_act("Open what would change the answer", "/compute")])


def _explain_linchpin(g: Graph, eid: str, now: str) -> dict:
    ep = g.get(eid)
    linchpins = [a for a in (ep.get("assumptions") or [])
                 if (_obj(g, a) or {}).get("linchpin") is True]
    # No count: the number of linchpins is not a value anything published — it is the
    # length of a list this function filtered — and every numeral in an answer is supposed
    # to be a number the record already holds [controller ruling, final fix round]. The
    # citations name them instead, and each one opens the assumption itself.
    text = ("An assumption the answer depends on — the record calls it a linchpin. If it "
            "turns out to be wrong the ranking does not shift a little, it inverts. "
            + ("This decision names none."
               if not linchpins else
               "Every linchpin on this decision is cited below, and none may go unread "
               "past the model gate."))
    actions = [_act("Read the first one", f"/review/{linchpins[0]}")] if linchpins else []
    actions.append(_act("Turn Explain on", "/?explain=1"))
    return _answer([text], linchpins or [eid], actions)


def _how_long(g: Graph, eid: str, now: str) -> dict:
    c = clock(g, eid, now=now)
    cur, last = c["current"], c["lastHumanAct"]
    parts = [f"It has been {cur['days']} days in {cur['plain']}"
             + (f", against an expected {cur['expected']}." if cur["expected"] else ".")]
    if last:
        parts.append(f"The last act by a person was “{last['what']}”, "
                     f"{last['daysAgo']} days ago, by {last['actorId']}.")
    return _answer(parts, [eid], [_act("Open the clock card", "/#clock"),
                                  _act("Open what needs you", "/")])


def _due(g: Graph, eid: str, now: str) -> dict:
    c = clock(g, eid, now=now)
    if c["dueIn"] is None:
        return _answer(["No deadline is set on this decision. The request step is where a "
                        "person sets one."], [eid],
                       [_act("Set a deadline", "/request?step=2"),
                        _act("Open the clock card", "/#clock")])
    if c["dueIn"] < 0:
        text = f"It was due {c['deadline']} and is overdue by {-c['dueIn']} days."
    else:
        text = f"Due {c['deadline']}, in {c['dueIn']} days."
    return _answer([text + f" It was opened on {c['openedAt']}."], [eid],
                   [_act("Open the clock card", "/#clock")])


def _why_late(g: Graph, eid: str, now: str) -> dict:
    c = clock(g, eid, now=now)
    over = [s for s in c["stages"] if s["expected"] and s["days"] > s["expected"]]
    if not over:
        return _answer(["Nothing is over its expected time."], [eid],
                       [_act("Open the clock card", "/#clock")])
    worst = max(over, key=lambda s: s["days"] - s["expected"])
    parts = [f"The stage that took the most time against its expected time is {worst['plain']}: "
             f"{worst['days']} days against {worst['expected']}"
             + (", and it is still running." if worst["running"] else ".")]
    if c["lastHumanAct"] and c["lastHumanAct"]["daysAgo"] > 0:
        parts.append(f"Nothing has happened for {c['lastHumanAct']['daysAgo']} days.")
    parts.append("The expected time per stage is a policy setting; it flags, it never blocks.")
    return _answer(parts, [eid], [_act("Open the clock card", "/#clock"),
                                  _act("Open what needs you", "/")])


def answer(g: Graph, episode_id: str, question: str, *, now: str,
           since: str | None = None) -> dict | None:
    """A deterministic answer for a matched intent, else None.

    `since` is the caller's cut-off for "what changed"; every other intent reports the
    record as it stands and ignores it.
    """
    intent = route_intent(question)
    if intent is None:
        return None
    handlers = {
        "blocking": _blocking, "consequences": _consequences,
        "what-flips": _what_flips, "explain-linchpin": _explain_linchpin,
        "how-long": _how_long, "due": _due, "why-late": _why_late,
    }
    if intent == "where-approve":
        return _where_approve(g, episode_id, now, question)
    if intent == "changed":
        return _changed(g, episode_id, now, since)
    return handlers[intent](g, episode_id, now)


# ---- the live-model path ------------------------------------------------------------------


def system_prompt() -> str:
    return _SYSTEM


def _context(g: Graph, episode_id: str, *, now: str) -> dict:
    ep = g.get(episode_id)
    rr = _obj(g, ep.get("readiness"))
    q = needs(g, episode_id, now=now)
    pack: dict[str, Any] = {
        episode_id: {"lifecycleState": ep.get("lifecycleState"), "charter": ep.get("charter"),
                     "runs": ep.get("runs"), "plan": ep.get("plan")},
        "needs": [{"kind": i["kind"], "text": i["text"], "route": i["route"]}
                  for i in q["items"] if i["actionable"]],
        "clock": clock(g, episode_id, now=now),
        "gaps": unconfirmed_gaps(g, episode_id),
    }
    if rr is not None:
        pack[rr["id"]] = {"ready": rr.get("ready"), "blockers": rr.get("blockers")}
    return pack


def user_prompt(g: Graph, episode_id: str, question: str, *, now: str) -> str:
    return (f"Question: {question}\n\nContext (the only objects and values you may cite "
            f"or quote):\n{canonical_json(_context(g, episode_id, now=now))}")


def answer_with_model(g: Graph, episode_id: str, question: str, *, backend: Any,
                      now: str) -> dict | None:
    """Ask `backend`; keep the reply only if `render.check_citations` accepts every
    paragraph against the cited objects. Any failure — no recording, a transport error,
    a policy refusal, an uncited numeral — yields None so the caller falls back."""
    try:
        reply = backend.complete_json(system=system_prompt(),
                                      user=user_prompt(g, episode_id, question, now=now),
                                      schema=ANSWER_SCHEMA)
    except (BackendError, PolicyRefusal, OSError, ValueError):
        return None
    paragraphs = [p for p in reply.get("paragraphs", []) if isinstance(p, str) and p.strip()]
    cites = [c for c in reply.get("cites", []) if isinstance(c, str)]
    if not paragraphs or not cites:
        return None
    candidate = {"sentences": [{"text": p, "cites": cites} for p in paragraphs]}
    if check_citations(g, candidate):
        return None
    return _answer(paragraphs, cites, [_act("Open what needs you", "/")])


__all__ = [
    "ANSWER_SCHEMA", "FALLBACK_SENTENCE", "INTENT_RULES", "SUGGESTED_QUESTIONS", "answer",
    "answer_with_model", "fallback", "route_intent", "system_prompt", "user_prompt",
]
