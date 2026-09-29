"""Sessions: a session is a *copy* of a demo store, never the committed fixture itself.

Opening Demo A five times at an event produces five directories under
`state_dir()/sessions/` and leaves `demos/a_cbo_gcv_2013/out/graph` byte-identical,
which is the only way a committed fixture and a live demo can share one store. A "new"
session starts from an empty `Graph` seeded with one human-authored `Policy`.
"""
from __future__ import annotations

import json
import shutil
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from docket.api.config import DEMOS, demos_dir, human_actor, state_dir
from docket.errors import TransitionRefused
from docket.store import Graph

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def default_policy_json(policy_id: str) -> dict:
    """The demonstration policy (`fixtures/policy-default.json`), re-keyed to
    `policy_id`. Used for `"pol-default"` itself (below, a "new" session's own seed)
    and, lazily, for `RECORDED_REQUEST_POLICY` — `routes/agent.py::post_elicit` seeds a
    second copy under that id the first time a caller actually elicits against
    `tests/fixtures/recorded/elicit.json` (see that call site, and `api.config`'s
    comment on the constant, for why one id is not enough)."""
    pol = json.loads((_FIXTURES_DIR / "policy-default.json").read_text())
    pol["id"] = policy_id
    return pol


def _now() -> str:
    """UTC wall-clock timestamp for API-driven writes.

    The kernel never reads the clock — `now` always arrives as an argument, which is
    exactly the contract that keeps a computed record reproducible. The API is a
    server, not the kernel: it is allowed a clock, and this is the one place in `api/`
    that reads it, so every kernel call downstream still receives `now` as a plain
    string argument, exactly the contract the kernel expects.
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Session:
    id: str
    source: str
    path: Path
    created: str
    graph: Graph
    lock: threading.RLock = field(default_factory=threading.RLock)

    def save(self) -> None:
        self.graph.save(self.path / "graph")


class SessionStore:
    """A session is a *copy*. Opening Demo A five times at an event produces five
    directories and leaves `demos/a_cbo_gcv_2013/out/graph` byte-identical, which is the
    only way a committed fixture and a live demo can share one store."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, source: str) -> Session:
        if source not in ({"new"} | set(DEMOS)):
            raise ValueError(f"unknown source {source!r}")
        sid = f"s-{uuid.uuid4().hex[:12]}"
        path = state_dir() / "sessions" / sid
        path.mkdir(parents=True)
        if source == "new":
            g = Graph()
            actor = human_actor()
            pol = json.loads((_FIXTURES_DIR / "policy-default.json").read_text())
            g.put({**pol, "createdBy": actor, "createdAt": _now()}, actor)
        else:
            src = demos_dir() / DEMOS[source] / "out" / "graph"
            if not (src / "log.jsonl").is_file():
                raise FileNotFoundError(f"demo store not built: {src}")
            shutil.copytree(src, path / "graph")
            g = Graph.load(path / "graph")
        s = Session(id=sid, source=source, path=path, created=_now(), graph=g,
                    lock=threading.RLock())
        if source == "new":
            s.save()
        with self._lock:
            self._sessions[sid] = s
        return s

    def get(self, sid: str) -> Session:
        with self._lock:
            if sid not in self._sessions:
                raise KeyError(sid)
            return self._sessions[sid]

    def list(self) -> list[dict]:
        with self._lock:
            sessions = list(self._sessions.values())
        return [{"id": s.id, "source": s.source, "created": s.created}
                for s in sorted(sessions, key=lambda s: s.created)]

    def delete(self, sid: str) -> None:
        with self._lock:
            s = self._sessions.pop(sid, None)
        if s is None:
            raise KeyError(sid)
        shutil.rmtree(s.path, ignore_errors=True)


@contextmanager
def writing(session: Session):
    """Hold the session lock for the whole call and save the store afterwards.

    Two callers hitting `accept` on the same object concurrently would otherwise both
    read rev n and both write rev n+1, and the second write would be refused by the
    store's append-only check with a message about revisions rather than about
    concurrency. One lock per session makes the refusal impossible instead of confusing.

    `kernel.lifecycle.transition()` writes the refusal record into the graph — via a
    normal `g.put()` that succeeds — *before* raising `TransitionRefused`; the state does
    not move, but the attempt is genuinely part of the record. A refusal that is real in
    memory but never reaches disk is indistinguishable, after a restart, from a refusal
    that was never recorded at all, which is exactly the silence the gate design exists
    to prevent. So `TransitionRefused` still saves, then re-raises. Any other exception
    leaves the store on disk untouched: `Graph.put()` validates before it mutates
    anything (schema, id, authority, append-only ordering all run before `_latest`/
    `_history`/`_log` are touched), so `ValidationError`/`AuthorityViolation` and the
    like mean nothing was actually written, and an unexpected bug is not something this
    context manager should paper over by persisting whatever partial state it left
    behind.
    """
    with session.lock:
        try:
            yield session.graph
        except TransitionRefused:
            session.save()
            raise
        else:
            session.save()
