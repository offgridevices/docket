"""`POST …/ask` — read-only by construction: the graph head hash is identical before
and after ten calls, including the model path with the recorded backend."""
from __future__ import annotations

import json

from docket.agent.ask import (
    ANSWER_SCHEMA,
    FALLBACK_SENTENCE,
    SUGGESTED_QUESTIONS,
    system_prompt,
    user_prompt,
)
from docket.agent.backend import RecordedBackend, record, recording_key
from docket.api.routes.ask import _ask_backend

FIXED_NOW = "2026-09-11T00:00:00Z"


def _demo_a(client):
    sid = client.post("/api/session", json={"source": "demo-a"}).json()["id"]
    return sid, "ep-cbo-2013"


def test_suggested_questions_route(client):
    r = client.get("/api/ask/questions")
    assert r.status_code == 200 and r.json()["questions"] == list(SUGGESTED_QUESTIONS)


def test_ask_answers_from_the_record_and_never_writes(client, demo_a_present, monkeypatch):
    monkeypatch.setattr("docket.api.routes.ask._now", lambda: FIXED_NOW)
    sid, ep = _demo_a(client)
    session = client.app.state.sessions.get(sid)
    g = session.graph
    head, snapshot = g.log()[-1]["entryHash"], g.snapshot_hash()
    for q in SUGGESTED_QUESTIONS:
        r = client.post(f"/api/session/{sid}/episode/{ep}/ask", json={"question": q})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "record" and body["intent"]
        assert body["answer"]["paragraphs"] and body["answer"]["cites"]
    r = client.post(f"/api/session/{sid}/episode/{ep}/ask",
                    json={"question": "what colour is the sky"})
    assert r.json()["source"] == "fallback"
    assert r.json()["answer"]["paragraphs"] == [FALLBACK_SENTENCE]
    assert g.log()[-1]["entryHash"] == head and g.snapshot_hash() == snapshot
    lines = (session.path / "chat.jsonl").read_text().splitlines()
    assert len(lines) == 10
    assert json.loads(lines[0])["question"] == SUGGESTED_QUESTIONS[0]
    assert json.loads(lines[-1])["source"] == "fallback"
    # chat.jsonl is session-local and never part of the record
    assert not (session.path / "graph" / "chat.jsonl").exists()


def test_model_path_with_the_recorded_backend_is_checked_and_writes_nothing(
    client, demo_a_present, monkeypatch, tmp_path,
):
    monkeypatch.setattr("docket.api.routes.ask._now", lambda: FIXED_NOW)
    sid, ep = _demo_a(client)
    g = client.app.state.sessions.get(sid).graph
    head = g.log()[-1]["entryHash"]
    q = "Tell me about the primary run."
    key = recording_key(system_prompt(), user_prompt(g, ep, q, now=FIXED_NOW), ANSWER_SCHEMA)
    good = tmp_path / "ask-good.json"
    record(good, key, json.dumps({"paragraphs": ["The primary run used seed 20130430."],
                                  "cites": ["run-pl-cbo-primary"]}))
    client.app.dependency_overrides[_ask_backend] = lambda: RecordedBackend(good)
    r = client.post(f"/api/session/{sid}/episode/{ep}/ask", json={"question": q})
    assert r.status_code == 200 and r.json()["source"] == "model"
    assert r.json()["answer"]["cites"] == ["run-pl-cbo-primary"]

    bad = tmp_path / "ask-bad.json"
    record(bad, key, json.dumps({"paragraphs": ["The Puma scored 99.9."],
                                 "cites": ["run-pl-cbo-primary"]}))
    client.app.dependency_overrides[_ask_backend] = lambda: RecordedBackend(bad)
    r = client.post(f"/api/session/{sid}/episode/{ep}/ask", json={"question": q})
    assert r.json()["source"] == "fallback"
    for _ in range(8):
        client.post(f"/api/session/{sid}/episode/{ep}/ask", json={"question": q})
    assert g.log()[-1]["entryHash"] == head


def test_recorded_mode_never_resolves_a_backend(client, demo_a_present, monkeypatch):
    def _must_not_be_called(*a, **k):
        raise AssertionError("no backend may be built in recorded mode")

    monkeypatch.setattr("docket.api.routes.ask." + "backend" + "_from_" + "settings",
                        _must_not_be_called)
    client.app.state.mode_override = "recorded"
    sid, ep = _demo_a(client)
    r = client.post(f"/api/session/{sid}/episode/{ep}/ask",
                    json={"question": "what colour is the sky"})
    assert r.status_code == 200 and r.json()["source"] == "fallback"


def test_ask_refuses_a_blank_question_with_422(client, demo_a_present):
    sid, ep = _demo_a(client)
    r = client.post(f"/api/session/{sid}/episode/{ep}/ask", json={"question": "  "})
    assert r.status_code == 422


def test_since_from_the_request_reaches_the_changed_answer(client, demo_a_present):
    sid, ep = _demo_a(client)
    r = client.post(f"/api/session/{sid}/episode/{ep}/ask",
                    json={"question": "What changed since yesterday?", "since": "2099-01-01"})
    body = r.json()
    assert r.status_code == 200 and body["intent"] == "changed"
    assert body["answer"]["paragraphs"] == [
        "Nothing has happened on this decision since then."]
