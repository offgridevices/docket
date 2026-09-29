"""Model settings: persisted provider/model/base-URL choice, an in-memory API key, the
denylist refusal path, and the live model list (plan 07 Task 2).

Nothing here is in the numeric path either — a backend choice never reaches a run, a
result, a weight or an observation. The one rule that matters more than any other in this
file: `PUT /api/settings/key` sets `app.state.api_key` and nothing else ever touches it.
It is never logged, never echoed back in a response body, and never written to a file —
`write_config` (plan 04 Task 1) accepts only `provider`/`model`/`baseUrl` and refuses a
config file that names a credential under any spelling, at any nesting depth.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from docket.agent.backend import (
    DENYLIST,
    is_denylisted,
    list_models,
    load_config,
    resolve_settings,
    write_config,
)
from docket.api.app import CanonicalJSONResponse, _redact
from docket.api.config import actor_id, current_api_key, write_actor_id
from docket.errors import BackendError, PolicyRefusal

router = APIRouter()

VALID_MODES = ("live", "recorded", "auto")
# Mirrors `backend_from_settings`'s own provider dispatch (`docket/agent/backend.py`) —
# not imported from there because that function encodes the names as literals, not a
# shared constant, and this task's file scope does not extend to adding one. [ruling M5]
# A provider this API persists must be one a backend can actually be built from; leaving
# it unvalidated meant `GET /settings/model` could report an active provider that
# `backend_from_settings` would refuse the moment anything tried to use it.
KNOWN_PROVIDERS = ("recorded", "openai-compatible", "anthropic")
# [ruling I2] The human-actor id this route accepts must never collide with the
# agent-actor convention (`agent.elicit.elicit()`/`agent_actor()`: `"agent:<model>"`) —
# a human's G1 approval written under an id that reads as an agent's would make the
# append-only record and the authority rail disagree about who approved it.
_MAX_ACTOR_ID_LEN = 128


def _resolved_model_guess() -> str:
    """Best-effort recomputation of what the model precedence would resolve to, used
    only to name a model in a 409 body when `resolve_settings()` itself refuses before
    it can return its own `BackendSettings.model` (e.g. `DOCKET_LLM_MODEL` set directly
    in the environment, to a denylisted id — bypassing this route's own PUT-time check,
    which only ever sees what a client sends through this API)."""
    try:
        cfg = load_config()
    except PolicyRefusal:
        cfg = {}
    return os.environ.get("DOCKET_LLM_MODEL") or cfg.get("model") or ""


def _policy_refusal_response(request: Request, exc: PolicyRefusal,
                             model: str | None) -> CanonicalJSONResponse:
    """A refusal that names a specific model (the one a client tried to persist, or the
    one `resolve_settings()` currently resolves to). [ruling I1, plan 07 T2 fix round]
    `_redact` (imported from `api.app`, the same function every other route's
    `PolicyRefusal` reaches through the app-wide handler) strips both the in-memory key
    and the policy's local-testing override hint — one implementation, not a local copy
    of the same rule that can silently stop matching a reworded message in `backend.py`.
    """
    return CanonicalJSONResponse(status_code=409, content={
        "error": "policy-refusal",
        "model": model,
        "message": _redact(request.app, str(exc)),
    })


def _config_invalid_response(request: Request, exc: PolicyRefusal) -> CanonicalJSONResponse:
    """[ruling M3] A malformed config *file* (bad JSON, an unknown key, an inlined
    credential at any nesting depth) is not a refusal of any particular model —
    reporting it as `policy-refusal` with an empty `model` field read as "the empty
    string violates policy", which is false. Distinct `error` value, no `model` key."""
    return CanonicalJSONResponse(status_code=409, content={
        "error": "config-invalid",
        "message": _redact(request.app, str(exc)),
    })


def _source(env_name: str, cfg: dict, key: str) -> str:
    if os.environ.get(env_name):
        return "env"
    if cfg.get(key):
        return "config"
    return "default"


def _model_view(request: Request) -> dict | CanonicalJSONResponse:
    """[ruling M3] `load_config()` and `resolve_settings()` are tried separately, in
    that order, so the two ways a `PolicyRefusal` can reach this route are told apart:
    a `load_config()` failure means the *file* is broken (`config-invalid`, no model
    named); a `resolve_settings()` failure past that point means the *resolved model*
    is denylisted (`policy-refusal`, naming it) — e.g. `DOCKET_LLM_MODEL` set directly
    in the environment, bypassing `PUT /settings/model`'s own check entirely.
    """
    try:
        cfg = load_config()
    except PolicyRefusal as exc:
        return _config_invalid_response(request, exc)
    try:
        settings = resolve_settings()
    except PolicyRefusal as exc:
        return _policy_refusal_response(request, exc, _resolved_model_guess())
    return {
        "provider": settings.provider,
        "model": settings.model,
        "baseUrl": settings.base_url,
        "source": {
            "provider": _source("DOCKET_LLM_PROVIDER", cfg, "provider"),
            "model": _source("DOCKET_LLM_MODEL", cfg, "model"),
            "baseUrl": _source("DOCKET_LLM_BASE_URL", cfg, "baseUrl"),
        },
        "timeout": settings.timeout,
    }


@router.get("/settings/model", response_model=None)
def get_model(request: Request) -> dict | JSONResponse:
    return _model_view(request)


class ModelUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    baseUrl: str | None = None


@router.put("/settings/model", response_model=None)
def put_model(body: ModelUpdate, request: Request) -> dict | JSONResponse:
    """Merge onto the persisted file only — never onto the environment or CLI layers of
    the precedence chain. A partial body (`{"model": ...}` alone) must not erase a
    previously saved provider/baseUrl, and must not accidentally bake today's transient
    `DOCKET_LLM_*` environment into tomorrow's on-disk default. The denylist check runs
    inside `write_config` itself, before any byte is written, so a refused model leaves
    the file exactly as it was.
    """
    if body.provider is not None and body.provider not in KNOWN_PROVIDERS:
        return CanonicalJSONResponse(status_code=400, content={
            "error": "invalid-provider",
            "message": f"provider must be one of {KNOWN_PROVIDERS}, got {body.provider!r}",
        })
    try:
        current = load_config()
    except PolicyRefusal:
        # [ruling I4] A refused (hand-edited, or otherwise malformed) config file must
        # not brick the one route that can fix it — fall back to an empty base so this
        # PUT overwrites the file outright, which also removes whatever made it refuse
        # (e.g. an accidentally-inlined credential) from disk.
        current = {}
    provider = body.provider if body.provider is not None else current.get("provider")
    model = body.model if body.model is not None else current.get("model")
    # [ruling M5] `baseUrl` is stripped, not validated — there is no fixed shape to
    # validate against (a bare host, a path prefix, and a port are all legitimate), so
    # rejecting one would only ever reject something this route cannot actually know is
    # wrong.
    base_url = body.baseUrl.strip() if body.baseUrl is not None else current.get("baseUrl")
    try:
        write_config(provider=provider, model=model, base_url=base_url)
    except PolicyRefusal as exc:
        return _policy_refusal_response(request, exc, model)
    return _model_view(request)


def _denylist_reason(model_id: str) -> str | None:
    """[ruling M1, T8 fix round] The policy family that matched `model_id`, or `None` if
    none did. Built from `DENYLIST` itself (the same compiled pattern `is_denylisted`/
    `check_model_policy` use) so this can never name a family the real policy doesn't
    also enforce, and — unlike `check_model_policy`'s refusal message — this never
    appends `OVERRIDE_HINT`: an API response must not hand a client a new way to spell
    out the override, even though the override is loud on purpose on the CLI.
    """
    hit = DENYLIST.search(model_id)
    if hit is None:
        return None
    return f"model id matches denylisted family {hit.group(0)!r} (policy P8)"


def _normalize_models(raw) -> list[dict]:
    """`list_models` (plan 04 Task 1) already returns `[{"id", "denylisted"}, ...]` for a
    real backend; this task's own test monkeypatches it to return bare ids instead
    (`docket.api.routes.settings.list_models`, imported into this module's namespace so
    the patch takes hold — see module docstring). Accept both shapes so the route is
    correct against the live function and against the test double alike.

    [ruling M1, T8 fix round] A `denylisted: true` entry also carries `reason` — the
    matched policy family, never the override hint — so a client can show *why* an
    entry is disabled, not just that it is. `list_models` only ever returns a denylisted
    entry at all under `DOCKET_LLM_ALLOW_DENYLISTED=1` (ruling C1, unchanged); this adds
    a field to that entry, it does not change when one appears.
    """
    out = []
    for m in raw:
        if isinstance(m, dict):
            mid = m.get("id")
            denylisted = m.get("denylisted", is_denylisted(mid) if mid else False)
        else:
            mid = m
            denylisted = is_denylisted(mid)
        entry = {"id": mid, "denylisted": denylisted}
        if denylisted and isinstance(mid, str):
            reason = _denylist_reason(mid)
            if reason is not None:
                entry["reason"] = reason
        out.append(entry)
    return out


@router.get("/settings/models", response_model=None)
def get_models(request: Request) -> dict | JSONResponse:
    try:
        load_config()
    except PolicyRefusal as exc:
        return _config_invalid_response(request, exc)
    try:
        settings = resolve_settings()
    except PolicyRefusal as exc:
        return _policy_refusal_response(request, exc, _resolved_model_guess())
    key = current_api_key(request)
    try:
        # [ruling C1] No `include_denylisted` argument here at all — that decision
        # belongs entirely to `list_models`'s own env-gated default
        # (`DOCKET_LLM_ALLOW_DENYLISTED`), the same one every other resolution point
        # honours. A picker that forces denylisted ids into view by default is the one
        # mistake the policy exists to prevent; when the override env *is* set (local
        # testing only), a denylisted id still comes back, each explicitly marked
        # `"denylisted": True`, so it renders as a visible warning rather than being
        # silently swapped in.
        # [ruling M1] 5s cap — a stale base URL must not hang the settings slide-over
        # for `list_models`'s own 30s default the way it would with no timeout at all.
        raw = list_models(base_url=settings.base_url, api_key=key, timeout=5.0)
        # [ruling M4] Normalization moved inside this `try`: a non-string id used to
        # reach `is_denylisted` outside any handler and crash with a bare `TypeError`
        # (an unhandled 500), not the 502 every other malformed-backend-response case
        # gets.
        normalized = _normalize_models(raw)
    except BackendError:
        raise
    except Exception as exc:  # a transport failure (or a malformed response) is a 502,
        raise BackendError(str(exc)) from exc  # never an unhandled 500
    return {"models": normalized}


@router.get("/settings/key")
def get_key(request: Request) -> dict:
    return {"keyPresent": bool(current_api_key(request))}


class KeyUpdate(BaseModel):
    apiKey: str


@router.put("/settings/key")
def put_key(body: KeyUpdate, request: Request) -> dict:
    """In memory, this process, this run, and nowhere else. `body.apiKey` is never
    written to a response, a log line, or a file — see `tests/api/test_settings.py` for
    the leak-proof this route is built to satisfy.

    [ruling I5] Reports whatever `current_api_key` actually resolves to, not a bare
    `True` — an empty `apiKey` here does not necessarily mean no key is present at all
    if `DOCKET_LLM_API_KEY` still supplies one in the environment (the same fallback
    `DELETE` below relies on).
    """
    request.app.state.api_key = body.apiKey
    return {"keyPresent": bool(current_api_key(request))}


@router.delete("/settings/key")
def delete_key(request: Request) -> dict:
    """[ruling I5] Clears only the in-memory override; if `DOCKET_LLM_API_KEY` is still
    set in the environment, a key is still effectively present and this must say so —
    reporting a bare `False` here lied about state a client (or `GET /settings/key`
    right afterward) would immediately contradict."""
    request.app.state.api_key = None
    return {"keyPresent": bool(current_api_key(request))}


@router.get("/settings/mode")
def get_mode(request: Request) -> dict:
    return {"mode": request.app.state.mode_override or "auto"}


class ModeUpdate(BaseModel):
    mode: str


@router.put("/settings/mode")
def put_mode(body: ModeUpdate, request: Request) -> dict:
    if body.mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {body.mode!r}")
    request.app.state.mode_override = None if body.mode == "auto" else body.mode
    return {"mode": body.mode}


@router.get("/settings/actor")
def get_actor() -> dict:
    return {"actorId": actor_id()}


class ActorUpdate(BaseModel):
    actorId: str


def _actor_id_error(stripped: str) -> str | None:
    """[ruling I2] `None` when `stripped` (the submitted id with leading/trailing
    whitespace removed) is acceptable; otherwise the message to report. Checked here,
    not in `write_actor_id`, because the write is otherwise a dumb persist (plan 04) and
    this validation is specific to the human-actor convention this route alone owns."""
    if not stripped:
        return "actor id must not be empty"
    if stripped.lower().startswith("agent:"):
        return "actor id must not start with 'agent:' (reserved for agent actors)"
    if len(stripped) > _MAX_ACTOR_ID_LEN:
        return f"actor id must be at most {_MAX_ACTOR_ID_LEN} characters"
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in stripped):
        return "actor id must not contain control characters"
    return None


@router.put("/settings/actor", response_model=None)
def put_actor(body: ActorUpdate) -> dict | JSONResponse:
    stripped = body.actorId.strip()
    error = _actor_id_error(stripped)
    if error is not None:
        return CanonicalJSONResponse(status_code=400, content={
            "error": "invalid-actor",
            "message": error,
        })
    write_actor_id(stripped)
    # [ruling I3] Report what the server will actually use, not the raw submission —
    # `DOCKET_UI_ACTOR` in the environment outranks the file `write_actor_id` just
    # wrote (`config.actor_id`'s own precedence), so echoing `stripped` back here would
    # answer a question nobody asked ("what did you send") instead of the one that
    # matters ("what will the next request be attributed to").
    return {"actorId": actor_id()}
