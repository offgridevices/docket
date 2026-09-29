import pytest

from docket.errors import ValidationError
from docket.kernel.mandate import score_mandate
from docket.kernel.validate import validate
from tests.kernel.conftest import episode, evidence, obj, put_all


def test_mandate_scorecard_flags_unsupported(base_graph):
    g = base_graph
    put_all(
        g,
        obj("cl-1", "Claim", text="c", questionClass="other", assessableAt={"level": "U"},
            supportedBy=[{"evidence": "ev-doc"}]),
        obj("me-1", "MandateElement", text="t", source="§234(b)(2)(A)", status="satisfied",
            satisfiedBy=["cl-1"]),
        obj("me-2", "MandateElement", text="t2", source="§234(b)(2)(B)", status="satisfied"),
        obj("me-3", "MandateElement", text="t3", source="§234(b)(2)(C)", status="not-applicable"),
        {**episode(), "rev": 2, "claims": ["cl-1"],
         "mandateElements": ["me-1", "me-2", "me-3"]},
    )
    ms = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    status = {r["element"]: r["status"] for r in ms["rows"]}
    assert status == {
        "me-1": "satisfied",
        "me-2": "asserted-unsupported",
        "me-3": "not-applicable-unreasoned",
    }
    assert ms["id"] == "ms-ep-1-1"
    assert ms["createdBy"]["actorType"] == "kernel"


@pytest.mark.parametrize(
    ("review_status", "expected"),
    [
        ("rejected", "asserted-unsupported"),
        ("draft", "asserted-unsupported"),
        ("reviewed", "satisfied"),
    ],
    ids=["rejected", "draft", "reviewed"],
)
def test_mandate_element_checks_cited_evidence_review_status(base_graph, review_status, expected):
    """A claim resting on rejected or draft evidence does not actually satisfy the
    element it's cited for, even though `supportedBy` has content — the row must not
    take the claim's word for it (fix round 1, review item 1)."""
    g = base_graph
    put_all(
        g,
        evidence("ev-cited", reviewStatus=review_status),
        obj("cl-1", "Claim", text="c", questionClass="other", assessableAt={"level": "U"},
            supportedBy=[{"evidence": "ev-cited"}]),
        obj("me-1", "MandateElement", text="t", source="s", status="satisfied",
            satisfiedBy=["cl-1"]),
        {**episode(), "rev": 2, "claims": ["cl-1"], "mandateElements": ["me-1"]},
    )
    ms = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert ms["rows"] == [{"element": "me-1", "status": expected, "satisfiedBy": ["cl-1"]}]


def test_mandate_element_satisfied_if_any_cited_claim_is_fully_supported(base_graph):
    """Only one of the addressing claims needs to be fully supported by reviewed
    evidence — a second, weaker claim citing rejected evidence does not sink the row."""
    g = base_graph
    put_all(
        g,
        evidence("ev-good", reviewStatus="reviewed"),
        evidence("ev-bad", reviewStatus="rejected"),
        obj("cl-1", "Claim", text="c1", questionClass="other", assessableAt={"level": "U"},
            supportedBy=[{"evidence": "ev-good"}]),
        obj("cl-2", "Claim", text="c2", questionClass="other", assessableAt={"level": "U"},
            supportedBy=[{"evidence": "ev-bad"}]),
        obj("me-1", "MandateElement", text="t", source="s", status="satisfied",
            satisfiedBy=["cl-1", "cl-2"]),
        {**episode(), "rev": 2, "claims": ["cl-1", "cl-2"], "mandateElements": ["me-1"]},
    )
    ms = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert ms["rows"] == [
        {"element": "me-1", "status": "satisfied", "satisfiedBy": ["cl-1", "cl-2"]}
    ]


def test_mandate_scorecard_reasoned_not_applicable(base_graph):
    g = base_graph
    put_all(
        g,
        obj("me-1", "MandateElement", text="t", source="s", status="not-applicable",
            statusReason="Volume 7 does not apply to this competition."),
        {**episode(), "rev": 2, "mandateElements": ["me-1"]},
    )
    ms = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert ms["rows"] == [{"element": "me-1", "status": "not-applicable", "satisfiedBy": []}]


def test_mandate_scorecard_ids_increment_per_episode(base_graph):
    g = base_graph
    put_all(g, {**episode(), "rev": 2, "mandateElements": []})
    first = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    second = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert first["id"] == "ms-ep-1-1"
    assert second["id"] == "ms-ep-1-2"


def test_mandate_scorecard_on_complete_graph_is_schema_valid(complete_episode):
    g = complete_episode
    ms = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert ms["rows"] == [{"element": "me-1", "status": "satisfied", "satisfiedBy": ["cl-1"]}]
    findings = validate(g)
    assert not any(f.rule == "schema" for f in findings)


def test_score_mandate_tolerates_dangling_and_malformed_ids(base_graph):
    """`put()` would itself reject a non-string mandateElements entry, but a
    hand-edited store is not guaranteed to be schema-clean — this must not raise."""
    g = base_graph
    put_all(g, {**episode(), "rev": 2, "mandateElements": ["missing-me"]})
    bad_ep = {**g.get("ep-1"), "mandateElements": ["missing-me", 42]}
    g._latest["ep-1"] = bad_ep
    g._history["ep-1"][bad_ep["rev"]] = bad_ep
    ms = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert ms["rows"] == []


def test_score_mandate_tolerates_garbage_satisfied_by(base_graph):
    g = base_graph
    put_all(
        g,
        obj("me-1", "MandateElement", text="t", source="s", status="satisfied",
            satisfiedBy=["missing-claim"]),
        {**episode(), "rev": 2, "mandateElements": ["me-1"]},
    )
    bad_me = {**g.get("me-1"), "satisfiedBy": ["missing-claim", 7]}
    g._latest["me-1"] = bad_me
    g._history["me-1"][bad_me["rev"]] = bad_me
    ms = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert ms["rows"] == [{"element": "me-1", "status": "asserted-unsupported", "satisfiedBy": []}]


def test_score_mandate_tolerates_hand_edited_episode(base_graph):
    """A hand-edited store can hold a non-list mandateElements; the scorer must not
    raise, only see nothing to score."""
    g = base_graph
    bad_ep = {**g.get("ep-1"), "mandateElements": "not-a-list"}
    g._latest["ep-1"] = bad_ep
    g._history["ep-1"][bad_ep["rev"]] = bad_ep
    ms = score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert ms["rows"] == []


def test_score_mandate_refuses_to_write_a_row_with_no_status(base_graph):
    """A hand-edited MandateElement missing `status` cannot produce a schema-valid row
    (`status` is a required string): reading it must not raise a KeyError, but writing
    the resulting scorecard is refused by validate-then-write rather than inventing a
    status or silently dropping the row."""
    g = base_graph
    put_all(
        g,
        obj("me-1", "MandateElement", text="t", source="s", status="satisfied"),
        {**episode(), "rev": 2, "mandateElements": ["me-1"]},
    )
    bad_me = {**g.get("me-1")}
    bad_me.pop("status", None)
    g._latest["me-1"] = bad_me
    g._history["me-1"][bad_me["rev"]] = bad_me
    with pytest.raises(ValidationError):
        score_mandate(g, "ep-1", now="2026-09-04T00:00:00Z")
