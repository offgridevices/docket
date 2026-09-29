"""Budget-book sub-demonstration — the OMFV/XM30 line as the public record states it.

Seven annual Army RDT&E R-2 exhibits (President's Budget FY2021 through FY2027) are
ingested as `Evidence` of type `BudgetExhibit`, each carrying the typed assertions the
book makes about the programme's cost, its schedule and its analysis history. Three
published documents join them. Nothing is scored and nothing is computed: the only rule
this record exists to exercise is `value_conflicts`, which reports where the same line
item is stated at two different values.

Rules held while transcribing
-----------------------------

1. **Every figure was re-read from the committed extract.** The full budget books are not
   in this repository, and the local research library is not a source. Each number, date
   and window below was read out of `sources/army-rdte-r2-fy20NN-omfv-xm30-extract.pdf`
   at the page named in its locator.

2. **Dual locators.** The extract sidecars say "Page numbering is that of the source
   volumes", so the page printed in a footer is a *volume* page, not a page of the
   committed file. Every locator therefore carries both: the volume page as printed in
   the footer (from FY2023 onward the Army prints it as `Volume 3d - 268`; FY2021 and
   FY2022 print a bare number) and the page of the committed extract PDF where that
   footer can be seen. A reviewer opens the extract at the extract page and reads the
   volume page off the bottom of the sheet.

3. **The record reports; it does not adjudicate.** Where two pages disagree, both are
   recorded with their locators and neither is marked correct. Appropriations change
   between budget years and R-2 exhibits contain routine typographical errors; deciding
   which figure is right is not something this record does or claims to do.

4. **Nothing here is controlled.** Every page of every extract carries the header
   `UNCLASSIFIED`; the industry-day slides carry Distribution Statement A; both GAO
   products are reports to congressional committees. Every classification is `U`.

The subject keys are deliberately narrow. `omfv-mta-total-cost-fy21-24` and
`omfv-mta-total-cost-fy21-25` are different subjects because they are different windows
— four years and five — so the rule does not report a scope difference as a conflict.
"""

from __future__ import annotations

from docket.store import Graph

H = {"actorType": "human", "actorId": "shreyash"}
NOW = "2026-09-05T00:00:00Z"
AS_OF = "2026-09-05"
EXTRACTED = "2026-09-05"

ASAFM = "https://www.asafm.army.mil/Budget-Materials/"
CUSTODIAN = "Assistant Secretary of the Army (Financial Management and Comptroller)"


def src(fy: str) -> str:
    """The committed extract for one budget year."""
    return f"sources/army-rdte-r2-fy{fy}-omfv-xm30-extract.pdf"


def loc(book: str, pe: str, exhibit: str, volume: list[str], extract: list[int]) -> str:
    """A dual locator: the volume page as the extract prints it, and the extract page.

    `volume` entries are written exactly as the footer prints them — `2a-99` for
    "Volume 2a - 99" (FY2023 onward), or a bare `506` for the FY2021/FY2022 books, which
    print the page number alone.
    """
    vol = ("volume p. " + volume[0] if len(volume) == 1
           else "volume pp. " + ", ".join(volume))
    ext = ("extract PDF p. " + str(extract[0]) if len(extract) == 1
           else "extract PDF pp. " + ", ".join(str(p) for p in extract))
    return f"{book} {pe} {exhibit}, {vol} ({ext})"


def cited(oid: str, type_name: str, source: str, locator: str, *,
          confidence: str = "explicit", **fields) -> dict:
    """An object transcribed from a committed public artefact, carrying where from."""
    return {
        "id": oid, "type": type_name, "rev": 1, "createdBy": H, "createdAt": NOW,
        "ingestionProvenance": {"sourceArtifact": source, "locator": locator,
                                "extractor": "human", "extractedAt": EXTRACTED},
        "confidence": confidence, **fields,
    }


def own(oid: str, type_name: str, **fields) -> dict:
    """An object this record supplies. The charter question is ours, not the Army's;
    saying it came off a budget page would be a false citation."""
    return {"id": oid, "type": type_name, "rev": 1, "createdBy": H, "createdAt": NOW,
            **fields}


# --------------------------------------------------------------------------------------
# The seven books. `submitted` is the date printed in every exhibit header of that book
# ("Date: March 2023"), read from the extract, not from the sidecar.
# --------------------------------------------------------------------------------------

BOOKS = [
    ("ev-pb2021", "2021", "FY2021", "PE 0604100A; PE 0605625A", "2020-02",
     "the pre-reset book: the only R-4A schedule that dates an Analysis of Alternatives"),
    ("ev-pb2022", "2022", "FY2022", "PE 0605625A", "2021-05",
     "the first book after the February 2020 reset"),
    ("ev-pb2023", "2023", "FY2023", "PE 0605625A", "2022-04",
     "states that the Army's formal Analysis of Alternatives is still to be executed"),
    ("ev-pb2024", "2024", "FY2024", "PE 0603645A; PE 0605625A", "2023-03",
     "submitted the same month as the Army's Section 234 report"),
    ("ev-pb2025", "2025", "FY2025", "PE 0604100A; PE 0605625A", "2024-03",
     "the first book to use the XM30 name"),
    ("ev-pb2026", "2026", "FY2026", "PE 0605625A", "2025-06",
     "redefines ARIES and CAVE as vehicle hardware rather than analytical activities"),
    ("ev-pb2027", "2027", "FY2027", "PE 0605625A", "2026-04",
     "the first appearance of an XM30 procurement line in any P-form"),
]

# --------------------------------------------------------------------------------------
# The assertions: (evidence id, subject, field, value, locator).
#
# Costs are numbers so that 1348 and 1348.0 compare equal; dates, quarters, windows and
# definitions are strings and compare as themselves.
# --------------------------------------------------------------------------------------

COST_FY21_24 = "omfv-mta-total-cost-fy21-24"
COST_FY21_25 = "omfv-mta-total-cost-fy21-25"

ASSERTIONS: list[tuple[str, str, str, object, str]] = [
    # ---- total cost of the Middle Tier of Acquisition effort, FY2021-FY2024 -----------
    ("ev-pb2023", COST_FY21_24, "costM", 1432.1,
     loc("PB2023", "PE 0605625A", "R-2/R-2A", ["2e-257", "2e-259"], [73, 75])),
    ("ev-pb2024", COST_FY21_24, "costM", 1348,
     loc("PB2024", "PE 0603645A", "R-2/R-2A", ["2a-99", "2a-101"], [60, 61])),
    ("ev-pb2024", COST_FY21_24, "costM", 1384,
     loc("PB2024", "PE 0605625A", "R-2/R-2A", ["3d-268", "3d-270"], [74, 76])),
    ("ev-pb2025", COST_FY21_24, "costM", 1330,
     loc("PB2025", "PE 0605625A", "R-2/R-2A", ["3d-191", "3d-192"], [64, 65])),
    # A different window — five years, not four — so a different subject. The rule must
    # not report a scope difference as a disagreement.
    ("ev-pb2027", COST_FY21_25, "costM", 1536,
     loc("PB2027", "PE 0605625A", "R-2/R-2A", ["3d-306", "3d-308"], [50, 52])),

    # ---- when the Analysis of Alternatives happened -----------------------------------
    ("ev-pb2021", "omfv-aoa", "window", "started FY2019",
     loc("PB2021", "PE 0604100A", "R-2A", ["451"], [75])),
    ("ev-pb2021", "omfv-aoa", "window", "2Q2020-1Q2021, completion",
     "PB2021 PE 0605625A R-4A, volume p. 506 (extract PDF p. 92); "
     "R-2A, volume p. 500 (extract PDF p. 86)"),
    ("ev-pb2023", "omfv-aoa", "window", "formal execution FY2023",
     loc("PB2023", "PE 0605625A", "R-2A", ["2e-261"], [77])),
    ("ev-pb2024", "omfv-aoa", "window", "formal execution FY2023",
     loc("PB2024", "PE 0605625A", "R-2A", ["3d-271"], [77])),
    ("ev-pb2025", "omfv-aoa", "window", "started FY2023, continuing to FY2025",
     loc("PB2025", "PE 0604100A", "R-2A", ["2b-33"], [52])),

    # ---- when the Phase 2 concept-design contracts were awarded -----------------------
    ("ev-pb2022", "omfv-phase2-award", "date", "2021-07",
     loc("PB2022", "PE 0605625A", "R-3", ["460"], [89])),
    ("ev-pb2023", "omfv-phase2-award", "date", "2021-07",
     loc("PB2023", "PE 0605625A", "R-3", ["2e-264"], [80])),
    ("ev-gao-23-106549", "omfv-phase2-award", "date", "2021-09",
     "GAO-23-106549, Highlights page (PDF p. 2) and printed p. 5 (PDF p. 8)"),

    # ---- the concept-design phase as the Army's own schedule states it ----------------
    # One line below the A-CDD row on the same R-4A sheets, and the Army statement most
    # directly comparable with the award date: 4Q FY2021 is July-September 2021, which is
    # compatible with the July the R-3 exhibits print *and* with the September GAO gives.
    # It is recorded so that the award-date disagreement above is read beside it rather
    # than on its own.
    #
    # All six books that carry the row are recorded, not a sample. Every one of these
    # sheets is already cited above for its A-CDD row, and a record that reads a page for
    # one line and passes over the line below it is doing the thing this product exists
    # to catch. Six books, one value, no finding — that is the record being complete
    # about something uncontested.
    ("ev-pb2022", "omfv-concept-design", "window", "4Q FY2021 - 1Q FY2023",
     loc("PB2022", "PE 0605625A", "R-4A", ["463"], [92])),
    ("ev-pb2023", "omfv-concept-design", "window", "4Q FY2021 - 1Q FY2023",
     loc("PB2023", "PE 0605625A", "R-4A", ["2e-268"], [84])),
    ("ev-pb2024", "omfv-concept-design", "window", "4Q FY2021 - 1Q FY2023",
     loc("PB2024", "PE 0605625A", "R-4A", ["3d-281"], [87])),
    ("ev-pb2025", "omfv-concept-design", "window", "4Q FY2021 - 1Q FY2023",
     loc("PB2025", "PE 0605625A", "R-4A", ["3d-204"], [77])),
    ("ev-pb2026", "omfv-concept-design", "window", "4Q FY2021 - 1Q FY2023",
     loc("PB2026", "PE 0605625A", "R-4A", ["3d-339"], [74])),
    ("ev-pb2027", "omfv-concept-design", "window", "4Q FY2021 - 1Q FY2023",
     loc("PB2027", "PE 0605625A", "R-4A", ["3d-320"], [64])),

    # ---- the Abbreviated Capability Development Document ------------------------------
    ("ev-pb2022", "omfv-acdd", "quarter", "1Q-2Q FY2022",
     loc("PB2022", "PE 0605625A", "R-4A", ["463"], [92])),
    ("ev-pb2023", "omfv-acdd", "quarter", "1Q-2Q FY2022",
     loc("PB2023", "PE 0605625A", "R-4A", ["2e-268"], [84])),
    ("ev-pb2024", "omfv-acdd", "quarter", "2Q-2Q FY2022",
     loc("PB2024", "PE 0605625A", "R-4A", ["3d-281"], [87])),
    ("ev-pb2025", "omfv-acdd", "quarter", "2Q-2Q FY2022",
     loc("PB2025", "PE 0605625A", "R-4A", ["3d-204"], [77])),
    ("ev-pb2026", "omfv-acdd", "quarter", "2Q-2Q FY2022",
     loc("PB2026", "PE 0605625A", "R-4A", ["3d-339"], [74])),
    ("ev-pb2027", "omfv-acdd", "quarter", "2Q-2Q FY2022",
     loc("PB2027", "PE 0605625A", "R-4A", ["3d-320"], [64])),
    ("ev-gao-23-106059", "omfv-acdd", "quarter", "2022-07 (4Q FY2022)",
     "GAO-23-106059 printed p. 128 (PDF p. 138), OMFV programme profile — the PDF is a "
     "deliberate sidecar-only source; see sources/gao-23-106059.source.md"),

    # ---- what ARIES and CAVE are ------------------------------------------------------
    ("ev-industry-day-2020-12", "aries", "definition",
     "performance M&S: highlights sensitivities between functional requirements",
     "Industry Day briefing, PDF p. 18 (slide footer 20)"),
    ("ev-pb2026", "aries", "definition",
     "Augmented Reality Integrated Environment for Situational Awareness - crew display "
     "overlay",
     loc("PB2026", "PE 0605625A", "R-2A", ["3d-330"], [65])),
    ("ev-industry-day-2020-12", "cave", "definition",
     "Immersive Simulation modeling; first-person perspective of the design",
     "Industry Day briefing, PDF p. 18 (slide footer 20)"),
    ("ev-pb2026", "cave", "definition",
     "Commanders Aperture Visual Enhancement - 360-degree camera/sensor system",
     loc("PB2026", "PE 0605625A", "R-2A", ["3d-330"], [65])),
]


def assertions_for(ev_id: str) -> list[dict]:
    """The assertion rows this evidence object carries, in table order."""
    return [{"subject": s, "field": f, "value": v, "locator": locator}
            for e, s, f, v, locator in ASSERTIONS if e == ev_id]


def _gaps(g: Graph) -> None:
    put = g.put

    put(own(
        "gap-exhibit-reliability", "InsufficientEvidence",
        sought=("the steps taken to ensure the consistency of figures across the annual "
                "exhibits"),
        whereLookedFor=["the seven committed R-2 extracts"],
        whyNotFound=("the R-2 exhibit format has no field for reconciliation against "
                     "prior years"),
        impact="degrading",
        indicatorsThatWouldResolve=[
            "a published reconciliation of the OMFV/XM30 cost lines across budget years"],
        confirmedBy={"actorId": "shreyash", "date": AS_OF}), H)

    put(own(
        "gap-document-reliability", "InsufficientEvidence",
        sought=("the steps taken to establish the reliability of the figures the three "
                "published documents print about the OMFV/XM30 effort"),
        whereLookedFor=["GAO-23-106549", "the GAO-23-106059 programme profile",
                        "the December 2020 industry-day slides"],
        whyNotFound=("GAO-23-106549 states at footnote 7 (printed p. 9) and in appendix I "
                     "(printed p. 18) that it did not independently assess or verify the "
                     "analytical efforts supporting the Army's report; the annual "
                     "assessment's programme profile and the industry-day slides carry no "
                     "methodology section at all"),
        impact="degrading",
        indicatorsThatWouldResolve=[
            "a published methodology for the dates given in either GAO product",
            "a methodology annex to the December 2020 industry-day briefing"],
        confirmedBy={"actorId": "shreyash", "date": AS_OF}), H)

    put(own(
        "gap-msa-line-studies", "InsufficientEvidence",
        sought=("which studies the annual Modeling Simulation & Analysis line funded, in "
                "particular the July 2021 Maneuver Battle Lab touchpoint and the "
                "September 2021 TRAC study"),
        whereLookedFor=["the seven PE 0605625A exhibits, FY2021-FY2027"],
        whyNotFound=("the exhibit has no field for the studies a line pays for; neither "
                     "TRAC nor the Maneuver Battle Lab appears in PE 0605625A in any year"),
        impact="degrading",
        indicatorsThatWouldResolve=[
            "an exhibit or study list naming the analyses the MS&A line funded"],
        confirmedBy={"actorId": "shreyash", "date": AS_OF}), H)


def _budget_exhibits(g: Graph) -> None:
    for ev_id, fy_digits, fiscal_year, program_element, submitted, note in BOOKS:
        source = src(fy_digits)
        g.put(cited(
            ev_id, "Evidence", source,
            f"the OMFV/XM30 pages of the PB {fiscal_year} justification books — {note}",
            title=(f"Army RDT&E R-2 exhibits, President's Budget {fiscal_year} — "
                   f"OMFV/XM30 extract"),
            evidenceType="BudgetExhibit",
            fiscalYear=fiscal_year,
            programElement=program_element,
            submitted=submitted,
            date=submitted,
            pointer={"uri": f"{source} ; {ASAFM}", "custodian": CUSTODIAN},
            classification={"level": "U", "metadataLevel": "U"},
            scopeOfValidity={
                "builtToAnswer": ("the President's Budget justification for the OMFV/XM30 "
                                  "effort"),
                "questionClass": "cost",
                "intendedUse": "congressional budget justification"},
            reviewStatus="reviewed",
            reliabilitySteps={"$gap": "gap-exhibit-reliability"},
            inclusionReason=("one of the seven annual R-2 exhibits covering the OMFV/XM30 "
                             "program elements"),
            assertions=assertions_for(ev_id)), H)


def _documents(g: Graph) -> None:
    put = g.put
    shared = {
        "classification": {"level": "U", "metadataLevel": "U"},
        "reviewStatus": "reviewed",
        "reliabilitySteps": {"$gap": "gap-document-reliability"},
    }

    put(cited(
        "ev-gao-23-106549", "Evidence", "sources/gao-23-106549.pdf",
        "printed pp. 1-18 (PDF pp. 4-21)",
        title=("GAO-23-106549, Optionally Manned Fighting Vehicle: Observations on the "
               "Objectivity, Validity, and Reliability of the Army's Report"),
        evidenceType="Document",
        publisher="U.S. Government Accountability Office",
        published="2023-06-27",
        date="2023-06-27",
        pointer={"uri": ("sources/gao-23-106549.pdf ; "
                         "https://www.gao.gov/products/gao-23-106549"),
                 "custodian": "GAO"},
        scopeOfValidity={
            "builtToAnswer": ("whether the Army's Section 234 report was objective, valid "
                              "and reliable as GAO defines those terms"),
            "questionClass": "other",
            "conditions": ["GAO did not independently assess or verify the analytical "
                           "efforts supporting the Army's report (footnote 7, printed "
                           "p. 9; appendix I, printed p. 18)"],
            "intendedUse": "report to congressional committees"},
        inclusionReason=("it dates the Phase 2 concept-design award, which the Army's own "
                         "budget exhibits date differently"),
        assertions=assertions_for("ev-gao-23-106549"), **shared), H)

    put(cited(
        "ev-gao-23-106059", "Evidence", "sources/gao-23-106059.source.md",
        "the sidecar for the OMFV/XM30 programme profile at printed p. 128 (PDF p. 138)",
        title=("GAO-23-106059, Weapon Systems Annual Assessment (2023) — OMFV/XM30 "
               "programme profile"),
        evidenceType="Document",
        publisher="U.S. Government Accountability Office",
        published="2023-06",
        date="2023-06",
        pointer={"uri": ("sources/gao-23-106059.source.md ; "
                         "https://www.gao.gov/products/gao-23-106059"),
                 "custodian": "GAO"},
        scopeOfValidity={
            "builtToAnswer": ("the annual status of major Department of War acquisition "
                              "programmes"),
            "questionClass": "schedule",
            "conditions": ["the 24.7 MB PDF is deliberately not committed; the committed "
                           "artefact is the sidecar, and the page is checkable at the "
                           "public landing page"],
            "intendedUse": "report to congressional committees"},
        inclusionReason=("it dates the approval of the Abbreviated Capability Development "
                         "Document, which the R-4A schedules place in a different quarter"),
        assertions=assertions_for("ev-gao-23-106059"), **shared), H)

    put(cited(
        "ev-industry-day-2020-12", "Evidence",
        "sources/army-2020-12-09-omfv-industry-day-briefing.pdf",
        "PDF p. 18 (slide footer 20), 'OMFV Phase 2 MS&A Activities'",
        title="Optionally Manned Fighting Vehicle Industry Day briefing, 9 December 2020",
        evidenceType="Document",
        publisher=("U.S. Army PEO Ground Combat Systems, PM Maneuver Combat Systems, "
                   "NGCV CFT and ACC-DTA"),
        published="2020-12-09",
        date="2020-12-09",
        pointer={"uri": ("sources/army-2020-12-09-omfv-industry-day-briefing.pdf ; "
                         "https://sam.gov/opp/86571129bfc34b668e8a7137a20f32b3/view"),
                 "custodian": "U.S. Army Contracting Command - Detroit Arsenal"},
        scopeOfValidity={
            "builtToAnswer": ("what the Phase 2 modelling, simulation and analysis "
                              "programme consisted of"),
            "questionClass": "other",
            "intendedUse": "industry briefing, Distribution Statement A"},
        inclusionReason=("it defines ARIES and CAVE as analytical activities, which the "
                         "FY2026 exhibit later redefines as vehicle hardware"),
        assertions=assertions_for("ev-industry-day-2020-12"), **shared), H)


def _frame(g: Graph) -> None:
    """The policy, charter and episode the value-conflict rule needs to see a register.

    `value_conflicts` reads the evidence register of every episode whose charter names
    the policy. Without these three objects the rule has nothing to look at and
    `validate(g, policy)` returns nothing at all.
    """
    put = g.put

    put(own(
        "pol-budget", "Policy",
        name="budget-record consistency",
        version="0.1",
        decisionClass="record-consistency",
        # Schema-forced: the catalogue requires a method even though nothing here is
        # evaluated. Nothing in this record is scored, ranked or aggregated.
        method="mavt",
        tailoring="published-21",
        aggregationK=1,
        requiredBiasChecks=[],
        requireAllLinchpinsVaried=False,
        prohibitedExclusionReasons=["time-or-resource"],
        blockingRules=[],
        nSimplex=200), H)

    put(own(
        "ch-budget", "Charter",
        question=("What does the public budget record state about the OMFV/XM30 effort's "
                  "cost, schedule and analysis history, and where does it contradict "
                  "itself?"),
        decisionToBeMade="which figures a decision record may rely on",
        consequencesOfErroneousOutput=("a decision package cites a cost, an award date or "
                                       "an analysis window that another page of the same "
                                       "public record contradicts"),
        questionClass="cost",
        scope={"included": ["PE 0605625A", "PE 0603645A", "PE 0604100A",
                            "PB2021 through PB2027 R-2, R-3 and R-4A exhibits"],
               "excluded": []},
        authority={"signer": "shreyash", "board": "n/a"},
        decisionClassPolicy="pol-budget",
        # The question is ours. The Army did not ask it.
        confidence="inferred"), H)

    put(own(
        "rk-msa-line-studies", "Risk",
        statement=("The annual Modeling Simulation & Analysis line is funded and described "
                   "every year, but no exhibit names the individual studies it paid for."),
        kind="data",
        consequence=("A cost or schedule figure taken from the MS&A line cannot be traced "
                     "to the analysis it funded, so a reader cannot tell whether a named "
                     "study is inside or outside the figure."),
        owner="shreyash",
        monitor=("Re-read the MS&A narrative in each new President's Budget for a study "
                 "list."),
        status="open",
        evidence=["gap-msa-line-studies"]), H)

    put(own(
        "ep-budget", "DecisionEpisode",
        sequence=1,
        charter="ch-budget",
        lifecycleState="DRAFT",
        transitions=[],
        objectives=[], alternatives=[], groundRules=[], constraints=[], assumptions=[],
        evidenceRegister=[ev_id for ev_id, *_ in BOOKS] + [
            "ev-gao-23-106549", "ev-gao-23-106059", "ev-industry-day-2020-12"],
        scenarios=[], claims=[], risks=["rk-msa-line-studies"], biasChecks=[],
        mandateElements=[], observations=[], weightSets=[], models=[],
        runs=[], flipAnalyses=[], narratives=[],
        asOf=AS_OF), H)


def build() -> Graph:
    """The ingestion record, as a human wrote it. Nothing is computed here."""
    g = Graph()
    _gaps(g)
    _budget_exhibits(g)
    _documents(g)
    _frame(g)
    return g
