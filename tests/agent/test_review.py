"""Gate G1 — the review sheet, and the three actions a human takes at it.

No backend call is made by anything under test here: `RecordedBackend` builds the DRAFT
episode that is *reviewed*, and every assertion afterwards is about the graph.
"""

import json
import re
from pathlib import Path

import pytest

from docket.agent.backend import RecordedBackend
from docket.agent.elicit import elicit_into
from docket.agent.review import (
    NUMERALS_IN_FIXED_PROSE,
    RATING_RELEVANT_HEADING,
    RATING_RELEVANT_LINE,
    accept,
    confirm_gaps,
    g1_review,
    g1_sheet,
    reject,
)
from docket.errors import AuthorityViolation, TransitionRefused, ValidationError
from docket.kernel.lifecycle import CHECKS, transition
from docket.kernel.validate import validate
from docket.objects import is_content
from docket.store import Graph
from tests.kernel.conftest import (
    H,
    alternative,
    drs,
    episode,
    evidence,
    measure,
    obj,
    objective,
    policy,
)

A = {"actorType": "agent", "actorId": "agent:recorded"}
NOW = "2026-09-04T00:00:00Z"
SRC = "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md"
EP = "ep-omfv-con"


@pytest.fixture
def draft():
    """The DRAFT episode Task 3's mapper produces, and its graph.

    The episode id is the one *passed in*, and every other id is read back out of the
    graph — Task 3 is free to change its own id shapes (it is doing exactly that in its
    fix round) without breaking G1, because G1 walks references and never spells an id.
    """
    g = Graph()
    g.put(policy(), H)
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    elicit_into(g, b,
                request_text=Path("tests/fixtures/requests/omfv-con-2020-02-25.md").read_text(),
                policy_id="pol-1", actor=A, now=NOW, source_artifact=SRC,
                requested_by="NGCV CFT", episode_id=EP)
    return g, g.get(EP)


# ---- the sheet -----------------------------------------------------------------------


def test_sheet_shows_every_gap_and_explains_every_inference(draft):
    g, ep = draft
    review = g1_review(g, ep["id"])
    sheet = g1_sheet(g, ep["id"])
    assert review["gaps"], "the fixture has at least one gap"
    for gap in review["gaps"]:
        assert gap["sought"] in sheet
        assert gap["whyNotFound"] in sheet
        assert all(w in sheet for w in gap["whereLookedFor"])
    assert "inferred by" in sheet
    # [ruling R16] the rating-relevant section, named as such
    assert RATING_RELEVANT_LINE in sheet
    assert "these change how the record is scored" in sheet
    assert RATING_RELEVANT_HEADING in sheet
    assert any(r["field"] == "priorityRank" for r in review["ratingRelevant"])
    assert any(r["field"] == "baselineFlag" for r in review["ratingRelevant"]) or \
        not [o for o in review["objects"] if o["type"] == "Alternative"]


def test_rating_relevant_names_the_citation_the_model_wrote_itself():
    """A model-written `pointer` is the one place a model string becomes a citation.

    It is not scored, and the section says so per row; it is listed beside `priorityRank`
    and `baselineFlag` because a URI and a custodian nobody checked read exactly like a
    source that was consulted. The source-artifact entry is *not* listed: its pointer is
    the caller's own argument, not something a model wrote.
    """
    g = Graph()
    g.put(policy(), H)
    prov = {"sourceArtifact": SRC, "locator": "p. 9", "extractor": "recorded:recorded",
            "extractedAt": NOW}
    common = dict(evidenceType="Document", publisher="p", published="2020",
                  classification={"level": "U", "metadataLevel": "U"},
                  scopeOfValidity={"builtToAnswer": "q", "questionClass": "other",
                                   "intendedUse": "u"},
                  reviewStatus="draft", reliabilitySteps=["drs-1"],
                  ingestionProvenance=prov, confidence="inferred")
    g.put({**obj("ev-src", "Evidence", title="the source", **common),
           "createdBy": A, "pointer": {"uri": SRC, "custodian": "docket repository"}}, A)
    g.put({**obj("ev-cited", "Evidence", title="a study the model named", **common),
           "createdBy": A,
           "pointer": {"uri": "https://example.invalid/study.pdf", "custodian": "TRADOC"}}, A)
    g.put(obj("drs-1", "DataReliabilityStep", description="d", method="source-review",
              performedBy="x", documentation="ev-src"), H)
    g.put(obj("ch-1", "Charter", question="q", decisionToBeMade="d",
              consequencesOfErroneousOutput="c", questionClass="other",
              scope={"included": ["a"], "excluded": []}, authority={"signer": "s"},
              decisionClassPolicy="pol-1"), H)
    g.put(episode("ep-1", evidenceRegister=["ev-src", "ev-cited"]), H)

    entries = {(r["objectId"], r["field"]): r for r in g1_review(g, "ep-1")["ratingRelevant"]}
    assert ("ev-cited", "pointer") in entries
    assert ("ev-src", "pointer") not in entries, "the source pointer is the caller's own"
    citation = entries[("ev-cited", "pointer")]
    assert citation["kind"] == "citation"
    assert citation["value"] == {"uri": "https://example.invalid/study.pdf",
                                 "custodian": "TRADOC"}
    sheet = g1_sheet(g, "ep-1")
    assert "https://example.invalid/study.pdf" in sheet
    assert RATING_RELEVANT_HEADING in sheet


def test_a_human_accepted_value_leaves_the_rating_relevant_list(draft):
    """Once a human owns the ordering it is the human's, not something still to review."""
    g, ep = draft
    oid = g.get(ep["id"])["objectives"][0]
    assert any(r["objectId"] == oid for r in g1_review(g, ep["id"])["ratingRelevant"])
    accept(g, oid, H, now=NOW)
    assert not any(r["objectId"] == oid for r in g1_review(g, ep["id"])["ratingRelevant"])


def test_checklist_is_read_from_the_gate_not_restated(draft):
    g, ep = draft
    checks = g1_review(g, ep["id"])["checks"]
    names = [c["name"] for c in checks]
    assert names == [n for n, _ in CHECKS["MODEL_APPROVED"]]
    # [ruling R13] already implemented in lifecycle.py — this is the reference, not a re-impl
    assert "charter-human-accepted" in names
    # every check says what would satisfy it, and says it in the gate's own words
    for check, (_, fn) in zip(checks, CHECKS["MODEL_APPROVED"], strict=True):
        assert check["whatWouldSatisfy"]
        assert check["whatWouldSatisfy"] in (fn.__doc__ or check["whatWouldSatisfy"])
    sheet = g1_sheet(g, ep["id"])
    for check in checks:
        assert f"[{'x' if check['satisfied'] else ' '}] {check['name']}" in sheet


def test_the_sheet_never_prints_a_number_the_graph_does_not_hold(draft):
    """Nothing on this sheet is computed. Every numeral is copied or is fixed prose.

    [M3] Token matching, not substring: `"4"` used to pass only because it occurs inside
    `"5000.84"`, which would have let a genuinely invented `4` through.

    [M4] Known limit of this guard: with the OMFV record in the allowlist, every single
    digit and many two-digit numbers occur *somewhere* in the JSON, so an invented small
    count ("6 of 9 objectives are primary") would still pass. The guard is tight where it
    matters — a score, a rating, a weight, none of which is a small integer that happens to
    be lying around in the record — and loose where it does not. It is a tripwire against
    the sheet growing arithmetic, not a proof that it has none.
    """
    g, ep = draft
    sheet = g1_sheet(g, ep["id"])
    from_graph = json.dumps([g.get(i) for i in sorted({ep["id"]} | g.reachable_from(ep["id"],
                                                                                    reverse=False))])
    allowed = set(re.findall(r"\d+", from_graph)) | set(NUMERALS_IN_FIXED_PROSE)
    for numeral in set(re.findall(r"\d+", sheet)):
        assert numeral in allowed, f"{numeral!r} appears on the sheet but not in the record"


def test_the_numeral_allowlist_follows_the_gate_docstrings(draft):
    """[M3] A check added in 03b citing a numbered instruction must not break the guard."""
    assert "4" in NUMERALS_IN_FIXED_PROSE          # AR 5-11 ¶4-5b, in the sheet's header
    from_checks = {n for _, c in CHECKS["MODEL_APPROVED"]
                   for n in re.findall(r"\d+", c.__doc__ or "")}
    assert from_checks <= set(NUMERALS_IN_FIXED_PROSE)


def test_review_carries_the_review_dialog_fields_for_every_object(draft):
    """Frontend spec §4: what · why · source · if it is wrong · what you can do · what
    happens to the record. Every item must answer all six before a human clicks."""
    g, ep = draft
    review = g1_review(g, ep["id"])
    assert review["episode"] == ep["id"]
    assert review["lifecycleState"] == "DRAFT"
    for item in review["objects"]:
        assert item["summary"]                       # WHAT
        assert item["explanation"]                   # WHY THE MODEL PROPOSED IT
        assert "locator" in item and "sourceArtifact" in item and "extractor" in item  # SOURCE
        assert set(item["ifWrong"]) == {"statement", "indicators"}                    # IF WRONG
        assert isinstance(item["actions"], list)                                      # CAN DO
        assert set(item["recordEffect"]) == set(item["actions"])       # HAPPENS TO THE RECORD
        assert item["authorType"] in ("agent", "human", "kernel", None)
    charter = next(o for o in review["objects"] if o["type"] == "Charter")
    assert charter["explanation"].startswith(
        ("inferred by", "quoted by", "at least one field was not found by"))
    assert charter["extractor"] in charter["explanation"]
    # the episode itself is on the sheet, and is not accept/reject-able
    ep_item = next(o for o in review["objects"] if o["type"] == "DecisionEpisode")
    assert ep_item["actions"] == []


def test_gaps_say_where_they_hang_and_the_sheet_is_deterministic(draft):
    g, ep = draft
    review = g1_review(g, ep["id"])
    attached = [a for gap in review["gaps"] for a in gap["attachedTo"]]
    assert attached, "at least one gap hangs off a named slot"
    for ref in attached:
        oid, _, path = ref.partition("/")
        assert g.has(oid) and path
    assert g1_review(g, ep["id"]) == review
    assert g1_sheet(g, ep["id"]) == g1_sheet(g, ep["id"])


def test_the_sheet_renders_over_a_store_this_process_did_not_write():
    """A dangling ref, a missing episode field, a marker pointing at nothing: no traceback."""
    g = Graph()
    g.put(policy(), H)
    g.put(obj("gap-x", "InsufficientEvidence", sought="s", whereLookedFor=["w"],
              whyNotFound="n", impact="degrading", indicatorsThatWouldResolve=[]), H)
    g.put(obj("ch-x", "Charter", question={"$gap": "gap-x"}, decisionToBeMade="d",
              consequencesOfErroneousOutput="c", questionClass="other",
              scope={"included": [], "excluded": []}, authority={"signer": "s"},
              decisionClassPolicy="pol-1"), H)
    g.put(episode("ep-x", charter="ch-x"), H)
    review = g1_review(g, "ep-x")
    assert review["ready"] is False
    assert g1_sheet(g, "ep-x")
    # an episode that is not there at all is a named refusal, not an AttributeError
    with pytest.raises(ValidationError):
        g1_review(g, "ep-nope")


# ---- C1: the gap that hangs off nothing ------------------------------------------------


def _orphan_gap(g, gid="ep-omfv-con-gap-99"):
    """An `InsufficientEvidence` nothing references, shaped exactly as the elicitation
    mapper's `_emit_unattached_gaps` writes one: the model reported looking for something
    and routed it to a field name that matched nothing, so the owner text lands in
    `whyNotFound` and no object can point at the result."""
    g.put({
        "id": gid, "type": "InsufficientEvidence", "rev": 1, "createdBy": A,
        "createdAt": NOW,
        "ingestionProvenance": {"sourceArtifact": SRC, "locator": "",
                                "extractor": "recorded:recorded", "extractedAt": NOW},
        "sought": "the funding line for the programme",
        "whereLookedFor": ["notice body"],
        "whyNotFound": ("the notice is silent on funding (model routed this to "
                        "'charter.thisFieldDoesNotExist', which matched no field)"),
        "impact": "degrading", "indicatorsThatWouldResolve": [],
    }, A)
    return gid


def test_an_unattached_gap_reaches_the_sheet_the_gate_and_the_validator(draft):
    """[C1] The reviewer's probe. A gap the model recorded but could not route to a field
    used to fall out of the sheet, out of `confirm_gaps` and out of the gate at once — so
    the record was signed asserting every gap was confirmed by a human who was never
    shown one. It is an omission nobody can attribute, which makes it everybody's."""
    g, ep = draft
    gid = _orphan_gap(g)
    assert g.refs_to(gid) == [], "the premise: nothing in the record points at it"

    review = g1_review(g, ep["id"])
    entry = next(x for x in review["gaps"] if x["id"] == gid)
    assert entry["attached"] is False
    assert entry["attachedTo"] == []

    sheet = g1_sheet(g, ep["id"])
    assert "## Unattached gaps" in sheet
    assert entry["sought"] in sheet
    assert "charter.thisFieldDoesNotExist" in sheet, "the owner the model aimed it at"

    # the gate: unsatisfied until it is signed, then satisfied
    assert not next(c for c in review["checks"] if c["name"] == "gaps-confirmed")["satisfied"]
    with pytest.raises(TransitionRefused) as exc:
        transition(g, ep["id"], "MODEL_APPROVED", H, now=NOW)
    assert "gaps-confirmed" in exc.value.unsatisfied

    # the validator names it
    named = [f for f in validate(g, g.get("pol-1")) if gid in f.objects]
    assert [f.rule for f in named] == ["gap-unconfirmed"]

    assert gid in confirm_gaps(g, ep["id"], H, now=NOW)
    assert g.get(gid)["confirmedBy"] == {"actorId": "fixture", "date": NOW}
    after = g1_review(g, ep["id"])
    assert next(c for c in after["checks"] if c["name"] == "gaps-confirmed")["satisfied"]
    assert [f for f in validate(g, g.get("pol-1")) if gid in f.objects] == []


def test_an_unattached_gap_holds_the_gate_shut_all_the_way_to_the_end(draft):
    """The same gap, on the full walk: G1 will not open while it is unsigned."""
    g, ep = draft
    _orphan_gap(g)
    accept(g, g.get(ep["id"])["charter"], H, now=NOW,
           consequencesOfErroneousOutput="industry designs to the wrong characteristics")
    for aid in g.get(ep["id"])["assumptions"]:
        if g.get(aid)["linchpin"]:
            accept(g, aid, H, now=NOW)
    with pytest.raises(TransitionRefused) as exc:
        transition(g, ep["id"], "MODEL_APPROVED", H, now=NOW)
    assert exc.value.unsatisfied == ["gaps-confirmed"]
    confirm_gaps(g, ep["id"], H, now=NOW)
    assert transition(g, ep["id"], "MODEL_APPROVED", H,
                      now=NOW)["lifecycleState"] == "MODEL_APPROVED"


# ---- I2 / I4: what the sheet offers, and what it prints ---------------------------------


def _mixed_graph():
    """One episode carrying the object types the six named sections do not cover."""
    g = Graph()
    g.put(policy(), H)
    g.put(evidence("ev-doc"), H)
    g.put(drs(), H)
    g.put(obj("ch-1", "Charter", question="q", decisionToBeMade="d",
              consequencesOfErroneousOutput="c", questionClass="other",
              scope={"included": ["a"], "excluded": []}, authority={"signer": "s"},
              decisionClassPolicy="pol-1"), H)
    g.put(objective("obj-1", measures=["m-1"]), H)
    g.put(measure("m-1", "obj-1"), H)
    g.put(obj("sc-1", "Scenario", name="cold start", description="d", rationale="r",
              conditions=["c"], source="ev-doc"), H)
    g.put(episode("ep-1", objectives=["obj-1"], scenarios=["sc-1"],
                  evidenceRegister=["ev-doc"]), H)
    return g


def test_reject_is_offered_only_where_it_would_do_something():
    """[I2] A button that writes an Exclusion and changes nothing is worse than no button:
    the store ends up asserting an object was excluded while it is still in force."""
    g = _mixed_graph()
    offered = {o["id"]: o["actions"] for o in g1_review(g, "ep-1")["objects"]}
    assert "reject" not in offered["pol-1"], "governance is not part of the model reviewed"
    assert offered["pol-1"] == []
    assert "reject" not in offered["drs-1"], "no episode list holds a reliability step"
    assert "reject" in offered["obj-1"] and "reject" in offered["sc-1"]
    assert "reject" in offered["ev-doc"], "Evidence has a dedicated path"
    # the Measure keeps its button, and the promise attached to it tells the truth
    assert "reject" in offered["m-1"]
    promise = next(o for o in g1_review(g, "ep-1")["objects"]
                   if o["id"] == "m-1")["recordEffect"]["reject"]
    assert "objective will still list this measure" in promise
    assert "objective_measured" in promise and "accept(objective, measures=" in promise
    # and where nothing is dropped, the promise says so rather than claiming a removal
    assert "Nothing is dropped" in promise or "still list" in promise


def test_reject_refuses_by_name_the_types_it_must_not_touch():
    """[I2] Policy and a gap, each with the remedy in the message."""
    g = _mixed_graph()
    gid = _orphan_gap(g, "gap-x")
    with pytest.raises(ValidationError, match="yardstick"):
        reject(g, "pol-1", H, now=NOW, reason="r")
    with pytest.raises(ValidationError, match="confirm_gaps"):
        reject(g, gid, H, now=NOW, reason="r")
    assert not [x for x in g.all("Exclusion")], "refused before any write"


def test_the_sheet_prints_every_object_it_built():
    """[I4] A review sheet with an undeclared omission in it is the failure this product
    argues against, so nothing may be built into `objects[]` and then not rendered."""
    g = _mixed_graph()
    review = g1_review(g, "ep-1")
    sheet = g1_sheet(g, "ep-1")
    assert "## Other objects in this record" in sheet
    for item in review["objects"]:
        if item["type"] in ("DecisionEpisode", "InsufficientEvidence"):
            continue
        assert item["id"] in sheet, f"{item['id']} was built but never printed"
    assert "pol-1" in sheet and "m-1" in sheet and "sc-1" in sheet and "drs-1" in sheet


def test_the_rejected_measure_note_is_on_the_exclusion_row():
    """[I1] Ruling (2): the sheet, not a test docstring, tells the reviewer."""
    g = _mixed_graph()
    reject(g, "m-1", H, now=NOW, reason="the metric is not observable on any alternative")
    sheet = g1_sheet(g, "ep-1")
    assert "the objective still lists this measure" in sheet
    assert "objective_measured" in sheet
    assert g.get("obj-1")["measures"] == ["m-1"]
    assert validate(g) == []


# ---- I3: the kernel can see the exclusions this module writes ---------------------------


def test_an_exclusion_written_at_g1_stays_visible_to_the_policy_rules(draft):
    """[I3] Dropping the id from the episode is what makes the rejection real — and it is
    also what used to hide the Exclusion from every rule that reads exclusions. A
    prohibited reason on a Category rejection validated clean."""
    g, ep = draft
    oid = g.get(ep["id"])["objectives"][-1]
    x = reject(g, oid, H, now=NOW, reason="no time to model it",
               reason_type="data-unavailable")
    assert oid not in g.get(ep["id"])["objectives"], "the id really did leave the episode"
    findings = validate(g, g.get("pol-1"))
    # the rule can see it: swap the stored reason for a prohibited one and it fires
    assert not [f for f in findings if f.rule == "exclusion-prohibited-reason"]
    g.put({**g.get(x["id"]), "rev": 2, "createdBy": H, "createdAt": NOW,
           "reasonType": "time-or-resource"}, H)
    fired = [f for f in validate(g, g.get("pol-1"))
             if f.rule == "exclusion-prohibited-reason"]
    assert [f.severity for f in fired] == ["blocking"]
    assert fired[0].objects == (x["id"],)


# ---- I5 / I6 / M1 / M2 ------------------------------------------------------------------


def test_reject_refuses_a_reason_the_governing_policy_prohibits(draft):
    """[I5] `other` is a bias *indicator*; `time-or-resource` is a **blocking** finding
    under the default policy. Guarding the softer failure and waving through the harder
    one was the wrong way round."""
    g, ep = draft
    oid = g.get(ep["id"])["objectives"][0]
    with pytest.raises(ValidationError, match="prohibited by policy"):
        reject(g, oid, H, now=NOW, reason="ran out of time", reason_type="time-or-resource")
    assert not [x for x in g.all("Exclusion")]
    # a reason the policy allows still works
    assert reject(g, oid, H, now=NOW, reason="belongs to the STE programme")["reasonType"] \
        == "out-of-scope"


def test_reject_will_not_strip_a_shared_object_out_of_a_second_episode():
    """[I6] Episode B must not lose an objective at episode A's gate, under a reason
    written about A."""
    g = Graph()
    g.put(policy(), H)
    g.put(evidence("ev-doc"), H)
    g.put(drs(), H)
    g.put(obj("ch-1", "Charter", question="q", decisionToBeMade="d",
              consequencesOfErroneousOutput="c", questionClass="other",
              scope={"included": ["a"], "excluded": []}, authority={"signer": "s"},
              decisionClassPolicy="pol-1"), H)
    g.put(objective("obj-1"), H)
    g.put(episode("ep-a", objectives=["obj-1"]), H)
    g.put(episode("ep-b", objectives=["obj-1"], sequence=2), H)

    with pytest.raises(ValidationError, match="more than one episode"):
        reject(g, "obj-1", H, now=NOW, reason="out of scope for episode A")
    assert g.get("ep-b")["objectives"] == ["obj-1"], "refused before any write"

    with pytest.raises(ValidationError, match="does not hold"):
        reject(g, "obj-1", H, now=NOW, reason="r", episode_id="ep-nope")

    x = reject(g, "obj-1", H, now=NOW, reason="out of scope for episode A",
               episode_id="ep-a")
    assert g.get("ep-a")["objectives"] == []
    assert g.get("ep-b")["objectives"] == ["obj-1"]
    assert x["$episodesTouched"] == ["ep-a"]
    # the pre-click promise named the sharing before the click
    effect = next(o for o in g1_review(g, "ep-b")["objects"]
                  if o["id"] == "obj-1")["recordEffect"]["reject"]
    assert "ep-b" in effect
    assert validate(g) == []


def test_the_returned_episodes_touched_key_is_not_a_stored_field():
    g = _mixed_graph()
    x = reject(g, "sc-1", H, now=NOW, reason="not reachable in the planning horizon")
    assert x["$episodesTouched"] == ["ep-1"]
    assert "$episodesTouched" not in g.get(x["id"])


def test_an_unsigned_human_actor_is_refused(draft):
    """[M1] G1 records *who* accepted the model; an approval nobody signed is not one."""
    g, ep = draft
    unsigned = {"actorType": "human"}
    before = g.snapshot_hash()
    for call in (lambda: confirm_gaps(g, ep["id"], unsigned, now=NOW),
                 lambda: accept(g, ep["charter"], unsigned, now=NOW, question="q"),
                 lambda: reject(g, g.get(ep["id"])["objectives"][0], unsigned, now=NOW,
                                reason="r")):
        with pytest.raises(AuthorityViolation, match="actorId"):
            call()
    assert g.snapshot_hash() == before


def test_a_second_reject_says_who_already_rejected_it(draft):
    """[M2] A double-click deserves a sentence, not the store's append-only arithmetic."""
    g, ep = draft
    oid = g.get(ep["id"])["objectives"][-1]
    reject(g, oid, H, now=NOW, reason="belongs to the STE programme")
    with pytest.raises(ValidationError, match="already rejected by fixture"):
        reject(g, oid, H, now=NOW, reason="belongs to the STE programme")


# ---- the gate ------------------------------------------------------------------------


def test_g1_is_refused_before_the_human_acts_and_passes_after(draft):
    g, ep = draft
    with pytest.raises(TransitionRefused) as exc:
        transition(g, ep["id"], "MODEL_APPROVED", H, now=NOW)
    unsatisfied = set(exc.value.unsatisfied)
    assert {"gaps-confirmed", "linchpins-human", "charter-human-accepted"} <= unsatisfied
    assert g.get(ep["id"])["lifecycleState"] == "DRAFT"
    assert g.get(ep["id"])["transitions"][-1]["refused"] is True   # the refusal is recorded

    confirm_gaps(g, ep["id"], H, now=NOW)
    accept(g, g.get(ep["id"])["charter"], H, now=NOW,
           consequencesOfErroneousOutput="Industry designs to the wrong characteristics and "
                                         "the Army buys a vehicle that cannot cross the "
                                         "bridges it must cross")
    for aid in g.get(ep["id"])["assumptions"]:
        if g.get(aid)["linchpin"]:
            accept(g, aid, H, now=NOW)

    ep2 = transition(g, ep["id"], "MODEL_APPROVED", H, now=NOW)
    assert ep2["lifecycleState"] == "MODEL_APPROVED"
    assert g1_review(g, ep["id"])["ready"] is True
    assert validate(g) == []


# ---- accept --------------------------------------------------------------------------


def test_accept_drops_the_model_confidence_and_keeps_provenance(draft):
    g, ep = draft
    ch = g.get(ep["charter"])
    out = accept(g, ch["id"], H, now=NOW, question="What characteristics should the OMFV have?")
    assert out["createdBy"] == H and "confidence" not in out
    assert out["ingestionProvenance"] == ch["ingestionProvenance"]
    assert out["rev"] == ch["rev"] + 1
    assert validate(g) == []
    # the caller may keep the annotation deliberately, and then it is kept
    kept = accept(g, ch["id"], H, now=NOW, confidence="inferred")
    assert kept["confidence"] == "inferred"


def test_accept_changes_only_what_the_caller_named(draft):
    g, ep = draft
    before = g.get(ep["charter"])
    after = accept(g, before["id"], H, now="2026-09-05T09:00:00Z", question="Q")
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed == {"question", "rev", "createdBy", "createdAt", "confidence"}


# ---- confirm_gaps --------------------------------------------------------------------


def test_confirm_gaps_is_idempotent_and_returns_what_it_signed(draft):
    g, ep = draft
    first = confirm_gaps(g, ep["id"], H, now=NOW)
    assert first == sorted(first) and first
    for gid in first:
        assert g.get(gid)["confirmedBy"] == {"actorId": "fixture", "date": NOW}
        assert g.get(gid)["createdBy"] == H
    assert confirm_gaps(g, ep["id"], H, now=NOW) == []
    assert validate(g) == []


# ---- reject --------------------------------------------------------------------------


def test_reject_records_a_typed_exclusion_not_a_deletion(draft):
    g, ep = draft
    obj_id = g.get(ep["id"])["objectives"][-1]
    x = reject(g, obj_id, H, now=NOW, reason="not a vehicle characteristic; belongs to the "
                                             "STE programme")
    assert x["type"] == "Exclusion" and x["id"] == f"ex-reject-{obj_id}"
    # [ruling R15] no enum member fits an Objective, so Category carries the type in label
    assert x["target"] == {"kind": "Category", "id": obj_id,
                           "label": x["target"]["label"]}
    assert x["target"]["label"].startswith("Objective:")
    assert x["reasonType"] == "out-of-scope"        # never "other": bias.py flags "other"
    assert x["authority"] == {"who": "fixture", "role": "reviewer", "date": NOW}
    assert x["retainedInStructure"] is True
    assert obj_id not in g.get(ep["id"])["objectives"]
    assert g.has(obj_id), "rejection is an omission with a reason, never a deletion"
    assert validate(g) == []
    # and the omission is still on the sheet after the object leaves the episode
    review = g1_review(g, ep["id"])
    assert x["id"] in [e["id"] for e in review["exclusions"]]
    assert x["target"]["label"] in g1_sheet(g, ep["id"])


def test_reject_evidence_keeps_it_in_the_register_and_excludes_it(draft):
    g, ep = draft
    ev_id = g.get(ep["id"])["evidenceRegister"][0]
    x = reject(g, ev_id, H, now=NOW, reason="superseded by the December 2020 industry day "
                                            "briefing")
    assert g.get(ev_id)["reviewStatus"] == "rejected"
    assert ev_id in g.get(ep["id"])["evidenceRegister"]
    assert x["target"]["kind"] == "Evidence" and x["target"]["id"] == ev_id
    assert validate(g) == []


def test_reject_an_alternative_screens_it_out_with_a_reason():
    g = Graph()
    g.put(policy(), H)
    g.put(obj("ch-1", "Charter", question="q", decisionToBeMade="d",
              consequencesOfErroneousOutput="c", questionClass="other",
              scope={"included": ["a"], "excluded": []}, authority={"signer": "s"},
              decisionClassPolicy="pol-1"), H)
    g.put(alternative("alt-a", baseline=True, status="candidate"), H)
    g.put(episode("ep-1", alternatives=["alt-a"]), H)
    x = reject(g, "alt-a", H, now=NOW, reason="cannot meet the transportability floor")
    alt = g.get("alt-a")
    assert alt["status"] == "screened-out"
    assert alt["statusReason"] == x["id"]      # policy_rules.alternative_status_unreasoned
    assert x["target"] == {"kind": "Alternative", "id": "alt-a", "label": "alt-a"}
    assert "alt-a" in g.get("ep-1")["alternatives"], "an alternative never vanishes"
    assert validate(g) == []


def test_reject_a_scenario_uses_its_own_enum_member_and_leaves_the_episode_list():
    g = Graph()
    g.put(policy(), H)
    g.put(evidence("ev-doc"), H)
    g.put(drs(), H)
    g.put(obj("ch-1", "Charter", question="q", decisionToBeMade="d",
              consequencesOfErroneousOutput="c", questionClass="other",
              scope={"included": ["a"], "excluded": []}, authority={"signer": "s"},
              decisionClassPolicy="pol-1"), H)
    g.put(obj("sc-1", "Scenario", name="cold start", description="d", rationale="r",
              conditions=["c"], source="ev-doc"), H)
    g.put(episode("ep-1", scenarios=["sc-1"]), H)
    x = reject(g, "sc-1", H, now=NOW, reason="not reachable in the planning horizon")
    assert x["target"]["kind"] == "Scenario"
    assert g.get("ep-1")["scenarios"] == []
    assert g.has("sc-1")
    assert validate(g) == []


def test_reject_a_measure_records_the_exclusion_but_cannot_unhook_it_from_its_objective():
    """A Measure hangs off `Objective.measures`, not off any episode list.

    So `reject` writes the Exclusion — the omission is recorded and shows on the sheet —
    but the objective still lists the measure. Pinned here deliberately rather than fixed
    silently: unhooking it would mean this module editing a third object the human never
    named, and a cascading edit nobody asked for is worse than a limitation nobody hid.
    """
    g = Graph()
    g.put(policy(), H)
    g.put(evidence("ev-doc"), H)
    g.put(drs(), H)
    g.put(obj("ch-1", "Charter", question="q", decisionToBeMade="d",
              consequencesOfErroneousOutput="c", questionClass="other",
              scope={"included": ["a"], "excluded": []}, authority={"signer": "s"},
              decisionClassPolicy="pol-1"), H)
    g.put(objective("obj-1", measures=["m-1"]), H)
    g.put(measure("m-1", "obj-1"), H)
    g.put(episode("ep-1", objectives=["obj-1"]), H)
    x = reject(g, "m-1", H, now=NOW, reason="the metric is not observable on any alternative")
    assert x["target"]["kind"] == "Measure"
    assert g.get("obj-1")["measures"] == ["m-1"], "known limitation, recorded not hidden"
    assert x["id"] in [e["id"] for e in g1_review(g, "ep-1")["exclusions"]]
    assert validate(g) == []


def test_reject_refuses_the_reason_types_that_would_be_a_finding_against_us(draft):
    g, ep = draft
    oid = g.get(ep["id"])["objectives"][0]
    with pytest.raises(ValidationError, match="bias"):
        reject(g, oid, H, now=NOW, reason="r", reason_type="other")
    with pytest.raises(ValidationError, match="not an Exclusion reasonType"):
        reject(g, oid, H, now=NOW, reason="r", reason_type="because-i-said-so")
    with pytest.raises(ValidationError, match="reason"):
        reject(g, oid, H, now=NOW, reason="   ")


def test_reject_refuses_the_two_objects_an_episode_cannot_lose(draft):
    g, ep = draft
    for oid in (ep["id"], g.get(ep["id"])["charter"]):
        with pytest.raises(ValidationError, match="accept|VOID"):
            reject(g, oid, H, now=NOW, reason="r")


# ---- the authority boundary ----------------------------------------------------------


def test_the_human_actions_refuse_an_agent_actor(draft):
    g, ep = draft
    before = g.snapshot_hash()
    for call in (lambda: confirm_gaps(g, ep["id"], A, now=NOW),
                 lambda: accept(g, ep["charter"], A, now=NOW, question="q"),
                 lambda: reject(g, g.get(ep["id"])["objectives"][0], A, now=NOW, reason="r")):
        with pytest.raises(AuthorityViolation):
            call()
    assert g.snapshot_hash() == before, "refused before any write, not three frames down"


def test_the_human_actions_refuse_a_kernel_actor_and_a_malformed_one(draft):
    g, ep = draft
    for bad in ({"actorType": "kernel", "actorId": "kernel"}, {}, None, "human"):
        with pytest.raises(AuthorityViolation):
            confirm_gaps(g, ep["id"], bad, now=NOW)


def test_confirm_gaps_signs_only_this_episodes_own_orphans(draft):
    """[R1] An orphan gap is shown at every episode's gate, but a reviewer may sign only
    the ones their own episode's elicitation minted (id prefixed with the episode id).
    Another episode's omission is not theirs to confirm."""
    g, ep = draft
    own = _orphan_gap(g, gid=f"{ep['id']}-gap-98")
    foreign = _orphan_gap(g, gid="ep-somewhere-else-gap-1")
    sheet_ids = {gap["id"] for gap in g1_review(g, ep["id"])["gaps"]}
    assert {own, foreign} <= sheet_ids
    foreign_row = next(gap for gap in g1_review(g, ep["id"])["gaps"] if gap["id"] == foreign)
    assert foreign_row["confirmableHere"] is False
    assert "not this episode's to confirm" in g1_sheet(g, ep["id"])
    signed = confirm_gaps(g, ep["id"], H, now=NOW)
    assert own in signed and foreign not in signed
    assert not is_content(g.get(foreign).get("confirmedBy"))


def test_reject_of_a_measure_honours_the_governing_policy():
    """[R2] A Measure hangs off an Objective, not an episode; the policy guard must still
    find the governing policy by walking up, or the prohibited-reason check is inert on
    exactly the type the Measure note is about."""
    g = _mixed_graph()
    with pytest.raises(ValidationError, match="prohibited by policy"):
        reject(g, "m-1", H, now=NOW, reason="ran out of time", reason_type="time-or-resource")
    assert not [x for x in g.all("Exclusion")]
