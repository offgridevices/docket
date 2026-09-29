"""Plan 07 Task 3: the hand-rolled SSE channel (fan-out and the bounded ring are the T3
fix round, rulings I1/I2).

Starlette's synchronous `TestClient` cannot exercise genuine concurrency: its transport
(`starlette.testclient._TestClientTransport.handle_request`) runs the whole ASGI
callable to completion on a blocking portal — `portal.call(self.app, scope, receive,
send)` — buffering the entire response body into an `io.BytesIO()` *before* `.get()` or
even `.stream()`'s `__enter__` returns anything to the caller. A stream generator that
blocks waiting for more events (this module's own, correctly, under a real ASGI server)
therefore hangs the test process forever under `TestClient`, rather than proving
anything about concurrent delivery.

So most of these tests either (a) publish into the channel directly or via a mutating
call, `close()` the channel explicitly (the same thing a real disconnect does, just
driven by the test instead of a dropped socket), and only then `GET` the stream — a
single, fully-buffered response the synchronous `TestClient` can return — or (b), for the
one thing that genuinely requires concurrent delivery (I1's fan-out: does every
subscriber on one session see every event, not a disjoint fraction of it), start a real
uvicorn server on an ephemeral loopback port and drive it with real, concurrently-open
HTTP connections. That test is `test_three_concurrent_subscribers_on_one_session_...`,
below.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import httpx
import uvicorn

from docket.agent.backend import RecordedBackend
from docket.api.routes.agent import _agent
from docket.api.stream import Channels

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "recorded"
REQUEST_TEXT = (REPO / "tests" / "fixtures" / "requests" / "omfv-con-2020-02-25.md").read_text()
SOURCE_ARTIFACT = "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md"

#: The ring's own bound (plan 07 T3 fix round, ruling I2) — hardcoded here rather than
#: imported from `docket.api.stream._RING_SIZE`: it is a documented contract number from
#: the ruling itself, not an implementation detail these tests should track through a
#: private import.
_RING_SIZE = 500


def _parse_sse(text: str) -> list[dict]:
    events: list[dict] = []
    current_event: str | None = None
    for line in text.splitlines():
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            events.append({"event": current_event, "data": json.loads(line[len("data:"):].strip())})
    return events


def _channels(client) -> Channels:
    """The process-lifetime registry, created directly rather than through a route —
    every test below either builds its own scenario straight against a `Channel` (no
    HTTP round trip needed to set one up) or has already created one via a mutating
    call; this is only for the former."""
    channels = getattr(client.app.state, "channels", None)
    if channels is None:
        channels = Channels()
        client.app.state.channels = channels
    return channels


def test_unknown_session_stream_is_404(client):
    r = client.get("/api/stream/nope")
    assert r.status_code == 404


def test_elicit_publishes_stage_object_and_done_in_write_order_when_replayed(client):
    backend = RecordedBackend(FIXTURES / "elicit.json")
    actor = {"actorType": "agent", "actorId": "agent:recorded"}
    client.app.dependency_overrides[_agent] = lambda: (backend, actor)
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]

    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT,
        "policyId": "pol-1", "requestedBy": "NGCV CFT", "episodeId": "ep-sse-elicit",
    })
    assert r.status_code == 200, r.text

    # The channel is created lazily, on `app.state`, by the first route that touches it
    # (`_channel_for` in `routes/agent.py`) — by the time the elicit call above has
    # returned, it exists and already holds every event that call published.
    client.app.state.channels.get(sid).close()

    # [ruling I2] a plain GET (no `since`) is live-only; `since=0` asks for the full
    # ring from the beginning.
    stream = client.get(f"/api/stream/{sid}?since=0")
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(stream.text)

    names = [e["event"] for e in events]
    assert names, "the channel published no events at all"
    assert names[0] == "stage"
    assert any(e["event"] == "object" for e in events)
    assert names[-1] == "done"
    assert "dropped" not in names, "fewer than the ring size was published; nothing evicted"

    done = events[-1]["data"]
    assert done["episode"] == "ep-sse-elicit"
    assert done["ids"]

    object_events = [e["data"] for e in events if e["event"] == "object"]
    assert all(o["authorType"] == "agent" for o in object_events)
    assert all(o["id"] in done["ids"] for o in object_events)
    # [ruling M2] the DecisionEpisode object itself must never appear as one of the
    # `object` events — it is reported through `done.episode`, not as one more DRAFT chip.
    assert done["episode"] not in [o["id"] for o in object_events]


def test_a_plain_get_with_no_since_replays_nothing_even_after_a_full_run(client):
    """[ruling I2] A late subscriber gets nothing unless it asks for `?since=`, even
    though the channel already holds a full session's worth of history — the defect the
    review found was a full-history replay dressed up as live progress."""
    backend = RecordedBackend(FIXTURES / "elicit.json")
    actor = {"actorType": "agent", "actorId": "agent:recorded"}
    client.app.dependency_overrides[_agent] = lambda: (backend, actor)
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]

    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT,
        "policyId": "pol-1", "requestedBy": "NGCV CFT", "episodeId": "ep-sse-nosince",
    })
    assert r.status_code == 200, r.text

    client.app.state.channels.get(sid).close()

    stream = client.get(f"/api/stream/{sid}")  # no ?since=
    assert stream.status_code == 200
    assert _parse_sse(stream.text) == []


def test_since_n_replays_only_events_with_a_higher_seq(client):
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    channel = _channels(client).get(sid)
    for i in range(5):
        channel.emit("stage", {"i": i})
    channel.close()

    everything = _parse_sse(client.get(f"/api/stream/{sid}?since=0").text)
    assert [e["data"]["i"] for e in everything] == [0, 1, 2, 3, 4]

    # seq is 1-based (i=0 -> seq=1, ... i=4 -> seq=5); `since=2` means "after seq 2".
    partial = _parse_sse(client.get(f"/api/stream/{sid}?since=2").text)
    assert [e["data"]["i"] for e in partial] == [2, 3, 4]

    everything_again = _parse_sse(client.get(f"/api/stream/{sid}?since=0").text)
    assert everything_again == everything, "replay must be idempotent, not consuming"


def test_ring_eviction_beyond_500_events_is_reported_as_a_dropped_event(client):
    """[ruling I2] The ring holds the last 500 events per session; anything older is
    gone, and a subscriber asking for it (`since=0`) is told so via a synthetic `dropped`
    event rather than silently missing the gap."""
    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    channel = _channels(client).get(sid)
    total = _RING_SIZE + 5
    for i in range(total):
        channel.emit("stage", {"i": i})
    channel.close()

    events = _parse_sse(client.get(f"/api/stream/{sid}?since=0").text)
    assert events[0]["event"] == "dropped"
    dropped = events[0]["data"]
    assert dropped["count"] == 5
    assert dropped["from"] == 1
    assert dropped["to"] == 5

    surviving = events[1:]
    assert len(surviving) == _RING_SIZE
    assert [e["data"]["i"] for e in surviving][0] == 5
    assert [e["data"]["i"] for e in surviving][-1] == total - 1


def test_two_sessions_get_independent_channels(client):
    sid_a = client.post("/api/session", json={"source": "new"}).json()["id"]
    sid_b = client.post("/api/session", json={"source": "new"}).json()["id"]

    channels = _channels(client)
    channel_a = channels.get(sid_a)
    channel_a.emit("stage", {"stage": "probe", "status": "started"})
    channel_a.close()
    channel_b = channels.get(sid_b)
    channel_b.close()

    resp_a = _parse_sse(client.get(f"/api/stream/{sid_a}?since=0").text)
    resp_b = _parse_sse(client.get(f"/api/stream/{sid_b}?since=0").text)
    assert resp_a and resp_a[0]["data"]["stage"] == "probe"
    assert resp_b == []


# ---- I1: genuine fan-out under a real ASGI server ------------------------------------------


class _NoSignalServer(uvicorn.Server):
    """`uvicorn.Server.serve()` installs SIGINT/SIGTERM handlers, which only works on
    the main thread of the main interpreter — this server runs on a background thread,
    so signal installation must be a no-op. The standard workaround for driving uvicorn
    from a thread in a test."""

    def install_signal_handlers(self) -> None:
        return None


class _LiveServer:
    """A real uvicorn server on an ephemeral loopback port — the one thing this test
    file needs that `TestClient` cannot give it: a stream genuinely held open while a
    concurrent mutating call runs against the same process."""

    def __init__(self, app) -> None:
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
        self.server = _NoSignalServer(config)
        self._thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self, timeout: float = 5.0) -> int:
        self._thread.start()
        deadline = time.monotonic() + timeout
        while not self.server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("uvicorn did not start within the timeout")
            time.sleep(0.01)
        return self.server.servers[0].sockets[0].getsockname()[1]

    def stop(self, timeout: float = 5.0) -> None:
        self.server.should_exit = True
        self._thread.join(timeout=timeout)


def test_three_concurrent_subscribers_on_one_session_each_see_every_event(env):
    """[ruling I1] Three readers subscribed to the SAME session, before the mutating
    elicit call runs, must each receive the full `stage` -> `object`* -> `stage` ->
    `done` sequence — not a disjoint fraction of it. This is exactly the defect the
    review's probe1 found: a point-to-point queue split one session's events between two
    readers, and neither ever saw `done`.

    `env` (not `client`): this test needs a real server bound to a real port, not a
    `TestClient`, but it still wants the same temp-state/recorded-backend isolation the
    `env` fixture sets up (no network, no real `~/.config/docket`).
    """
    from docket.api.app import create_app

    app = create_app()
    backend = RecordedBackend(FIXTURES / "elicit.json")
    actor = {"actorType": "agent", "actorId": "agent:recorded"}
    app.dependency_overrides[_agent] = lambda: (backend, actor)

    server = _LiveServer(app)
    port = server.start()
    base = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(timeout=20.0) as setup:
            sid = setup.post(f"{base}/api/session", json={"source": "new"}).json()["id"]

        results: dict[int, list[str]] = {}
        errors: list[BaseException] = []
        connected = threading.Barrier(3, timeout=10.0)

        def _reader(idx: int) -> None:
            try:
                with httpx.Client(timeout=20.0) as c, \
                        c.stream("GET", f"{base}/api/stream/{sid}") as resp:
                    assert resp.status_code == 200
                    connected.wait()
                    names: list[str] = []
                    for line in resp.iter_lines():
                        if line.startswith("event:"):
                            names.append(line[len("event:"):].strip())
                        if names and names[-1] == "done":
                            break
                    results[idx] = names
            except BaseException as exc:  # noqa: BLE001 - surfaced on the main thread below
                errors.append(exc)

        readers = [threading.Thread(target=_reader, args=(i,)) for i in range(3)]
        for t in readers:
            t.start()
        # A margin between "headers received client-side" and "the generator has
        # actually registered its queue server-side" — the same margin the review's own
        # probe1 used ("subscribed 1.5 s before the elicit POST").
        time.sleep(1.5)

        with httpx.Client(timeout=20.0) as poster:
            r = poster.post(f"{base}/api/session/{sid}/elicit", json={
                "requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT,
                "policyId": "pol-1", "requestedBy": "NGCV CFT",
                "episodeId": "ep-live-fanout",
            })
            assert r.status_code == 200, r.text

        for t in readers:
            t.join(timeout=20.0)
            assert not t.is_alive(), "a reader thread did not finish within the timeout"
        assert not errors, errors
        assert len(results) == 3

        for idx, names in results.items():
            assert names, f"reader {idx} saw no events at all"
            assert names[0] == "stage", f"reader {idx}: {names}"
            assert names.count("object") >= 1, f"reader {idx}: {names}"
            assert names[-1] == "done", f"reader {idx}: {names}"

        # The defining assertion: fan-out means every subscriber's own event list is
        # identical; a point-to-point queue would have split them.
        first = results[0]
        for idx, names in results.items():
            assert names == first, f"reader {idx} diverged: {names} != {first}"
    finally:
        server.stop()
