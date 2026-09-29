"""A hand-rolled SSE channel: one per session, fed by the agent routes' worker threads,
drained by `GET /api/stream/{session}` (plan 07 Task 3; fan-out and the bounded ring are
the T3 fix round, ruling I1/I2).

No new dependency (`sse-starlette` is deliberately not taken — plan 07's Dependencies
section). The agent routes run their kernel/agent calls in a worker thread via
`anyio.to_thread.run_sync` (the graph and the backend are synchronous, and holding
`session.lock` for the call's whole duration is `sessions.writing`'s own contract); the
worker thread calls `Channel.emit(...)` while the event loop stays free to serve this
module's async generator on any number of concurrent `GET /api/stream/{session}`
connections.

Every `Channel` is a broadcast, not a point-to-point queue [ruling I1]: `subscribe()`
creates its own `asyncio.Queue` per caller, added to a shared set under a lock, and
`emit()` puts a copy of the event onto every queue currently in that set — two browser
tabs, a React StrictMode double-mount, or an `EventSource` reconnect racing the old
connection's teardown all see the full stream, not a disjoint half of it. Delivery
crosses from the emitting worker thread to the event loop via
`loop.call_soon_threadsafe(...)` [ruling M7]: a subscriber's `await queue.get()` wakes as
soon as an item is scheduled, rather than a fixed-interval poll grabbing and releasing an
`anyio` thread-pool slot several times a second for every open stream — the same
thread-pool `post_elicit`/`post_dispatch`'s own `run_sync(_run)` calls and every sync
`def` route share.

Each channel also keeps a bounded ring of its last `_RING_SIZE` events, each carrying a
monotonic `seq` [ruling I2]. A plain `GET /api/stream/{s}` (no `since`) is a *live*
subscription only: a late subscriber sees nothing that happened before it connected,
never a replay of a whole session's history mistaken for progress. `GET
/api/stream/{s}?since=<seq>` additionally replays every ring event with a higher `seq`
before switching to live delivery — for a client that already knows how far it got (a
page reload, a reconnect) and wants exactly what it missed, no more. If some of that
range has already fallen out of the ring, the replay opens with a synthetic `dropped`
event naming the gap, rather than silently skipping straight past it.

Event names are exactly the four the frontend spec fixes: `stage`, `object`, `finding`,
`done`, plus `error` for a failed call and `dropped` for an unrecoverable ring gap.
Payload shapes are the agent routes' concern, not this module's — `Channel.emit` takes
whatever dict a caller gives it and JSON-encodes it verbatim (canonical: sorted keys,
matching `app.CanonicalJSONResponse`'s convention for every other response body in this
service).

[ruling M6] This registry (`app.state.channels`) is per-process, in memory, with no
cross-process fan-out of any kind. The deployment this module assumes is **one uvicorn
worker**: `uvicorn --workers 2` (or any multi-process deployment) would put the mutating
route and a given `GET /api/stream/{s}` connection in different processes some of the
time, and an event emitted in one process is never delivered to a subscriber connected to
another. `docket ui` must pin a single worker for this reason.
"""
from __future__ import annotations

import asyncio
import json
import threading
from collections import deque
from collections.abc import AsyncIterator

from fastapi import Request
from starlette.responses import StreamingResponse

#: Put onto every live subscriber's queue to end its `subscribe()` generator cleanly —
#: used by `Channel.close()`. Nothing in the agent routes calls `close()` on its own; it
#: exists for tests (a synchronous `TestClient` cannot hold a stream open while a mutating
#: call runs concurrently — see `tests/api/test_stream.py`'s own module docstring) and for
#: a future caller such as `DELETE /api/session/{s}`.
_CLOSE = object()

#: How long `subscribe()`'s live wait blocks before sending a keepalive comment — "gives
#: the client something to notice when the server dies" (plan 07 Task 3). Also the single
#: `await`'s timeout, so the loop still gets a chance to re-check
#: `request.is_disconnected()` periodically even with no traffic; this is not the busy
#: poll ruling M7 removed; it is one native async wait with a deadline.
_HEARTBEAT_SECONDS = 15.0

#: Events kept per session, oldest dropped first once the ring is full [ruling I2].
_RING_SIZE = 500


def _format(event: str, data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


class Channel:
    """One session's SSE stream: a fan-out broadcast plus a bounded, seq'd ring.

    `emit`/`close` are the only methods a worker thread calls, and both are safe to call
    from any thread, with or without a running event loop, and with zero, one, or many
    live subscribers.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Captured the moment a caller running *on* the event loop touches this channel
        # (construction, if that happens inside a route; otherwise the first
        # `subscribe()`). `emit()`/`close()` need it to hop from a worker thread back
        # onto the loop via `call_soon_threadsafe`; until it is known, there cannot yet
        # be a live subscriber to deliver to, so `emit`/`close` simply skip delivery.
        try:
            self._loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        self._subscribers: set[asyncio.Queue] = set()
        self._history: deque[tuple[int, str, dict]] = deque(maxlen=_RING_SIZE)
        self._seq = 0
        #: The highest `seq` ever evicted from `_history`. `0` means nothing has been
        #: evicted yet — every event since the channel's birth is still in the ring.
        self._evicted = 0
        self._closed = False

    def emit(self, event: str, data: dict) -> None:
        """Record the event in the ring and hand a copy to every current subscriber.

        Thread-safe: called from the agent routes' worker thread while the event loop
        concurrently drains zero or more `subscribe()` generators on the request-handling
        thread. Delivery is `loop.call_soon_threadsafe(queue.put_nowait, ...)` [ruling
        M7] rather than a lock a worker thread would have to block on.
        """
        item = dict(data)
        with self._lock:
            self._seq += 1
            entry = (self._seq, event, item)
            if len(self._history) == self._history.maxlen:
                self._evicted = self._history[0][0]
            self._history.append(entry)
            subscribers = list(self._subscribers)
            loop = self._loop
        if loop is not None:
            for q in subscribers:
                loop.call_soon_threadsafe(q.put_nowait, entry)
        # `loop is None` only when nothing has ever run on the event loop for this
        # channel, which means `subscribers` is necessarily empty too (a subscriber can
        # only exist once `subscribe()` — itself always driven by the event loop — has
        # run at least once) — there is nothing to deliver to.

    def close(self) -> None:
        """Mark the channel closed and wake every live subscriber so its `subscribe()`
        generator returns. A subscriber that connects *after* `close()` still gets
        whatever `since` asks for, then also returns immediately rather than waiting."""
        with self._lock:
            self._closed = True
            subscribers = list(self._subscribers)
            loop = self._loop
        if loop is not None:
            for q in subscribers:
                loop.call_soon_threadsafe(q.put_nowait, _CLOSE)

    async def subscribe(self, request: Request, since: int | None = None) -> AsyncIterator[str]:
        """Yield SSE frames for this channel.

        With `since=None` (the default: a plain `GET /api/stream/{s}`), this is a live
        subscription only — nothing that happened before this call started is replayed
        [ruling I2]. With `since=<seq>`, every ring event with a higher `seq` is replayed
        first, preceded by a synthetic `dropped` event if part of that range has already
        fallen out of the ring; live delivery follows either way.

        The subscriber's own `asyncio.Queue` is registered *before* the ring is read
        (both under the same lock), so no event emitted concurrently with this call can
        be missed or double-delivered: anything not yet in the ring snapshot is
        necessarily still to come, and arrives only through the queue.
        """
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._loop is None:
                self._loop = loop
            self._subscribers.add(queue)
            backlog = list(self._history) if since is not None else []
            evicted = self._evicted
            closed = self._closed
        try:
            if since is not None:
                if evicted > since:
                    yield _format("dropped", {
                        "from": since + 1, "to": evicted, "count": evicted - since,
                    })
                for seq, event, data in backlog:
                    if seq > since:
                        yield _format(event, data)
            if closed:
                return
            while True:
                if await request.is_disconnected():
                    return
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if item is _CLOSE:
                    return
                _seq, event, data = item
                yield _format(event, data)
        finally:
            with self._lock:
                self._subscribers.discard(queue)


class Channels:
    """One `Channel` per session id, created lazily and never removed within this
    process's lifetime — a session already lives until the process exits or
    `DELETE /api/session/{s}` runs, and a stale, empty channel costs one bounded ring."""

    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> Channel:
        with self._lock:
            channel = self._channels.get(session_id)
            if channel is None:
                channel = Channel()
                self._channels[session_id] = channel
            return channel


def channels_for(request: Request) -> Channels:
    """The process-lifetime `Channels` registry, stored lazily on `app.state` rather
    than in `app.py`'s factory — `app.py` is plan 07 Task 1's committed file, and a
    registry only the agent routes and this module's own route ever read or write has no
    reason to be wired through it."""
    existing = getattr(request.app.state, "channels", None)
    if existing is not None:
        return existing
    created = Channels()
    request.app.state.channels = created
    return created


def sse_response(channel: Channel, request: Request,
                 *, since: int | None = None) -> StreamingResponse:
    return StreamingResponse(
        channel.subscribe(request, since=since),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
