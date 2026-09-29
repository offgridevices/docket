"""Agent-stage routes: one route per `docket.agent.*` function, an SSE progress channel
for the two calls slow enough to need one, and the human/agent actor boundary implemented
once (plan 07 Task 3; C1/C2/I1-I6/M1-M9 are the T3 fix round).

No route here decides anything about the record. Every handler is: resolve the session,
take `writing(session)`, resolve the actor (never from the request body — see `_agent`
and `Depends(human_actor)` below), call the one agent-or-kernel function the route table
names, and return its result through `serialize.object_view`/`episode_view` or as-is. A
handler that starts growing a conditional about what the record should say belongs in
`agent/` or `kernel/`, not here.

The human actor is `docket.api.config.human_actor` — the configured actor id, read
server-side, never accepted from a client. The agent actor is derived from the resolved
backend by `_agent`, below, which is also the FastAPI dependency tests override to inject
a `RecordedBackend` without touching the network (`app.dependency_overrides[_agent] =
lambda: (RecordedBackend(...), {...})`). `/dispatch` uses a separate dependency,
`_dispatch_actor`, which derives the same actor shape from configured settings alone —
`dispatch()` never calls a backend, so this route never constructs one [ruling I3].
"""
from __future__ import annotations

import ipaddress
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import anyio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict

from docket.agent.backend import backend_from_settings, resolve_settings
from docket.agent.dispatch import dispatch, read_back
from docket.agent.elicit import elicit_into
from docket.agent.narrate import narrate
from docket.agent.plan import approve_plan, author_weight_set, propose_plan
from docket.agent.review import accept, confirm_gaps, g1_review, g1_sheet, reject
from docket.api.app import CanonicalJSONResponse, _redact
from docket.api.config import (
    LLM_API_KEY_ENV,
    RECORDED_REQUEST_POLICY,
    ConfigInvalid,
    agent_actor,
    agent_actor_for_settings,
    current_api_key,
    human_actor,
)
from docket.api.serialize import episode_view, object_view
from docket.api.sessions import default_policy_json, writing
from docket.api.stream import channels_for, sse_response
from docket.errors import PolicyRefusal
from docket.kernel.flip import flip_summary
from docket.kernel.lifecycle import transition

router = APIRouter()

#: `accept`'s `**edits` splat reaching `review.accept(g, obj_id, actor, *, now, **edits)`
#: verbatim — a client edit under any of `accept`'s own positional/keyword parameter
#: names collides as a duplicate keyword argument. Python's calling convention already
#: refuses `actor`/`now`/`g`/`obj_id` (an unhandled `TypeError`, a 500); refusing them
#: here by name turns that into a printable 400 before the call is even attempted
#: [ruling M1].
#:
#: [ruling I1, plan 07 T6 fix round] `createdBy`, `createdAt`, `confirmedBy`,
#: `approvedBy`, `authority`, `signedBy` and `lifecycleState` are the record's own
#: signature and authority fields — who did something, when, and under what authority.
#: `store.put` only checks `createdBy` against the actor it was given; nothing checked
#: `confirmedBy`, so `edits.confirmedBy` let a request body satisfy `gaps-confirmed`'s
#: own definition of "a human signed this" with a name the server never resolved — a
#: forged signature on a G1 gate check. These are blocked here for the same reason
#: `actor`/`now` are: a request body may never write who did something or when: that is
#: always the server's to say.
_RESERVED_EDIT_KEYS = frozenset({
    "g", "obj_id", "actor", "now",
    "createdBy", "createdAt", "confirmedBy", "approvedBy", "authority", "signedBy",
    "lifecycleState",
})

#: Hostnames `_is_loopback_base_url` treats as loopback without an IP-literal parse.
#: `ipaddress.ip_address("localhost")` raises `ValueError` — it is not an IP literal —
#: so it needs its own check.
_LOOPBACK_HOSTS = frozenset({"localhost"})


def _now() -> str:
    """See `routes/kernel.py`'s `_now`: the kernel and the agent stages never read a
    clock, `now` always arrives as a plain string argument, and every route module that
    needs one defines this same one-liner rather than importing another module's private
    helper."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_loopback_base_url(base_url: str) -> bool:
    """Whether `base_url`'s host is loopback or a private address.

    [ruling I6, plan 07 T3 fix round] Ollama's default (`http://localhost:11434/v1`, or
    any other on-box/on-LAN server) needs no key; a real host on the open internet
    (`https://openrouter.ai/api/v1`) does. An empty or unparsable `base_url` is treated
    as NOT loopback — refuse rather than guess.
    """
    host = urlparse(base_url).hostname or ""
    if host in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def _config_invalid(request: Request, exc: ConfigInvalid) -> CanonicalJSONResponse:
    """The same `config-invalid` shape `routes/settings.py`'s own
    `_config_invalid_response` uses for a broken config *file* — distinct from
    `policy-refusal` because an unconfigured model does not match any denylisted family
    [ruling M3, plan 07 T3 fix round]."""
    return CanonicalJSONResponse(status_code=409, content={
        "error": "config-invalid", "message": _redact(request.app, str(exc)),
    })


def _settings_for(request: Request):
    """`resolve_settings()`, with the recorded backend forced when the server is in
    recorded mode.

    `app.state.mode_override` is what `GET /api/health` reports as `mode`, what the
    header's `RECORDED` chip prints, and what `PUT /api/settings/mode` sets — including
    from the Intake screen's one-click "Switch to recorded" when no backend answers. Until
    this helper existed, that switch changed only the *label*: `resolve_settings()` reads
    `DOCKET_LLM_PROVIDER`/`llm.json` and knows nothing about the mode, so a machine
    configured for a live provider went on calling it while the header said `RECORDED`.
    Honesty rule 10 is explicit that the chip means "a recorded elicitation, which is not
    evidence that a live model would produce the same objects" — so the chip and the
    backend must be the same fact, and this is where they are made one.

    `mode == "live"` forces nothing: "live" means "do not fall back", not "override my
    configured provider", and a `recorded` provider chosen deliberately stays recorded.
    """
    if request.app.state.mode_override == "recorded":
        return resolve_settings(provider="recorded")
    return resolve_settings()


def _agent(request: Request) -> tuple[Any, dict] | CanonicalJSONResponse:
    """The backend this request should use, and the agent actor derived from it — or a
    409 `config-invalid`/`policy-refusal` response in place of that pair.

    The actor is derived from the backend, never accepted from the client: no route in
    this module reads `actorType` or `actorId` from a request body, so a client cannot
    forge one. Refuses (`PolicyRefusal`) a denylisted model, exactly as
    `resolve_settings()` always does; separately refuses `anthropic` specifically when no
    key is configured (in memory or in the environment), and refuses `openai-compatible`
    the same way unless its base URL is loopback or a private address [ruling I6] — a
    caller pointed at Ollama needs no key, but a caller pointed at a real host on the
    network (`openrouter.ai`) must not have its request text leave the machine before
    anything checks for one. Either refusal reaches the client as 409 through `app.py`'s
    app-wide `PolicyRefusal` handler, which already redacts the in-memory key and the
    policy's local-testing override hint (`api.app._redact`) — this function raises
    plainly and lets that one, shared handler do the redaction, rather than keeping a
    second copy of the same rule.

    [ruling M3] An empty resolved model id (`agent_actor` raising `ConfigInvalid`)
    cannot go through that same exception-class handler without also claiming to be a
    `policy-refusal`, so it is caught here and turned into the same `config-invalid`
    body `routes/settings.py` already uses for a broken config file — returned, not
    raised. Every route below that depends on `_agent` checks
    `isinstance(agent, CanonicalJSONResponse)` and returns it unchanged in that case,
    the same way FastAPI passes through any other route function's own early response.

    A FastAPI dependency, not a plain helper: tests override it directly
    (`app.dependency_overrides[_agent] = lambda: (RecordedBackend(...), actor)`) to
    inject a specific recorded fixture per call, without a live network path anywhere in
    the test suite.
    """
    settings = _settings_for(request)
    key = current_api_key(request)
    if settings.provider == "anthropic" and not key:
        raise PolicyRefusal(
            f"no API key configured for provider {settings.provider!r}: set "
            f"{LLM_API_KEY_ENV}, or PUT /api/settings/key, before calling an agent stage"
        )
    if settings.provider == "openai-compatible" and not key \
            and not _is_loopback_base_url(settings.base_url):
        host = urlparse(settings.base_url).hostname or settings.base_url or "(no base URL)"
        raise PolicyRefusal(
            f"{host!r} requires an API key: set {LLM_API_KEY_ENV}, or "
            f"PUT /api/settings/key, before calling an agent stage"
        )
    backend = backend_from_settings(settings, api_key=key)
    try:
        actor = agent_actor(backend)
    except ConfigInvalid as exc:
        return _config_invalid(request, exc)
    return backend, actor


def _dispatch_actor(request: Request) -> dict | CanonicalJSONResponse:
    """The agent actor for `/dispatch` alone, derived from `resolve_settings()` with no
    backend ever constructed [ruling I3, plan 07 T3 fix round] — see
    `config.agent_actor_for_settings` for the full rationale. `resolve_settings()` itself
    already enforces the denylist (`check_model_policy`); nothing here needs a key, a
    reachable base URL, or any network access at all.
    """
    settings = _settings_for(request)
    try:
        return agent_actor_for_settings(settings)
    except ConfigInvalid as exc:
        return _config_invalid(request, exc)


def _channel_for(request: Request, session_id: str):
    return channels_for(request).get(session_id)


def _summary_of(obj: dict) -> str:
    """A one-line, presentational-only label for an SSE `object` event — not what a
    reviewer reads to decide anything (that is `g1_review`'s own, richer `_summary`);
    this exists only so a chip has a caption before the caller fetches the full object
    view."""
    for field in ("name", "statement", "title", "question", "text", "sought"):
        value = obj.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(obj.get("type") or "")


# ---- the SSE channel ---------------------------------------------------------------------


@router.get("/stream/{s}")
async def get_stream(s: str, request: Request, since: int | None = None):
    """`since` omitted: a live subscription only, nothing before now replayed [ruling
    I2]. `since=<seq>`: replay every event after `seq` from the channel's bounded ring
    first (with a `dropped` event if part of that range already fell out of it), then go
    live."""
    request.app.state.sessions.get(s)  # KeyError -> 404 (global handler) if unknown
    channel = _channel_for(request, s)
    return sse_response(channel, request, since=since)


# ---- elicit --------------------------------------------------------------------------------


class ElicitRequest(BaseModel):
    requestText: str
    sourceArtifact: str
    sourceTitle: str | None = None
    # [ruling C2, plan 07 T3 fix round] Required and non-blank — see `post_elicit`. A
    # missing key is a 422 naming the field (pydantic); a present-but-blank one is a 422
    # from `elicit()`'s own guard ("requested_by must not be blank"). Never defaulted to
    # the operator's own actor id: `Charter.authority.signer` is a claim about who asked
    # for the trade study, and an operator opening a demo session is not that.
    requestedBy: str
    episodeId: str | None = None
    asOf: str | None = None
    policyId: str | None = None
    now: str | None = None


@router.post("/session/{s}/elicit")
async def post_elicit(s: str, body: ElicitRequest, request: Request,
                       agent: tuple[Any, dict] | CanonicalJSONResponse = Depends(_agent)) -> dict:
    """`elicit_into` in a worker thread (`anyio.to_thread.run_sync`), so the event loop
    stays free to serve a concurrent `GET /api/stream/{s}` connection while it runs.
    Emits `stage`(started) -> one `object` per DRAFT id the call wrote, in the order
    `elicit()` itself returns them (dependency order: gaps, evidence, charter,
    objectives, ...), never including the `DecisionEpisode` object itself [ruling M2] ->
    `stage`(finished) -> `done`; a raised exception emits a redacted `error` [ruling C1]
    and still propagates, so the app-wide handler still turns it into the right status
    code.
    """
    if isinstance(agent, CanonicalJSONResponse):
        return agent
    backend, actor = agent
    session = request.app.state.sessions.get(s)
    channel = _channel_for(request, s)
    now = body.now or _now()
    episode_id = body.episodeId or f"ep-{uuid.uuid4().hex[:10]}"
    policy_id = body.policyId or "pol-default"
    requested_by = body.requestedBy

    def _run() -> tuple[dict, list[str]]:
        channel.emit("stage", {"stage": "elicit", "status": "started", "detail": episode_id})
        # [ruling M5] every graph read below (building the object/episode views, the SSE
        # `object` payloads, the gap ids) happens inside `writing(session)`, i.e. while
        # `session.lock` is held — `Graph` is not thread-safe and this session may have a
        # second caller.
        with writing(session) as g:
            # [plan 07 Task 9 Part B] `tests/fixtures/recorded/elicit.json`'s committed
            # response is recorded under exactly one policy id
            # (`RECORDED_REQUEST_POLICY`, "pol-1" — `agent.elicit`'s user prompt embeds
            # it literally, so the recording key only matches a caller who elicits with
            # this exact id; see `api.config`'s own comment on the constant). No
            # session is seeded with that id at creation time — doing so
            # unconditionally in `sessions.SessionStore.create` broke
            # `test_kernel_routes.py::test_verify_reason_is_record_unchanged_
            # rendering_changed_on_demo_as_own_package` (opening Demo A would then
            # always carry one more object than the committed package was built
            # against, even for a session that never elicits anything). Seeded here
            # instead, lazily, only the first time a caller actually elicits against
            # this exact id, and by a human actor — `objects.AGENT_FORBIDDEN_TYPES`
            # refuses an agent-authored Policy ("the gate the agent is measured
            # against; it may not author its own parameters") — which keeps every
            # untouched session byte-identical and confines the one-time cost to
            # whoever actually needs it. Written before `log_before` is captured, so it
            # can never be mistaken for one of this elicitation's own DRAFT objects on
            # the SSE stream or in `objects`/`gaps` below.
            if policy_id == RECORDED_REQUEST_POLICY and not g.has(policy_id):
                h = human_actor()
                g.put({**default_policy_json(policy_id), "createdBy": h, "createdAt": now}, h)
            log_before = len(g.log())
            episode = elicit_into(
                g, backend, request_text=body.requestText, policy_id=policy_id,
                actor=actor, now=now, source_artifact=body.sourceArtifact,
                requested_by=requested_by, episode_id=episode_id, as_of=body.asOf,
                source_title=body.sourceTitle,
            )
            # [ruling M2] write order, straight off the append-only log — `elicit_into`
            # writes every object `elicit()` returned (in *its* dependency order: gaps,
            # then evidence, then Charter, Objectives, Alternatives, GroundRules,
            # Constraints, Assumptions) before writing the episode itself last; reading
            # `g.log()` rather than `sorted(g.ids())` preserves that order instead of
            # replacing it with lexicographic id order, and excluding `episode["id"]`
            # keeps the episode's own SSE `object` event from firing (it is reported
            # through `done`/`episode`, not as one more DRAFT chip).
            new_ids = [entry["id"] for entry in g.log()[log_before:]
                       if entry["id"] != episode["id"]]
            for oid in new_ids:
                obj = g.get(oid)
                created_by = obj.get("createdBy") or {}
                channel.emit("object", {
                    "id": oid, "type": obj.get("type"),
                    "authorType": created_by.get("actorType"),
                    "confidence": obj.get("confidence"),
                    "provenance": obj.get("ingestionProvenance"),
                    "summary": _summary_of(obj),
                })
            gap_ids = sorted(oid for oid in new_ids
                              if g.get(oid).get("type") == "InsufficientEvidence")
            result = {
                "episode": episode_view(g, episode["id"]),
                "objects": [object_view(g, oid) for oid in new_ids],
                "gaps": gap_ids,
            }
        return result, new_ids, episode["id"]

    try:
        result, new_ids, episode_id_done = await anyio.to_thread.run_sync(_run)
    except Exception as exc:
        # [ruling C1] the same redaction the HTTP body gets from `app.py`'s exception
        # handler — `_redact` strips the in-memory key and the policy override hint
        # before either can reach the one channel a browser holds open for the session.
        channel.emit("error", {"error": type(exc).__name__,
                               "message": _redact(request.app, str(exc))})
        raise
    channel.emit("stage", {"stage": "elicit", "status": "finished"})
    channel.emit("done", {"stage": "elicit", "ids": new_ids, "episode": episode_id_done})
    return result


# ---- G1: the review sheet and its three human actions --------------------------------------


@router.get("/session/{s}/episode/{e}/g1")
def get_g1(s: str, e: str, request: Request) -> dict:
    g = request.app.state.sessions.get(s).graph
    return g1_review(g, e)


@router.get("/session/{s}/episode/{e}/g1.md")
def get_g1_sheet(s: str, e: str, request: Request) -> PlainTextResponse:
    g = request.app.state.sessions.get(s).graph
    return PlainTextResponse(g1_sheet(g, e), media_type="text/markdown")


class AcceptRequest(BaseModel):
    edits: dict[str, Any] = {}
    now: str | None = None


_DEFAULT_ACCEPT = AcceptRequest()


@router.post("/session/{s}/object/{oid}/accept")
def post_accept(s: str, oid: str, request: Request, body: AcceptRequest = _DEFAULT_ACCEPT,
                 actor: dict = Depends(human_actor)) -> dict:
    # [ruling M1] a client edit under one of `accept`'s own parameter names would
    # otherwise reach it as a duplicate keyword argument — an unhandled 500 where a
    # printable 400 belongs. [ruling I1] the signature/authority fields are blocked for
    # a different reason: not a collision, a boundary — the message names it.
    reserved = _RESERVED_EDIT_KEYS & body.edits.keys()
    if reserved:
        raise ValueError(
            f"edits may not set {sorted(reserved)}: {sorted(reserved)} is written by "
            "the server, never by a request body"
        )
    session = request.app.state.sessions.get(s)
    now = body.now or _now()
    with writing(session) as g:
        accept(g, oid, actor, now=now, **body.edits)
        result = object_view(g, oid)  # [ruling M5] read while the lock is still held
    return result


class RejectRequest(BaseModel):
    reason: str
    reasonType: str = "out-of-scope"
    episodeId: str | None = None
    now: str | None = None


@router.post("/session/{s}/object/{oid}/reject")
def post_reject(s: str, oid: str, body: RejectRequest, request: Request,
                 actor: dict = Depends(human_actor)) -> dict:
    session = request.app.state.sessions.get(s)
    now = body.now or _now()
    with writing(session) as g:
        exclusion = reject(g, oid, actor, now=now, reason=body.reason,
                            reason_type=body.reasonType, episode_id=body.episodeId)
    return exclusion


class ConfirmGapsRequest(BaseModel):
    now: str | None = None


_DEFAULT_CONFIRM_GAPS = ConfirmGapsRequest()


@router.post("/session/{s}/episode/{e}/confirm-gaps")
def post_confirm_gaps(s: str, e: str, request: Request,
                       body: ConfirmGapsRequest = _DEFAULT_CONFIRM_GAPS,
                       actor: dict = Depends(human_actor)) -> dict:
    session = request.app.state.sessions.get(s)
    now = body.now or _now()
    with writing(session) as g:
        confirmed = confirm_gaps(g, e, actor, now=now)
    return {"confirmed": confirmed}


class TransitionRequest(BaseModel):
    to: str
    now: str | None = None


@router.post("/session/{s}/episode/{e}/transition")
def post_transition(s: str, e: str, body: TransitionRequest, request: Request,
                     actor: dict = Depends(human_actor)) -> dict:
    """`kernel.lifecycle.transition` — a refusal (`TransitionRefused`) is 409 with
    `unsatisfied[]` via the app-wide handler; `sessions.writing` still saves the graph
    on that path, because the refused attempt is itself part of the record."""
    session = request.app.state.sessions.get(s)
    now = body.now or _now()
    with writing(session) as g:
        transition(g, e, body.to, actor, now=now)
        result = episode_view(g, e)  # [ruling M5] read while the lock is still held
    return result


# ---- weights: the human value judgement propose_plan needs -------------------------------


class WeightsRequest(BaseModel):
    name: str
    weights: dict[str, float]
    rationale: str | None = None
    now: str | None = None


@router.post("/session/{s}/episode/{e}/weights")
def post_author_weights(s: str, e: str, body: WeightsRequest, request: Request,
                        actor: dict = Depends(human_actor)) -> dict:
    """`agent.plan.author_weight_set` — human only, exactly like `accept`/`reject`/
    `confirm-gaps`/`transition` above: the actor is the server's own configured actor
    (`Depends(human_actor)`), never accepted from the body. A validation failure (a
    missing/extra objective, a negative weight, a sum off by more than the kernel's own
    tolerance) is 422 via the app-wide `ValidationError` handler, naming the failing
    rule — `author_weight_set` reuses `kernel.evaluate.check_weights` rather than
    keeping a second copy of it, so this route's 422 body is the kernel's own wording.
    A second call for the same episode supersedes the one `WeightSet` this route ever
    writes as a new revision (see `author_weight_set`'s own docstring) — the response
    is always `object_view` of that one id, current revision.
    """
    session = request.app.state.sessions.get(s)
    now = body.now or _now()
    with writing(session) as g:
        ws = author_weight_set(g, e, actor, now=now, name=body.name, weights=body.weights,
                               rationale=body.rationale)
        result = object_view(g, ws["id"])  # [ruling M5] read while the lock is still held
    return result


# ---- plan (G2) -----------------------------------------------------------------------------


class ProposePlanRequest(BaseModel):
    planId: str | None = None
    now: str | None = None


_DEFAULT_PROPOSE_PLAN = ProposePlanRequest()


@router.post("/session/{s}/episode/{e}/plan")
def post_propose_plan(s: str, e: str, request: Request,
                       body: ProposePlanRequest = _DEFAULT_PROPOSE_PLAN,
                       agent: tuple[Any, dict] | CanonicalJSONResponse = Depends(_agent)) -> dict:
    if isinstance(agent, CanonicalJSONResponse):
        return agent
    backend, actor = agent
    session = request.app.state.sessions.get(s)
    now = body.now or _now()
    with writing(session) as g:
        plan = propose_plan(backend, g, e, actor=actor, now=now, plan_id=body.planId)
    return plan


class ApprovePlanRequest(BaseModel):
    now: str | None = None


_DEFAULT_APPROVE_PLAN = ApprovePlanRequest()


@router.post("/session/{s}/plan/{p}/approve")
def post_approve_plan(s: str, p: str, request: Request,
                       body: ApprovePlanRequest = _DEFAULT_APPROVE_PLAN,
                       actor: dict = Depends(human_actor)) -> dict:
    session = request.app.state.sessions.get(s)
    now = body.now or _now()
    with writing(session) as g:
        plan = approve_plan(g, p, actor, now=now)
    return plan


# ---- dispatch (X) ---------------------------------------------------------------------------


class DispatchRequest(BaseModel):
    seed: int = 0
    now: str | None = None


_DEFAULT_DISPATCH = DispatchRequest()


@router.post("/session/{s}/plan/{p}/dispatch")
async def post_dispatch(s: str, p: str, request: Request,
                         body: DispatchRequest = _DEFAULT_DISPATCH,
                         actor: dict | CanonicalJSONResponse = Depends(_dispatch_actor)) -> dict:
    """`dispatch()` (agent actor) -> `flip_summary` per run -> the `EVALUATED`
    transition, driven by the human actor exactly as `agent.dispatch`'s own module
    docstring requires ("Plan 07's stage flow must call ... itself after a successful
    dispatch, or the Readiness screen sits behind a gate nobody drove"). Each step
    reports an SSE `stage`; a refusal at any step (an unapproved plan, an episode not yet
    at G2) emits a redacted `error` [ruling C1] and propagates — `dispatch()` raises
    before writing anything in that case, so nothing here needs to unwind a partial
    computation.

    [ruling I3] This route never resolves or instantiates an LLM backend: `dispatch()`
    is pure kernel arithmetic behind the agent actor's name, and gating it on a backend
    (a key, a reachable base URL) coupled the deterministic compute path's failure mode
    to the LLM configuration. `actor` comes from `_dispatch_actor`, derived from
    configured settings alone.
    """
    if isinstance(actor, CanonicalJSONResponse):
        return actor
    session = request.app.state.sessions.get(s)
    channel = _channel_for(request, s)
    now = body.now or _now()

    def _run() -> tuple[dict, dict]:
        channel.emit("stage", {"stage": "dispatch", "status": "started", "detail": p})
        # [ruling M5] `episode_view` below reads the graph while `session.lock` is still
        # held, same as every other route's post-write read.
        with writing(session) as g:
            outcome = dispatch(g, p, actor=actor, seed=body.seed, now=now)
            channel.emit("stage", {"stage": "dispatch", "status": "finished",
                                    "detail": f"{len(outcome['runs'])} run(s)"})
            channel.emit("stage", {"stage": "flip-summary", "status": "started"})
            summaries = [flip_summary(g, run["id"], seed=body.seed, now=now)
                         for run in outcome["runs"]]
            channel.emit("stage", {"stage": "flip-summary", "status": "finished"})
            channel.emit("stage", {"stage": "transition", "status": "started",
                                    "detail": "EVALUATED"})
            episode_id = g.get(p)["episode"]
            transition(g, episode_id, "EVALUATED", human_actor(), now=now)
            channel.emit("stage", {"stage": "transition", "status": "finished"})
            result = {
                "runs": outcome["runs"], "flips": outcome["flips"], "flipSummaries": summaries,
                "episode": episode_view(g, episode_id),
            }
        return result, outcome, episode_id

    try:
        result, outcome, episode_id = await anyio.to_thread.run_sync(_run)
    except Exception as exc:
        channel.emit("error", {"error": type(exc).__name__,
                               "message": _redact(request.app, str(exc))})
        raise
    channel.emit("done", {"stage": "dispatch",
                          "ids": [run["id"] for run in outcome["runs"]],
                          "episode": episode_id})
    return result


@router.get("/session/{s}/run/{r}")
def get_run(s: str, r: str, request: Request) -> dict:
    g = request.app.state.sessions.get(s).graph
    return read_back(g, r)


# ---- narrate (N) --------------------------------------------------------------------------


class NarrateRequest(BaseModel):
    # [ruling I5, plan 07 T3 fix round] `extra="forbid"`: a caller-supplied `context`
    # would bypass `rendering`'s withholding gate entirely (`narrate()`'s own docstring:
    # "Ignored when `context` is supplied directly") — the plan's body spec is `{section}`
    # only, and this route no longer accepts anything else under that name or any other.
    model_config = ConfigDict(extra="forbid")

    section: str
    now: str | None = None


@router.post("/session/{s}/episode/{e}/narrate")
def post_narrate(s: str, e: str, body: NarrateRequest, request: Request,
                  rendering: str = "unclassified",
                  agent: tuple[Any, dict] | CanonicalJSONResponse = Depends(_agent)) -> dict:
    """`agent.narrate.narrate`. A never-clean draft raises `UncitedSentenceError`, which
    the app-wide handler turns into 422 with the offending `sentence` — nothing here
    parses the message itself, `errors.py`'s structured `sentence` attribute already
    carries it (plan 07 Task 1's fix round). The context pack is always built at the
    requested `rendering` server-side — see `NarrateRequest` above."""
    if isinstance(agent, CanonicalJSONResponse):
        return agent
    backend, actor = agent
    session = request.app.state.sessions.get(s)
    now = body.now or _now()
    with writing(session) as g:
        stored = narrate(g, e, section=body.section, backend=backend, actor=actor, now=now,
                          rendering=rendering)
        result = object_view(g, stored["id"])  # [ruling M5] read while the lock is held
    return result
