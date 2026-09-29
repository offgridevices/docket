# GAO-23-106549 teardown

**Source:** `sources/gao-23-106549.pdf` — *Optionally Manned Fighting Vehicle:
Observations on the Objectivity, Validity, and Reliability of the Army's Report*,
GAO, 27 June 2023, 23 pages. Signed by Mona Sehgal, Acting Director, Contracting
and National Security Acquisitions.

**Why this document is the whole method.** GAO took a real Army ground-vehicle
acquisition decision, graded it against twenty-one published research-standard
questions using two analysts working independently and then reconciling, and
wrote down exactly where the record fell short. That is an answer key produced by
an outside referee. Our Phase I demonstration runs our schema against the Army's
own report and shows it surfaces the same gaps.

The questions themselves are transcribed in `src/docket/standard/research-standards-36.yaml`.

---

## Read this before writing a single proposal sentence

**GAO did not check the Army's math.** Footnote 7 (p. 9) and Appendix I are
explicit: *"We did not independently assess or verify the analytical efforts
supporting the report."* Every finding below is a **representation** failure —
the report did not say enough for a reader to judge it — not an analysis failure.
The Army may have done everything right and simply not written it down.

**The Army had no comments on the draft. GAO made no recommendations.** There is
no finding of wrongdoing here, and the proposal must not imply one.

**Sensitivity analysis was partially present, not missing.** GAO explicitly
credited the combat-effectiveness section for varying assumptions across the four
vehicles — engines with varying power, variance in infantry carried (p. 14). Do
not claim the Army skipped sensitivity analysis.

Overclaiming any of these three is the fastest way to lose a technically
sophisticated reviewer who has read the report.

---

## What the Army's report actually contained

It reads as a populated schema instance, which is the point:

| Object | Count |
|---|---|
| Desired characteristics | 9 |
| Prioritized attributes derived from them | 28 |
| "Analytical efforts" | 11 = 7 modelling-and-simulation studies + 4 soldier touchpoints |
| Vendor feedback events | 4 |
| Additional studies, used only for the combat-effectiveness comparison | 3 |
| Vehicles compared | 4 = 3 OMFV government concepts + modernized Bradley M2A4 |

The report was mandated by Section 234 of the FY2022 NDAA (Pub. L. No. 117-81,
§ 234), which set its scope. GAO assessed three sections of it.

---

## GAO's verdicts

GAO graded each of the three sections on objectivity, validity, and reliability.
The pattern is identical every time.

| Report section | Objectivity | Validity | Reliability |
|---|---|---|---|
| Desired characteristics | Generally objective | **Insufficient detail to conclude** | **Insufficient detail to conclude** |
| Force structure & operational concepts | Generally objective | **Insufficient detail to conclude** | **Insufficient detail to conclude** |
| Combat effectiveness comparison | Generally objective | **Insufficient detail to conclude** | **Insufficient detail to conclude** |

Three sections, three times the same verdict. Objectivity survives because the
Army drew on multiple independent sources, which limits any single source's
influence. Validity and reliability collapse for one repeated reason: **the
methodology, the data-reliability steps, and the VV&A status were not in the
report.**

That repetition is the strongest possible argument for our position. This is not
one team having a bad day. It is a structural gap in how decision records are
assembled, and it is exactly what a schema fixes.

---

## The nine findings, and the schema objects they become

### F1 — Evidence reused past the question it was built to answer

*Section 2, validity, p. 12.* The Army drew force-structure observations from a
September 2021 TRAC study and a July 2021 Maneuver Battle Lab soldier touchpoint.
Both found that a different force structure improved survivability and lethality.

But GAO reports, from Army officials themselves: *"these analyses were not
designed to draw conclusions on force structure alternatives. Instead, the
analyses were intended to assess the desired characteristics, indicating that
they may not be appropriate to support conclusions on force structure and
operational concepts."*

Nobody lied. Evidence was carried across a boundary its own authors would not
have carried it across, and nothing in the system could see the boundary because
the boundary was never recorded as data.

> **Schema consequence.** Every evidence object records the question it was built
> to answer. A claim that cites evidence outside that scope is a detectable
> error, not a judgment call. This is the strongest novelty claim in the proposal
> because it is anchored to a documented real failure rather than to a
> hypothetical.
>
> Implicates **EXE-3** (were the models appropriate for their intended purpose).

### F2 — Excluded evidence, excluded silently

*Section 2, objectivity, p. 11.* A second TRAC study expanded on the first, adding
another terrain scenario and detail from a vendor's concepts. The Army's report
included no observations from it and gave no reason.

GAO's language is careful and worth copying: *"Describing why this analysis was
not included could help prevent a perceived bias in the selection of the
analyses."*

> **Schema consequence.** Exclusion is a first-class object that demands a reason.
> Absence is invisible by construction; make it an object and silence becomes
> visible. This object was not anticipated before reading the report — it came out
> of the evidence, which is itself worth saying in the technical volume.

### F3 — The study-selection method is not described

*Section 3, objectivity, p. 13.* The combat-effectiveness comparison rests on
three additional studies. GAO: *"the report does not, however, describe how the
Army chose the three studies it presented. Describing why these analyses were
included could prevent a perceived bias in the selection of analyses."* Army
officials named a rule in interview — the studies that *"would provide the most
illustrative examples"* — which would have been auditable had it been written
down.

> **Schema consequence.** The inverse of F2. Inclusion needs a recorded reason
> too, not only exclusion: every evidence object carries an
> `Evidence.inclusionReason`, and a study cited without one is a gap.
> Implicates **DES-1**, **DES-3** and **EXE-1**.

### F4 — Classification is the root cause, three separate times

This is the finding that turns a schema into a product requirement.

| Where | What was withheld | Stated reason |
|---|---|---|
| p. 11 | Observations from the second TRAC study | *"not included due to security concerns"* |
| p. 14 | Quantitative survivability, mobility, and lethality metrics — which existed and were used | *"did not include these metrics in the report due to security concerns"* |
| p. 9–10 | Methodology and model detail behind the 11 analytical efforts | classification cited in interviews (the description gap itself is F7) |

The metrics were not missing. They were used, and they could not be shown.

> **Schema consequence.** Separate **claim**, **evidence pointer**, and
> **classification of the evidence**. A reader at an unclassified level must be
> able to verify that a metric exists, has provenance, and passed VV&A — without
> seeing its value. A decision package assessable at one level while its evidence
> sits at another.
>
> This is a serious differentiator and it emerged from the report rather than
> from the topic text, which is the sort of thing a reviewer notices.

### F5 — VV&A that exists but does not travel

*Sections 1 and 3, reliability, pp. 10 and 14.* Army officials told GAO that all
models and simulations behind the 11 analytical efforts had gone through the
Army's standard verification, validation, and accreditation process. That answer
was given **verbally, in an interview**. It is not in the report.

The Army described VV&A as determining whether models accurately represent the
developer's specifications; the extent to which they are accurate real-world
representations; and whether a model is acceptable for a specific purpose. That
last clause is the same scope-of-validity idea as F1, already written into
Army doctrine.

> **Schema consequence.** VV&A status is a property of the model object and
> travels with the package. It cannot live in an interview.
>
> Implicates **EXE-8** (have the models been described and documented adequately)
> and **PRE-2** (does the report present a well-documented assessment).

### F6 — An unsupported assumption stated plainly (Poland bridges)

*Section 1, validity, p. 9.* The report *"assumes that bridges in Poland are
representative of those across Eastern Europe, but the Army does not identify the
data and methods used to support this assumption."*

A single sentence, and it is the cleanest possible demonstration of the
stage-4 "what flips the decision" gate: an assumption that is both unevidenced
and load-bearing. Worth using as a worked example in the technical volume — it is
concrete, it is short, and it needs no classified context to understand.

Implicates **DES-4** and **DES-5**.

*The first pass folded these three findings into the classification finding.
They are separate, and GAO states each on its own. Every heading in this
section is numbered to match
`library/gao/derived/gao-23-106549-ground-truth.yaml` (F1–F9).*

### F7 — the methodology of the 11 analytical efforts is not described

*pp. 9–10, repeated for every section.* GAO's sentence is about description, not
classification: *"the Army report did not clearly describe the methodology of
these efforts."* The interviews cited classification for some detail, but GAO's
finding is that the report does not say what each effort did, with what
instrument, on what sample. The soldier touchpoints are the sharpest case —
neither the report nor Army regulation specifies a method, sample size,
instrument or analysis standard for a touchpoint.

> **Schema consequence.** Evidence objects carry type-specific required fields
> (a touchpoint has `n`, `selectionRule`, `instrument`, `analysisMethod`; an M&S
> study has `model`, `scenarios`, a VV&A record). Absence becomes a gap object,
> not an inference. Implicates **EXE-8** and **PRE-2**.

### F8 — the steps taken to ensure data reliability are not described

*p. 9, repeated per section.* GAO's phrase: the report did not describe *"the
steps it took to ensure data reliability."* This is the anchor reliability
finding, and it is not the VV&A finding — data reliability (GAO-20-283G) is
about the inputs, VV&A about the models.

> **Schema consequence.** Every Evidence object carries `reliabilitySteps[]`;
> an empty list is a gap. Implicates **EXE-5**.

### F9 — "force structure" and "operational concepts" are not defined

*p. 10.* *"The Army's report did not clearly define, however, force structure
or operational concepts."* The section that draws conclusions about them never
says what they are.

> **Schema consequence.** Charter scope terms carry definitions; an undefined
> scope term is a validation finding. Implicates **DES-2** and **DES-3**.

---

## Three qualifications to the verdict table

1. **"Generally objective" carries GAO's own qualifier** on every section, e.g.
   p. 9: *"the report does not, however, thoroughly describe all of the
   assumptions and limitations the Army may have considered in the study, which
   are components of objectivity."* Quote the verdict with its qualifier.
2. **§234(d) asked GAO for more than GAO delivered.** The statute directed an
   assessment of objectivity, validity and reliability; GAO assessed the
   *report's presentation* of them (footnote 7). The criteria are statutory —
   §234(d) was added in conference with no legislative history — which is why
   the standard is not GAO's preference but Congress's.
3. **Award-date discrepancy.** GAO says the five concept-design contracts were
   awarded September 2021 (pp. 2, 5). Five SAM.gov award notices and two Army
   budget books (PB2022 R-3 p. 500; PB2023 R-3 p. 290) say July 2021. State the
   Army record's date and footnote the conflict; do not assert GAO is wrong.

The sensitivity credit (p. 14) stands: the Army varied assumptions across the
four vehicles. Do not claim otherwise.

---

## What the demonstration can and cannot show

**Can:** reconstruct the decision package structure from the public report,
score it on the 36-question standard under GAO's own 21-question tailoring, and
surface the same gaps GAO found — with the evidence-scope violation in F1
detected mechanically rather than by reading fifteen pages.

**Cannot:** reproduce the Army's analysis or its numbers. The metrics are
classified. Say this plainly in the proposal; a reviewer who spots us eliding it
will discount everything else.

---

## Open threads

- GAO-21-460, GAO-15-548, GAO-06-938, GAO-11-82R, GAO-15-457R, GAO-16-820 and
  GAO-18-230 are in `library/gao/`. The reconciled 36-question standard with
  provenance is `library/gao/derived/gao-research-standards-master-36.yaml`
  (promoted to `src/docket/standard/research-standards-36.yaml` by plan 02).
- `gao.gov` blocks scripted fetches, but `files.gao.gov/assets/<id>.pdf` works
  with a browser user-agent, and a real headless Chrome session clears the rest.
