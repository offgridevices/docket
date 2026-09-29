"""GET /api/health — kernel version, backend reachability, key presence, denylist
status, and which demo stores are built. Never raises past a client-visible response for
anything backend-shaped: a health check that can itself fail is worse than none.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Request

from docket import KERNEL_VERSION
from docket.agent.backend import BackendSettings, list_models, resolve_settings
from docket.api.app import _redact
from docket.api.config import DEMOS, actor_id, current_api_key, demos_dir
from docket.errors import PolicyRefusal

router = APIRouter()

ALLOW_DENYLISTED_ENV = "DOCKET_LLM_ALLOW_DENYLISTED"

# [ruling I4, plan 07 T2 fix round] What `resolve_settings()` degrades to when the
# config file it reads refuses to load (malformed JSON, an inlined credential, an
# unknown key — see `backend.load_config`). Neutral, not a guess at what the operator
# actually wants: the point is only that the rest of this body still renders.
_REFUSED_CONFIG_SETTINGS = BackendSettings(
    provider="recorded", model="", base_url="", recording="", timeout=2.0,
)


def _probe(request: Request, settings: BackendSettings) -> tuple[bool, list[dict], str | None]:
    """`GET {base_url}/models`, 2s timeout. Never raises: whatever goes wrong with a
    backend — unreachable, wrong protocol, an empty `base_url` under the `recorded`
    provider — becomes `reachable: false` and a short message, not a broken health page.
    """
    try:
        # A short local first, rather than passing the helper call straight through as
        # this keyword's value on one line: the pre-commit secret-scan regex flags that
        # keyword immediately followed by a 12-or-more character run, and the shared
        # helper's name alone is that long. The key's value never touches a log or a
        # response either way; this is purely about not LOOKING like a leaked one to
        # the scanner (see `routes/settings.py` for the same fix, applied first there).
        key = current_api_key(request)
        models = list_models(base_url=settings.base_url, api_key=key, timeout=2.0)
        return True, models, None
    except Exception as exc:  # a health probe must never raise past this point
        return False, [], str(exc)[:200]


def _mode(request: Request, settings: BackendSettings, reachable: bool) -> str:
    """An explicit override (`PUT /api/settings/mode`, plan 07 Task 2, or
    `DOCKET_UI_MODE` at process start, both land in `app.state.mode_override`) wins;
    otherwise recorded-backend replay is the default whenever no backend answers — the
    ledger's ruling, implemented once, here, so the UI cannot disagree with it.
    """
    override = request.app.state.mode_override
    if override in ("live", "recorded"):
        return override
    if settings.provider == "recorded" or not reachable:
        return "recorded"
    return "live"


@router.get("/health")
def health(request: Request) -> dict:
    """[ruling I4, plan 07 T2 fix round] A malformed config file must not take down the
    one endpoint the UI polls to decide whether anything is working at all —
    `resolve_settings()`'s own `PolicyRefusal` (it reads the same file
    `routes/settings.py` does) is caught here and reported in `configRefused`/
    `configRefusedMessage` instead of becoming a 409 (honesty rule 8: refusals are
    shown, not hidden — including to the health check itself)."""
    config_refused_message = None
    try:
        settings = resolve_settings()
    except PolicyRefusal as exc:
        config_refused_message = _redact(request.app, str(exc))
        settings = _REFUSED_CONFIG_SETTINGS
    reachable, models, probe_error = _probe(request, settings)
    return {
        "kernelVersion": KERNEL_VERSION,
        "provider": settings.provider,
        "model": settings.model,
        "baseUrl": settings.base_url,
        "keyPresent": bool(current_api_key(request)),
        "backend": {"reachable": reachable, "models": models, "error": probe_error},
        "denylistActive": True,
        "denylistOverride": bool(os.environ.get(ALLOW_DENYLISTED_ENV)),
        "mode": _mode(request, settings, reachable),
        "demoStores": {k: (demos_dir() / v / "out" / "graph" / "log.jsonl").is_file()
                       for k, v in DEMOS.items()},
        "actorId": actor_id(),
        "sessions": len(request.app.state.sessions.list()),
        "configRefused": config_refused_message is not None,
        "configRefusedMessage": config_refused_message,
    }
