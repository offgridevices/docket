# src/docket/agent/record.py
"""Maintainer-only re-recording helper for `RecordedBackend` fixtures [pre-flight defect
21: the path form, matching the message `RecordedBackend` itself prints on a miss].

    uv run python -m docket.agent.record <recording.json> [--force]

[fix round 1, issue M4] `record_case`/`main` refuse to silently clobber an existing
key: if `path` already stores a response for the key a case just produced and the new
response differs, the write is refused (a one-line diff naming the key and both
responses' sha256) unless `--force` (CLI) / `force=True` (`record_case`) is given. An
identical re-recording is always a no-op regardless of `--force`.

This is the one module in this package that makes REAL network calls against a LIVE
backend, and it is never imported by a test with a live backend behind it [ruling R9]:
`tests/agent/test_backend.py::test_only_this_module_constructs_a_live_backend` scans every
other test file for a live-backend construction and would fail if one leaked in here.
`tests/agent/test_record.py` exercises `main()`'s argument handling, its refusal, and its
warning against a fake, in-process `Backend` passed in directly — dependency injection, not
`docket.agent.backend.backend_from_settings`, is what keeps that test off the network.

Settings resolve exactly the way every `docket agent ...` command resolves them
(`--provider`/`--model`/`--base-url` beat `DOCKET_LLM_*` env, which beats the config file;
see `docket.agent.backend.resolve_settings`) — this module takes no flags of its own, so a
maintainer sets those the normal way (environment or config) before running it. It refuses
outright if the resolved (or injected) backend is `"recorded"`: there is nothing to record
against a fixture, and the point of this tool is to produce one.

A "case" is a `(system, user, schema)` triple this module already knows how to ask for —
built from the SAME prompt-construction code the real pipeline uses (`docket.agent.elicit`,
here), so the fixture key `record_case` writes is the exact key that code will later look
up. Only one case ships (`"elicit"`), as a template a maintainer edits for a specific source
artifact before recording: Stage P's and Stage N's prompts are built from a real episode's
graph state (`docket.agent.plan`/`docket.agent.narrate`), and reproducing one generically
here would mean carrying a second copy of a Demo graph that could drift from the real one.
A maintainer re-recording `plan.json`/`narrate-*.json` builds a `Case` from the graph in
hand and calls `record_case(backend, path, case)` directly — see `tests/fixtures/recorded/
README.md` ruling R10: read the numbers back out of the graph, never hand-type one in.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from docket.agent.backend import Backend, record, recording_key, resolve_settings
from docket.canon import canonical_json, sha256_hex

__all__ = ["Case", "CASES", "RecordingConflict", "record_case", "main"]


class RecordingConflict(Exception):
    """[fix round 1, issue M4] Raised by `record_case` when `path` already has `case`'s
    key stored with a response that differs from the one just recorded, and `force` was
    not given. A maintainer re-recording a fixture is exactly the situation where
    silently clobbering a previously-reviewed value is the failure mode to guard
    against; an identical re-recording (the common case — nothing about the world
    changed) is a no-op, never a conflict."""

    def __init__(self, key: str, old_response: str, new_response: str):
        self.key = key
        self.old_sha256 = sha256_hex(old_response)
        self.new_sha256 = sha256_hex(new_response)
        super().__init__(
            f"{key}: existing recorded response differs from the newly recorded one "
            f"(old sha256={self.old_sha256} new sha256={self.new_sha256}); pass "
            f"force=True (CLI: --force) to overwrite, or leave the fixture alone"
        )


class Case(NamedTuple):
    system: str
    user: str
    schema: dict
    note: str


def _elicit_case() -> Case:
    """A template Stage-E case. Edit `request_text`/`source_artifact`/`policy_id` below
    for the actual source artifact being elicited before recording against it — the
    values here are placeholders, not a claim about any real request."""
    from docket.agent.elicit import ELICITATION_SCHEMA, USER_TEMPLATE
    from docket.agent.prompts import system_prompt

    user = USER_TEMPLATE.format(
        source_artifact="sources/example-request.md",
        request_text=(
            "Replace this placeholder with the exact text of the request being "
            "elicited, then re-run this case before trusting the recorded response."
        ),
        policy_id="pol-1",
    )
    return Case(
        system=system_prompt(), user=user, schema=ELICITATION_SCHEMA,
        note="template elicitation case; edit request_text/source_artifact/policy_id "
             "for the real source artifact before recording",
    )


#: name -> zero-argument builder, so building a `Case` (which may load prompt text from
#: disk) is deferred until this module is actually asked to record something.
CASES: dict[str, Callable[[], Case]] = {"elicit": _elicit_case}


def _existing_response(path: Path, key: str) -> str | None:
    """The response already stored at `key` in the fixture at `path`, or `None` if the
    file does not exist yet or does not carry that key."""
    path = Path(path)
    if not path.is_file():
        return None
    entry = json.loads(path.read_text()).get(key)
    return entry["response"] if entry else None


def record_case(backend: Backend, path: Path, case: Case, *, force: bool = False) -> str:
    """Run `case` through `backend.complete_json` and write the *validated* response
    into the fixture at `path`, keyed exactly as `RecordedBackend` will look it up later
    (`recording_key`). Returns the key written.

    Goes through the public `complete_json`, never a backend's own `_raw`: a response
    that reaches here has already passed schema validation (including any
    structured-output renegotiation a live backend needed), so what lands in the fixture
    is guaranteed replayable — not whatever the network happened to send on the first,
    possibly-malformed, attempt.

    [fix round 1, issue M4] If `path` already has a stored response under this exact
    key: an IDENTICAL response is a no-op (the file is not rewritten at all — nothing
    about the world changed); a DIFFERENT response raises `RecordingConflict` unless
    `force=True`, so a maintainer re-recording one fixture cannot silently clobber a
    previously-reviewed value for another case sharing the same file.
    """
    obj = backend.complete_json(system=case.system, user=case.user, schema=case.schema)
    key = recording_key(case.system, case.user, case.schema)
    new_response = canonical_json(obj)
    existing = _existing_response(path, key)
    if existing is not None:
        if existing == new_response:
            return key                                     # identical: no-op
        if not force:
            raise RecordingConflict(key, existing, new_response)
        print(
            f"overwriting {key}: old sha256={sha256_hex(existing)} "
            f"new sha256={sha256_hex(new_response)} (--force)",
            file=sys.stderr,
        )
    record(path, key, new_response, note=case.note)
    return key


_USAGE = "usage: python -m docket.agent.record <recording.json> [--force]"
_REFUSAL = (
    "refusing: the resolved provider is \"recorded\" — there is nothing to record "
    "against a fixture. Set --provider/DOCKET_LLM_PROVIDER (and --model/--base-url as "
    "needed) to a live backend first."
)
_WARNING = (
    "WARNING: this makes REAL network calls against a LIVE backend and may cost money. "
    "Recording into: {path}"
)


def main(argv: list[str] | None = None, *, backend: Backend | None = None) -> int:
    """Parse `<recording.json> [--force]`, resolve (or accept an injected) backend,
    refuse a `"recorded"` one, print the cost warning, run every case in `CASES`, and
    report the key each one wrote. Returns the process exit code; never raises for a
    usage, policy, or recording-conflict refusal — those are printed to stderr and
    returned as a non-zero code, the same convention every `docket` CLI command uses.

    `backend`, when given, is used as-is and never resolved from settings — this is
    what lets `tests/agent/test_record.py` exercise every branch here against a fake,
    in-process backend without this module (or the test) ever constructing a live one.

    [fix round 1, issue M4] `--force` is passed straight through to `record_case`: a
    case whose key already exists in `path` with a DIFFERENT response is otherwise
    refused (printing the one-line diff summary from the `RecordingConflict` raised)
    without touching the file; an identical re-recording is always a silent no-op,
    `--force` or not.
    """
    argv = list(sys.argv if argv is None else argv)
    if len(argv) not in (2, 3) or (len(argv) == 3 and argv[2] != "--force"):
        print(_USAGE, file=sys.stderr)
        return 2
    path = Path(argv[1])
    force = len(argv) == 3

    if backend is None:
        settings = resolve_settings()
        if settings.provider == "recorded":
            print(_REFUSAL, file=sys.stderr)
            return 1
        from docket.agent.backend import backend_from_settings

        backend = backend_from_settings(settings)
    if getattr(backend, "name", None) == "recorded":
        print(_REFUSAL, file=sys.stderr)
        return 1

    print(_WARNING.format(path=path), file=sys.stderr)
    for name, build_case in CASES.items():
        try:
            key = record_case(backend, path, build_case(), force=force)
        except RecordingConflict as e:
            print(f"refusing to overwrite {name} ({e}); pass --force to overwrite",
                  file=sys.stderr)
            return 1
        print(f"recorded {name} -> {key}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
