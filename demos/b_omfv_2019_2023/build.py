"""Demonstration B — the OMFV requirements chain, 2020-2023, as one DecisionProgram.

Five episodes on the public record, three sub-episodes for the three sections GAO
graded, and GAO-23-106549's nine findings detected by named kernel rules on the
sub-episode GAO attributed each one to.

Sources, and the locator convention each one uses:

| file | convention |
|---|---|
| `sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md` | section name |
| `sources/army-2020-04-09-omfv-industry-day-narrative.pdf` | `p. N` (PDF page = printed page) |
| `sources/army-2020-12-09-omfv-industry-day-briefing.pdf` | `PDF p. N (slide footer M)` |
| `sources/gao-23-106549.pdf` | `printed p. N (PDF p. N+3)` |
| `sources/acc-dta-2022-10-25-omfv-phase-3-4-industry-qa-01-140.pdf` | `PDF p. N` |
| `sources/army-rdte-r2-fy2025-omfv-xm30-extract.pdf` | source-volume page + extract PDF page |
| `sources/breaking-defense-2020-02-06-polish-bridge-problem.source.md` | sidecar only |

The Dec 2020 briefing's slide footers are one or two out from the PDF page index (PDF 5
is footer "6", PDF 17 is "19", PDF 18 is "20"), so every locator into it carries both
numbers. The budget extract states that "page numbering is that of the source volumes",
so its locators carry the volume page and the extract page.

Five rules held while transcribing.

1. **Every sentence is somebody's, and the record says whose.** Text lifted verbatim from
   a source is `confidence: "explicit"` with the page it came off. A sentence this
   reconstruction wrote — the charter question, the consequences paragraph, the
   identification of "TRAC OE" with the second TRAC study GAO never names — is
   `confidence: "inferred"`. `confidence` is an object-level envelope field, so one
   reconstructed sentence marks the whole object inferred; that is a coarser instrument
   than one would like and the README says so.

2. **The Army's Section 234 report is not public and is not invented.** March 2023 is
   reconstructed *from GAO's description of it*. What is recorded is what GAO reports,
   with the GAO page that reports it. The report itself is an Evidence object with a
   gapped pointer, covered by a typed Exclusion, and cited by no Claim.

3. **GAO did not assess or verify the Army's analytical work** (footnote 7, printed p. 9;
   Appendix I, printed p. 17). Every one of F1-F9 is a *representation* failure. Nothing
   in this record says the analysis was wrong, because GAO does not say that.

4. **GAO published nine section-by-dimension verdicts in prose, not a grid and not
   per-question labels.** Three section headings, each followed by an Objectivity, a
   Validity and a Reliability paragraph, printed pp. 8-14; Figure 3 (printed p. 7) is the
   standards figure and carries no verdicts. Arranging the nine as a 3x3 grid is *ours*,
   as is the cut of GAO's prose into nine findings and every per-question state this
   record produces under the `gao-23-106549` tailoring. The nine verdicts are GAO's, and
   they are the only thing compared cell for cell.

5. **Where the schema demands a field the record does not have, the record says so.** A
   gap object, a typed Exclusion, or — where neither is possible because the field is not
   a slot — a disclosed schema-forced string. `Policy.method`, `Model.definition.version`
   and `Measure.metric.units`/`direction` are the three of those, and the README lists
   them.

Each episode is dated to its own source: `createdAt` and `asOf` are the date of the
document that opened it, so the elapsed-time predicates (accreditation age, scope
validity) read as they would have then. The transcription date lives in
`ingestionProvenance.extractedAt`.
"""

from __future__ import annotations

from docket.kernel.refresh import is_computed_bias_risk
from docket.store import Graph

H = {"actorType": "human", "actorId": "shreyash"}

# One `now` per episode: the date of the document that opened it.
NOW1 = "2020-02-25T00:00:00Z"
NOW2 = "2020-12-09T00:00:00Z"
NOW3 = "2021-09-30T00:00:00Z"
NOW4 = "2023-03-31T00:00:00Z"
NOW5 = "2023-06-26T00:00:00Z"
AS_OF = {1: "2020-02-25", 2: "2020-12-09", 3: "2021-09-30", 4: "2023-03-31",
         5: "2023-06-26"}
EXTRACTED = "2026-09-06"

SRC_CON = "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md"
SRC_NARRATIVE = "sources/army-2020-04-09-omfv-industry-day-narrative.pdf"
SRC_BRIEFING = "sources/army-2020-12-09-omfv-industry-day-briefing.pdf"
SRC_GAO = "sources/gao-23-106549.pdf"
SRC_QA = "sources/acc-dta-2022-10-25-omfv-phase-3-4-industry-qa-01-140.pdf"
SRC_BREAKING_DEFENSE = "sources/breaking-defense-2020-02-06-polish-bridge-problem.source.md"
SRC_AWARD_STUB = "sources/army-2023-06-26-omfv-phase-3-4-award.source.md"
SRC_R2_FY2025 = "sources/army-rdte-r2-fy2025-omfv-xm30-extract.pdf"

PROGRAM = "prg-omfv"
CHARTER = "ch-omfv"
POLICY = "pol-omfv"
EPISODE_1 = "ep-omfv-2020-02"
EPISODE_2 = "ep-omfv-2020-02-r2"
EPISODE_3 = "ep-omfv-2020-02-r3"
EPISODE_4 = "ep-omfv-2020-02-r4"
EPISODE_5 = "ep-omfv-2020-02-r5"
SUB_EPISODES = {"dc": "ep-omfv-2020-02-r4-dc", "fs": "ep-omfv-2020-02-r4-fs",
                "ce": "ep-omfv-2020-02-r4-ce"}
MAIN_CHAIN = [EPISODE_1, EPISODE_2, EPISODE_3, EPISODE_4, EPISODE_5]

# The three sections of the Army's March 2023 report, as GAO grades them, and the printed
# pages of GAO-23-106549 on which each section's grade appears.
SECTION_TITLES = {
    "dc": "the desired characteristics for the OMFV (GAO printed pp. 8-10)",
    "fs": "force structure designs and operational concepts (GAO printed pp. 10-12)",
    "ce": ("the combat effectiveness of the OMFV concepts compared with the modernized "
           "Bradley (GAO printed pp. 13-14)"),
}


def gao(printed_page: int) -> str:
    """A pointer into the committed GAO PDF. Printed page + 3 = PDF page."""
    return f"{SRC_GAO}#page={printed_page + 3}"


def gao_at(printed_page: int) -> str:
    """The locator string for a GAO page, printed and PDF both named."""
    return f"printed p. {printed_page} (PDF p. {printed_page + 3})"


def slide(pdf_page: int, footer: int) -> str:
    """The locator string for a Dec 2020 briefing slide. Never a bare slide number."""
    return f"PDF p. {pdf_page} (slide footer {footer})"


def slide_uri(pdf_page: int) -> str:
    return f"{SRC_BRIEFING}#page={pdf_page}"


def cited(oid: str, type_name: str, artifact: str, locator: str, *, now: str,
          confidence: str = "explicit", **fields) -> dict:
    """An object transcribed from a source, carrying where it came from.

    The parameter is `artifact`, not `source`: `RefreshTrigger`, `GroundRule`,
    `Constraint` and `Scenario` all have their own required `source` field, and a
    helper that shadowed it would refuse exactly the objects that need it most."""
    return {
        "id": oid, "type": type_name, "rev": 1, "createdBy": H, "createdAt": now,
        "ingestionProvenance": {"sourceArtifact": artifact, "locator": locator,
                                "extractor": "human", "extractedAt": EXTRACTED},
        "confidence": confidence, **fields,
    }


def own(oid: str, type_name: str, *, now: str, **fields) -> dict:
    """An object this reconstruction supplies. No ingestion provenance, because it was
    not extracted from anything: the policy, the plans and the weight set are ours, and
    saying they came off an Army page would be a false citation."""
    return {"id": oid, "type": type_name, "rev": 1, "createdBy": H, "createdAt": now,
            **fields}


def revise(g: Graph, oid: str, *, now: str, **fields) -> dict:
    """One human revision of an object already in the graph."""
    o = g.get(oid)
    return g.put({**o, "rev": o["rev"] + 1, "createdBy": H, "createdAt": now, **fields}, H)


# ---- the nine characteristics, verbatim -------------------------------------------
# Text: SAM.gov notice 2020-02-25, section "OMFV Characteristics: Objectives".
# Rank: Industry Day Narrative 2020-04-09, p. 6, section 3.2 — "The OMFV Characteristics
# are prioritized in the following order: 1. Survivability 2. Mobility 3. Growth
# 4. Lethality 5. Weight 6. Logistics 7. Transportability 8. Manning 9. Training".
# The February notice states NO priority order; the rank is the April document's, and the
# locator on every Objective says so.
CHARACTERISTICS_FEB = [
    ("obj-survivability", "Survivability", 1,
     "The OMFV must protect the crew and Soldiers from emerging threats and CBRN "
     "environments. The OMFV should reduce likelihood of detection by minimizing "
     "thermal, visual, and acoustic signatures."),
    ("obj-mobility", "Mobility", 2,
     "The OMFV must have mobility that can keep pace with the Abrams in a combined arms "
     "fight through rural and urban terrain."),
    ("obj-growth", "Growth", 3,
     "The OMFV must possess the growth margins and open architecture required for rapid "
     "upgrades and insertion of future technologies such as mission command systems, "
     "protection systems, and sensors."),
    ("obj-lethality", "Lethality", 4,
     "The OMFV equipped platoons must defeat future near-peer soldiers, infantry "
     "fighting vehicles, helicopters, small unmanned aerial systems, and tanks as part "
     "of a Combined Arms Team in rural and urban terrain."),
    ("obj-weight", "Weight", 5,
     "The OMFV must traverse 80% of Main Supply Routes (MSRs), national highways, and "
     "bridges in pacing threat countries, and reduce the cost of logistics and "
     "maintenance. Designs must allow for future growth in components and component "
     "weights without overall growth of vehicle weight through modularity and "
     "innovation."),
    ("obj-logistics", "Logistics", 6,
     "The OMFV must reduce the logistical burden on ABCTs and must be equipped with "
     "advanced diagnostic and prognostic capabilities. Advanced manufacturing and other "
     "innovative techniques should be included in the design that reduce the time and "
     "cost of vehicle repairs."),
    ("obj-transportability", "Transportability", 7,
     "The OMFV must be worldwide deployable by standard inter- and intra-theater sea, "
     "waterway, air, rail, and road modes of transportation."),
    ("obj-manning", "Manning", 8,
     "The OMFV should operate with the minimal number of crew members required to fight "
     "and win. The OMFV should allow commanders to choose between manned or remote "
     "operation based on the tactical situation."),
    ("obj-training", "Training", 9,
     "The OMFV should contain embedded training capabilities that are compatible with "
     "the Synthetic Training Environment (STE)."),
]

# The December 2020 updated CON, verbatim, Dec 2020 briefing PDF p. 5 (slide footer 6).
SURVIVABILITY_DEC = (
    "The OMFV shall be survivable against modern direct fire, indirect fire, and blast "
    "threats. The OMFV should reduce likelihood of detection by minimizing thermal, "
    "visual, and acoustic signatures.")
MANNING_DEC = (
    "A platoon of OMFVs will transport 30 Soldiers that dismount from the vehicles. Each "
    "OMFV vehicle will be crewed by no more than two Soldiers who will be positioned in "
    "the hull. Squad members can perform crew duties prior to dismounting the OMFV but "
    "the vehicles must remain operational after dismounting. The OMFV should allow "
    "commanders to choose between manned or remote operation based on the tactical "
    "situation.")

CONFIRMED = {"actorId": "shreyash", "date": "2026-09-06"}


def _gaps(g: Graph) -> None:
    """The five gaps the February-to-December record already carries.

    Every one is `confirmedBy` a human: G1 refuses an episode that reaches an
    unconfirmed gap, and — since the orphan-gap rule landed — a gap that hangs off
    nothing at all holds G1 shut store-wide, so each of these is also referenced by the
    slot it fills.
    """
    g.put(cited(
        "gap-reliability-steps", "InsufficientEvidence", SRC_GAO, gao_at(9), now=NOW1,
        confidence="absent",
        sought="the steps the Army took to ensure the reliability of the data used in "
               "the analyses supporting the March 2023 report",
        whereLookedFor=[
            "GAO-23-106549 printed pp. 9-10 (PDF pp. 12-13)",
            "the Army's Section 234 report, which is not public",
            "public web search, 2026-09-06"],
        whyNotFound=(
            "GAO reports that \"the Army report did not clearly describe the methodology "
            "of these efforts; the steps it took to ensure data reliability; or the "
            "verification, validation, and accreditation of the models and simulations "
            "it used\" (printed p. 9)"),
        confirmedBy=CONFIRMED, impact="blocking",
        indicatorsThatWouldResolve=[
            "release of the Army's Section 234 report with its data-reliability section",
            "an Army data-reliability assessment published for any of the 11 analytical "
            "efforts"]), H)

    g.put(cited(
        "gap-poland-data", "InsufficientEvidence", SRC_GAO, gao_at(9), now=NOW1,
        confidence="absent",
        sought="the data and methods supporting the assumption that bridges in Poland "
               "are representative of those across Eastern Europe",
        whereLookedFor=[
            "the Army's Section 234 report as described in GAO-23-106549 printed p. 9",
            "public web search, 2026-09-06"],
        whyNotFound=(
            "the report assumes that bridges in Poland are representative of those "
            "across Eastern Europe, but the Army does not identify the data and methods "
            "used to support this assumption (GAO-23-106549 printed p. 9)"),
        confirmedBy=CONFIRMED, impact="blocking",
        indicatorsThatWouldResolve=[
            "an ERDC-style bridge classification study for the pacing theatre",
            "release of the bridge classification data behind the Weight threshold"]), H)


def _episode_1_evidence(g: Graph) -> None:
    """The three documents the February 2020 record rests on.

    Every Evidence object in this demonstration carries `reliabilitySteps` as the same
    gap object. That is F8 stated once and referenced everywhere, not eight separate
    silences: GAO's finding is about the report as a whole.
    """
    g.put(cited(
        "ev-con-2020-02", "Evidence", SRC_CON,
        "section 'OMFV Characteristics: Objectives'", now=NOW1,
        title=("Optionally Manned Fighting Vehicle (OMFV) Characteristics For Industry "
               "Comment, SAM.gov notice, 25 February 2020"),
        evidenceType="Document",
        publisher="Department of the Army, Next Generation Combat Vehicles "
                  "Cross-Functional Team",
        published="2020-02-25", date="2020-02-25",
        pointer={"uri": "https://sam.gov/opp/7bc2690bb261442d970970d574dab8ff/view",
                 "custodian": "SAM.gov"},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": "the desired characteristics for the OMFV",
            "questionClass": "desired-characteristics",
            "intendedUse": "industry comment"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Next Generation Combat Vehicles Cross-Functional Team",
                    "role": "issuing authority", "date": "2020-02-25"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason="the Army's own statement of the nine desired characteristics"), H)

    g.put(cited(
        "ev-industry-day-narrative-2020-04", "Evidence", SRC_NARRATIVE,
        "p. 6, section 3.2", now=NOW1,
        title="Industry Day Narrative for OMFV, 9 April 2020",
        evidenceType="Document",
        publisher="Department of the Army, Next Generation Combat Vehicles "
                  "Cross-Functional Team",
        published="2020-04-09", date="2020-04-09",
        pointer={"uri": f"{SRC_NARRATIVE}#page=6",
                 "custodian": "Department of the Army (DISTRIBUTION A: approved for "
                              "public release)"},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": "the OMFV acquisition approach and the priority order of "
                             "the nine desired characteristics",
            "questionClass": "desired-characteristics",
            "intendedUse": "industry day briefing narrative"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Next Generation Combat Vehicles Cross-Functional Team",
                    "role": "issuing authority", "date": "2020-04-09"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=("the only public document that states the priority order of the "
                         "nine characteristics; the February notice does not")), H)

    g.put(cited(
        "ev-breaking-defense", "Evidence", SRC_BREAKING_DEFENSE, "sidecar, two quoted "
        "sentences", now=NOW1,
        title=("Breaking Defense, 'OMFV: The Army's Polish Bridge Problem', 6 February "
               "2020"),
        evidenceType="Document",
        publisher="Breaking Defense (Sydney J. Freedberg Jr.)",
        published="2020-02-06", date="2020-02-06",
        pointer={"uri": "https://breakingdefense.com/2020/02/omfv-the-armys-polish-"
                        "bridge-problem/",
                 "custodian": ("Breaking Defense — copyrighted press; no artefact "
                               "committed, see " + SRC_BREAKING_DEFENSE)},
        classification={"level": "U",
                        "caveats": ["copyrighted press, not a US Government work"],
                        "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("why the OMFV's weight matters for movement across Eastern "
                              "European bridges"),
            "questionClass": "desired-characteristics",
            "intendedUse": "trade press explanation of the Weight characteristic"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Breaking Defense", "role": "publisher (editorial review; "
                    "no other review record is public)", "date": "2020-02-06"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=("the public, articulable operational rationale for the "
                         "Poland-bridges assumption; the assumption is reasonable, which "
                         "is exactly why an unevidenced version of it is easy to nod "
                         "past"),
        limitations=[
            {"statement": ("Copyrighted press. No copy is committed and only the two "
                           "sentences the sidecar already quotes may be reproduced."),
             "impact": ("the rationale is read from two quoted sentences, not from the "
                        "article")}]), H)


def _objectives_and_measure(g: Graph) -> None:
    """The nine characteristics as Objectives, and the one Measure the record supports.

    Eight of the nine carry no Measure, and that is the true statement: the Army's 28
    prioritized attributes are not public (GAO printed p. 8), and `Measure.metric.units`
    and `direction` are required fields with no slot, so inventing a metric for the other
    eight would be exactly the schema-forced fabrication this project refuses. The eight
    blocking `objective-measured` findings that result are the finding, not a bug.
    """
    for oid, name, rank, text in CHARACTERISTICS_FEB:
        g.put(cited(
            oid, "Objective", SRC_CON,
            f"section 'OMFV Characteristics: Objectives', {name} (characteristic text); "
            f"{SRC_NARRATIVE} p. 6 section 3.2 (priorityRank {rank})",
            now=NOW1, name=name, description=text, priority="primary", priorityRank=rank,
            provenance="ev-con-2020-02",
            **({"measures": ["m-weight-bridges"]} if oid == "obj-weight" else {})), H)

    g.put(cited(
        "m-weight-bridges", "Measure", SRC_CON,
        "section 'OMFV Characteristics: Objectives', Weight", now=NOW1,
        objective="obj-weight",
        task="Move the fleet across the pacing theatre",
        attribute="route and bridge trafficability at the vehicle's design weight",
        measure=("traverse 80% of Main Supply Routes (MSRs), national highways, and "
                 "bridges in pacing threat countries"),
        metric={"units": ("percent of MSRs, national highways and bridges in pacing "
                          "threat countries"),
                "direction": "max"},
        criteria={"threshold": 80}), H)


def _assumptions_and_alternatives(g: Graph) -> None:
    g.put(cited(
        "as-poland-bridges", "Assumption", SRC_GAO, gao_at(9), now=NOW1,
        statement=("bridges in Poland are representative of those across Eastern "
                   "Europe"),
        linchpin=True,
        rationale=("Breaking Defense, 6 February 2020: \"Poland in particular has many "
                   "rivers and few reinforced bridges\", and \"few of them [Eastern "
                   "European bridges] can handle more than 55 tons\". That is a real "
                   "operational rationale, and it is not the same thing as evidence for "
                   "representativeness."),
        evidence={"$gap": "gap-poland-data"},
        implicationsIfWrong=("the 80 percent Weight threshold, and therefore the design "
                             "weight envelope, could be set against the wrong bridge "
                             "population"),
        indicatorsThatWouldAlter=[
            "a bridge classification survey of the pacing theatre",
            "a change in the pacing threat country set"],
        variedInSensitivity=False), H)

    g.put(cited(
        "as-manning-feb", "Assumption", SRC_CON,
        "section 'OMFV Characteristics: Objectives', Manning", now=NOW1,
        statement=("The OMFV should operate with the minimal number of crew members "
                   "required to fight and win."),
        linchpin=False,
        rationale=("the February 2020 characteristic states the crew as a minimum to be "
                   "found, not as a number: no crew size appears anywhere in the notice"),
        evidence="ev-con-2020-02",
        implicationsIfWrong=("a crew size chosen later on other grounds would be "
                             "unconstrained by this characteristic, which is what "
                             "happened in December 2020 when the CON fixed it at two"),
        indicatorsThatWouldAlter=[
            "the Army states a crew number in a published characteristic",
            "a soldier touchpoint finds a minimum crew below or above the design"],
        variedInSensitivity=False), H)

    g.put(cited(
        "alt-omfv-concept", "Alternative", SRC_CON, "section 'OMFV Characteristics'",
        now=NOW1,
        name="OMFV concept",
        description=("The vehicle the nine characteristics describe: a Bradley "
                     "replacement inside the Armored Brigade Combat Team, to be refined "
                     "with industry rather than specified up front (February 2020 "
                     "notice, Background and Concept of employment)."),
        status="candidate", baselineFlag=False, enteredOrder=1), H)

    g.put(cited(
        "alt-m2a4-bradley", "Alternative", SRC_GAO, gao_at(13), now=NOW1,
        name="modernized Bradley M2A4",
        description=("The status-quo vehicle. GAO printed p. 13: the Army's report "
                     "\"compared three government concepts for the OMFV with a "
                     "modernized version of the M2A4 Bradley\"."),
        status="candidate", baselineFlag=True, enteredOrder=2), H)


def _charter_and_policy(g: Graph) -> None:
    """The programme charter, its two undefined terms (F9), and the decision-class policy.

    The two gapped definitions are GAO printed p. 10: "The Army's report did not clearly
    define, however, force structure or operational concepts." They are recorded on the
    Charter because that is where this schema keeps scope terms, and they drive
    `definition-missing` — a warning, twice.
    """
    for gid, term, where in (
        ("gap-def-force-structure", "force structure", "printed p. 10"),
        ("gap-def-operational-concepts", "operational concepts", "printed p. 10"),
    ):
        g.put(cited(
            gid, "InsufficientEvidence", SRC_GAO, gao_at(10), now=NOW1,
            confidence="absent",
            sought=f"a definition of \"{term}\" as the Army's report uses it",
            whereLookedFor=[
                f"GAO-23-106549 {where} (PDF p. 13)",
                "the Army's Section 234 report, which is not public",
                "the February 2020 and December 2020 published characteristics"],
            whyNotFound=("The Army's report did not clearly define, however, force "
                         "structure or operational concepts. (GAO-23-106549 printed "
                         "p. 10)"),
            confirmedBy=CONFIRMED, impact="degrading",
            indicatorsThatWouldResolve=[
                "the Army publishes a definition with the force-structure analysis it "
                "says will follow in 18 to 24 months (GAO printed p. 10)"]), H)

    g.put(cited(
        CHARTER, "Charter", SRC_CON,
        "Background and Concept of employment; priority order from "
        f"{SRC_NARRATIVE} p. 6 section 3.2; undefined terms from {SRC_GAO} "
        f"{gao_at(10)}",
        now=NOW1, confidence="inferred",
        question=("What characteristics must the OMFV have, in what priority, to replace "
                  "the Bradley in the Armored Brigade Combat Team?"),
        decisionToBeMade=("the CON to A-CDD to PSPEC requirements chain for the OMFV: "
                          "which characteristics are published, in what order of "
                          "priority, and how industry concepts refine them into "
                          "requirements"),
        consequencesOfErroneousOutput=(
            "A fleet that cannot cross the bridges of the theatre it is bought for (the "
            "Weight characteristic sets an 80 percent trafficability target), cannot "
            "carry the squad it is built around (the December 2020 Manning "
            "characteristic fixes a platoon at 30 dismounts and a crew of two), or "
            "cannot be afforded. This paragraph is reconstructed: no public Army "
            "document states the consequences of getting the characteristics wrong, "
            "which is why this Charter is marked inferred."),
        questionClass="desired-characteristics",
        scope={
            "included": [
                "Survivability", "Mobility", "Growth", "Lethality", "Weight",
                "Logistics", "Transportability", "Manning", "Training",
                "the OMFV fighting as part of a section, platoon and company of "
                "mechanized infantry inside an ABCT (February 2020 notice, Concept of "
                "employment)"],
            "excluded": []},
        definitions=[
            {"term": "ABCT", "text": "Armored Brigade Combat Team"},
            {"term": "force structure", "text": {"$gap": "gap-def-force-structure"}},
            {"term": "operational concepts",
             "text": {"$gap": "gap-def-operational-concepts"}}],
        authority={"signer": "Next Generation Combat Vehicles Cross-Functional Team",
                   "board": "Army Futures Command"},
        successCriteria=[
            "characteristics stated broadly enough for industry to trade against",
            "a priority order industry can design to",
            "requirements refined through Phase 2 modelling and simulation rather than "
            "specified up front"],
        decisionClassPolicy=POLICY, mandateElements=[]), H)

    g.put(own(
        POLICY, "Policy", now=NOW1,
        name=("OMFV requirements-characteristics review, scored against GAO's own "
              "aggregation rule: GAO-23-106549 printed p. 17 (PDF p. 20) — \"we drew "
              "conclusions that the report was generally objective when available "
              "information presented in the report was consistent with our definition of "
              "objectivity but was missing information that would have addressed the "
              "generally accepted research standards\""),
        version="0.1",
        decisionClass="requirements-characteristics",
        # Schema-forced. The `method` enum offers mavt/ahp/topsis/pugh and has no value
        # for a requirements-refinement process that computes nothing. `mavt` is the
        # kernel's only implemented method and is recorded here so the plan steps have
        # something to agree with; no MAVT aggregation is ever run in this demonstration.
        method="mavt",
        tailoring="gao-23-106549",
        # Ruling R3: GAO's rule is "generally X unless a mapped question raises a real
        # concern", not "at most one question at state 2". An explicit k of 21 — one per
        # question in the published set — makes `generally_X` hold unless a mapped
        # question is at state 3 or 4, which is what printed p. 17 describes.
        aggregationK=21,
        requiredBiasChecks=["independent-disconfirming-review"],
        # False, and deliberately: `linchpin-not-varied` fires only where a sealed run
        # exists, and this record has none — the OMFV chain is a narrative record, not a
        # computed one. Setting it true would demand of the Army a sensitivity analysis
        # GAO did not ask for and would collide with the credit GAO did give (printed
        # p. 14).
        requireAllLinchpinsVaried=False,
        prohibitedExclusionReasons=["time-or-resource"],
        blockingRules=[],
        nSimplex=200), H)


def _december_objects(g: Graph) -> None:
    """The December 2020 replacements, created before the refresh that installs them.

    `open_refresh` validates its `replacements` map before it writes anything: every
    value must already be an object in the graph. So the three replacing objects and the
    document they came off are written here, at their own December date, and the refresh
    in `run.py` only maps the old ids onto them.
    """
    g.put(cited(
        "ev-con-2020-12", "Evidence", SRC_BRIEFING, slide(5, 6), now=NOW2,
        title=("OMFV Industry Day briefing, 9 December 2020 — Updated OMFV "
               "Characteristics (CON)"),
        evidenceType="Document",
        publisher="Department of the Army, Next Generation Combat Vehicles "
                  "Cross-Functional Team",
        published="2020-12-09", date="2020-12-09",
        pointer={"uri": slide_uri(5),
                 "custodian": "Department of the Army (DISTRIBUTION STATEMENT A: "
                              "approved for public release)"},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": "the updated desired characteristics for the OMFV",
            "questionClass": "desired-characteristics",
            "intendedUse": "industry day briefing"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Next Generation Combat Vehicles Cross-Functional Team",
                    "role": "issuing authority", "date": "2020-12-09"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=("the updated CON: the text that supersedes the February 2020 "
                         "characteristics")), H)

    g.put(cited(
        "obj-survivability-dec", "Objective", SRC_BRIEFING,
        f"{slide(5, 6)}, characteristic A; priorityRank from {SRC_NARRATIVE} p. 6 "
        "section 3.2 and the December slide's own statement that the nine "
        "characteristics are listed in order of priority "
        f"({slide(11, 13)})",
        now=NOW2, name="Survivability", description=SURVIVABILITY_DEC,
        priority="primary", priorityRank=1, provenance="ev-con-2020-12"), H)

    g.put(cited(
        "obj-manning-dec", "Objective", SRC_BRIEFING,
        f"{slide(5, 6)}, characteristic H", now=NOW2,
        name="Manning", description=MANNING_DEC, priority="primary", priorityRank=8,
        provenance="ev-con-2020-12"), H)

    g.put(cited(
        "as-manning-dec", "Assumption", SRC_BRIEFING, f"{slide(5, 6)}, characteristic H",
        now=NOW2,
        statement=("A platoon of OMFVs will transport 30 Soldiers that dismount from the "
                   "vehicles. Each OMFV vehicle will be crewed by no more than two "
                   "Soldiers who will be positioned in the hull."),
        linchpin=False,
        rationale=("the December 2020 updated CON states the platoon dismount count and "
                   "the crew size as design facts; the slide gives no derivation for "
                   "either number"),
        evidence="ev-con-2020-12",
        implicationsIfWrong=("a platoon that cannot put 30 soldiers on the ground, or a "
                             "two-soldier crew that cannot fight the vehicle, would "
                             "invalidate the concept the Phase 2 designs were built to"),
        indicatorsThatWouldAlter=[
            "a soldier touchpoint finds two crew insufficient",
            "a change in the Army's platoon structure or squad size"],
        variedInSensitivity=False), H)

    g.put(cited(
        "rt-con-update-2020-12", "RefreshTrigger", SRC_BRIEFING, slide(5, 6), now=NOW2,
        kind="assumption-changed",
        source=("OMFV Industry Day briefing, 9 December 2020, " + slide(5, 6)),
        description=("The updated CON restates Survivability and Manning. Survivability "
                     "loses the February clause on protecting the crew from CBRN "
                     "environments and becomes survivability against modern direct fire, "
                     "indirect fire and blast threats. Manning stops being \"the minimal "
                     "number of crew members required to fight and win\" and becomes 30 "
                     "dismounts per platoon and no more than two crew, positioned in the "
                     "hull. The slide gives no reason for either change."),
        detectedAt="2020-12-09",
        affected=["as-manning-feb", "obj-survivability", "obj-manning"]), H)


def _episode_1(g: Graph) -> None:
    g.put(own(
        PROGRAM, "DecisionProgram", now=NOW1,
        name="OMFV requirements decision, 2019-2023",
        charter=CHARTER, episodes=[EPISODE_1], refreshTriggers=[], diffs=[]), H)

    g.put(own(
        EPISODE_1, "DecisionEpisode", now=NOW1,
        program=PROGRAM, sequence=1, charter=CHARTER, lifecycleState="DRAFT",
        transitions=[],
        objectives=[oid for oid, _, _, _ in CHARACTERISTICS_FEB],
        alternatives=["alt-omfv-concept", "alt-m2a4-bradley"],
        groundRules=[], constraints=[],
        assumptions=["as-poland-bridges", "as-manning-feb"],
        evidenceRegister=["ev-con-2020-02", "ev-industry-day-narrative-2020-04",
                          "ev-breaking-defense"],
        scenarios=[], claims=[], risks=[], biasChecks=[], mandateElements=[],
        observations=[], weightSets=[], models=[], runs=[], flipAnalyses=[],
        narratives=[], asOf=AS_OF[1]), H)


def build() -> Graph:
    """The February 2020 record, plus everything the December refresh needs to exist."""
    g = Graph()
    _gaps(g)
    _episode_1_evidence(g)
    _objectives_and_measure(g)
    _assumptions_and_alternatives(g)
    _charter_and_policy(g)
    _december_objects(g)
    _episode_1(g)
    return g


# ---- episode 2: the December 2020 updated CON -------------------------------------
def revise_r2(g: Graph) -> None:
    """The human revision of the r2 episode, after `open_refresh` has installed the three
    December replacements.

    `open_refresh` copies the prior episode's reference lists with the replacements
    applied; it does not add ids. Everything new in December — the three Manning
    constraints, the typed exclusion for the dropped CBRN clause, and the three
    provenance inputs the slide names — is added here by a human revision.

    The provenance sentence is **not** in GAO-23-106549. It is on the December 2020
    briefing, PDF p. 11 (slide footer 13): "Publish Broad Updated Characteristics (CON) -
    Generated using threat analysis, market research, and the ABCT operational concept."
    So these three objects enter the register in December 2020, at episode 2, not in
    February and not from GAO.
    """
    for oid, statement, implications in (
        ("con-30-dismounts",
         "A platoon of OMFVs will transport 30 Soldiers that dismount from the vehicles.",
         "Thirty dismounts across a platoon fixes the seat count the design must carry "
         "and, with the two-crew constraint, fixes how many vehicles a platoon needs."),
        ("con-two-crew",
         "Each OMFV vehicle will be crewed by no more than two Soldiers.",
         "A crew of two is the December 2020 CON's answer to February's \"minimal number "
         "of crew members required to fight and win\"; every crew task above two has to "
         "be automated, remoted or dropped."),
        ("con-crew-in-hull",
         "The two crew members will be positioned in the hull.",
         "Crew in the hull removes the manned turret, which is what makes an unmanned or "
         "remote turret a design consequence of the Manning characteristic rather than a "
         "vendor preference."),
    ):
        g.put(cited(
            oid, "Constraint", SRC_BRIEFING, f"{slide(5, 6)}, characteristic H",
            now=NOW2, statement=statement, kind="physical", source="ev-con-2020-12",
            implications=implications), H)

    g.put(cited(
        "ex-cbrn-dropped", "Exclusion", SRC_BRIEFING, slide(5, 6), now=NOW2,
        target={"kind": "Measure", "label": "CBRN protection"},
        reasonType="superseded",
        reason=("the December 2020 updated CON states the Survivability characteristic "
                "without the February 2020 clause on protecting the crew and Soldiers "
                "from CBRN environments; the slide gives no reason for the change"),
        authority={"who": "Next Generation Combat Vehicles Cross-Functional Team",
                   "role": "requirements owner", "date": "2020-12-09"},
        retainedInStructure=True), H)

    # Created here, not in `build()`: an InsufficientEvidence nothing references is an
    # orphan gap, and orphan gaps hold G1 shut store-wide. A gap comes into existence at
    # the same moment as the slot it fills.
    g.put(cited(
        "gap-con-inputs", "InsufficientEvidence", SRC_BRIEFING, slide(11, 13), now=NOW2,
        confidence="absent",
        sought=("the threat analysis, the market research and the ABCT operational "
                "concept the December 2020 CON was generated from: which documents they "
                "are, who authored them, what threat set and what method"),
        whereLookedFor=[
            "OMFV Industry Day briefing, 9 December 2020, " + slide(11, 13),
            "the February 2020 and December 2020 published characteristics",
            "public web search, 2026-09-06"],
        whyNotFound=("the slide names the three inputs and nothing else about them: no "
                     "title, date, author, threat set, method or respondent set appears "
                     "in any public Army document"),
        confirmedBy=CONFIRMED, impact="degrading",
        indicatorsThatWouldResolve=[
            "the Army names or releases any of the three inputs",
            "a released A-CDD traces the characteristics back to a named threat "
            "analysis"]), H)

    provenance_reason = (
        "Publish Broad Updated Characteristics (CON) - Generated using threat analysis, "
        "market research, and the ABCT operational concept. (OMFV Industry Day briefing, "
        "9 December 2020, " + slide(11, 13) + ")")
    provenance_pointer = {
        "uri": slide_uri(11),
        "custodian": ("Department of the Army, NGCV CFT — the underlying analysis is not "
                      "public; the 9 December 2020 Industry Day briefing is the public "
                      "record that names it")}
    provenance_scope = {
        "builtToAnswer": "the inputs the Army used to generate the updated CON",
        "questionClass": "desired-characteristics",
        "intendedUse": "generation of the December 2020 updated characteristics"}

    g.put(cited(
        "ev-threat-analysis", "Evidence", SRC_BRIEFING, slide(11, 13), now=NOW2,
        title="Threat analysis used to generate the December 2020 updated CON",
        evidenceType="ThreatAnalysis", date="2020",
        pointer=provenance_pointer,
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity=provenance_scope, reviewStatus="reviewed",
        reviewers=[{"name": "Next Generation Combat Vehicles Cross-Functional Team",
                    "role": "issuing authority (no review record is public)",
                    "date": "2020-12-09"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=provenance_reason,
        threatSet={"$gap": "gap-con-inputs"},
        authority={"$gap": "gap-con-inputs"}), H)

    g.put(cited(
        "ev-market-research-2020", "Evidence", SRC_BRIEFING, slide(11, 13), now=NOW2,
        title="Market research used to generate the December 2020 updated CON",
        evidenceType="MarketResearch", date="2020",
        pointer=provenance_pointer,
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity=provenance_scope, reviewStatus="reviewed",
        reviewers=[{"name": "Next Generation Combat Vehicles Cross-Functional Team",
                    "role": "issuing authority (no review record is public)",
                    "date": "2020-12-09"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=provenance_reason,
        method={"$gap": "gap-con-inputs"},
        respondents={"$gap": "gap-con-inputs"}), H)

    g.put(cited(
        "ev-abct-opconcept", "Evidence", SRC_BRIEFING, slide(11, 13), now=NOW2,
        title="ABCT operational concept used to generate the December 2020 updated CON",
        evidenceType="Document", date="2020",
        pointer=provenance_pointer,
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity=provenance_scope, reviewStatus="reviewed",
        reviewers=[{"name": "Next Generation Combat Vehicles Cross-Functional Team",
                    "role": "issuing authority (no review record is public)",
                    "date": "2020-12-09"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=provenance_reason,
        publisher={"$gap": "gap-con-inputs"},
        published={"$gap": "gap-con-inputs"}), H)

    ep = g.get(EPISODE_2)
    revise(
        g, EPISODE_2, now=NOW2,
        constraints=["con-30-dismounts", "con-two-crew", "con-crew-in-hull"],
        evidenceRegister=ep["evidenceRegister"] + [
            "ev-con-2020-12", "ev-threat-analysis", "ev-market-research-2020",
            "ev-abct-opconcept"])


# ---- episode 3: the eleven analytical efforts -------------------------------------
VVA_SECTIONS = ("Problem Statement", "M&S Requirements and Acceptability Criteria",
                "M&S Assumptions, Capabilities, Limitations & Risks/Impacts",
                "Accreditation Methodology", "Issues", "Key Participants", "Resources",
                "Lessons Learned")

# The seven named efforts on the Phase 2 schedule, Dec 2020 briefing PDF p. 17 (slide
# footer 19): ARIES 1, MBL1, ARIES 2, TRAC AoA, HSI 1, HSI 2, TRAC OE. Their descriptions
# are on PDF p. 18 (slide footer 20).
ARIES_DESCRIPTION = (
    "ARIES / performance M&S - Highlights sensitivities between functional requirements "
    "in real time to inform the program. Analytics will be performed on mobility, "
    "vehicle dynamics, automotive performance, and under-hood cooling M&S.")
TRAC_OE_DESCRIPTION = (
    "TRAC Operational Effectiveness (OE) - TRAC OE analyzes how well the concept design "
    "performs in a combat scenario within an organization (e.g. Company/Battalion level) "
    "by conducting multiple runs of specific scenarios.")
JACK_DESCRIPTION = (
    "JACK modeling - A 10 week event to facilitate human factors analysis by Soldiers in "
    "a digital environment.")
CAVE_DESCRIPTION = (
    "Immersive Simulation modeling (CAVE) - CAVE support will provide Soldiers a first "
    "person perspective of the OMFV design.")

# GAO printed p. 10: the sentence that makes EXE-14 rate 3 rather than 4, and the reason
# `model_vva` emits `vva-verbal` rather than `model-vva`.
VVA_INTERVIEW = (
    "Army officials told us that the models and simulations informing the 11 analytical "
    "efforts had gone through the Army's standard verification, validation, and "
    "accreditation process to ensure their reliability. (GAO-23-106549 printed p. 10)")

MS_SCOPE = {
    "builtToAnswer": ("the desired characteristics for the OMFV — GAO printed p. 12: "
                      "\"these analyses were not designed to draw conclusions on force "
                      "structure alternatives. Instead, the analyses were intended to "
                      "assess the desired characteristics\""),
    "questionClass": "desired-characteristics",
    "intendedUse": "Phase 2 modelling, simulation and analysis"}


def _r3_gaps(g: Graph) -> None:
    g.put(cited(
        "gap-model-docs", "InsufficientEvidence", SRC_GAO, gao_at(9), now=NOW3,
        confidence="absent",
        sought=("the methodology, model description and documentation for the 11 "
                "analytical efforts"),
        whereLookedFor=[
            "GAO-23-106549 printed pp. 9-10 (PDF pp. 12-13)",
            "OMFV Industry Day briefing, 9 December 2020, " + slide(18, 20),
            "public web search, 2026-09-06"],
        whyNotFound=("the Army report did not clearly describe the methodology of these "
                     "efforts; the steps it took to ensure data reliability; or the "
                     "verification, validation, and accreditation of the models and "
                     "simulations it used (GAO-23-106549 printed p. 9)"),
        confirmedBy=CONFIRMED, impact="blocking",
        indicatorsThatWouldResolve=[
            "release of any MIL-STD-3022 accreditation report for ARIES or TRAC OE",
            "an Army model description published for either model"]), H)

    g.put(cited(
        "gap-touchpoint-fields", "InsufficientEvidence", SRC_GAO, gao_at(10), now=NOW3,
        confidence="absent",
        sought=("the sample size, selection rule, unit, dates, instrument and analysis "
                "method of each soldier touchpoint"),
        whereLookedFor=[
            "GAO-23-106549 printed pp. 8-11 (PDF pp. 11-14)",
            "OMFV Industry Day briefing, 9 December 2020, " + slide(18, 20),
            "Army regulation on soldier touchpoints, searched 2026-09-06"],
        whyNotFound=("neither the Army's report as GAO describes it nor any public Army "
                     "regulation specifies a method, sample size, instrument or analysis "
                     "standard for a soldier touchpoint (GAO-23-106549 printed "
                     "pp. 9-10)"),
        confirmedBy=CONFIRMED, impact="blocking",
        indicatorsThatWouldResolve=[
            "an Army human-systems-integration plan for the OMFV touchpoints",
            "release of the touchpoint reports"]), H)

    g.put(cited(
        "gap-vendor-events", "InsufficientEvidence", SRC_GAO, gao_at(8), now=NOW3,
        confidence="absent",
        sought="which vendors attended which of the four vendor feedback events, and when",
        whereLookedFor=["GAO-23-106549 printed p. 8 (PDF p. 11)",
                        "public web search, 2026-09-06"],
        whyNotFound=("GAO reports that \"the Army conducted four vendor feedback events "
                     "that provided the Army and its industry partners with "
                     "opportunities to exchange concepts and comments\" and names "
                     "neither the vendors nor the events"),
        confirmedBy=CONFIRMED, impact="degrading",
        indicatorsThatWouldResolve=["an Army list of the Phase 2 vendor feedback events"]), H)

    g.put(cited(
        "gap-234-report", "InsufficientEvidence", SRC_GAO, gao_at(8), now=NOW3,
        confidence="absent",
        sought="the Army's Section 234 report, March 2023",
        whereLookedFor=["GAO-23-106549, which describes it throughout",
                        "public web search, 2026-09-06"],
        whyNotFound=("the report is not public and never was: it is a report to the "
                     "congressional defense committees. Everything this record holds "
                     "about it is a reconstruction from GAO's description"),
        confirmedBy=CONFIRMED, impact="degrading",
        indicatorsThatWouldResolve=["public release of the Section 234 report"]), H)

    g.put(cited(
        "gap-additional-studies", "InsufficientEvidence", SRC_GAO, gao_at(13), now=NOW3,
        confidence="absent",
        sought=("the author, performing organisation and method of the three additional "
                "studies GAO names at printed p. 13"),
        whereLookedFor=["GAO-23-106549 printed p. 13 (PDF p. 16)",
                        "public web search, 2026-09-06"],
        whyNotFound=("GAO names the three studies by subject and year and nothing else: "
                     "\"(1) a 2018 Bradley size, weight, power, and cooling growth "
                     "study; (2) a study to support the program's market research in "
                     "2020; and (3) a study to support concept design in 2021\""),
        confirmedBy=CONFIRMED, impact="degrading",
        indicatorsThatWouldResolve=["the Army names or releases any of the three"]), H)

    g.put(cited(
        "gap-trac-aoa-model", "InsufficientEvidence", SRC_GAO, gao_at(11), now=NOW3,
        confidence="absent",
        sought=("which model the September 2021 TRAC study named at GAO printed p. 11 "
                "was run on"),
        whereLookedFor=["GAO-23-106549 printed pp. 10-12 (PDF pp. 13-15)",
                        "OMFV Industry Day briefing, 9 December 2020, "
                        + slide(17, 19) + " and " + slide(18, 20),
                        "public web search, 2026-09-06"],
        whyNotFound=("GAO names the study by date and performer and says nothing about "
                     "the model under it. The December 2020 Phase 2 schedule carries two "
                     "TRAC line items, \"TRAC AoA\" and \"TRAC OE\", and slide footer 20 "
                     "describes a model called TRAC OE; nothing public says that the "
                     "September 2021 study ran on it. Recording `mdl-trac` here would "
                     "have asserted that, so the slot is a gap"),
        confirmedBy=CONFIRMED, impact="degrading",
        indicatorsThatWouldResolve=[
            "an Army or TRAC publication naming the model behind the September 2021 "
            "study"]), H)

    g.put(cited(
        "gap-unnamed-efforts", "InsufficientEvidence", SRC_GAO, gao_at(8), now=NOW3,
        confidence="absent",
        sought=("the identity of the four of GAO's eleven analytical efforts that no "
                "public document names"),
        whereLookedFor=["GAO-23-106549 printed pp. 8-14 (PDF pp. 11-17)",
                        "OMFV Industry Day briefing, 9 December 2020, "
                        + slide(17, 19) + " and " + slide(18, 20),
                        "public web search, 2026-09-06"],
        whyNotFound=("GAO counts \"seven previously conducted analytical studies\" and "
                     "four soldier touchpoints — eleven analytical efforts (printed "
                     "p. 8) — and names only some of them. The December 2020 Phase 2 "
                     "schedule names seven: ARIES 1, ARIES 2, TRAC AoA, TRAC OE, MBL1, "
                     "HSI 1 and HSI 2. Seven is what this record holds; the other four "
                     "are named in no public document and are not invented here"),
        confirmedBy=CONFIRMED, impact="degrading",
        indicatorsThatWouldResolve=[
            "public release of the Section 234 report, which lists all eleven",
            "an Army list of the Phase 2 modelling, simulation and analysis efforts"]), H)

    g.put(own(
        "gap-weights", "InsufficientEvidence", now=NOW3,
        confidence="absent",
        sought=("a published weighting across the nine OMFV characteristics or the 28 "
                "prioritized attributes"),
        whereLookedFor=["GAO-23-106549 printed p. 8 (PDF p. 11), which states that the "
                        "28 attributes were prioritized but does not publish them",
                        "the February and December 2020 published characteristics"],
        whyNotFound=("the Army published a priority ORDER over the nine characteristics "
                     "and never a set of weights; the equal weighting this record's "
                     "WeightSet carries is ours, not the Army's"),
        confirmedBy=CONFIRMED, impact="degrading",
        indicatorsThatWouldResolve=["release of the 28 prioritized attributes with their "
                                    "relative weights"]), H)


def _models_and_vva(g: Graph) -> None:
    """The two named models, and the two VV&A records GAO's interview sentence produces.

    `accreditationDecision.basis` is `interview`, because that is exactly what the record
    is: officials told GAO the process had been followed. That drives the `vva-verbal`
    warning and EXE-14 state 3 under `published-21-plus-vva` — F5. Every other MIL-STD-3022
    field, and every section's content, is the same gap object: F7, and EXE-8 = 4.

    `accreditationDecision.date` is `"2021"` and is inferred — GAO gives no date for the
    accreditations, only that they happened before the March 2023 report. Against the
    March 2023 `asOf` that is inside three years, so `ReaccreditationRequired` does not
    fire and does not mask F5. If the real date were earlier the reaccreditation warning
    would fire too; nothing in this record turns on which.
    """
    for vid, model_name in (("vva-aries", "ARIES / performance M&S"),
                            ("vva-trac", "TRAC Operational Effectiveness (OE)")):
        g.put(cited(
            vid, "VVARecord", SRC_GAO, gao_at(10), now=NOW3, confidence="inferred",
            problemStatement=CHARTER,
            requirementsAndAcceptabilityCriteria={"$gap": "gap-model-docs"},
            assumptionsCapabilitiesLimitationsRisks={
                "assumptions": {"$gap": "gap-model-docs"},
                "capabilities": {"$gap": "gap-model-docs"},
                "limitations": {"$gap": "gap-model-docs"},
                "risks": {"$gap": "gap-model-docs"}},
            methodology={"$gap": "gap-model-docs"},
            accreditationDecision={
                "authority": ("Army officials, the Army's standard verification, "
                              "validation and accreditation process"),
                "date": "2021",
                "scope": ("the models and simulations informing the 11 analytical "
                          f"efforts, of which {model_name} is one"),
                "basis": "interview"},
            sections=[{"name": name, "content": {"$gap": "gap-model-docs"}}
                      for name in VVA_SECTIONS]), H)

    g.put(cited(
        "mdl-aries", "Model", SRC_BRIEFING, slide(18, 20), now=NOW3,
        name="ARIES / performance M&S",
        # `definition.version` is required and is NOT a slot, so a gap marker fails the
        # schema. The string says what the record says: nobody published a version.
        definition={"kind": "simulation", "version": "unversioned in the public record"},
        intendedUse=ARIES_DESCRIPTION,
        questionClass="desired-characteristics",
        vvaRecord="vva-aries", qualificationStatus="draft",
        limitations=[
            {"statement": ("The public record describes what ARIES highlights, not how "
                           "it computes it."),
             "justification": {"$gap": "gap-model-docs"}}]), H)

    g.put(cited(
        "mdl-trac", "Model", SRC_BRIEFING, slide(18, 20), now=NOW3,
        name="TRAC Operational Effectiveness (OE)",
        definition={"kind": "simulation", "version": "unversioned in the public record"},
        intendedUse=TRAC_OE_DESCRIPTION,
        questionClass="desired-characteristics",
        vvaRecord="vva-trac", qualificationStatus="draft",
        limitations=[
            {"statement": ("The public record describes the scenario runs, not the "
                           "combat model underneath them."),
             "justification": {"$gap": "gap-model-docs"}}]), H)


def _ms_study(oid: str, title: str, *, artifact: str, locator: str,
              model: str | dict, vva: str, inclusion: str, pointer_uri: str,
              custodian: str, date: str | None = None,
              confidence: str = "explicit") -> dict:
    fields = dict(
        title=title, evidenceType="MSStudy",
        pointer={"uri": pointer_uri, "custodian": custodian},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity=MS_SCOPE, reviewStatus="reviewed",
        reviewers=[{"name": "Department of the Army", "role": "performing organisation "
                    "(no review record is public)", "date": date or "2021"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=inclusion,
        model=model, scenarios={"$gap": "gap-model-docs"}, vvaRecord=vva)
    if date:
        fields["date"] = date
    return cited(oid, "Evidence", artifact, locator, now=NOW3, confidence=confidence,
                 **fields)


def _touchpoint(oid: str, title: str, *, artifact: str, locator: str, inclusion: str,
                pointer_uri: str, custodian: str, dates, date: str | None = None,
                confidence: str = "explicit") -> dict:
    fields = dict(
        title=title, evidenceType="SoldierTouchpoint",
        pointer={"uri": pointer_uri, "custodian": custodian},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity=MS_SCOPE, reviewStatus="reviewed",
        reviewers=[{"name": "Department of the Army", "role": "performing organisation "
                    "(no review record is public)", "date": date or "2021"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=inclusion,
        n={"$gap": "gap-touchpoint-fields"},
        selectionRule={"$gap": "gap-touchpoint-fields"},
        unit={"$gap": "gap-touchpoint-fields"},
        instrument={"$gap": "gap-touchpoint-fields"},
        dates=dates,
        analysisMethod={"$gap": "gap-touchpoint-fields"})
    if date:
        fields["date"] = date
    return cited(oid, "Evidence", artifact, locator, now=NOW3, confidence=confidence,
                 **fields)


ARMY_CUSTODIAN = ("Department of the Army (the study itself is not public); the cited "
                  "document is the public record that names it")


def _r3_evidence(g: Graph) -> None:
    """The eleven analytical efforts, the four vendor feedback events and the three
    additional studies, as the public record has them.

    Two pointer conventions, and the difference matters. An effort GAO or the Army names
    in a public document gets a pointer *to that public document*, with a custodian line
    saying the study itself is the Army's and is not public — the pointer locates the
    record of the study, not the study. An effort nothing public names beyond the Section
    234 report gets a gapped pointer. Neither is a claim that an Army file is public.
    """
    for oid, label in (("ev-aries-1", "ARIES 1"), ("ev-aries-2", "ARIES 2")):
        g.put(_ms_study(
            oid, f"{label} — ARIES / performance modelling and simulation, OMFV Phase 2",
            artifact=SRC_BRIEFING, locator=f"{slide(17, 19)} (timeline); {slide(18, 20)} "
                                          "(description)",
            model="mdl-aries", vva="vva-aries",
            inclusion=("named on the OMFV Phase 2 schedule as one of the Phase 2 MS&A "
                       f"activities ({slide(17, 19)}); {ARIES_DESCRIPTION}"),
            pointer_uri=slide_uri(17), custodian=ARMY_CUSTODIAN), H)

    g.put(_ms_study(
        "ev-trac-aoa",
        "TRAC AoA — a September 2021 study conducted by the Army's Research and Analysis "
        "Center (TRAC); identified with the \"TRAC AoA\" line on the December 2020 "
        "Phase 2 schedule by US, not by GAO",
        artifact=SRC_GAO, locator=f"{gao_at(11)}; named on the Phase 2 schedule at "
                                  f"{SRC_BRIEFING} {slide(17, 19)}",
        model={"$gap": "gap-trac-aoa-model"}, vva="vva-trac", date="2021-09",
        confidence="inferred",
        inclusion=("GAO printed p. 11: the report noted the Army used \"a September 2021 "
                   "study conducted by the Army's Research and Analysis Center (TRAC)\", "
                   "one of the two of the 11 analytical efforts the force-structure "
                   "observations rely on. GAO does not tie that study to either of the "
                   "two TRAC line items on the December 2020 Phase 2 schedule; tying it "
                   "to \"TRAC AoA\" is OURS, and the schedule's own placement points the "
                   "other way (see the README's schedule paragraph). Marked inferred for "
                   "that reason"),
        pointer_uri=gao(11), custodian=ARMY_CUSTODIAN), H)

    g.put(_ms_study(
        "ev-trac-oe",
        "TRAC Operational Effectiveness (Dec 2020 Industry Day slide, "
        f"{slide(18, 20)}) — inferred by us to be the second TRAC study GAO describes at "
        "printed p. 11; GAO does not name it",
        artifact=SRC_BRIEFING, locator=f"{slide(17, 19)} (timeline); {slide(18, 20)} "
                                      f"(description); GAO {gao_at(11)} (the second "
                                      "TRAC study, unnamed)",
        model="mdl-trac", vva="vva-trac", confidence="inferred",
        inclusion=("GAO printed p. 11: \"a second TRAC study expanded on the first, and "
                   "added another scenario with different terrain and details from a "
                   "vendor's concepts.\" GAO never names it. The identification with the "
                   "\"TRAC OE\" entry on the December 2020 Phase 2 schedule is OURS, and "
                   "this object is marked inferred for that reason"),
        pointer_uri=slide_uri(18), custodian=ARMY_CUSTODIAN), H)

    g.put(_touchpoint(
        "ev-mbl-1",
        "MBL1 — the July 2021 soldier touchpoint conducted by the Maneuver Battle Lab "
        "within the Maneuver Capabilities Development and Integration Directorate; "
        "identified with the \"MBL1\" line on the December 2020 Phase 2 schedule by US, "
        "not by GAO",
        artifact=SRC_GAO, locator=f"{gao_at(11)}; named on the Phase 2 schedule at "
                                  f"{SRC_BRIEFING} {slide(17, 19)}",
        inclusion=("GAO printed p. 11: one of the two of the 11 analytical efforts the "
                   "force-structure observations rely on. MBL1 is the only Maneuver "
                   "Battle Lab item on the December 2020 schedule, so the identification "
                   "is a safe inference — but it is still OURS, and the schedule places "
                   "MBL1 around April 2021 against GAO's July 2021"),
        pointer_uri=gao(11), custodian=ARMY_CUSTODIAN, confidence="inferred",
        dates="2021-07", date="2021-07"), H)

    g.put(_touchpoint(
        "ev-hsi-1", "HSI 1 — JACK human factors modelling",
        artifact=SRC_BRIEFING, locator=f"{slide(17, 19)}; {slide(18, 20)}",
        inclusion=("named on the OMFV Phase 2 schedule as a Phase 2 MS&A activity "
                   f"({slide(17, 19)}); {JACK_DESCRIPTION}. Slide footer 20 lists six "
                   "MS&A activities against seven timeline items and never maps HSI 1 "
                   "onto JACK; that mapping is OURS"),
        pointer_uri=slide_uri(18), custodian=ARMY_CUSTODIAN, confidence="inferred",
        dates={"$gap": "gap-touchpoint-fields"}), H)

    g.put(_touchpoint(
        "ev-hsi-2", "HSI 2 — Immersive Simulation modelling (CAVE)",
        artifact=SRC_BRIEFING, locator=f"{slide(17, 19)}; {slide(18, 20)}",
        inclusion=("named on the OMFV Phase 2 schedule as a Phase 2 MS&A activity "
                   f"({slide(17, 19)}); {CAVE_DESCRIPTION}. Slide footer 20 never maps "
                   "HSI 2 onto the CAVE immersive simulation; that mapping is OURS"),
        pointer_uri=slide_uri(18), custodian=ARMY_CUSTODIAN, confidence="inferred",
        dates={"$gap": "gap-touchpoint-fields"}), H)

    for n in (1, 2, 3, 4):
        g.put(cited(
            f"ev-vendor-feedback-{n}", "Evidence", SRC_GAO, gao_at(8), now=NOW3,
            title=f"Vendor feedback event {n} of 4",
            evidenceType="VendorFeedback",
            pointer={"uri": gao(8), "custodian": ARMY_CUSTODIAN},
            classification={"level": "U", "metadataLevel": "U"},
            scopeOfValidity={
                "builtToAnswer": "the desired characteristics for the OMFV",
                "questionClass": "desired-characteristics",
                "intendedUse": ("exchange of concepts and comments between the Army and "
                                "its industry partners")},
            reviewStatus="reviewed",
            reviewers=[{"name": "Department of the Army", "role": "convening authority "
                        "(no review record is public)", "date": "2021"}],
            reliabilitySteps={"$gap": "gap-reliability-steps"},
            inclusionReason=("GAO printed p. 8: \"the report noted that the Army "
                             "conducted four vendor feedback events that provided the "
                             "Army and its industry partners with opportunities to "
                             "exchange concepts and comments\""),
            vendors={"$gap": "gap-vendor-events"},
            event={"$gap": "gap-vendor-events"}), H)


# GAO printed p. 13, verbatim: "(1) a 2018 Bradley size, weight, power, and cooling
# growth study; (2) a study to support the program's market research in 2020; and (3) a
# study to support concept design in 2021."
ADDITIONAL_STUDIES = [
    ("ev-bradley-swapc-2018",
     "a 2018 Bradley size, weight, power, and cooling growth study", "2018"),
    ("ev-market-research-study-2020",
     "a study to support the program's market research in 2020", "2020"),
    ("ev-concept-design-2021", "a study to support concept design in 2021", "2021"),
]


def _additional_studies(g: Graph) -> None:
    """The three additional studies — F3.

    Each object **omits the `inclusionReason` key entirely**, which is the finding:
    `inclusion-reason-missing` fires on a *cited* evidence object that does not say why
    it was included. GAO printed p. 13: "While these studies are used to support the
    comparison, the report does not, however, describe how the Army chose the three
    studies it presented."

    They are `Document`, not `MSStudy`. GAO names them by subject and year and says
    nothing about their method; typing them as modelling and simulation studies would
    assert something the record does not contain.
    """
    for oid, description, year in ADDITIONAL_STUDIES:
        g.put(cited(
            oid, "Evidence", SRC_GAO, gao_at(13), now=NOW3,
            title=description[0].upper() + description[1:],
            evidenceType="Document",
            publisher={"$gap": "gap-additional-studies"},
            published=year, date=year,
            pointer={"uri": gao(13), "custodian": ARMY_CUSTODIAN},
            classification={"level": "U", "metadataLevel": "U"},
            scopeOfValidity={
                "builtToAnswer": ("the combat effectiveness comparison between the OMFV "
                                  "concepts and the modernized Bradley"),
                "questionClass": "combat-effectiveness",
                "intendedUse": "support to the Section 234 comparison"},
            reviewStatus="reviewed",
            reviewers=[{"name": "Department of the Army", "role": "performing "
                        "organisation (no review record is public)", "date": year}],
            reliabilitySteps={"$gap": "gap-reliability-steps"}), H)


PLAN_AUTHORITY = {
    "document": "OMFV Industry Day briefing, 9 December 2020",
    "paragraph": f"Phase 2 MS&A Activities, {slide(18, 20)}"}


def _plan(oid: str, episode: str, *, now: str, steps: list[str], approved: str,
          authority: dict = None) -> dict:
    """One episode's Plan.

    Every episode needs its own: `Plan.episode` is a required ref, so one Plan cannot
    serve two, and `open_refresh` does not carry `plan` forward. Each step's `method`
    equals `pol-omfv.method` because G2's `policy-method-matches` requires it — see the
    schema-forced note on the policy.
    """
    evaluators = {"aries": "mdl-aries", "trac": "mdl-trac"}
    return own(
        oid, "Plan", now=now, episode=episode, policyBasis=POLICY,
        steps=[{"id": s, "evaluator": evaluators[s], "method": "mavt",
                "alternatives": ["alt-omfv-concept", "alt-m2a4-bradley"],
                "measures": ["m-weight-bridges"], "weightSet": "ws-omfv",
                "authority": authority or PLAN_AUTHORITY}
               for s in steps],
        approvedBy={"actorId": "Next Generation Combat Vehicles Cross-Functional Team",
                    "date": approved},
        confidence="inferred")


def trigger_r3(g: Graph) -> None:
    """`rt-phase2-efforts`, written just before the refresh it opens.

    `RefreshTrigger.affected` is a reference list, so every id in it must resolve — which
    is why the trigger is written here, after the December replacements exist, and not in
    `build()`.
    """
    g.put(cited(
        "rt-phase2-efforts", "RefreshTrigger", SRC_BRIEFING, slide(17, 19), now=NOW3,
        kind="evidence-changed",
        source=("OMFV Industry Day briefing, 9 December 2020, " + slide(17, 19) + " and "
                + slide(18, 20) + "; GAO-23-106549 " + gao_at(8)),
        description=("The Phase 2 modelling, simulation and analysis programme runs: "
                     "ARIES 1, MBL1, ARIES 2, TRAC AoA, HSI 1, HSI 2 and TRAC OE, with "
                     "four vendor feedback events alongside. GAO printed p. 8 counts the "
                     "result as \"seven previously conducted analytical studies\" and "
                     "four soldier touchpoints — the report's \"11 analytical efforts\". "
                     "The characteristics are unchanged; what changes is the evidence "
                     "under them."),
        detectedAt="2021-09-30",
        affected=["obj-survivability-dec", "obj-mobility", "obj-growth", "obj-lethality",
                  "obj-weight", "obj-logistics", "obj-transportability",
                  "obj-manning-dec", "obj-training"]), H)


def revise_r3(g: Graph) -> None:
    """The human revision of the r3 episode: the eleven analytical efforts enter the
    record, and with them the gaps GAO found in how they were described.

    `open_refresh` was called with an empty `replacements` map, because nothing was
    replaced: the characteristics of December 2020 are still the characteristics of
    September 2021. `diff_episodes` therefore reports `pairing: "unknown"` and
    `changed: []`, which is the honest reading — see the README's diff-semantics section.
    """
    _r3_gaps(g)
    _models_and_vva(g)
    _r3_evidence(g)
    _additional_studies(g)

    # Seven of GAO's eleven analytical efforts are named in a public document; four are
    # not. The arithmetic was already in `rt-phase2-efforts.description`; this puts the
    # shortfall in the record as a first-class gap rather than only in prose. It is
    # recorded here, at episode 3, because that is when the efforts enter the record —
    # the charter of February 2020 could not have named a gap that did not yet exist.
    ch = g.get(CHARTER)
    revise(g, CHARTER, now=NOW3, limitations=[
        {"statement": ("GAO counts eleven analytical efforts behind the Army's report — "
                       "\"seven previously conducted analytical studies\" and four "
                       f"soldier touchpoints ({gao_at(8)}). Seven of the eleven are "
                       "named in a public document and are in this record: ARIES 1, "
                       "ARIES 2, TRAC AoA, TRAC OE, MBL1, HSI 1 and HSI 2. The other "
                       "four are named nowhere public and are not invented here."),
         "mitigation": {"$gap": "gap-unnamed-efforts"}},
        *(ch.get("limitations") or [])])

    g.put(own(
        "ws-omfv", "WeightSet", now=NOW3, confidence="inferred",
        name="equal weighting over the one published OMFV metric",
        method="equal", weights={"m-weight-bridges": 1.0},
        provenance={"$gap": "gap-weights"}), H)

    g.put(_plan("pl-omfv-r3", EPISODE_3, now=NOW3, steps=["aries", "trac"],
                approved="2020-12-09"), H)

    ep = g.get(EPISODE_3)
    revise(
        g, EPISODE_3, now=NOW3,
        evidenceRegister=ep["evidenceRegister"] + [
            "ev-aries-1", "ev-aries-2", "ev-trac-aoa", "ev-trac-oe", "ev-mbl-1",
            "ev-hsi-1", "ev-hsi-2",
            "ev-vendor-feedback-1", "ev-vendor-feedback-2", "ev-vendor-feedback-3",
            "ev-vendor-feedback-4",
            "ev-bradley-swapc-2018", "ev-market-research-study-2020",
            "ev-concept-design-2021"],
        models=["mdl-aries", "mdl-trac"],
        weightSets=["ws-omfv"],
        plan="pl-omfv-r3")


# ---- episode 4 and the three sections GAO graded ----------------------------------
def trigger_r4(g: Graph) -> None:
    g.put(cited(
        "rt-234-report", "RefreshTrigger", SRC_GAO, gao_at(8), now=NOW4,
        kind="evidence-changed",
        source=("Army Section 234 report, March 2023 — reconstructed from "
                "GAO-23-106549"),
        description=("The Army reports to the congressional defense committees under "
                     "Section 234 of the FY2022 NDAA. The report identifies nine desired "
                     "characteristics and 28 prioritized attributes, presents preliminary "
                     "observations on force structure and operational concepts, and "
                     "compares the combat effectiveness of three OMFV concepts with the "
                     "modernized Bradley M2A4. The report is the Army's own product, not "
                     "an external finding, which is why this trigger is "
                     "`evidence-changed`."),
        detectedAt="2023-03-31",
        affected=["obj-survivability-dec", "obj-mobility", "obj-growth", "obj-lethality",
                  "obj-weight", "obj-logistics", "obj-transportability",
                  "obj-manning-dec", "obj-training",
                  "alt-omfv-concept", "alt-m2a4-bradley"]), H)


def revise_r4(g: Graph) -> None:
    """The March 2023 report enters the record as an object nothing cites.

    `ev-234-report` has a gapped pointer, because the report is not public. It is covered
    by a typed Exclusion so `silent-omission` does not fire on it, and **no Claim cites
    it**: a claim resting on a gapped pointer fires `NotAssessableAtLevel`, which would
    put a second F4-shaped finding on every section and blur the one GAO actually made.
    """
    g.put(cited(
        "ev-234-report", "Evidence", SRC_GAO, gao_at(8), now=NOW4, confidence="inferred",
        title=("Department of the Army, report to the congressional defense committees "
               "under Section 234 of the National Defense Authorization Act for Fiscal "
               "Year 2022, March 2023"),
        evidenceType="Document",
        publisher="Department of the Army", published="2023-03", date="2023-03",
        pointer={"$gap": "gap-234-report"},
        classification={"level": "U",
                        "caveats": ["not publicly released; its release status has not "
                                    "been verified by this project"],
                        "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("the desired characteristics, the force structure designs "
                              "and operational concepts, and the combat effectiveness of "
                              "the OMFV compared with the modernized Bradley"),
            "questionClass": "desired-characteristics",
            "intendedUse": "the Army's report to the congressional defense committees"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Department of the Army", "role": "issuing authority",
                    "date": "2023-03"}],
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=("the document GAO-23-106549 assesses; everything this record "
                         "holds about March 2023 is a reconstruction from GAO's "
                         "description of it")), H)

    g.put(cited(
        "ex-234-report-not-public", "Exclusion", SRC_GAO, gao_at(8), now=NOW4,
        target={"kind": "Evidence", "id": "ev-234-report",
                "label": "the Army's March 2023 Section 234 report"},
        reasonType="data-unavailable",
        reason=("the report is a report to the congressional defense committees and is "
                "not public; no claim in this record rests on it, because a claim "
                "resting on a gapped pointer cannot be assessed at any level"),
        authority={"who": "shreyash", "role": "reconstruction author",
                   "date": "2026-09-06"},
        retainedInStructure=True), H)

    # GAO printed p. 13: the report "compared three government concepts for the OMFV with
    # a modernized version of the M2A4 Bradley". Both alternatives were evaluated.
    revise(g, "alt-m2a4-bradley", now=NOW4, status="evaluated")
    revise(g, "alt-omfv-concept", now=NOW4, status="evaluated")

    g.put(_plan("pl-omfv-r4", EPISODE_4, now=NOW4, steps=["aries", "trac"],
                approved="2023-03-31"), H)

    ep = g.get(EPISODE_4)
    revise(g, EPISODE_4, now=NOW4,
           evidenceRegister=ep["evidenceRegister"] + ["ev-234-report"],
           plan="pl-omfv-r4")


NINE_AT_R4 = ["obj-survivability-dec", "obj-mobility", "obj-growth", "obj-lethality",
              "obj-weight", "obj-logistics", "obj-transportability", "obj-manning-dec",
              "obj-training"]


def _sub_episode_claims(g: Graph) -> None:
    """The claims of the three sections GAO graded, each in the section GAO put it in."""
    g.put(cited(
        "cl-nine-characteristics", "Claim", SRC_GAO, gao_at(8), now=NOW4,
        text=("The Army's report identified nine desired characteristics for the OMFV "
              "and prioritized 28 attributes derived from these characteristics."),
        questionClass="desired-characteristics", assessableAt={"level": "U"},
        supportedBy=[{"evidence": "ev-con-2020-02"}, {"evidence": "ev-threat-analysis"},
                     {"evidence": "ev-market-research-2020"},
                     {"evidence": "ev-abct-opconcept"}],
        addresses=list(NINE_AT_R4), section="objectives-and-measures"), H)

    g.put(cited(
        "cl-weight-threshold", "Claim", SRC_GAO, gao_at(9), now=NOW4,
        # `inferred`: GAO printed p. 9 reports the Poland assumption and the missing data
        # and methods behind it, and the February notice states the Weight characteristic
        # — but no source writes this sentence. It is our composition of the two.
        confidence="inferred",
        text=("The Weight characteristic's 80 percent trafficability target is set "
              "against a bridge population the record represents by Poland."),
        questionClass="desired-characteristics", assessableAt={"level": "U"},
        # Both the February 2020 notice, which publishes the Weight characteristic, and
        # the trade-press article, which is where the Poland figure appears.
        #
        # An earlier revision cited the press article alone, on the stated ground that
        # citing the CON "would paper over `as-poland-bridges`'s gap ... F6 would
        # disappear behind a citation that does not answer it". Measured, that is false:
        # `linchpin-unevidenced` reads the Assumption's own `evidence` field, never the
        # Claim's `supportedBy`, so nothing was ever at risk. Adding the CON leaves every
        # per-question state on `dc` identical and F6 still fires on `as-poland-bridges`.
        # Recording an Army requirements claim as resting on Breaking Defense and nothing
        # else would have been a false statement about the record, made for a reason that
        # does not hold.
        supportedBy=[{"evidence": "ev-con-2020-02"},
                     {"evidence": "ev-breaking-defense"}],
        addresses=["obj-weight"], section="objectives-and-measures"), H)

    g.put(cited(
        "cl-force-structure-improves", "Claim", SRC_GAO, gao_at(12), now=NOW4,
        text=("The first TRAC analysis found that a different force structure improved "
              "survivability and lethality, and the Maneuver Battle Lab analysis drew "
              "similar conclusions."),
        questionClass="force-structure", assessableAt={"level": "U"},
        # No `reuseJustification` on either entry, and that is the finding: GAO printed
        # p. 12 — "these analyses were not designed to draw conclusions on force
        # structure alternatives. Instead, the analyses were intended to assess the
        # desired characteristics."
        supportedBy=[{"evidence": "ev-trac-aoa"}, {"evidence": "ev-mbl-1"}],
        addresses=["obj-survivability-dec", "obj-lethality"],
        section="evaluation-results"), H)

    g.put(cited(
        "cl-concepts-outperform-m2a4", "Claim", SRC_GAO, gao_at(13), now=NOW4,
        text=("The report compared three government concepts for the OMFV with a "
              "modernized version of the M2A4 Bradley and presented findings on the "
              "survivability and force protection, mobility, lethality, payload, and "
              "operational effectiveness of the four vehicles."),
        questionClass="combat-effectiveness", assessableAt={"level": "U"},
        supportedBy=[{"evidence": "ev-ce-metrics"}] +
                    [{"evidence": oid} for oid, _, _ in ADDITIONAL_STUDIES],
        addresses=list(NINE_AT_R4), section="evaluation-results"), H)


def _combat_effectiveness_objects(g: Graph) -> None:
    """The withheld metrics (F4) and the sensitivity credit GAO gave (printed p. 14)."""
    g.put(cited(
        "gap-ce-metrics-pointer", "InsufficientEvidence", SRC_GAO, gao_at(14), now=NOW4,
        confidence="absent",
        sought=("a locator, custodian and schema for the quantitative survivability, "
                "mobility and lethality metrics behind the combat-effectiveness "
                "comparison"),
        whereLookedFor=["GAO-23-106549 printed p. 14 (PDF p. 17)",
                        "the Army's Section 234 report, which is not public"],
        whyNotFound=("Army officials told us, however, that they had quantitative "
                     "metrics for each of these characteristics and used them in support "
                     "of the report. The officials stated that they did not include "
                     "these metrics in the report due to security concerns. "
                     "(GAO-23-106549 printed p. 14)"),
        confirmedBy=CONFIRMED, impact="blocking",
        indicatorsThatWouldResolve=[
            "a classified annex is identified with a CDRL number and a custodian, so the "
            "metrics can be located even where the values cannot be read",
            "release of the metrics at a lower classification"]), H)

    g.put(cited(
        "ev-ce-metrics", "Evidence", SRC_GAO, gao_at(14), now=NOW4, confidence="inferred",
        title=("quantitative survivability, mobility and lethality metrics for the four "
               "vehicles, held by the Army and not included in the report"),
        evidenceType="Dataset", date="2023-03",
        pointer={"$gap": "gap-ce-metrics-pointer"},
        # The VALUE is classified; that is not the finding. The finding is that the
        # record gives no way to locate it, which is what makes the claim resting on it
        # unassessable even at the level the claim itself claims.
        classification={"level": "S", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("the combat effectiveness of the OMFV concepts against the "
                              "modernized Bradley"),
            "questionClass": "combat-effectiveness",
            "intendedUse": "the Section 234 comparison"},
        reviewStatus="draft",
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=("GAO printed p. 14: the officials \"had quantitative metrics for "
                         "each of these characteristics and used them in support of the "
                         "report\""),
        custodian={"$gap": "gap-ce-metrics-pointer"},
        schemaRef={"$gap": "gap-ce-metrics-pointer"}), H)

    for oid, statement, implications in (
        ("as-engine-power",
         "The OMFV concepts are compared with engines of varying power.",
         "If the engine-power variation across the concepts does not span the range the "
         "fielded vehicle would sit in, the mobility comparison understates the "
         "uncertainty in the result."),
        ("as-infantry-carried",
         "The OMFV concepts are compared with variance in the number of infantry "
         "soldiers each can transport.",
         "If the dismount-count variation does not span the platoon structures the Army "
         "would actually field, the payload comparison understates the uncertainty in "
         "the result."),
    ):
        g.put(cited(
            oid, "Assumption", SRC_GAO, gao_at(14), now=NOW4,
            statement=statement, linchpin=False,
            rationale=("GAO printed p. 14: \"each OMFV concept presents different "
                       "assumptions for some of its characteristics, such as engines "
                       "with varying power or variance in the number of infantry "
                       "soldiers it can transport.\" GAO credits this as a form of "
                       "sensitivity analysis that can provide increased reliability in "
                       "results."),
            evidence="ev-ce-metrics",
            implicationsIfWrong=implications,
            indicatorsThatWouldAlter=[
                "the range of the varied assumption is published and is narrower than "
                "the fielded design space"],
            # This is the credit GAO gave, recorded as GAO gave it. DES-6 reads state 2
            # on the combat-effectiveness section because of these two objects, and the
            # README says plainly that the Army did not lack a sensitivity analysis.
            variedInSensitivity=True), H)


def build_sub_episodes(g: Graph) -> None:
    """The three sections of the March 2023 report, as three sub-episodes of `-r4`.

    They are built directly rather than by `open_refresh`, and they are **not appended to
    `prg-omfv.episodes`**. If they were, `_latest_episode` would return the last of them
    and episode 5 would be born `ep-omfv-2020-02-r4-ce-r5`. Each carries `sequence: 4`,
    `supersedes: "ep-omfv-2020-02-r4"` and `refreshedBecause: "rt-234-report"` — the last
    of those because `diff_episodes` refuses an episode that cannot say why it exists —
    and each omits the `program` field so nothing implies it sits in the chain.

    All three share one Charter and one evidence register, which is what GAO's own report
    does: it grades three sections of one document. Two findings therefore fire on
    sections GAO did not attribute them to. Those cross-fires are recorded, not
    suppressed — see `out/findings_matrix.json` and the README.
    """
    _sub_episode_claims(g)
    _combat_effectiveness_objects(g)

    r4 = g.get(EPISODE_4)
    common = {k: list(r4[k]) for k in
              ("objectives", "alternatives", "groundRules", "constraints", "assumptions",
               "evidenceRegister", "scenarios", "risks", "biasChecks", "mandateElements",
               "observations", "weightSets", "models")}
    # A bias indicator the kernel computed for `-r4` is a conclusion about `-r4`. Each
    # section's own `readiness_report` computes its own, so copying the parent's here
    # would put a 2023 whole-report indicator on three sections as if each had earned it
    # — the same error `open_refresh` used to make along the main chain.
    common["risks"] = [i for i in common["risks"]
                       if not is_computed_bias_risk(g, i)]

    sections = {
        "dc": (["cl-nine-characteristics", "cl-weight-threshold"], {}),
        "fs": (["cl-force-structure-improves"], {}),
        "ce": (["cl-concepts-outperform-m2a4"],
               {"evidenceRegister": common["evidenceRegister"] + ["ev-ce-metrics"],
                "assumptions": common["assumptions"] + ["as-engine-power",
                                                        "as-infantry-carried"]}),
    }
    for key, (claims, override) in sections.items():
        ep_id = SUB_EPISODES[key]
        plan_id = f"pl-omfv-r4-{key}"
        g.put(_plan(plan_id, ep_id, now=NOW4, steps=["aries", "trac"],
                    approved="2023-03-31"), H)
        g.put(own(
            ep_id, "DecisionEpisode", now=NOW4,
            sequence=4, charter=CHARTER, lifecycleState="DRAFT", transitions=[],
            **{**common, **override},
            claims=claims, runs=[], flipAnalyses=[], narratives=[],
            plan=plan_id, supersedes=EPISODE_4, refreshedBecause="rt-234-report",
            asOf=AS_OF[4]), H)


def file_gao_grading_trigger(g: Graph) -> None:
    """GAO's own report, filed as a trigger that opens no episode.

    `RefreshTrigger.affected` is typed `ref: [Claim, Assumption, Evidence, Objective,
    Model, Alternative]` — a DecisionEpisode id there is a blocking schema finding — so
    the trigger names the three Claims, one per graded section, and
    `affected_episodes(g, "rt-gao-grading")` walks reverse reachability from them to the
    three sub-episodes.
    """
    g.put(cited(
        "rt-gao-grading", "RefreshTrigger", SRC_GAO, gao_at(1), now="2023-06-27T00:00:00Z",
        kind="external-finding",
        source="GAO-23-106549, 27 June 2023",
        description=("GAO assesses the extent to which the Army's Section 234 report "
                     "presents objective, valid and reliable analysis of the three "
                     "sections. GAO did not independently assess or verify the "
                     "analytical efforts supporting the report (footnote 7, printed "
                     "p. 9; Appendix I, printed p. 17). The Army had no comments on the "
                     "draft and GAO made no recommendations (printed p. 14)."),
        detectedAt="2023-06-27",
        affected=["cl-nine-characteristics", "cl-force-structure-improves",
                  "cl-concepts-outperform-m2a4"]), H)
    program = g.get(PROGRAM)
    revise(g, PROGRAM, now="2023-06-27T00:00:00Z",
           refreshTriggers=sorted({*program["refreshTriggers"], "rt-gao-grading"}))


def file_signature_management_correction(g: Graph) -> None:
    """ACC-DTA Q&A control no. 021 — a trigger that opens no episode.

    What the record shows, verbatim from PDF p. 5: the question asks whether it is "an
    error that the signature management requirements are being shown as P3 in column F?
    The latest rev of the requirements has these at P2." The Government Response is
    "Attachment 0010 will be corrected to reflect signature management requirement P2 in
    column F."

    That is an attachment being corrected to match a requirements revision that already
    carried P2. It is not a dated Army decision to re-prioritise signature management,
    and there is no `obj-signature-management` to attach one to: signature management is
    a clause inside the Survivability characteristic in both the February and December
    CON texts. It is filed, and it opens nothing, because a document correction aligning
    an attachment with an existing revision is not a change of model requiring
    re-approval — and filing it as one would assert a decision no public document records.

    It is also dated **2022-10-25**, five months *before* the Section 234 report, not
    after the June 2023 downselect.
    """
    g.put(cited(
        "rt-sigmgmt-correction", "RefreshTrigger", SRC_QA, "PDF p. 5, control no. 021",
        now="2022-10-25T00:00:00Z",
        kind="artefact-version-changed",
        source=("ACC-DTA, OMFV Phase 3-4 Solicitation W56HZV-22-R-0026 Questions and "
                "Answers 01-140, 25 October 2022, Q&A control no. 021, PDF p. 5"),
        description=("Attachment 0010 showed the signature management requirements at P3 "
                     "in column F while the latest revision of the requirements had them "
                     "at P2. The Government response: \"Attachment 0010 will be corrected "
                     "to reflect signature management requirement P2 in column F.\" A "
                     "document correction to match an existing revision — not a "
                     "re-prioritisation decision, and not dated to one."),
        detectedAt="2022-10-25",
        affected=["obj-survivability-dec"]), H)
    program = g.get(PROGRAM)
    revise(g, PROGRAM, now="2022-10-25T00:00:00Z",
           refreshTriggers=sorted({*program["refreshTriggers"], "rt-sigmgmt-correction"}))


# ---- episode 5: the Phase 3/4 downselect ------------------------------------------
# The two performers and the award month are printed in a source this repository has
# already committed and verified: `army-rdte-r2-fy2025-omfv-xm30-extract.pdf`, Exhibit
# R-3 (RDT&E Project Cost Analysis, PB 2025 Army), PE 0605625A Manned Ground Vehicle /
# Project CF6 Optionally Manned Fighting Vehicle (OMFV) — source-volume page
# "Volume 3d - 201", extract PDF p. 74. Product Development, contract method C/FFP,
# performing activity "General Dynamics Land Systems & American Rheinmetall Vehicles :
# Sterling Heights, MI & Slidell, LA", FY2023 award date "Jun 2023".
#
# The press release itself is a stub (`sources/army-2023-06-26-omfv-phase-3-4-award.
# source.md`) whose release status is still a human call, and nothing is quoted from it.
R2_LOCATOR = ("Exhibit R-3, PE 0605625A / Project CF6, source-volume page "
              "\"Volume 3d - 201\", extract PDF p. 74")


def trigger_r5(g: Graph) -> None:
    """`rt-downselect`, and the replacing Alternative it needs to already exist."""
    g.put(cited(
        "alt-xm30-gdls", "Alternative", SRC_R2_FY2025, R2_LOCATOR, now=NOW5,
        name="XM30 (OMFV) detailed design — General Dynamics Land Systems",
        description=("One of the two Phase 3/4 Product Development performers named on "
                     "the PB2025 R-3 exhibit against a June 2023 award date. The "
                     "abstract \"OMFV concept\" of 2020 has become two funded detailed "
                     "designs."),
        status="selected", baselineFlag=False, enteredOrder=3), H)

    g.put(cited(
        "rt-downselect", "RefreshTrigger", SRC_R2_FY2025, R2_LOCATOR, now=NOW5,
        kind="evidence-changed",
        source=("Army/DoW public announcement of the OMFV Phase 3/4 awards, 26 June 2023 "
                "(" + SRC_AWARD_STUB + " — stub; release status is a human call and "
                "nothing is quoted from it). The two performers and the June 2023 award "
                "month are independently printed in " + SRC_R2_FY2025 + ", " +
                R2_LOCATOR),
        description=("Phase 3/4 Product Development is awarded to two vendors. The "
                     "single \"OMFV concept\" alternative the record has carried since "
                     "February 2020 is replaced by two funded detailed designs."),
        detectedAt="2023-06-26",
        affected=["alt-omfv-concept"]), H)


def revise_r5(g: Graph) -> None:
    """The second selected alternative, and the exclusion that covers the rest.

    `replacements` is a 1:1 map, so a one-to-two split is recorded as **one replacement
    plus one addition**: `alt-omfv-concept → alt-xm30-gdls` goes through the refresh
    engine, and `alt-xm30-rheinmetall` is added by this human revision. The README says
    so rather than faking a second map entry.
    """
    g.put(cited(
        "alt-xm30-rheinmetall", "Alternative", SRC_R2_FY2025, R2_LOCATOR, now=NOW5,
        name="XM30 (OMFV) detailed design — American Rheinmetall Vehicles",
        description=("The second of the two Phase 3/4 Product Development performers "
                     "named on the PB2025 R-3 exhibit against a June 2023 award date."),
        status="selected", baselineFlag=False, enteredOrder=4), H)

    g.put(cited(
        "ex-phase2-concepts-not-selected", "Exclusion", SRC_R2_FY2025, R2_LOCATOR,
        now=NOW5,
        # Label only, no `id`: the unselected vendors are not objects in this graph and
        # naming them would need a source this project does not hold.
        target={"kind": "Alternative",
                "label": "the Phase 2 concept-design vendors not selected for Phase 3/4"},
        # `other`, not `dominated`: the Army published no domination finding. The
        # consequence is honest and intended — `bias.py`'s selection indicator counts
        # exclusions with `reasonType: other`, so this raises a `bias-selection` Risk,
        # and the public record does give no rationale.
        reasonType="other",
        reason=("not selected in the Army's Phase 3/4 source selection; the public "
                "record gives no rationale"),
        authority={"who": "Army source selection", "role": "source selection authority",
                   "date": "2023-06-26"},
        retainedInStructure=True), H)

    g.put(_plan("pl-omfv-r5", EPISODE_5, now=NOW5, steps=["aries", "trac"],
                approved="2023-06-26"), H)

    ep = g.get(EPISODE_5)
    revise(g, EPISODE_5, now=NOW5,
           alternatives=ep["alternatives"] + ["alt-xm30-rheinmetall"],
           plan="pl-omfv-r5")


# ---- the counterfactual repair ----------------------------------------------------
COUNTERFACTUAL_PROVENANCE = {
    "sourceArtifact": "demos/b_omfv_2019_2023/README.md#counterfactual-repair",
    "locator": "counterfactual",
    "extractor": "counterfactual",
    "extractedAt": "2026-09-06"}
NOW_CF = "2026-09-06T00:00:00Z"


def _cf(oid: str, type_name: str, **fields) -> dict:
    """An object the counterfactual repair writes. It describes no real document."""
    return {"id": oid, "type": type_name, "rev": 1, "createdBy": H, "createdAt": NOW_CF,
            "ingestionProvenance": dict(COUNTERFACTUAL_PROVENANCE),
            "confidence": "inferred", **fields}


def _cf_revise(g: Graph, oid: str, **fields) -> dict:
    o = g.get(oid)
    return g.put({**o, "rev": o["rev"] + 1, "createdBy": H, "createdAt": NOW_CF,
                  "ingestionProvenance": dict(COUNTERFACTUAL_PROVENANCE),
                  "confidence": "inferred", **fields}, H)


def repair_ce(g: Graph) -> None:
    """What the record would have to contain for the withheld metrics to be *locatable*.

    This is a counterfactual. It says nothing about what the Army did, and it must never
    run against the main store: `run.py` applies it to a separate graph copy saved under
    `out/counterfactual/`. Every object it writes is `confidence: "inferred"` and carries
    an `ingestionProvenance` whose `sourceArtifact` is this demonstration's own README,
    so no reader can mistake one for the record.

    The classification level of `ev-ce-metrics` **stays `S`**. The value is still
    withheld; that is the whole point. What changes is that the record now says where the
    package is and who holds it, so a reader cleared to S can go and read it and a reader
    who is not can see that it exists and that the claim rests on it.

    Two things are repaired, because `assessable-with-classified-value` and EXE-14 state 1
    each need more than the brief supposed:

    * `_metadata_missing` must come back **empty** — content pointer, content
      `scopeOfValidity` *and* `reviewStatus != "draft"`. A pointer alone is not enough.
    * `vva_signed` is `_all(models, ...)`: it asks every Model in the episode, not one. So
      both `vva-aries` and `vva-trac` are repaired, not just `vva-trac`, and both need
      `basis == "document"` **with** a real `document` ref, an `authority` and a `date` —
      a `document` basis with no document scores 4, not 1.
    """
    g.put(_cf(
        "cf-ev-vva-accreditation", "Evidence",
        title=("COUNTERFACTUAL: a MIL-STD-3022 accreditation report for the models and "
               "simulations informing the 11 analytical efforts"),
        evidenceType="Document",
        publisher="COUNTERFACTUAL — no such document is known to exist",
        published="2021",
        pointer={"uri": "counterfactual: an accreditation report cited by the Section 234 "
                        "report",
                 "custodian": "COUNTERFACTUAL — Army Futures Command"},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("whether the models and simulations informing the 11 "
                              "analytical efforts are accredited for this use"),
            "questionClass": "desired-characteristics",
            "intendedUse": "counterfactual accreditation basis"},
        reviewStatus="reviewed",
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason=("counterfactual: the document that would turn GAO's interview "
                         "sentence into a signed accreditation")), H)

    g.put(_cf(
        "cf-ev-ce-metrics-package", "Evidence",
        title=("COUNTERFACTUAL: the delivery record for the OMFV combat effectiveness "
               "metrics package"),
        evidenceType="Document",
        publisher="COUNTERFACTUAL — no such document is known to exist",
        published="2023",
        pointer={"uri": "counterfactual: a CDRL delivery record for the metrics package",
                 "custodian": "COUNTERFACTUAL — PEO Ground Combat Systems"},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": "where the combat effectiveness metrics package is held",
            "questionClass": "combat-effectiveness",
            "intendedUse": "counterfactual locator for a withheld dataset"},
        reviewStatus="reviewed",
        reliabilitySteps={"$gap": "gap-reliability-steps"},
        inclusionReason="counterfactual: the record that would locate the withheld value"), H)

    g.put(_cf(
        "cf-drs-ce-metrics", "DataReliabilityStep",
        description=("COUNTERFACTUAL: a described reliability step for the combat "
                     "effectiveness metrics — the source review the Section 234 report "
                     "would have had to describe for EXE-5 to rise above state 4."),
        method="source-review",
        performedBy="COUNTERFACTUAL — PEO Ground Combat Systems",
        date="2023-03",
        documentation="cf-ev-ce-metrics-package"), H)

    _cf_revise(
        g, "ev-ce-metrics",
        pointer={"uri": "OMFV combat effectiveness metrics package (counterfactual)",
                 "custodian": "COUNTERFACTUAL — PEO Ground Combat Systems"},
        custodian="COUNTERFACTUAL — PEO Ground Combat Systems",
        reviewStatus="reviewed",
        reviewers=[{"name": "COUNTERFACTUAL — PEO Ground Combat Systems",
                    "role": "custodian review", "date": "2023-03"}],
        reliabilitySteps=["cf-drs-ce-metrics"])

    for vid in ("vva-aries", "vva-trac"):
        acc = dict(g.get(vid)["accreditationDecision"])
        acc.update({"basis": "document", "document": "cf-ev-vva-accreditation"})
        _cf_revise(g, vid, accreditationDecision=acc)
