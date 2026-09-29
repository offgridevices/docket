# GAO-15-548 positive control — run report

Source: `sources/gao-15-548-army-combat-vehicles-industrial-base-study.pdf` (printed page + 3 = PDF page).
Tailoring `gao-15-548`, kernel 0.1.0, seed 15548, asOf/now `2014-04-30T00:00:00Z`, aggregation k = 21.

> Every per-question state and every dimension verdict below is OURS. GAO-15-548 published neither: printed p. 24 (PDF p. 27), "we determined that qualitative assessment ratings provide the best explanation of the nuances of the analysis and findings, rather than numeric ratings for each individual standard." The objectivity/validity/reliability frame comes from Section 234(d) of the FY2022 NDAA by way of GAO-23-106549, not from GAO-15-548.

GAO's own published verdict, printed p. 7: the Army's combat vehicle industrial base study's approach — "including its design, execution, and presentation of results — was both reasonable and sound for its intended purposes". GAO assessed the reasonableness of the study's *methods* (printed p. 2); it did not assess or verify the study's underlying analytical work, and neither does this record.

## Dimension verdicts (ours)

| dimension | verdict | qualifier |
|---|---|---|
| objectivity | `generally_objective` | generally objective, with concerns: DES-4 (assumptions are listed without rationale); PRE-3 (claims are presented but no evaluation run exists in the record); PRE-4 (claims are backed by evidence but not tied to a run's sealed results) |
| validity | `generally_valid` | generally valid, with concerns: PRE-1 (claims are backed by evidence but not tied to a run's sealed results); PRE-3 (claims are presented but no evaluation run exists in the record) |
| reliability | `generally_reliable` | generally reliable, with concerns: DES-6 (sensitivity covered some assumptions); PRE-3 (claims are presented but no evaluation run exists in the record) |

## Per-question states (ours)

| question | band | state | firing clause | question |
|---|---|---|---|---|
| DES-1 | design | 1 | `charter_complete_and_plan_approved→1` | Is the study's design clear? |
| DES-2 | design | 1 | `charter_question_and_terms_defined→1` | Is the study's objective clearly stated? |
| DES-3 | design | 1 | `scope_defined_and_terms_defined→1` | Is the study's scope clearly defined? |
| DES-4 | design | 2 | `assumptions_listed→2` | Are the assumptions explicitly identified? |
| DES-5 | design | 1 | `assumptions_all_evidenced_and_consistent→1` | Are the assumptions reasonable and consistent? |
| DES-6 | design | 2 | `any_assumption_varied→2` | Are the assumptions varied to allow for sensitivity analyses? |
| DES-7 | design | 1 | `constraints_discussed→1` | Are major constraints identified and discussed? |
| DES-8 | design | 1 | `scenarios_have_rationale→1` | Are the scenarios that were modeled reasonable ones to consider? |
| DES-9 | design | 1 | `scenarios_cover_conditions→1` | Do the scenarios represent a reasonably complete range of conditions? |
| DES-10 | design | — | `tailored-out` | Was the study plan followed? |
| DES-11 | design | — | `tailored-out` | Were deviations from the study plan explained and documented? |
| DES-12 | design | — | `tailored-out` | Do the study scope, methodology, and objectives fully address the study charter and associated guidance? |
| DES-13 | design | — | `tailored-out` | Are the limitations explicitly identified? |
| DES-14 | design | — | `tailored-out` | Do the assumptions support a sound, objective, and balanced analysis? |
| EXE-1 | execution | 1 | `methodology_covers_objectives→1` | Is the study's methodology consistent with the study objective? |
| EXE-2 | execution | 1 | `objectives_addressed→1` | Are the study's objectives addressed? |
| EXE-3 | execution | 1 | `models_scope_ok→1` | Were the models used to support the analyses appropriate for their intended purpose? |
| EXE-4 | execution | 1 | `data_scope_all_known→1` | Were the data used valid for the study's purposes? |
| EXE-5 | execution | 1 | `reliability_all→1` | Were the data used sufficiently reliable for the study's purposes? |
| EXE-6 | execution | 1 | `limitations_all_explained→1` | Were any data limitations identified and were the impact of the limitations adequately explained? |
| EXE-7 | execution | 1 | `ms_limitations_all_justified→1` | Were any modeling and simulation limitations identified, explained, and justified? |
| EXE-8 | execution | 2 | `models_documented_na_reasoned→2` | Have the models used in the study been described and documented adequately? |
| EXE-9 | execution | — | `tailored-out` | Was the study methodology executed consistent with the study plan and schedule? |
| EXE-10 | execution | — | `tailored-out` | Were the model input data properly generated to support the methodology? |
| EXE-11 | execution | — | `tailored-out` | Is the analytical baseline fully and completely identified and used consistently throughout the study for the various analyses? |
| EXE-12 | execution | — | `tailored-out` | Were the baseline data verified and validated? |
| EXE-13 | execution | — | `tailored-out` | Was the data verification and validation process documented? |
| EXE-14 | execution | — | `tailored-out` | Was a verification, validation, and accreditation (VV&A) report that addresses the models and data certification signed by the study director and included in the report? |
| EXE-15 | execution | — | `tailored-out` | Are the measures of effectiveness (MOEs) and essential elements of analysis (EEAs) addressed, and do they adhere to the guidance in the study terms of reference? |
| PRE-1 | presentation | 2 | `claims_all_supported→2` | Do the results of the modeling support the report findings? |
| PRE-2 | presentation | 1 | `claims_exist_no_silence_no_blocking_gaps→1` | Does the report present an assessment that is well documented? |
| PRE-3 | presentation | 2 | `claims_exist_no_silence→2` | Are the conclusions sound? |
| PRE-4 | presentation | 2 | `claims_all_supported→2` | Are the study results presented in the report in a clear manner? |
| PRE-5 | presentation | — | `tailored-out` | Are recommendations supported by analyses? |
| PRE-6 | presentation | — | `tailored-out` | Is a realistic range of options provided? |
| PRE-7 | presentation | — | `tailored-out` | Are study participants/stakeholders informed of the study results and recommendations? |

Applicable questions: 21 of 36. States present among them: [1, 2].

## Readiness

`ready`: **False**.

| blocker | objects | why |
|---|---|---|
| `objective-run-coverage` | obj-viability | no evaluation run on this episode scored any measure of this primary objective, so the record does not answer it (design §7.1) |

Warnings raised: none.
Open gaps: `gap-criteria`, `gap-kearney-report`, `gap-msr-derivation`, `gap-risk-perspective-rationale`, `gap-weights`.
Open exclusions: `ex-vva-na`.

## Agreement with the measurement target

Measured against demos/control_gao_15_548/expected.yaml — OUR measurement target, recorded from a run of this file; GAO published no per-question key.

- label agreement (`assessed` / `unable_to_assess`): **1.000** over 21 shared questions
- exact-state agreement: **1.000**
- majority baseline on the target labels: 1.000
- Cohen's kappa: 0.000 — the target carries one label only, so kappa is undefined in substance and reads 0.0; it carries no information here

Disagreements: none.

This is a regression check on the fixture, not a comparison against GAO. GAO-15-548 published no per-question ratings (printed p. 24), so there is no external key for this case; the only external comparison available is against GAO's published qualitative verdict, quoted above.
