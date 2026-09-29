"""Workspace routes (plan 2026-09-11): the clock, the activity log, the queue, send-back
and sign. Everything but the two human acts is read-only and computed at request time
from the session's copy of the record; nothing here is ever rendered into a package."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from docket.api.config import human_actor
from docket.api.serialize import episode_view, object_view
from docket.api.sessions import writing
from docket.kernel.clock import clock, describe_log_entry
from docket.kernel.commit import sign
from docket.kernel.queue import needs
from docket.kernel.refresh import signer_return

router = APIRouter()


def _now() -> str:
    """See `routes/kernel.py`'s `_now`: the one clock the API may read."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/session/{s}/episode/{e}/clock")
def get_clock(s: str, e: str, request: Request) -> dict:
    session = request.app.state.sessions.get(s)
    with session.lock:
        return clock(session.graph, e, now=_now())


@router.get("/session/{s}/activity")
def get_activity(s: str, request: Request, episode: str | None = None) -> dict:
    """Every log entry as a sentence, newest first; `?episode=` keeps only the entries
    whose object the episode reaches (plus the episode itself).

    Deliberately `reachable_from(..., reverse=False)` and not `clock._reach`: the clock
    adds every orphan gap in the store to an episode's scope, because a recorded absence
    nothing points at is still something that episode has to answer for. The log is a
    different question — "what happened to this decision" — and an absence filed against
    another episode did not happen to this one.

    An episode id the record does not hold filters nothing, rather than everything: an
    empty log would read as "nothing has happened here", which is a claim about the
    record and not about the parameter.
    """
    session = request.app.state.sessions.get(s)
    with session.lock:
        g = session.graph
        keep = None
        if isinstance(episode, str) and g.has(episode):
            keep = g.reachable_from(episode, reverse=False) | {episode}
        entries = [describe_log_entry(g, entry) for entry in g.log()
                   if keep is None or entry.get("id") in keep]
    entries.reverse()
    return {"entries": entries}


@router.get("/session/{s}/episode/{e}/needs")
def get_needs(s: str, e: str, request: Request) -> dict:
    session = request.app.state.sessions.get(s)
    with session.lock:
        return needs(session.graph, e, now=_now())


class SendBackRequest(BaseModel):
    reason: str


@router.post("/session/{s}/episode/{e}/send-back", response_model=None)
def post_send_back(s: str, e: str, body: SendBackRequest,
                   request: Request) -> dict | JSONResponse:
    """`kernel.refresh.signer_return` — the actor is the server's own configured actor,
    never anything the client sends. A signed (or not-yet-rendered) package answers 409
    by name rather than the helper's 422, because "nothing awaits a signature here" is
    a state of the record, not a malformed request. The session lock is released
    between that check and the write, so two requests can both pass it; the kernel's
    own `PENDING_SIGNATURE` check, inside the write, is what keeps the loser safe —
    it answers 422 rather than filing a second return against a package that has since
    been signed.

    `human_actor()` is called here rather than injected with `Depends(human_actor)`,
    exactly as `routes/program.py`'s `/refresh` does: a dependency is bound to the
    function object at import time, and the regression this route's own test simulates
    (an actor that is somehow not human) is only reachable — and so only provable —
    when the lookup happens on the call. The refusal itself is the kernel's
    (`AuthorityViolation` -> 403), never this route's.
    """
    session = request.app.state.sessions.get(s)
    with session.lock:
        g = session.graph
        if not g.has(e):
            raise KeyError(e)
        if g.get(e).get("lifecycleState") != "PENDING_SIGNATURE":
            return JSONResponse(status_code=409, content={
                "error": "not-pending-signature",
                "message": f"episode {e} is not awaiting a signature; nothing to send back",
            })
    with writing(session) as g:
        trigger = signer_return(g, e, actor=human_actor(), now=_now(), reason=body.reason)
        result = object_view(g, trigger["id"])
    return result


class SignRequest(BaseModel):
    selected: str
    role: str
    stopRules: list[str]
    dissent: list[dict] | None = None
    now: str | None = None


@router.post("/session/{s}/episode/{e}/sign")
def post_sign(s: str, e: str, body: SignRequest, request: Request) -> dict:
    """`kernel.commit.sign` — a person signs; the commitment binds to the full package's
    hash and the SIGNED transition is driven through the same gate as every other.

    A refusal by the gate (`TransitionRefused`) is 409 with `unsatisfied[]` through the
    app-wide handler — the same body the transition route produces — and `writing` still
    saves on that path, because the commitment and the refused attempt are both part of
    the record. The kernel's own up-front refusals (`ValidationError`: wrong state, an
    unknown option, no stop rule, no full package, a standing send-back) are 422, with
    nothing written. An unknown episode is 404, checked here as `post_send_back` does.

    `human_actor()` is called here rather than injected, for the reason `post_send_back`
    gives: the refusal of a non-human actor is the kernel's (`AuthorityViolation` -> 403),
    and it is only provable when the lookup happens on the call.
    """
    session = request.app.state.sessions.get(s)
    with session.lock:
        if not session.graph.has(e):
            raise KeyError(e)
    now = body.now or _now()
    with writing(session) as g:
        cm = sign(g, e, actor=human_actor(), now=now, selected=body.selected, role=body.role,
                  stop_rules=body.stopRules, dissent=body.dissent)
        result = {"commitment": object_view(g, cm["id"]), "episode": episode_view(g, e)}
    return result
