# Demonstration B — OMFV requirements programme, 2020-2023

Measured by `demos/b_omfv_2019_2023/run.py`. Every number here came out of a run; none was chosen in advance.

## GAO's nine verdicts, reproduced

| section | objectivity | validity | reliability |
|---|---|---|---|
| `dc` — the desired characteristics for the OMFV (GAO printed pp. 8-10) | generally_objective | insufficient_to_conclude | insufficient_to_conclude |
| `fs` — force structure designs and operational concepts (GAO printed pp. 10-12) | generally_objective | insufficient_to_conclude | insufficient_to_conclude |
| `ce` — the combat effectiveness of the OMFV concepts compared with the modernized Bradley (GAO printed pp. 13-14) | generally_objective | insufficient_to_conclude | insufficient_to_conclude |

**9 of GAO's 9 verdicts match.**

GAO publishes those nine verdicts **in prose** — three section headings, each with an Objectivity / Validity / Reliability paragraph, printed pp. 8-14 — and **no per-question labels**. Arranging them as a 3x3 grid is ours, and so are the per-question states beneath it.

### What the nine cells rest on

Two scorer decisions taken during this same plan are load-bearing on **objectivity**, and both are named here so the headline number cannot be read as the output of an untouched scorer:

* the narrative-only presentation clauses added to PRE-3 and PRE-4 (`docs/decisions/2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md`) — withdraw them and PRE-3 and PRE-4 both read 4 on all three sections, objectivity falls to `insufficient_to_conclude`, and the measured grid is **6 of 9**;
* `pol-omfv.aggregationK = 21` (`docs/decisions/2026-09-05-aggregation-k-is-a-policy-parameter.md`) — at the kernel default `k = 1` the measured grid is **6 of 9**.

Measured at several values of `k`: k=1 → 6/9; k=3 → 6/9; k=4 → 8/9; k=5 → 9/9; k=21 → 9/9.

**Objectivity is the only dimension either decision reaches.** Validity and reliability read `insufficient_to_conclude` from PRE-1 = 4 and EXE-5 = 4, and both of those come from GAO's own F8 — every cited evidence item's `reliabilitySteps` is the `gap-reliability-steps` object. Six of the nine cells do not move under either counterfactual.

## The nine findings

Seven are detected by a named kernel rule. **F7 and F8 are detected by a rating** — EXE-8 and EXE-5 reaching state 4 — which is not a rule; the `detected_by` column in `findings_matrix.json` says which is which.

| finding | detected | by | on | GAO attributes it to | also fires on | page |
|---|---|---|---|---|---|---|
| F1 | yes | rule | fs | fs | - | printed p. 12 |
| F2 | yes | rule | ce, dc, fs | fs | dc, ce | printed p. 11 |
| F3 | yes | rule | ce | ce | - | printed p. 13 |
| F4 | yes | rule | ce | ce | - | printed p. 14 |
| F5 | yes | rule | ce, dc, fs | dc, fs, ce | - | printed p. 10 |
| F6 | yes | rule | ce, dc, fs | dc | fs, ce | printed p. 9 |
| F7 | yes | rating | ce, dc, fs | dc, fs, ce | - | printed pp. 9-10 |
| F8 | yes | rating | ce, dc, fs | dc, fs, ce | - | printed p. 9 |
| F9 | yes | rule | ce, dc, fs | fs | dc, ce | printed p. 10 |

## The counterfactual repair, in full

| | before | after |
|---|---|---|
| scope finding on `ev-ce-metrics` | `NotAssessableAtLevel` | `assessable-with-classified-value` |
| EXE-14 (`published-21-plus-vva`) | 3 | 1 |
| EXE-5 | 4 | 2 |
| combat-effectiveness row (grid tailoring) | generally_objective / insufficient_to_conclude / insufficient_to_conclude | generally_objective / insufficient_to_conclude / generally_reliable |
| `ev-ce-metrics` classification level | S | S |

Re-scored under the grid tailoring, the repair also moves EXE-5 from 4 to 2 and with it GAO's reliability verdict on the combat-effectiveness section, from `insufficient_to_conclude` to `generally_reliable`. That is the whole of it: one described reliability step on one dataset. Validity does not move, because PRE-1 still reads 4 — every other cited evidence item's `reliabilitySteps` is still the `gap-reliability-steps` object, which is GAO's F8 stated once.

## Readiness

| episode | ready | blocking rules |
|---|---|---|
| `ep-omfv-2020-02` | False | bias-check-missing, linchpin-unevidenced, objective-measured, objective-run-coverage, silent-omission |
| `ep-omfv-2020-02-r2` | False | bias-check-missing, linchpin-unevidenced, objective-measured, objective-run-coverage, silent-omission |
| `ep-omfv-2020-02-r3` | False | bias-check-missing, linchpin-unevidenced, objective-measured, objective-run-coverage, silent-omission |
| `ep-omfv-2020-02-r4` | False | bias-check-missing, linchpin-unevidenced, objective-measured, objective-run-coverage, silent-omission |
| `ep-omfv-2020-02-r5` | False | bias-check-missing, linchpin-unevidenced, objective-measured, objective-run-coverage, silent-omission |
| `ep-omfv-2020-02-r4-dc` | False | bias-check-missing, linchpin-unevidenced, objective-measured, objective-run-coverage, silent-omission |
| `ep-omfv-2020-02-r4-fs` | False | ReusePastPurpose, bias-check-missing, linchpin-unevidenced, objective-measured, objective-run-coverage, silent-omission |
| `ep-omfv-2020-02-r4-ce` | False | NotAssessableAtLevel, bias-check-missing, linchpin-unevidenced, objective-measured, objective-run-coverage, silent-omission |

## Honesty

**There is no evaluation run anywhere in this demonstration.** No number is computed, no ranking is produced, no flip analysis exists. Every question that needs a run (PRE-1, EXE-5's ladder, `objective-run-coverage`) reads accordingly. Nothing here is evidence that the numeric path works — that is Demonstration A's job.

GAO-23-106549 footnote 7, printed p. 9: "We did not independently assess or verify the analytical efforts supporting the report." Appendix I, printed p. 17, says the same. Printed p. 14: "The Army told us that they had no comments on the draft report."

Every one of F1-F9 is therefore a REPRESENTATION failure, not an analysis failure. Nothing in this demonstration says the Army's analysis was wrong, because GAO does not say that, and GAO made no recommendations.

GAO-23-106549 printed p. 14: "The report varies assumptions for each of the vehicles across some of the desired characteristics. Varying such assumptions provides a form of sensitivity analysis, which can provide increased reliability in results. For example, each OMFV concept presents different assumptions for some of its characteristics, such as engines with varying power or variance in the number of infantry soldiers it can transport."

Reproduced: DES-6 rates 2 on the combat-effectiveness section. Do not claim the Army lacked a sensitivity analysis.

Nine section-by-dimension verdicts in prose and nine findings. GAO published NO per-question labels for this report. Any per-question reading of it is OURS and is labelled as such here, in src/docket/standard/tailorings/gao-23-106549.yaml and in src/docket/standard/rules.yaml.

GAO numbers nothing. It writes nine distinct criticisms across pp. 9-14 in prose, and cutting them into nine labelled findings F1-F9 is OUR enumeration. So is arranging GAO's nine section-by-dimension verdicts into a 3x3 grid. A reader who counted eight or ten would not be contradicting GAO.
