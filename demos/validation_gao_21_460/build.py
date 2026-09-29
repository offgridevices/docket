"""Validation demonstration — the Army's 2021 MDO TWV Study, as GAO-21-460 describes it.

Source: U.S. Government Accountability Office, *Tactical Wheeled Vehicles*, GAO-21-460
(2021), `sources/gao-21-460-tactical-wheeled-vehicles-accessible.pdf`. Public: a US
Government work with no distribution limitation. Page numbers in this file are the
report's *printed* page numbers; the PDF page is the printed page plus five, and every
object's `ingestionProvenance.locator` carries both.

The record was built blind, from one file: `study_description.txt`, an extract of the
report's printed pp. 6, 9, 11–14 and 35–36 — the pages that describe the Army's study.
The report's own assessment of that study was not read while this fixture was written, so
nothing here is fitted to the per-question labels it will be scored against. That is the
whole point of the exercise, and it is the reason the transcription rules below are
strict rather than convenient.

Four rules held while transcribing:

1. **Quoted text is the report's, character for character.** The three lines of effort
   (p. 11), the two definitions (p. 6), the readiness assumption (p. 12), the model's
   intended use (p. 13), the schedule slip and the brigade-level mitigation (p. 14), the
   scope sentence (p. 12) and GAO's two-analyst procedure (p. 36) are copied, not
   summarised. Where a value is glossed rather than quoted, the gloss carries its printed
   page.
2. **Anything the description does not say is an `InsufficientEvidence` object, never a
   plausible sentence.** Ten of them: the G-8 tasking memo and the FCC OPORD (neither
   published), the study's own data files, slides and model documentation, the dataset
   schemas, the evaluation thresholds, the consequences of and the indicators against the
   90 percent readiness assumption, the two accreditation records, and the weighting
   across the three lines of effort. Each names where it was looked for and what would
   resolve it, and each is confirmed by a human.
3. **Some required fields have no answer in the description, and the schema will not take
   a gap marker for them.** They are filled with the most conservative reading available
   and flagged in a comment at the point of use: `Policy.method` (the enum has no value
   for a capabilities-based assessment), `Model.definition.version` (not a slot),
   `Measure.metric.direction` for the launch-and-support count, `Evidence.classification`
   for the unpublished Army documents, the Charter's consequences-of-error sentence (a
   reconstruction, and labelled one), and the equal weighting across the three lines of
   effort — which is ours, not the Army's, and says so in its name.
4. **The study had not reported.** GAO's audit closed before the final report issued
   (p. 14), so this record carries no Claims, no Observations, no runs and no commitment.
   The episode is a DRAFT with a plan and nothing computed.

The record is dated to the study, not to the report: `createdAt` and the episode's `asOf`
are 2021-05-01, mid-execution, which is the state the description actually describes. The
real transcription date lives in `ingestionProvenance.extractedAt`.
"""

from __future__ import annotations

from docket.store import Graph

H = {"actorType": "human", "actorId": "shreyash"}
NOW = "2021-05-01T00:00:00Z"
AS_OF = "2021-05-01"
SRC = "sources/gao-21-460-tactical-wheeled-vehicles-accessible.pdf"
EXTRACTED = "2026-09-05T00:00:00Z"

# Every gap in this record was confirmed by a human, on the day it was transcribed.
CONFIRMED = {"actorId": "shreyash", "date": "2026-09-05"}
MDO = "European MDO environment"

# The study's authors' own documents are not public. Their classification is not stated
# anywhere in the description and the schema requires one, so they carry U with the
# caveat that says exactly that — the alternative is to assert a level nobody published.
UNRELEASED = {
    "level": "U",
    "caveats": ["not publicly released; its release status has not been verified by "
                "this project"],
    "metadataLevel": "U",
}
PUBLIC = {"level": "U", "metadataLevel": "U"}


def o(oid: str, t: str, page: int, **fields) -> dict:
    """An object transcribed from GAO-21-460, carrying the printed page it came from."""
    return {
        "id": oid, "type": t, "rev": 1, "createdBy": H, "createdAt": NOW,
        "ingestionProvenance": {
            "sourceArtifact": SRC,
            "locator": f"printed p. {page} (PDF p. {page + 5})",
            "extractor": "human", "extractedAt": EXTRACTED},
        "confidence": "explicit", **fields,
    }


def _gaps(put) -> None:
    """Every question the description does not answer, typed and confirmed.

    `whereLookedFor`, `whyNotFound` and `indicatorsThatWouldResolve` are required by the
    schema, so recording a gap costs more work than inventing a value would. That is the
    design: it is the only thing standing between an honest record and a fluent one.
    """
    put(o("gap-g8-memo", "InsufficientEvidence", 35,
          sought=("Army Deputy Chief of Staff G-8 memorandum, Tactical Wheeled Vehicle "
                  "Study, 30 April 2020"),
          whereLookedFor=["GAO-21-460 printed pp. 35-36", "public web search 2026-09-05"],
          whyNotFound="an internal Army tasking memorandum; not published",
          impact="degrading",
          indicatorsThatWouldResolve=["release of the G-8 tasking memorandum"],
          confirmedBy=CONFIRMED))

    put(o("gap-fcc-oporder", "InsufficientEvidence", 36,
          sought=("Army Futures Command, Futures and Concepts Center, FCC OPORD 19-014: "
                  "Multi-Domain Operations Tactical Wheeled Vehicle Study, and its date"),
          whereLookedFor=["GAO-21-460 printed p. 36", "public web search 2026-09-05"],
          whyNotFound=("an internal Army operation order; not published, and the "
                       "description gives no date"),
          impact="degrading",
          indicatorsThatWouldResolve=["release of FCC OPORD 19-014"],
          confirmedBy=CONFIRMED))

    put(o("gap-study-artefacts", "InsufficientEvidence", 14,
          sought="the study's own data files, slides and model documentation",
          whereLookedFor=["GAO-21-460 printed pp. 11-14, 35-36"],
          whyNotFound="the study's final report was not available during GAO's audit",
          impact="degrading",
          indicatorsThatWouldResolve=[
              "issue of the 2021 MDO TWV Study final report",
              "release of the study's data files, slides or model documentation"],
          confirmedBy=CONFIRMED))

    put(o("gap-data-schema", "InsufficientEvidence", 13,
          sought="the schema or field list of the study's datasets",
          whereLookedFor=["GAO-21-460 printed p. 13"],
          whyNotFound=("the description names the datasets and who validated them, and "
                       "says nothing about what fields they hold"),
          impact="informational",
          indicatorsThatWouldResolve=["release of the study's datasets or their field lists"],
          confirmedBy=CONFIRMED))

    put(o("gap-thresholds", "InsufficientEvidence", 11,
          sought=("the threshold and objective values the study scored each line of effort "
                  "against"),
          whereLookedFor=["GAO-21-460 printed pp. 11-14"],
          whyNotFound=("the description gives one example threshold (an airborne unit is "
                       "required to be 100 percent mobile) and no criteria for the other "
                       "lines of effort"),
          impact="degrading",
          indicatorsThatWouldResolve=[
              "release of the study's evaluation criteria for the three lines of effort"],
          confirmedBy=CONFIRMED))

    put(o("gap-readiness-implications", "InsufficientEvidence", 12,
          sought="what would follow if the 90 percent operational readiness rate did not hold",
          whereLookedFor=["GAO-21-460 printed p. 12"],
          whyNotFound=("the description reports the assumption and its sensitivity "
                       "treatment, not the consequences of it being wrong"),
          impact="degrading",
          indicatorsThatWouldResolve=[
              "the study's final report states what follows if the rate does not hold",
              "release of the sensitivity analysis the Army performed on readiness rates"],
          confirmedBy=CONFIRMED))

    put(o("gap-readiness-indicators", "InsufficientEvidence", 12,
          sought="indicators that would alter the 90 percent readiness assumption",
          whereLookedFor=["GAO-21-460 printed p. 12"],
          whyNotFound=("the description reports that readiness rates were varied, and names "
                       "no condition under which the assumed rate would be revised"),
          impact="informational",
          indicatorsThatWouldResolve=[
              "an Army source naming the conditions that would revise the assumed rate"],
          confirmedBy=CONFIRMED))

    put(o("gap-vva-lbc", "InsufficientEvidence", 14,
          sought=("the MIL-STD-3022 accreditation package for the Logistics Battle Command "
                  "model"),
          whereLookedFor=["GAO-21-460 printed pp. 13-14"],
          whyNotFound=("we were not able to examine the consistency and verifiability of "
                       "data measurement as well as the description and documentation of "
                       "the models used for the study"),
          impact="degrading",
          indicatorsThatWouldResolve=[
              "release of an accreditation package for the Logistics Battle Command model"],
          confirmedBy=CONFIRMED))

    put(o("gap-vva-cba", "InsufficientEvidence", 12,
          sought="an accreditation decision for the capabilities based assessment",
          whereLookedFor=["GAO-21-460 printed pp. 12-13"],
          whyNotFound="the description names the method but records no accreditation of it",
          impact="degrading",
          indicatorsThatWouldResolve=[
              "release of an accreditation decision for the capabilities based assessment"],
          confirmedBy=CONFIRMED))

    put(o("gap-weights", "InsufficientEvidence", 11,
          sought="the relative weighting the study applied across the three lines of effort",
          whereLookedFor=["GAO-21-460 printed pp. 11-14"],
          whyNotFound=("the description does not state that the lines of effort were "
                       "weighted or combined"),
          impact="informational",
          indicatorsThatWouldResolve=[
              "the study's final report states how the three lines of effort were combined"],
          confirmedBy=CONFIRMED))


def _reliability(put) -> None:
    """The five data-reliability steps the description reports.

    `documentation` is required and is the same for all five: GAO-21-460 is where each
    step is reported. The steps' own records are the study's, and are not public.
    """
    put(o("drs-gao-two-analysts", "DataReliabilityStep", 36,
          description=("two GAO analysts used a data collection tool to independently "
                       "evaluated the Army study against the generally accepted research "
                       "standards … The two analysts then completed their independent "
                       "analyses, and the GAO team compared the two sets of observations, "
                       "discussed, and reconciled any differences."),
          method="expert-review", performedBy="GAO", date="2021",
          documentation="ev-gao-21-460"))

    put(o("drs-foe-validation", "DataReliabilityStep", 13,
          description=("the study used the expertise of the Future Operational Environment "
                       "Directorate within the Futures and Concepts Center to validate two "
                       "elements of the evaluation criteria for the Mobility line of effort: "
                       "Priority of Targeting and Signature Detection."),
          method="expert-review",
          performedBy=("Future Operational Environment Directorate, Futures and Concepts "
                       "Center"),
          documentation="ev-gao-21-460"))

    put(o("drs-sme-mobility", "DataReliabilityStep", 13,
          description=("subject matter experts reviewed the mobility percentages for each "
                       "unit to determine their reliability."),
          method="expert-review", performedBy="subject matter experts",
          documentation="ev-gao-21-460"))

    put(o("drs-pm-validation", "DataReliabilityStep", 13,
          description=("The Army then provided information on the identified solutions to "
                       "program managers to validate how many vehicles were required to meet "
                       "these expected gaps."),
          method="expert-review", performedBy="program managers",
          documentation="ev-gao-21-460"))

    put(o("drs-cdid-workshops", "DataReliabilityStep", 13,
          description=("subject matter experts from the Capabilities Developments "
                       "Integration Directorates reviewed and validated data for the "
                       "Distribution and Transportation line of effort at workshops "
                       "conducted prior to modeling."),
          method="expert-review",
          performedBy=("subject matter experts from the Capabilities Developments "
                       "Integration Directorates"),
          documentation="ev-gao-21-460"))


def _evidence(put) -> None:
    """Seven evidence items: the GAO report, the two documents that set the study up, what
    Army officials told GAO, two datasets and the one modelling study."""
    put(o("ev-gao-21-460", "Evidence", 35,
          title="U.S. Government Accountability Office, Tactical Wheeled Vehicles, GAO-21-460",
          evidenceType="Document",
          publisher="U.S. Government Accountability Office", published="2021-07-15",
          # The cover gives only "July 2021"; the exact day is from the report's landing
          # page, recorded in the committed sidecar, not from printed p. 35.
          date="2021-07-15",
          pointer={"uri": "https://www.gao.gov/products/gao-21-460",
                   "custodian": "U.S. Government Accountability Office"},
          classification=PUBLIC,
          scopeOfValidity={
              "builtToAnswer": ("the Army's progress in identifying specific capabilities "
                                "and requirements for its 2022 TWV Strategy"),
              "questionClass": "other",
              "intendedUse": "report to congressional committees"},
          reviewStatus="reviewed",
          reliabilitySteps=["drs-gao-two-analysts"],
          inclusionReason="the only public description of the study"))

    put(o("ev-g8-memo-2020-04-30", "Evidence", 35,
          # The memo is named on printed p. 35; the title and the 30 April 2020 date are
          # from footnote 3 on printed p. 36.
          title=("Department of the Army, Deputy Chief of Staff, G-8, Memorandum, Tactical "
                 "Wheeled Vehicle Study (Apr. 30, 2020)"),
          evidenceType="Document",
          publisher="Department of the Army, Deputy Chief of Staff, G-8",
          published="2020-04-30", date="2020-04-30",
          pointer={"$gap": "gap-g8-memo"},
          classification=UNRELEASED,
          scopeOfValidity={
              "builtToAnswer": "the objective of the 2021 MDO TWV Study",
              "questionClass": "capability-gap",
              "intendedUse": "tasking"},
          reviewStatus="reviewed",
          reliabilitySteps=["drs-gao-two-analysts"],
          inclusionReason="the document the study's authors said set the study objective"))

    put(o("ev-fcc-oporder-19-014", "Evidence", 36,
          title=("Army Futures Command, Futures and Concepts Center, FCC OPORD 19-014: "
                 "Multi-Domain Operations Tactical Wheeled Vehicle Study"),
          evidenceType="Document",
          publisher="Army Futures Command, Futures and Concepts Center",
          published={"$gap": "gap-fcc-oporder"},
          pointer={"$gap": "gap-fcc-oporder"},
          classification=UNRELEASED,
          scopeOfValidity={
              "builtToAnswer": "the objective of the 2021 MDO TWV Study",
              "questionClass": "capability-gap",
              "intendedUse": "tasking"},
          reviewStatus="reviewed",
          reliabilitySteps=["drs-gao-two-analysts"],
          inclusionReason=("the second document the study's authors said guided the conduct "
                           "of the study")))

    put(o("ev-army-officials-2021", "Evidence", 12,
          title=("Statements Army officials made to GAO about how the 2021 MDO TWV Study was "
                 "conducted (printed pp. 12, 13, 14)"),
          evidenceType="ExpertAssessment",
          experts=["Futures and Concepts Center officials", "Army modeling officials",
                   "MDO TWV Study officials"],
          method="statements to GAO in interview",
          pointer={"uri": "https://www.gao.gov/products/gao-21-460",
                   "custodian": "U.S. Government Accountability Office"},
          classification=PUBLIC,
          scopeOfValidity={
              "builtToAnswer": "how the study was conducted",
              "questionClass": "capability-gap",
              "intendedUse": "GAO's assessment"},
          reviewStatus="reviewed",
          reliabilitySteps=["drs-gao-two-analysts"],
          inclusionReason=("the stressor force, the readiness assumption, the model's "
                           "validation and the schedule slip are all reported as statements "
                           "of Army officials, not as documents")))

    put(o("ev-mobility-data", "Evidence", 13,
          title="The mobility percentages for each unit, Mobility line of effort",
          evidenceType="Dataset",
          custodian="Army Futures Command, Futures and Concepts Center",
          schemaRef={"$gap": "gap-data-schema"},
          pointer={"$gap": "gap-study-artefacts"},
          classification=UNRELEASED,
          scopeOfValidity={
              "builtToAnswer": "the mobility of each unit type",
              "questionClass": "capability-gap",
              "conditions": [MDO],
              "intendedUse": "the Mobility line of effort"},
          reviewStatus="reviewed",
          reliabilitySteps=["drs-foe-validation", "drs-sme-mobility"],
          inclusionReason=("the data behind the Mobility line of effort; the description "
                           "reports its two validation steps and none of its contents")))

    put(o("ev-lsp-data", "Evidence", 13,
          title=("Force design update data and the program-manager-validated vehicle counts, "
                 "Launch and Support Platforms line of effort"),
          evidenceType="Dataset",
          custodian="Army Futures Command",
          schemaRef={"$gap": "gap-data-schema"},
          pointer={"$gap": "gap-study-artefacts"},
          classification=UNRELEASED,
          scopeOfValidity={
              "builtToAnswer": ("how many vehicles were required to meet the identified "
                                "launch and support platform capability gaps"),
              "questionClass": "capability-gap",
              "conditions": [MDO],
              "intendedUse": "the Launch and Support Platforms line of effort"},
          reviewStatus="reviewed",
          reliabilitySteps=["drs-pm-validation"],
          inclusionReason=("the data behind the Launch and Support Platforms line of effort: "
                           "an Army force design update process identified the gaps and "
                           "program managers validated the counts")))

    put(o("ev-lbc-study", "Evidence", 13,
          title=("Logistics Battle Command modelling of the Distribution and Transportation "
                 "line of effort (printed pp. 13, 14)"),
          evidenceType="MSStudy",
          model="mdl-lbc",
          scenarios=["sc-europe-mdo"],
          vvaRecord="vva-lbc",
          pointer={"$gap": "gap-study-artefacts"},
          classification=UNRELEASED,
          scopeOfValidity={
              "builtToAnswer": ("whether the current TWV fleet is sufficient to provide "
                                "sustainment"),
              "questionClass": "capability-gap",
              "conditions": [MDO],
              "intendedUse": "the Distribution and Transportation line of effort"},
          reviewStatus="reviewed",
          reliabilitySteps=["drs-cdid-workshops"],
          inclusionReason=("the only modelling the description reports results from: the "
                           "initial results for this line of effort (printed p. 14)")))


def _charter(put) -> None:
    put(o("ch-twv-2021", "Charter", 9, confidence="inferred",
          question=("to identify the capabilities and requirements needed for TWVs in the "
                    "MDO environment (printed p. 9), to inform the Army's 2022 TWV Strategy "
                    "(printed pp. 9, 12)"),
          decisionToBeMade=("what TWV fleet capabilities and requirements the Army's 2022 "
                            "TWV Strategy should adopt"),
          # The description states no consequence of error, and a gap marker here fails the
          # G1 charter check — a charter with no stated stakes is not a charter. This
          # sentence is a reconstruction from the study's stated purpose and says so in its
          # own text; the whole object is marked `inferred` because of it.
          consequencesOfErroneousOutput=(
              "The 2022 TWV Strategy sets TWV fleet capabilities and requirements for a "
              "force the Army plans to have MDO-capable in a single theater by 2028; a wrong "
              "answer buys the wrong number and type of tactical wheeled vehicles for that "
              "force. GAO-21-460 does not state the consequences of error; this sentence is "
              "a reconstruction from the study's stated purpose (printed pp. 6, 9)."),
          questionClass="capability-gap",
          # The object's own locator is printed p. 9 (the study's question), but the scope
          # sentences are printed p. 12 and the two definitions are printed p. 6. Each
          # carries its own page inline, so a reader can trace it without the fixture table.
          scope={
              "included": [
                  "the TWVs the Army needs for a notional force in a European MDO "
                  "environment (printed p. 12)",
                  "about 66 percent of the types of units currently used in the Army "
                  "(printed p. 12)",
                  "some surrogate units for those that currently do not exist but may in "
                  "2028— such as Strategic Fires Battalions (printed p. 12)"],
              "excluded": []},
          definitions=[
              {"term": "capabilities",
               "text": ("the technologies and abilities needed to achieve a specific "
                        "mission, for example, the fuel capacity, or equivalent, needed to "
                        "travel 300 miles (printed p. 6)")},
              {"term": "requirements",
               "text": ("the number and types of TWVs needed to achieve Army objectives "
                        "(printed p. 6)")}],
          conditionsOfInterest=[MDO],
          limitations=[
              {"statement": ("In the Distribution and Transportation line of effort, the "
                             "Army identified the lack of a sufficient, Office of the "
                             "Secretary of Defense-approved, Multi-Domain Operations Defense "
                             "Planning Scenario for the European theater as a limitation "
                             "(printed pp. 13–14)."),
               "mitigation": ("Modeling officials stated they modified an existing scenario "
                              "previously developed to support a European Command wargame "
                              "(printed pp. 13–14); recorded as sc-europe-mdo.")},
              {"statement": ("Another limitation identified for this line of effort was a "
                             "sustainment analysis focused on distribution from the theater "
                             "operations down to the brigade level (printed p. 14)."),
               "mitigation": ("no mitigation was necessary for this limitation since there "
                              "were no specific shortfalls identified at the brigade level")}],
          authority={"signer": "Army Deputy Chief of Staff, G-8",
                     "board": "Army Futures Command, Futures and Concepts Center"},
          successCriteria=["a 2022 TWV Strategy informed by identified capabilities and "
                           "requirements"],
          # `readiness_report` resolves the tailoring through this field and refuses without
          # it: the charter is where a record says which standard it asked to be held to.
          decisionClassPolicy="pol-twv"))


def _value_model(put) -> None:
    """Three objectives, three measures, two alternatives.

    The description lists the three lines of effort (p. 11) and does not rank them, so no
    Objective carries a `priorityRank`: the field is optional, and an absent rank says
    nothing where a fabricated one would say something false.
    """
    put(o("obj-mobility", "Objective", 11,
          name=("Mobility. The ability of a unit to move from point A to B using only its "
                "own assets, expressed as a percentage."),
          priority="primary", measures=["m-mobility-pct"],
          # `provenance` is inferred, not stated: printed p. 12 says the study's
          # *objective* "addresses Army G-8's direction", and printed p. 11 lists the three
          # lines of effort without attributing the three-way split to the memo.
          provenance="ev-g8-memo-2020-04-30", confidence="inferred"))

    put(o("obj-launch-support", "Objective", 11,
          name=("Launch and Support Platforms. Some TWVs are used as a platform for weapon "
                "systems such as the High Mobility Artillery Rocket System or communication "
                "systems."),
          priority="primary", measures=["m-lsp-vehicles"],
          # `provenance` is inferred, not stated: printed p. 12 says the study's
          # *objective* "addresses Army G-8's direction", and printed p. 11 lists the three
          # lines of effort without attributing the three-way split to the memo.
          provenance="ev-g8-memo-2020-04-30", confidence="inferred"))

    put(o("obj-distribution", "Objective", 11,
          name=("Distribution and Transportation. The conveyance and delivery of supplies, "
                "equipment, and troops; for example, truck companies that deliver water, "
                "fuel, ammunition, and food to the battlefield."),
          priority="primary", measures=["m-dt-sustainment"],
          # `provenance` is inferred, not stated: printed p. 12 says the study's
          # *objective* "addresses Army G-8's direction", and printed p. 11 lists the three
          # lines of effort without attributing the three-way split to the memo.
          provenance="ev-g8-memo-2020-04-30", confidence="inferred"))

    put(o("m-mobility-pct", "Measure", 11,
          objective="obj-mobility",
          task="move a unit from point A to B using only its own assets",
          attribute="mobility",
          measure="percentage of the unit moved by its own assets",
          metric={"units": "percent", "direction": "max"},
          criteria={"$gap": "gap-thresholds"},
          conditions=[MDO]))

    put(o("m-lsp-vehicles", "Measure", 13,
          objective="obj-launch-support",
          task=("provide a platform for weapon systems such as the High Mobility Artillery "
                "Rocket System or communication systems"),
          attribute="launch and support platforms",
          measure=("number of TWVs required to meet the identified launch and support "
                   "platform capability gaps"),
          # `direction` is schema-forced. The description states no direction of goodness
          # for this count — it is the number of vehicles needed to close a gap, which is
          # neither a thing to maximise nor, on its own, a thing to minimise.
          metric={"units": "vehicles", "direction": "min"},
          criteria={"$gap": "gap-thresholds"},
          conditions=[MDO]))

    put(o("m-dt-sustainment", "Measure", 14,
          objective="obj-distribution",
          task=("distribute supplies, equipment and troops from theater operations down to "
                "brigade level"),
          attribute="sustainment",
          measure=("sufficiency of the TWV fleet to provide sustainment from theater "
                   "operations down to brigade level"),
          metric={"units": "sufficient or insufficient", "direction": "max"},
          criteria={"$gap": "gap-thresholds"},
          conditions=[MDO]))

    put(o("alt-current-fleet", "Alternative", 14,
          name="the current TWV fleet",
          description=("Army officials told GAO that the initial results of modeling for the "
                       "Distribution and Transportation line of effort shows the current TWV "
                       "fleet is sufficient to provide sustainment (printed p. 14)."),
          status="candidate", baselineFlag=True, enteredOrder=1))

    put(o("alt-mdo-fleet", "Alternative", 14,
          name="the TWV fleet required for a European MDO environment",
          description=("The initial results indicated the potential need for an increase in "
                       "TWVs and associated trailers due to mobility requirements and the "
                       "need for additional launch and support platforms (printed p. 14). "
                       "Army officials stated that these results did not reflect the results "
                       "of modeling and relied, in part, on previously completed analyses."),
          status="candidate", baselineFlag=False, enteredOrder=2))


def _grca(put) -> None:
    """Ground rule, constraint, assumption, scenario."""
    put(o("gr-mdo-force", "GroundRule", 12,
          statement=("the TWVs the Army needs for a notional force in a European MDO "
                     "environment — the stressor force for the study according to Futures "
                     "and Concepts Center officials"),
          source="ev-gao-21-460"))

    put(o("con-schedule", "Constraint", 14,
          statement=("According to MDO TWV Study officials, they delayed the final report "
                     "from March 2021 until July 2021 due to the time required to accurately "
                     "define the level of detail needed for the force used in the model."),
          kind="programmatic", source="ev-gao-21-460",
          implications=("the 2022 TWV Strategy depends on a study whose final report was not "
                        "available during GAO's audit, so only the study's design and "
                        "portions of its execution could be assessed (printed pp. 14, 35).")))

    put(o("as-readiness-90", "Assumption", 12,
          statement=("the Army assumes an operational readiness rate of 90 percent but then "
                     "mitigates for this assumption by varying readiness rates to perform "
                     "sensitivity analysis according to Army officials."),
          linchpin=True,
          rationale=("the study's assumptions are clearly defined and mitigation assessments "
                     "were performed (printed p. 12)"),
          evidence="ev-army-officials-2021",
          implicationsIfWrong={"$gap": "gap-readiness-implications"},
          indicatorsThatWouldAlter={"$gap": "gap-readiness-indicators"},
          variedInSensitivity=True))

    put(o("sc-europe-mdo", "Scenario", 14,
          name="Modified European Command wargame scenario",
          description=("An existing scenario previously developed to support a European "
                       "Command wargame, which modeling officials stated they modified for "
                       "the study (printed pp. 13–14). The description does not say what was "
                       "modified."),
          rationale=("It mitigates the limitation the Army identified for the Distribution "
                     "and Transportation line of effort: the lack of a sufficient, Office of "
                     "the Secretary of Defense-approved, Multi-Domain Operations Defense "
                     "Planning Scenario for the European theater (printed pp. 13–14)."),
          conditions=[MDO],
          source="ev-gao-21-460"))


# MIL-STD-3022 §5.3 retains every section, whether or not it has content. Both records
# below carry all eight; what is missing is recorded as a gap, section by section.
VVA_SECTIONS = ["Problem Statement", "M&S Requirements and Acceptability Criteria",
                "M&S Assumptions, Capabilities, Limitations & Risks/Impacts",
                "Accreditation Methodology", "Issues", "Key Participants", "Resources",
                "Lessons Learned"]


def _models(put) -> None:
    """Two models and their VV&A records. Neither model has a public accreditation package.

    `definition.version` is required and is *not* a slot, so a gap marker fails schema
    validation there: both models carry the literal string that says the description gives
    no version, rather than a version number nobody published.
    """
    lbc_gap = {"$gap": "gap-vva-lbc"}
    put(o("vva-lbc", "VVARecord", 13, confidence="inferred",
          problemStatement="ch-twv-2021",
          requirementsAndAcceptabilityCriteria=lbc_gap,
          assumptionsCapabilitiesLimitationsRisks={
              "assumptions": lbc_gap, "capabilities": lbc_gap,
              "limitations": lbc_gap, "risks": lbc_gap},
          methodology=lbc_gap,
          # The one piece of content in this record: the description reports an internal
          # V&V process, not its package. The date is the audit year, not a stated
          # accreditation date, which is why the object is marked `inferred`.
          accreditationDecision={
              "authority": ("Army modeling officials — an internal verification and "
                            "validation process involving experts not involved with the "
                            "project"),
              "date": "2021",
              "scope": ("review of the Logistics Battle Command model to ensure it is "
                        "appropriate for the Distribution and Transportation line of effort"),
              "basis": "interview"},
          sections=[{"name": n, "content": lbc_gap} for n in VVA_SECTIONS]))

    put(o("mdl-lbc", "Model", 13,
          name="Logistics Battle Command model",
          definition={"kind": "simulation", "version": "unversioned in the public description"},
          intendedUse=("simulates the consumption and distribution of all classes of supply "
                       "at either the platform level or the unit level"),
          questionClass="capability-gap",
          vvaRecord="vva-lbc",
          qualificationStatus="validated",
          limitations=[
              {"statement": ("The model requires extensive data inputs from various sources "
                             "(printed p. 13)."),
               "justification": lbc_gap}]))

    cba_gap = {"$gap": "gap-vva-cba"}
    put(o("vva-cba", "VVARecord", 12,
          problemStatement="ch-twv-2021",
          requirementsAndAcceptabilityCriteria=cba_gap,
          assumptionsCapabilitiesLimitationsRisks={
              "assumptions": cba_gap, "capabilities": cba_gap,
              "limitations": cba_gap, "risks": cba_gap},
          methodology=cba_gap,
          accreditationDecision=cba_gap,
          sections=[{"name": n, "content": cba_gap} for n in VVA_SECTIONS]))

    put(o("mdl-cba", "Model", 12,
          name="Capabilities based assessment",
          definition={"kind": "rubric", "version": "unversioned in the public description"},
          intendedUse=("the assessment of all three lines of effort that identified the "
                       "operational tasks, conditions, and standards needed to achieve "
                       "military objectives; assessed current and future capabilities to "
                       "identify gaps; and sought to determine TWV solutions (printed "
                       "pp. 12–13)"),
          questionClass="capability-gap",
          vvaRecord="vva-cba",
          qualificationStatus="draft"))


def build() -> Graph:
    """The record as a human transcribed it from the description, before anything is
    computed. There is nothing to compute: the study had not reported."""
    g = Graph()

    def put(obj: dict) -> None:
        g.put(obj, H)

    # Our scoring policy, not the Army's — the description says nothing about how the
    # study would be scored. `method` is forced: the enum offers mavt/ahp/topsis/pugh and
    # has no value for a capabilities-based assessment, which is what the study ran.
    put(o("pol-twv", "Policy", 6, confidence="inferred",
          name="MDO TWV capability study (GAO-21-460 comparison policy)",
          version="0.1", decisionClass="capability-study", method="mavt",
          tailoring="gao-21-460", aggregationK=1, requiredBiasChecks=[],
          requireAllLinchpinsVaried=False,
          prohibitedExclusionReasons=["time-or-resource"], blockingRules=[],
          nSimplex=200))

    _gaps(put)
    _reliability(put)
    _evidence(put)
    _charter(put)
    _value_model(put)
    _grca(put)
    _models(put)

    # Equal weights across the three lines of effort are ours, and the name says so: the
    # description never states that the lines of effort were weighted or combined at all.
    put(o("ws-twv", "WeightSet", 11, confidence="inferred",
          name="equal weight across the three lines of effort (ours, not the Army's)",
          method="equal",
          weights={"m-mobility-pct": 0.333333, "m-lsp-vehicles": 0.333333,
                   "m-dt-sustainment": 0.333334},
          provenance={"$gap": "gap-weights"}))

    put(o("ep-twv-2021", "DecisionEpisode", 9,
          sequence=1, charter="ch-twv-2021", lifecycleState="DRAFT", transitions=[],
          objectives=["obj-mobility", "obj-launch-support", "obj-distribution"],
          alternatives=["alt-current-fleet", "alt-mdo-fleet"],
          groundRules=["gr-mdo-force"], constraints=["con-schedule"],
          assumptions=["as-readiness-90"],
          evidenceRegister=["ev-gao-21-460", "ev-g8-memo-2020-04-30",
                            "ev-fcc-oporder-19-014", "ev-army-officials-2021",
                            "ev-mobility-data", "ev-lsp-data", "ev-lbc-study"],
          scenarios=["sc-europe-mdo"],
          models=["mdl-lbc", "mdl-cba"], weightSets=["ws-twv"],
          # Linked here, at the episode's first revision, so that G2's `plan-present`
          # check has something to read when a human drives the gate.
          plan="pl-twv",
          # Everything below is empty because the study had not reported (printed p. 14):
          # no claims, no observations, no runs, no distribution.
          claims=[], risks=[], biasChecks=[], mandateElements=[], observations=[],
          runs=[], flipAnalyses=[], narratives=[], distribution=[],
          asOf=AS_OF))

    step_authority = {
        "document": "FCC OPORD 19-014: Multi-Domain Operations Tactical Wheeled Vehicle Study",
    }
    steps = [("mobility", "mdl-cba", "m-mobility-pct", "Mobility"),
             ("launch-support", "mdl-cba", "m-lsp-vehicles", "Launch and Support Platforms"),
             ("distribution-transportation", "mdl-lbc", "m-dt-sustainment",
              "Distribution and Transportation")]
    put(o("pl-twv", "Plan", 36, confidence="inferred",
          episode="ep-twv-2021", policyBasis="pol-twv",
          steps=[{"id": sid, "evaluator": evaluator, "method": "mavt",
                  "alternatives": ["alt-current-fleet", "alt-mdo-fleet"],
                  "measures": [measure], "weightSet": "ws-twv",
                  "authority": {**step_authority,
                                "paragraph": f"study plan, {loe} line of effort "
                                             f"(GAO-21-460 printed p. 36)"}}
                 for sid, evaluator, measure, loe in steps],
          # The description gives no date for the OPORD, so the date here is the G-8
          # tasking memo's, named in the same appendix — hence `inferred` on the whole
          # object. `deviations` is omitted rather than set to `[]`: the description says
          # nothing about deviations, and an empty list would assert there were none.
          approvedBy={"actorId": ("Army Futures Command, Futures and Concepts Center "
                                  "(FCC OPORD 19-014)"),
                      "date": "2020-04-30"}))

    return g
