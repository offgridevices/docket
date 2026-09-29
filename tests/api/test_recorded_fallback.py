"""Health-driven recorded fallback, end to end (plan 07 Task 9, Step 2).

Two facts, both asserted against the actual production code paths — never a
dependency-injected double:

1. `GET /api/health` must not hang or crash when the configured backend is a live
   provider pointed at a connection nothing answers; it must say so
   (`backend.reachable: false`) and recommend the recorded fallback (`mode: "recorded"`)
   comfortably within the 2s probe timeout `routes/health.py::_probe` itself sets.
2. That recommendation is real, not cosmetic: switching the *actual* resolution chain
   (`docket.agent.backend.resolve_settings` and the settings-to-backend resolver — the
   same functions `routes/agent.py`'s `_agent` dependency calls on every request) to the
   recorded
   provider lets an elicit call through the API succeed, against nothing but a committed
   fixture.

Recording path used: `tests/fixtures/recorded/elicit.json`, via `DOCKET_LLM_RECORDING`.

Not `demos/a_cbo_gcv_2013/recording.json` — no file by that name (or any
`recording.json`) exists anywhere in this repository; that path does not match what the
agent routes actually resolve. `resolve_settings()`'s own default
(`docket.agent.backend.DEFAULT_RECORDING`) is `tests/fixtures/recorded/default.json`,
which is deliberately empty (ruling N3, `tests/fixtures/recorded/README.md`) so it raises
`RecordingMissing` on any real lookup — it exists to prove `RecordedBackend` constructs
cleanly out of the box, not to answer a prompt. `elicit.json` is the one committed
fixture that actually holds a response for the elicit request this file sends (the same
one `tests/api/test_agent_routes.py` injects via a dependency override); this file reaches
the identical recorded key through `DOCKET_LLM_RECORDING` instead, to prove the
*environment-driven* path — what flipping "switch to recorded" would actually set — works
end to end, not only the test-only override seam.
"""
from __future__ import annotations

import socket
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "recorded"
REQUEST_TEXT = (REPO / "tests" / "fixtures" / "requests" / "omfv-con-2020-02-25.md").read_text()
SOURCE_ARTIFACT = "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md"


def _refused_port() -> int:
    """A loopback TCP port nothing is listening on. Binding then releasing it (rather
    than just picking a high number) guarantees the OS actually had it free a moment
    ago, so the connection attempt below gets a fast, deterministic refusal instead of
    landing on some other process's live listener."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_health_reports_recorded_fallback_within_the_probe_timeout(client, monkeypatch):
    port = _refused_port()
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DOCKET_LLM_BASE_URL", f"http://127.0.0.1:{port}")

    start = time.monotonic()
    r = client.get("/api/health")
    elapsed = time.monotonic() - start

    assert r.status_code == 200
    body = r.json()
    assert body["backend"]["reachable"] is False
    assert body["mode"] == "recorded"
    assert elapsed < 3.0, f"health took {elapsed:.2f}s against a refused connection"


def test_health_also_reports_recorded_mode_once_actually_switched(client, monkeypatch):
    """`routes/health.py::_mode` returns `"recorded"` whenever `settings.provider ==
    "recorded"`, independent of reachability — the same switch the elicit test below
    relies on. Asserted here so a future change decoupling the two would be caught
    against this file, not only `tests/api/test_health.py`."""
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    monkeypatch.setenv("DOCKET_LLM_RECORDING", str(FIXTURES / "elicit.json"))
    body = client.get("/api/health").json()
    assert body["mode"] == "recorded"


def test_elicit_succeeds_through_the_api_in_recorded_mode(client, monkeypatch):
    """Not a dependency override: this drives `resolve_settings()`/
    the settings-to-backend resolver (the functions `routes/agent.py::_agent` actually calls on
    every request) through the environment — the same seam a real "switch to recorded"
    action sets. If this ever needed a dependency override to pass, the recorded
    fallback would not be real end to end, only demonstrable in a test that routes
    around the resolution chain."""
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    monkeypatch.setenv("DOCKET_LLM_RECORDING", str(FIXTURES / "elicit.json"))

    sid = client.post("/api/session", json={"source": "new"}).json()["id"]
    r = client.post(f"/api/session/{sid}/elicit", json={
        "requestText": REQUEST_TEXT, "sourceArtifact": SOURCE_ARTIFACT,
        "policyId": "pol-1", "requestedBy": "NGCV CFT", "episodeId": "ep-recorded-fallback",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["episode"]["id"] == "ep-recorded-fallback"
    assert body["objects"], "elicit.json must map onto at least one DRAFT object"
