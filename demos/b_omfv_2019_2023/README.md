# Demonstration B — the OMFV requirements decision as a programme, 2020–2023

One `DecisionProgram`, five episodes, and the three sections of the Army's March 2023
Section 234 report as three sub-episodes of the fourth. GAO's nine section-by-dimension
verdicts are reproduced on those three sections, and each of GAO's nine findings is
detected on the section GAO attributed it to — seven of them by a named kernel rule and
two (F7, F8) by a per-question rating, which is not a rule.

GAO publishes those nine verdicts **in prose**: three section headings, each followed by
an Objectivity paragraph, a Validity paragraph and a Reliability paragraph, printed
pp. 8–14. Arranging them as a 3×3 grid is *ours*. Figure 3 (printed p. 7) is the standards
figure and carries no verdicts. "The grid" below always means our arrangement of GAO's
nine verdicts, never a table GAO printed.

```
uv run python -m demos.b_omfv_2019_2023.run
uv run pytest -q tests/demos/test_demo_b.py
```

Everything under `out/` is produced by that command and nothing else. Two runs are
byte-identical: every `now` and the seed are constants and no clock, network or
environment variable is read.

---

## 1. The episode chain

The ids are the ones `open_refresh` actually produces — `f"{base}-r{sequence + 1}"`. There
is no `ep-omfv-2020-12`; there is `ep-omfv-2020-02-r2`.

| # | id | opened by | date | source of the refresh | driven to |
|---|---|---|---|---|---|
| 1 | `ep-omfv-2020-02` | `build()` | 2020-02-25 | SAM.gov notice, *OMFV Characteristics For Industry Comment* | MODEL_APPROVED |
| 2 | `ep-omfv-2020-02-r2` | `rt-con-update-2020-12` | 2020-12-09 | Industry Day briefing, PDF p. 5 (slide footer 6) | MODEL_APPROVED |
| 3 | `ep-omfv-2020-02-r3` | `rt-phase2-efforts` | 2021-09-30 | Industry Day briefing, PDF p. 17 (footer 19) and p. 18 (footer 20); GAO printed p. 8 | PLAN_APPROVED |
| 4 | `ep-omfv-2020-02-r4` | `rt-234-report` | 2023-03-31 | the Army's Section 234 report, reconstructed from GAO-23-106549 | PLAN_APPROVED |
| 4a | `ep-omfv-2020-02-r4-dc` | built directly from `-r4` | 2023-03-31 | GAO printed pp. 8–10 — the desired characteristics | PLAN_APPROVED |
| 4b | `ep-omfv-2020-02-r4-fs` | built directly from `-r4` | 2023-03-31 | GAO printed pp. 10–12 — force structure and operational concepts | PLAN_APPROVED |
| 4c | `ep-omfv-2020-02-r4-ce` | built directly from `-r4` | 2023-03-31 | GAO printed pp. 13–14 — combat effectiveness | PLAN_APPROVED |
| 5 | `ep-omfv-2020-02-r5` | `rt-downselect` | 2023-06-26 | PB2025 R-3 exhibit, PE 0605625A / CF6, source-volume page "Volume 3d - 201", extract PDF p. 74 | PLAN_APPROVED |

**Episode 5's date: the month is sourced, the day is not.** The R-3 exhibit prints
`Jun 2023` — a month, with no day. No committed source prints **26** June. GAO-23-106549,
published 27 June 2023, says at printed p. 10 only that the Army "has not yet awarded
contracts for a detailed design, but plans to do so by the third quarter of fiscal year
2023". So `2023-06-26` is a **working date**, held pending the release-status call on
`sources/army-2023-06-26-omfv-phase-3-4-award.source.md` (plan 05 human-only item 4), and
the stub says the same. The chronology argument below does not depend on the day: what it
needs is that the award came *before* GAO's report, and the exhibit's month together with
GAO's 27 June cover date give that. If the day turns out to be a different day in June
2023, episode 5's `asOf` moves within the month and nothing else changes; if it turns out
to be after 27 June, the run order of episode 5 and `rt-gao-grading` swaps, and that would
be a real correction.

**`createdAt` is the episode's clock, not the transcriber's.** Each episode is dated to
the document that opened it, and every object created inside it takes that date — so
objects reconstructed *from* GAO-23-106549 (June 2023) but belonging to the February 2020
episode carry `createdAt: 2020-02-25`: `as-poland-bridges`, `gap-reliability-steps`,
`gap-poland-data`, `gap-def-force-structure`, `gap-def-operational-concepts`. Read
literally, the record says a human authored a 2023-sourced object in 2020. The convention
is deliberate — it makes the elapsed-time predicates (accreditation age, scope validity)
read as they would have at the time — and nothing is misdated in provenance: when each
object was actually transcribed is in `ingestionProvenance.extractedAt`, which reads
`2026-09-06` throughout. A revision moves `createdAt` to the revising episode's date, so
`alt-m2a4-bradley`, revised at the March 2023 episode, reads `2023-03-31`.

Episodes 1 and 2 have **no Plan**, and stop at `MODEL_APPROVED`. The public record at
those dates is a requirements notice and a briefing slide, not an analysis plan, and
inventing one to reach the next gate would be the fabrication this project exists to
refuse. `open_refresh` only refuses a `DRAFT` prior, so `MODEL_APPROVED` is enough.
`open_refresh` does not carry `plan`, `readiness` or `commitment` forward and `Plan.episode`
is a required ref, so **every episode from 3 onwards has its own Plan**.

The three sub-episodes are **not appended to `prg-omfv.episodes`**. If they were,
`_latest_episode` would return the last of them and episode 5 would have been born
`ep-omfv-2020-02-r4-ce-r5`. Each carries `sequence: 4`, `supersedes:
"ep-omfv-2020-02-r4"`, `refreshedBecause: "rt-234-report"` and no `program` field.

**Two triggers are filed and open nothing.**

* `rt-sigmgmt-correction`, 25 October 2022 — ACC-DTA Q&A control no. 021, PDF p. 5.
  Attachment 0010 showed the signature-management requirements at P3 while *"the latest
  rev of the requirements has these at P2"*, and the Government response was
  *"Attachment 0010 will be corrected to reflect signature management requirement P2 in
  column F."* That is a document correction aligning an attachment with a revision that
  already carried P2. It is **not** a dated Army decision to re-prioritise signature
  management, and this record does not assert one. It is also dated five months *before*
  the Section 234 report, not after the June 2023 downselect. There is no
  `obj-signature-management` either: signature management is a clause inside the
  Survivability characteristic in both the February and December CON texts, so the trigger
  is filed against `obj-survivability-dec`.
* `rt-gao-grading`, 27 June 2023 — GAO-23-106549 itself. Its `affected` list names the
  three Claims, not the three episodes, because `RefreshTrigger.affected` is typed
  `ref: [Claim, Assumption, Evidence, Objective, Model, Alternative]`.

---

## 2. The finding-detection matrix

Measured by `run.py` and written to `out/findings_matrix.json`. GAO's own attribution of
each finding to a section is transcribed in `gao_23_106549_ground_truth.yaml`, under
`transcribed:`; the mechanisms and object ids in the table below are under `ours:`.

**Seven of the nine are detected by a named kernel rule. Two are not.** F7 and F8 are
detected by a **rating** — EXE-8 and EXE-5 reaching state 4 — which is a question's score,
not a rule. The `detected_by` field in `findings_matrix.json` and the "by" column of
`out/report.md` say which is which, and the table below marks them.

| finding | detecting mechanism | kind | object | GAO attributes it to | also fires on | GAO page |
|---|---|---|---|---|---|---|
| F1 | `ReusePastPurpose` ×2, and EXE-3 state 3 via `model_evidence_reuse_past_purpose` | rule | `ev-trac-aoa`, `ev-mbl-1` on `cl-force-structure-improves` | `fs` | — | printed p. 12 |
| F2 | `silent-omission` | rule | `ev-trac-oe` | `fs` | **`dc`, `ce`** | printed p. 11 |
| F3 | `inclusion-reason-missing` ×3, and a computed `bias-selection` Risk | rule | `ev-bradley-swapc-2018`, `ev-market-research-study-2020`, `ev-concept-design-2021` | `ce` | — | printed p. 13 |
| F4 | `NotAssessableAtLevel` | rule | `ev-ce-metrics` on `cl-concepts-outperform-m2a4` | `ce` | — | printed p. 14 |
| F5 | `vva-verbal` ×2, and EXE-14 state 3 under `published-21-plus-vva` | rule | `vva-aries`, `vva-trac` | `dc`, `fs`, `ce` | — | printed p. 10 |
| F6 | `linchpin-unevidenced` | rule | `as-poland-bridges` | `dc` | **`fs`, `ce`** | printed p. 9 |
| F7 | EXE-8 state 4 | **rating** | `gap-model-docs` | `dc`, `fs`, `ce` | — | printed pp. 9–10 |
| F8 | EXE-5 state 4 | **rating** | `gap-reliability-steps` | `dc`, `fs`, `ce` | — | printed p. 9 |
| F9 | `definition-missing` ×2 | rule | `ch-omfv` — "force structure", "operational concepts" | `fs` | **`dc`, `ce`** | printed p. 10 |

**"F1–F9 all detected" is only honest next to the false positives.** Three findings fire
on sections GAO did not attribute them to:

| rule | cross-fires on | why |
|---|---|---|
| `definition-missing` | `dc`, `ce` | the three sections are three parts of one report and share one Charter |
| `silent-omission` | `dc`, `ce` | they share one evidence register, so `ev-trac-oe` is uncited in all three |
| `linchpin-unevidenced` | `fs`, `ce` | they share one assumption list, so `as-poland-bridges` is unevidenced in all three |

That is not a defect in the rules. It is what happens when one document is graded section
by section and the sections are not independent records — which is exactly what GAO did.
The matrix records the cross-fires rather than filtering them out.

**That table is the list after one correction of ours, and the size of the correction is
measured.** `readiness_report` keeps a finding for an episode if the finding names
*anything* that episode can reach, and all three sections share one evidence register — so
the kernel's own scoping puts `inclusion-reason-missing` (F3's rule) on `dc` and `fs` as
well, three spurious firings each. Our attribution rule reads the episode the finding
names and gives it only to the section whose claim did the citing, which is right. But the
cross-fire table would otherwise read as the complete list of what over-fires when it is
the list after we removed one. `findings_matrix.json` therefore carries
`cross_fires_suppressed_by_our_attribution`, computed on every run by scoring the same
findings both ways; it currently reads `{"inclusion-reason-missing": ["dc", "fs"]}`.

**The shared register is load-bearing, not merely convenient.** It is what puts F2 on `fs`
at all. GAO says the force-structure observations "rely on two of the 11 analytical
efforts" (printed p. 11); a section-scoped register would have left `ev-trac-oe` out of
`fs` entirely, and F2 would have missed GAO's own attribution. Modelling the register as
the report's rather than the section's is defensible — it *is* one report — but it is a
modelling choice that earns a detection, and saying so is stronger than leaving a reviewer
to find it.

**Earlier-episode `silent-omission` counts.** Episodes 1–5 have no claims at all, so every
entry in their evidence register is an uncited omission and the rule fires on each one.
Measured: 3, 7, 21, 21, 21 for episodes 1 to 5. That is the rule working as designed on a
record that has not yet drawn conclusions, not five more findings about the Army.

### Attribution is ours

Kernel findings are graph-global: `validate()` runs over the whole store, and
`readiness_report` keeps any finding naming an object the episode can reach — and because
every episode references its programme, and the programme references every episode,
"reachable" is very nearly "everything". `run.py` therefore decides for itself which
episode owns a finding, from the episode's own reference lists (`_attributable`). The same
applies to `affected_episodes(g, "rt-gao-grading")`: reverse reachability is transitive
and the trigger is filed on the programme, so the raw answer is all eight episodes.
`out/affected_by_gao.json` prints the raw set **and** the three graded sections, and says
which is the kernel's and which is ours.

---

## 3. GAO's nine verdicts, and what our nine cells rest on

| section | objectivity | validity | reliability |
|---|---|---|---|
| desired characteristics (`dc`) | generally objective | insufficient to conclude | insufficient to conclude |
| force structure / operational concepts (`fs`) | generally objective | insufficient to conclude | insufficient to conclude |
| combat effectiveness (`ce`) | generally objective | insufficient to conclude | insufficient to conclude |

**9 of GAO's 9 verdicts match** (`out/grid.json`).

GAO published **nine verdicts in prose and nine findings, and no per-question labels**.
The twenty-one per-question states underneath (`out/results.json`, `states`) are **ours**,
produced by the `gao-23-106549` tailoring, which carries that warning in its own header.
Arranging the nine verdicts as a grid is ours too; the verdicts are GAO's, and they are
the only thing compared cell for cell.

### What the nine cells rest on

Nine of nine is **not** reachable at an untouched scorer. Two decisions taken during this
same plan are load-bearing, both are on the human sign-off list, and both are named here
rather than left for a reviewer to find in the commit log.

| decision | where | withdraw it and the measured grid is |
|---|---|---|
| PRE-3 gains `{when: claims_exist_no_silence, state: 2}` and PRE-4 gains `{when: claims_exist, state: 2}` (ruling R2, commit `5ca1686`) | [`docs/decisions/2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md`](../../docs/decisions/2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md) | **6 of 9** — PRE-3 and PRE-4 both read 4 on all three sections and objectivity falls to `insufficient_to_conclude` |
| `pol-omfv.aggregationK = 21` instead of the kernel default 1 (ruling R3) | [`docs/decisions/2026-09-05-aggregation-k-is-a-policy-parameter.md`](../../docs/decisions/2026-09-05-aggregation-k-is-a-policy-parameter.md) | **6 of 9** at `k = 1` |

Both numbers are **measured on every run**, not written down here once: `run.py` re-scores
the record on a throwaway copy of the store with each decision withdrawn and writes the
result to `out/grid.json` (`counterfactuals`) and `out/report.md`. Both probes are also
pinned as tests in `tests/demos/test_demo_b.py`. Measured across the aggregation dial:

| `k` | 1 | 3 | 4 | 5 | 21 |
|---|---|---|---|---|---|
| cells matching | 6 | 6 | 8 | 9 | 9 |

**Objectivity is the only dimension either decision reaches, and that is the stronger
story.** Validity and reliability read `insufficient to conclude` on all three sections
because **PRE-1 = 4 and EXE-5 = 4**, and both of those come from GAO's own F8: every cited
evidence item's `reliabilitySteps` is the `gap-reliability-steps` object, so
`claims_all_supported` cannot pass and no dial moves it. **Six of the nine cells are
immovable under either counterfactual.** What R2 and `k` buy is the three objectivity
cells; what GAO's F8 holds is the other six.

`pol-omfv` quotes GAO's own aggregation sentence in its `name`: *"we drew conclusions that
the report was generally objective when available information presented in the report was
consistent with our definition of objectivity but was missing information that would have
addressed the generally accepted research standards"* (printed p. 17, PDF p. 20). With
`k = 21`, `generally_X` holds unless a mapped question is at state 3 or 4 — which is what
that sentence describes. That is the argument for the value; the table above is what
happens without it.

**"No silence" beside F2 is not a contradiction.** PRE-2 and PRE-3 reach state 2 through
`claims_exist_no_silence`, and the `silence` that predicate reads is the **structural**
rule in `validate.py` — "every required slot holds content, an Exclusion or a recorded
gap" — not the policy rule `silent-omission`, which is about evidence no claim cites.
These sections carry 16–19 `silent-omission` findings each and no `silence` finding at
all, and both statements are true at once: every slot is filled or gapped, and much of the
register is uncited.

---

## 4. The counterfactual repair

`out/counterfactual/` holds a **separate store**. The repair never runs against the main
graph, every object it writes is `confidence: "inferred"`, and every one carries an
`ingestionProvenance` whose `sourceArtifact` is this file (`#counterfactual-repair`), so
nothing in it can be mistaken for the record. New objects are prefixed `cf-`; the three
objects it *revises* keep their ids, because a revision cannot be renamed — they are
identified by that same counterfactual provenance instead.

`out/ce-before.json`, `out/ce-after.json` and `out/repair.json`:

| | before | after |
|---|---|---|
| scope finding on `ev-ce-metrics` | `NotAssessableAtLevel` | `assessable-with-classified-value` |
| EXE-14 (`published-21-plus-vva`) | 3 | 1 |
| **EXE-5** | **4** | **2** |
| **combat-effectiveness row, re-scored under the grid tailoring** | generally objective / insufficient to conclude / **insufficient to conclude** | generally objective / insufficient to conclude / **generally reliable** |
| `ev-ce-metrics` classification level | **S** | **S** |

**The third row is the interesting one, and an earlier version of this file did not
report it.** `cf-drs-ce-metrics` gives `ev-ce-metrics` a content `reliabilitySteps`, which
is exactly the silence GAO found in F8, so EXE-5 rises from 4 to 2 — and re-scored under
the grid tailoring that flips GAO's **reliability** verdict on this section from
"insufficient to conclude" to "generally reliable". That is a larger claim than "a pointer
makes a withheld dataset locatable", and a better demonstration: **one described
reliability step on one dataset moves a GAO cell.** It is also strictly bounded. Validity
does not move, because PRE-1 still reads 4 — every *other* cited evidence item's
`reliabilitySteps` is still the `gap-reliability-steps` object, which is F8 stated once
rather than eight times. And the repaired step is a counterfactual object: no such step is
described in any public record.

**This says what the record would have to contain. It says nothing about what the Army
did.** The classification level stays `S` throughout: the value is still withheld, and
that is the point — the scope finding was never "the metrics are classified", it was "the
record gives no way to locate them".

Two things the repair had to do that are worth naming, because both were measured rather
than assumed:

* `assessable-with-classified-value` needs `_metadata_missing` to come back **empty** — a
  content `pointer` *and* a content `scopeOfValidity` *and* `reviewStatus != "draft"`. A
  pointer alone is not enough.
* `vva_signed` is `_all(models, …)`: it asks every Model on the episode. So **both**
  `vva-aries` and `vva-trac` are repaired, each to `basis: "document"` with a real
  `document` ref, an `authority` and a `date`. A `document` basis with no document ref
  scores 4, not 1.

F7 is *not* repaired: the VV&A sections stay gapped, so EXE-8 stays at 4.

---

## 5. Diff semantics

Repeating plan 03b's ruling, because it governs everything in `out/diffs.json`:
**field-level diffs are not tracked in Phase I; only replacements.**

* `changed[]` is paired from the new episode's `replacements` map — never by sorting
  `added` and `removed` and zipping them. `pairing` says which happened:
  `"replacements"` at episode 2 (three pairs) and episode 5 (one pair), `"unknown"` at
  episodes 3 and 4, where nothing was replaced and no pairing was attempted.
* An object retained under the same id reads as unchanged even if its content was revised
  in between. The seven unchanged characteristics at episode 2 appear in neither `added`
  nor `removed`, and that absence is how the artefact records "retained".
* `judgmentsConsistent` is `[]` in every diff here. It is `sorted(claims_a & claims_b)`,
  and no main-chain episode has claims — the claims live on the three sub-episodes, which
  are not part of the chain and are not diffed against each other.
* `replacements` is **1:1**. Episode 5 splits one alternative into two, and that is
  recorded as one replacement (`alt-omfv-concept → alt-xm30-gdls`) plus one addition
  (`alt-xm30-rheinmetall`), not as a faked second map entry.
* Every diff shows one `risk-bias-…-selection` object **removed** and the successor's own
  **added**. That is the refresh engine no longer carrying computed bias indicators
  forward: a bias indicator the kernel computed for episode *N* is a conclusion about
  episode *N*, and the successor recomputes its own (`refresh.is_computed_bias_risk`).
  Before that fix, `ep-omfv-2020-02-r4-ce.risks` held five inherited indicators, one per
  prior episode, and any consumer reading `episode.risks` would have attributed 2020 bias
  readings to a 2023 section. Risks a *human* recorded still carry forward.

---

## 6. `ready` is false for every episode

Not one of the eight is ready, and that is the finding rather than a bug. The blocking
rules, measured:

| rule | why |
|---|---|
| `bias-check-missing` | `pol-omfv` requires an `independent-disconfirming-review` and the public record contains none. GAO credits the Army's use of three kinds of source for **objectivity** (printed p. 9) — that is not an independent disconfirming review, and manufacturing a `BiasCheck` out of the four vendor feedback events would be a fabrication in the demonstration the technical volume leans on. |
| `objective-measured` ×8 | The record names nine desired characteristics and publishes a metric for exactly one. The Army's 28 prioritized attributes are not public (printed p. 8), and `Measure.metric.units`/`direction` are required fields with no slot, so inventing metrics for the other eight is the one thing this record may not do. |
| `linchpin-unevidenced` | F6 — `as-poland-bridges`. |
| `silent-omission` | F2 on `ev-trac-oe`, plus every other register entry no claim cites. |
| `NotAssessableAtLevel` | F4 — `ev-ce-metrics`, on the combat-effectiveness section only. |
| `ReusePastPurpose` | F1, on the force-structure section only. |
| `objective-run-coverage` | No evaluation run scored the one measure the record has. There are no runs at all: this is a narrative record, not a computed one. |

`pol-omfv.requireAllLinchpinsVaried` is **false**, deliberately. The `linchpin-not-varied`
rule fires only where a sealed run exists, and this record has none — so setting it true
would demand of the Army a sensitivity analysis GAO did not ask for and would sit badly
beside the credit GAO *did* give (§7 below).

---

## 7. Honesty

**The Section 234 report is a reconstruction.** It is not public and never was — it is a
report to the congressional defense committees. Everything this record holds about March
2023 is what GAO-23-106549 reports about it, with the GAO page that reports it.
`ev-234-report` has a gapped pointer, is covered by a typed Exclusion, and is cited by no
Claim.

**GAO did not assess or verify the Army's underlying analytical work.** Footnote 7, printed
p. 9: *"We did not independently assess or verify the analytical efforts supporting the
report."* Appendix I, printed p. 17, says the same. Every one of F1–F9 is a
**representation** failure, not an analysis failure. Nothing in this demonstration says the
Army's analysis was wrong, because GAO does not say that.

**The Army had no comments on the draft and GAO made no recommendations** (printed p. 14).

**GAO credited the sensitivity analysis.** Printed p. 14: *"The report varies assumptions
for each of the vehicles across some of the desired characteristics. Varying such
assumptions provides a form of sensitivity analysis, which can provide increased
reliability in results. For example, each OMFV concept presents different assumptions for
some of its characteristics, such as engines with varying power or variance in the number
of infantry soldiers it can transport."* That credit is reproduced: DES-6 rates **2** on
the combat-effectiveness section. This record does **not** claim the Army lacked a
sensitivity analysis.

**GAO published nine verdicts in prose and nine findings, not per-question labels, and
not a grid.** The 3×3 arrangement is ours, the cut into nine findings is our enumeration
(GAO numbers nothing), and the per-question layer is ours — labelled as ours here, in
`src/docket/standard/tailorings/gao-23-106549.yaml` and in `src/docket/standard/rules.yaml`.

**Five identifications of GAO-named studies are ours, and all five are marked
`inferred`.** GAO names two TRAC studies (printed p. 11: *"a September 2021 study
conducted by the Army's Research and Analysis Center (TRAC)"* and *"a second TRAC study
expanded on the first"*). The December 2020 Phase 2 schedule has two TRAC line items,
`TRAC AoA` and `TRAC OE`. **Mapping one pair onto the other is ours in both directions,
and the record does not settle it.** Column positions read off the deck with
`pdftotext -layout` (PDF p. 17, slide footer 19), against that page's own month header
row:

| schedule item | text column | nearest month on the header row |
|---|---|---|
| `TRAC AoA` | 19 | Nov 2020 |
| `ARIES 1` | 43 | Feb 2021 |
| `MBL1` | 55 | Apr 2021 |
| `TRAC OE` | 83 | Sep 2021 |
| `HSI 1` / `HSI 2` | 117 | Feb 2022 |

Those are label positions on a Gantt row, so they locate a bar approximately, not a start
date. But they point the *other* way from this record's reading: GAO's September 2021
study is `ev-trac-aoa` here, and the schedule puts `TRAC AoA` around November 2020 and
`TRAC OE` around September 2021. Likewise GAO's July 2021 Maneuver Battle Lab touchpoint
is `ev-mbl-1`, and the schedule puts `MBL1` around April 2021. `MBL1` is at least the only
Maneuver Battle Lab item on the deck; `HSI 1` and `HSI 2` are mapped onto the JACK and
CAVE activities by us, and slide footer 20 lists six MS&A activities against seven
timeline items and never makes that mapping itself.

Nothing here changes a rating — `ReusePastPurpose` fires from the `questionClass`
mismatch and `silent-omission` from the uncited register entry, whichever study is which —
but if a reviewer reverses the two TRAC studies, F1's and F2's objects swap. So
`ev-trac-aoa`, `ev-trac-oe`, `ev-mbl-1`, `ev-hsi-1` and `ev-hsi-2` are all
`confidence: "inferred"` and each says why in its own `title` and `inclusionReason`.
`ev-trac-aoa.model` is a **gap** (`gap-trac-aoa-model`) rather than `mdl-trac`: recording
the model would have asserted that GAO's September 2021 study ran on the model the deck
calls TRAC OE, which no source says.

**`ev-trac-oe` in particular is our inference.** GAO says only that *"a second TRAC study
expanded on the first, and added another scenario with different terrain and details from
a vendor's concepts"* (printed p. 11) and never names it. Identifying it with the "TRAC
OE" entry on the December 2020 Phase 2 schedule is ours.

**Seven of GAO's eleven analytical efforts are in this record; four are named nowhere
public.** GAO counts *"seven previously conducted analytical studies"* and four soldier
touchpoints (printed p. 8). The December 2020 schedule names seven of the eleven — ARIES
1, ARIES 2, TRAC AoA, TRAC OE, MBL1, HSI 1, HSI 2 — and those seven are what the record
holds (four `MSStudy`, three `SoldierTouchpoint`). The other four are recorded as the gap
`gap-unnamed-efforts`, hung on a `ch-omfv` limitation, rather than invented.

**`cl-weight-threshold` cites the February notice as well as the trade press.** An earlier
revision cited only the Breaking Defense article, on the stated ground that citing the CON
would hide F6 behind a citation that does not answer it. That reason is mechanically
false: `linchpin-unevidenced` reads the Assumption's own `evidence` field, never the
Claim's `supportedBy`. Measured, adding the CON leaves every `dc` state identical and F6
still fires on `as-poland-bridges`. Recording an Army requirements claim as resting on
trade press and nothing else would have been a false statement about the record.

**The second TRAC study's omission is the *report's*, not "the Army's".** Army officials
did give a reason, in interview: *"observations from this study were not included due to
security concerns"* (printed p. 11). What is missing is the reason **in the report**.

**Signature management P3 → P2 is an attachment correction**, dated October 2022, not a
re-prioritisation decision and not after the downselect. See §1.

**Schema-forced fields, disclosed.** Four places where the catalogue requires a value the
record does not have and offers no gap slot:

* `Policy.method` — the enum offers `mavt`/`ahp`/`topsis`/`pugh` and has no value for a
  requirements-refinement process that computes nothing. `mavt` is recorded; no MAVT
  aggregation is ever run here.
* `Model.definition.version` — no version was ever published for ARIES or TRAC OE. The
  string reads "unversioned in the public record".
* `Measure.metric.units` and `direction` on `m-weight-bridges` — read off the Weight
  characteristic's own sentence, which is the only reason that measure exists at all.
* `WeightSet.weights` — the equal weighting is **ours**. The Army published a priority
  *order*, never weights; `ws-omfv.provenance` is the gap `gap-weights` and the object is
  `confidence: "inferred"`.

**`confidence` is an object-level envelope field**, so one reconstructed sentence marks a
whole object `inferred`. `ch-omfv` is inferred because its `consequencesOfErroneousOutput`
paragraph is ours, even though its scope list is verbatim. That is coarser than one would
like and there is no finer instrument in this schema.

**`Objective.provenance` is a single ref.** Each of the nine characteristics points at the
notice it was published in. It cannot *also* point at the threat analysis, the market
research and the ABCT operational concept the December slide names as the CON's inputs;
those are in the evidence register and cited by `cl-nine-characteristics` instead. The
schema does not support two provenances and this record does not work around it.

**One source is a stub with an open release call, and the award *day* rests on it.**
`sources/army-2023-06-26-omfv-phase-3-4-award.source.md` records the June 2023 press
release; nothing is quoted from it and its release status is a human decision that has not
been made. The two facts episode 5 needs — the June 2023 award and the two performers —
come instead from a committed, already-verified public budget exhibit
(`sources/army-rdte-r2-fy2025-omfv-xm30-extract.pdf`, Exhibit R-3, PE 0605625A / Project
CF6, source-volume page "Volume 3d - 201", extract PDF p. 74). That exhibit prints the
month, **`Jun 2023`**, and no day; **26 June is a working date, not a sourced one** (see
§1). The **unselected** Phase 2 vendors are named nowhere:
`ex-phase2-concepts-not-selected` records them by label only, with no `id`, because naming
them would need a source this project does not hold.

---

## 8. What this demonstration does not show

There is no evaluation run anywhere in it. No number is computed, no ranking is produced,
no flip analysis exists. The OMFV requirements chain is a narrative record and this is a
faithful reconstruction of one; the arithmetic path is Demonstration A's job. What is
demonstrated here is the refresh machinery, the diff artefact, and mechanical detection of
the nine things GAO found wrong with how one report described its own analysis.
