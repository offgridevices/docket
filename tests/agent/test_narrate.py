# tests/agent/test_narrate.py
"""Stage N: the agent drafts narrative prose; the kernel's own `check_citations` is the
only thing that decides whether a draft is ever written. No network anywhere in this
file — `RecordedBackend` only [ruling R9]."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from docket.agent.backend import RecordedBackend
from docket.agent.narrate import CITATION_RULE, context_pack, narrate, user_prompt
from docket.canon import canonical_json
from docket.errors import UncitedSentenceError, ValidationError
from docket.kernel.render import check_citations, render_package
from docket.store import Graph

A = {"actorType": "agent", "actorId": "agent:recorded"}
NOW = "2013-04-30T00:00:00Z"
SEC = "evaluation-results"

FIXTURES = Path(__file__).parents[1] / "fixtures" / "recorded"


@pytest.fixture(scope="session")
def demo_a_graph_dir(tmp_path_factory):
    """Run Demo A once per session into a temp dir — never into demos/*/out."""
    from demos.a_cbo_gcv_2013.run import run

    d = tmp_path_factory.mktemp("demo-a")
    run(d)
    return d / "graph"


@pytest.fixture
def g(demo_a_graph_dir):
    return Graph.load(demo_a_graph_dir)


def _top_result(g, section_run_index: int = 0) -> tuple[str, str, float]:
    """`(run_id, result_id, stored value)` for the top-ranked alternative of one of the
    episode's runs — read from the graph, never hard-coded [defect 12]."""
    run_id = g.get("ep-cbo-2013")["runs"][section_run_index]
    top_alt = g.get(run_id)["ranking"][0]
    res_id = f"res-{run_id}-{top_alt}"
    return run_id, res_id, g.get(res_id)["value"]


# --- context_pack ----------------------------------------------------------------


def test_context_pack_is_deterministic_and_id_keyed(g):
    a = context_pack(g, "ep-cbo-2013", SEC)
    b = context_pack(g, "ep-cbo-2013", SEC)
    assert a == b and all(g.has(k) or k.startswith("run-") for k in a)


def test_context_pack_only_carries_ids_and_values_the_graph_already_holds(g):
    """Every numeral anywhere in the pack must already sit on the object of that same
    id in the graph — the pack is a filtered copy, never a computation."""
    pack = context_pack(g, "ep-cbo-2013", SEC)
    for oid, fields in pack.items():
        assert g.has(oid)
        stored = g.get(oid)
        for k, v in fields.items():
            assert stored.get(k) == v


def test_context_pack_covers_every_defined_section_deterministically(g):
    for section in ("problem-statement", "evaluation-results", "what-flips", "readiness",
                    "alternatives", "grca"):
        a = context_pack(g, "ep-cbo-2013", section)
        b = context_pack(g, "ep-cbo-2013", section)
        assert a == b
        assert a, f"{section} pack is unexpectedly empty on Demo A's graph"


def test_a_valid_but_unimplemented_section_returns_an_empty_pack_not_a_refusal(g):
    """`cover` is one of the 16 real package sections but has no context-pack builder —
    it must not be confused with an actually-unknown section string."""
    assert context_pack(g, "ep-cbo-2013", "cover") == {}


def test_unknown_section_is_refused(g):
    with pytest.raises(ValidationError) as exc:
        context_pack(g, "ep-cbo-2013", "not-a-section")
    # the refusal names all 16 valid keys, per the brief
    for key in ("problem-statement", "evaluation-results", "what-flips", "readiness",
                "alternatives", "grca", "cover", "machine-annex"):
        assert key in str(exc.value)


def test_a_dangling_reference_is_skipped_not_raised(g):
    """A hand-edited episode naming a run that does not exist must not crash the pack
    builder — it is simply left out."""
    ep = g.get("ep-cbo-2013")
    broken = {**ep, "rev": ep["rev"] + 1, "createdBy": ep["createdBy"], "createdAt": NOW,
              "runs": [*ep["runs"], "run-does-not-exist"]}
    # Apply directly to a throwaway copy of the graph via put (same actor as stored).
    g.put(broken, ep["createdBy"])
    pack = context_pack(g, "ep-cbo-2013", SEC)
    assert "run-does-not-exist" not in pack


def test_user_prompt_has_no_clock_or_seed(g):
    up = user_prompt(g, "ep-cbo-2013", SEC)
    assert NOW not in up
    assert "20130430" not in up


# --- [ruling I2] classification-aware withholding ---------------------------------

RAISED_EVIDENCE = "ev-army-expert-estimates"  # backs an observation behind the top alt


def _raise_one_evidence_to_s(g) -> None:
    """Mutate this test's own in-memory copy of Demo A — never the graph on disk, never
    another test's `g` (the `g` fixture reloads a fresh `Graph` per test) — by raising
    one real `Evidence` item's *value* classification from `U` to `S`. This is the
    session-copy-with-one-evidence-item-raised the ruling asks for."""
    ev = g.get(RAISED_EVIDENCE)
    assert ev["classification"]["level"] == "U", "test assumes Demo A ships this at U"
    actor = ev["createdBy"]
    g.put({**ev, "rev": ev["rev"] + 1, "createdBy": actor, "createdAt": NOW,
           "classification": {**ev["classification"], "level": "S"}}, actor)


def test_context_pack_rejects_an_unknown_rendering(g):
    with pytest.raises(ValidationError):
        context_pack(g, "ep-cbo-2013", SEC, rendering="top-secret")


def test_unclassified_pack_withholds_a_value_tainted_by_non_u_evidence(g):
    _raise_one_evidence_to_s(g)
    _run_id, res_id, real_value = _top_result(g)
    pack = context_pack(g, "ep-cbo-2013", SEC, rendering="unclassified")
    assert pack[res_id]["value"] == "[withheld: S]"
    # the real number must not leak into the pack anywhere, not just under this key
    assert str(real_value) not in canonical_json(pack)


def test_full_pack_still_carries_the_real_value(g):
    _raise_one_evidence_to_s(g)
    _run_id, res_id, real_value = _top_result(g)
    pack = context_pack(g, "ep-cbo-2013", SEC, rendering="full")
    assert pack[res_id]["value"] == real_value


def test_default_rendering_is_unclassified_the_safe_default(g):
    _raise_one_evidence_to_s(g)
    _run_id, res_id, _real_value = _top_result(g)
    pack = context_pack(g, "ep-cbo-2013", SEC)  # no rendering kwarg at all
    assert pack[res_id]["value"] == "[withheld: S]"


def test_narrate_recorded_fixtures_still_replay_on_the_unmodified_graph(g):
    """The I2 change must not have altered `user_prompt`'s text for Demo A as shipped
    (every object there is level `U`, so nothing is tainted and the pack is byte-for-
    byte what it was before this change) — otherwise the three committed recording keys
    would go stale as `RecordingMissing`. Confirmed directly against the *unmodified*
    graph `g` gives by default (this test does not call `_raise_one_evidence_to_s`)."""
    b = RecordedBackend(FIXTURES / "narrate-clean.json")
    nar = narrate(g, "ep-cbo-2013", section=SEC, backend=b, actor=A, now=NOW)
    assert len(b.calls) == 1
    assert check_citations(g, nar) == []


# --- the citation rule cites nothing the model could copy as a value --------------


VALUE_SHAPED = re.compile(
    r"\$\s*\d"
    r"|\b\d+(?:[.,]\d+)?\s*(?:%|M\b|B\b|K\b)"
    r"|\b\d+(?:[.,]\d+)?\s*(?:km|kg|mm|tons?|miles?|hours?|dollars|percent)\b"
    r"|\bFY\s?\d{2,4}\b"
)


def test_the_citation_rule_prompt_part_names_no_numeral_the_model_could_copy():
    """[deliverable] The prompt part that states the citation rule must not itself hand
    the model a value-shaped literal — a dollar figure, a percentage, a unit-bearing
    number — that a careless model could paste into a sentence as though it were a
    quoted value. A bare section-reference numeral (`§7.8`) is a citation, not a value,
    and is excluded here the same way the elicitation prompts' own guard test excludes
    `§4.9`/`¶4-5b`/`GAO-20-283G`."""
    assert not VALUE_SHAPED.search(CITATION_RULE)


# --- narrate: clean on the first try -----------------------------------------------


def test_narrative_is_stored_and_rendered_with_its_citations(g):
    b = RecordedBackend(FIXTURES / "narrate-clean.json")
    nar = narrate(g, "ep-cbo-2013", section=SEC, backend=b, actor=A, now=NOW)
    assert nar["type"] == "Narrative" and nar["createdBy"] == A
    assert nar["id"] in g.get("ep-cbo-2013")["narratives"]
    assert len(b.calls) == 1

    # [defect 12] the expected numeral is read from the graph, never hard-coded
    _run_id, res_id, value = _top_result(g)
    assert str(value) in nar["sentences"][0]["text"]

    # every numeral in the written Narrative equals a stored value by the same
    # canonical (rounded-to-precision) comparison check_citations itself applies —
    # not merely a substring match.
    assert check_citations(g, nar) == []

    text = render_package(g, "ep-cbo-2013", rendering="full", now=NOW)
    assert nar["sentences"][0]["text"] in text and res_id in text


def test_a_clean_draft_does_not_change_lifecycle_state_or_transitions(g):
    ep_before = g.get("ep-cbo-2013")
    b = RecordedBackend(FIXTURES / "narrate-clean.json")
    narrate(g, "ep-cbo-2013", section=SEC, backend=b, actor=A, now=NOW)
    ep_after = g.get("ep-cbo-2013")
    assert ep_after["lifecycleState"] == ep_before["lifecycleState"]
    assert ep_after["transitions"] == ep_before["transitions"]
    assert ep_after["rev"] == ep_before["rev"] + 1


# --- narrate: one wrong numeral, fed back, corrected -------------------------------


def test_a_wrong_numeral_is_fed_back_and_corrected(g):
    # [defect 10] two files, because the same prompt yields the same recording key
    b = RecordedBackend(FIXTURES / "narrate-retry.json")
    nar = narrate(g, "ep-cbo-2013", section=SEC, backend=b, actor=A, now=NOW)
    assert len(b.calls) == 2, "one bad draft, one corrected draft"
    _run_id, _res_id, value = _top_result(g)
    assert str(value) in nar["sentences"][0]["text"]
    assert str(value + 1) not in nar["sentences"][0]["text"]
    assert check_citations(g, nar) == []


# --- narrate: never clean -----------------------------------------------------------


def test_a_fabricated_number_exhausts_the_retries_and_raises(g):
    # [defect 11] every retry prompt has its own recorded (still bad) response, so this
    # raises UncitedSentenceError and not RecordingMissing
    log_len_before = len(g.log())
    b = RecordedBackend(FIXTURES / "narrate-fabricated.json")
    with pytest.raises(UncitedSentenceError) as exc:
        narrate(g, "ep-cbo-2013", section=SEC, backend=b, actor=A, now=NOW)
    assert len(b.calls) == 3
    assert exc.value.narrative_id is not None
    assert exc.value.sentence and "scores" in exc.value.sentence
    # [review M1] the previous filter-comprehension assertion here was vacuous: `nid` is
    # freshly computed and can only ever appear in `narratives` if the linking `g.put`
    # actually ran, so it passed even against a mutant that wrote the failing candidate
    # unlinked. Asking the graph directly is the assertion that actually tests the claim.
    assert not g.has(exc.value.narrative_id), "nothing is stored on failure"
    assert len(g.log()) == log_len_before, (
        "a refusal writes nothing at all, not even a partial draft"
    )


def test_unknown_section_is_refused_via_narrate_too(g):
    b = RecordedBackend(FIXTURES / "narrate-clean.json")
    with pytest.raises(ValidationError):
        narrate(g, "ep-cbo-2013", section="not-a-section", backend=b, actor=A, now=NOW)
