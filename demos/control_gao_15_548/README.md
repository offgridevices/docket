# Positive control — the A.T. Kearney combat vehicle industrial base study (GAO-15-548)

**Source:** U.S. Government Accountability Office, *Army Combat Vehicles: Industrial Base
Study's Approach Met Research Standards*, GAO-15-548 (16 June 2015) —
`sources/gao-15-548-army-combat-vehicles-industrial-base-study.pdf`, public, committed.
Page numbers below are the report's **printed** pages; the PDF page is three higher, which
is what the `#page=` pointers in the record carry.

**Run it:** `uv run python -m demos.control_gao_15_548.run` → writes `out/`.
**Check it:** `uv run pytest -q tests/demos/test_control_gao_15_548.py`.
**Results file:** this demo declares **`out/control.json`** as its machine-readable
summary — the name is the module constant `RESULTS_FILE` in `run.py`, so plan 05 Task 8's
`run_all` can read it rather than remember it. (Demo A declares `results.json` and
`validation_gao_21_460` declares `agreement.json`; the names differ on purpose, which is
why each demo has to state its own.)

---

## What this control is for

Every other case in the Phase I validation set is a study somebody found fault with. Run
only against those, a scorer that returned "concerns" for any input at all would look
perfect. This is the case that makes the scorer falsifiable in the other direction: **a
study GAO examined and passed, under the same standard, put through the same pipeline.**

Same buyer, same vehicle family, same congressional-report genre, one generation earlier
than OMFV. GAO's own published verdict, printed p. 7:

> the Army's combat vehicle industrial base study's approach — including its design,
> execution, and presentation of results — was both reasonable and sound for its intended
> purposes

The control passes if the schema does not manufacture representation faults that the study
did not have. It does. **Measured:** every one of the 21 applicable questions scores 1 or
2, all three dimension verdicts read `generally_*`, and not a single representation
finding fires — the readiness report's warning list is empty.

---

## Everything below the line is OURS, not GAO's

> **GAO published no per-question ratings for this study.** Printed p. 24 (PDF p. 27):
> *"For reporting purposes, we determined that qualitative assessment ratings provide the
> best explanation of the nuances of the analysis and findings, rather than numeric
> ratings for each individual standard."* Every per-question state in the table below is
> ours.
>
> **GAO-15-548 does not grade on objectivity, validity and reliability either.** That
> frame comes from Section 234(d) of the FY2022 NDAA and appears in GAO-23-106549 (printed
> p. 17). Mapping this study onto the three dimensions, and the three verdicts, are ours
> as well.
>
> GAO-21-460 Figure 6 remains **the only per-question published key** in the twenty-year
> series. This case has none.

### Measured per-question states

Tailoring `gao-15-548` — 21 applicable questions of the 36-question standard, 15 tailored
out. Read from `out/control.json`; the third column is the rule clause that fired.

| question | state | firing clause |
|---|---|---|
| DES-1 Is the study's design clear? | 1 | `charter_complete_and_plan_approved` |
| DES-2 Is the study's objective clearly stated? | 1 | `charter_question_and_terms_defined` |
| DES-3 Is the study's scope clearly defined? | 1 | `scope_defined_and_terms_defined` |
| **DES-4 Are the assumptions explicitly identified?** | **2** | `assumptions_listed` |
| DES-5 Are the assumptions reasonable and consistent? | 1 | `assumptions_all_evidenced_and_consistent` |
| **DES-6 Are the assumptions varied to allow for sensitivity analyses?** | **2** | `any_assumption_varied` |
| DES-7 Are major constraints identified and discussed? | 1 | `constraints_discussed` |
| DES-8 Are the scenarios that were modeled reasonable ones to consider? | 1 | `scenarios_have_rationale` |
| DES-9 Do the scenarios represent a reasonably complete range of conditions? | 1 | `scenarios_cover_conditions` |
| EXE-1 Is the methodology consistent with the study objective? | 1 | `methodology_covers_objectives` |
| EXE-2 Are the study's objectives addressed? | 1 | `objectives_addressed` |
| EXE-3 Were the models appropriate for their intended purpose? | 1 | `models_scope_ok` |
| EXE-4 Were the data valid for the study's purposes? | 1 | `data_scope_all_known` |
| EXE-5 Were the data sufficiently reliable? | 1 | `reliability_all` |
| EXE-6 Were data limitations identified and their impact explained? | 1 | `limitations_all_explained` |
| EXE-7 Were M&S limitations identified, explained and justified? | 1 | `ms_limitations_all_justified` |
| **EXE-8 Have the models been described and documented adequately?** | **2** | `models_documented_na_reasoned` |
| **PRE-1 Do the results of the modeling support the report findings?** | **2** | `claims_all_supported` |
| PRE-2 Does the report present an assessment that is well documented? | 1 | `claims_exist_no_silence_no_blocking_gaps` |
| **PRE-3 Are the conclusions sound?** | **2** | `claims_exist_no_silence` |
| **PRE-4 Are the study results presented clearly?** | **2** | `claims_all_supported` |

Fifteen questions are tailored out: DES-10 to DES-14, EXE-9 to EXE-15, PRE-5 to PRE-7.
They are retained in the 36-question standard (GAO-16-820 App. I) and scored on request.

### Measured dimension verdicts (ours)

| dimension | verdict | the state-2 questions the qualifier names |
|---|---|---|
| objectivity | `generally_objective` | DES-4, PRE-3, PRE-4 |
| validity | `generally_valid` | PRE-1, PRE-3 |
| reliability | `generally_reliable` | DES-6, PRE-3 |

Aggregation `k = 21`, set on `pol-kearney`. **Measured: at the kernel default `k = 1` all
three dimensions read `not_objective` / `not_valid` / `not_reliable`** — the scorer would
fail a study GAO passed, on three questions the qualifier sentence already names. The
policy parameter exists so it does not, and its basis is GAO's own aggregation rule,
GAO-23-106549 printed p. 17:

> we drew conclusions that the report was generally objective when available information
> presented in the report was consistent with our definition of objectivity but was
> missing information that would have addressed the generally accepted research standards

That is a rule about *missing information*, not a count of it. `k = 21` makes
`generally_X` hold unless a mapped question reaches state 3 or 4; the weight then sits on
the qualifier sentence, which names every state-2 question by id and by topic. This is a
**policy parameter**, not a kernel change: the default is untouched and every other policy
in the repository still uses it.

**This value is pending Shreyash's sign-off.** The reasoning, the alternatives and the
reversal conditions are in
`docs/decisions/2026-09-05-aggregation-k-is-a-policy-parameter.md`; the `k = 1` result is
recorded immediately above and pinned as a test, so the choice can be reversed on the
evidence rather than on argument. Note also that `k` caps state-2 questions only — one
state-3 question still forces `not_X` at any `k`, which the DES-6 probe below
demonstrates.

`aggregationK` is also the **only** dial on `pol-kearney` that changes anything. Measured:
setting `blockingRules` to Demo A's four-rule promotion list and `requireAllLinchpinsVaried`
to `true` leaves every per-question state, both verdict sets, the single blocker and the
empty warning list untouched — `requireAllLinchpinsVaried` is in fact read nowhere in
`src/docket` outside the schema and an API fixture. So the whole `generally_*` result rests
on one number, and that number has a decision file behind it.

---

## Which finding classes fire, and which do not

This is the substance of what the control controls for.

### Fires: one blocker, and it is about a missing computation, not a misrepresentation

| rule | object | why |
|---|---|---|
| `objective-run-coverage` | `obj-viability` | no evaluation run scored any measure of the primary objective |

`ready` is **false**, for that one reason. It is a true statement about a narrative study:
five of the study's six analyses are qualitative, GAO publishes no per-alternative
numbers, and this record therefore carries `runs: []`, no `Observation`, and no
`FlipAnalysis`. Rather than invent numbers to clear the blocker, the record stops at
`PLAN_APPROVED` — the `EVALUATED` gate asks that every planned step have a sealed run
behind it, and that gate is not driven because it would rightly refuse.

The same fact is what puts PRE-1, PRE-3 and PRE-4 at 2 rather than 1: each of their
state-1 clauses reads a run's sealed results, and there are none. They reach 2 rather than
4 through the narrative-only clauses added under ruling R2
(`docs/decisions/2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md`).

### Does not fire: every representation rule in the kernel

Measured — the readiness report's `warnings` list is **empty** and `computedBiasRisks` is
**empty**. None of these fires:

`silent-omission`, `claim-unsupported`, `claim-on-gap`, `claim-on-exclusion`,
`inclusion-reason-missing`, `definition-missing`, `linchpin-unevidenced`, `model-vva`,
`vva-verbal`, `accreditation-scope`, `bias-check-missing`,
`bias-check-evidence-unreviewed`, `bias-check-evidence-gap`, `ReusePastPurpose`,
`ModelUsePastPurpose`, `ReaccreditationRequired`, `NotAssessableAtLevel`, `scope-unknown`,
`scope-lapsed`, `condition-mismatch`, `value-conflict`, `assumption-conflict`,
`gap-unconfirmed`, `exclusion-prohibited-reason`, `baseline-present`,
`alternative-status-unreasoned`, `objective-measured`, `observation-duplicate`.

Why each stays quiet, in the cases where it took work to keep it quiet:

* **`silent-omission`** — the evidence register holds ten items. Nine are cited by a
  Claim. The tenth is the Kearney report itself, whose pointer is a recorded gap
  (`gap-kearney-report`): it is covered by a typed `Exclusion`
  (`ex-kearney-report-not-public`) instead. *Measured probe:* point that exclusion at
  something else and `silent-omission` fires on the report. The cover is load-bearing.
* **`NotAssessableAtLevel`** — no Claim rests on the Kearney report, for the same reason.
  A claim asserting "assessable at U" while resting on evidence whose metadata nobody
  outside the Army can see is exactly what the scope checker exists to refuse.
  Demonstration A hits the identical mechanism with the Army's Milestone A analysis of
  alternatives.
* **`ReusePastPurpose`** — every Claim carries the charter's question class,
  `industrial-base`, and so does every piece of evidence it rests on. Nothing here is
  reused past the purpose it was built for, so nothing needs a reuse justification.
* **`definition-missing`** — both charter definitions carry text. This matters for the
  DES-4 correction below.
* **`bias-check-evidence-unreviewed`** — `bc-oem-review` (the May 2013 presentation of
  contractor-specific preliminary findings to the original equipment manufacturers,
  printed p. 14) produces `ev-oem-review-2013`, whose `reviewStatus` is `reviewed`: the
  manufacturers were the reviewers.

---

## The DES-4 mechanism — a correction

An earlier draft of the plan attributed DES-4 = 2 to a gapped **charter definition** of
"minimum sustainment rate". That is the wrong object. A `Charter.definitions[].text` gap
drives `definition-missing`, which feeds DES-2 and DES-3, not DES-4. DES-4's ladder is
`assumptions_all_have_rationale → 1`, else `assumptions_listed → 2`, and it reads
**assumption rationales**.

And it is not one assumption but **two** — which is closer to GAO, not further from it.
GAO printed p. 10 says the study's assumptions were generally reasonable "although some
key assumptions could have been discussed or defined more explicitly", and gives exactly
two examples:

1. `as-min-sustainment-rate` — printed p. 13, the study *"used the minimum sustainment
   rates as derived by the original equipment manufacturers, but did not include specific
   information on how that minimum sustainment rate was derived"* → `rationale` is
   `gap-msr-derivation`.
2. `as-army-risk-perspective` — printed p. 12, *"a key assumption that was not explicitly
   identified was that the study assessed risk from the perspective of the Army"* →
   `rationale` is `gap-risk-perspective-rationale`.

**Measured:** patch either rationale alone and DES-4 stays at 2; patch both and it goes to
1. The state rests on those two objects and on nothing else, and they are GAO's own two
examples. The definition of "minimum sustainment rate" is carried in the charter *with
text* (printed p. 13, as GAO reports Army and commercial industry officials describing it),
so `definition-missing` does not fire and DES-2/DES-3 stay at 1.

`gap-msr-derivation` is `degrading`, not `blocking`, on GAO's own authority — printed
p. 13: *"we do not believe that the lack of explicitly stated information materially
affected the results of the study."* A blocking gap would drop PRE-2 from 1 to 2 and would
put a severity on the record that GAO did not.

---

## Why this case's VV&A is recorded and GAO-21-460's is a gap

Both reconstructions face the same question — what accreditation did the study's model
have? — and answer it differently, on the sources rather than on convenience.

**Here**, the accreditation basis is recorded as the study's own documentation
(`basis: "document"`, `document: "ev-kearney-final-report"`, authority "A.T. Kearney (the
study's authors)") because GAO **had** that documentation: printed p. 2, GAO gathered
*"interim and final study briefings, backup slides that detail the methodological elements
of the study, and the final report to the congressional defense committees"*, and found
the study executed in accordance with its defined methodology. **In `demos/
validation_gao_21_460`**, the same field is honestly a gap or an interview-basis
assertion, because GAO-21-460 printed p. 35 records that the study's **final report was
not available** during the audit. Different evidence, different record. Reading GAO's
documentary review as an accreditation basis is still **our** reading, and it is labelled
`confidence: "inferred"` on the object and stated in `expected.yaml`.

The consequence is load-bearing, and worth stating plainly rather than leaving to be
inferred: EXE-14 (a signed VV&A report) is tailored out of `gao-15-548`, so the reading
buys no state directly — but **measured**, replacing both `accreditationDecision`s with a
recorded gap (DECISION NEEDED 1 option (a)) takes EXE-3 from 1 to 4, makes `model-vva`
block, and collapses validity to `insufficient_to_conclude`. This is not a free field.

Three further layers sit on that same field and none of them is GAO's:

1. The basis **document** is `ev-kearney-final-report`, whose own `pointer` is a recorded
   gap. A document-basis accreditation resting on a document nobody can read is still a
   document-basis accreditation as far as the kernel is concerned — `vva-verbal` fires only
   when the basis is *not* a document, so nothing notices. That is a kernel blind spot this
   control happens to sit on, not a fixture defect, and it is flagged for plans 06 and 08.
2. The accreditation **authority** is the model's own author, A.T. Kearney. Under
   MIL-STD-3022 an accreditation authority is the *user* organisation, not the developer.
   The record says who it was; it does not claim the arrangement met the standard.
3. The **date**, 2014-04, is the month the final report went to the committees, not a
   stated accreditation date — GAO reports none.

So the quietest passing field in this record is the one with the least behind it. Said
here rather than discovered later.

---

## Fields the schema forced, and what we put in them

Design §2.3 item 19 is the failure mode where a tool's own catalogue forces a shape onto a
record that the record does not have. It happens to us here, four times, and pretending
otherwise would be the same fault.

| field | what the schema demands | what this record says | honest status |
|---|---|---|---|
| `Policy.method` | one of `mavt`, `ahp`, `topsis`, `pugh` | `mavt` | **forced.** The enum has no value for a six-analysis management-consulting method. No MAVT arithmetic runs in this control; the value exists only so the plan's steps can match the policy. |
| `Model.definition.version` | a required string, not a P3 slot | `"unversioned in the public description"` | **forced.** GAO never versions the spreadsheet model or the six-analysis method. A gap marker is not permitted in a non-slot field, so the string says so instead. |
| `Measure.metric.units` and `.direction` | required strings, `direction` ∈ {`max`, `min`} | descriptive units per analysis; `min` for the three cost-shaped analyses, `max` for the current-state assessment and the network strategy plan | **forced.** Five of the six analyses are qualitative; GAO reports findings, not scores. The directions are our reading. |
| `WeightSet` on every `Plan.step` | required | `ws-kearney`, six equal weights, `provenance: {"$gap": "gap-weights"}` | **ours, and labelled.** The public account does not say the analyses were weighted or combined into a single score at all. The name of the object says "OURS, not the study's". |
| `Plan.approvedBy` | an actor and a date | the Army's **October 2012 contract award** to the management consulting firm — printed p. 18: "The Army issued a contract with the management consulting firm in October 2012" | **a reconstruction, recorded in the field the kernel reserves for the G2 human approval.** GAO's page reports a contract award, not an approval of a methodology, and this row does not upgrade it into one. The human approval of *this record* is `shreyash`, and it is in the episode's transition log, not here; the Plan object carries `confidence: "inferred"`. |

Two further shapes are ours rather than the study's: the split of the six analyses across
two Objectives (four to "assess the base", two to "develop strategic alternatives") is
GAO's own, printed p. 9 — but making them `Measure`s under `Objective`s at all is the
schema's idea, not the study's.

---

## Which reliability steps are general and which are item-specific

This is the softest judgement in the fixture and it should not have to be dug out of a
review, so it is here.

`EXE-5` reads 1 because **every** claim-cited evidence item carries a
`DataReliabilityStep`. Four of those attachments are ones GAO names against the specific
item: the non-respondent follow-up on the supplier survey (printed pp. 15–16), the
overhead normalisation on the manufacturing cost data (printed p. 16), the Abrams program
office on the government cost data (printed p. 16), and GAO's own two-analyst
reconciliation on GAO's own report (printed p. 2).

**The other seven attachments read a general GAO finding at the scope GAO wrote it at.**
Printed pp. 16–17 carry a titled section — *"The Army Took Sufficient Actions to Ensure
the Data Were Valid and Reliable for the Study's Purposes"* — and under that heading each
step is stated as a universal about the study's data, followed by an instance marked
**"For example"**:

> To ensure that valid data were obtained, the study's authors went to the original
> sources to obtain relevant information and sought clarification to make sure they
> understood the data provided. **For example**, they obtained information on government
> expenses at the Joint Systems Manufacturing Center directly from the Abrams program
> office.

> To ensure the data's reliability, the study's authors went back to the data sources, in
> many cases multiple times, to review their methods and ensure they were using the data
> correctly. **For example**, the financial analysis for the Bradley engine…

Those two general findings are attached as follows, and each carries the caveat in its own
`description` field:

| step | attached to | GAO names the item? |
|---|---|---|
| `drs-original-sources` (printed p. 16) | `ev-manufacturer-data`, `ev-amc-baseline`, `ev-oem-rates`, `ev-army-procurement-plans` | no — GAO's named example is the Abrams program office, which carries `drs-abrams-program-office` instead |
| `drs-supplier-review` (printed p. 17) | `ev-benchmark-data`, `ev-oem-review-2013` | `ev-benchmark-data` is close (printed p. 16 describes the same put-it-back-to-the-supplier loop for benchmark estimates); `ev-oem-review-2013` is not GAO's named Bradley-engine example |

**Why this is reading GAO rather than embellishing GAO:** the "For example" is the tell.
Had GAO written only the two instances, attaching them to other items would be
over-reading. GAO wrote a general finding about the study's data and then illustrated it.

**And the counterfactual is measured, not argued.** Withdraw the general steps from the
items GAO does not name — recording a confirmed gap in the slot, since an empty
`reliabilitySteps` is a blocking `silence` finding — and the record reads: EXE-5 **2**
(`reliability_some`), PRE-1 **4** (`always`), and validity **`insufficient_to_conclude`**.
The mechanism is that `claims_all_supported` is an *all* over claim-cited evidence, so one
gapped item drops PRE-1 from 2 straight to 4 with nothing in between. Pinned as a test
beside the DES-6 and `k = 1` probes
(`::test_the_general_reliability_steps_are_load_bearing_and_the_alternative_is_measured`).

That result is the reason for keeping the attachment rather than a reason to be
comfortable with it. PRE-1 = 4 means "insufficient information to determine whether the
results support the findings" — about a study for which GAO wrote a titled section
concluding the data *were* valid and reliable. Withdrawing a finding GAO made and then
reporting the silence we created would be the larger misrepresentation, and it would run
in the direction that damages the study, which is the direction a positive control exists
to guard. If a reader disagrees, the alternative is one edit away and its result is
already published.

One item is deliberately **not** given a reliability step: `ev-kearney-final-report`. The
study is not data the study used, GAO describes no step taken on the report itself, and
its `reliabilitySteps` slot therefore holds the same recorded absence its `pointer` does.
No scoring effect — no Claim cites it.

---

## What is in the record

* **21 applicable questions**, one `DecisionEpisode` (`ep-kearney-2014`, `asOf`
  2014-04-30), one `DecisionProgram`, one `Charter` with two defined terms, four
  limitations each carrying GAO's recorded mitigation, and two `MandateElement`s (Senate
  Report 112-173 and the FY2013 NDAA conference report, printed p. 1 fn 2).
* **Two `Objective`s and six `Measure`s** — the six analyses GAO names verbatim at printed
  p. 13: current state assessment, cost baseline, supplier base analysis, benchmark
  comparison, scenario analysis, network strategy plan.
* **Three `Alternative`s** — continue Bradley production at York (the baseline), the
  two-year "warm shutdown" with restart (printed p. 11), and the courses of action the
  scenarios produced (printed pp. 14, 18).
* **Five `Assumption`s**, one of them a linchpin (the two-year warm shutdown), and one of
  them (`as-demand-scenarios`) `variedInSensitivity: true` — GAO credits this study's
  sensitivity analysis explicitly at printed p. 12, and nothing in this repository says
  otherwise. *Measured probe:* withdraw that credit and DES-6 falls 2 → 3 and reliability
  falls to `not_reliable`.
* **Ten `Evidence` items and six `DataReliabilityStep`s**, located across printed
  pp. 1–2 and 11–18 (and p. 22 fn 1 for the Kearney report's title).
* **Eleven `Claim`s**, each naming what it rests on; **five recorded gaps**, each with what
  was sought, where it was looked for, why it was not found and a human confirmation; **two
  typed `Exclusion`s**.
* **Two `Model`s with two `VVARecord`s**, whose MIL-STD-3022 §5.3 sections are filled where
  GAO describes them and marked not-applicable by a typed exclusion where GAO's account
  says nothing — which is what puts EXE-8 at 2 rather than 1.

Confidence discipline: only `ev-gao-15-548` and `drs-two-analysts` — GAO's account of GAO's
own work — carry `confidence: "explicit"`. Everything describing the Kearney study carries
`confidence: "inferred"`, because it was assembled out of GAO's prose rather than
transcribed from a study that is not public. Gaps carry `confidence: "absent"`.

---

## The agreement number, and what it is not

`out/control.json` reports **1.000** label agreement and **1.000** exact-state agreement
over 21 questions against `expected.yaml`, with Cohen's kappa **0.0** and a majority
baseline of **1.0**.

Read that carefully. `expected.yaml`'s per-question table is a **measurement target
recorded from a run of this same file**, not a published key — GAO published none. So the
1.000 is a regression check: it says the fixture still scores what it scored when the
table was taken. It is **not** a skill score and **not** evidence about GAO. The kappa is
0.0 and the baseline is 1.0 precisely because the target carries a single label; both are
reported so that the 1.000 cannot be quoted on its own. The only external comparison
available for this case is against GAO's published qualitative verdict, quoted at the top
of this file. `demos/validation_gao_21_460` is where a real per-question key exists.

---

## What this does not show

* **GAO did not assess or verify the Army's underlying analytical work** — not here, and
  not in GAO-23-106549 either (footnote 7, printed p. 9: "We did not independently assess
  or verify the analytical efforts supporting the report"). GAO-15-548 assessed the
  *reasonableness of the study's methods* (printed p. 2). Every finding in the series is a
  representation finding. This control shows that a record whose representation GAO
  approved does not trip the representation rules; it shows nothing about whether the
  study's numbers were right, and neither did GAO.
* **`generally_valid` in particular rests on two of our readings, not on GAO's text
  alone.** Both are measured, published and reversible, but a reader should know which
  load-bearing joints are ours. (1) PRE-1 = 2 depends on the general reliability-step
  attribution — withdraw it and PRE-1 = 4 and validity reads
  `insufficient_to_conclude`. (2) EXE-3 = 1 depends on reading GAO's documentary review as
  the study's accreditation basis — gap it instead and EXE-3 = 4, `model-vva` blocks and
  validity reads `insufficient_to_conclude` again. Objectivity and reliability do not turn
  on either. Both readings have their own section above.
* **The per-question layer is ours throughout.** GAO's published output for this study is
  a qualitative narrative and a one-sentence verdict. The 21 states, the three dimension
  verdicts and the aggregation rule that produced them are this project's construction.
* **The reconstruction is a reading of one document.** A different careful reader working
  from GAO-15-548 could file the same facts against different objects. Nothing here has
  been checked by a second reader; that is an open item in the Phase I plan.
* **One passed case is one case.** It rules out the trivial failure mode — a scorer that
  says "concerns" to everything — and nothing more. It says nothing about how the scorer
  behaves on a study that is *partly* sound, which is where the interesting errors live.
* **The study itself is unavailable.** Everything about the Kearney study here is GAO's
  account of it. If the April 2014 report is ever released, several of these objects would
  be rewritten from the source rather than from the description, and the states could
  move.
