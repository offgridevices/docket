# tests/kernel/test_render.py
import json

import pytest

from docket import KERNEL_ACTOR
from docket.canon import canonical_json
from docket.errors import UncitedSentenceError, ValidationError
from docket.kernel.readiness import readiness_report
from docket.kernel.refresh import diff_episodes, open_refresh
from docket.kernel.render import (
    SECTIONS,
    ai_assistance_summary,
    build_package,
    check_citations,
    content_snapshot_hash,
    latest_package_hash,
    rating_scale_legend,
    readiness_ready_text,
    ready_text,
    render_package,
    tailoring_note,
)
from docket.schema import catalogue
from docket.standard import load_tailoring
from docket.store import Graph
from tests.kernel.conftest import (
    H,
    alternative,
    charter,
    drs,
    episode,
    evidence,
    obj,
    policy,
    put_all,
    revise,
    transition_record,
)

NOW = "2026-09-04T00:00:00Z"
SEED = 11
A = {"actorType": "agent", "actorId": "agent:elicit"}


def _fresh_base_graph() -> Graph:
    """A minimal, valid graph — built the same way `base_graph` is, but callable more
    than once so a test can compare two independently-built graphs."""
    g = Graph()
    put_all(g, policy(), evidence("ev-doc"), drs(), charter(), episode())
    return g


def test_sections_match_schema_package_sections():
    assert [key for key, _ in SECTIONS] == catalogue()["package_sections"]


def test_check_citations_numbers_must_come_from_cited_objects(base_graph):
    g = base_graph
    put_all(g, obj("res-1", "Result", run="run-x", alternative="alt-a", aggregate=True,
                   value=45.1, units="pct", method="mavt"))
    nar = obj("nar-1", "Narrative", episode="ep-1", section="evaluation-results",
              sentences=[{"text": "The Puma scores 45.1 percent.", "cites": ["res-1"]}])
    assert check_citations(g, nar) == []
    bad = {**nar, "sentences": [{"text": "The Puma scores 46 percent.", "cites": ["res-1"]}]}
    assert check_citations(g, bad) and "46" in check_citations(g, bad)[0]
    missing = {**nar, "sentences": [{"text": "Plain claim.", "cites": ["nope"]}]}
    assert any("nope" in e for e in check_citations(g, missing))


def test_check_citations_tolerates_a_sentence_with_no_cites_field_at_all():
    # A hand-edited or pre-validation narrative may not even have the key; check_citations
    # must name it, not raise a KeyError, before the schema rule ever sees it.
    g = Graph()
    n = {"sentences": [{"text": "No citation anywhere."}]}
    errs = check_citations(g, n)
    assert errs == ["sentence 0 ('No citation anywhere.'): no citation"]


def test_check_citations_error_names_the_sentence_text_not_just_its_index(base_graph):
    """M6: a repair loop reading the error needs the sentence's own words, not just an
    index into a list it may not have handy."""
    g = base_graph
    put_all(g, obj("res-1", "Result", run="run-x", alternative="alt-a", aggregate=True,
                   value=45.1, units="pct", method="mavt"))
    nar = obj("nar-1", "Narrative", episode="ep-1", section="evaluation-results",
              sentences=[{"text": "The Puma scores 46 percent.", "cites": ["res-1"]}])
    errs = check_citations(g, nar)
    assert errs and "The Puma scores 46 percent." in errs[0]


def test_render_all_sections_and_unclassified_withholding(base_graph):
    g = base_graph
    put_all(
        g,
        evidence("ev-s", classification={"level": "S", "metadataLevel": "U"}),
        alternative("alt-a", baseline=True),
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="surv",
            metric={"units": "pct", "direction": "max"}, criteria={"$gap": "gap-c"}),
        obj("gap-c", "InsufficientEvidence", sought="s", whereLookedFor=["x"],
            whyNotFound="w", impact="degrading", indicatorsThatWouldResolve=[]),
        obj("ob-1", "Observation", alternative="alt-a", measure="m-1", value=27,
            evidence="ev-s"),
        obj("ex-sec", "Exclusion", target={"kind": "Section", "label": "commitment"},
            reasonType="not-applicable", reason="analysis only, no decision taken",
            authority={"who": "CBO", "role": "analyst", "date": "2013-04"},
            retainedInStructure=True),
        {**episode(), "rev": 2, "alternatives": ["alt-a"], "objectives": ["obj-1"],
         "observations": ["ob-1"], "evidenceRegister": ["ev-s"]},
    )
    full = render_package(g, "ep-1", rendering="full", now=NOW)
    uncl = render_package(g, "ep-1", rendering="unclassified", now=NOW)
    for title in ("1. Problem statement", "6. Evidence register", "13. Commitment",
                  "15. Machine annex"):
        assert title in full and title in uncl
    assert "27" in full and "[withheld: S]" in uncl
    assert "27" not in uncl.split("6. Evidence register")[0].split("4. Alternatives")[-1]
    assert "analysis only, no decision taken" in full
    assert render_package(g, "ep-1", rendering="full", now=NOW) == full  # deterministic


def _agent_and_g1_graph(*, evidence_over: dict | None = None) -> Graph:
    """A minimal graph with one agent-authored, draft Evidence item reachable from the
    episode's evidence register, and one recorded, unrefused, human G1 transition."""
    g = Graph()
    put_all(g, policy(), drs(), charter())
    ev = evidence("ev-agent", reviewStatus="draft", **(evidence_over or {}))
    g.put({**ev, "createdBy": A}, A)
    g.put(
        episode(
            evidenceRegister=["ev-agent"],
            transitions=[transition_record("DRAFT", "MODEL_APPROVED")],
        ),
        H,
    )
    return g


def test_ai_assistance_label_names_the_agent_and_the_human_gate():
    """Deliverable: the record readout names the agent actor that authored a reachable
    object and the human actor behind the recorded G1 approval — both read from the
    graph, not asserted from policy."""
    g = _agent_and_g1_graph()
    summary = ai_assistance_summary(g, g.get("ep-1"))
    assert summary == {
        "agentActors": ["agent:elicit"],
        "humanGates": [{"gate": "G1", "state": "MODEL_APPROVED",
                        "actorId": "fixture", "at": NOW}],
        "agentComputedNoResult": True,
        "noAiAssistance": False,
    }
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    cover = text.split("## 1. Problem statement")[0]
    assert "**AI assistance:**" in cover
    assert "`agent:elicit`" in cover
    assert "G1 (MODEL_APPROVED) by `fixture`" in cover
    assert "no agent-authored `EvaluationRun`" in cover
    # The Machine annex's structured block is the same fact, not a second computation
    # that could drift from the Cover's prose.
    annex_line = next(ln for ln in text.splitlines() if ln.startswith("- aiAssistance:"))
    assert json.loads(annex_line.removeprefix("- aiAssistance: ")) == summary


def test_ai_assistance_label_says_so_explicitly_when_nothing_is_agent_authored():
    """Deliverable: a record with no agent-authored object anywhere it reaches states
    the absence explicitly, rather than printing an empty or silent section."""
    g = _fresh_base_graph()
    summary = ai_assistance_summary(g, g.get("ep-1"))
    assert summary["noAiAssistance"] is True
    assert summary["agentActors"] == []
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    cover = text.split("## 1. Problem statement")[0]
    assert "**AI assistance:** No AI assistance is recorded in this episode." in cover
    assert "Agent-authored objects" not in cover


def test_ai_assistance_block_is_identical_across_renderings():
    """Actor ids carry no evidence classification of their own — unlike the evidence
    register or evaluation results, nothing about `createdBy` is gated by
    `metadata_withheld`/`_withheld` (both key off an *Evidence* item's own
    classification) — so the AI-assistance block must print byte-identical text at
    both renderings even when the very same record withholds other values."""
    g = _agent_and_g1_graph(
        evidence_over={"classification": {"level": "S", "metadataLevel": "S"}}
    )
    full = render_package(g, "ep-1", rendering="full", now=NOW)
    uncl = render_package(g, "ep-1", rendering="unclassified", now=NOW)

    def ai_block(text: str) -> str:
        cover = text.split("## 1. Problem statement")[0]
        return cover.split("**AI assistance:**")[1]

    assert ai_block(full) == ai_block(uncl)
    # Sanity: this graph does withhold *something* under unclassified — just not the
    # AI-assistance block — so the test is not vacuously true over an all-public record.
    assert "[withheld: S]" in uncl and "[withheld: S]" not in full


def test_render_package_refuses_an_unknown_episode_id_by_name_not_keyerror():
    """A CLI or agent caller passing a typo'd episode id gets a named refusal, not
    a bare `KeyError` out of `Graph.get`."""
    with pytest.raises(ValidationError) as exc:
        render_package(Graph(), "ep-missing", rendering="full", now=NOW)
    assert "ep-missing" in str(exc.value)


def test_uncited_sentence_refused(base_graph):
    g = base_graph
    put_all(g, obj("nar-1", "Narrative", episode="ep-1", section="problem-statement",
                   sentences=[{"text": "No basis.", "cites": ["missing"]}]),
            {**episode(), "rev": 2, "narratives": ["nar-1"]})
    with pytest.raises(UncitedSentenceError):
        render_package(g, "ep-1", rendering="full", now=NOW)


def test_build_package_hashes_and_writes(base_graph, tmp_path):
    pkg, text = build_package(base_graph, "ep-1", rendering="full", now=NOW, out_dir=tmp_path)
    assert (tmp_path / "package-full.md").read_text() == text
    assert pkg["hash"] and pkg["graphSnapshotHash"]
    assert base_graph.get(pkg["id"])["rendering"] == "full"


def test_build_package_path_is_basename_and_dir_independent(tmp_path):
    dir_a, dir_b = tmp_path / "out-a" / "nested", tmp_path / "elsewhere" / "out-b"
    pkg_a, text_a = build_package(
        _fresh_base_graph(), "ep-1", rendering="full", now=NOW, out_dir=dir_a
    )
    pkg_b, text_b = build_package(
        _fresh_base_graph(), "ep-1", rendering="full", now=NOW, out_dir=dir_b
    )
    assert text_a == text_b
    assert pkg_a["path"] == "package-full.md" == pkg_b["path"]
    # Two graphs built the same way, rendered into two different directory roots, must
    # produce a canonically identical DecisionPackage object (and thus an identical
    # graph snapshot hash) — an absolute or directory-dependent path would break this.
    assert canonical_json(pkg_a) == canonical_json(pkg_b)


def test_latest_package_hash_tracks_the_most_recently_built_package():
    g = _fresh_base_graph()
    assert latest_package_hash(g, "ep-1") is None
    assert latest_package_hash(g, "ep-1", rendering="unclassified") is None

    first, _ = build_package(g, "ep-1", rendering="full", now=NOW)
    assert latest_package_hash(g, "ep-1") == first["hash"]
    # A different rendering of the same episode is tracked independently.
    assert latest_package_hash(g, "ep-1", rendering="unclassified") is None

    # A second build under changed content is what "most recent" actually means: the
    # newer one wins even though both packages remain in the graph (build_package never
    # revises an existing DecisionPackage; each build mints a fresh id at rev 1).
    put_all(g, obj("risk-1", "Risk", statement="s", kind="other", consequence="c",
                   owner="o", status="open"))
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "risks": ["risk-1"]})
    second, _ = build_package(g, "ep-1", rendering="full", now=NOW)
    assert first["hash"] != second["hash"]
    assert latest_package_hash(g, "ep-1") == second["hash"]

    # A different episode's packages must not answer for this one.
    put_all(g, charter("ch-2"), {**episode("ep-2", charter="ch-2")})
    assert latest_package_hash(g, "ep-2") is None


def test_readiness_section_prints_tailoring_honesty_note_once():
    g = Graph()
    put_all(g, policy(tailoring="gao-23-106549"), evidence("ev-doc"), drs(), charter(),
            episode())
    readiness_report(g, "ep-1", seed=SEED, now=NOW)
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    note = load_tailoring("gao-23-106549")["note"]
    assert note and text.count(note) == 1


def test_readiness_section_prints_no_note_for_a_tailoring_without_one():
    g = _fresh_base_graph()  # default policy() tailoring is "published-21"
    assert load_tailoring("published-21")["note"] is None
    readiness_report(g, "ep-1", seed=SEED, now=NOW)
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "10. Readiness" in text


# ---- fix round 1: public captions/ready-text helpers, for docket.api.routes.kernel ----


def test_rating_scale_legend_is_public_and_unchanged():
    """Renamed from `_rating_scale_legend` (plan 07 Task 7 fix round) so
    `routes/kernel.py` can import it without reaching into a private name — same
    function, same one call site in `_readiness_body`, same output."""
    legend = rating_scale_legend()
    assert legend.startswith("Rating scale (GAO-11-82R")
    g = _fresh_base_graph()
    readiness_report(g, "ep-1", seed=SEED, now=NOW)
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert legend in text


def test_tailoring_note_is_public_and_unchanged():
    """Renamed from `_tailoring_note`, same behaviour: the tailoring's own `note`, or
    `None` when it has none or cannot be loaded."""
    assert tailoring_note("gao-23-106549") == load_tailoring("gao-23-106549")["note"]
    assert tailoring_note("published-21") is None
    assert tailoring_note("not-a-real-tailoring") is None


def test_ready_text_matches_the_readiness_bodys_own_line():
    """`ready_text` is the exact substring `_readiness_body` interpolates into "Ready
    (no blocking findings)" — extracted, not re-derived, so the API and the package can
    never print two different answers for the same report."""
    g = _fresh_base_graph()
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert ready_text(rr, []) == str(rr["ready"])
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert f"**Ready (no blocking findings):** {ready_text(rr, [])} ·" in text


def test_ready_text_substitutes_when_a_live_blocking_finding_is_not_yet_stored():
    from docket.kernel.findings import Finding

    g = _fresh_base_graph()
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["ready"] is True
    live = Finding(rule="a-new-rule", severity="blocking", objects=("ep-1",), message="new")
    assert ready_text(rr, [live]) == "unavailable — record changed since the readiness report"


def test_readiness_ready_text_resolves_its_own_findings_from_the_graph():
    """The convenience wrapper `routes/kernel.py` actually calls: given only the graph
    and the episode id (no separately-computed `findings` list), it must answer exactly
    what `ready_text` would given the same policy-derived findings `render_package`
    itself uses."""
    g = _fresh_base_graph()
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert readiness_ready_text(g, "ep-1", rr) == str(rr["ready"])


def test_seal_verified_line_and_no_inputs_changed_badge_on_a_clean_run(complete_episode):
    text = render_package(complete_episode, "ep-1", rendering="full", now=NOW)
    assert "seal verified by `docket validate` (rule run-seal)" in text
    assert "inputs changed since sealing" not in text
    assert "seal not verified" not in text


def test_inputs_changed_badge_when_a_bound_observation_is_revised_after_sealing(
    complete_episode,
):
    g = complete_episode
    revise(g, "ob-a-m1", value=999)
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "inputs changed since sealing — re-evaluate" in text
    # The run's own record still verifies; only its inputs moved.
    assert "seal verified by `docket validate` (rule run-seal)" in text


def test_seal_not_verified_when_a_sealed_result_is_revised(complete_episode):
    g = complete_episode
    run_id = g.get("ep-1")["runs"][-1]
    run = g.get(run_id)
    agg_id = f"res-{run_id}-{run['ranking'][0]}"
    revise(g, agg_id, value=g.get(agg_id)["value"])  # bumps rev only: rev 1 -> 2
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "seal not verified" in text
    assert "seal verified by `docket validate` (rule run-seal)" not in text


def test_what_flips_prints_refusal_message_instead_of_robustness_when_stale(
    complete_episode,
):
    g = complete_episode
    revise(g, "ob-a-m1", value=999)
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["flipSummary"] == {}
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    section_text = text.split("8. What flips the decision")[-1].split("9. Bias checks")[0]
    assert "Weight-simplex robustness" not in section_text
    assert "robustness withheld" in section_text and "refuses this run" in section_text
    # The per-parameter table itself still comes from the stored FlipAnalysis objects,
    # not from the (refused) weight-simplex summary — every flip's row is still there,
    # naming the run it came from (D2/D3: displayed via the Measure's own attribute,
    # not the full stored parameter.label sentence).
    flips = [g.get(i) for i in g.get("ep-1")["flipAnalyses"]]
    assert flips and all(f["run"] in section_text for f in flips)


def test_refresh_log_states_pairing_and_the_id_only_judgment_limitation():
    g = Graph()
    put_all(
        g,
        policy(), evidence("ev-doc"), drs(), charter(),
        obj("cl-1", "Claim", text="Old claim text.", questionClass="other",
            assessableAt={"level": "U"}, supportedBy=[{"evidence": "ev-doc"}]),
        obj("cl-2", "Claim", text="New claim text.", questionClass="other",
            assessableAt={"level": "U"}, supportedBy=[{"evidence": "ev-doc"}]),
        {**episode(), "claims": ["cl-1"], "lifecycleState": "SUSPECT"},
        obj("prog-1", "DecisionProgram", name="p", charter="ch-1", episodes=["ep-1"],
            refreshTriggers=[], diffs=[]),
        obj("trig-1", "RefreshTrigger", kind="evidence-changed", source="s", description="d",
            detectedAt=NOW, affected=["cl-1"]),
    )
    new_ep = open_refresh(g, "prog-1", "trig-1", actor=H, now=NOW,
                           replacements={"cl-1": "cl-2"})
    diff_episodes(g, "ep-1", new_ep["id"], now=NOW)
    text = render_package(g, new_ep["id"], rendering="full", now=NOW)
    assert "(replacements pairing)" in text
    assert "compared by claim id only, not content" in text


# ---- fix round 1 -----------------------------------------------------------------


def test_c1_unclassified_narrative_sentence_citing_a_withheld_value_is_redacted(base_graph):
    g = base_graph
    put_all(
        g,
        evidence("ev-s", classification={"level": "S", "metadataLevel": "U"}),
        alternative("alt-a", baseline=True),
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="surv",
            metric={"units": "pct", "direction": "max"}, criteria={"threshold": 1}),
        obj("ob-1", "Observation", alternative="alt-a", measure="m-1", value=27,
            evidence="ev-s"),
        obj("nar-1", "Narrative", episode="ep-1", section="evaluation-results",
            sentences=[{"text": "Configuration A scores 27 percent on survivability.",
                        "cites": ["ob-1"]}]),
        {**episode(), "rev": 2, "alternatives": ["alt-a"], "objectives": ["obj-1"],
         "observations": ["ob-1"], "narratives": ["nar-1"]},
    )
    full = render_package(g, "ep-1", rendering="full", now=NOW)
    uncl = render_package(g, "ep-1", rendering="unclassified", now=NOW)
    assert "Configuration A scores 27 percent" in full
    assert "_[sentence withheld: S]_" in uncl
    assert "Configuration A scores 27 percent" not in uncl
    # The withheld value must not survive anywhere in the narrative/results section —
    # scoped past the Cover/annex, since a graph-snapshot hex hash can coincidentally
    # contain "27" as a substring of an unrelated hash digit run.
    section_text = uncl.split("7. Evaluation results")[-1].split("8. What flips")[0]
    assert "27" not in section_text


def test_c2_two_consecutive_full_builds_are_byte_identical(complete_episode):
    g = complete_episode
    pkg1, text1 = build_package(g, "ep-1", rendering="full", now=NOW)
    pkg2, text2 = build_package(g, "ep-1", rendering="full", now=NOW)
    assert text1 == text2
    assert pkg1["hash"] == pkg2["hash"]
    assert pkg1["graphSnapshotHash"] == pkg2["graphSnapshotHash"]


def test_c2_full_then_unclassified_print_the_same_graph_snapshot_hash(complete_episode):
    # R4: must build (not just render) both, so a DecisionPackage is actually written
    # into the graph between the two calls — a bare render_package/render_package pair
    # never writes a package at all, so it cannot tell the C2 fix from its absence
    # (confirmed against the pre-fix code by the round-1 review's mutation check).
    g = complete_episode
    _, full = build_package(g, "ep-1", rendering="full", now=NOW)
    _, uncl = build_package(g, "ep-1", rendering="unclassified", now=NOW)

    def snapshot_line(text):
        return next(line for line in text.splitlines() if line.startswith("- Graph snapshot:"))

    assert snapshot_line(full) == snapshot_line(uncl)


def test_c2_verify_semantics_reusing_prior_renderedAt_reproduces_identical_bytes(
    complete_episode,
):
    """Plan 07's `/verify`: re-render at `now = prior["renderedAt"]` and expect
    identical bytes, even after an unrelated intervening build at a different `now`."""
    g = complete_episode
    prior, prior_text = build_package(g, "ep-1", rendering="full", now=NOW)
    build_package(g, "ep-1", rendering="full", now="2026-09-05T00:00:00Z")
    _, verify_text = build_package(g, "ep-1", rendering="full", now=prior["renderedAt"])
    assert verify_text == prior_text


def test_c3_empty_rationale_prints_typed_marker_and_names_the_live_silence_finding(
    complete_episode,
):
    g = complete_episode
    revise(g, "as-1", rationale="")
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "rationale: _[not stated]_" in text
    section_text = text.split("10. Readiness")[-1].split("11. Risks")[0]
    assert "no readiness report has been produced" in section_text
    assert "silence" in section_text and "rationale" in section_text


def test_i4_numeral_only_present_in_a_hash_field_is_refused(base_graph):
    g = base_graph
    put_all(g, obj(
        "run-x", "EvaluationRun", plan="pl-1", step="s1", evaluator="mdl-1",
        evaluatorVersion="1", method="mavt",
        inputsHash="a" * 32, parameterBindings={}, seed=1, kernelVersion="0.1.0",
        outputs=[], outputHashes=[], ranking=["alt-a"], sealedAt=NOW, sealedBy="kernel",
        runRecordHash="a" * 30 + "42",
    ))
    nar = obj("nar-1", "Narrative", episode="ep-1", section="evaluation-results",
              sentences=[{"text": "The record shows 42 clearly.", "cites": ["run-x"]}])
    errs = check_citations(g, nar)
    assert errs and "42" in errs[0]


def test_i5_flip_summary_names_its_run_and_lists_runs_not_summarised(complete_episode):
    g = complete_episode
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    run_id = g.get("ep-1")["runs"][-1]
    assert rr["flipSummary"]["runsNotSummarised"] == []
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    section_text = text.split("8. What flips the decision")[-1].split("9. Bias checks")[0]
    assert f"for run {run_id}" in section_text


def test_i10_flip_table_carries_a_stale_run_badge_naming_the_run(complete_episode):
    g = complete_episode
    run_id = g.get("ep-1")["runs"][-1]
    revise(g, "ob-a-m1", value=999)
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    section_text = text.split("8. What flips the decision")[-1].split("9. Bias checks")[0]
    assert f"inputs changed since sealing for run {run_id}" in section_text


def test_i6_rating_scale_legend_and_aggregation_rule_are_printed():
    g = Graph()
    put_all(g, policy(tailoring="gao-23-106549"), evidence("ev-doc"), drs(), charter(),
            episode())
    readiness_report(g, "ep-1", seed=SEED, now=NOW)
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "Rating scale (GAO-11-82R" in text
    assert "indeterminate" in text
    assert "Aggregation rule:" in text


def test_i7_ready_line_is_qualified_no_blocking_findings():
    g = _fresh_base_graph()
    readiness_report(g, "ep-1", seed=SEED, now=NOW)
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "**Ready (no blocking findings):**" in text


def test_i8_dangling_charter_does_not_crash_and_is_named_unavailable():
    g = Graph()
    put_all(g, policy(), evidence("ev-doc"), drs(), {**episode(), "charter": "ch-missing"})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "charter unavailable" in text


def test_i8_dangling_decision_class_policy_does_not_crash():
    g = Graph()
    put_all(g, evidence("ev-doc"), drs(), charter(decisionClassPolicy="pol-missing"),
            episode())
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "policy unresolved" in text


def test_i8_decision_class_policy_pointing_at_a_non_policy_object_does_not_crash():
    g = Graph()
    put_all(g, evidence("ev-doc"), drs(), charter(decisionClassPolicy="ev-doc"), episode())
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "policy unresolved" in text


def test_i8_dangling_objective_id_does_not_crash(base_graph):
    g = base_graph
    put_all(g, {**episode(), "rev": 2, "objectives": ["obj-missing"]})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "objective obj-missing unresolved" in text


def test_i8_dangling_evidence_register_id_does_not_crash(base_graph):
    g = base_graph
    put_all(g, {**episode(), "rev": 2, "evidenceRegister": ["ev-missing"]})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "ev-missing" in text and "unresolved" in text


def test_i8_dangling_run_id_does_not_crash(base_graph):
    g = base_graph
    put_all(g, {**episode(), "rev": 2, "runs": ["run-missing"]})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "run run-missing unresolved" in text


def test_i8_dangling_narrative_id_does_not_crash_and_is_noted_in_the_annex(base_graph):
    g = base_graph
    put_all(g, {**episode(), "rev": 2, "narratives": ["nar-missing"]})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "unresolved narrative references: nar-missing" in text


def test_i9_written_file_uses_utf8_encoding_and_unix_newlines(tmp_path):
    g = _fresh_base_graph()
    put_all(g, obj("nar-1", "Narrative", episode="ep-1", section="problem-statement",
                   sentences=[{"text": "Uses ¶ and · and — characters.", "cites": ["ch-1"]}]))
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H, "narratives": ["nar-1"]})
    _, text = build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path)
    raw = (tmp_path / "package-full.md").read_bytes()
    assert raw == text.encode("utf-8")
    assert b"\r\n" not in raw


def test_i11_scope_review_and_reliability_gated_on_metadata_level_not_just_pointer(
    base_graph,
):
    g = base_graph
    put_all(
        g,
        evidence("ev-s", classification={"level": "S", "metadataLevel": "S"},
                 scopeOfValidity={"builtToAnswer": "SECRET TARGET SET SIZE 42",
                                  "questionClass": "other", "intendedUse": "u"}),
        {**episode(), "rev": 2, "evidenceRegister": ["ev-s"]},
    )
    full = render_package(g, "ep-1", rendering="full", now=NOW)
    uncl = render_package(g, "ep-1", rendering="unclassified", now=NOW)
    assert "SECRET TARGET SET SIZE" in full
    assert "SECRET TARGET SET SIZE" not in uncl
    assert "[withheld: S]" in uncl


def test_m2_evidence_and_observation_tables_are_order_insensitive_to_list_order(base_graph):
    g = base_graph
    put_all(
        g,
        evidence("ev-a"), evidence("ev-b"),
        alternative("alt-a"),
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="m",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 1}),
        obj("ob-a", "Observation", alternative="alt-a", measure="m-1", value=1, evidence="ev-a"),
        obj("ob-b", "Observation", alternative="alt-a", measure="m-1", value=2, evidence="ev-b"),
    )
    forward = {**episode(), "rev": 2, "alternatives": ["alt-a"], "objectives": ["obj-1"],
               "evidenceRegister": ["ev-a", "ev-b"], "observations": ["ob-a", "ob-b"]}
    put_all(g, forward)
    text_forward = render_package(g, "ep-1", rendering="full", now=NOW)
    reversed_ep = {**forward, "rev": 3, "evidenceRegister": ["ev-b", "ev-a"],
                   "observations": ["ob-b", "ob-a"]}
    put_all(g, reversed_ep)
    text_reversed = render_package(g, "ep-1", rendering="full", now=NOW)

    def table(text, start, end):
        return text.split(start)[-1].split(end)[0]

    # The Cover/annex graph-snapshot hash legitimately differs between the two
    # revisions (the episode's own stored list order is part of its content hash) —
    # M2 is about the *tables themselves* reading the same regardless of that order.
    assert (table(text_forward, "6. Evidence register", "7. Evaluation results")
            == table(text_reversed, "6. Evidence register", "7. Evaluation results"))
    assert (table(text_forward, "7. Evaluation results", "8. What flips")
            == table(text_reversed, "7. Evaluation results", "8. What flips"))


def test_m3_measure_criteria_renders_as_objective_slash_threshold_not_json(base_graph):
    g = base_graph
    put_all(
        g,
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="m",
            metric={"units": "u", "direction": "max"},
            criteria={"threshold": 50, "objective": 80}),
        {**episode(), "rev": 2, "objectives": ["obj-1"]},
    )
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "objective 80 / threshold 50" in text
    assert '"objective":80' not in text


def test_m4_truncated_justification_shows_ellipsis():
    g = _fresh_base_graph()
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    sa = g.get(rr["standardsAssessment"])
    ratings = list(sa["ratings"])
    ratings[0] = {**ratings[0], "justification": [f"x-{i}" for i in range(8)]}
    g.put({**sa, "rev": sa["rev"] + 1, "ratings": ratings}, KERNEL_ACTOR)
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "x-0, x-1, x-2, x-3, x-4, x-5…" in text


def test_m5_charter_authority_board_and_delegations_print(base_graph):
    g = base_graph
    put_all(g, {**g.get("ch-1"), "rev": 2,
               "authority": {"signer": "PM", "board": "CSG", "delegations": ["deputy PM"]}})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "board CSG" in text and "deputy PM" in text


def test_m5_evidence_accreditedFor_and_validUntil_print(base_graph):
    g = base_graph
    put_all(
        g,
        evidence("ev-acc", scopeOfValidity={
            "builtToAnswer": "q", "questionClass": "other", "intendedUse": "u",
            "accreditedFor": "desert conditions", "validUntil": "2020-01-01"}),
        {**episode(), "rev": 2, "evidenceRegister": ["ev-acc"]},
    )
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "desert conditions" in text and "2020-01-01" in text


def test_m5_risk_mitigation_and_monitor_print(base_graph):
    g = base_graph
    put_all(
        g,
        obj("act-1", "Action", description="Re-run the weighting session", owner="analyst",
            status="open"),
        obj("rk-1", "Risk", statement="s", kind="other", consequence="c", owner="o",
            status="open", mitigation=["act-1"], monitor="Watch the metric monthly."),
        {**episode(), "rev": 2, "risks": ["rk-1"]},
    )
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "Re-run the weighting session" in text and "Watch the metric monthly." in text


def test_m5_claim_text_prints_in_traceability_rows(base_graph):
    g = base_graph
    put_all(g, obj("cl-1", "Claim", text="A specific, quotable claim sentence.",
                   questionClass="other", assessableAt={"level": "U"},
                   supportedBy=[{"evidence": "ev-doc"}]),
            {**episode(), "rev": 2, "claims": ["cl-1"]})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "A specific, quotable claim sentence." in text


def test_m7_graph_object_exists_even_if_the_file_write_fails(tmp_path, monkeypatch):
    g = _fresh_base_graph()

    def boom(self, *a, **kw):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr("pathlib.Path.write_text", boom)
    with pytest.raises(OSError):
        build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path)
    # The DecisionPackage object is already in the graph, regenerable, even though the
    # file write failed — never the reverse (an orphan file naming no object).
    pkgs = g.all("DecisionPackage")
    assert len(pkgs) == 1 and pkgs[0]["episode"] == "ep-1"
    assert not (tmp_path / "package-full.md").exists()


# ---- Demo A findings (D1-D4) ------------------------------------------------------


def test_d1_unreferenced_exclusion_still_prints_under_other_exclusions_on_record(
    base_graph,
):
    g = base_graph
    put_all(g, obj(
        "ex-orphan", "Exclusion",
        target={"kind": "Alternative", "label": "long-distance transportability"},
        reasonType="out-of-scope",
        reason="CBO excluded long-distance transportability from its comparison.",
        authority={"who": "CBO", "role": "analyst", "date": "2013-04"},
        retainedInStructure=True,
    ))
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    section_text = text.split("10. Readiness")[-1].split("11. Risks")[0]
    assert "Other exclusions on record" in section_text
    assert "ex-orphan" in section_text
    assert "CBO excluded long-distance transportability" in section_text


def test_d1_exclusion_printed_elsewhere_is_not_duplicated_in_other_exclusions(base_graph):
    """An Exclusion already shown through its natural slot (here, an Alternative's own
    `statusReason`) must not also appear in the catch-all list — printed once, D1
    says, not twice."""
    g = base_graph
    put_all(
        g,
        obj("ex-dominated", "Exclusion", target={"kind": "Alternative", "label": "alt-b"},
            reasonType="dominated", reason="Dominated on both measures.",
            authority={"who": "PM", "role": "decision authority", "date": "2026-08-01"},
            retainedInStructure=True),
        alternative("alt-b", status="screened-out", statusReason="ex-dominated"),
        {**episode(), "rev": 2, "alternatives": ["alt-b"]},
    )
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "Dominated on both measures." in text
    assert text.count("ex-dominated") <= 1 or "Other exclusions on record" not in (
        text.split("10. Readiness")[-1].split("11. Risks")[0]
    )
    section_text = text.split("10. Readiness")[-1].split("11. Risks")[0]
    assert "ex-dominated" not in section_text


def test_d2_flip_table_names_the_run_for_each_row(complete_episode):
    g = complete_episode
    run_id = g.get("ep-1")["runs"][-1]
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    section_text = text.split("8. What flips the decision")[-1].split("9. Bias checks")[0]
    assert "| run |" in section_text
    assert run_id in section_text


def test_d3_flip_label_uses_measure_attribute_not_the_full_stored_sentence(
    complete_episode,
):
    g = complete_episode
    m1 = g.get("m-1")
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    section_text = text.split("8. What flips the decision")[-1].split("9. Bias checks")[0]
    assert f"weight on {m1['attribute']}" in section_text
    flips = [g.get(i) for i in g.get("ep-1")["flipAnalyses"]]
    stored_labels = {f["parameter"]["label"] for f in flips if f["parameter"]["kind"] == "weight"}
    assert stored_labels and all(label not in section_text for label in stored_labels)


def test_d4_alternatives_sort_by_entered_order_then_id_not_by_id_alone(base_graph):
    g = base_graph
    put_all(
        g,
        alternative("alt-zzz", order=1, name="Z first entered"),
        alternative("alt-aaa", order=2, name="A second entered"),
        {**episode(), "rev": 2, "alternatives": ["alt-aaa", "alt-zzz"]},
    )
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    section_text = text.split("4. Alternatives")[-1].split("5. Ground rules")[0]
    assert section_text.index("Z first entered") < section_text.index("A second entered")


# ---- fix round 2 (re-review) -------------------------------------------------------


def test_r1_unclassified_leak_through_a_non_aggregate_result_citation_is_redacted(
    complete_episode,
):
    """R1: `evaluate()` stamps a non-aggregate Result's `raw` field with the untouched
    observation value, so citing that Result is citing the observation one hop removed
    — the same withholding rule must apply."""
    g = complete_episode
    revise(g, "ev-test", classification={"level": "S", "metadataLevel": "U"})
    run_id = g.get("ep-1")["runs"][-1]
    res_id = f"res-{run_id}-alt-a-m-1"
    assert g.has(res_id) and g.get(res_id)["aggregate"] is False
    put_all(g, obj(
        "nar-leak", "Narrative", episode="ep-1", section="evaluation-results",
        sentences=[{"text": "Configuration A was measured at 80 on the capability "
                            "measure.", "cites": [res_id]}],
    ))
    ep = g.get("ep-1")
    put_all(g, {**ep, "rev": ep["rev"] + 1, "createdBy": H,
               "narratives": ep["narratives"] + ["nar-leak"]})
    full = render_package(g, "ep-1", rendering="full", now=NOW)
    uncl = render_package(g, "ep-1", rendering="unclassified", now=NOW)
    assert "Configuration A was measured at 80" in full
    assert "_[sentence withheld: S]_" in uncl
    # Scoped to the section the leak was in: "80" legitimately appears elsewhere on
    # the page (an unrelated measure's criteria), so a bare "not in uncl" would be a
    # weak assertion, not a probe of the actual defect.
    section_text = uncl.split("7. Evaluation results")[-1].split("8. What flips")[0]
    assert "80" not in section_text


def test_r2_blocking_finding_after_a_stale_readiness_report_is_named_not_hidden(
    complete_episode,
):
    """R2: a stored ReadinessReport does not update itself when the episode is edited
    afterwards — the branch Demo A and plan 07 actually take. A live blocking finding
    absent from the stored `blockers` must still be named, and `Ready` must not read
    `True` while one is outstanding."""
    g = complete_episode
    readiness_report(g, "ep-1", seed=SEED, now=NOW)
    revise(g, "as-1", rationale="")
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    section_text = text.split("10. Readiness")[-1].split("11. Risks")[0]
    ready_line = next(
        line for line in section_text.splitlines() if line.startswith("**Ready")
    )
    assert "unavailable — record changed since the readiness report" in ready_line
    assert "True" not in ready_line
    assert "Blocking findings since the readiness report" in section_text
    assert "silence" in section_text and "rationale" in section_text


def test_r3_slot_exclusion_marker_pointing_at_a_deleted_object_does_not_crash(base_graph):
    g = base_graph
    put_all(g, {**g.get("ch-1"), "rev": 2, "question": {"$exclusion": "x-missing"}})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "_[exclusion x-missing unresolved]_" in text


def test_r3_slot_gap_marker_pointing_at_a_deleted_object_does_not_crash(base_graph):
    g = base_graph
    put_all(g, {**g.get("ch-1"), "rev": 2, "question": {"$gap": "g-missing"}})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "_[gap g-missing unresolved]_" in text


def test_r3_readiness_pointing_at_a_wrong_typed_object_does_not_crash(base_graph):
    g = base_graph
    put_all(g, {**episode(), "rev": 2, "readiness": "ev-doc"})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "8. What flips the decision" in text
    assert "10. Readiness" in text


def test_r4_c2_test_uses_build_package_and_actually_catches_the_regression():
    """Documents the round-1 review's own mutation check as a standing assertion:
    building the same content twice must print the same graph-snapshot line even
    though the second build has one more `DecisionPackage` sitting in the graph than
    the first (proving `_content_snapshot` — and not coincidence — is what the
    `test_c2_full_then_unclassified_print_the_same_graph_snapshot_hash` test above
    actually exercises, now that it calls `build_package`, not `render_package`)."""
    g = _fresh_base_graph()
    pkg1, text1 = build_package(g, "ep-1", rendering="full", now=NOW)
    pkg2, text2 = build_package(g, "ep-1", rendering="full", now=NOW)
    assert len(g.all("DecisionPackage")) == 2
    assert pkg1["graphSnapshotHash"] == pkg2["graphSnapshotHash"]

    def snapshot_line(text):
        return next(line for line in text.splitlines() if line.startswith("- Graph snapshot:"))

    assert snapshot_line(text1) == snapshot_line(text2)


def test_r5_missing_threshold_and_distance_render_as_a_dash_not_python_none(base_graph):
    g = base_graph
    put_all(g, obj(
        "flip-x", "FlipAnalysis", run="run-x", parameter={"kind": "weight",
        "target": "ws-1:m-1", "label": "weight on m"}, currentValue=0.5,
        range={"lo": 0.0, "hi": 1.0, "source": "default"}, flipThreshold=None,
        flipDistance=None, direction="none", rankingBefore=["alt-a"], rankingAfter=None,
        kernelVersion="0.1.0",
    ), {**episode(), "rev": 2, "flipAnalyses": ["flip-x"]})
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    section_text = text.split("8. What flips the decision")[-1].split("9. Bias checks")[0]
    assert "None" not in section_text
    assert " | — | — | none |" in section_text


def test_r6_content_snapshot_hash_is_exported_and_matches_the_stored_graphSnapshotHash(
    complete_episode,
):
    g = complete_episode
    pkg, _ = build_package(g, "ep-1", rendering="full", now=NOW)
    assert content_snapshot_hash(g) == pkg["graphSnapshotHash"]


def test_r7_annex_labels_state_what_the_counts_exclude(complete_episode):
    g = complete_episode
    build_package(g, "ep-1", rendering="full", now=NOW)
    text = render_package(g, "ep-1", rendering="full", now=NOW)
    assert "objects (excluding rendered packages):" in text
    assert "log entries (excluding package writes):" in text


def test_render_is_identical_after_a_save_and_load_round_trip(tmp_path):
    """The store sorts keys on save, so a dict-valued field such as dimensionVerdicts
    comes back in a different order than it was written; the renderer must not let that
    order reach the page."""
    from tests.kernel.conftest import COMPLETE_NOW, complete_graph

    g = complete_graph()
    readiness_report(g, "ep-1", seed=1, now=COMPLETE_NOW)
    before = render_package(g, "ep-1", rendering="full", now=COMPLETE_NOW)
    g.save(tmp_path / "graph")
    reloaded = Graph.load(tmp_path / "graph")
    after = render_package(reloaded, "ep-1", rendering="full", now=COMPLETE_NOW)
    assert before == after
