# tests/kernel/test_readiness.py
"""The readiness report: one verdict, and every reason behind it named by id."""
import contextlib

import pytest

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.canon import canonical_json
from docket.errors import TransitionRefused, ValidationError
from docket.kernel.evaluate import evaluate
from docket.kernel.lifecycle import transition
from docket.kernel.readiness import readiness_report
from docket.kernel.validate import validate
from tests.kernel.conftest import (
    COMPLETE_SEED,
    NOW,
    H,
    alternative,
    charter,
    complete_graph,
    episode,
    evidence,
    gap,
    measure,
    obj,
    objective,
    put_all,
    revise,
)

SEED = 11
STRUCTURAL = ("schema", "ref-integrity", "silence", "marker-type", "log-chain", "authority",
              "run-seal")


def with_programme(g):
    """`complete_episode` given a lineage: a programme with its own charter and one
    earlier episode (sequence 0) carrying a charter of its own."""
    put_all(g,
            charter("ch-prior", question="Which configurations are worth comparing at all?"),
            charter("ch-programme", question="How should the fleet be recapitalised?"),
            episode("ep-0", sequence=0, charter="ch-prior", biasChecks=["bc-1", "bc-2"]),
            obj("prg-1", "DecisionProgram", name="Fleet recapitalisation",
                charter="ch-programme", episodes=["ep-0", "ep-1"],
                refreshTriggers=[], diffs=[]))
    revise(g, "ep-1", program="prg-1")
    return g


def with_second_run(g):
    """A second sealed run on the same episode — a second single-step Plan over the same
    inputs. Demo A's plan has two steps, so a two-run episode is the normal case."""
    put_all(g, obj("pl-2", "Plan", episode="ep-1", policyBasis="pol-1",
                   approvedBy={"actorId": "programme manager", "date": "2026-08-27"},
                   deviations=[], steps=list(g.get("pl-1")["steps"])))
    revise(g, "ep-1", plan="pl-2")
    evaluate(g, "pl-2", seed=COMPLETE_SEED, now=NOW)
    return g


def exclusion(oid, target_id, label, **over):
    """A typed Exclusion — the conftest has no builder for one and is read-only."""
    base = dict(target={"kind": "Alternative", "id": target_id, "label": label},
                reasonType="dominated",
                reason="Dominated on both measures by Configuration A.",
                authority={"who": "programme manager", "role": "decision authority",
                           "date": "2026-08-01"},
                retainedInStructure=True)
    base.update(over)
    return obj(oid, "Exclusion", **base)


def flip_distance_by_assumption(g, episode_id="ep-1"):
    out = {}
    for fid in g.get(episode_id)["flipAnalyses"]:
        f = g.get(fid)
        if isinstance(f.get("assumption"), str) and f["flipDistance"] is not None:
            out[f["assumption"]] = min(out.get(f["assumption"], 9.9), f["flipDistance"])
    return out


# ---- the brief's own case ------------------------------------------------------------


def test_readiness_assembles_and_blocks_on_linchpin_gap(base_graph):
    g = base_graph
    put_all(g, gap("gap-1", impact="blocking"),
            obj("as-1", "Assumption", statement="Poland bridges are representative",
                linchpin=True, rationale="r", evidence={"$gap": "gap-1"},
                implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
                variedInSensitivity=False),
            alternative("alt-a", baseline=True),
            {**episode(), "rev": 2, "assumptions": ["as-1"], "alternatives": ["alt-a"]})
    rr = readiness_report(g, "ep-1", seed=1, now="2026-09-04T00:00:00Z")
    assert rr["ready"] is False
    assert any(b["rule"] == "linchpin-unevidenced" for b in rr["blockers"])
    assert rr["openGaps"] == ["gap-1"]
    assert g.get(rr["standardsAssessment"])["tailoring"] == "published-21"
    assert g.get("ep-1")["readiness"] == rr["id"]
    assert rr["flipSummary"] == {} and rr["policyVersion"] == "0.1"


# ---- the positive case ---------------------------------------------------------------


def test_complete_episode_is_ready_with_no_blockers(complete_episode):
    g = complete_episode
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)

    assert rr["blockers"] == []
    assert rr["ready"] is True
    assert rr["id"] == "rr-ep-1-1"
    assert rr["episode"] == "ep-1"
    assert g.get("ep-1")["readiness"] == "rr-ep-1-1"
    assert g.get(rr["standardsAssessment"])["tailoring"] == "full-36"
    assert g.get(rr["mandateScorecard"])["rows"] == [
        {"element": "me-1", "status": "satisfied", "satisfiedBy": ["cl-1"]}
    ]
    assert rr["flipSummary"]["run"] == "run-pl-1-s1"
    assert rr["flipSummary"]["seed"] == SEED
    assert rr["biasChecksStatus"] == [{"check": "bc-1", "status": "performed"},
                                      {"check": "bc-2", "status": "performed"}]
    assert rr["openGaps"] == [] and rr["openExclusions"] == []
    assert rr["policyVersion"] == "0.1"
    assert rr["kernelVersion"] == KERNEL_VERSION
    assert rr["seed"] == SEED


def test_the_report_is_stored_and_leaves_the_store_clean(complete_episode):
    g = complete_episode
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)

    stored = g.get(rr["id"])
    assert stored == rr
    assert stored["type"] == "ReadinessReport" and stored["rev"] == 1
    assert stored["createdBy"] == KERNEL_ACTOR and stored["createdAt"] == NOW
    ep = g.get("ep-1")
    assert ep["createdBy"] == KERNEL_ACTOR and ep["createdAt"] == NOW
    assert [f for f in validate(g) if f.rule in STRUCTURAL] == []


def test_two_builds_of_the_same_record_produce_identical_reports():
    one, two = complete_graph(), complete_graph()
    first = readiness_report(one, "ep-1", seed=SEED, now=NOW)
    second = readiness_report(two, "ep-1", seed=SEED, now=NOW)
    assert canonical_json(first) == canonical_json(second)
    assert one.snapshot_hash() == two.snapshot_hash()


def test_a_second_call_on_a_clean_record_is_still_ready(complete_episode):
    """The re-run defect the 03a review predicted: `bias_indicators` writing the same
    Risk id twice used to make the second report impossible."""
    g = complete_episode
    first = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    second = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert (first["id"], second["id"]) == ("rr-ep-1-1", "rr-ep-1-2")
    assert second["ready"] is True and second["blockers"] == []
    assert g.get("ep-1")["readiness"] == "rr-ep-1-2"
    assert [f for f in validate(g) if f.rule in STRUCTURAL] == []


def attempt_to_sign(g):
    """Attempt G3 and return the transition record it wrote, refused or not."""
    with contextlib.suppress(TransitionRefused):
        transition(g, "ep-1", "SIGNED", H, now=NOW)
    return g.get("ep-1")["transitions"][-1]


def test_the_signature_gate_reads_the_reports_verdict(complete_episode):
    """Both directions of the contract with G3. Whether the signature also binds to a
    built package is `commitment-package-hash`'s business, not this module's, so the
    gate is read through its own record rather than by requiring the whole edge."""
    g = complete_episode
    assert readiness_report(g, "ep-1", seed=SEED, now=NOW)["ready"] is True
    for state in ("EVALUATED", "PENDING_SIGNATURE"):
        transition(g, "ep-1", state, H, now=NOW)  # PENDING_SIGNATURE needs a report at all
    assert g.get("ep-1")["lifecycleState"] == "PENDING_SIGNATURE"
    assert "readiness-ready" in attempt_to_sign(g)["checksSatisfied"]

    revise(g, "ep-1", alternatives=["alt-a", "alt-b"])  # drops the baseline
    assert readiness_report(g, "ep-1", seed=SEED, now=NOW)["ready"] is False
    assert "readiness-ready" in attempt_to_sign(g)["checksUnsatisfied"]


def test_ready_is_exactly_not_blockers(complete_episode):
    g = complete_episode
    revise(g, "ep-1", alternatives=["alt-a", "alt-b"])  # drops the baseline
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert [b["rule"] for b in rr["blockers"]] == ["baseline-present"]
    assert rr["ready"] is (not rr["blockers"])


# ---- where blockers come from --------------------------------------------------------


def test_structural_blocking_findings_block_and_dangling_ids_do_not_crash(complete_episode):
    g = complete_episode
    revise(g, "ep-1", objectives=["obj-1", "obj-missing"])
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["ready"] is False
    assert any(b["rule"] == "ref-integrity" and b["objects"] == ["ep-1"]
               for b in rr["blockers"])


def test_scope_blocking_findings_block(complete_episode):
    g = complete_episode
    revise(g, "ev-test", reviewStatus="rejected")
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert any(b["rule"] == "claim-on-rejected-evidence" and b["objects"] == ["cl-2", "ev-test"]
               for b in rr["blockers"])
    assert rr["ready"] is False


def test_policy_blocking_rules_promote_a_warning_and_warnings_are_kept(complete_episode):
    g = complete_episode
    put_all(g, gap("gap-x", impact="degrading", confirmed=False))
    revise(g, "con-1", source={"$gap": "gap-x"})

    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["ready"] is True
    assert rr["openGaps"] == ["gap-x"]
    assert [w["rule"] for w in rr["warnings"]] == ["gap-unconfirmed"]

    revise(g, "pol-1", blockingRules=["gap-unconfirmed"])
    again = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert again["id"] == "rr-ep-1-2"
    assert again["ready"] is False
    assert [b["rule"] for b in again["blockers"]] == ["gap-unconfirmed"]
    assert again["blockers"][0]["severity"] == "warning"
    assert again["blockers"][0]["promotedBy"] == "policy.blockingRules"
    assert again["warnings"] == []


def test_a_blocking_rule_no_kernel_rule_emits_is_itself_a_blocker(complete_episode):
    """A one-character typo in a policy would otherwise switch off a blocker the policy
    author asked for, and the package would print a clean readiness section."""
    g = complete_episode
    revise(g, "pol-1", blockingRules=["linchpin-unevidencd", "gap-unconfirmed"])
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)

    assert rr["ready"] is False
    unknown = [b for b in rr["blockers"] if b["rule"] == "blocking-rule-unknown"]
    assert len(unknown) == 1
    assert unknown[0]["objects"] == ["pol-1"]
    assert "linchpin-unevidencd" in unknown[0]["message"]


def test_info_findings_are_recorded_not_dropped(complete_episode):
    g = complete_episode
    sov = {**g.get("ev-test")["scopeOfValidity"], "questionClass": "cost"}
    revise(g, "ev-test", scopeOfValidity=sov)
    revise(g, "cl-2", supportedBy=[{"evidence": "ev-test",
                                    "reuseJustification": {"text": "The cost dataset is the "
                                                                   "same instrumented run.",
                                                            "authority": "chief engineer"}}])
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["ready"] is True
    assert any(w["rule"] == "reuse-justified" and w["severity"] == "info"
               for w in rr["warnings"])


def test_a_stale_run_is_a_blocker_not_a_crash(complete_episode):
    g = complete_episode
    revise(g, "ob-b-m1", value=61)
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)

    assert rr["flipSummary"] == {}
    assert rr["ready"] is False
    stale = [b for b in rr["blockers"] if b["rule"] == "run-stale"]
    assert len(stale) == 1
    assert stale[0]["objects"] == ["run-pl-1-s1"]
    assert stale[0]["message"].startswith("run stale; re-evaluate")
    assert any(w["rule"] == "run-inputs-changed" for w in rr["warnings"])


def test_a_stale_run_blocks_even_when_the_policy_lists_nothing(complete_episode):
    g = complete_episode
    assert g.get("pol-1")["blockingRules"] == []
    revise(g, "ob-b-m1", value=61)
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert [b["rule"] for b in rr["blockers"]] == ["run-stale"]


def test_the_runs_not_summarised_are_named(complete_episode):
    g = with_second_run(complete_episode)
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["ready"] is True
    assert rr["flipSummary"]["run"] == "run-pl-2-s1"
    assert rr["flipSummary"]["runsNotSummarised"] == ["run-pl-1-s1"]


def test_a_dangling_last_run_is_named_not_silently_replaced(complete_episode):
    g = complete_episode
    revise(g, "ep-1", runs=["run-pl-1-s1", "run-gone"])
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["flipSummary"] == {}
    assert any(b["rule"] == "flip-summary-unavailable" and b["objects"] == ["run-gone"]
               for b in rr["blockers"])
    assert any(b["rule"] == "ref-integrity" for b in rr["blockers"])


# ---- the three design §7.1 readiness checks ------------------------------------------


def test_primary_objective_no_run_covers_is_a_blocker(complete_episode):
    g = complete_episode
    put_all(g,
            objective("obj-2", measures=["m-3"], name="Sustain the fleet",
                      description="Availability.", provenance="ev-doc"),
            measure("m-3", "obj-2", task="Keep the fleet available", attribute="Availability",
                    measure="Operational availability",
                    metric={"units": "percent", "direction": "max"},
                    criteria={"threshold": 70, "objective": 90}))
    revise(g, "ep-1", objectives=["obj-1", "obj-2"])
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert [b["rule"] for b in rr["blockers"]] == ["objective-run-coverage"]
    assert rr["blockers"][0]["objects"] == ["obj-2"]


def test_accreditation_with_no_stated_scope_is_a_blocker(complete_episode):
    g = complete_episode
    revise(g, "vva-1", accreditationDecision={**g.get("vva-1")["accreditationDecision"],
                                              "scope": ""})
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert [b["rule"] for b in rr["blockers"]] == ["accreditation-scope"]
    assert rr["blockers"][0]["objects"] == ["mdl-1", "vva-1"]
    assert "states no scope" in rr["blockers"][0]["message"]


def test_accreditation_against_a_charter_outside_the_lineage_is_a_blocker(complete_episode):
    g = complete_episode
    put_all(g, charter("ch-other", question="Which supplier should build the winner?"))
    revise(g, "vva-1", problemStatement="ch-other")
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert [b["rule"] for b in rr["blockers"]] == ["accreditation-scope"]
    assert rr["blockers"][0]["objects"] == ["mdl-1", "vva-1", "ch-other"]


def test_an_unrelated_charter_asking_the_same_question_is_still_a_blocker(complete_episode):
    """Lineage, not wording. A charter nobody in this programme ever adopted does not
    become this decision's problem statement by asking the same question."""
    g = complete_episode
    put_all(g, charter("ch-lookalike", question=g.get("ch-1")["question"]))
    revise(g, "vva-1", problemStatement="ch-lookalike")
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert [b["rule"] for b in rr["blockers"]] == ["accreditation-scope"]
    assert rr["blockers"][0]["objects"] == ["mdl-1", "vva-1", "ch-lookalike"]


def test_an_earlier_episodes_charter_in_the_same_programme_is_accepted(complete_episode):
    """A model accredited for episode 1 of a programme is accredited for episode 2:
    the refresh path re-uses the model, and re-accreditation is the elapsed-time rule's
    business (AR 5-11 ¶4-2i(3)), not this check's."""
    g = with_programme(complete_episode)
    revise(g, "vva-1", problemStatement="ch-prior")
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["blockers"] == [] and rr["ready"] is True


def test_the_programmes_own_charter_is_accepted(complete_episode):
    g = with_programme(complete_episode)
    revise(g, "vva-1", problemStatement="ch-programme")
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["blockers"] == [] and rr["ready"] is True


def test_a_later_episodes_charter_is_not_accepted(complete_episode):
    """Lower `sequence` only: an accreditation cannot be justified by a decision that
    had not been taken yet."""
    g = with_programme(complete_episode)
    put_all(g, charter("ch-later", question="A question asked after this one."),
            episode("ep-2", sequence=9, charter="ch-later",
                    biasChecks=["bc-1", "bc-2"]))
    revise(g, "prg-1", episodes=["ep-0", "ep-1", "ep-2"])
    revise(g, "vva-1", problemStatement="ch-later")
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert [b["rule"] for b in rr["blockers"]] == ["accreditation-scope"]
    assert rr["blockers"][0]["objects"] == ["mdl-1", "vva-1", "ch-later"]


def test_required_bias_check_needs_reviewed_evidence(complete_episode):
    g = complete_episode
    put_all(g, evidence("ev-premortem-notes", title="Premortem session notes",
                        reviewStatus="draft", publisher="programme office",
                        published="2026-07-15"))
    revise(g, "bc-1", producedEvidence="ev-premortem-notes")
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert [b["rule"] for b in rr["blockers"]] == ["bias-check-evidence-unreviewed"]
    assert rr["blockers"][0]["objects"] == ["bc-1", "ev-premortem-notes"]


# ---- gaps and exclusions -------------------------------------------------------------


def test_open_gaps_rank_blocking_first_then_shortest_flip_distance(complete_episode):
    g = complete_episode
    put_all(g, gap("gap-block", impact="blocking"),
            gap("gap-as1", impact="degrading"), gap("gap-as2", impact="degrading"))
    revise(g, "con-1", source={"$gap": "gap-block"})
    revise(g, "as-1", evidence={"$gap": "gap-as1"})
    revise(g, "as-2", evidence={"$gap": "gap-as2"})

    distances = flip_distance_by_assumption(g)
    nearer, further = ("gap-as1", "gap-as2") if distances["as-1"] < distances["as-2"] \
        else ("gap-as2", "gap-as1")

    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["openGaps"] == ["gap-block", nearer, further]
    assert {b["rule"] for b in rr["blockers"]} == {"linchpin-unevidenced"}


def test_open_exclusions_are_listed(complete_episode):
    g = complete_episode
    put_all(g, alternative("alt-c", order=4, status="screened-out", name="Configuration C",
                           description="Dominated on both measures.", statusReason="ex-c"),
            exclusion("ex-c", "alt-c", "Configuration C"))
    revise(g, "ep-1", alternatives=["alt-a", "alt-b", "alt-base", "alt-c"])
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["openExclusions"] == ["ex-c"]
    assert rr["ready"] is True


# ---- tolerance and refusal -----------------------------------------------------------


def test_an_id_that_is_not_an_episode_is_a_named_refusal(base_graph):
    for bad in ("ep-nope", "ch-1", None):
        with pytest.raises(ValidationError) as exc:
            readiness_report(base_graph, bad, seed=SEED, now=NOW)
        assert "is not a DecisionEpisode" in str(exc.value)


def test_an_unresolvable_policy_still_produces_a_report(complete_episode):
    g = complete_episode
    revise(g, "ch-1", decisionClassPolicy="pol-gone")
    rr = readiness_report(g, "ep-1", tailoring="published-21", k=1, seed=SEED, now=NOW)
    assert rr["policyVersion"] == "unknown"
    assert rr["ready"] is False
    assert any(b["rule"] == "ref-integrity" and b["objects"] == ["ch-1"] for b in rr["blockers"])


def test_a_decision_class_policy_that_is_not_a_policy_is_reported(complete_episode):
    """The schema types the field `ref: Policy` but nothing checks the target's type, so
    every policy-dependent rule would no-op in silence."""
    g = complete_episode
    revise(g, "ch-1", decisionClassPolicy="ev-doc")
    rr = readiness_report(g, "ep-1", tailoring="full-36", seed=SEED, now=NOW)
    assert rr["policyVersion"] == "unknown"
    assert rr["ready"] is False
    unresolved = [b for b in rr["blockers"] if b["rule"] == "policy-unresolved"]
    assert len(unresolved) == 1 and unresolved[0]["objects"] == ["ch-1", "ev-doc"]


def test_a_broken_policy_reference_does_not_hide_the_structure_only_rules(complete_episode):
    """A mistyped policy reference must not turn the readiness section quiet: the rules
    that read no policy field at all still have something to say about this record.

    The stand-in readiness.py passes when `decisionClassPolicy` cannot be read as a
    Policy is `{}`, not a fragment carrying the broken reference's id —
    `policy_rules._episodes` treats a policy with no `id` at all as "no real Policy to
    read a field from, run the structure-only rules over every episode in the graph". A
    second, unrelated episode with its own dropped baseline proves that widening does
    not leak across episodes: its `baseline-present` finding stays out of *this*
    episode's report, which still names only ep-1.
    """
    g = complete_episode
    revise(g, "ep-1", alternatives=["alt-a", "alt-b"])  # drops the baseline
    revise(g, "ch-1", decisionClassPolicy="ev-doc")
    put_all(g, charter("ch-far"), alternative("alt-far"),
            episode("ep-far", charter="ch-far", alternatives=["alt-far"]))
    rr = readiness_report(g, "ep-1", tailoring="full-36", seed=SEED, now=NOW)
    assert rr["ready"] is False
    assert {"policy-unresolved", "baseline-present"} <= {b["rule"] for b in rr["blockers"]}
    baseline_blockers = [b for b in rr["blockers"] if b["rule"] == "baseline-present"]
    assert baseline_blockers and all(b["objects"] == ["ep-1"] for b in baseline_blockers)


def test_an_unknown_tailoring_is_refused_before_any_write(complete_episode):
    g = complete_episode
    entries = len(g.log())
    for bad in ("no-such-tailoring", "../../etc/passwd"):
        with pytest.raises(ValidationError) as exc:
            readiness_report(g, "ep-1", tailoring=bad, seed=SEED, now=NOW)
        assert bad in str(exc.value)
    assert len(g.log()) == entries


def test_no_tailoring_anywhere_is_a_named_refusal(complete_episode):
    g = complete_episode
    revise(g, "ch-1", decisionClassPolicy="pol-gone")
    with pytest.raises(ValidationError) as exc:
        readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert "tailoring" in str(exc.value)


def test_a_schema_invalid_episode_is_refused_before_any_write(complete_episode):
    """A hand-edited episode cannot carry a readiness link, so the call refuses rather
    than writing a report the episode will never point at."""
    g = complete_episode
    bad_ep = {**g.get("ep-1"), "observations": "not-a-list"}
    g._latest["ep-1"] = bad_ep
    g._history["ep-1"][bad_ep["rev"]] = bad_ep
    entries = len(g.log())

    with pytest.raises(ValidationError) as exc:
        readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert "does not validate" in str(exc.value)
    assert len(g.log()) == entries


def test_hand_edited_neighbours_do_not_crash_the_report(complete_episode):
    """The episode still validates; the objects around it have been edited into shapes
    a clean `put` would never allow. Every check reads them defensively."""
    g = complete_episode
    for oid, over in (("obj-1", {"measures": "not-a-list"}),
                      ("mdl-1", {"vvaRecord": 7}),
                      ("vva-1", {"accreditationDecision": "not-an-object"}),
                      ("bc-1", {"producedEvidence": 7}),
                      ("run-pl-1-s1", {"outputs": "not-a-list"})):
        bad = {**g.get(oid), **over}
        g._latest[oid] = bad
        g._history[oid][bad["rev"]] = bad

    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["ready"] is False
    assert any(b["rule"] == "schema" for b in rr["blockers"])
    # An unreadable field is the schema rule's finding, reported once. The readiness
    # checks skip what they cannot read rather than reporting it a second time as a
    # coverage, accreditation or bias-evidence failure.
    assert {"objective-run-coverage", "accreditation-scope",
            "bias-check-evidence-unreviewed"}.isdisjoint({b["rule"] for b in rr["blockers"]})


def test_a_dangling_bias_check_is_reported_not_dropped(complete_episode):
    g = complete_episode
    revise(g, "ep-1", biasChecks=["bc-1", "bc-gone"])
    rr = readiness_report(g, "ep-1", seed=SEED, now=NOW)
    assert rr["biasChecksStatus"] == [{"check": "bc-1", "status": "performed"},
                                      {"check": "bc-gone", "status": None}]
    assert rr["ready"] is False
