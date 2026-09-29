"""`POST …/ask` (spec §7): reads this decision, never writes to it.

A matched intent is answered from the record by `agent.ask.answer`. An unmatched one
is sent to the configured model only when the server is not in recorded mode and a
backend resolves; the reply must pass the renderer's citation check or the fallback
sentence is returned. Every answer is appended to the session's own `chat.jsonl` —
session-local, next to the graph directory, never inside it.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from docket.agent.ask import (
    SUGGESTED_QUESTIONS,
    answer,
    answer_with_model,
    fallback,
    route_intent,
)
from docket.agent.backend import backend_from_settings
from docket.api.config import current_api_key
from docket.api.routes.agent import _settings_for
from docket.errors import BackendError, PolicyRefusal, ValidationError

router = APIRouter()


def _now() -> str:
    """See `routes/kernel.py`'s `_now`: the one clock the API may read."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ask_backend(request: Request) -> Any | None:
    """The backend an unmatched question may go to, or None.

    A chat question must not 409 on a missing key, a denylisted model or a broken
    config file the way an agent stage does — it falls back to the honest sentence
    instead, so every way of having no usable backend is answered with `None` here.
    The resolution is deliberately not `routes/agent.py`'s `Depends(_agent)`: that one
    also mints an agent actor, and the chat never acts.

    Two ways of saying "recorded" are honoured before anything is built: the server's
    own mode override (the header's `RECORDED` chip) and a resolved `recorded`
    provider. Neither reaches a model, so neither may spend a recording lookup on a
    chat question.

    Tests override this dependency to inject a `RecordedBackend`.
    """
    if request.app.state.mode_override == "recorded":
        return None
    try:
        settings = _settings_for(request)
        if settings.provider == "recorded":
            return None
        key = current_api_key(request)
        return backend_from_settings(settings, api_key=key)
    except (PolicyRefusal, BackendError, OSError, ValueError):
        return None


class AskRequest(BaseModel):
    question: str
    #: The cut-off the "what changed" intent reads: with one set, that answer lists only
    #: entries this episode's record gained at or after it. Every other intent reports
    #: the record as it stands and ignores it.
    since: str | None = None


@router.get("/ask/questions")
def get_questions() -> dict:
    return {"questions": list(SUGGESTED_QUESTIONS)}


@router.post("/session/{s}/episode/{e}/ask")
def post_ask(s: str, e: str, body: AskRequest, request: Request,
             backend: Any | None = Depends(_ask_backend)) -> dict:
    """Answer from the record, else from the model, else the fallback sentence.

    The session lock is held for the read and the `chat.jsonl` append together, so a
    transcript line can never be interleaved with another request's. Nothing inside it
    calls `sessions.writing`: this route has no write path to the record at all, which
    is what `tests/api/test_ask.py` proves by comparing the head entry hash and the
    snapshot hash across ten calls.
    """
    question = body.question.strip()
    if not question:
        raise ValidationError(["ask needs a question"])
    session = request.app.state.sessions.get(s)
    now = _now()
    with session.lock:
        g = session.graph
        if not g.has(e):
            raise KeyError(e)
        intent = route_intent(question)
        result = answer(g, e, question, now=now, since=body.since)
        source = "record"
        if result is None and backend is not None:
            result = answer_with_model(g, e, question, backend=backend, now=now)
            source = "model"
        if result is None:
            result, source = fallback(), "fallback"
        line = {"at": now, "episode": e, "question": question, "intent": intent,
                "source": source, "answer": result}
        with open(session.path / "chat.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")
    return {"answer": result, "source": source, "intent": intent}
