"""`sessions.writing()`: a refused transition must reach disk, not just the in-memory
graph — `kernel.lifecycle.transition()` writes the refusal record via a normal `g.put()`
that succeeds *before* raising `TransitionRefused`, so the refusal is a real part of the
record, not a rejected write. The only way to prove it survives is to reload the store
from disk in a fresh `Graph`, never the same in-process `Session.graph` object.
"""
from __future__ import annotations

import pytest

from docket.api.config import human_actor
from docket.api.sessions import SessionStore, writing
from docket.errors import TransitionRefused
from docket.kernel.lifecycle import transition
from docket.store import Graph

NOW = "2026-09-05T00:00:00Z"


def _charter_and_episode(actor: dict) -> tuple[dict, dict]:
    charter = {
        "id": "ch-1", "type": "Charter", "rev": 1, "createdBy": actor, "createdAt": NOW,
        "question": "q", "decisionToBeMade": "d", "consequencesOfErroneousOutput": "c",
        "questionClass": "other", "scope": {"included": ["a"], "excluded": []},
        "authority": {"signer": "s"}, "decisionClassPolicy": "pol-default",
    }
    episode = {
        "id": "ep-1", "type": "DecisionEpisode", "rev": 1, "createdBy": actor,
        "createdAt": NOW, "sequence": 1, "charter": "ch-1", "lifecycleState": "DRAFT",
        "transitions": [], "objectives": [], "alternatives": [], "groundRules": [],
        "constraints": [], "assumptions": [], "evidenceRegister": [], "scenarios": [],
        "claims": [], "risks": [], "biasChecks": [], "mandateElements": [],
        "observations": [], "weightSets": [], "models": [], "runs": [],
        "flipAnalyses": [], "narratives": [], "asOf": "2026-09-05",
    }
    return charter, episode


def test_a_refused_transition_is_persisted_to_disk(env):
    """`PLAN_APPROVED` is not an edge out of `DRAFT` (`EDGES["DRAFT"] ==
    {"MODEL_APPROVED", "VOID"}`), so this refuses regardless of check predicates — the
    point here is disk persistence of the refusal, not which check failed."""
    store = SessionStore()
    session = store.create("new")
    actor = human_actor()
    charter, episode = _charter_and_episode(actor)
    with writing(session) as g:
        g.put(charter, actor)
        g.put(episode, actor)

    with pytest.raises(TransitionRefused):
        with writing(session) as g:
            transition(g, "ep-1", "PLAN_APPROVED", actor, now=NOW)

    # A FRESH Graph, loaded straight from disk — not the same in-process Session.graph
    # object — is the only thing that can catch a save that silently didn't happen.
    reloaded = Graph.load(session.path / "graph")
    ep = reloaded.get("ep-1")
    assert ep["transitions"], "the refusal never reached disk"
    last = ep["transitions"][-1]
    assert last["to"] == "PLAN_APPROVED"
    assert last["refused"] is True
    assert "edge-DRAFT-to-PLAN_APPROVED" in last["checksUnsatisfied"]


def test_an_unexpected_error_inside_writing_leaves_disk_untouched(env):
    """An exception other than `TransitionRefused` must not trigger a save: `Graph.put`
    validates before it mutates anything, so `ValidationError`/`AuthorityViolation` (and
    an outright bug, simulated here with a plain `ValueError`) mean nothing was actually
    written, and `writing()` must not paper over that by persisting anyway."""
    store = SessionStore()
    session = store.create("new")
    before = (session.path / "graph" / "manifest.json").read_bytes()

    with pytest.raises(ValueError, match="boom"):
        with writing(session):
            raise ValueError("boom")

    after = (session.path / "graph" / "manifest.json").read_bytes()
    assert before == after
