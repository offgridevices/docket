"""FastAPI app factory: routers, the exception-to-status table, and the built SPA mount.

One process: this app imports `docket.kernel` and `docket.agent` directly, so a
`TransitionRefused` or an `AuthorityViolation` arrives here as a typed Python exception,
never as parsed subprocess stderr — the whole reason `src/docket/api/` exists instead of
shelling out to the CLI.
"""
from __future__ import annotations

import importlib
import json
import os
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from docket.agent.backend import OVERRIDE_HINT
from docket.api.config import UI_MODE_ENV, UI_NOT_BUILT_MESSAGE, static_dir
from docket.api.sessions import SessionStore
from docket.errors import (
    AuthorityViolation,
    BackendError,
    PolicyRefusal,
    RecordingMissing,
    TransitionRefused,
    UncitedSentenceError,
    ValidationError,
)

# Route modules land one per plan-07 task (T1: health, session; T2: settings; T3: agent;
# T4: kernel, program). A module that does not exist yet at import time is skipped, not
# an error — the same "degrade gracefully" rule the plan applies to the demo stores and
# to `render.py` — so this loop does not need editing again as each task's file lands.
# The 2026-09-11 UI rebuild adds two more: `workspace` (T2) and `ask` (T5); `ask` has
# not landed yet, and the loader below returning `None` for it is the same tolerated
# absence, not an error.
_ROUTE_MODULES = ("health", "settings", "session", "agent", "kernel", "program", "workspace", "ask")


def _load_route_module(name: str):
    """Import `docket.api.routes.<name>`, tolerating only that exact module's absence.

    Returns the module, or `None` if it has not landed yet. Anything else that goes
    wrong while importing a module that DOES exist on disk — a bad type hint, a bad
    decorator, a typo, an unrelated missing dependency inside it — is a bug in that
    module, not an absent one, and must not be silently swallowed: a demo that starts
    with routes quietly missing is worse than one that refuses to start and says which
    module broke it. The distinction is made on `ModuleNotFoundError.name`, not the
    exception type alone, because a module that DOES exist can itself raise
    `ModuleNotFoundError` for a *different* missing name (an absent third-party
    dependency, a typo'd import inside it) — that must fail loudly too, not be mistaken
    for "this route is simply not built yet".
    """
    fq_name = f"docket.api.routes.{name}"
    try:
        return importlib.import_module(fq_name)
    except ModuleNotFoundError as exc:
        if exc.name == fq_name:
            return None
        raise RuntimeError(f"route module {fq_name!r} failed to import: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"route module {fq_name!r} failed to import: {exc}") from exc


class CanonicalJSONResponse(JSONResponse):
    """Sorted-key JSON for every route: "every response body is canonical JSON (sorted
    keys) where it is kernel data" (plan 07 Task 1). Applying it as the app's default
    response class, rather than per route, means a route added later inherits it
    automatically instead of a reviewer having to check each new route by hand."""

    def render(self, content) -> bytes:
        return json.dumps(
            content, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")


class SPAStaticFiles(StaticFiles):
    """Serve the built SPA; fall back to `index.html` for any client-side route.

    A bare `StaticFiles` 404s on a deep link (e.g. `/package` with no `package.html` on
    disk) because it only knows about files that exist. The SPA's own router needs the
    shell every time, provided the path does not look like a static asset (has no
    extension) and is not itself under `/api/` — every *registered* API route already
    matches before Starlette ever reaches this mount (it is included first, in
    `create_app`), but an unmatched `/api/...` path (a typo, a route from a future task
    that has not landed yet) is not claimed by anything and would otherwise fall through
    to here just like `/package` does, and silently answering it with the HTML shell
    instead of a 404 is exactly the kind of API/UI boundary confusion `/api/*` exists to
    rule out.

    [plan 07 Task 9 fix] `StaticFiles.get_response` does not *return* a 404 response for
    a missing path — it *raises* `starlette.exceptions.HTTPException(404)` (see
    `StaticFiles.get_response`'s own final line). The original version of this method
    checked `response.status_code == 404` on the awaited call, which the exception never
    let it reach: every unknown client route (`/package`, a hard refresh on `/readiness`,
    ...) 404'd straight through instead of falling back to the shell, silently defeating
    the whole point of this class. Fixed by catching the exception instead of inspecting
    a response that is never returned in that case.
    """

    def _eligible_for_fallback(self, path: str) -> bool:
        return "." not in path and path != "api" and not path.startswith("api/")

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404 and self._eligible_for_fallback(path):
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and self._eligible_for_fallback(path):
            return await super().get_response("index.html", scope)
        return response


def _redact(app: FastAPI, message: str) -> str:
    """Replace the in-memory API key, if any, with `***`, and strip the policy's
    local-testing override hint — both before either can reach a response body.

    A key cannot normally reach an exception message — nothing in the kernel or the
    agent layer touches it — this is the backstop for "normally", not the mechanism.

    [ruling I1, plan 07 T2 fix round] `check_model_policy`'s refusal text is
    deliberately loud for a human on the CLI — `OVERRIDE_HINT` is named in the message
    on purpose, because "an override nobody sees is the same as no policy"
    (`backend.py`). Every API route's contract says the opposite: a denylisted-model
    refusal must carry no hint that an override exists at all. This used to be a local
    fix inside `routes/settings.py` alone; any *other* route that lets a
    `PolicyRefusal` reach this app-wide handler unmodified (e.g. a future agent route
    resolving settings on every call) got no redaction at all. Fixing it here, once,
    covers every route through this same handler — `routes/settings.py` now also calls
    this function directly for the 409 bodies it builds itself.
    """
    key = getattr(app.state, "api_key", None) or os.environ.get("DOCKET_LLM_API_KEY")
    if key:
        message = message.replace(key, "***")
    idx = message.find(OVERRIDE_HINT)
    if idx != -1:
        message = message[:idx].rstrip()
    return message


_SENTENCE_RE = re.compile(r"sentence \d+ \((.*?)\):")


def _sentence_for(exc: UncitedSentenceError) -> str | None:
    """The offending sentence's text: the structured `exc.sentence` attribute when a
    caller set one, else a best-effort parse of the message.

    `UncitedSentenceError` now carries an optional `sentence` attribute (errors.py); no
    current caller (`render.render_package`) sets it yet, so this still falls back to
    parsing `str(exc)` in practice, but a future caller that does set it is read first
    and the parse is never even attempted — the parse is a bridge, not the contract.
    """
    if exc.sentence is not None:
        return exc.sentence
    return _parsed_sentence(str(exc))


def _parsed_sentence(message: str) -> str | None:
    """Best-effort recovery of the offending sentence's text from an
    `UncitedSentenceError` message (`render.render_package` raises with
    `f"{narrative_id}: " + "; ".join(check_citations(...))`, and each of those errors
    reads `f"sentence {i} ({text!r}): ..."`) for a caller that did not set the
    structured `sentence` attribute — this is a parse of the message string, not a
    re-derivation from the graph; it degrades to `None` rather than raising if the
    message does not match the shape `render.py` currently produces.
    """
    m = _SENTENCE_RE.search(message)
    if not m:
        return None
    try:
        import ast

        return ast.literal_eval(m.group(1))
    except (ValueError, SyntaxError):
        return m.group(1)


def _install_error_handlers(app: FastAPI) -> None:
    """The contract the frontend codes against (plan 07 Task 1, "Step 7"). Every handler
    redacts the in-memory API key before it can reach a response body."""

    def _register(exc_class, status_code: int, error: str, extra=None,
                  response_cls=JSONResponse):
        def _handle(request: Request, exc: Exception):
            body = {"error": error, "message": _redact(app, str(exc))}
            if extra is not None:
                body.update(extra(exc))
            return response_cls(status_code=status_code, content=body)

        app.add_exception_handler(exc_class, _handle)

    _register(TransitionRefused, 409, "transition-refused",
              lambda e: {"unsatisfied": e.unsatisfied})
    _register(AuthorityViolation, 403, "authority-violation")
    # [ruling M2, plan 07 T2 fix round] canonical (sorted-key) JSON for this one body,
    # same as every 200 response already gets from the app's default response class —
    # not widened to the other handlers above/below, which are outside this task's file
    # scope.
    _register(PolicyRefusal, 409, "policy-refusal", response_cls=CanonicalJSONResponse)
    _register(UncitedSentenceError, 422, "uncited-sentence",
              lambda e: {"sentence": _sentence_for(e)})
    _register(ValidationError, 422, "validation", lambda e: {"errors": e.errors})
    # RecordingMissing subclasses BackendError; Starlette matches the most specific
    # registered class in the exception's MRO, so registering both is enough — a
    # RecordingMissing never falls through to the BackendError body. The plan's table
    # gives them different statuses on purpose: 503 says "this recorded fixture has no
    # answer for this prompt" (a fixture-completeness problem, retryable once the
    # recording is extended), 502 says "a live backend answered badly" (a transport/
    # protocol problem) — collapsing them to one status would erase that distinction.
    _register(RecordingMissing, 503, "recording-missing")
    _register(BackendError, 502, "backend")
    # `SessionStore.get`/`delete` and `Graph.get` both raise a plain `KeyError` for "not
    # found" (a session id, or an object id/rev inside one); both read as "the thing
    # named in the URL does not exist" and are folded into the same 404 here.
    app.add_exception_handler(
        KeyError, lambda request, exc: JSONResponse(status_code=404,
                                                     content={"error": "no-session"}))
    _register(FileNotFoundError, 409, "demo-not-built")
    # Not part of the plan's literal table: a malformed request (an unknown session
    # `source`) must not 500 either. `SessionStore.create` is the only raiser.
    _register(ValueError, 400, "bad-request")


def create_app() -> FastAPI:
    app = FastAPI(
        title="docket", docs_url=None, redoc_url=None,
        openapi_url="/api/openapi.json", default_response_class=CanonicalJSONResponse,
    )
    app.state.sessions = SessionStore()
    app.state.api_key = None            # in memory, this process, this run. Never written.
    app.state.mode_override = os.environ.get(UI_MODE_ENV) or None

    for name in _ROUTE_MODULES:
        module = _load_route_module(name)
        if module is not None:
            app.include_router(module.router, prefix="/api")

    _install_error_handlers(app)

    static = static_dir()
    if (static / "index.html").is_file():
        app.mount("/", SPAStaticFiles(directory=static, html=True), name="ui")
    else:
        # [plan 07 Task 9] `docket ui` already prints `UI_NOT_BUILT_MESSAGE` to the
        # terminal it was launched from and still serves the API either way — this is
        # the same message for whoever is looking at the browser instead (no terminal
        # in view, e.g. a projector), rather than a bare framework 404 at `/`. Every
        # `/api/*` route is registered above and answers normally regardless of this
        # branch; only the bare SPA shell is affected.
        @app.get("/", include_in_schema=False)
        def _spa_not_built() -> PlainTextResponse:
            return PlainTextResponse(UI_NOT_BUILT_MESSAGE)

    return app
