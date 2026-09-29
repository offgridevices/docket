"""Direct tests of `app._install_error_handlers` against a throwaway FastAPI app, for
exceptions Task 1's own routes cannot raise (`RecordingMissing`, `BackendError`,
`UncitedSentenceError`) — the same technique the review used to probe them live.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docket.api.app import _install_error_handlers
from docket.errors import BackendError, RecordingMissing, UncitedSentenceError


def _client_raising(exc: Exception) -> TestClient:
    app = FastAPI()
    app.state.api_key = None
    app.state.mode_override = None

    @app.get("/boom")
    def boom():
        raise exc

    _install_error_handlers(app)
    return TestClient(app)


def test_recording_missing_is_503_distinct_from_backend_error_502():
    r = _client_raising(RecordingMissing("no recording for this prompt"))
    resp = r.get("/boom")
    assert resp.status_code == 503
    assert resp.json()["error"] == "recording-missing"


def test_backend_error_stays_502():
    r = _client_raising(BackendError("malformed structured output"))
    resp = r.get("/boom")
    assert resp.status_code == 502
    assert resp.json()["error"] == "backend"


# ---- M4: UncitedSentenceError carries structured narrative_id/sentence attributes ----


def test_uncited_sentence_error_carries_structured_attributes():
    exc = UncitedSentenceError(
        "nar-1: sentence 0 ('the parsed text'): no citation",
        narrative_id="nar-1", sentence="the real sentence",
    )
    assert exc.narrative_id == "nar-1"
    assert exc.sentence == "the real sentence"
    # the message format itself is unchanged — every existing caller/test still matches it
    assert str(exc) == "nar-1: sentence 0 ('the parsed text'): no citation"


def test_uncited_sentence_error_defaults_both_attributes_to_none():
    """The one call site that exists today (`render.render_package`) does not pass
    either keyword — this is what makes the fallback parse in `app.py` still load-
    bearing in practice."""
    exc = UncitedSentenceError("nar-1: sentence 0 ('x'): no citation")
    assert exc.narrative_id is None
    assert exc.sentence is None


def test_handler_prefers_the_structured_sentence_over_the_parsed_one():
    exc = UncitedSentenceError(
        "nar-1: sentence 0 ('the parsed text'): no citation",
        narrative_id="nar-1", sentence="the real sentence",
    )
    r = _client_raising(exc)
    resp = r.get("/boom")
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "uncited-sentence"
    assert body["sentence"] == "the real sentence"


def test_handler_falls_back_to_parsing_when_the_attribute_is_absent():
    exc = UncitedSentenceError("nar-1: sentence 0 ('parsed text'): no citation")
    r = _client_raising(exc)
    resp = r.get("/boom")
    assert resp.status_code == 422
    assert resp.json()["sentence"] == "parsed text"


def test_handler_degrades_to_none_when_neither_attribute_nor_shape_is_present():
    exc = UncitedSentenceError("a message that does not match the expected shape at all")
    r = _client_raising(exc)
    resp = r.get("/boom")
    assert resp.status_code == 422
    assert resp.json()["sentence"] is None
