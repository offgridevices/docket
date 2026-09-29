from docket.kernel.bias import bias_indicators
from docket.kernel.standards import score_standards
from docket.kernel.validate import validate
from tests.kernel.conftest import alternative, episode, evidence, obj, put_all


def test_over_specification_and_selection_indicators(base_graph):
    g = base_graph
    put_all(
        g,
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1", "m-2"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="x",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 1}),
        obj("m-2", "Measure", objective="obj-1", task="t", attribute="a", measure="y",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 2}),
        obj("ex-o", "Exclusion", target={"kind": "Study", "label": "s"}, reasonType="other",
            reason="r", authority={"who": "w", "role": "r", "date": "2023"},
            retainedInStructure=True),
        {**episode(), "rev": 2, "objectives": ["obj-1"]},
    )
    risks = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    kinds = {r["kind"] for r in risks}
    assert {"bias-over-specification", "bias-selection"} <= kinds
    assert set(g.get("ep-1")["risks"]) == {r["id"] for r in risks}
    assert all(r["owner"] == "unassigned" and r["status"] == "open" for r in risks)


def test_over_specification_does_not_fire_when_objective_level_criteria_present(base_graph):
    """Design §7.6 is thresholds *vs* objectives-level criteria: a measure that states
    both is the doctrinally normal case (OAS Table 5-2), not an over-specified one."""
    g = base_graph
    put_all(
        g,
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1", "m-2"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="x",
            metric={"units": "u", "direction": "max"},
            criteria={"threshold": 50, "objective": 80}),
        obj("m-2", "Measure", objective="obj-1", task="t", attribute="a", measure="y",
            metric={"units": "u", "direction": "max"},
            criteria={"threshold": 60, "objective": 35}),
        {**episode(), "rev": 2, "objectives": ["obj-1"]},
    )
    risks = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert "bias-over-specification" not in {r["kind"] for r in risks}


def test_over_specification_requires_at_least_two_measures(base_graph):
    g = base_graph
    put_all(
        g,
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="x",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 50}),
        {**episode(), "rev": 2, "objectives": ["obj-1"]},
    )
    risks = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert "bias-over-specification" not in {r["kind"] for r in risks}


def test_over_specification_stays_silent_and_des14_stays_1_on_complete_graph(complete_episode):
    """The repo's own "no concerns" reference fixture must not trip any indicator, and
    in particular must not knock DES-14 down to state 2 (fix round 1, review item 2)."""
    g = complete_episode
    risks = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert risks == []
    sa = score_standards(g, "ep-1", "full-36", k=1, now="2026-09-04T00:00:00Z")
    states = {r["questionId"]: r["state"] for r in sa["ratings"]}
    assert states["DES-14"] == 1


def test_selection_indicator_evidence_excludes_the_episode_id(base_graph):
    """`silent_omission`'s Finding.objects is `(episode_id, evidence_id)`; the episode
    id is not evidence the indicator was computed *from* in the sense of a cited
    source, and must not appear in the Risk's `evidence` list (fix round 1, review item
    4)."""
    g = base_graph
    put_all(g, evidence("ev-orphan"), {**episode(), "rev": 2,
                                        "evidenceRegister": ["ev-doc", "ev-orphan"]})
    risks = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    selection = next(r for r in risks if r["kind"] == "bias-selection")
    assert "ep-1" not in selection["evidence"]
    assert {"ev-doc", "ev-orphan"} <= set(selection["evidence"])


def test_bias_indicators_is_idempotent_when_nothing_changes(base_graph):
    g = base_graph
    put_all(
        g,
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1", "m-2"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="x",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 1}),
        obj("m-2", "Measure", objective="obj-1", task="t", attribute="a", measure="y",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 2}),
        {**episode(), "rev": 2, "objectives": ["obj-1"]},
    )
    first = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert first != []
    log_len = len(g.log())
    second = bias_indicators(g, "ep-1", now="2026-09-05T00:00:00Z")
    assert second == first
    assert len(g.log()) == log_len


def test_bias_indicators_revises_a_changed_risk_exactly_once(base_graph):
    g = base_graph
    put_all(
        g,
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1", "m-2"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="x",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 1}),
        obj("m-2", "Measure", objective="obj-1", task="t", attribute="a", measure="y",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 2}),
        {**episode(), "rev": 2, "objectives": ["obj-1"]},
    )
    first = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    over_spec_id = next(r["id"] for r in first if r["kind"] == "bias-over-specification")
    assert g.get(over_spec_id)["rev"] == 1
    risks_before = list(g.get("ep-1")["risks"])

    put_all(
        g,
        obj("m-3", "Measure", objective="obj-1", task="t2", attribute="b", measure="z",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 3}),
    )
    obj_1 = g.get("obj-1")
    put_all(g, {**obj_1, "rev": obj_1["rev"] + 1, "measures": ["m-1", "m-2", "m-3"]})

    second = bias_indicators(g, "ep-1", now="2026-09-04T01:00:00Z")
    over_spec_2 = next(r for r in second if r["kind"] == "bias-over-specification")
    assert over_spec_2["id"] == over_spec_id
    assert over_spec_2["rev"] == 2
    assert over_spec_2["evidence"] == sorted(["m-1", "m-2", "m-3"])
    # the id was already listed; a changed revision does not get re-appended
    assert g.get("ep-1")["risks"].count(over_spec_id) == 1
    assert set(g.get("ep-1")["risks"]) == set(risks_before)


def test_no_indicators_on_clean_episode(base_graph):
    g = base_graph
    put_all(g, alternative("alt-a", baseline=True), {**episode(), "rev": 2,
                                                      "alternatives": ["alt-a"]})
    assert bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z") == []
    # a call that fires nothing must not touch the episode at all
    assert g.get("ep-1")["rev"] == 2


def test_anchoring_indicator_fires_for_first_entered_with_a_short_flip(base_graph):
    g = base_graph
    put_all(
        g,
        alternative("alt-a", order=1, status="selected"),
        alternative("alt-b", order=2, status="evaluated"),
        obj("as-1", "Assumption", statement="s", linchpin=True, rationale="r",
            evidence="ev-doc", implicationsIfWrong="i",
            indicatorsThatWouldAlter=["x"], variedInSensitivity=True),
        obj("fa-1", "FlipAnalysis", run="run-x",
            parameter={"kind": "weight", "target": "ws-1:m-1", "label": "weight on m-1"},
            assumption="as-1", currentValue=0.6, range={"lo": 0.5, "hi": 0.7, "source": "sweep"},
            flipThreshold=0.65, flipDistance=0.05, direction="up",
            rankingBefore=["alt-a", "alt-b"], rankingAfter=["alt-b", "alt-a"],
            kernelVersion="0.1.0"),
        {**episode(), "rev": 2, "alternatives": ["alt-a", "alt-b"], "assumptions": ["as-1"],
         "flipAnalyses": ["fa-1"]},
    )
    risks = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    anchoring = next(r for r in risks if r["kind"] == "bias-anchoring")
    assert anchoring["id"] == "risk-bias-ep-1-anchoring"
    assert anchoring["evidence"] == sorted({"alt-a", "fa-1"})
    assert anchoring["owner"] == "unassigned"
    assert anchoring["status"] == "open"


def test_anchoring_indicator_does_not_fire_without_a_short_flip(base_graph):
    g = base_graph
    put_all(
        g,
        alternative("alt-a", order=1, status="selected"),
        alternative("alt-b", order=2, status="evaluated"),
        {**episode(), "rev": 2, "alternatives": ["alt-a", "alt-b"]},
    )
    risks = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert "bias-anchoring" not in {r["kind"] for r in risks}


def test_confirmation_indicator_fires_when_selected_evidence_is_reviewed_more_often(base_graph):
    g = base_graph
    put_all(
        g,
        evidence("ev-reviewed-1", reviewStatus="reviewed"),
        evidence("ev-reviewed-2", reviewStatus="reviewed"),
        evidence("ev-draft-1", reviewStatus="draft"),
        evidence("ev-draft-2", reviewStatus="draft"),
        alternative("alt-a", order=1, status="selected"),
        alternative("alt-b", order=2, status="evaluated"),
        obj("ob-a1", "Observation", alternative="alt-a", measure="m-1", value=1,
            evidence="ev-reviewed-1"),
        obj("ob-a2", "Observation", alternative="alt-a", measure="m-2", value=1,
            evidence="ev-reviewed-2"),
        obj("ob-b1", "Observation", alternative="alt-b", measure="m-1", value=1,
            evidence="ev-draft-1"),
        obj("ob-b2", "Observation", alternative="alt-b", measure="m-2", value=1,
            evidence="ev-draft-2"),
        {**episode(), "rev": 2, "alternatives": ["alt-a", "alt-b"],
         "observations": ["ob-a1", "ob-a2", "ob-b1", "ob-b2"]},
    )
    risks = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    assert {r["kind"] for r in risks} == {"bias-confirmation"}


def test_bias_indicators_on_complete_graph_stay_schema_valid(complete_episode):
    g = complete_episode
    risks = bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z")
    findings = validate(g)
    assert not any(f.rule == "schema" for f in findings)
    assert {r["id"] for r in risks} <= set(g.get("ep-1")["risks"])


def test_bias_indicators_tolerates_a_hand_edited_episode(base_graph):
    """A hand-edited store can hold a non-list `alternatives`/`objectives`/`runs` or a
    charter with no policy; the indicator computation must not raise, only find
    nothing to compute from."""
    g = base_graph
    bad_ep = {
        **g.get("ep-1"),
        "charter": "missing-charter",
        "alternatives": "not-a-list",
        "objectives": None,
        "flipAnalyses": 7,
        "runs": [{"not": "a string id"}],
    }
    g._latest["ep-1"] = bad_ep
    g._history["ep-1"][bad_ep["rev"]] = bad_ep
    assert bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z") == []


def test_bias_indicators_tolerates_a_malformed_alternative(base_graph):
    g = base_graph
    put_all(
        g,
        alternative("alt-a", order=1, status="selected"),
        {**episode(), "rev": 2, "alternatives": ["alt-a"]},
    )
    bad_alt = {**g.get("alt-a")}
    bad_alt.pop("enteredOrder", None)
    g._latest["alt-a"] = bad_alt
    g._history["alt-a"][bad_alt["rev"]] = bad_alt
    assert bias_indicators(g, "ep-1", now="2026-09-04T00:00:00Z") == []


def test_the_episode_revision_is_stamped_with_the_caller_s_now(base_graph):
    """An episode revision written at `now` says `now`. Carrying the previous revision's
    `createdAt` forward would date a kernel write to whenever a human last touched the
    object — and the whole record is read by its timestamps."""
    g = base_graph
    put_all(
        g,
        obj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
            measures=["m-1", "m-2"]),
        obj("m-1", "Measure", objective="obj-1", task="t", attribute="a", measure="x",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 1}),
        obj("m-2", "Measure", objective="obj-1", task="t", attribute="a", measure="y",
            metric={"units": "u", "direction": "max"}, criteria={"threshold": 2}),
        {**episode(), "rev": 2, "objectives": ["obj-1"]},
    )
    assert g.get("ep-1")["createdAt"] == "2026-09-04T00:00:00Z"
    risks = bias_indicators(g, "ep-1", now="2026-11-30T12:00:00Z")
    assert risks and g.get("ep-1")["risks"]
    assert g.get("ep-1")["createdAt"] == "2026-11-30T12:00:00Z"
