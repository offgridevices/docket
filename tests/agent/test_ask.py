"""agent/ask.py — reads the record, answers, navigates; never writes."""
import json
import re
from urllib.parse import quote

import pytest

from docket.agent.ask import (
    ANSWER_SCHEMA,
    FALLBACK_SENTENCE,
    SUGGESTED_QUESTIONS,
    answer,
    answer_with_model,
    fallback,
    route_intent,
    system_prompt,
    user_prompt,
)
from docket.agent.backend import RecordedBackend, record, recording_key
from docket.kernel.clock import clock
from docket.kernel.queue import needs
from docket.store import Graph
from tests.kernel.conftest import (
    charter,
    complete_graph,
    drs,
    episode,
    evidence,
    obj,
    policy,
    put_all,
    revise,
)

NOW = "2026-09-11T00:00:00Z"
NUM = re.compile(r"-?\d+(?:\.\d+)?")


@pytest.fixture
def demo_a():
    from demos.a_cbo_gcv_2013.run import run

    def _build(tmp_path):
        run(tmp_path)
        return Graph.load(tmp_path / "graph")

    return _build


@pytest.fixture
def demo_b():
    """Demo B's committed store, loaded and never written to — `ask` has no write path at
    all, which is the property this file exists to hold. Rebuilding the programme for one
    assertion would cost four years of episodes; the API tests load it the same way."""
    from pathlib import Path

    store = Path(__file__).resolve().parents[2] / "demos" / "b_omfv_2019_2023" / "out" / "graph"
    if not (store / "log.jsonl").is_file():
        pytest.skip("Demo B store not built yet")
    return Graph.load(store)


def test_the_nine_suggested_questions_each_route_to_an_intent():
    assert len(SUGGESTED_QUESTIONS) == 9
    assert [route_intent(q) for q in SUGGESTED_QUESTIONS] == [
        "blocking", "consequences", "changed", "where-approve", "what-flips",
        "explain-linchpin", "how-long", "due", "why-late",
    ]


def test_close_paraphrases_route_by_keyword():
    assert route_intent("what's holding this up?") == "blocking"
    assert route_intent("how far away is a flip") == "what-flips"
    assert route_intent("when is the deadline") == "due"
    assert route_intent("has anything happened since yesterday") == "changed"
    assert route_intent("what colour is the sky") is None


def _numerals(text: str) -> set[str]:
    return set(NUM.findall(text))


def _numerals_in(value) -> set[str]:
    if isinstance(value, bool):
        return set()
    if isinstance(value, int | float):
        return {str(value)}
    if isinstance(value, dict):
        return set().union(*(_numerals_in(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_numerals_in(v) for v in value)) if value else set()
    if isinstance(value, str):
        return _numerals(value)
    return set()


def test_every_deterministic_answer_cites_and_quotes_only_record_or_clock_numbers(tmp_path, demo_a):
    g = demo_a(tmp_path)
    allowed = _numerals_in(clock(g, "ep-cbo-2013", now=NOW)) | \
        _numerals_in(needs(g, "ep-cbo-2013", now=NOW))
    for q in SUGGESTED_QUESTIONS:
        a = answer(g, "ep-cbo-2013", q, now=NOW)
        assert a is not None, q
        assert a["paragraphs"] and a["cites"] and a["actions"], q
        assert all(g.has(c) for c in a["cites"]), (q, a["cites"])
        cited = set()
        for c in a["cites"]:
            cited |= _numerals_in({k: v for k, v in g.get(c).items()
                                   if k not in ("rev", "createdAt", "id")})
        for p in a["paragraphs"]:
            for n in _numerals(p):
                assert n in cited or n in allowed, (q, p, n)
        assert all(x["route"].startswith("/") for x in a["actions"])


def test_blocking_answer_says_nothing_blocks_demo_a_and_counts_what_waits(tmp_path, demo_a):
    """Demo A is ready and its only remaining act is the signature, so nothing blocks it —
    the two SIGNED checks that act would satisfy are not counted against it. The answer
    says so and names how many things are waiting on a person, in the singular."""
    g = demo_a(tmp_path)
    q = needs(g, "ep-cbo-2013", now=NOW)
    assert q["blocking"]["count"] == 0
    a = answer(g, "ep-cbo-2013", "What is blocking this right now?", now=NOW)
    joined = " ".join(a["paragraphs"])
    assert joined == "Nothing is blocking this decision. 1 thing is waiting on a person."
    assert {x["route"] for x in a["actions"]} == {"/"}


def test_blocking_answer_prints_the_headers_own_number_not_the_row_count(demo_b):
    """The chat and the `blocking` counter are the same number, in the same words: the
    header counts findings and checks, and the chat may not print the number of grouped
    rows instead [controller ruling, final fix round]."""
    eid = "ep-omfv-2020-02-r5"
    q = needs(demo_b, eid, now=NOW)
    rows = len(q["blocking"]["items"])
    assert q["blocking"]["count"] > rows
    a = answer(demo_b, eid, "What is blocking this right now?", now=NOW)
    first = a["paragraphs"][0]
    assert first == (f"{q['blocking']['count']} findings and checks stop this decision "
                     "moving on right now:")
    assert not first.startswith(f"{rows} ")


def test_the_linchpin_answer_names_no_number_of_its_own(tmp_path, demo_a):
    """The count of linchpins is nobody's published value — it is `len()` of a list this
    module filtered — so the answer names them by citation instead of printing one."""
    g = demo_a(tmp_path)
    a = answer(g, "ep-cbo-2013", SUGGESTED_QUESTIONS[5], now=NOW)
    assert _numerals(" ".join(a["paragraphs"])) == set()
    linchpins = [i for i in g.get("ep-cbo-2013")["assumptions"]
                 if g.get(i).get("linchpin") is True]
    assert a["cites"] == sorted(linchpins) and linchpins


def test_what_flips_reads_the_ranked_flip_from_the_stored_summary(tmp_path, demo_a):
    g = demo_a(tmp_path)
    a = answer(g, "ep-cbo-2013", "What would change the answer?", now=NOW)
    rr = g.get(g.get("ep-cbo-2013")["readiness"])
    first = rr["flipSummary"]["ranked"][0]
    assert first in a["cites"]
    assert a["actions"][0]["route"] == "/compute"


def test_fallback_is_the_honest_sentence_with_the_chips():
    f = fallback()
    assert f["paragraphs"] == [FALLBACK_SENTENCE]
    assert f["cites"] == []
    assert [x["label"] for x in f["actions"]] == list(SUGGESTED_QUESTIONS[:4])
    # the chip text is a query value, so it is percent-encoded, not pasted in raw
    assert f["actions"][0]["route"] == "/ask?q=" + quote(SUGGESTED_QUESTIONS[0])
    assert all(" " not in x["route"] and "?" not in x["route"].split("?q=", 1)[1]
               for x in f["actions"])


def test_answer_returns_none_for_an_unmatched_question():
    assert answer(complete_graph(), "ep-1", "what colour is the sky", now=NOW) is None


def test_model_answer_passes_only_when_every_numeral_is_in_a_cited_object(tmp_path, demo_a):
    g = demo_a(tmp_path)
    q = "Tell me about the primary run."
    key = recording_key(system_prompt(), user_prompt(g, "ep-cbo-2013", q, now=NOW), ANSWER_SCHEMA)
    good = tmp_path / "good.json"
    record(good, key, json.dumps({
        "paragraphs": ["The primary run ranked the alternatives with seed 20130430."],
        "cites": ["run-pl-cbo-primary"],
    }))
    a = answer_with_model(g, "ep-cbo-2013", q, backend=RecordedBackend(good), now=NOW)
    assert a is not None and a["cites"] == ["run-pl-cbo-primary"]

    bad = tmp_path / "bad.json"
    record(bad, key, json.dumps({
        "paragraphs": ["The primary run scored the Puma at 99.9."],
        "cites": ["run-pl-cbo-primary"],
    }))
    assert answer_with_model(g, "ep-cbo-2013", q, backend=RecordedBackend(bad), now=NOW) is None


def test_model_answer_is_none_when_the_recording_has_no_answer(tmp_path, demo_a):
    g = demo_a(tmp_path)
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    assert answer_with_model(g, "ep-cbo-2013", "anything", backend=RecordedBackend(empty),
                             now=NOW) is None


def _one_episode_graph(**over):
    g = Graph()
    put_all(g, policy(), evidence("ev-doc"), drs(), charter(), episode(**over))
    return g


def test_what_changed_reads_only_the_asked_episode_of_a_multi_episode_session():
    g = _one_episode_graph()
    # a second, wholly separate decision in the same session, written last
    put_all(g, policy("pol-2"), charter("ch-2", decisionClassPolicy="pol-2"),
            episode("ep-2", sequence=2, charter="ch-2"))
    a = answer(g, "ep-1", "What changed since yesterday?", now=NOW)
    assert "ep-1" in a["cites"]
    assert not ({"ep-2", "ch-2", "pol-2"} & set(a["cites"])), a["cites"]
    joined = " ".join(a["paragraphs"])
    assert "ep-2" not in joined and "ch-2" not in joined

    b = answer(g, "ep-2", "What changed since yesterday?", now=NOW)
    assert "ep-2" in b["cites"]
    assert not ({"ep-1", "ch-1", "pol-1"} & set(b["cites"])), b["cites"]


def test_what_changed_honours_since_and_drops_older_entries():
    g = _one_episode_graph()
    revise(g, "ep-1", createdAt="2026-09-10T00:00:00Z", asOf="2026-09-10")
    everything = answer(g, "ep-1", "What changed since yesterday?", now=NOW)
    assert len(everything["paragraphs"]) > 2

    a = answer(g, "ep-1", "What changed since yesterday?", now=NOW, since="2026-09-08")
    assert len(a["paragraphs"]) == 2, a["paragraphs"]
    assert a["paragraphs"][1].startswith("2026-09-10")
    assert a["cites"] == ["ep-1"]

    none_left = answer(g, "ep-1", "What changed since yesterday?", now=NOW,
                       since="2026-09-11T00:00:00Z")
    assert none_left["paragraphs"] == ["Nothing has happened on this decision since then."]
    assert none_left["cites"] == ["ep-1"]


def test_what_flips_never_prints_a_null_threshold_or_distance():
    g = Graph()
    put_all(
        g, policy(), evidence("ev-doc"), drs(), charter(),
        obj("fa-1", "FlipAnalysis", run="run-1", currentValue=0.6,
            parameter={"kind": "weight", "target": "ws-1:m-1",
                       "label": "the weight on Capability"},
            range={"lo": 0, "hi": 1, "source": "sweep"},
            flipThreshold=None, flipDistance=None, direction="none",
            rankingBefore=["alt-a", "alt-b"], rankingAfter=None, kernelVersion="test"),
        obj("rr-1", "ReadinessReport", episode="ep-1", standardsAssessment="sa-1",
            mandateScorecard="ms-1", blockers=[], warnings=[], openGaps=[],
            openExclusions=[], flipSummary={"ranked": ["fa-1"]}, biasChecksStatus=[],
            computedBiasRisks=[], ready=True, policyVersion="0.1", kernelVersion="test",
            seed=1),
        episode(readiness="rr-1", flipAnalyses=["fa-1"]),
    )
    a = answer(g, "ep-1", "What would change the answer?", now=NOW)
    joined = " ".join(a["paragraphs"])
    assert "None" not in joined and "null" not in joined
    assert "the weight on Capability" in joined
    assert {"fa-1", "ep-1"} <= set(a["cites"])
    assert a["actions"][0]["route"] == "/compute"
