"""Demonstration A — CBO's 2013 Ground Combat Vehicle study as a docket record.

Source: Congressional Budget Office, *The Army's Ground Combat Vehicle Program and
Alternatives* (April 2013), `sources/cbo-2013-04-gcv-program-and-alternatives.pdf`.
Public: a US Government work with no distribution limitation (see the sidecar
`.source.md`). Page numbers in this file are the report's *printed* page numbers; the
PDF page is the printed page plus five, which is what the `#page=` anchors carry.

Three rules held while transcribing:

1. **Every number is CBO's, as printed.** Nothing is recomputed, rounded, interpolated
   or averaged on the way in. The four category scores and the two cost figures come off
   Table 2-2 (p. 21); the weights come off Table A-3 (p. 35). The kernel does the
   arithmetic afterwards and reproduces CBO's published overall figures.
2. **The Army's files are not public and are not invented.** The Milestone A analysis of
   alternatives (March 2011), the combat simulations (February–December 2010), the
   soldier ranking behind the weights and the per-vehicle mobility attributes are all
   recorded as Evidence, but their *contents* are not: what is recorded is what CBO
   reports about them, with a pointer to the CBO page that reports it and a custodian
   line that says the originals are the Army's and are not public. Where CBO reports
   nothing — the simulation model's name, its VV&A record, the survey's size and dates,
   the AoA report itself — the record carries an `InsufficientEvidence` object, not a
   guess.
3. **Nothing in this record is classified.** Every classification is `U`, because every
   source is public. The withholding path is demonstrated in the test suite against a
   throwaway copy of this graph, never by mislabelling a document here.

The record is dated to the source: `createdAt` and the episode's `asOf` are 2013-04-30,
so the elapsed-time predicates (accreditation age, scope validity) read as they would
have when CBO published. The real transcription date lives in
`ingestionProvenance.extractedAt`.
"""

from __future__ import annotations

from docket.store import Graph

H = {"actorType": "human", "actorId": "shreyash"}
NOW = "2013-04-30T00:00:00Z"
AS_OF = "2013-04-30"
SRC = "sources/cbo-2013-04-gcv-program-and-alternatives.pdf"
EXTRACTED = "2026-09-05"


def anchor(printed_page: int) -> str:
    """A pointer into the committed PDF. Printed page + 5 = PDF page."""
    return f"{SRC}#page={printed_page + 5}"


def cited(oid: str, type_name: str, locator: str, *, confidence: str = "explicit", **fields):
    """An object transcribed from the CBO report, carrying where it came from."""
    return {
        "id": oid, "type": type_name, "rev": 1, "createdBy": H, "createdAt": NOW,
        "ingestionProvenance": {"sourceArtifact": SRC, "locator": locator,
                                "extractor": "human", "extractedAt": EXTRACTED},
        "confidence": confidence, **fields,
    }


def own(oid: str, type_name: str, **fields):
    """An object this reconstruction supplies: no ingestion provenance, because it was
    not extracted from anything. The policy, the plan, the evaluation model and its
    VV&A record are ours; saying they came off a CBO page would be a false citation."""
    return {"id": oid, "type": type_name, "rev": 1, "createdBy": H, "createdAt": NOW, **fields}


# ---- CBO Table 2-2 (p. 21) -------------------------------------------------------------
# Improvement in capability relative to the current Bradley IFV, percent, as printed:
# (protection and survivability, lethality, mobility, number of occupants, full squad).
CATEGORY = {
    "alt-gcv": (27, -7, 24, 29, 100),
    "alt-namer": (33, -36, 4, 29, 100),
    "alt-upgraded-bradley": (27, 60, 15, 0, 0),
    "alt-puma": (28, 103, 22, -14, 0),
    "alt-retain-bradley": (0, 0, 0, 0, 0),
}
# Total cost of development and procurement, 2014–2030, billions of 2013 dollars (Table 2-2).
COST = {"alt-gcv": 28.8, "alt-namer": 19.5, "alt-upgraded-bradley": 19.5,
        "alt-puma": 14.5, "alt-retain-bradley": 4.6}
# Programmatic risk, as printed (Table 2-2) — qualitative, and deliberately not scored.
RISK = {"alt-gcv": "High", "alt-namer": "Low", "alt-upgraded-bradley": "Intermediate",
        "alt-puma": "Low", "alt-retain-bradley": "None"}

ALTERNATIVES = {
    "alt-gcv": (
        "Army's plan: field the Ground Combat Vehicle",
        "The notional GCV — the December 2010 Design Concept After Trades: 1,748 vehicles, "
        "50 to 65 tons, 9 passengers and a crew of 3, average procurement unit cost capped "
        "at $13.5 million in 2013 dollars (pp. 2, 7, 8).",
        1),
    "alt-namer": (
        "Option 1: purchase the Israeli Namer armored personnel carrier",
        "1,748 Namer APCs on the GCV's procurement schedule (pp. 2, 20): 68 to 70 tons, "
        "9 passengers. The best protected vehicle CBO examined (p. 24) and the least "
        "lethal — its largest weapon is a 12.7 mm machine gun (p. 25; described as its "
        "primary weapon at p. 23).",
        2),
    "alt-upgraded-bradley": (
        "Option 2: upgrade the Bradley infantry fighting vehicle",
        "1,748 upgraded Bradley IFVs: 35 to 41 tons, 7 passengers. More lethal than the "
        "notional GCV, less mobile, and two passengers short of a full squad (pp. 2, 20).",
        3),
    "alt-puma": (
        "Option 3: purchase the German Puma infantry fighting vehicle",
        "2,048 Pumas — five per platoon rather than four, to keep 28 seats in the platoon: "
        "35 to 47 tons, 6 passengers. The most lethal vehicle CBO examined (pp. 2, 20, 24).",
        4),
    "alt-retain-bradley": (
        "Option 4: retain the current Bradley infantry fighting vehicle",
        "Extend the life of 820 current Bradley IFVs and continue research and development. "
        "No new capability; this is the reference vehicle every improvement is measured "
        "against — the M2A3 version used in Iraq, with reactive and underbelly armor "
        "(pp. 2, 21).",
        5),
}

CONDITIONS = ["unconventional threats", "conventional armored battle",
              "northeast Asia intense battle"]

# (measure id, objective, task, attribute, measure, units, direction, locator)
MEASURES = [
    ("m-prot", "obj-capability", "Protect the occupants and survive attack",
     "protection and survivability",
     "improvement combining the reduction in soldiers lost (two-thirds) and in vehicles "
     "lost (one-third) in the Army's simulations",
     "percent improvement vs the current Bradley IFV", "max", "p. 10 fn 13; p. 34"),
    ("m-leth", "obj-capability", "Destroy enemy forces", "lethality",
     "improvement combining capability against enemy vehicles (60 percent) and against "
     "enemy personnel (40 percent)",
     "percent improvement vs the current Bradley IFV", "max", "p. 10 fn 14; p. 34"),
    ("m-mob", "obj-capability", "Travel on- and off-road", "mobility",
     "six automotive attributes weighted per the Army's scheme: acceleration, average "
     "off-road speed, range on a tank of fuel, turning radius, width, bridge-crossing "
     "capacity",
     "percent improvement vs the current Bradley IFV", "max", "p. 35 (Table A-2)"),
    ("m-pax", "obj-capability", "Carry the squad", "passenger capacity",
     "percentage increase in passengers carried beyond the current Bradley's seven",
     "percent vs the current Bradley IFV", "max", "p. 34"),
    ("m-squad", "obj-capability", "Carry a full nine-member squad",
     "passenger capacity, all or nothing",
     "100 if the vehicle is designed to carry a full nine-member squad, otherwise 0",
     "percent, all or nothing", "max", "p. 34"),
    ("m-cost", "obj-cost", "Afford the fleet", "total cost",
     "development and procurement of the fleet, 2014 through 2030",
     "billions of 2013 dollars", "min", "p. 21 (Table 2-2)"),
]

# (scenario id, name, description, rationale)
SCENARIOS = [
    ("sc-unconventional", "Unconventional threats",
     "U.S. forces confronting unconventional threats and small numbers of combatants; "
     "CBO reports company-sized incidents in Iraq and Afghanistan among the simulated "
     "scenarios (p. 10 fn 12).",
     "Situations similar to recent operations in Iraq and Afghanistan. This is where the "
     "GCV showed its largest relative gain: 60 percent fewer occupants lost (p. 10)."),
    ("sc-conventional", "Conventional armored battle",
     "Larger, more conventional battles against enemies equipped with armored vehicles, "
     "including a battalion-sized encounter in southwest Asia (p. 10 fn 12).",
     "The Army simulated it: a battalion-sized encounter in southwest Asia is among the "
     "scenarios CBO reports (p. 10 fn 12), and it is where the GCV's reduction in "
     "losses was smaller than against unconventional threats (p. 10)."),
    ("sc-ne-asia", "Northeast Asia intense battle",
     "The most intense battle CBO reports the Army simulating: a brigade-sized battle set "
     "in northeast Asia (p. 10 and fn 12).",
     "It bounds the survivability claim: in this scenario the GCVs' survivability was no "
     "greater than the current Bradley IFVs' (p. 10)."),
]


def _evidence(g) -> None:
    """The evidence register: two CBO products, four Army products, one ARCIC document."""
    put = g.put

    put(cited(
        "drs-cbo-army-data", "DataReliabilityStep", "p. 21 (Table 2-2 source line); p. 33 fn 1",
        description=(
            "CBO states the provenance of every capability score in the source line of the "
            "tables that print it: the Army's Report on the Results of the Ground Combat "
            "Vehicle Analysis of Alternatives (Milestone A), March 2011, and Department of "
            "the Army personal communications to CBO staff of May 2012 and December 2012. "
            "CBO went to the AoA report itself, citing Tab B (trade impact analysis, p. 7 "
            "fn 10) and Tab I (affordability strategy, p. 33 fn 1)."),
        method="source-review", performedBy="Congressional Budget Office", date="2012-05",
        documentation="ev-cbo-2013"), H)

    put(cited(
        "drs-cbo-cost-method", "DataReliabilityStep", "pp. 7, 23–24",
        description=(
            "CBO built its own cost estimates rather than adopting the Army's: development "
            "cost projected from the Army's preliminary Milestone A estimates as revised for "
            "the January 2013 programme changes; GCV procurement from the $13.5 million "
            "average procurement unit cost ceiling set by the Undersecretary of Defense for "
            "Acquisition, Technology, and Logistics; the foreign vehicles from their "
            "published unit costs and an assumed adaptation cost."),
        method="source-review", performedBy="Congressional Budget Office", date="2013-04",
        documentation="ev-cbo-cost-estimate"), H)

    put(cited(
        "ev-cbo-2013", "Evidence", "whole report; capability scores at p. 21 (Table 2-2)",
        title=("Congressional Budget Office, The Army's Ground Combat Vehicle Program and "
               "Alternatives (April 2013)"),
        evidenceType="Document", publisher="Congressional Budget Office", published="2013-04",
        date="2013-04",
        pointer={"uri": "https://www.cbo.gov/publication/44044",
                 "custodian": "Congressional Budget Office"},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("Compare the Army's plan for the Ground Combat Vehicle with "
                              "four alternatives on capability, cost and programmatic risk "
                              "over 2014–2030"),
            "questionClass": "requirements-tradeoff",
            "conditions": ["unconventional threats", "conventional armored battle",
                           "northeast Asia intense battle"],
            "intendedUse": "inform the Congress on the Ground Combat Vehicle program"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Philip Webre and Derek Trunkey (CBO)", "role": "internal review",
                    "date": "2013-04"},
                   {"name": "Scot A. Arnold (Institute for Defense Analyses)",
                    "role": "external review", "date": "2013-04"},
                   {"name": ("Gilbert F. Decker, formerly Assistant Secretary of the Army "
                             "for Research, Development, and Acquisition"),
                    "role": "external review", "date": "2013-04"}],
        reliabilitySteps=["drs-cbo-army-data"],
        inclusionReason="the analysis this record reconstructs",
        limitations=[
            {"statement": ("The Army intends to change the requirements for the amount of "
                           "protection and the size of the GCV's cannon; CBO could not "
                           "account for those changes because the details were still "
                           "pending (pp. 1 fn 1, 8)"),
             "impact": ("the GCV's capability scores describe the December 2010 notional "
                        "design, not the vehicle the Army would field")},
            {"statement": ("CBO accepted the Army's goals for the vehicle and for the number "
                           "of vehicles needed; different goals would have changed the "
                           "criteria (p. 5)"),
             "impact": ("the comparison answers the Army's question, not the prior question "
                        "of whether those are the right goals")}]), H)

    put(cited(
        "ev-cbo-cost-estimate", "Evidence", "p. 21 (Table 2-2); p. 23 (Table 2-3); p. 7",
        title=("CBO's cost estimates for the GCV program and the four options, 2014–2030"),
        evidenceType="Document", publisher="Congressional Budget Office", published="2013-04",
        date="2013-04",
        pointer={"uri": anchor(21), "custodian": "Congressional Budget Office"},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("What would developing and procuring each option cost over "
                              "2014–2030, in 2013 dollars?"),
            "questionClass": "cost",
            "intendedUse": "compare the cost of the Army's plan with four alternatives"},
        reviewStatus="reviewed",
        reviewers=[{"name": "David Mosher and Matthew Goldberg (CBO)",
                    "role": "general supervision of the report (p. 37)",
                    "date": "2013-04"},
                   {"name": "Philip Webre and Derek Trunkey (CBO)",
                    "role": "internal review of the report (p. 37)",
                    "date": "2013-04"}],
        reliabilitySteps=["drs-cbo-cost-method"],
        inclusionReason=("the cost side of the comparison; unlike the capability scores, "
                         "these are CBO's own estimates rather than the Army's"),
        limitations=[
            {"statement": ("Procurement costs are difficult to project this early: the GCV "
                           "figure is built from the $13.5 million unit-cost ceiling rather "
                           "than from a validated estimate (p. 7)"),
             "impact": "the GCV's $28.8 billion is a ceiling-driven figure, not an actual"}]), H)

    put(cited(
        "gap-aoa-report", "InsufficientEvidence", "p. 7 fn 10; p. 33 fn 1", confidence="absent",
        sought=("Department of the Army, Headquarters, Report on the Results of the Ground "
                "Combat Vehicle Analysis of Alternatives (Milestone A) to the Armed Services "
                "Committees (March 2011), including Tab B and Tab I"),
        whereLookedFor=["CBO's source lines and footnotes (Tab B at p. 7 fn 10, Tab I at "
                        "p. 33 fn 1)",
                        "public web search, 2026-09-05"],
        whyNotFound=("a report to the congressional defense committees; not published and "
                     "not found in any public repository"),
        confirmedBy={"actorId": "shreyash", "date": "2026-09-05"}, impact="degrading",
        indicatorsThatWouldResolve=[
            "public release of the Milestone A AoA report",
            "public release of Tab I, 'Ground Combat Vehicle Affordability Strategy'"]), H)

    put(cited(
        "ev-army-aoa-2011", "Evidence", "p. 7 fn 10; p. 21 (Table 2-2 source line)",
        title=("Department of the Army, Headquarters, Report on the Results of the Ground "
               "Combat Vehicle Analysis of Alternatives (Milestone A), March 2011"),
        evidenceType="Document", publisher="Department of the Army, Headquarters",
        published="2011-03", date="2011-03",
        pointer={"$gap": "gap-aoa-report"},
        classification={"level": "U",
                        "caveats": ["not publicly released; its release status has not been "
                                    "verified by this project"],
                        "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": "Which vehicle should the Army pursue at Milestone A?",
            "questionClass": "requirements-tradeoff",
            "intendedUse": "the Army's Milestone A decision and its report to the Congress"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Department of the Army, Headquarters",
                    "role": "issuing authority (no review record seen by this project)",
                    "date": "2011-03"}],
        reliabilitySteps=["drs-cbo-army-data"],
        inclusionReason=("the source CBO names for the upgraded Bradley's protection and "
                         "lethality scores and for the Army's category weights"),
        limitations=[
            {"statement": ("The report itself is not public: everything recorded here is "
                           "what CBO reports about it"),
             "impact": ("its scores cannot be checked against the analysis that produced "
                        "them; the pointer is a recorded gap, not a locator")}]), H)

    put(cited(
        "gap-sim-model", "InsufficientEvidence", "pp. 10–11", confidence="absent",
        sought="the name and version of the combat simulation the Army ran in 2010",
        whereLookedFor=["CBO pp. 10–11 and p. 10 fn 12", "CBO appendix, pp. 33–35"],
        whyNotFound=("CBO reports 'a series of computer simulations of combat' and lists the "
                     "scenarios, but never names the model"),
        confirmedBy={"actorId": "shreyash", "date": "2026-09-05"}, impact="degrading",
        indicatorsThatWouldResolve=["the AoA report, or any public Army source, names the "
                                    "model"]), H)

    put(cited(
        "gap-sim-vva", "InsufficientEvidence", "pp. 10–11", confidence="absent",
        sought=("a verification, validation and accreditation record for the Army's 2010 "
                "combat simulations"),
        whereLookedFor=["the CBO report", "public Army sources, 2026-09-05"],
        whyNotFound="no VV&A record for these simulations appears in the public record",
        confirmedBy={"actorId": "shreyash", "date": "2026-09-05"}, impact="degrading",
        indicatorsThatWouldResolve=["an accreditation record released with the AoA"]), H)

    put(cited(
        "ev-army-sim-2010", "Evidence", "pp. 10–11",
        title=("Army combat simulations, February–December 2010: the notional GCV "
               "substituted for the current Bradley IFV"),
        evidenceType="MSStudy", date="2010-12",
        pointer={"uri": anchor(10),
                 "custodian": ("Department of the Army (originals, not public); CBO "
                               "(reported values)")},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("How much better does the notional GCV protect its occupants, "
                              "survive attack and destroy enemy forces than the current "
                              "Bradley IFV?"),
            "questionClass": "combat-effectiveness",
            "conditions": ["unconventional threats", "conventional armored battle",
                           "northeast Asia intense battle"],
            "intendedUse": "the Army's Ground Combat Vehicle analysis of alternatives"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Department of the Army (analysis of alternatives)",
                    "role": "author", "date": "2010-12"}],
        reliabilitySteps=["drs-cbo-army-data"],
        inclusionReason=("the only combat-simulation results for the GCV in the public "
                         "record (pp. 10–11)"),
        limitations=[
            {"statement": ("Technical data were insufficient to simulate the Namer or the "
                           "Puma (p. 20 fn 4)"),
             "impact": ("those two vehicles' protection and lethality rest on Army analysts' "
                        "estimates, not on simulation")},
            {"statement": ("Only the aggregate results are public: CBO reports the averages "
                           "and two scenario extremes, not the runs"),
             "impact": "the 27 percent composite cannot be recomputed from public data"}],
        model={"$gap": "gap-sim-model"},
        scenarios=["sc-unconventional", "sc-conventional", "sc-ne-asia"],
        vvaRecord={"$gap": "gap-sim-vva"}), H)

    put(cited(
        "ev-army-expert-estimates", "Evidence", "p. 20 fn 4; values at p. 21 (Table 2-2)",
        title=("Army analysts' estimates of the Namer's and the Puma's performance relative "
               "to the current Bradley IFV"),
        evidenceType="ExpertAssessment", date="2011-03",
        pointer={"uri": anchor(20),
                 "custodian": ("Department of the Army (originals, not public); CBO "
                               "(reported values)")},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("How would the Namer and the Puma have performed against the "
                              "current Bradley IFV on protection, survivability and "
                              "lethality?"),
            "questionClass": "combat-effectiveness",
            "intendedUse": "the Army's analysis of alternatives, in place of simulation"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Department of the Army (analysis of alternatives)",
                    "role": "author", "date": "2011-03"}],
        reliabilitySteps=["drs-cbo-army-data"],
        inclusionReason=("the Army's stated substitute where technical data were "
                         "insufficient to simulate (p. 20 fn 4)"),
        limitations=[
            {"statement": "These are estimates, not simulation output (p. 20 fn 4)",
             "impact": ("the Namer's and the Puma's protection and lethality carry more "
                        "uncertainty than the GCV's, and CBO publishes no band on either")}],
        experts=["Army analysts (not named in the public record)"],
        method=("estimate of how the vehicle would have performed relative to the current "
                "Bradley IFV")), H)

    put(cited(
        "ev-army-mobility-data", "Evidence", "p. 35 (Table A-2); p. 24 (Table 2-4)",
        title=("Automotive characteristics behind the mobility score: acceleration, average "
               "off-road speed, range on a tank of fuel, turning radius, width and "
               "bridge-crossing capacity"),
        evidenceType="Dataset", date="2012-05",
        pointer={"uri": anchor(35),
                 "custodian": ("Department of the Army (per-vehicle values, personal "
                               "communication to CBO, May 2012; not public); CBO (published "
                               "attribute weights)")},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("How mobile is each of the five vehicles on- and off-road, "
                              "relative to the current Bradley IFV?"),
            "questionClass": "requirements-tradeoff",
            "intendedUse": "CBO's mobility score"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Congressional Budget Office", "role": "compiler",
                    "date": "2013-04"}],
        reliabilitySteps=["drs-cbo-army-data"],
        inclusionReason=("six attributes weighted per the Army's scheme, with long-distance "
                         "transportability excluded (Table A-2, p. 35)"),
        limitations=[
            {"statement": ("Table A-2 publishes the attribute weights but not the "
                           "per-vehicle attribute values behind them"),
             "impact": ("the mobility score is taken as printed and cannot be recomputed "
                        "from public data")},
            {"statement": ("The six CBO weights are transcribed exactly as Table A-2 "
                           "prints them and they sum to 1.01, against the table's own "
                           "printed total of 1.00 — CBO's rounding to two decimals, not "
                           "a transcription error"),
             "impact": ("any recomputation from these weights would be out by up to one "
                        "percent of the mobility score")}],
        custodian="Department of the Army (values); Congressional Budget Office (weights)",
        schemaRef=("Table A-2: acceleration 0.29, average off-road speed 0.24, range 0.18, "
                   "turning radius 0.06, width 0.12, bridge-crossing capacity 0.12")), H)

    put(cited(
        "gap-survey-n", "InsufficientEvidence", "p. 33", confidence="absent",
        sought=("the sample size, unit, dates and instrument of the soldier ranking behind "
                "the Army's AoA category weights"),
        whereLookedFor=["CBO appendix, pp. 33–34", "the AoA's Tab I, which is not public"],
        whyNotFound=("CBO reports only that the weights were based on rankings given by "
                     "soldiers who had been deployed with combat brigades in Iraq, "
                     "Afghanistan, Kosovo, or Bosnia"),
        confirmedBy={"actorId": "shreyash", "date": "2026-09-05"}, impact="informational",
        indicatorsThatWouldResolve=["release of the AoA's Tab I"]), H)

    put(cited(
        "ev-soldier-survey", "Evidence", "pp. 33–34 (Table A-1)",
        title=("Soldier ranking of the characteristics that matter most in a fighting "
               "vehicle — the source of the Army's AoA category weights"),
        evidenceType="SoldierTouchpoint",
        pointer={"uri": anchor(33),
                 "custodian": ("Department of the Army (instrument and responses, not "
                               "public); CBO (reported weights)")},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("Which characteristics of a fighting vehicle matter most to "
                              "soldiers who have deployed with combat brigades?"),
            "questionClass": "desired-characteristics",
            "intendedUse": "set the Army's AoA category weights"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Department of the Army (analysis of alternatives)",
                    "role": "author", "date": "2011-03"}],
        reliabilitySteps=["drs-cbo-army-data"],
        inclusionReason="the basis of CBO's primary-metric weights (pp. 33–34)",
        limitations=[
            {"statement": ("Only the second half of the derivation is public. CBO's four "
                           "weights are the Army's four retained weights renormalised — "
                           "0.20/0.15/0.10/0.05 over their sum of 0.50 gives "
                           "0.40/0.30/0.20/0.10 exactly (Table A-1, p. 34) — but how the "
                           "Army turned soldiers' rankings into those weights is in the "
                           "AoA's Tab I, which is not public"),
             "impact": ("the rankings → Army weights step cannot be checked; the Army "
                        "weights → CBO weights step is an exact division and can be "
                        "checked against Table A-1")}],
        n={"$gap": "gap-survey-n"},
        selectionRule=("soldiers who had been deployed with combat brigades in Iraq, "
                       "Afghanistan, Kosovo, or Bosnia (p. 33)"),
        unit={"$gap": "gap-survey-n"},
        instrument=["ranking of the vehicle's most important characteristics (p. 33)"],
        dates={"$gap": "gap-survey-n"},
        analysisMethod=("rankings converted to category weights in the Army's AoA, Tab I, "
                        "'Ground Combat Vehicle Affordability Strategy' (p. 33 fn 1)")), H)

    put(cited(
        "gap-squad-reliability", "InsufficientEvidence", "p. 6 fn 2 and fn 4",
        confidence="absent",
        sought=("any step taken to check the reliability of the Army's squad paper before "
                "its rationale was relied on"),
        whereLookedFor=["CBO p. 6, Box 1-1 and fn 2/fn 4",
                        "the document itself (CBO's link no longer resolves, 2026-09-05)"],
        whyNotFound=("CBO cites the document for the Army's rationale and describes no check "
                     "on it; the document could not be retrieved to check anything either. "
                     "`drs-cbo-army-data` covers CBO's handling of the Army's capability "
                     "data and does not reach this paper, so it is not claimed here."),
        confirmedBy={"actorId": "shreyash", "date": "2026-09-05"}, impact="informational",
        indicatorsThatWouldResolve=["the paper is retrieved from an Army repository",
                                    "an Army source describes its provenance"]), H)

    put(cited(
        "ev-army-squad-2011", "Evidence", "p. 6, Box 1-1 and fn 2/fn 4",
        title=("Department of the Army, Capabilities Integration Center, The Squad and Its "
               "Ground Combat Vehicle (2011)"),
        evidenceType="Document", publisher="Army Capabilities Integration Center",
        published="2011", date="2011",
        pointer={"uri": "http://go.usa.gov/4fDJ",
                 "custodian": "Army Capabilities Integration Center"},
        classification={"level": "U", "metadataLevel": "U"},
        scopeOfValidity={
            "builtToAnswer": ("Why does the Army want a full nine-member squad in one "
                              "vehicle?"),
            "questionClass": "operational-concept",
            "intendedUse": "the Army's rationale for the nine-member-squad goal"},
        reviewStatus="reviewed",
        reviewers=[{"name": "Army Capabilities Integration Center",
                    "role": "issuing authority", "date": "2011"}],
        reliabilitySteps={"$gap": "gap-squad-reliability"},
        inclusionReason=("the source CBO cites for the Army's squad rationale (Box 1-1, "
                         "p. 6)"),
        limitations=[
            {"statement": ("The document itself was not retrieved: the link CBO gives no "
                           "longer resolves (checked 2026-09-05)"),
             "impact": ("the rationale is read from CBO's summary in Box 1-1, not from the "
                        "source")}]), H)


def _exclusions(g) -> None:
    """Every omission this record makes, typed and attributed. Five are CBO's own; three
    say why a package section is empty."""
    put = g.put

    put(cited(
        "ex-no-thresholds", "Exclusion", "p. 21; p. 33",
        target={"kind": "Measure",
                "label": "threshold and objective values for the five capability measures"},
        reasonType="data-unavailable",
        reason=("CBO compared percentage improvement relative to the current Bradley IFV and "
                "published no threshold or objective value for any category; the Army's "
                "threshold and objective values live in the Milestone A AoA, which is not "
                "public."),
        authority={"who": "Congressional Budget Office", "role": "analyst", "date": "2013-04"},
        retainedInStructure=True), H)

    put(cited(
        "ex-namer-puma-sim", "Exclusion", "p. 20 fn 4",
        target={"kind": "Study",
                "label": "combat simulation of the Namer and the Puma"},
        reasonType="data-unavailable",
        reason=("The technical data were insufficient to simulate the performance of the "
                "Namer or the Puma; instead the Army's analysts estimated how those two "
                "vehicles would have performed relative to the current Bradley IFV. Their "
                "estimates are carried as evidence in their own right, not as simulation."),
        authority={"who": "Department of the Army (analysts)", "role": "analysis of "
                   "alternatives", "date": "2011-03"},
        evidence="ev-army-expert-estimates", retainedInStructure=True), H)

    put(cited(
        "ex-transportability", "Exclusion", "p. 34 fn 3",
        target={"kind": "Measure",
                "label": "long-distance transportability (a seventh mobility attribute)"},
        reasonType="data-unavailable",
        reason=("CBO did not have enough data on the types and numbers of conveyances needed "
                "to move the vehicles long distances by rail, ship or air. The Army's scheme "
                "weights it 0.15; excluding it raised the weights on the other six "
                "attributes (Table A-2)."),
        authority={"who": "Congressional Budget Office", "role": "analyst", "date": "2013-04"},
        retainedInStructure=True), H)

    put(cited(
        "ex-army-categories", "Exclusion", "pp. 33–34 (Table A-1)",
        target={"kind": "Category",
                "label": "cost, communications, growth potential and sustainability "
                         "(four of the Army's eight AoA categories)"},
        reasonType="assessed-differently",
        reason=("The Army's analysis included several categories that CBO assessed "
                "differently — such as cost — or excluded altogether for a variety of "
                "reasons, including an insufficiency of data for analysis of all four "
                "vehicles. CBO's primary-metric weights are the Army's weights for the four "
                "remaining categories, renormalised: the Army weighted protection and "
                "survivability 0.20, lethality 0.15, mobility 0.10 and passenger capacity "
                "0.05, which sum to 0.50, and dividing each by 0.50 gives CBO's "
                "0.40/0.30/0.20/0.10 exactly (Table A-1, p. 34)."),
        authority={"who": "Congressional Budget Office", "role": "analyst", "date": "2013-04"},
        retainedInStructure=True), H)

    put(cited(
        "ex-risk-not-scored", "Exclusion", "p. 21 (Table 2-2)",
        target={"kind": "Measure", "label": "programmatic risk"},
        reasonType="assessed-differently",
        reason=("CBO reported programmatic risk qualitatively — High for the GCV, "
                "Intermediate for the upgraded Bradley, Low for the Namer and the Puma, None "
                "for retaining the current Bradley — and combined it into neither "
                "overall-improvement metric. It is therefore not scored here either; it is "
                "recorded on the alternatives and as a Risk."),
        authority={"who": "Congressional Budget Office", "role": "analyst", "date": "2013-04"},
        retainedInStructure=True), H)

    put(own(
        "ex-vva-na", "Exclusion",
        target={"kind": "Section", "label": "VV&A Issues / Lessons Learned"},
        reasonType="not-applicable",
        reason=("MIL-STD-3022 §5.3 retains every section; there are no outstanding issues "
                "and no lessons learned to record for a reproduction of a published "
                "additive metric."),
        authority={"who": "shreyash", "role": "reconstruction author", "date": "2026-09-05"},
        retainedInStructure=True), H)

    put(cited(
        "ex-no-commitment", "Exclusion", "p. 37 ('About This Document')",
        target={"kind": "Section", "label": "commitment"},
        reasonType="not-applicable",
        reason=("In keeping with CBO's mandate to provide objective and impartial analysis, "
                "the report makes no recommendations, and no decision was taken in it. The "
                "episode therefore stops at PENDING_SIGNATURE: there is nothing to sign."),
        authority={"who": "Congressional Budget Office", "role": "analyst", "date": "2013-04"},
        retainedInStructure=True), H)

    put(cited(
        "ex-no-mandate", "Exclusion", "p. 37 ('About This Document')",
        target={"kind": "Section", "label": "mandate-elements"},
        reasonType="not-applicable",
        reason=("The report was prepared at the request of the former Chairman and Ranking "
                "Member of the Tactical Air and Land Forces Subcommittee of the House "
                "Committee on Armed Services; the request carried no itemised list of things "
                "the report had to contain. The one mandate constraint CBO states — that it "
                "make no recommendations — is recorded as the exclusion on the commitment "
                "section."),
        authority={"who": "Congressional Budget Office", "role": "analyst", "date": "2013-04"},
        retainedInStructure=True), H)

    put(own(
        "ex-no-refresh", "Exclusion",
        target={"kind": "Section", "label": "refresh-log"},
        reasonType="not-applicable",
        reason=("Demonstration A is a point-in-time reconstruction of one published study: "
                "there is no prior episode, no refresh trigger and no diff. Demonstration B "
                "exercises the refresh path."),
        authority={"who": "shreyash", "role": "reconstruction author", "date": "2026-09-05"},
        retainedInStructure=True), H)


def _model_and_charter(g) -> None:
    put = g.put

    put(own(
        "pol-cbo", "Policy", name="point-trade-study", version="0.1",
        decisionClass="trade-study", method="mavt", tailoring="published-21", aggregationK=1,
        requiredBiasChecks=["structured-alternative-comparison"],
        requireAllLinchpinsVaried=True, prohibitedExclusionReasons=["time-or-resource"],
        # `run-inputs-changed` is a warning by default; naming it here promotes it to a
        # blocker, so a record whose numbers no longer match its sealed run cannot be
        # called ready.
        blockingRules=["linchpin-unevidenced", "baseline-present", "silent-omission",
                       "run-inputs-changed"],
        nSimplex=2000), H)

    put(cited(
        "ch-gcv-2013", "Charter", "pp. 1–5, 10–12, 20–21", confidence="inferred",
        question=("How would the Army's planned Ground Combat Vehicle compare with four "
                  "alternatives — the Israeli Namer, an upgraded Bradley, the German Puma, "
                  "and retaining the current Bradley — in capability, cost and programmatic "
                  "risk over 2014 through 2030, measured against the current Bradley IFV?"),
        decisionToBeMade=("Whether to continue the Ground Combat Vehicle program as planned "
                          "or to pursue one of the four alternatives."),
        consequencesOfErroneousOutput=(
            "The Army fields a fleet that is less capable, costlier or riskier than an "
            "available alternative — the GCV program is $28.8 billion over 2014–2030 — or "
            "gives up the nine-member-squad capability it has made one of its highest "
            "priorities."),
        questionClass="requirements-tradeoff",
        scope={"included": [
            "the notional GCV (December 2010 Design Concept After Trades)",
            "four alternatives: Namer, upgraded Bradley, Puma, retain the current Bradley",
            "protection and survivability", "lethality", "mobility", "passenger capacity",
            "total development and procurement cost, 2014–2030",
            "programmatic risk, reported qualitatively"],
            "excluded": [
            "how the choice of contractor would affect the industrial base or employment "
            "(p. 5)",
            "which threats the Army will face and how its armored forces will confront them "
            "(p. 5)",
            "the Army's pending changes to the GCV's protection and cannon requirements "
            "(p. 8)",
            "long-distance transportability (p. 34 fn 3)",
            "communications, growth potential and sustainability (p. 34)"]},
        definitions=[
            {"term": "protection and survivability",
             "text": ("Protection is the vehicle's ability to protect its occupants from the "
                      "effects of attacks; survivability is its ability to withstand attacks "
                      "and still continue to operate. Improvement is determined by the "
                      "reduction in losses of vehicles and personnel (Table 1-2 note a, "
                      "p. 11).")},
            {"term": "lethality",
             "text": ("The vehicle's ability to destroy enemy personnel and vehicles "
                      "(Table 1-2 note b, p. 11).")},
            {"term": "mobility",
             "text": "The ability to travel on- and off-road (Table 1-2 note c, p. 11)."},
            {"term": "passenger capacity",
             "text": ("The number of passengers carried beyond the crew. The primary metric "
                      "scores the percentage increase over the current Bradley's seven; the "
                      "secondary metric scores 100 if the vehicle carries a full nine-member "
                      "squad and 0 if it does not (pp. 11, 34).")},
            {"term": "programmatic risk",
             "text": ("The risk that a program's cost will rise or its schedule will "
                      "lengthen; CBO reads it off how close a vehicle is to production "
                      "(p. 20).")}],
        conditionsOfInterest=["unconventional threats", "conventional armored battle",
                              "northeast Asia intense battle"],
        # Three of these five limitations are resolved by a typed Exclusion rather than by
        # a sentence: the mitigation slot holds the exclusion object itself, so the reason
        # for the omission is one object, printed wherever the omission is mentioned.
        limitations=[
            {"statement": ("The comparison places estimated scores for two vehicles beside "
                           "simulated scores for a third."),
             "mitigation": {"$exclusion": "ex-namer-puma-sim"}},
            {"statement": ("Long-distance transportability is not among the mobility "
                           "attributes, although the Army's scheme weights it 0.15."),
             "mitigation": {"$exclusion": "ex-transportability"}},
            {"statement": ("Four of the Army's eight analysis-of-alternatives categories are "
                           "not in the comparison at all."),
             "mitigation": {"$exclusion": "ex-army-categories"}},
            {"statement": ("The Army intends to change the GCV's protection and cannon "
                           "requirements; the details were still pending."),
             "mitigation": ("CBO analysed the December 2010 notional design and said so "
                            "(p. 8); recorded here as a limitation on the CBO evidence.")},
            {"statement": ("CBO's inputs are published rounded to whole percent, so the "
                           "overall figures can only be reproduced to within a rounding "
                           "point."),
             "mitigation": ("The acceptance criterion in the VV&A record is ±1 point, and "
                            "the reproduction is reported against CBO's printed values.")}],
        authority={"signer": "the Congress (the decision); CBO (the analysis)",
                   "board": ("Tactical Air and Land Forces Subcommittee, House Committee on "
                             "Armed Services (requester)")},
        successCriteria=["greater improvement in capability relative to the current Bradley "
                         "IFV",
                         "lower total cost of development and procurement, 2014–2030",
                         "lower programmatic risk"],
        decisionClassPolicy="pol-cbo", mandateElements=[]), H)

    put(own(
        "vva-cbo-metric", "VVARecord", problemStatement="ch-gcv-2013",
        requirementsAndAcceptabilityCriteria=(
            "Reproduce both of CBO's published overall-improvement figures (Table 2-2, "
            "p. 21) from CBO's published category scores and published weights (Table A-3, "
            "p. 35), to within the one point CBO's own rounding to whole percent allows, and "
            "reproduce both published rankings exactly."),
        assumptionsCapabilitiesLimitationsRisks={
            "assumptions": [
                "value is additive across the four categories, as CBO's construction is",
                "the category scores are commensurable percentages on a common reference"],
            "capabilities": ["weighted additive aggregation over the four categories",
                             "one-at-a-time flip analysis and weight-simplex robustness"],
            "limitations": ["no interaction terms between categories",
                            "CBO's inputs are published rounded to whole percent"],
            "risks": ["a reproduction within a rounding point could mask a different "
                      "construction that happens to agree at this precision"]},
        methodology=("Additive multi-attribute value aggregation over the four categories "
                     "(docket kernel, method mavt), with the weights of Table A-3 and no "
                     "value-function transformation: the raw percentage improvement is the "
                     "value."),
        accreditationDecision={
            "authority": ("Congressional Budget Office (published methodology, appendix "
                          "pp. 33–35); reproduction checked against Table 2-2 by this "
                          "reconstruction"),
            "date": "2013-04",
            "scope": ("comparison of the notional GCV and four alternatives on four "
                      "categories of capability, relative to the current Bradley IFV, on "
                      "CBO's own published inputs"),
            "basis": "document", "document": "ev-cbo-2013"},
        sections=[
            {"name": "Problem Statement", "content": "See the charter, ch-gcv-2013."},
            {"name": "M&S Requirements and Acceptability Criteria",
             "content": ("Reproduce CBO's Table 2-2 overall-improvement figures to within "
                         "one point and both rankings exactly.")},
            {"name": "M&S Assumptions, Capabilities, Limitations & Risks/Impacts",
             "content": "As listed in the structured field of this record."},
            {"name": "Accreditation Methodology",
             "content": ("Comparison of the kernel's output against CBO's published values, "
                         "asserted in the demonstration's test suite.")},
            {"name": "Issues", "content": {"$exclusion": "ex-vva-na"}},
            {"name": "Key Participants",
             "content": ("CBO (methodology, appendix pp. 33–35); the docket kernel "
                         "(computation); shreyash (reconstruction).")},
            {"name": "Resources", "content": "The public CBO report, and nothing else."},
            {"name": "Lessons Learned", "content": {"$exclusion": "ex-vva-na"}}]), H)

    put(own(
        "mdl-cbo-metric", "Model",
        name="CBO's overall-improvement metric (additive, four weighted categories)",
        definition={"kind": "code", "version": "0.1.0"},
        intendedUse=("Combine four category improvement scores into one overall improvement "
                     "relative to the current Bradley IFV."),
        questionClass="requirements-tradeoff", vvaRecord="vva-cbo-metric",
        qualificationStatus="validated",
        inputs=["m-prot", "m-leth", "m-mob", "m-pax", "m-squad"],
        limitations=[
            {"statement": "Additive: no interaction between the categories.",
             "justification": ("It matches CBO's published construction, which combines the "
                               "categories by a weighting scheme and nothing else "
                               "(pp. 33–34).")},
            {"statement": "The value function is the identity on CBO's percentage scale.",
             "justification": ("CBO combines the percentages directly; introducing a "
                               "normalisation would change the published numbers.")}]), H)


def _episode(g, observation_ids: list[str]) -> None:
    put = g.put

    put(cited(
        "bc-structured", "BiasCheck", "pp. 20–31 (Chapter 2); p. 21 (Table 2-2)",
        checkType="structured-alternative-comparison", requiredBy="pol-cbo",
        performedBy="Congressional Budget Office", performedAt="2013-04",
        producedEvidence="ev-cbo-2013", status="performed"), H)

    put(cited(
        "rk-gcv-programmatic", "Risk", "p. 20",
        statement=("The GCV program carries high programmatic risk: the vehicle is in the "
                   "early stages of development and several years from production, while "
                   "the Namer and the Puma are already in production."),
        kind="schedule",
        consequence=("Cost growth and schedule delay relative to options that are already "
                     "in production; CBO rates the GCV High and both foreign vehicles Low."),
        owner="Department of the Army (GCV program)", status="open",
        monitor=("Programmatic risk is re-read at each milestone; CBO reports it "
                 "qualitatively and does not score it (see ex-risk-not-scored)."),
        evidence=["ev-cbo-2013", "ex-risk-not-scored"]), H)

    put(own(
        "prg-gcv-2013", "DecisionProgram",
        name="Bradley replacement — the CBO 2013 point study",
        charter="ch-gcv-2013", episodes=["ep-cbo-2013"], refreshTriggers=[], diffs=[]), H)

    put(own(
        "ep-cbo-2013", "DecisionEpisode", program="prg-gcv-2013", sequence=1,
        charter="ch-gcv-2013", lifecycleState="DRAFT", transitions=[],
        objectives=["obj-capability", "obj-cost"], alternatives=list(ALTERNATIVES),
        groundRules=["gr-reference", "gr-dollars", "gr-army-goals"],
        constraints=["con-unit-cost", "con-platoon"],
        assumptions=["as-nine-squad", "as-army-weights", "as-expert-estimates"],
        evidenceRegister=["ev-cbo-2013", "ev-cbo-cost-estimate", "ev-army-aoa-2011",
                          "ev-army-sim-2010", "ev-army-expert-estimates",
                          "ev-army-mobility-data", "ev-soldier-survey", "ev-army-squad-2011"],
        scenarios=["sc-unconventional", "sc-conventional", "sc-ne-asia"],
        claims=[], risks=["rk-gcv-programmatic"], biasChecks=["bc-structured"],
        mandateElements=[], observations=observation_ids,
        weightSets=["ws-primary", "ws-secondary"], models=["mdl-cbo-metric"],
        # The plan is linked here, at the episode's first revision, so that G2's
        # `plan-present` check has something to read when the human drives the gate.
        plan="pl-cbo", runs=[], flipAnalyses=[], narratives=[],
        distribution=[{"to": ("Tactical Air and Land Forces Subcommittee, House Committee "
                              "on Armed Services"), "date": "2013-04"},
                      {"to": "the public (cbo.gov)", "date": "2013-04"}],
        asOf=AS_OF), H)

    step_authority = {
        "document": ("CBO, The Army's Ground Combat Vehicle Program and Alternatives "
                     "(April 2013)"),
        "paragraph": "Appendix, 'Overall Improvement' (pp. 33–34) and Table A-3 (p. 35)",
    }
    put(own(
        "pl-cbo", "Plan", episode="ep-cbo-2013", policyBasis="pol-cbo",
        steps=[
            {"id": "primary", "evaluator": "mdl-cbo-metric", "method": "mavt",
             "alternatives": list(ALTERNATIVES),
             "measures": ["m-prot", "m-leth", "m-mob", "m-pax"], "weightSet": "ws-primary",
             "sensitivitySweeps": [], "biasChecks": ["bc-structured"],
             "authority": step_authority},
            {"id": "secondary", "evaluator": "mdl-cbo-metric", "method": "mavt",
             "alternatives": list(ALTERNATIVES),
             "measures": ["m-prot", "m-leth", "m-mob", "m-squad"], "weightSet": "ws-secondary",
             "sensitivitySweeps": [], "biasChecks": ["bc-structured"],
             "authority": step_authority}],
        deviations=[],
        approvedBy={"actorId": "shreyash", "date": "2026-09-05"}), H)


def build() -> Graph:
    """The whole record as a human wrote it, before anything is computed."""
    g = Graph()
    put = g.put

    _evidence(g)
    _exclusions(g)
    _model_and_charter(g)

    for sid, name, description, rationale in SCENARIOS:
        put(cited(sid, "Scenario", "p. 10 and fn 12", name=name, description=description,
                  rationale=rationale,
                  conditions=[{"sc-unconventional": "unconventional threats",
                               "sc-conventional": "conventional armored battle",
                               "sc-ne-asia": "northeast Asia intense battle"}[sid]],
                  source="ev-army-sim-2010"), H)

    put(cited("obj-capability", "Objective", "pp. 1, 10–11",
              name="Improve combat vehicle capability relative to the current Bradley IFV",
              description=("The four categories CBO scored: protection and survivability, "
                           "lethality, mobility, passenger capacity."),
              priority="primary", priorityRank=1,
              measures=["m-prot", "m-leth", "m-mob", "m-pax", "m-squad"],
              provenance="ev-cbo-2013"), H)
    put(cited("obj-cost", "Objective", "pp. 3, 21",
              name="Keep down the total cost of development and procurement, 2014–2030",
              description="Billions of 2013 dollars, over the whole fleet.",
              priority="secondary", priorityRank=2, measures=["m-cost"],
              provenance="ev-cbo-cost-estimate"), H)

    for mid, obj_id, task, attribute, measure, units, direction, locator in MEASURES:
        # Only the capability measures are scored per condition; cost is a fleet total.
        extra = {"conditions": CONDITIONS} if obj_id == "obj-capability" else {}
        put(cited(mid, "Measure", locator, objective=obj_id, task=task, attribute=attribute,
                  measure=measure, metric={"units": units, "direction": direction},
                  criteria={"$exclusion": "ex-no-thresholds"},
                  valueFunction={"kind": "identity"}, **extra), H)

    for aid, (name, description, order) in ALTERNATIVES.items():
        put(cited(aid, "Alternative", "p. 2 (Summary Table 1); pp. 20–31",
                  name=name, description=f"{description} Programmatic risk: {RISK[aid]}.",
                  status="evaluated", baselineFlag=(aid == "alt-retain-bradley"),
                  enteredOrder=order), H)

    observation_ids = []
    for aid, (prot, leth, mob, pax, squad) in CATEGORY.items():
        capability_evidence = {
            "alt-gcv": "ev-army-sim-2010",
            "alt-namer": "ev-army-expert-estimates",
            "alt-puma": "ev-army-expert-estimates",
            "alt-upgraded-bradley": "ev-army-aoa-2011",
            # The reference vehicle scores zero by construction, not by measurement.
            "alt-retain-bradley": "ev-cbo-2013",
        }[aid]
        rows = [("m-prot", prot, capability_evidence), ("m-leth", leth, capability_evidence),
                ("m-mob", mob, "ev-army-mobility-data"), ("m-pax", pax, "ev-cbo-2013"),
                ("m-squad", squad, "ev-cbo-2013"),
                ("m-cost", COST[aid], "ev-cbo-cost-estimate")]
        for mid, value, ev in rows:
            oid = f"ob-{aid.removeprefix('alt-')}-{mid.removeprefix('m-')}"
            put(cited(oid, "Observation", "p. 21 (Table 2-2)", alternative=aid, measure=mid,
                      value=value, evidence=ev), H)
            observation_ids.append(oid)

    put(cited("ws-primary", "WeightSet", "p. 35 (Table A-3)",
              name=("CBO's primary metric — the Army's weights for the four retained "
                    "categories, renormalised"),
              method="derived",
              weights={"m-prot": 0.40, "m-leth": 0.30, "m-mob": 0.20, "m-pax": 0.10},
              provenance="ev-soldier-survey"), H)
    put(cited("ws-secondary", "WeightSet", "p. 35 (Table A-3)",
              name="CBO's secondary metric — equal weights, full squad scored all or nothing",
              method="equal",
              weights={"m-prot": 0.25, "m-leth": 0.25, "m-mob": 0.25, "m-squad": 0.25},
              provenance="ev-cbo-2013"), H)

    put(cited("gr-reference", "GroundRule", "p. 11; p. 21 (Table 2-2 note b)",
              statement=("Every improvement is measured relative to the current Bradley IFV "
                         "— the M2A3 version used in Iraq, with reactive and underbelly "
                         "armor."),
              source="ev-cbo-2013"), H)
    put(cited("gr-dollars", "GroundRule", "p. 21 (Table 2-2)",
              statement=("Costs are total development and procurement over 2014 through "
                         "2030, in 2013 dollars."),
              source="ev-cbo-cost-estimate"), H)
    put(cited("gr-army-goals", "GroundRule", "p. 5",
              statement=("CBO accepted the Army's goals for the vehicle and the Army's "
                         "estimate of how many vehicles are needed; different goals would "
                         "have changed the criteria."),
              source="ev-cbo-2013"), H)

    put(cited("con-unit-cost", "Constraint", "pp. 7, 8, 12",
              statement=("The GCV's average procurement unit cost may not exceed $13.5 "
                         "million in 2013 dollars ($13.0 million in 2011 dollars), set by "
                         "the Undersecretary of Defense for Acquisition, Technology, and "
                         "Logistics in August 2011."),
              kind="programmatic", source="ev-cbo-2013",
              implications=("To stay under the cap the Design Concept After Trades gave up "
                            "an antitank missile launcher, gave up armor kits for two-thirds "
                            "of the planned vehicles, and kept a 25 mm cannon. That is why "
                            "the notional GCV scores -7 on lethality — less lethal than the "
                            "vehicle it replaces.")), H)
    put(cited("con-platoon", "Constraint", "p. 20",
              statement=("Each mechanized infantry platoon must be able to carry at least 28 "
                         "passengers."),
              kind="policy", source="ev-cbo-2013",
              implications=("The Puma carries six, so Option 3 fields five vehicles per "
                            "platoon instead of four — 2,048 vehicles rather than 1,748 — "
                            "which is why its fleet cost is $14.5 billion and not less.")), H)

    put(cited(
        "as-nine-squad", "Assumption", "p. 6 (Box 1-1); p. 34",
        statement=("Carrying a full nine-member squad in one vehicle materially improves the "
                   "squad's effectiveness on dismount, and enough so that the secondary "
                   "metric is right to score it all-or-nothing: 100 for a vehicle that "
                   "carries nine, 0 for one that does not."),
        linchpin=True,
        rationale=("The Army's stated reason is that a squad split between vehicles is hard "
                   "to organise and direct immediately after the soldiers exit, especially "
                   "under fire or in a city (Box 1-1, p. 6)."),
        evidence="ev-army-squad-2011",
        implicationsIfWrong=("The secondary metric overstates the GCV and the Namer. The "
                             "primary metric's ranking — Puma, then upgraded Bradley, both "
                             "ahead of the GCV — would govern, and the GCV's case would rest "
                             "on protection alone."),
        indicatorsThatWouldAlter=[
            "the Army adopts a squad size other than nine",
            "evidence that a split-squad dismount does not reduce effectiveness",
            "a change in the Army's platoon structure or in the 28-seat platoon rule"],
        variedInSensitivity=True,
        parameterBinding={"kind": "weight", "target": "ws-secondary:m-squad"}), H)

    put(cited(
        "as-army-weights", "Assumption", "pp. 33–34 (Table A-1)",
        statement=("CBO's primary-metric weights — 0.40 protection and survivability, 0.30 "
                   "lethality, 0.20 mobility, 0.10 passenger capacity — represent deployed "
                   "soldiers' preferences well enough to rank the vehicles."),
        linchpin=False,
        rationale=("They are the weights the Army derived from rankings given by soldiers "
                   "who had deployed with combat brigades (p. 33), restricted to the four "
                   "categories CBO could assess and renormalised to sum to one "
                   "(Table A-1, p. 34)."),
        evidence="ev-soldier-survey",
        implicationsIfWrong=("The primary ranking could change. CBO's own secondary metric "
                             "is the published alternative weighting, and it comes within "
                             "0.0165 of weight of reversing the top choice — so the answer "
                             "is more sensitive to this weighting than the two published "
                             "rankings, which agree on the Puma, make it look."),
        indicatorsThatWouldAlter=["a new soldier survey",
                                  "an Army revision of the AoA weighting scheme"],
        variedInSensitivity=True,
        parameterBinding={"kind": "weight", "target": "ws-primary:m-prot"}), H)

    put(cited(
        "as-expert-estimates", "Assumption", "p. 20 fn 4",
        statement=("Army analysts' estimates for the Namer and the Puma are comparable with "
                   "simulation results for the GCV and can be placed in the same table."),
        linchpin=False,
        rationale=("The technical data were insufficient to simulate those two vehicles, so "
                   "the Army's analysts estimated how they would have performed relative to "
                   "the current Bradley IFV (p. 20 fn 4)."),
        evidence="ev-army-expert-estimates",
        implicationsIfWrong=("The Puma's 103 on lethality and the Namer's 33 on protection "
                             "carry more uncertainty than the GCV's simulated scores, and "
                             "the Puma leads on both metrics largely on that 103."),
        indicatorsThatWouldAlter=["simulation data for the Namer or the Puma",
                                  "a published band on either estimate"],
        variedInSensitivity=False), H)

    _episode(g, observation_ids)
    return g
