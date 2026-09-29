"""The positive control — the A.T. Kearney combat vehicle industrial base study,
reconstructed from GAO-15-548, the report in which GAO found its approach sound.

Source: U.S. Government Accountability Office, *Army Combat Vehicles: Industrial Base
Study's Approach Met Research Standards*, GAO-15-548 (16 June 2015) —
`sources/gao-15-548-army-combat-vehicles-industrial-base-study.pdf`, public, committed.
Page numbers in this file are the report's **printed** pages; the PDF page is the printed
page plus three, which is what the `#page=` anchors carry.

Four rules held while reconstructing:

1. **The study itself is not public and is not invented.** The A.T. Kearney report — "M1
   Abrams Tank Upgrade and Bradley Fighting Vehicle Industrial Base Study: Report to
   Congress", April 2014 (GAO printed p. 22 fn 1) — went to the congressional defense
   committees and was never released. Everything here is what *GAO* reports about it,
   with the GAO page that reports it. Where GAO's account says nothing, the record
   carries an `InsufficientEvidence` object, not a guess.
2. **Reconstructed, and labelled so.** Every object that describes the Kearney study
   carries `confidence: "inferred"`, because it was assembled out of GAO's prose rather
   than transcribed from the study. Only the two objects that describe *GAO's own* work
   — GAO's report and GAO's two-analyst reconciliation — are `confidence: "explicit"`.
   Gaps carry `confidence: "absent"`.
3. **GAO published no per-question ratings for this study**, and does not use the
   objectivity / validity / reliability frame at all. Printed p. 24: "we determined that
   qualitative assessment ratings provide the best explanation of the nuances of the
   analysis and findings, rather than numeric ratings for each individual standard."
   Every per-question state this record produces, and all three dimension verdicts, are
   **ours**. See `expected.yaml` and the README.
4. **GAO assessed the reasonableness of the study's methods** (printed p. 2), not the
   study's underlying analysis. Nothing here says otherwise.

The record is dated to the study: `createdAt` and the episode's `asOf` are 2014-04-30,
the month the final report went to the congressional defense committees, so the
elapsed-time predicates (accreditation age, scope validity) read as they would have then.
The real transcription date lives in `ingestionProvenance.extractedAt`.
"""

from __future__ import annotations

from docket.store import Graph

H = {"actorType": "human", "actorId": "shreyash"}
NOW = "2014-04-30T00:00:00Z"
AS_OF = "2014-04-30"
SRC = "sources/gao-15-548-army-combat-vehicles-industrial-base-study.pdf"
EXTRACTED = "2026-09-05"
EPISODE = "ep-kearney-2014"

# Who confirmed each recorded absence, and when. A gap is a human's signature on "this
# really is missing from the public record", so it is written once and reused.
CONFIRMED = {"actorId": "shreyash", "date": "2026-09-05"}


def anchor(printed_page: int) -> str:
    """A pointer into the committed PDF. Printed page + 3 = PDF page."""
    return f"{SRC}#page={printed_page + 3}"


def loc(*printed_pages: int) -> str:
    """A locator naming both page numberings, so a reader can find it either way."""
    return "; ".join(f"printed p. {p} (PDF p. {p + 3})" for p in printed_pages)


def o(oid: str, type_name: str, locator: str, *, confidence: str = "inferred", **fields):
    """An object reconstructed from a cited page of GAO-15-548.

    The default confidence is `inferred`, not `explicit`: GAO's report is the only public
    account of the Kearney study, so every statement here about the *study* is read off
    somebody else's description of it. Objects about GAO's own work pass
    `confidence="explicit"`; recorded absences pass `confidence="absent"`.
    """
    return {
        "id": oid, "type": type_name, "rev": 1, "createdBy": H, "createdAt": NOW,
        "ingestionProvenance": {"sourceArtifact": SRC, "locator": locator,
                                "extractor": "human", "extractedAt": EXTRACTED},
        "confidence": confidence, **fields,
    }


def own(oid: str, type_name: str, **fields):
    """An object this reconstruction supplies: no ingestion provenance, because it was
    not extracted from anything. The decision-class policy, the equal weighting, the
    single-episode programme and the two typed exclusions are ours; citing a GAO page for
    them would be a false citation.

    These are the five most "ours" objects in the record, so they carry
    `confidence: "inferred"` too — the envelope allows it on any object, and leaving the
    field off the objects nobody could mistake for GAO's would be the one place the
    labelling discipline went quiet.
    """
    return {"id": oid, "type": type_name, "rev": 1, "createdBy": H, "createdAt": NOW,
            "confidence": "inferred", **fields}


# ---- the six analyses, as GAO names them (printed p. 13) ---------------------------
#
# GAO printed p. 9 splits them between the two halves of the study's objective: four
# elements address "assessing the combined commercial and government combat vehicle
# industrial base", two address "developing viable strategic alternatives to sustain that
# industrial base within a constrained fiscal environment". The split below is GAO's.
#
# `metric.units` and `metric.direction` are REQUIRED by the Measure schema and are not
# P3 slots, so a qualitative consulting method has to be forced into them. The strings
# below are descriptive, the directions are our reading, and both are disclosed in the
# README — this is the schema-forced-field failure mode the design accuses other tools
# of, appearing in our own catalogue.
#
# (measure id, objective, task, attribute, measure, units, direction, locator pages)
MEASURES = [
    ("m-current-state", "obj-viability",
     "Conduct a current state assessment of the combat vehicle industrial base",
     "capability, capacity and critical manufacturing skills at each production and "
     "sustainment facility",
     "the capabilities, capacity and critical manufacturing skills identified at the key "
     "government and commercial facilities; the assessment of critical manufacturing "
     "skills is a step within it (printed pp. 9, 14)",
     "facilities and critical skills characterised (qualitative — GAO reports findings, "
     "not a score; units are schema-forced)", "max", (9, 14)),
    ("m-cost-baseline", "obj-viability",
     "Establish the original equipment manufacturer / government cost baseline",
     "the cost of each manufacturing process at each production facility",
     "the costs of various manufacturing processes for combat vehicles at different "
     "production facilities, normalised so that overhead rates are comprised of the same "
     "elements (printed pp. 9, 13, 16)",
     "cost per manufacturing process per facility, in dollars, overhead-normalised",
     "min", (9, 13, 16)),
    ("m-supplier-base", "obj-viability",
     "Conduct a supplier base analysis",
     "the ability of key suppliers to withstand enduring periods of low demand",
     "suppliers identified as critical, fragile or at risk, from the written survey, the "
     "non-respondent follow-up and interviews and site visits with 72 suppliers "
     "(printed pp. 9, 14, 15)",
     "suppliers identified as critical or at risk (count)", "min", (9, 14, 15)),
    ("m-benchmark", "obj-viability",
     "Conduct a benchmark comparison",
     "combat vehicle manufacturing costs against industry benchmark data",
     "the range within which the study's authors expected a withheld cost to fall, "
     "estimated from industry benchmark data and their own industry experience and then "
     "put back to the supplier (printed pp. 9, 16)",
     "difference between an observed facility cost and the industry benchmark, in dollars",
     "min", (9, 16)),
    ("m-scenario-analysis", "obj-alternatives",
     "Develop and assess multiple scenarios for sustaining the combat vehicle industrial "
     "base",
     "the financial consequences to manufacturers and suppliers at different levels of "
     "demand",
     "the financial consequences to various manufacturers and suppliers in the industrial "
     "base based on different levels of demand, computed through the spreadsheet-based "
     "model (printed pp. 9, 13)",
     "financial consequence to each manufacturer and supplier, in dollars, per demand "
     "scenario", "min", (9, 13)),
    ("m-network-strategy", "obj-alternatives",
     "Develop a network strategy plan",
     "potential alternatives for restructuring parts of the combat vehicle industrial base",
     "potential courses of action to alter the structure of the combat vehicle industrial "
     "base, such as consolidation of production at certain facilities (printed pp. 9, 14, "
     "18)",
     "courses of action developed and assessed (count)", "max", (9, 14, 18)),
]

MEASURE_IDS = [m[0] for m in MEASURES]

ALTERNATIVES = [
    ("alt-continue-production",
     "Continue Bradley production at the York facility",
     "The status quo the shutdown analysis is measured against: Bradley Fighting Vehicle "
     "production continues at the BAE facility in York, Pennsylvania. GAO printed p. 11 "
     "reports the study's in-depth assessment of the potential costs of shutting that "
     "line down, which presupposes the cost of continuing it.",
     True, 1, (10, 11)),
    ("alt-warm-shutdown",
     "A two-year 'warm shutdown' of the Bradley line, followed by restart",
     "GAO printed p. 11, verbatim: the Army's study assumed \"a two-year shutdown of the "
     "Bradley line followed by restart, which the study's authors termed a 'warm "
     "shutdown,' because the shutdown included an anticipated restart date.\" The study "
     "estimated $53 million for the shutdown and restart.",
     False, 2, (11,)),
    ("alt-courses-of-action",
     "Restructure the industrial base along one of the courses of action the scenarios "
     "produced",
     "GAO printed p. 14, verbatim: the scenarios \"were run through the model to help the "
     "Army develop potential courses of action to alter the structure of the combat "
     "vehicle industrial base.\" GAO printed p. 18 names consolidation of production at "
     "certain facilities as an example, and records that these options were not required "
     "by the congressional direction and were not included in the final report.",
     False, 3, (14, 18)),
]

# The MIL-STD-3022 §5.3 retained sections, in the order the standard lists them. A
# section GAO's account does not describe is retained and marked not-applicable by a
# typed Exclusion rather than dropped — which is what makes EXE-8 rate 2 rather than 1.
VVA_SECTIONS = ("Problem Statement", "M&S Requirements and Acceptability Criteria",
                "M&S Assumptions, Capabilities, Limitations & Risks/Impacts",
                "Accreditation Methodology", "Issues", "Key Participants", "Resources",
                "Lessons Learned")


def _vva_sections(described: dict[str, str]) -> list[dict]:
    """Every retained section, with content where GAO describes it and the typed
    not-applicable exclusion where GAO's account says nothing."""
    return [{"name": name,
             "content": described.get(name, {"$exclusion": "ex-vva-na"})}
            for name in VVA_SECTIONS]


# ---- data reliability steps (printed pp. 2, 15, 16, 17) ------------------------------


def _reliability_steps(g: Graph) -> None:
    put = g.put

    put(o("drs-two-analysts", "DataReliabilityStep", loc(2), confidence="explicit",
          description=(
              "GAO's own reconciliation, verbatim from printed p. 2: \"Two GAO analysts "
              "individually evaluated the Army study against these standards, consulting "
              "with GAO specialists in the areas of economics, survey and research "
              "methods, and, as needed, obtaining clarifications and additional "
              "information from the Army and the study's authors. After completing their "
              "independent analyses, we compared the two sets of observations and "
              "discussed and reconciled any differences.\" Printed p. 23 adds that the "
              "two analysts used a scorecard methodology."),
          method="expert-review", performedBy="U.S. Government Accountability Office",
          date="2015-06", documentation="ev-gao-15-548"), H)

    put(o("drs-original-sources", "DataReliabilityStep", loc(16),
          description=(
              "Verbatim from printed p. 16: \"the study's authors went to the original "
              "sources to obtain relevant information and sought clarification to make "
              "sure they understood the data provided.\" GAO states this of the study's "
              "data generally — the section is headed \"The Army Took Sufficient Actions to "
              "Ensure the Data Were Valid and Reliable for the Study's Purposes\" and the "
              "Abrams program office follows a \"For example\" — so attaching it to a "
              "particular evidence item GAO does not name is our reading, not GAO's. See "
              "the README, 'Which reliability steps are general and which are "
              "item-specific'."),
          method="source-review", performedBy="A.T. Kearney", date="2013",
          documentation="ev-gao-15-548"), H)

    put(o("drs-abrams-program-office", "DataReliabilityStep", loc(16, 17),
          description=(
              "Printed p. 16: the study's authors obtained information on government "
              "expenses at the Joint Systems Manufacturing Center directly from the "
              "Abrams program office. Printed p. 17 adds that the financial data the "
              "production facilities provided \"had also been reviewed by the Defense "
              "Contract Management Agency, the government agency responsible for, among "
              "other things, monitoring contractors' management of their indirect "
              "costs.\""),
          method="source-review", performedBy="A.T. Kearney", date="2013",
          documentation="ev-gao-15-548"), H)

    put(o("drs-normalise-overhead", "DataReliabilityStep", loc(16),
          description=(
              "Printed p. 16: because different production facilities charge different "
              "activities to different accounts, the calculation of overhead rates had to "
              "be standardised. The study's authors examined the time charges for "
              "accounts that contribute to factory overhead at different facilities and "
              "made efforts to normalise the data, ensuring that \"overhead rates for each "
              "facility were generally comprised of the same elements.\""),
          method="electronic-testing", performedBy="A.T. Kearney", date="2013",
          documentation="ev-gao-15-548"), H)

    put(o("drs-nonrespondent-followup", "DataReliabilityStep", loc(15, 16),
          description=(
              "Printed p. 15: the study's authors contacted non-responding suppliers and "
              "obtained publicly available information on the companies, including credit "
              "rating information, to develop an accurate company business profile; that "
              "identified reasons for non-participation, some of which showed a subset "
              "should not have been in the original survey. Printed p. 16 records that "
              "over 20 non-respondents agreed to participate in the study site visits, "
              "and that GAO judged these steps \"generally reasonable\" while noting the "
              "authors did not formally compare respondents to non-respondents."),
          method="corroboration", performedBy="A.T. Kearney", date="2013",
          documentation="ev-gao-15-548"), H)

    put(o("drs-supplier-review", "DataReliabilityStep", loc(16, 17),
          description=(
              "Verbatim from printed p. 17: to ensure the data's reliability the study's "
              "authors \"went back to the data sources, in many cases multiple times, to "
              "review their methods and ensure they were using the data correctly.\" GAO's "
              "example is the Bradley engine financial analysis, reviewed with the "
              "supplier's general manager and working team; printed p. 16 records the same "
              "loop for benchmark-estimated costs, which were put back to the supplier. "
              "GAO states this of the study's data generally — the section is headed \"The "
              "Army Took Sufficient Actions to Ensure the Data Were Valid and Reliable for "
              "the Study's Purposes\" and the Bradley engine follows a \"For example\" — so "
              "attaching it to a particular evidence item GAO does not name is our reading, "
              "not GAO's. See the README, 'Which reliability steps are general and which "
              "are item-specific'."),
          method="corroboration", performedBy="A.T. Kearney", date="2013",
          documentation="ev-gao-15-548"), H)


# ---- recorded absences ---------------------------------------------------------------


def _gaps(g: Graph) -> None:
    put = g.put

    put(o("gap-kearney-report", "InsufficientEvidence", loc(1, 2, 18, 19, 22),
          confidence="absent",
          sought=(
              "A.T. Kearney / Department of the Army, \"M1 Abrams Tank Upgrade and Bradley "
              "Fighting Vehicle Industrial Base Study: Report to Congress\", the final "
              "report to the congressional defense committees, April 2014 (title from GAO "
              "printed p. 22 fn 1)"),
          whereLookedFor=["GAO-15-548 printed pp. 1-2, 18, 22",
                          "public web search, 2026-09-05"],
          whyNotFound=(
              "a report to the congressional defense committees; not published. GAO "
              "printed p. 19 records that the Army did not provide it even to the "
              "original equipment manufacturers and suppliers, \"due to the classification "
              "of the report as 'for official use only.'\""),
          confirmedBy=CONFIRMED, impact="degrading",
          indicatorsThatWouldResolve=[
              "public release of the April 2014 report to the congressional defense "
              "committees",
              "release of the interim and final study briefings or the backup slides GAO "
              "reviewed (printed p. 2)"]), H)

    put(o("gap-msr-derivation", "InsufficientEvidence", loc(13), confidence="absent",
          sought="how the minimum sustainment rate the study used was derived",
          whereLookedFor=["GAO-15-548 printed p. 13",
                          "public web search for the original equipment manufacturers' "
                          "minimum sustainment rate derivations, 2026-09-05"],
          whyNotFound=(
              "Verbatim, printed p. 13: the study \"noted that it used the minimum "
              "sustainment rates as derived by the original equipment manufacturers, but "
              "did not include specific information on how that minimum sustainment rate "
              "was derived\", and \"could have included more explicit information about the "
              "assumptions used to define the minimum sustainment rate\"."),
          confirmedBy=CONFIRMED,
          # Degrading, not blocking, and the distinction is GAO's own: printed p. 13,
          # "we do not believe that the lack of explicitly stated information materially
          # affected the results of the study, but if better explained, would provide
          # clearer understanding of the assumptions." A blocking gap would drop PRE-2
          # from 1 to 2 and would put a severity on the record that GAO did not.
          impact="degrading",
          indicatorsThatWouldResolve=[
              "the original equipment manufacturers publish the derivation of their "
              "minimum sustainment rates",
              "release of the April 2014 report with the assumptions used to define the "
              "minimum sustainment rate"]), H)

    put(o("gap-risk-perspective-rationale", "InsufficientEvidence", loc(12, 13),
          confidence="absent",
          sought=(
              "the study's own statement of why risk was assessed from the perspective of "
              "the Army rather than from that of the original equipment manufacturers or "
              "the individual suppliers"),
          whereLookedFor=["GAO-15-548 printed pp. 12-13",
                          "public web search for any Army or A.T. Kearney statement of the "
                          "perspective from which the study assessed risk, 2026-09-05"],
          whyNotFound=(
              "GAO printed p. 12 records that this \"key assumption ... was not explicitly "
              "identified\" by the study, and printed p. 13 that it \"was presented in the "
              "study as a finding; however, we believe it to be an assumption\". An "
              "assumption the study did not identify as one states no rationale for "
              "itself; the reading that it is an assumption at all is GAO's."),
          confirmedBy=CONFIRMED, impact="degrading",
          indicatorsThatWouldResolve=[
              "release of the April 2014 report showing the perspective stated as an "
              "assumption with its rationale"]), H)

    put(o("gap-criteria", "InsufficientEvidence", loc(9, 13), confidence="absent",
          sought=(
              "the threshold and objective values each of the six analyses was scored "
              "against"),
          whereLookedFor=["GAO-15-548 printed pp. 9, 13-14 (the methodology and its "
                          "execution)", "GAO-15-548 printed p. 10, figure 2 (a raster "
                          "figure with no text layer)"],
          whyNotFound=(
              "GAO describes the six analyses and their findings; the study's own "
              "threshold and objective values are not in the public account, and GAO "
              "nowhere says the analyses were scored against numeric criteria at all."),
          confirmedBy=CONFIRMED, impact="informational",
          indicatorsThatWouldResolve=[
              "release of the April 2014 report or the backup slides that detail the "
              "methodological elements of the study (printed p. 2)"]), H)

    put(o("gap-weights", "InsufficientEvidence", loc(9, 13), confidence="absent",
          sought="the relative weighting across the six analyses",
          whereLookedFor=["GAO-15-548 printed pp. 9, 13-14", "GAO-15-548 printed p. 10, "
                          "figure 2"],
          whyNotFound=(
              "the public account does not say the six analyses were weighted, or "
              "combined into a single score at all; the equal weighting this record "
              "carries is ours, supplied because the Plan schema requires a WeightSet."),
          confirmedBy=CONFIRMED, impact="informational",
          indicatorsThatWouldResolve=[
              "release of the April 2014 report or the backup slides showing how the six "
              "analyses were combined"]), H)


# ---- typed omissions -----------------------------------------------------------------


def _exclusions(g: Graph) -> None:
    put = g.put

    put(own("ex-kearney-report-not-public", "Exclusion",
            target={"kind": "Evidence", "id": "ev-kearney-final-report",
                    "label": ("the Army's April 2014 report to the congressional defense "
                              "committees")},
            reasonType="data-unavailable",
            reason=(
                "The report is not published; GAO's description of it is the only public "
                "account. It stays in the evidence register because it is the study under "
                "assessment, but no Claim in this record rests on it: its pointer is a "
                "recorded gap, and a claim resting on evidence whose metadata nobody "
                "outside the Army can see is exactly what the scope checker is right to "
                "refuse. Demonstration A hits the same mechanism with the Army's "
                "Milestone A analysis of alternatives."),
            authority={"who": "shreyash", "role": "reconstruction author",
                       "date": "2026-09-05"},
            retainedInStructure=True), H)

    put(own("ex-vva-na", "Exclusion",
            target={"kind": "Section",
                    "label": "VV&A sections the public account does not describe"},
            reasonType="not-applicable",
            reason=(
                "This section is not applicable (MIL-STD-3022 §5.3 retained section); "
                "GAO's account of the study does not describe it. The section is retained "
                "and marked rather than dropped, which is why EXE-8 reads 2 — documented "
                "with reasoned not-applicables — and not 1."),
            authority={"who": "shreyash", "role": "reconstruction author",
                       "date": "2026-09-05"},
            retainedInStructure=True), H)


# ---- the evidence register -----------------------------------------------------------
#
# Ten items. One — the Kearney report itself — is covered by a typed Exclusion because
# its pointer is a gap. The other nine are each cited by a Claim, which is what keeps the
# `silent-omission` rule quiet: evidence a record lists and then never mentions again is
# a silence, and the rule is right to block on it.


def _evidence(g: Graph) -> None:
    put = g.put

    put(o("ev-gao-15-548", "Evidence", loc(1, 2, 3, 18, 19, 23), confidence="explicit",
          title=("U.S. Government Accountability Office, Army Combat Vehicles: Industrial "
                 "Base Study's Approach Met Research Standards, GAO-15-548 (16 June 2015)"),
          evidenceType="Document", publisher="U.S. Government Accountability Office",
          published="2015-06-16", date="2015-06-16",
          pointer={"uri": "https://www.gao.gov/products/gao-15-548",
                   "custodian": "U.S. Government Accountability Office"},
          classification={"level": "U", "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("Was the Army's combat vehicle industrial base study's "
                                "approach — its design, execution and presentation of "
                                "results — reasonable and sound for its intended "
                                "purposes?"),
              "questionClass": "industrial-base",
              "intendedUse": ("report to the congressional defense committees on the "
                              "reasonableness of the study's methods, under the Joint "
                              "Explanatory Statement to accompany the National Defense "
                              "Authorization Act for Fiscal Year 2014")},
          reviewStatus="reviewed",
          reviewers=[{"name": "Marie A. Mak, Director, Acquisition and Sourcing "
                              "Management, GAO",
                      "role": "signing director", "date": "2015-06-16"},
                     {"name": "Department of Defense (Office of the Assistant Secretary "
                              "of the Army for Acquisition, Logistics, and Technology)",
                      "role": "agency comment on the draft", "date": "2015-06-08"}],
          reliabilitySteps=["drs-two-analysts"],
          inclusionReason=("the only public account of the Army's study, and the source of "
                           "every locator in this record"),
          limitations=[
              {"statement": ("GAO assessed the reasonableness of the study's methods "
                             "(printed p. 2). Its examination covered the study's design, "
                             "execution and presentation of results."),
               "impact": ("this record is a reconstruction of the study's *method* as GAO "
                          "describes it; it carries no independent check of the study's "
                          "numbers, and neither does GAO's report")},
              {"statement": ("Printed p. 3 and printed p. 23: GAO interviewed "
                             "representatives from six suppliers that participated in the "
                             "study, and states that \"the views of these suppliers cannot "
                             "be generalized to the views of all those suppliers that "
                             "participated in the study.\""),
               "impact": ("the supplier perspectives GAO reports are illustrative, not "
                          "representative of the supplier base")},
              {"statement": ("Printed p. 18: the original equipment manufacturers and the "
                             "suppliers GAO spoke with \"reported they had not received "
                             "copies of the final report, so they were unable to comment "
                             "fully on the nature of the final report's findings.\""),
               "impact": ("the manufacturer and supplier commentary GAO collected bears on "
                          "the interim briefings and the facility-specific information, "
                          "not on the final report as issued")}]), H)

    put(o("ev-kearney-final-report", "Evidence", loc(1, 2, 18, 22),
          title=("A.T. Kearney / Department of the Army, \"M1 Abrams Tank Upgrade and "
                 "Bradley Fighting Vehicle Industrial Base Study: Report to Congress\" "
                 "(April 2014), with the interim and final study briefings and the backup "
                 "slides that detail the study's methodological elements"),
          evidenceType="Document",
          publisher="Department of the Army / A.T. Kearney", published="2014-04",
          date="2014-04",
          pointer={"$gap": "gap-kearney-report"},
          classification={"level": "U",
                          "caveats": ["GAO printed p. 19 reports the Army withheld the "
                                      "report from the manufacturers and suppliers as "
                                      "'for official use only'; its present release "
                                      "status has not been verified by this project"],
                          "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("What is the state of the combined commercial and "
                                "government combat vehicle industrial base, and what "
                                "strategic alternatives would sustain it within a "
                                "constrained fiscal environment?"),
              "questionClass": "industrial-base",
              "intendedUse": ("the Army's report to the congressional defense committees "
                              "and its investment decisions in the combat vehicle "
                              "industrial base")},
          reviewStatus="reviewed",
          reviewers=[{"name": "Department of the Army",
                      "role": "submitting authority", "date": "2014-04"},
                     {"name": "U.S. Government Accountability Office",
                      "role": "assessment of the reasonableness of the study's methods",
                      "date": "2015-06"}],
          # The study is not "data the study used", so none of the six reliability steps
          # applies to it. GAO describes no reliability step taken *on the report itself*,
          # so the slot holds the same recorded absence its pointer does. No scoring
          # effect: no Claim cites this item, so it is not in `_cited_evidence`.
          reliabilitySteps={"$gap": "gap-kearney-report"},
          inclusionReason="the study under assessment",
          limitations=[
              {"statement": ("The report itself is not public: everything recorded about "
                             "it here is what GAO reports about it."),
               "impact": ("its findings cannot be checked against the analysis that "
                          "produced them; the pointer is a recorded gap, not a locator, "
                          "and no Claim in this record rests on this item")}]), H)

    put(o("ev-manufacturer-data", "Evidence", loc(13, 16),
          title=("Cost data for combat vehicle manufacturing processes, collected at the "
                 "government and commercial production facilities"),
          evidenceType="Dataset", date="2013",
          pointer={"uri": anchor(13),
                   "custodian": ("A.T. Kearney and the manufacturers and suppliers (the "
                                 "data itself, not public); U.S. Government Accountability "
                                 "Office (the published description)")},
          classification={"level": "U", "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("What does each manufacturing process for combat vehicles "
                                "cost at each production facility?"),
              "questionClass": "industrial-base",
              "intendedUse": "the study's original equipment manufacturer / government "
                             "cost baseline"},
          reviewStatus="reviewed",
          reviewers=[{"name": "A.T. Kearney", "role": "collecting analyst", "date": "2013"},
                     {"name": "U.S. Government Accountability Office",
                      "role": "method reviewed against research standards",
                      "date": "2015-06"}],
          reliabilitySteps=["drs-original-sources", "drs-normalise-overhead"],
          inclusionReason="the cost baseline is one of the study's six analyses",
          custodian="A.T. Kearney (collected from the manufacturers and suppliers)",
          schemaRef=("cost by manufacturing process and facility, with factory overhead "
                     "rates normalised so each facility's rate is comprised of the same "
                     "elements (printed p. 16)"),
          limitations=[
              {"statement": ("The cost data themselves are proprietary and are not public; "
                             "GAO's description of how they were collected is the whole of "
                             "the public account."),
               "impact": ("no cost figure in this record can be checked against the data "
                          "behind it")}]), H)

    put(o("ev-supplier-survey", "Evidence", loc(15, 16),
          title=("Written survey of about 200 suppliers of key combat vehicle parts, with "
                 "non-respondent follow-up"),
          evidenceType="MarketResearch", date="2013",
          pointer={"uri": anchor(15),
                   "custodian": ("A.T. Kearney (the instrument and the responses, not "
                                 "public); U.S. Government Accountability Office (the "
                                 "published description)")},
          classification={"level": "U", "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("Which suppliers of key combat vehicle parts can withstand "
                                "enduring periods of low demand?"),
              "questionClass": "industrial-base",
              "intendedUse": "the study's supplier base analysis"},
          reviewStatus="reviewed",
          reviewers=[{"name": "A.T. Kearney", "role": "surveying analyst", "date": "2013"},
                     {"name": "U.S. Government Accountability Office",
                      "role": "method reviewed against research standards, consulting GAO "
                              "specialists in survey and research methods",
                      "date": "2015-06"}],
          reliabilitySteps=["drs-nonrespondent-followup"],
          inclusionReason="the primary supplier-base data source",
          method=("a written survey sent to about 200 suppliers of key parts of the various "
                  "combat vehicles — engines, transmissions, radar and target acquisition "
                  "components, and many other smaller parts (printed p. 15)"),
          respondents=("about 25 percent responded; the authors contacted the "
                       "non-respondents, and over 20 of them agreed to participate in the "
                       "study site visits (printed pp. 15-16)"),
          limitations=[
              {"statement": ("Printed p. 15: \"a relatively low response rate — about 25 "
                             "percent — to a survey sent to about 200 suppliers.\""),
               "impact": ("supplier coverage rests partly on the non-respondent follow-up, "
                          "the site visits and publicly available company information "
                          "rather than on survey responses")},
              {"statement": ("Printed p. 16: \"the authors did not formally compare the "
                             "respondents to the non-respondents — an additional analysis "
                             "step that could have further mitigated concern about the "
                             "response rate\"."),
               "impact": ("the risk that respondents differ systematically from "
                          "non-respondents was reduced by follow-up but never measured")}]),
        H)

    put(o("ev-amc-baseline", "Evidence", loc(15),
          title=("The other supplier information sources: the Army Materiel Command's "
                 "Industrial Base Baseline Assessment and six more"),
          evidenceType="Dataset", date="2013",
          pointer={"uri": anchor(15),
                   "custodian": ("U.S. Army Materiel Command and the Department of Defense "
                                 "(the sources themselves, not public); U.S. Government "
                                 "Accountability Office (the published description)")},
          classification={"level": "U", "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("Which suppliers make up the combat vehicle industrial "
                                "base, when the original equipment manufacturers will not "
                                "furnish a comprehensive list?"),
              "questionClass": "industrial-base",
              "intendedUse": ("mitigating the study's first limitation — no comprehensive "
                              "supplier list")},
          reviewStatus="reviewed",
          reviewers=[{"name": "A.T. Kearney", "role": "compiling analyst", "date": "2013"},
                     {"name": "U.S. Government Accountability Office",
                      "role": "mitigation reviewed against research standards",
                      "date": "2015-06"}],
          reliabilitySteps=["drs-original-sources"],
          inclusionReason=("the study's stated mitigation for the absence of a "
                           "comprehensive supplier list"),
          custodian="U.S. Army Materiel Command; Department of Defense; the combat vehicle "
                    "program offices",
          schemaRef=("verbatim, printed p. 15: \"the Army Materiel Command's Industrial "
                     "Base Baseline Assessment; a Department of Defense database of "
                     "suppliers; combat vehicle program manager interviews; other "
                     "industrial base studies; a sustainment engineering risk assessment; "
                     "ground combat systems consolidated parts lists; and lists of "
                     "long-lead items for various vehicles\""),
          limitations=[
              {"statement": ("Printed p. 15: the original equipment manufacturers elected, "
                             "for business competition reasons, not to furnish information "
                             "that clearly identified all the suppliers for each vehicle."),
               "impact": ("the supplier population is assembled from seven partial sources "
                          "rather than from one authoritative list; the study's authors "
                          "asserted they do not think they missed any key suppliers "
                          "(printed p. 16), which is an assertion, not a measurement")}]), H)

    put(o("ev-benchmark-data", "Evidence", loc(16),
          title=("Industry benchmark cost data, and the study's authors' own industry "
                 "experience, used where a supplier withheld proprietary cost data"),
          evidenceType="Dataset", date="2013",
          pointer={"uri": anchor(16),
                   "custodian": ("A.T. Kearney (the benchmark data, not public); U.S. "
                                 "Government Accountability Office (the published "
                                 "description)")},
          classification={"level": "U", "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("What range should a facility or supplier cost fall in, "
                                "when the supplier will not provide the actual figure?"),
              "questionClass": "industrial-base",
              "intendedUse": "the study's benchmark comparison and its cost baseline"},
          reviewStatus="reviewed",
          reviewers=[{"name": "A.T. Kearney", "role": "estimating analyst", "date": "2013"},
                     {"name": "U.S. Government Accountability Office",
                      "role": "mitigation reviewed against research standards",
                      "date": "2015-06"}],
          reliabilitySteps=["drs-supplier-review"],
          inclusionReason=("the study's stated mitigation where suppliers were reticent to "
                           "provide proprietary cost information"),
          custodian="A.T. Kearney",
          schemaRef=("an estimated range within which the authors expected a withheld cost "
                     "to fall, put back to the supplier to discuss whether it was a "
                     "reasonable proxy (printed p. 16)"),
          limitations=[
              {"statement": ("Some cost lines are estimated rather than reported: printed "
                             "p. 16 records that these efforts \"often resulted in the "
                             "supplier sharing the actual data\", which means they did not "
                             "always."),
               "impact": ("those cost lines are proxies wherever the supplier did not go on "
                          "to share the actual data, and GAO does not say how many did")}]),
        H)

    put(o("ev-oem-rates", "Evidence", loc(13),
          title=("Minimum sustainment rates as derived by the original equipment "
                 "manufacturers"),
          evidenceType="ExpertAssessment", date="2013",
          pointer={"uri": anchor(13),
                   "custodian": ("the original equipment manufacturers (the rates and their "
                                 "derivation, not public); U.S. Government Accountability "
                                 "Office (the published description)")},
          classification={"level": "U", "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("What is the minimum production rate a facility can sustain "
                                "financially?"),
              "questionClass": "industrial-base",
              "intendedUse": ("the study's scenario analysis and its assessment of the "
                              "effects of low demand")},
          reviewStatus="reviewed",
          reviewers=[{"name": "the original equipment manufacturers",
                      "role": "deriving party", "date": "2013"},
                     {"name": "U.S. Government Accountability Office",
                      "role": "assumption reviewed against research standards",
                      "date": "2015-06"}],
          reliabilitySteps=["drs-original-sources"],
          inclusionReason=("the rate the study's low-demand analysis turns on, and the one "
                           "input GAO says the study should have documented better"),
          experts=["the original equipment manufacturers"],
          method=("minimum sustainment rate as derived by each original equipment "
                  "manufacturer; the derivation itself is a recorded gap "
                  "(gap-msr-derivation)"),
          limitations=[
              {"statement": ("Printed p. 13: Army and commercial industry officials told "
                             "GAO that minimum sustainment rate \"is a somewhat subjective "
                             "term because different organizations may include different "
                             "cost assumptions in assessing the minimum production rate it "
                             "can sustain financially.\""),
               "impact": ("two manufacturers' rates are not necessarily comparable, and "
                          "printed p. 13 records that \"a change in the minimum sustainment "
                          "rate could impact the findings of a study\"")}]), H)

    put(o("ev-army-procurement-plans", "Evidence", loc(11, 12),
          title=("The Army's updated combat vehicle procurement plans and the recent "
                 "contractor actions current at the time of the study"),
          evidenceType="Document", publisher="Department of the Army", published="2013",
          date="2013",
          pointer={"uri": anchor(11),
                   "custodian": ("Department of the Army and the original equipment "
                                 "manufacturers (the plans and actions themselves, not "
                                 "public); U.S. Government Accountability Office (the "
                                 "published description)")},
          classification={"level": "U", "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("When does the Army anticipate restarting Bradley "
                                "production, and what has changed at the York facility "
                                "since 2012?"),
              "questionClass": "industrial-base",
              "intendedUse": ("the study's shutdown and restart cost assumptions for the "
                              "York facility")},
          reviewStatus="reviewed",
          reviewers=[{"name": "Department of the Army", "role": "issuing authority",
                      "date": "2013"},
                     {"name": "U.S. Government Accountability Office",
                      "role": "assumption reviewed against research standards",
                      "date": "2015-06"}],
          reliabilitySteps=["drs-original-sources"],
          inclusionReason=("the basis GAO gives for calling the shutdown assumptions "
                           "reasonable — \"they were based on current information, such as "
                           "updated procurement plans and recent contractor actions\" "
                           "(printed p. 11)"),
          limitations=[
              {"statement": ("The plans and the contractor actions are not public; GAO's "
                             "characterisation of them as current information is the whole "
                             "of the public account."),
               "impact": ("the currency of the plans, and therefore the reasonableness GAO "
                          "reads off it, cannot be checked against the plans themselves")}]),
        H)

    put(o("ev-oem-review-2013", "Evidence", loc(14),
          title=("Contractor-specific preliminary findings presented to the original "
                 "equipment manufacturers, May 2013"),
          evidenceType="Document", publisher="A.T. Kearney", published="2013-05",
          date="2013-05",
          pointer={"uri": anchor(14),
                   "custodian": ("A.T. Kearney and the original equipment manufacturers "
                                 "(the briefings, not public); U.S. Government "
                                 "Accountability Office (the published description)")},
          classification={"level": "U", "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("Are the study's facility-specific preliminary findings "
                                "accurate, in the view of the manufacturer whose facility "
                                "they describe?"),
              "questionClass": "industrial-base",
              "intendedUse": ("giving the original equipment manufacturers an opportunity "
                              "to weigh in on the accuracy of the findings related to "
                              "their facility")},
          reviewStatus="reviewed",
          reviewers=[{"name": "BAE Systems and General Dynamics Land Systems (the two "
                              "original equipment manufacturers)",
                      "role": "reviewing party", "date": "2013-05"},
                     {"name": "U.S. Government Accountability Office",
                      "role": "corroborated in interviews with the manufacturers",
                      "date": "2015-06"}],
          reliabilitySteps=["drs-supplier-review"],
          inclusionReason=("the evidence produced by the study's independent disconfirming "
                           "review; the bias check bc-oem-review names it"),
          limitations=[
              {"statement": ("The review covered contractor-specific preliminary findings, "
                             "not the final report: printed p. 18 records that the "
                             "manufacturers and suppliers had not received copies of the "
                             "final report."),
               "impact": ("the disconfirming review reaches the facility findings, not the "
                          "conclusions as finally presented")}]), H)

    put(o("ev-abrams-cost-data", "Evidence", loc(16, 17),
          title=("Government expenses at the Joint Systems Manufacturing Center, obtained "
                 "from the Abrams program office, and the facilities' financial data"),
          evidenceType="Dataset", date="2013",
          pointer={"uri": anchor(16),
                   "custodian": ("the Abrams program office and the production facilities "
                                 "(the data itself, not public); U.S. Government "
                                 "Accountability Office (the published description)")},
          classification={"level": "U", "metadataLevel": "U"},
          scopeOfValidity={
              "builtToAnswer": ("What does the government spend at the Joint Systems "
                                "Manufacturing Center, and what are the facilities' "
                                "financial baselines?"),
              "questionClass": "industrial-base",
              "intendedUse": ("the study's cost baseline for the government-owned, "
                              "contractor-operated facility, and the baseline data used to "
                              "develop scenarios")},
          reviewStatus="reviewed",
          reviewers=[{"name": "Abrams program office", "role": "providing office",
                      "date": "2013"},
                     {"name": "Defense Contract Management Agency",
                      "role": ("reviewed the facilities' financial data (printed p. 17)"),
                      "date": "2013"}],
          reliabilitySteps=["drs-abrams-program-office"],
          inclusionReason=("GAO's worked example of the study going to the original source "
                           "for government cost data"),
          custodian="Abrams program office; the production facilities",
          schemaRef=("government expenses at the Joint Systems Manufacturing Center, and "
                     "per-facility baseline data — cost, hours per unit, manufacturing "
                     "capability (printed p. 17)"),
          limitations=[
              {"statement": ("Printed p. 17: where a firm elected not to provide company "
                             "data, the authors estimated the firm's financial information "
                             "from various sources and met with the firm to review those "
                             "estimates for accuracy."),
               "impact": ("some facility baselines are reviewed estimates rather than "
                          "reported figures, and GAO does not say which")}]), H)


# ---- the decision-class policy, the charter, the models -------------------------------


def _policy_and_charter(g: Graph) -> None:
    put = g.put

    put(own(
        "pol-kearney", "Policy",
        name=(
            "Industrial-base study assessed against GAO's 21 published questions, "
            "aggregated by GAO's own stated rule. GAO-23-106549 printed p. 17: \"we drew "
            "conclusions that the report was generally objective when available "
            "information presented in the report was consistent with our definition of "
            "objectivity but was missing information that would have addressed the "
            "generally accepted research standards.\" That is a rule about missing "
            "information, not a count of it, so aggregationK is set high enough that "
            "generally_X holds unless a mapped question reaches state 3 or 4. See "
            "docs/decisions/2026-09-05-aggregation-k-is-a-policy-parameter.md and the "
            "README: the parameter is a policy choice, not a kernel change, the qualifier "
            "sentence on each verdict names every state-2 question, and the value is "
            "pending Shreyash's sign-off."),
        version="0.1", decisionClass="industrial-base-study",
        # Schema-forced: `method` is an enum of {mavt, ahp, topsis, pugh} and the enum has
        # no value for a six-analysis consulting method. `mavt` is the closest and is
        # disclosed in the README; no MAVT arithmetic is run in this control.
        method="mavt", tailoring="gao-15-548", aggregationK=21,
        requiredBiasChecks=["independent-disconfirming-review"],
        requireAllLinchpinsVaried=False, prohibitedExclusionReasons=["time-or-resource"],
        blockingRules=[], nSimplex=200), H)

    put(o("ch-kearney-2014", "Charter", loc(5, 8, 11, 13, 15),
          question=(
              "Verbatim, printed p. 8: the study's objective was \"to complete an "
              "assessment of the combined commercial and government combat vehicle "
              "industrial base and develop viable strategic alternatives to sustain that "
              "base within a constrained fiscal environment.\""),
          decisionToBeMade=(
              "Which investments the Army should make in the combat vehicle industrial "
              "base, and whether to accept a production break at the Bradley line at the "
              "York, Pennsylvania facility (printed pp. 5, 11)."),
          consequencesOfErroneousOutput=(
              "Printed p. 5: decreased production of combat vehicles \"could lead to the "
              "loss of critical skills, production infrastructure, and key suppliers\", "
              "and the Army's 2011 Industrial Base Baseline Assessment indicates these "
              "effects could \"negatively affect the military's ability to quickly restart "
              "production of parts and vehicles for future combat operations.\""),
          questionClass="industrial-base",
          scope={
              "included": [
                  "the Abrams main battle tank", "the Bradley Family of Vehicles",
                  "the Stryker Family of Vehicles",
                  "the M109 Paladin Family of Vehicles", "the M88 Recovery Vehicle",
                  "the M113 Armored Personnel Carrier Family of Vehicles",
                  "the Ground Combat Vehicle", "the Armored Multi-Purpose Vehicle",
                  "U.S. Marine Corps combat vehicles",
                  "the Joint Systems Manufacturing Center, Lima, Ohio",
                  "the BAE facilities in York, Pennsylvania",
                  "the Anniston Army Depot, Anniston, Alabama",
                  "the GDLS facility in London, Ontario", "the Red River Army Depot",
                  "the suppliers who furnish parts and equipment to the combat vehicle "
                  "original equipment manufacturers",
                  "an in-depth assessment of the potential costs of shutting down the York "
                  "production facility (printed p. 10)"],
              # GAO records no exclusion from the study's scope; printed p. 18 says the
              # study went *beyond* the congressional direction. An empty list is the
              # complete answer here, not a silence.
              "excluded": []},
          definitions=[
              {"term": "combat vehicle industrial base",
               "text": ("Printed p. 5: \"many separate but interrelated facilities in both "
                        "the government and commercial sectors\" — the government depots "
                        "and the government-owned contractor-operated Joint Systems "
                        "Manufacturing Center, the commercial production facilities, and "
                        "\"hundreds of suppliers who furnish parts and equipment to the "
                        "combat vehicle original equipment manufacturers.\"")},
              {"term": "minimum sustainment rate",
               "text": ("Printed p. 13, as GAO reports it: Army and commercial industry "
                        "officials have noted that minimum sustainment rate \"is a somewhat "
                        "subjective term because different organizations may include "
                        "different cost assumptions in assessing the minimum production "
                        "rate it can sustain financially.\" The study used the rates as "
                        "derived by the original equipment manufacturers; how they were "
                        "derived is a recorded gap (gap-msr-derivation), carried on the "
                        "assumption that uses them, not on this definition.")}],
          conditionsOfInterest=["constrained fiscal environment"],
          # The four limitations GAO lists at printed p. 15, each with the mitigation GAO
          # records at printed pp. 15-16. Three of the four resolve to an evidence item in
          # the register rather than to a sentence alone.
          limitations=[
              {"statement": ("Printed p. 15: \"the study's authors were not provided with a "
                             "comprehensive list of suppliers.\""),
               "mitigation": ("The authors obtained as much supplier information as "
                              "possible from seven other sources, including the Army "
                              "Materiel Command's Industrial Base Baseline Assessment "
                              "(ev-amc-baseline; printed p. 15).")},
              {"statement": ("Printed p. 15: \"there was a relatively low completion rate "
                             "on the survey sent to the suppliers\" — about 25 percent of "
                             "about 200 suppliers."),
               "mitigation": ("The authors obtained publicly available company and credit "
                              "rating information on the non-respondents and secured site "
                              "visits with over 20 of them (drs-nonrespondent-followup; "
                              "printed pp. 15-16). GAO notes the authors did not formally "
                              "compare respondents to non-respondents.")},
              {"statement": ("Printed p. 15: \"the study's authors were not always provided "
                             "with the facility data they requested\", suppliers being "
                             "reticent about proprietary information."),
               "mitigation": ("The authors used industry benchmark data and their own "
                              "industry experience to estimate a cost range and put the "
                              "estimate back to the supplier, which often resulted in the "
                              "supplier sharing the actual data (ev-benchmark-data; printed "
                              "p. 16).")},
              {"statement": ("Printed p. 15: \"facilities included different elements in "
                             "their overhead rates, potentially limiting comparison of "
                             "overhead rates across the differing facilities.\""),
               "mitigation": ("The authors examined the time charges for the accounts that "
                              "contribute to factory overhead and normalised them so that "
                              "each facility's overhead rate was comprised of the same "
                              "elements (drs-normalise-overhead; printed p. 16).")}],
          authority={
              "signer": ("Department of the Army (the study's client; the Office of the "
                         "Assistant Secretary of the Army for Acquisition, Logistics, and "
                         "Technology answered for it on GAO's draft, printed p. 19)"),
              "board": ("the congressional defense committees, under Senate Report 112-173 "
                        "and the conference report to the National Defense Authorization "
                        "Act for Fiscal Year 2013 (printed pp. 1 fn 2, 5)")},
          successCriteria=[
              "an assessment of the combined commercial and government combat vehicle "
              "industrial base",
              "viable strategic alternatives to sustain that base within a constrained "
              "fiscal environment",
              "the financial impact and risk of a production break for the Bradley Fighting "
              "Vehicle",
              "the Army's analysis and plans for the government-owned/contractor-operated "
              "tank production facility"],
          decisionClassPolicy="pol-kearney",
          mandateElements=["me-ndaa13-bradley", "me-sasc-goco"]), H)

    put(o("me-ndaa13-bradley", "MandateElement", loc(1, 5, 8),
          text=("The conferees for the National Defense Authorization Act for Fiscal Year "
                "2013 directed the Secretary of the Army to report to the congressional "
                "defense committees on the Bradley Fighting Vehicle industrial base, "
                "including an assessment of the financial impact and risk of a production "
                "break — the cost of shutdown compared with the cost of continued "
                "production — and of the industrial capability and capacity impact and "
                "risk, including the loss of a specialised workforce and supplier base."),
          source=("H.R. Rep. No. 112-705, at 885 (2012) (Conf. Rep.), as quoted at GAO-15-548 "
                  "printed p. 1 fn 2"),
          satisfiedBy=["cl-shutdown-cost", "cl-mandate-coverage"], status="satisfied"), H)

    put(o("me-sasc-goco", "MandateElement", loc(1, 5, 8),
          text=("Senate Report 112-173 directed the Secretary of the Army to report on the "
                "Army's analysis and plans to utilise and configure its "
                "government-owned/contractor-operated facility, where Abrams tanks are "
                "produced, to meet the Army's tank and other tracked and wheeled vehicle "
                "production requirements to 2025 and beyond."),
          source=("S. Rep. No. 112-173, at 23-24 (2012), as quoted at GAO-15-548 printed "
                  "p. 1 fn 2"),
          satisfiedBy=["cl-mandate-coverage"], status="satisfied"), H)

    # -- the two models, and their VV&A records ---------------------------------------
    #
    # `Model.definition.version` is required and is not a slot, so a model the public
    # account never versions has to carry a string saying so. Disclosed in the README.

    put(o("mdl-kearney-financial", "Model", loc(13, 14),
          name="The study's spreadsheet-based financial consequence model",
          definition={"kind": "code", "version": "unversioned in the public description"},
          intendedUse=(
              "Verbatim, printed pp. 13-14 (the sentence begins on p. 13 and finishes on "
              "p. 14): the study's authors \"used the information collected through the "
              "current state assessment and the cost baseline to develop a "
              "spreadsheet-based model to examine the financial consequences to various "
              "manufacturers and suppliers in the industrial base based on different "
              "levels of demand.\" Printed p. 14: \"These scenarios were run through the "
              "model to help the Army develop potential courses of action to alter the "
              "structure of the combat vehicle industrial base.\""),
          questionClass="industrial-base", vvaRecord="vva-kearney",
          qualificationStatus="validated",
          inputs=["m-current-state", "m-cost-baseline"],
          outputs=["m-scenario-analysis"],
          limitations=[
              {"statement": ("Printed p. 14 fn 8: \"This model was developed to support the "
                             "continued analysis of future state industrial base "
                             "environmental changes.\" It was built for this study and for "
                             "its continuation, not as a general-purpose cost model."),
               "justification": ("GAO found the study \"was executed in accordance with its "
                                 "defined methodology\" and that the authors \"successfully "
                                 "conducted each of the six analyses\" (printed p. 13), the "
                                 "scenario analysis among them.")},
              {"statement": ("The model's own construction is not public: GAO describes "
                             "what it does and what went into it, not how it computes."),
               "justification": ("GAO's assessment is of the reasonableness of the study's "
                                 "methods (printed p. 2); the model's internals were "
                                 "available to GAO through the backup slides that detail "
                                 "the methodological elements of the study, and are not "
                                 "available to this record.")}]), H)

    put(o("mdl-kearney-method", "Model", loc(9, 13),
          name="The six-analysis industrial base assessment method",
          definition={"kind": "rubric", "version": "unversioned in the public description"},
          intendedUse=(
              "Verbatim, printed p. 13: the study's authors \"successfully conducted each "
              "of the six analyses — the current state assessment, cost baseline, supplier "
              "base analysis, benchmark comparison, scenario analysis, and network strategy "
              "plan.\" Printed p. 9 assigns the first four to assessing the industrial base "
              "and the last two to developing strategic alternatives."),
          questionClass="industrial-base", vvaRecord="vva-kearney-method",
          qualificationStatus="validated",
          inputs=MEASURE_IDS,
          limitations=[
              {"statement": ("Five of the six analyses are qualitative: GAO reports their "
                             "findings, not scores, and this record therefore carries no "
                             "Observation and no evaluation run."),
               "justification": ("GAO's own conclusion is qualitative for the same reason "
                                 "— printed p. 24: \"we determined that qualitative "
                                 "assessment ratings provide the best explanation of the "
                                 "nuances of the analysis and findings, rather than numeric "
                                 "ratings for each individual standard.\"")}]), H)

    put(o("vva-kearney", "VVARecord", loc(2, 13, 14),
          problemStatement="ch-kearney-2014",
          requirementsAndAcceptabilityCriteria=(
              "Printed p. 13: the model had to examine the financial consequences to "
              "various manufacturers and suppliers in the industrial base at different "
              "levels of demand, from the current state assessment and the cost baseline. "
              "No numeric acceptance criterion appears in the public account."),
          assumptionsCapabilitiesLimitationsRisks={
              "assumptions": [
                  "the minimum sustainment rates as derived by the original equipment "
                  "manufacturers (printed p. 13; the derivation is gap-msr-derivation)",
                  "risk assessed from the perspective of the Army (printed pp. 12-13; GAO "
                  "reads this as an assumption the study did not identify as one)"],
              "capabilities": [
                  "financial consequence to each manufacturer and supplier at a given level "
                  "of demand (printed p. 13)",
                  "scenarios run through the model to develop courses of action to alter "
                  "the structure of the industrial base (printed p. 14)"],
              "limitations": [
                  "developed to support the continued analysis of future state industrial "
                  "base environmental changes, not as a general cost model (printed p. 14 "
                  "fn 8)",
                  "rests on cost data that are in part benchmark estimates rather than "
                  "reported figures (printed p. 16)"],
              "risks": [
                  "printed p. 13: \"a change in the minimum sustainment rate could impact "
                  "the findings of a study\""]},
          methodology=(
              "Printed p. 13: a spreadsheet-based model built from the current state "
              "assessment and the cost baseline, exercised over demand scenarios."),
          # DECISION: the accreditation basis recorded here is the study's own
          # documentation, on the strength of GAO printed p. 2 — GAO reviewed "interim and
          # final study briefings, backup slides that detail the methodological elements of
          # the study, and the final report to the congressional defense committees" and
          # found the method sound. This is OUR reading and is labelled as such in
          # expected.yaml and the README. It is what distinguishes this case from the
          # GAO-21-460 reconstruction, where the same field is honestly a gap because
          # GAO-21-460 printed p. 35 says the study's final report was not available.
          accreditationDecision={
              "authority": "A.T. Kearney (the study's authors)", "date": "2014-04",
              "scope": ("the financial consequences to manufacturers and suppliers in the "
                        "combat vehicle industrial base at different levels of demand"),
              "basis": "document", "document": "ev-kearney-final-report"},
          sections=_vva_sections({
              "Problem Statement": "See the charter, ch-kearney-2014.",
              "M&S Requirements and Acceptability Criteria":
                  ("Examine the financial consequences to manufacturers and suppliers at "
                   "different levels of demand (printed p. 13). No numeric acceptance "
                   "criterion is public."),
              "M&S Assumptions, Capabilities, Limitations & Risks/Impacts":
                  "As listed in the structured field of this record.",
              "Accreditation Methodology":
                  ("GAO reviewed the interim and final study briefings, the backup slides "
                   "detailing the methodological elements of the study, and the final "
                   "report, and found the study executed in accordance with its defined "
                   "methodology (printed pp. 2, 13). Reading that as the accreditation "
                   "basis is ours."),
              "Key Participants":
                  ("A.T. Kearney (authors); the Army Program Executive Office for Ground "
                   "Combat Systems; the two original equipment manufacturers; shreyash "
                   "(reconstruction)."),
              "Resources":
                  ("GAO-15-548 and nothing else; the study's own documentation is not "
                   "public (gap-kearney-report)."),
          })), H)

    put(o("vva-kearney-method", "VVARecord", loc(2, 9, 13),
          problemStatement="ch-kearney-2014",
          requirementsAndAcceptabilityCriteria=(
              "Printed p. 9: the methodology had to be consistent with and address the "
              "study's objective. Printed p. 13: each of the six analyses had to be "
              "conducted as defined."),
          assumptionsCapabilitiesLimitationsRisks={
              "assumptions": [
                  "the six analyses together answer both halves of the study's objective "
                  "(printed p. 9)"],
              "capabilities": [
                  "current state assessment, cost baseline, supplier base analysis and "
                  "benchmark comparison, addressing the state of the industrial base "
                  "(printed p. 9)",
                  "scenario analysis and network strategy plan, addressing strategic "
                  "alternatives to sustain it (printed p. 9)"],
              "limitations": [
                  "five of the six analyses are qualitative; GAO reports findings, not "
                  "scores",
                  "the criteria each analysis was scored against are not public "
                  "(gap-criteria)"],
              "risks": [
                  "printed p. 14: the original equipment manufacturers thought the number "
                  "of critical skills identified was too low, though GAO found the "
                  "criteria reasonable and reasonably applied"]},
          methodology=(
              "Printed p. 9: four elements addressing the assessment of the industrial "
              "base and two addressing the development of strategic alternatives, "
              "described in more detail in figure 2 at printed p. 10."),
          accreditationDecision={
              "authority": "A.T. Kearney (the study's authors)", "date": "2014-04",
              "scope": ("the six-analysis assessment of the combined commercial and "
                        "government combat vehicle industrial base"),
              "basis": "document", "document": "ev-kearney-final-report"},
          sections=_vva_sections({
              "Problem Statement": "See the charter, ch-kearney-2014.",
              "M&S Requirements and Acceptability Criteria":
                  ("The methodology had to be consistent with and address the study's "
                   "objective, and each of the six analyses had to be conducted as defined "
                   "(printed pp. 9, 13)."),
              "M&S Assumptions, Capabilities, Limitations & Risks/Impacts":
                  "As listed in the structured field of this record.",
              "Accreditation Methodology":
                  ("GAO found the study executed in accordance with its defined "
                   "methodology and the six analyses successfully conducted (printed "
                   "p. 13). Reading that as the accreditation basis is ours."),
              "Key Participants":
                  ("A.T. Kearney (authors); GAO (assessment against generally accepted "
                   "research standards); shreyash (reconstruction)."),
              "Resources":
                  ("GAO-15-548 and nothing else; the study's own documentation is not "
                   "public (gap-kearney-report)."),
          })), H)


# ---- objectives, measures, alternatives, GRC&A ----------------------------------------


def _value_model(g: Graph) -> None:
    put = g.put

    put(o("obj-viability", "Objective", loc(8, 9),
          name=("Assess the combined commercial and government combat vehicle industrial "
                "base"),
          description=("The first half of the study's objective (printed p. 8). GAO printed "
                       "p. 9 assigns four of the six analyses to it: the current state "
                       "assessment, the cost baseline, the supplier base analysis and the "
                       "benchmark comparison."),
          priority="primary", priorityRank=1,
          measures=["m-current-state", "m-cost-baseline", "m-supplier-base", "m-benchmark"],
          provenance="ev-gao-15-548"), H)

    put(o("obj-alternatives", "Objective", loc(8, 9),
          name=("Develop viable strategic alternatives to sustain that base within a "
                "constrained fiscal environment"),
          description=("The second half of the study's objective (printed p. 8). GAO "
                       "printed p. 9 assigns the remaining two analyses to it: the scenario "
                       "analysis and the network strategy plan."),
          priority="secondary", priorityRank=2,
          measures=["m-scenario-analysis", "m-network-strategy"],
          provenance="ev-gao-15-548"), H)

    for mid, obj_id, task, attribute, measure, units, direction, pages in MEASURES:
        put(o(mid, "Measure", loc(*pages), objective=obj_id, task=task, attribute=attribute,
              measure=measure, metric={"units": units, "direction": direction},
              criteria={"$gap": "gap-criteria"},
              conditions=["constrained fiscal environment"]), H)

    for aid, name, description, baseline, order, pages in ALTERNATIVES:
        put(o(aid, "Alternative", loc(*pages), name=name, description=description,
              status="evaluated", baselineFlag=baseline, enteredOrder=order), H)

    put(o("gr-three-programs", "GroundRule", loc(8, 9),
          statement=("Verbatim, printed p. 8: \"the study primarily focused on three "
                     "programs — the Abrams, Bradley, and Stryker vehicles\". GAO found "
                     "this appropriate given the congressional language and because these "
                     "three comprise a large portion of combat vehicle production; the "
                     "scope nonetheless covered all the key combat vehicles."),
          source="ev-gao-15-548"), H)

    put(o("con-fiscal", "Constraint", loc(5, 8),
          statement=("Verbatim, printed p. 8: the strategic alternatives had to sustain the "
                     "combat vehicle industrial base \"within a constrained fiscal "
                     "environment\"."),
          kind="programmatic", source="ev-gao-15-548",
          implications=(
              "The alternatives had to sustain the base at a reduced rate of demand rather "
              "than by buying more vehicles: printed p. 1 records the Army's budget request "
              "for these vehicles falling from $8.8 billion in 2010 to $1.7 billion in 2013 "
              "with further decreases anticipated between 2015 and 2019, and printed p. 5 "
              "records the concern that the corresponding decrease could make the base "
              "unsustainable. It is why the scenario analysis is framed on levels of "
              "demand and why the network strategy plan considers consolidation.")), H)

    put(o("sc-demand-levels", "Scenario", loc(12, 13, 14),
          name="Different levels of demand for combat vehicles",
          description=("Printed pp. 13-14: the spreadsheet-based model examined the "
                       "financial consequences to various manufacturers and suppliers "
                       "\"based on different levels of demand\", and those scenarios were "
                       "run through the model to help the Army develop potential courses of "
                       "action."),
          rationale=("Printed p. 12: the study \"explicitly identified and appropriately "
                     "varied assumptions about the expected demand for combat vehicles when "
                     "developing scenarios for the combat vehicle industrial base using "
                     "sensitivity analysis\", which GAO calls \"a key characteristic for a "
                     "credible study based on generally accepted research standards\". "
                     "Printed p. 6 records the study's finding that production and "
                     "sustainment demand is the factor with the most impact on the "
                     "industrial base."),
          conditions=["constrained fiscal environment"], source="ev-gao-15-548"), H)


def _assumptions(g: Graph) -> None:
    put = g.put

    put(o("as-warm-shutdown", "Assumption", loc(11),
          statement=("Verbatim, printed p. 11: the Army's study assumed \"a two-year "
                     "shutdown of the Bradley line followed by restart, which the study's "
                     "authors termed a 'warm shutdown,' because the shutdown included an "
                     "anticipated restart date.\""),
          linchpin=True,
          rationale=("Verbatim, printed p. 11: \"This assumption was reasonable because it "
                     "was based on the Army's anticipated time frame for restarting "
                     "production at the time of the study.\" GAO adds that the shutdown "
                     "assumptions generally were reasonable \"because they were based on "
                     "current information, such as updated procurement plans and recent "
                     "contractor actions.\""),
          evidence="ev-army-procurement-plans",
          implicationsIfWrong=("The $53 million shutdown-and-restart estimate would not "
                               "hold (printed p. 11): a longer break, or one with no "
                               "anticipated restart date, changes the inventory and "
                               "employee cost treatment the estimate rests on, and with it "
                               "the comparison against the 2012 original equipment "
                               "manufacturer estimate of $750 million."),
          indicatorsThatWouldAlter=[
              "a change in the Army's anticipated restart date for Bradley production",
              "a change in the Army's Bradley procurement plans",
              "a decision to shut the line down without an anticipated restart date"],
          variedInSensitivity=False), H)

    put(o("as-york-costs", "Assumption", loc(11),
          statement=("Printed p. 11: the inventory cost estimate was based on costs "
                     "associated with the disposition of the inventory of the current "
                     "Bradley production line at the York facility, and the employee cost "
                     "estimate included only the employee costs associated with that same "
                     "line."),
          linchpin=False,
          rationale=("Printed p. 11: GAO found this \"appropriate since it was consistent "
                     "with the assumption of a 2-year shutdown of Bradley production at "
                     "this particular facility\", and printed p. 11 fn 7 records that at "
                     "the time of the study it was not anticipated that the Abrams "
                     "production line would be shut down."),
          evidence="ev-manufacturer-data",
          implicationsIfWrong=("If a shutdown reached beyond the current Bradley line — "
                               "other lines at York, or inventory held elsewhere — the "
                               "$53 million estimate would understate the cost."),
          indicatorsThatWouldAlter=[
              "a shutdown scope extending beyond the current Bradley production line at "
              "York",
              "an anticipated shutdown of the Abrams production line"],
          variedInSensitivity=False), H)

    put(o("as-min-sustainment-rate", "Assumption", loc(13),
          statement=("Verbatim, printed p. 13: the study \"used the minimum sustainment "
                     "rates as derived by the original equipment manufacturers, but did not "
                     "include specific information on how that minimum sustainment rate was "
                     "derived.\""),
          linchpin=False,
          # This is the object that makes DES-4 rate 2: the ladder is
          # `assumptions_all_have_rationale -> 1`, else `assumptions_listed -> 2`, and a
          # rationale that is a recorded gap is not content. The charter-definition route
          # (`definition-missing`) drives DES-2/DES-3 instead, and both definitions here
          # carry text, so it does not fire.
          rationale={"$gap": "gap-msr-derivation"},
          evidence="ev-oem-rates",
          implicationsIfWrong=("Verbatim, printed p. 13: \"a change in the minimum "
                               "sustainment rate could impact the findings of a study\". "
                               "GAO adds that it does not believe the lack of explicitly "
                               "stated information materially affected the results of this "
                               "one."),
          indicatorsThatWouldAlter=[
              "a published derivation of the minimum sustainment rate",
              "a manufacturer restating its minimum sustainment rate on different cost "
              "assumptions"],
          variedInSensitivity=False), H)

    put(o("as-army-risk-perspective", "Assumption", loc(12, 13),
          statement=("Verbatim, printed p. 12: \"a key assumption that was not explicitly "
                     "identified was that the study assessed risk from the perspective of "
                     "the Army\" — that at some future date the Army would not have access "
                     "to a needed manufacturing capability or critical supply component, "
                     "rather than the risk to the original equipment manufacturers or the "
                     "individual suppliers."),
          linchpin=False,
          rationale={"$gap": "gap-risk-perspective-rationale"},
          evidence="ev-gao-15-548",
          implicationsIfWrong=("A supplier-side or manufacturer-side reading of risk would "
                               "rank the fragile suppliers differently, and could change "
                               "which suppliers the study says require direct Army action "
                               "(printed p. 14)."),
          indicatorsThatWouldAlter=[
              "the study, or a successor, states the perspective from which risk is "
              "assessed",
              "a manufacturer- or supplier-perspective risk assessment of the same base"],
          variedInSensitivity=False), H)

    put(o("as-demand-scenarios", "Assumption", loc(12),
          statement=("Printed p. 12: assumptions about the expected demand for combat "
                     "vehicles, used when developing the scenarios for the combat vehicle "
                     "industrial base."),
          linchpin=False,
          rationale=("Verbatim, printed p. 12: the study \"explicitly identified and "
                     "appropriately varied assumptions about the expected demand for combat "
                     "vehicles when developing scenarios for the combat vehicle industrial "
                     "base using sensitivity analysis\", which GAO defines as \"identifying "
                     "key elements and varying the assumed value of a single element while "
                     "holding the others constant to identify the extent to which a "
                     "conclusion relies on a particular value for that element\" and calls "
                     "\"a key characteristic for a credible study\"."),
          evidence="ev-gao-15-548",
          implicationsIfWrong=("The scenarios would bracket the wrong range of demand, and "
                               "the financial consequences the model reports for each "
                               "manufacturer and supplier would be computed off it."),
          indicatorsThatWouldAlter=[
              "a change in the Army's anticipated combat vehicle production between 2015 "
              "and 2019",
              "a demand level outside the range the study's scenarios varied over"],
          # This is what gives DES-6 state 2 via `any_assumption_varied`. GAO credits the
          # study's sensitivity analysis explicitly at printed p. 12; nothing in this
          # record says the study lacked one.
          variedInSensitivity=True), H)


# ---- the plan, the bias check, the claims, the episode --------------------------------


STEP_AUTHORITY = {
    "document": ("GAO, Army Combat Vehicles: Industrial Base Study's Approach Met Research "
                 "Standards, GAO-15-548 (16 June 2015)"),
    "paragraph": ("'The Study's Objective, Scope, and Methodology Were Reasonable', printed "
                  "p. 9 (the six methodological elements), and 'The Study was Executed in "
                  "Accordance with the Defined Methodology', printed p. 13"),
}

# (step id, evaluator, measure)
STEPS = [
    ("current-state", "mdl-kearney-method", "m-current-state"),
    ("cost-baseline", "mdl-kearney-method", "m-cost-baseline"),
    ("supplier-base", "mdl-kearney-method", "m-supplier-base"),
    ("benchmark", "mdl-kearney-method", "m-benchmark"),
    ("scenario-analysis", "mdl-kearney-financial", "m-scenario-analysis"),
    ("network-strategy", "mdl-kearney-method", "m-network-strategy"),
]


def _plan_and_checks(g: Graph) -> None:
    put = g.put

    put(own("ws-kearney", "WeightSet",
            name=("Equal weight across the six analyses — OURS, not the study's. GAO's "
                  "account does not say the six analyses were weighted, or combined into a "
                  "single score at all."),
            method="equal",
            weights={mid: 1 / 6 for mid in MEASURE_IDS},
            provenance={"$gap": "gap-weights"}), H)

    put(o("pl-kearney", "Plan", loc(9, 13, 18), episode=EPISODE, policyBasis="pol-kearney",
          steps=[{"id": sid, "evaluator": evaluator, "method": "mavt",
                  "alternatives": [a[0] for a in ALTERNATIVES], "measures": [measure],
                  "weightSet": "ws-kearney", "sensitivitySweeps": [],
                  "biasChecks": ["bc-oem-review"], "authority": STEP_AUTHORITY}
                 for sid, evaluator, measure in STEPS],
          # An explicit empty list, not an absent field: GAO printed p. 13 found the study
          # "was executed in accordance with its defined methodology", so "no deviations"
          # is a supported statement here rather than a silence.
          deviations=[],
          # The approval recorded is the Army's, on the study's methodology, not an
          # approval of this reconstruction: printed p. 18, "The Army issued a contract
          # with the management consulting firm in October 2012". Disclosed in the README.
          approvedBy={"actorId": ("Department of the Army (contract with the management "
                                  "consulting firm, October 2012)"),
                      "date": "2012-10"}), H)

    put(o("bc-oem-review", "BiasCheck", loc(14),
          checkType="independent-disconfirming-review", requiredBy="pol-kearney",
          performedBy="A.T. Kearney", performedAt="2013-05",
          producedEvidence="ev-oem-review-2013", status="performed"), H)


CLAIMS = [
    ("cl-excess-capacity", (17,), "evaluation-results", ["obj-viability"],
     ("Verbatim, printed p. 17: the final report \"clearly concluded that there was "
      "significant excess in large structure machining capacity throughout the ground "
      "combat vehicle manufacturing network\", and linked that conclusion to the study's "
      "assessment of manufacturing capabilities. GAO found the conclusion reasonable in "
      "that it flowed logically from the evidence collected based on the methodology."),
     ["ev-gao-15-548"], []),
    ("cl-critical-suppliers", (14, 15), "evaluation-results", ["obj-viability"],
     ("Printed p. 14: on the information collected and analysed as part of its supplier "
      "base analysis, including interviews and site visits with 72 suppliers, the study "
      "identified several key suppliers that required direct action by the Army to ensure "
      "that production of key items continues during the period of low demand."),
     ["ev-gao-15-548", "ev-supplier-survey", "ev-amc-baseline"], []),
    ("cl-critical-skills", (14,), "evaluation-results", ["obj-viability"],
     ("Verbatim, printed p. 14: through an assessment of critical manufacturing skills "
      "within the current state assessment, \"the study identified the most critical and "
      "at-risk skills as various types of welding and inspection.\" GAO records that the "
      "original equipment manufacturers thought the number identified was too low, and that "
      "GAO nonetheless found the criteria reasonable and reasonably applied."),
     ["ev-gao-15-548"], []),
    ("cl-cost-baseline", (13,), "evaluation-results", ["obj-viability"],
     ("Verbatim, printed p. 13: to establish a cost baseline the study's authors identified "
      "the costs of various manufacturing processes for combat vehicles at different "
      "production facilities \"by requesting data from manufacturers and suppliers, "
      "observing production operations, walking along production lines and interviewing "
      "production workers about production operations at both government and commercial "
      "manufacturing facilities.\""),
     ["ev-gao-15-548", "ev-manufacturer-data"], []),
    ("cl-benchmark-estimates", (16,), "evaluation-results", ["obj-viability"],
     ("Printed p. 16: where suppliers were reticent to provide proprietary cost information, "
      "the study's authors used industry benchmark data and their own industry experience to "
      "estimate a range within which they expected the costs to fall, then provided that "
      "estimate to the supplier to discuss whether it was a reasonable proxy — which, the "
      "authors told GAO, often resulted in the supplier sharing the actual data."),
     ["ev-gao-15-548", "ev-benchmark-data"], []),
    ("cl-data-valid-reliable", (16, 17), "evidence-register", ["obj-viability"],
     ("Printed pp. 16-17: the study's authors went to the original sources to obtain "
      "relevant information and sought clarification to make sure they understood the data "
      "provided — obtaining government expenses at the Joint Systems Manufacturing Center "
      "directly from the Abrams program office, and using facility financial data that had "
      "also been reviewed by the Defense Contract Management Agency."),
     ["ev-gao-15-548", "ev-abrams-cost-data"], []),
    ("cl-min-sustainment-rate", (13,), "grca", ["obj-viability"],
     ("Verbatim, printed p. 13: the study \"noted that it used the minimum sustainment rates "
      "as derived by the original equipment manufacturers, but did not include specific "
      "information on how that minimum sustainment rate was derived\". GAO judged that the "
      "lack of explicitly stated information did not materially affect the results of the "
      "study, but that more explicit information would have been useful to the study's "
      "stakeholders."),
     ["ev-gao-15-548", "ev-oem-rates"], []),
    ("cl-oem-review", (14,), "bias-checks", ["obj-viability"],
     ("Verbatim, printed p. 14: as part of executing the defined methodology, "
      "\"contractor-specific preliminary findings were presented to the original equipment "
      "manufacturers in May 2013\", which gave them an opportunity to weigh in on the "
      "accuracy of the findings related to their facility."),
     ["ev-gao-15-548", "ev-oem-review-2013"], []),
    ("cl-shutdown-cost", (11, 12), "evaluation-results", ["obj-alternatives"],
     ("Printed p. 11: the Army's study estimated $53 million for a shutdown and restart of "
      "the Bradley Fighting Vehicle production line, against a 2012 original equipment "
      "manufacturer study's $750 million, and \"appropriately cautions against comparison of "
      "these results\" because the two studies had very different assumptions caused by "
      "differing time frames and by actions the Army and the manufacturer took in the "
      "intervening time. Printed p. 12 records that the manufacturer agreed the two "
      "estimates could not be compared."),
     ["ev-gao-15-548", "ev-army-procurement-plans"], ["me-ndaa13-bradley"]),
    ("cl-mandate-coverage", (18,), "mandate-elements", ["obj-viability"],
     ("Printed p. 18: the final report addressed the information required by the "
      "congressional direction — an assessment of the Bradley Fighting Vehicle industrial "
      "base, and the Army's analysis and plans for using the Joint Systems Manufacturing "
      "Center in Lima, Ohio, where the Abrams tank is produced — and went beyond it, "
      "covering Strykers, M109 Paladins, M88 Hercules, M113 Armored Personnel Carriers, the "
      "Ground Combat Vehicle, the Armored Multi-Purpose Vehicle and U.S. Marine Corps combat "
      "vehicles, and identifying potential courses of action such as consolidation of "
      "production at certain facilities."),
     ["ev-gao-15-548"], ["me-ndaa13-bradley", "me-sasc-goco"]),
    ("cl-presentation", (7, 17, 18), "readiness", ["obj-viability"],
     ("Verbatim, printed pp. 7 and 17: the study's \"findings and conclusions were presented "
      "in a clear, comprehensive, and timely manner\". Printed p. 18 records the timeline: a "
      "contract in October 2012, preliminary results to the Army in April 2013, interim "
      "briefings to key congressional committees later in 2013, and a final report to those "
      "committees in April 2014."),
     ["ev-gao-15-548"], []),
]


def _claims_and_episode(g: Graph) -> None:
    put = g.put

    for cid, pages, section, addresses, text, evidence_ids, mandate in CLAIMS:
        fields = {
            "text": text,
            # Every claim in this record is a statement about the combat vehicle industrial
            # base study, so every one carries the charter's question class. Nothing here
            # is reused past the purpose its evidence was built for, and the scope checker
            # says so by staying silent.
            "questionClass": "industrial-base",
            "assessableAt": {"level": "U"},
            "supportedBy": [{"evidence": e} for e in evidence_ids],
            "addresses": addresses,
            "section": section,
        }
        if mandate:
            fields["mandateElements"] = mandate
        put(o(cid, "Claim", loc(*pages), **fields), H)

    put(own("prg-kearney", "DecisionProgram",
            name=("The Army combat vehicle industrial base study — a single-episode "
                  "programme"),
            charter="ch-kearney-2014", episodes=[EPISODE], refreshTriggers=[], diffs=[]), H)

    put(o(EPISODE, "DecisionEpisode", loc(1, 18), program="prg-kearney", sequence=1,
          charter="ch-kearney-2014", lifecycleState="DRAFT", transitions=[],
          objectives=["obj-viability", "obj-alternatives"],
          alternatives=[a[0] for a in ALTERNATIVES],
          groundRules=["gr-three-programs"], constraints=["con-fiscal"],
          assumptions=["as-warm-shutdown", "as-york-costs", "as-min-sustainment-rate",
                       "as-army-risk-perspective", "as-demand-scenarios"],
          evidenceRegister=["ev-gao-15-548", "ev-kearney-final-report",
                            "ev-manufacturer-data", "ev-supplier-survey", "ev-amc-baseline",
                            "ev-benchmark-data", "ev-oem-rates", "ev-army-procurement-plans",
                            "ev-oem-review-2013", "ev-abrams-cost-data"],
          scenarios=["sc-demand-levels"],
          claims=[c[0] for c in CLAIMS],
          risks=[], biasChecks=["bc-oem-review"],
          mandateElements=["me-ndaa13-bradley", "me-sasc-goco"],
          observations=[], weightSets=["ws-kearney"],
          models=["mdl-kearney-financial", "mdl-kearney-method"],
          # Linked at the episode's first revision so G2's `plan-present` check has
          # something to read when the human drives the gate.
          plan="pl-kearney",
          # No evaluation run, and none invented. Five of the six analyses are qualitative
          # and GAO publishes no per-alternative numbers, so there is nothing for the
          # kernel to compute. That is exactly why `objective-run-coverage` blocks, and the
          # README says so.
          runs=[], flipAnalyses=[], narratives=[],
          distribution=[{"to": "the congressional defense committees", "date": "2014-04"},
                        {"to": ("the Army (preliminary results)"), "date": "2013-04"},
                        {"to": ("key congressional committees (interim briefings)"),
                         "date": "2013"}],
          asOf=AS_OF), H)


def build() -> Graph:
    """The whole reconstruction as a human wrote it, before any gate is driven."""
    g = Graph()
    _reliability_steps(g)
    _gaps(g)
    _exclusions(g)
    _evidence(g)
    _policy_and_charter(g)
    _value_model(g)
    _assumptions(g)
    _plan_and_checks(g)
    _claims_and_episode(g)
    return g
