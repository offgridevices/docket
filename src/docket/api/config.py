"""Where the UI keeps its state, who it acts as, and which mode it is in.

None of this is kernel state. The kernel takes `now` and `seed` as arguments and writes
only to the graph; this module holds the things a *server* needs and a kernel must not:
a home directory, a process-lifetime actor id, and a live/recorded switch.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import Request

STATE_DIR_ENV, DEMOS_DIR_ENV = "DOCKET_STATE_DIR", "DOCKET_DEMOS_DIR"
UI_ACTOR_ENV, UI_MODE_ENV = "DOCKET_UI_ACTOR", "DOCKET_UI_MODE"
CONFIG_DIR_ENV = "DOCKET_CONFIG_DIR"
SOURCES_DIR_ENV = "DOCKET_SOURCES_DIR"
LLM_API_KEY_ENV = "DOCKET_LLM_API_KEY"
# [plan 07 Task 9] The built SPA's location — `ui/vite.config.ts`'s `outDir`, gitignored,
# built by `make ui-build`/`docket ui`. Overridable so a test (`tests/api/test_spa_serving.py`)
# can exercise both the "built" and "not built" cases without depending on whether this
# machine happens to have run `npm run build`.
STATIC_DIR_ENV = "DOCKET_STATIC_DIR"
_DEFAULT_UI_CONFIG = Path.home() / ".config" / "docket" / "ui.json"
UI_CONFIG = _DEFAULT_UI_CONFIG
DEMOS = {"demo-a": "a_cbo_gcv_2013", "demo-b": "b_omfv_2019_2023"}
DEFAULT_ACTOR = "shreyash"
# The exact line both `docket ui` (stdout) and `api.app`'s fallback `/` response (a
# browser hitting the demo before anything has been built) print — one string, so the
# two can never drift into disagreeing about what to run.
UI_NOT_BUILT_MESSAGE = (
    "The docket UI is not built yet. Run `make ui-build` (or `cd ui && npm ci && npm "
    "run build`), then reload this page or restart `docket ui`. The API itself is "
    "already live at /api/*."
)
# [plan 07 Task 9 Part B] The one Policy id `tests/fixtures/recorded/elicit.json`'s
# committed response is recorded under: `agent.elicit`'s user prompt embeds the policy
# id literally ("Policy id: {policy_id}. Produce the JSON object..."), and the
# recording key is a hash over that prompt — eliciting with any other policy id (a
# session's own seeded `pol-default`, a demo's own `pol-cbo`/`pol-omfv`, or omitting it
# for `routes/agent.py`'s own `"pol-default"` fallback) changes the prompt and misses
# the recording (`RecordingMissing`), so this is the *only* id a live elicitation
# against that fixture may use. `sessions.SessionStore.create` seeds a Policy at this id
# into every session it creates (new or demo-sourced) for exactly that reason — without
# it, the elicited Charter's `decisionClassPolicy` points at an id nothing in the graph
# defines, `kernel.validate`'s `ref-integrity` rule reports that as a BLOCKING
# structural finding, and G1 approval is refused on `no-blocking-structural` forever,
# regardless of what a human does at the gate. Discovered building `openDemoASeeded`
# (`ui/e2e/_fixtures.ts`) — see `task-9b-report.md`. `routes/session.py`'s `/sources`
# route re-exports this name (`tests/api/test_sources_route.py` imports it from there)
# so the UI is told the same id it must seed against.
RECORDED_REQUEST_POLICY = "pol-1"


def static_dir() -> Path:
    """`src/docket/api/static` — `api.app.create_app`'s SPA mount and `docket ui`'s
    missing-build check both read this, so the two can never disagree about where the
    built bundle is supposed to live."""
    if env := os.environ.get(STATIC_DIR_ENV):
        return Path(env)
    return Path(__file__).parent / "static"


def _config_path() -> Path:
    """`UI_CONFIG`, redirected under `DOCKET_CONFIG_DIR` when set and `UI_CONFIG` itself
    has not been overridden by a caller.

    `UI_CONFIG` stays a plain module attribute, not a function: `tests/api/test_settings.py`
    already monkeypatches it directly (`monkeypatch.setattr("docket.api.config.UI_CONFIG",
    fake_config)`), and changing that contract here would break a test this module does
    not own. `DOCKET_CONFIG_DIR` is a second, coarser seam for every *other* test: the
    `env` fixture in `tests/api/conftest.py` sets it once for every API test, so
    `actor_id`/`write_actor_id` never touch the real developer machine's
    `~/.config/docket` even in a test that forgot to monkeypatch `UI_CONFIG` by hand. A
    caller who *did* monkeypatch `UI_CONFIG` directly still wins — this only falls back to
    the environment variable when `UI_CONFIG` is still exactly its own default.
    """
    if UI_CONFIG != _DEFAULT_UI_CONFIG:
        return UI_CONFIG
    if env := os.environ.get(CONFIG_DIR_ENV):
        return Path(env) / "ui.json"
    return UI_CONFIG


def state_dir() -> Path:
    p = Path(os.environ.get(STATE_DIR_ENV) or (Path.home() / ".local/share/docket"))
    (p / "sessions").mkdir(parents=True, exist_ok=True)
    return p


def repo_root() -> Path:
    """The repository checkout this package was installed from, or the cwd.

    `demos/`, `sources/` and `tests/fixtures/` are all repository data, not package data
    — none of them is inside `src/docket`. Walk up from this file until a directory
    holding both `demos/` and `pyproject.toml` appears, so the server works from an
    editable install and from any working directory. A non-editable install has no such
    parent; the cwd is the honest fallback, and every caller must tolerate the directory
    it names not existing.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "demos").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


def demos_dir() -> Path:
    if env := os.environ.get(DEMOS_DIR_ENV):
        return Path(env)
    return repo_root() / "demos"


def sources_dir() -> Path:
    """`sources/` — the public source documents and their `.source.md` provenance stubs
    (plan 07 Task 6's source picker). Public data only, by the repository's own hard
    boundary; nothing controlled ever lands there, so listing it needs no filter."""
    if env := os.environ.get(SOURCES_DIR_ENV):
        return Path(env)
    return repo_root() / "sources"


def actor_id() -> str:
    """Precedence: env > ui.json > default. ui.json holds an actor id and nothing else —
    the LLM config file (llm.json) refuses unknown keys by design, so this cannot live
    there, and an actor id is not a credential."""
    if env := os.environ.get(UI_ACTOR_ENV):
        return env
    try:
        return json.loads(_config_path().read_text()).get("actorId") or DEFAULT_ACTOR
    except (OSError, json.JSONDecodeError):
        return DEFAULT_ACTOR


def write_actor_id(value: str) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"actorId": value}, indent=2) + "\n")
    path.chmod(0o600)


def current_api_key(request: Request) -> str:
    """The in-memory key set by `PUT /api/settings/key`, falling back to the
    environment. [ruling M6, plan 07 T2 fix round] `routes/settings.py` and
    `routes/health.py` each carried their own verbatim copy of this rule; one home for
    it here removes the drift risk if a future change touches one call site and not the
    other. `DELETE /settings/key` resets `app.state.api_key` to `None`, which is
    exactly the sentinel `backend_from_settings` also treats as "use the environment" —
    clearing the override does not require also unsetting `DOCKET_LLM_API_KEY` for the
    two to agree.
    """
    return request.app.state.api_key or os.environ.get(LLM_API_KEY_ENV) or ""


def human_actor() -> dict:
    return {"actorType": "human", "actorId": actor_id()}


class ConfigInvalid(Exception):
    """No model is configured, so there is nothing to name an agent actor after.

    [ruling M3, plan 07 T3 fix round] Distinct from `docket.errors.PolicyRefusal`: an
    empty model id does not match any denylisted family, so reporting it as
    `policy-refusal` would read as "the empty string violates policy", which is false —
    the same distinction `routes/settings.py`'s own `_config_invalid_response` already
    draws for a malformed config *file*. Routes catch this and answer 409
    `config-invalid`, never the unnamed actor id `"agent:"`.
    """


def _named_model_id(model_id: str) -> str:
    """`model_id`, or refuse it. [ruling M3] `agent.elicit.elicit()`'s own
    `startswith("agent:")` check accepts the unnamed id `"agent:"` as well-formed — an
    empty `model_id` (an `openai-compatible`/`anthropic` provider resolved with no
    `--model`/`DOCKET_LLM_MODEL`/config-file model set) would otherwise silently name no
    model at all as a DRAFT object's author."""
    if not model_id:
        raise ConfigInvalid(
            "no model is configured: set DOCKET_LLM_MODEL, PUT /api/settings/model, "
            "or select the recorded backend"
        )
    return model_id


def agent_actor(backend) -> dict:
    """`{"actorType": "agent", "actorId": "agent:<model>"}` — the ledger's actor-id
    convention (`agent.elicit.elicit()` refuses any `createdBy.actorId` that does not
    start with `"agent:"`; `agent.cli._actor_for` builds the same shape for the CLI).

    [plan 07 Task 3 fix] This used to read `backend.extractor` — which names the
    structured-output mode a live backend negotiated (e.g.
    `"openai-compatible:llama3/json_schema"`) or, for `RecordedBackend`,
    `"recorded:recorded"` — neither of which ever starts with `"agent:"`. Every call
    through this function into `elicit_into` would have raised `AuthorityViolation`
    before writing anything. `backend.model_id` is the right field: it is exactly the
    model name the convention asks for, and it is what `agent.cli._actor_for` already
    uses. `ingestionProvenance.extractor` (set independently, inside `elicit()` itself)
    still carries the full extractor string for provenance display.

    [ruling M3, plan 07 T3 fix round] Raises `ConfigInvalid` rather than mint the
    unnamed actor id `"agent:"` when `backend.model_id` is empty.
    """
    return {"actorType": "agent", "actorId": f"agent:{_named_model_id(backend.model_id)}"}


def agent_actor_for_settings(settings) -> dict:
    """The same `{"actorType": "agent", "actorId": "agent:<model>"}` shape as
    `agent_actor`, derived from `agent.backend.BackendSettings` alone — no backend is
    constructed.

    [ruling I3, plan 07 T3 fix round] `/dispatch` needs only an actor to name in the
    record's log line (`agent.dispatch`'s own module docstring: "`actor` is accepted
    only so a caller ... has someone to name"); `dispatch()` never calls a backend, so
    resolving one merely to compute this string coupled the deterministic compute path's
    failure mode to the LLM configuration — a demo machine with no key configured would
    409 on pure kernel arithmetic. `RecordedBackend.__init__` hardcodes
    `model_id = "recorded"` regardless of `settings.model`
    (`agent.backend.RecordedBackend`), so the `recorded` provider is special-cased the
    same way here, without importing or instantiating it.
    """
    model_id = "recorded" if settings.provider == "recorded" else settings.model
    return {"actorType": "agent", "actorId": f"agent:{_named_model_id(model_id)}"}
