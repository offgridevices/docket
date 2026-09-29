# tests/agent/conftest.py
"""Graph builders for tests/agent, built on `tests.kernel.conftest`'s helpers (Task 8's
brief: "build the fixtures on tests/kernel/conftest.py's helpers... plus a
DecisionProgram"). Kept minimal — one stale model, one lapsed
`scopeOfValidity.validUntil` behind a Claim, one wrong-question-class model, one new
Evidence whose title contains an indicator, one assumption whose
`indicatorsThatWouldAlter` is a `{"$gap": ...}` marker.
"""

import pytest

from docket.store import Graph
from tests.kernel.conftest import charter, drs, episode, evidence, model, obj, policy, put_all


def vva_record(oid: str, date: str, **over):
    base = dict(
        problemStatement="ch-1", requirementsAndAcceptabilityCriteria="r",
        assumptionsCapabilitiesLimitationsRisks={
            "assumptions": ["a"], "capabilities": ["c"], "limitations": ["l"], "risks": ["r"],
        },
        methodology="m",
        accreditationDecision={"authority": "PM", "date": date, "scope": "s",
                               "basis": "document"},
        sections=[{"name": "Problem Statement", "content": "x"}],
    )
    base.update(over)
    return obj(oid, "VVARecord", **base)


def claim(oid: str, evidence_id: str, qc: str = "other", level: str = "U", **over):
    base = dict(text="c", questionClass=qc, assessableAt={"level": level},
                supportedBy=[{"evidence": evidence_id}])
    base.update(over)
    return obj(oid, "Claim", **base)


def assumption(oid: str, indicators, evidence_id: str = "ev-doc", **over):
    base = dict(statement="s", linchpin=False, rationale="r", evidence=evidence_id,
                implicationsIfWrong="i", indicatorsThatWouldAlter=indicators,
                variedInSensitivity=False)
    base.update(over)
    return obj(oid, "Assumption", **base)


def program(oid: str = "prg-1", **over):
    base = dict(name="p", charter="ch-1", episodes=["ep-1"], refreshTriggers=[], diffs=[])
    base.update(over)
    return obj(oid, "DecisionProgram", **base)


def _base_graph() -> Graph:
    g = Graph()
    put_all(g, policy(), evidence("ev-doc"), drs(), charter(), episode())
    return g


@pytest.fixture
def program_with_stale_model():
    """`mdl-1`'s VV&A was accredited 2019-05-01; the episode's `asOf` (2026-09-04) is
    more than three years past it -> `ReaccreditationRequired` -> `elapsed-time`. The
    model's questionClass matches the charter's ("other"), so `ModelUsePastPurpose`
    does not also fire here."""
    g = _base_graph()
    put_all(
        g,
        vva_record("vva-1", "2019-05-01"),
        model("mdl-1", vva="vva-1"),
        {**episode(), "rev": 2, "models": ["mdl-1"], "program": "prg-1"},
        program("prg-1"),
    )
    return g, "prg-1"


@pytest.fixture
def program_with_lapsed_evidence():
    """A Claim rests on Evidence whose `scopeOfValidity.validUntil` (2020-01-01) is
    before the episode's `asOf` (2026-09-04) -> `scope-lapsed` -> `evidence-changed`."""
    g = _base_graph()
    put_all(
        g,
        evidence("ev-lapsed", scopeOfValidity={
            "builtToAnswer": "q", "questionClass": "other", "intendedUse": "u",
            "validUntil": "2020-01-01",
        }),
        claim("cl-1", "ev-lapsed"),
        {**episode(), "rev": 2, "claims": ["cl-1"], "evidenceRegister": ["ev-lapsed"],
         "program": "prg-2"},
        program("prg-2"),
    )
    return g, "prg-2"


@pytest.fixture
def program_with_wrong_class_model():
    """`mdl-2`'s questionClass ("force-structure") differs from the charter's ("other")
    -> `ModelUsePastPurpose` only [ruling R11: not a refresh trigger]. Accreditation is
    recent, so `ReaccreditationRequired` does not also fire."""
    g = _base_graph()
    put_all(
        g,
        vva_record("vva-2", "2025-01-01"),
        model("mdl-2", vva="vva-2", questionClass="force-structure"),
        {**episode(), "rev": 2, "models": ["mdl-2"], "program": "prg-3"},
        program("prg-3"),
    )
    return g, "prg-3"


@pytest.fixture
def program_with_indicator():
    """Assumption `as-1`'s indicator "fuel price volatility" matches the title of
    `ev-new`, Evidence created after the episode's `asOf` and not in its
    evidenceRegister -> one `indicator-detected` proposal."""
    g = _base_graph()
    put_all(
        g,
        assumption("as-1", ["fuel price volatility"]),
        evidence("ev-new", title="2026 Fuel Price Volatility Outlook", createdAt="2026-09-10"),
        {**episode(), "rev": 2, "assumptions": ["as-1"], "program": "prg-4"},
        program("prg-4"),
    )
    return g, "prg-4"


@pytest.fixture
def program_with_boundary_indicator():
    """[fix round 1, issue I1] Indicator "rice" (4 chars, clears `_MIN_INDICATOR_LEN`)
    must not fire on the "rice" hiding inside "Price" (no letter boundary on either
    side), but must fire on a real word match bounded by a space/string-start or a
    hyphen. Three Evidence items exercise all three cases against the same assumption
    in one graph."""
    g = _base_graph()
    put_all(
        g,
        assumption("as-3", ["rice"]),
        evidence("ev-steel", title="2026 Steel Price Index Update", createdAt="2026-09-10"),
        evidence("ev-rice-word", title="Rice price index, 2026", createdAt="2026-09-11"),
        evidence("ev-rice-hyphen", title="rice-yield update", createdAt="2026-09-12"),
        {**episode(), "rev": 2, "assumptions": ["as-3"], "program": "prg-6"},
        program("prg-6"),
    )
    return g, "prg-6"


@pytest.fixture
def program_with_gapped_indicators():
    """`indicatorsThatWouldAlter` is a `{"$gap": ...}` marker [pre-flight defect 15]:
    `detect` must skip it, not iterate it."""
    g = _base_graph()
    put_all(
        g,
        assumption("as-2", {"$gap": "gap-x"}),
        evidence("ev-new2", title="Some new evidence", createdAt="2026-09-10"),
        {**episode(), "rev": 2, "assumptions": ["as-2"], "program": "prg-5"},
        program("prg-5"),
    )
    return g, "prg-5"
