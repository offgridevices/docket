# src/docket/agent/backend.py
"""Model-agnostic LLM backends. One method: complete_json. Tests use RecordedBackend only.

Two live implementations exist to prove model-agnosticism, not to express a preference
[ruling R18]: OpenRouter's OpenAI-compatible path already serves Anthropic models, so
`AnthropicBackend` is never the default, is never named in the docs, and exists so
that "model-agnostic" is a property of the code and not a claim in a document.

Nothing here is in the numeric path. A backend returns JSON that some other module maps
onto DRAFT objects; no value it produces reaches a run, a result, a weight or an
observation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from jsonschema import Draft202012Validator

from docket.canon import canonical_json, sha256_hex
from docket.errors import BackendError, PolicyRefusal, RecordingMissing

log = logging.getLogger("docket.agent.backend")

# ---- policy: PRC-origin model families (design P8) ----------------------------------

# [ruling R1] Family substrings, matched case-insensitively against the whole resolved
# model id with NON-LETTER boundaries, so both `glm-4.5` (OpenRouter) and `glm4:9b`
# (Ollama tag syntax, which uses `:` not `-`) match. Bare `spark` is deliberately absent:
# it false-positives on innocent ids such as `sparkle-7b`; `sparkdesk` carries the family.
# `ling` and `step` are added per the brief-writer's ruling (progress.md "Briefs written"
# entry (c)) so that `ling-1t` and `step-1v` are caught; both are still boundary-matched,
# so `sparkle`/`stepping`/`darling` remain unaffected.
#
# [ruling I5] `step` and `moss` are also ordinary English words, and a bare boundary
# check ("not adjacent to a letter") is not enough to keep them out of prose: "Step 1:"
# and "the next step." both have a non-letter on both sides of "step". `step` is
# therefore special-cased below to require a version/tag suffix — a digit, optionally
# introduced by one of `-_.:` (`step3`, `step-1v`, `step.2`, `step_7` match; `step 1`,
# `a step-by-step guide`, `the next step.` do not, because a space is not in that
# separator set and "the next step." has no digit at all after it). `moss` is spelled
# out as the literal family name `moss-moon` instead of the bare word, for the same
# reason ("moss grows" no longer contains the family string at all).
DENYLIST_FAMILIES: tuple[str, ...] = (
    "deepseek", "qwen", "qwq", "qvq", "kimi", "moonshot", "glm", "chatglm", "zhipu", "yi",
    "baichuan", "minimax", "hunyuan", "ernie", "doubao", "internlm", "internvl", "minicpm",
    "cogvlm", "seed-oss", "skywork", "xverse", "telechat", "stepfun", "sparkdesk",
    "longcat", "dots.llm", "pangu", "sensechat", "moss-moon", "ling", "step",
)


def _family_alternative(family: str) -> str:
    """Build the regex alternative for one family. `step` needs a version/tag-suffix
    lookahead instead of the plain not-a-letter boundary every other family uses
    [ruling I5]; everything else keeps the original boundary form."""
    if family == "step":
        return r"step(?=[-_.:]?\d)"
    return re.escape(family) + r"(?![a-z])"


# The model-id check: applied to a single resolved model id (never free prose), so the
# plain boundary form is the right level of strictness for every family except `step`.
DENYLIST = re.compile(
    r"(?<![a-z])(?:" + "|".join(_family_alternative(f) for f in DENYLIST_FAMILIES) + r")",
    re.IGNORECASE,
)

# [ruling I5] The document/fixture scan (below, used only by the repo-wide "no
# denylisted name" guard test) is deliberately tighter than the model-id check: a bare
# family word bounded by non-letters is still routine in English prose ("a paper by
# Yi et al.", "Ling gave the go-ahead"), so scanning prose with the model-id pattern
# produces false positives the model-id check itself does not have to worry about.
# The document scan additionally requires a `:`, `-`, or digit immediately before or
# after the family word — the shape every real model tag has (`qwen3.8:27b-mlx`,
# `deepseek-v3`, `internvl3`) and ordinary prose does not.
_TAG_CONTEXT = r"[:\-0-9]"


def _doc_scan_alternative(family: str) -> str:
    if family == "step":
        # [ruling N1] `step(?=[-_.:]?\d)` alone (I5's fix) is still not tight enough for
        # the DOCUMENT scan specifically: `step-1`, `step-2`, `step_3` are this
        # codebase's own Plan.steps/Result-id convention, lexically identical to that
        # lookahead. Requiring something AFTER the digit run — another letter (the "v" in
        # `step-1v`) or another separator (the "-" in `step-1-8k`) — is what a real
        # StepFun tag has and a bare step-id does not. The digit run must be excluded
        # from the trailing class (`[a-z_.:-]`, not `[a-z0-9_.:-]`), or `step-10` would
        # re-match by backtracking the `\d+` down to `1` and reading the `0` as "more
        # tag". Accepted residual: a bare `step-3` written in a document is no longer
        # flagged here — it is lexically identical to a docket plan-step id — but the
        # strict `DENYLIST` above still refuses it as a model id at every resolution
        # point, which is where a refusal actually matters.
        return r"step(?=[-_.:]?\d+[a-z_.:-])"
    esc = re.escape(family)
    if any(c in family for c in "-_.:"):
        # [ruling N2] a family that already contains a separator (`moss-moon`,
        # `seed-oss`, `dots.llm`) is tag-shaped by construction — requiring an
        # ADDITIONAL external `:`/`-`/digit would make it unmatchable standing alone
        # (`DOC_SCAN_DENYLIST.search("moss-moon")` was `None` before this fix), so it
        # gets the plain boundary form instead, same as the model-id check.
        return r"(?<![a-z])" + esc + r"(?![a-z])"
    return (rf"(?:(?<={_TAG_CONTEXT}){esc}(?![a-z])"
            rf"|(?<![a-z]){esc}(?={_TAG_CONTEXT}))")


DOC_SCAN_DENYLIST = re.compile(
    "|".join(_doc_scan_alternative(f) for f in DENYLIST_FAMILIES), re.IGNORECASE,
)

# Honest limit, recorded rather than papered over: the accepted family set does not catch
# every PRC-origin id in circulation. These are known to pass. The denylist is a
# tripwire against the ids we know of, not a guarantee — extending the set needs a
# ruling. (`ling-1t` and `step-1v`, the originally-known-uncaught pair, are now caught by
# the `ling`/`step` families above and have been replaced here with two other real,
# currently-uncaught PRC-origin families so this honesty check stays non-vacuous.)
KNOWN_UNCAUGHT: tuple[str, ...] = ("aquila2-34b", "orion-14b-chat")

ALLOW_ENV = "DOCKET_LLM_ALLOW_DENYLISTED"
# [ruling I1, plan 07 T2 fix round] The exact sentence `check_model_policy` appends to a
# refusal — named so any caller that must strip it (an API response redactor; an API
# must never advertise that an override exists, even though the override is loud on
# purpose on the CLI) can match it exactly instead of re-deriving a copy of the same
# string that can silently drift out of sync with this one.
OVERRIDE_HINT = f"Set {ALLOW_ENV}=1 to override for local testing."


def is_denylisted(model: str) -> bool:
    return bool(model) and DENYLIST.search(model) is not None


def check_model_policy(model: str) -> str:
    """Return `model`, or refuse it. Called wherever a model id is resolved [ruling R3].

    The override exists because two of the four locally cached models are denylisted and
    local testing is the only way to exercise a live backend on this machine. It is loud
    on purpose: an override nobody sees is the same as no policy. [ruling M4: this
    docstring names no PRC-origin family, on the same policy DENYLIST_FAMILIES enforces.]
    """
    if not model:
        return model
    hit = DENYLIST.search(model)
    if hit is None:
        return model
    if os.environ.get(ALLOW_ENV) == "1":
        log.warning(
            "model %r matches the PRC-origin denylist family %r and is permitted ONLY "
            "because %s=1 (local testing). It must not appear in the docs, in a "
            "committed fixture, in a demo default, or in a screenshot.",
            model, hit.group(0), ALLOW_ENV,
        )
        return model
    raise PolicyRefusal(
        f"model {model!r} matches the PRC-origin denylist family {hit.group(0)!r} and is "
        f"excluded by policy (design P8). {OVERRIDE_HINT}"
    )


# ---- the protocol and the shared JSON loop ------------------------------------------


class Backend(Protocol):
    name: str
    model_id: str

    def complete_json(self, *, system: str, user: str, schema: dict,
                      max_retries: int = 2) -> dict: ...


class JsonBackendBase:
    name = "base"
    model_id = "base"

    @property
    def extractor(self) -> str:
        """What `ingestionProvenance.extractor` records for objects this backend fed."""
        return f"{self.name}:{self.model_id}"

    def _raw(self, system: str, user: str, schema: dict,
             budget: _RequestBudget | None = None) -> str:
        raise NotImplementedError

    def on_validation_failure(self) -> None:
        """Hook: a response parsed but failed the schema. Subclasses may renegotiate."""

    def complete_json(self, *, system: str, user: str, schema: dict,
                      max_retries: int = 2) -> dict:
        validator = Draft202012Validator(schema)
        errors: list[str] = []
        prompt = user
        # [ruling M5/N5] one HTTP-attempt budget for THIS call, spent by `_post` no
        # matter which loop (this one, or a live backend's own renegotiation loop) is
        # asking. Passed down as an explicit argument rather than stashed on `self`
        # [ruling N5]: two concurrent `complete_json` calls on one shared backend
        # instance (plan 07 is a server) each get their own local budget this way and
        # cannot exhaust or reset each other's. Backends with no network path
        # (RecordedBackend, the test fakes) simply ignore the argument.
        budget = _RequestBudget()
        for _attempt in range(max_retries + 1):
            raw = self._raw(system, prompt, schema, budget)
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                errors = [f"response was not valid JSON: {e}"]
            else:
                errors = [
                    f"{'/'.join(map(str, er.path)) or '<root>'}: {er.message}"
                    for er in validator.iter_errors(obj)
                ]
                if not errors:
                    return obj
            self.on_validation_failure()
            prompt = (user + "\n\nYour previous response failed validation:\n- "
                      + "\n- ".join(errors) + "\nReturn only a corrected JSON object.")
        raise BackendError(
            f"{self.name}: no valid response after {max_retries + 1} attempts: {errors}"
        )


# ---- recorded replay -----------------------------------------------------------------


def recording_key(system: str, user: str, schema: dict) -> str:
    """The fixture key. Deliberately over the prompt only: `now` and `seed` never appear
    in a prompt, so a recording is date-stable and a fixture does not rot on the clock."""
    return sha256_hex(system + "\n\x00\n" + user + "\n\x00\n" + canonical_json(schema))


def record(path: Path, key: str, response: str, note: str = "") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text()) if path.exists() else {}
    data[key] = {"response": response, "note": note}
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


class RecordedBackend(JsonBackendBase):
    name = "recorded"

    def __init__(self, path: Path):
        # [ruling M7] fail at construction, not on the first missed lookup: a silently
        # empty fixture builds fine and only fails later as a confusing RecordingMissing
        # for the *first prompt*, which looks like a wrong-recording bug rather than a
        # wrong-path one. Tests that want an empty fixture create the file explicitly.
        self.path = Path(path)
        if not self.path.is_file():
            raise RecordingMissing(
                f"no recording file at {self.path}: RecordedBackend requires an existing "
                f"fixture (create one with record(), or point --recording / "
                f"DOCKET_LLM_RECORDING at a file that exists)"
            )
        self.data = json.loads(self.path.read_text())
        self.model_id = "recorded"
        self.calls: list[str] = []

    def _raw(self, system, user, schema, budget=None):
        key = recording_key(system, user, schema)
        self.calls.append(key)
        if key not in self.data:
            raise RecordingMissing(
                f"no recording {key} in {self.path}\n"
                f"  system[:80]={system[:80]!r}\n  user[:200]={user[:200]!r}\n"
                f"  (re-record with `uv run python -m docket.agent.record {self.path}`)"
            )
        return self.data[key]["response"]


# ---- live backends -------------------------------------------------------------------

# [ruling R7] A cold 30B MLX model can take minutes to load; a single 120 s scalar timeout
# is the failure mode a live demo cannot afford. Connect stays short so an unreachable
# endpoint fails fast.
DEFAULT_READ_TIMEOUT = 600.0
TRANSPORT_RETRIES = 2
RETRY_STATUS = (429, 500, 502, 503, 504)
BACKOFF_SECONDS = 2.0
TRANSPORT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
                    httpx.ReadError, httpx.RemoteProtocolError)

# [ruling M5] `complete_json`'s schema-validation retries, `OpenAICompatibleBackend`'s
# one-shot structured-output renegotiation, and `_post`'s own transport retries are three
# independently-capped loops that can still multiply: a model that is both flaky and
# never schema-conformant could otherwise chain them into dozens of 600s-read-timeout
# requests for a single `complete_json` call. `_RequestBudget` is shared across all three
# for the duration of one `complete_json` call and hard-stops the whole thing once the
# total number of HTTP attempts crosses this ceiling, regardless of which loop is asking.
MAX_TOTAL_REQUESTS = 10


class _RequestBudget:
    def __init__(self, limit: int = MAX_TOTAL_REQUESTS):
        self.remaining = limit

    def spend(self, url: str) -> None:
        if self.remaining <= 0:
            raise BackendError(
                f"{url}: exceeded the overall request budget of {MAX_TOTAL_REQUESTS} HTTP "
                f"attempts for one complete_json call (schema retries + structured-output "
                f"negotiation + transport retries, combined)"
            )
        self.remaining -= 1


def _timeout(read: float) -> httpx.Timeout:
    return httpx.Timeout(connect=10.0, read=read, write=30.0, pool=10.0)


def _post(url: str, *, body: dict, headers: dict, read: float, budget: _RequestBudget):
    """POST with up to two transport retries and fixed backoff on connect/read errors and
    on 429/5xx. This is NOT independent of the schema-validation retry loop in
    `complete_json` or the structured-output renegotiation loop in
    `OpenAICompatibleBackend._raw` [ruling M5 — correcting an earlier version of this
    docstring that claimed the two never compound]: all three share one `_RequestBudget`
    per `complete_json` call, so the worst case is capped at `MAX_TOTAL_REQUESTS` total
    HTTP attempts, not their product."""
    last: Exception | None = None
    for attempt in range(TRANSPORT_RETRIES + 1):
        budget.spend(url)
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=_timeout(read))
        except TRANSPORT_ERRORS as exc:
            last = exc
        else:
            if r.status_code in RETRY_STATUS and attempt < TRANSPORT_RETRIES:
                log.warning("backend HTTP %s from %s; retrying", r.status_code, url)
                time.sleep(BACKOFF_SECONDS)
                continue
            return r
        if attempt < TRANSPORT_RETRIES:
            log.warning("backend transport error from %s (%s); retrying", url, last)
            time.sleep(BACKOFF_SECONDS)
    raise BackendError(f"{url}: transport failed after {TRANSPORT_RETRIES + 1} attempts: {last}")


def _raise_for_status(r, url: str) -> None:
    """[ruling I6] Convert a raw `httpx.HTTPStatusError` into a `DocketError` before it
    can escape the backend abstraction — plan 07 imports these functions directly, and an
    unhandled `httpx` exception there is an unhandled 500, not a settings-screen error."""
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise BackendError(f"{url}: HTTP {r.status_code}: {r.text[:200]}") from exc


class OpenAICompatibleBackend(JsonBackendBase):
    name = "openai-compatible"

    def __init__(self, *, model: str, base_url: str, api_key: str,
                 timeout: float | None = None):
        self.model_id = check_model_policy(model)       # [ruling R3]
        self.base_url = base_url.rstrip("/")
        self._key = api_key
        self.read_timeout = timeout or _env_timeout()
        # [ruling N5] a fallback budget for calling `_raw` directly, standalone, without
        # going through `complete_json` first (which otherwise passes its own per-call
        # budget as an explicit argument — see `_raw` below).
        self._budget = _RequestBudget()
        # [ruling R8] which structured-output mode actually worked, recorded so
        # ingestionProvenance can name it and a silent downgrade is visible in the record.
        # [ruling I6] in `_raw` below, this only ever changes once an HTTP call in the
        # new mode has succeeded — never merely attempted — except on the R8
        # validation-failure downgrade (`on_validation_failure`, just below): that path
        # flips it eagerly, before the next attempt, because it's a forward-looking hint
        # for what to try next rather than a provenance claim about what just happened.
        # A response that fails validation produces no object, so nothing is ever
        # misattributed to it in practice [ruling N4].
        self.structured_mode = "json_schema"

    @property
    def extractor(self) -> str:
        return f"{self.name}:{self.model_id}/{self.structured_mode}"

    def on_validation_failure(self) -> None:
        # A server that answers 200 while ignoring the schema is the common local case.
        if self.structured_mode == "json_schema":
            log.warning("%s ignored json_schema; falling back to json_object", self.model_id)
            self.structured_mode = "json_object"

    def _response_format(self, mode: str, schema: dict) -> dict:
        if mode == "json_schema":
            return {"type": "json_schema",
                    "json_schema": {"name": "docket", "schema": schema, "strict": False}}
        return {"type": "json_object"}

    def _raw(self, system, user, schema, budget=None):
        # [ruling N5] prefer the budget threaded down from `complete_json` (fresh per
        # call, so two concurrent calls on this instance can't share or clobber one
        # another's counter); fall back to the instance-level budget set in `__init__`
        # only when `_raw` is called standalone, without going through `complete_json`.
        budget = budget if budget is not None else self._budget
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        mode = self.structured_mode
        for attempt in range(2):                      # at most one renegotiation
            body = {"model": self.model_id, "temperature": 0,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": user}],
                    "response_format": self._response_format(mode, schema)}
            r = _post(f"{self.base_url}/chat/completions", body=body, headers=headers,
                      read=self.read_timeout, budget=budget)
            # [ruling R8] any 4xx while asking for json_schema is a capability answer,
            # not an error: downgrade once and ask again. The plan's old rule (400 AND
            # "response_format" in the body text) missed 422 and every terse error page.
            # [ruling I6] EXCEPT 401/403/404: those mean "wrong key" or "wrong path", not
            # "this server doesn't support json_schema" — retrying them as json_object
            # would waste a request and misreport why the call actually failed.
            if (attempt == 0 and mode == "json_schema"
                    and 400 <= r.status_code < 500 and r.status_code not in (401, 403, 404)):
                log.warning("%s refused json_schema (HTTP %s); retrying as json_object",
                            self.base_url, r.status_code)
                mode = "json_object"
                continue
            _raise_for_status(r, self.base_url)
            # [ruling I6] record the mode only now — a call in this mode just succeeded.
            self.structured_mode = mode
            return r.json()["choices"][0]["message"]["content"]
        raise BackendError(f"{self.base_url}: could not negotiate structured output")


class AnthropicBackend(JsonBackendBase):
    """Kept to prove model-agnosticism, not to express a preference [ruling R18]. Never
    the default; never named in user-facing text.

    `base_url` follows Anthropic's own convention (no `/v1` segment — the API version is
    the `anthropic-version` header instead), unlike `OpenAICompatibleBackend`, which
    requires `/v1` in its `base_url` (OpenAI's convention, which Ollama also follows).
    A trailing `/v1` is stripped automatically [ruling M6] so passing either the
    OpenAI-style or the bare form both resolve to the same, correct endpoint.
    """

    name = "anthropic"

    def __init__(self, *, model: str, base_url: str = "https://api.anthropic.com",
                 api_key: str, timeout: float | None = None):
        self.model_id = check_model_policy(model)       # [ruling R3]
        base_url = base_url.rstrip("/")
        if base_url.endswith("/v1"):                     # [ruling M6]
            base_url = base_url[: -len("/v1")]
        self.base_url = base_url
        self._key = api_key
        self.read_timeout = timeout or _env_timeout()
        # [ruling N5] fallback budget for a standalone `_raw` call — see
        # OpenAICompatibleBackend.__init__ for the full rationale.
        self._budget = _RequestBudget()

    def _raw(self, system, user, schema, budget=None):
        budget = budget if budget is not None else self._budget
        body = {"model": self.model_id, "max_tokens": 8192, "temperature": 0,
                "system": system, "messages": [{"role": "user", "content": user}],
                "tools": [{"name": "emit", "description": "Emit the structured result",
                           "input_schema": schema}],
                "tool_choice": {"type": "tool", "name": "emit"}}
        headers = {"x-api-key": self._key, "anthropic-version": "2023-06-01",
                   "Content-Type": "application/json"}
        r = _post(f"{self.base_url}/v1/messages", body=body, headers=headers,
                  read=self.read_timeout, budget=budget)
        _raise_for_status(r, self.base_url)              # [ruling I6]
        for block in r.json()["content"]:
            if block.get("type") == "tool_use":
                return json.dumps(block["input"])
        raise BackendError("anthropic: no tool_use block in response")


def list_models(*, base_url: str, api_key: str = "", timeout: float | None = None,
                include_denylisted: bool | None = None) -> list[dict]:
    """`GET {base_url}/models` — the model picker plan 07 needs (frontend spec §6
    `/api/settings/models`). Live network: never called from a test.

    [ruling M3] Returns `[{"id": ..., "denylisted": bool}, ...]`, sorted by id. By
    default, denylisted ids are dropped entirely — a model picker that never shows a
    PRC-origin id is the point of the policy, and R2 already forbids one appearing in a
    screenshot. Pass `include_denylisted=True` (or leave it unset while
    `DOCKET_LLM_ALLOW_DENYLISTED=1`, mirroring every other resolution point) to include
    them anyway, each explicitly marked `"denylisted": True` so a settings screen can
    render a visible warning instead of silently hiding or silently allowing one.
    """
    if include_denylisted is None:
        include_denylisted = os.environ.get(ALLOW_ENV) == "1"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    r = httpx.get(f"{base_url.rstrip('/')}/models", headers=headers,
                  timeout=_timeout(timeout or 30.0))
    _raise_for_status(r, base_url)                        # [ruling I6]
    ids = sorted(str(m.get("id")) for m in r.json().get("data", []) if m.get("id"))
    out = []
    for mid in ids:
        denylisted = is_denylisted(mid)
        if denylisted and not include_denylisted:
            continue
        out.append({"id": mid, "denylisted": denylisted})
    return out


# ---- configuration surface [rulings R6, R3] -------------------------------------------

CONFIG_ENV = "DOCKET_LLM_CONFIG"
DEFAULT_CONFIG = Path.home() / ".config" / "docket" / "llm.json"
CONFIG_FIELDS = ("provider", "model", "baseUrl")
# A config file may not carry a credential under ANY of these spellings. Rejecting the
# file outright (rather than dropping the key) is the point: a key that lands on disk has
# already leaked, and silently ignoring it teaches the writer that persisting one works.
SECRET_CONFIG_KEYS = ("apikey", "api_key", "key", "token", "secret", "authorization",
                      "password", "bearer")
# [ruling M7] Resolved against the repo root, not the process CWD: a relative path here
# meant "no recording, ever" the moment `docket` ran from anywhere else. `backend.py`
# lives at src/docket/agent/backend.py, three parents up from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RECORDING = str(_REPO_ROOT / "tests" / "fixtures" / "recorded" / "default.json")


@dataclass(frozen=True)
class BackendSettings:
    provider: str
    model: str
    base_url: str
    recording: str
    timeout: float


def _env_timeout() -> float:
    raw = os.environ.get("DOCKET_LLM_TIMEOUT", "")
    try:
        return float(raw) if raw else DEFAULT_READ_TIMEOUT
    except ValueError:
        log.warning("DOCKET_LLM_TIMEOUT=%r is not a number; using %s", raw,
                    DEFAULT_READ_TIMEOUT)
        return DEFAULT_READ_TIMEOUT


def config_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    return Path(os.environ.get(CONFIG_ENV) or DEFAULT_CONFIG)


def _find_secret_key(data, _seen: int = 0) -> str | None:
    """[ruling I2] Walk a parsed JSON value for a secret-shaped key at ANY nesting depth,
    not just the top level — `{"model": {"api_key": "..."}}` is just as much a leaked
    credential as a top-level one, and the shallow version of this check both missed it
    and then crashed downstream (`check_model_policy` expects a string, not a dict)."""
    if _seen > 50:                      # pathological/cyclic input: refuse, don't hang
        return "<value nested too deeply>"
    if isinstance(data, dict):
        for k, v in data.items():
            if k.strip().lower().replace("-", "_") in SECRET_CONFIG_KEYS:
                return k
            found = _find_secret_key(v, _seen + 1)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_secret_key(item, _seen + 1)
            if found is not None:
                return found
    return None


def load_config(path: str | Path | None = None) -> dict:
    """Provider / model / base URL only, and each must be a string. A file naming a
    credential anywhere in its structure is refused, never merely emptied of it."""
    p = config_path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise PolicyRefusal(f"{p} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyRefusal(f"{p} must be a JSON object")
    hit = _find_secret_key(data)
    if hit is not None:
        # Name the key, never the value.
        raise PolicyRefusal(
            f"{p} contains {hit!r} (at any nesting depth): the model config file may hold "
            f"provider, model and baseUrl only. API keys come from the environment and are "
            f"never persisted."
        )
    unknown = sorted(set(data) - set(CONFIG_FIELDS))
    if unknown:
        raise PolicyRefusal(f"{p} has unknown keys {unknown}; allowed: {list(CONFIG_FIELDS)}")
    for field in CONFIG_FIELDS:
        if field in data and not isinstance(data[field], str):
            # [ruling I2] a non-string value here (e.g. a nested object with no secret-
            # shaped key inside it) must not reach `check_model_policy` and crash there
            # with a bare TypeError; refuse it here, by name, as a PolicyRefusal instead.
            raise PolicyRefusal(
                f"{p}: {field!r} must be a string, got {type(data[field]).__name__}"
            )
    return {k: v for k, v in data.items() if v}


def write_config(*, provider: str | None = None, model: str | None = None,
                 base_url: str | None = None, path: str | Path | None = None) -> Path:
    """Persist provider/model/baseUrl, 0600, after checking the model against the
    denylist [ruling I1 — reversing an earlier version of this function that deferred
    the check to the next read]. Plan 07's `PUT /api/settings/model` calls this directly
    and must fail the request rather than silently persist a refused choice."""
    if model:
        check_model_policy(model)                       # [ruling R3/I1]
    p = config_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in
            (("provider", provider), ("model", model), ("baseUrl", base_url)) if v}
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    # [ruling M8] create at 0600 directly rather than write-then-chmod, so the file is
    # never briefly readable at the process umask.
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(p, 0o600)          # normalize even if `p` already existed at looser perms
    return p


def resolve_settings(*, provider: str | None = None, model: str | None = None,
                     base_url: str | None = None, recording: str | None = None,
                     timeout: float | None = None) -> BackendSettings:
    """Precedence: explicit arguments (CLI flags) > DOCKET_LLM_* environment > config file.

    The overview said "environment variables only"; ruling R6 widens it so the plan-07
    settings screen has somewhere to persist a choice. The API key is not part of this:
    it is read from the environment (or held in the server's memory for one session) and
    never written here.
    """
    cfg = load_config()
    settings = BackendSettings(
        provider=provider or os.environ.get("DOCKET_LLM_PROVIDER")
                 or cfg.get("provider") or "recorded",
        model=model or os.environ.get("DOCKET_LLM_MODEL") or cfg.get("model") or "",
        base_url=base_url or os.environ.get("DOCKET_LLM_BASE_URL") or cfg.get("baseUrl") or "",
        recording=recording or os.environ.get("DOCKET_LLM_RECORDING") or DEFAULT_RECORDING,
        timeout=timeout or _env_timeout(),
    )
    check_model_policy(settings.model)          # [ruling R3] every resolution point
    return settings


def backend_from_settings(s: BackendSettings, *, api_key: str | None = None) -> Backend:
    key = os.environ.get("DOCKET_LLM_API_KEY", "") if api_key is None else api_key
    if s.provider == "recorded":
        return RecordedBackend(Path(s.recording))
    if s.provider == "openai-compatible":
        if not s.base_url:
            raise PolicyRefusal("openai-compatible needs a base URL "
                                "(--base-url or DOCKET_LLM_BASE_URL)")
        return OpenAICompatibleBackend(model=s.model, base_url=s.base_url, api_key=key,
                                       timeout=s.timeout)
    if s.provider == "anthropic":
        return AnthropicBackend(model=s.model,
                                base_url=s.base_url or "https://api.anthropic.com",
                                api_key=key, timeout=s.timeout)
    raise PolicyRefusal(f"unknown provider {s.provider!r}")


def backend_from_env(**overrides) -> Backend:
    """Kept under its plan name; now a thin wrapper over the precedence chain."""
    api_key = overrides.pop("api_key", None)
    return backend_from_settings(resolve_settings(**overrides), api_key=api_key)
