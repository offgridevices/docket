"""Program-level routes: the timeline, refresh-watch detection, and opening a refresh
(plan 07 Task 4).

`refresh` is the one write in plan 07 that reopens a model for a human to approve again
— `kernel.refresh.open_refresh` itself refuses a non-human actor
(`AuthorityViolation`), and this route only ever passes `config.human_actor()`, never
anything the client sends, so there is no way to reach it with any other actor. `/watch`
follows the same rule for anything it files: it only ever passes `human_actor()` to
`file_all`, never anything the client sends.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from docket.agent import refresh_watch
from docket.api.config import human_actor
from docket.api.serialize import episode_view
from docket.api.sessions import writing
from docket.kernel.clock import programme_timing
from docket.kernel.refresh import open_refresh

router = APIRouter()


def _now() -> str:
    """See `routes/kernel.py`'s `_now` — same one-line clock, same reason each route
    module that needs it defines its own rather than importing another module's
    private helper."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- timeline ------------------------------------------------------------------------


@router.get("/session/{s}/program/{p}/timeline")
def get_timeline(s: str, p: str, request: Request) -> dict:
    """Program + episodes + `EpisodeDiff`s + `RefreshTrigger`s, resolved. An unknown or
    not-yet-built program id (Demo B, or any id the graph does not resolve to a
    `DecisionProgram`) is an empty timeline, not an error — the plan's own rule for a
    degraded dependency: a missing future plan/demo must not turn a routine screen load
    into a 404.

    `timing` is `kernel.clock.programme_timing` — every number the timeline prints (the
    days each episode lived, the months between them, the months since the last one and
    the re-accreditation clock), computed here at request time against `_now()` so no
    browser does date arithmetic of its own. It is a read: nothing is written, and none
    of it is ever rendered into a package. `None` on the empty branch."""
    g = request.app.state.sessions.get(s).graph
    if not g.has(p) or g.get(p).get("type") != "DecisionProgram":
        return {"program": None, "episodes": [], "diffs": [], "refreshTriggers": [],
                "timing": None}
    program = g.get(p)
    episodes = [episode_view(g, eid) for eid in program.get("episodes") or []
                if isinstance(eid, str) and g.has(eid)]
    diffs = [g.get(d) for d in program.get("diffs") or [] if isinstance(d, str) and g.has(d)]
    triggers = [g.get(t) for t in program.get("refreshTriggers") or []
                if isinstance(t, str) and g.has(t)]
    return {"program": program, "episodes": episodes, "diffs": diffs,
            "refreshTriggers": triggers, "timing": programme_timing(g, p, now=_now())}


# ---- watch (agent.refresh_watch) ------------------------------------------------------


class WatchRequest(BaseModel):
    episodeId: str | None = None


_DEFAULT_WATCH_REQUEST = WatchRequest()


@router.post("/session/{s}/program/{p}/watch")
def post_watch(s: str, p: str, request: Request, body: WatchRequest = _DEFAULT_WATCH_REQUEST,
               file: bool = False) -> dict:
    """`agent.refresh_watch.detect` — proposals only, no envelope (no `id`/`rev`/
    `createdBy`): "Detected, not filed" until a human files them. `?file=true` calls
    `file_all`, always with `human_actor()` — never anything the client sends — so the
    agent proposes and the human files, exactly the boundary `/refresh` already draws
    for opening the refresh itself (plan 07 Task 4 follow-up, CARRY from the T8 review).

    `filed` never changes type: `[]` when `file=false` (nothing was written — `detect()`
    calls no backend and writes nothing), or the list of `RefreshTrigger` ids `file_all`
    created, in the same order as `proposals`, when `file=true`. A client checks one
    shape either way.
    """
    session = request.app.state.sessions.get(s)
    now = _now()
    proposals = refresh_watch.detect(session.graph, p, now=now, episode_id=body.episodeId)
    if not file:
        return {"proposals": proposals, "filed": []}
    with writing(session) as g:
        filed = refresh_watch.file_all(g, p, proposals, actor=human_actor(), now=now)
    return {"proposals": proposals, "filed": [t["id"] for t in filed]}


# ---- refresh ---------------------------------------------------------------------------


class RefreshRequest(BaseModel):
    triggerId: str
    replacements: dict[str, str] | None = None


@router.post("/session/{s}/program/{p}/refresh")
def post_refresh(s: str, p: str, body: RefreshRequest, request: Request) -> dict:
    session = request.app.state.sessions.get(s)
    with writing(session) as g:
        new_ep = open_refresh(g, p, body.triggerId, actor=human_actor(), now=_now(),
                               replacements=body.replacements)
    return episode_view(session.graph, new_ep["id"])
