# Demonstration A — CBO's 2013 Ground Combat Vehicle study as a docket record

**Source:** Congressional Budget Office, *The Army's Ground Combat Vehicle Program and
Alternatives* (April 2013) — `sources/cbo-2013-04-gcv-program-and-alternatives.pdf`,
public, committed. Page numbers below are the report's printed pages; the PDF page is
five higher, which is what the `#page=` pointers in the record carry.

**Run it:** `uv run python -m demos.a_cbo_gcv_2013.run` → writes `out/`.
**Check it:** `uv run pytest -q tests/demos`.

This is the same decision as OMFV, one generation earlier: what should replace the
Bradley infantry fighting vehicle. It is public, quantitative, and its author showed the
work — which is why it can be reconstructed as a docket record without the proposer
writing both the question and the answer key.

## What it demonstrates

**1. The kernel reproduces CBO's published answer from CBO's published inputs.**
Table 2-2 (p. 21) gives four category scores per vehicle; Table A-3 (p. 35) gives the two
weight sets. Nothing else is used. The kernel's additive aggregation produces:

| vehicle | primary metric | CBO printed | secondary metric | CBO printed |
|---|---|---|---|---|
| German Puma | 45.1 | 45 | 38.25 | 38 |
| Upgraded Bradley | 31.8 | 32 | 25.5 | 25 |
| Notional GCV | 16.4 | 16 | 36.0 | 36 |
| Israeli Namer | 6.1 | 6 | 25.25 | 25 |
| Current Bradley | 0.0 | 0 | 0.0 | 0 |

Both rankings are CBO's, exactly: Puma, upgraded Bradley, GCV, Namer on the primary
metric; Puma, GCV, upgraded Bradley, Namer on the secondary. The differences in the table
are CBO's own rounding to whole percent, and nothing else — the kernel's arithmetic is
exact, and the record says so in its acceptance criterion (`vva-cbo-metric`: reproduce
within one point, reproduce both rankings exactly).

**2. What flips the decision, and by how little.** The record binds CBO's pivotal
assumption — that a full nine-member squad in one vehicle matters (Box 1-1, p. 6) — to
the weight the secondary metric puts on it, and the kernel searches for the point where
the answer changes:

| parameter (secondary metric) | CBO's weight | flips at | distance | result |
|---|---|---|---|---|
| `ws-secondary:m-squad` — the full nine-member squad | 0.25 | 0.266504 | 0.016504 | GCV overtakes the Puma |
| `ws-secondary:m-leth` — lethality | 0.25 | 0.234339 | 0.015661 | GCV overtakes the Puma |
| `ws-secondary:m-mob` — mobility | 0.25 | 0.647059 | 0.397059 | GCV overtakes the Puma |
| `ws-secondary:m-prot` — protection and survivability | 0.25 | 0.791667 | 0.541667 | Namer overtakes the Puma |

Every number in that table is checked against `out/results.json` by
`tests/demos/test_demo_a.py::test_the_readme_flip_table_matches_the_run` — prose that
quotes a computed number has to be pinned to the run that produced it, or it goes stale
in silence.

The Puma wins on **both** of CBO's published metrics. What CBO's second metric does is
bring the answer to within 0.0165 of weight of reversing: raise the weight on the full
squad from 0.25 to 0.2665 and the GCV leads. Note the honest correction here — an earlier
draft of the plan said CBO's two weight sets "straddle" the flip point. They do not: the
primary metric weights passenger capacity 0.10 and the secondary 0.25, and both are below
the 0.2665 the GCV needs. The interesting fact is the smallness of the remaining gap, not
a straddle.

The shortest flip on the secondary metric is not the squad weight but the **lethality**
weight, at 0.2343 — barely shorter (0.0157 against 0.0165). That is worth reading twice:
CBO's answer turns on the Puma's 103 percent lethality advantage almost as tightly as it
turns on the squad, and the Puma's lethality score is an Army analyst's *estimate*, not a
simulation result (p. 20 fn 4).

Across 2,000 random weightings of the four secondary-metric categories, the Puma ranks
first in 52.6 percent, the GCV in 43.75 percent, the Namer in 3.65 percent, and the
upgraded Bradley in none.

**3. Omissions are objects, not footnotes.** Five typed `Exclusion`s carry CBO's own
omissions, each with a reason type, an authority and a date: long-distance
transportability (data unavailable, p. 34 fn 3), four of the Army's eight AoA categories
(assessed differently, Table A-1), combat simulation of the Namer and the Puma (data
unavailable, p. 20 fn 4), threshold and objective values for the measures (not public),
and programmatic risk (assessed differently — CBO reported it qualitatively and combined
it into neither metric, so this record does not score it either). Four more say why a
section of the package or of the VV&A record is empty — mandate elements, the refresh log,
the commitment, and MIL-STD-3022's retained "Issues / Lessons Learned". Nine in all. Three
of the charter's five limitations resolve to a typed exclusion rather than to a sentence.

**4. Gaps are objects too.** Five `InsufficientEvidence` records, each naming what was
sought, where it was looked for, why it was not found, and who confirmed it: the Army's
Milestone A AoA report, the name of the combat simulation model, that simulation's VV&A
record, the size and dates of the soldier ranking behind the weights, and any step taken
to check the Army's squad paper before relying on it.

**5. Reuse past purpose, justified — the mechanism GAO's F1 finding is about.** Three Army
products in this record were built to answer one question and used to answer another, and
CBO said so each time. The scope checker sees all three and records them as `reuse-justified`
rather than blocking:

- the Army analysts' estimates for the Namer and the Puma were built for
  *combat-effectiveness* and support a *requirements-tradeoff* claim (`cl-primary`);
- the soldier ranking was collected to find out which characteristics matter most
  (*desired-characteristics*) and became the weighting of a *requirements-tradeoff*
  (`cl-weights`).

A third, on `cl-squad-rationale`, cites CBO's report for a claim about the Army's
operational concept. Remove any of the three justifications and that edge becomes a
blocking `ReusePastPurpose`.

**6. The record is ready, for reasons you can read — and the scorer still bites.**
`readiness.ready` is `true` with an empty blocker list, five open gaps, six open
exclusions (the three package-section exclusions are printed in their own sections rather
than listed here, because nothing references them), and one class of warning
(`reuse-justified`, which is information, not a complaint). The standards scorer, tailored
to GAO's 21 published questions, returns *generally objective*, *generally valid* and
*generally reliable* — the last of those qualified: **"generally reliable, with concerns:
EXE-5 (only some cited evidence describes its reliability steps)"**. That concern is real,
and it is the record telling the truth about its source: CBO describes no reliability step
for the Army's squad paper, so the record
carries a gap where a step would go, and EXE-5 scores 2 instead of 1. EXE-8 is the other
state 2; every other applicable question is state 1.

**7. It runs the same way twice.** No clock, no network, no environment: `NOW` is
2013-04-30 and `SEED` is 20130430. Two runs produce byte-identical packages, results and
graph store, which the test suite checks by building twice into temporary directories and
comparing bytes.

## The record's own shape

160 objects, 169 log entries. Committed output in `out/`:

| file | what |
|---|---|
| `out/package-full.md` | the full-rendering decision package |
| `out/package-unclassified.md` | the unclassified rendering |
| `out/results.json` | the numbers this README quotes, machine-readable, including both package hashes |
| `out/graph/` | the whole object store with its hash-chained log |

The package hashes are not repeated here on purpose: they are in `out/results.json` and in
the `DecisionPackage` objects in the store, and a hash copied into prose is a hash that
goes stale silently. `tests/demos` rebuilds `out/` and compares bytes, so a stale
committed output fails the suite rather than misleading a reader.

Lifecycle: `DRAFT → MODEL_APPROVED → PLAN_APPROVED → EVALUATED → PENDING_SIGNATURE`. Each
transition records every check the gate ran and who drove it. Nothing was computed before
the model was approved and the plan was approved by a named human — and `evaluate()`
refuses on its own account if either is untrue, so the guarantee does not depend on
anyone remembering to call the gate.

The episode stops at `PENDING_SIGNATURE`. CBO makes no recommendations, by mandate
(p. 37), and no decision was taken in the source document, so there is nothing to sign:
the commitment section prints a typed exclusion saying exactly that.

## The withheld-value demonstration

Every source in this record is public and every classification is `U`, so the two
renderings withhold nothing. They differ only in their header line and in the graph
snapshot recorded on the cover. That is the honest outcome for an all-public
reconstruction, and this README will not pretend otherwise by labelling a public document
as controlled.

The mechanism is still demonstrated, in
`tests/demos/test_demo_a.py::test_unclassified_rendering_withholds_a_classified_value`: it
marks one evidence item CUI in a **throwaway copy** of the graph — never in `out/` — and
checks that the unclassified rendering replaces the values resting on it with
`[withheld: CUI]` while the full rendering prints them. Demonstration B exercises the
withholding path on the real record.

## Where the numbers came from

Every observation value is Table 2-2 (p. 21), as printed. The evidence behind each one is
recorded separately, because it differs by vehicle and by category:

| what | evidence | why |
|---|---|---|
| GCV protection, lethality | `ev-army-sim-2010` | Army combat simulations, Feb–Dec 2010 (pp. 10–11) |
| Namer and Puma protection, lethality | `ev-army-expert-estimates` | technical data were insufficient to simulate them (p. 20 fn 4) |
| Upgraded Bradley protection, lethality | `ev-army-aoa-2011` | the Army's Milestone A analysis (p. 21 source line) |
| all mobility scores | `ev-army-mobility-data` | six weighted automotive attributes (Table A-2, p. 35) |
| passenger capacity, full squad | `ev-cbo-2013` | CBO's own calculation from passenger counts (p. 34) |
| all costs | `ev-cbo-cost-estimate` | CBO's own estimates, not the Army's (pp. 7, 21, 23) |

Where CBO publishes a range it is recorded as a range — but CBO publishes ranges only for
vehicle weight and unit cost, neither of which is a scored measure here. Every scored
value in Table 2-2 is a point, so no observation in this record carries a band, and none
was invented. The scenario-level spread CBO does report (60 percent fewer occupants lost
against unconventional threats; no survivability gain at all in the northeast Asia case,
p. 10) is recorded on the `Scenario` objects, where it is a fact about the simulation
rather than an uncertainty we made up about the composite.

## Honest limits

- **CBO's inputs are published rounded to whole percent.** Reproduction is exact against
  those rounded inputs; it is not a reproduction of CBO's unrounded arithmetic, which is
  not public. A reproduction to within a rounding point could in principle mask a
  different construction that happens to agree at this precision. The VV&A record says so.
- **The Army's files are not public and are not in this record.** The Milestone A AoA
  report, the 2010 simulations, the soldier ranking and the per-vehicle mobility
  attributes are all recorded as evidence with a pointer to the CBO page that *reports*
  their results and a custodian line saying the originals are the Army's. Nothing about
  their contents is asserted beyond what CBO prints.
- **`ev-army-aoa-2011` is marked `reviewed`, and that word is doing less work than it
  looks.** The schema offers only draft / reviewed / rejected. The AoA report was issued
  by Headquarters, Department of the Army to the Armed Services Committees, so `draft`
  would be wrong; but no review record for it has been seen by this project, and the
  reviewer entry says exactly that.
- **Two claims deliberately do not cite the Army files.** `ev-army-aoa-2011`'s pointer is
  a recorded gap, and the scope checker is right that a claim asserting "assessable at U"
  cannot rest on evidence whose metadata nobody outside the Army can see. Those two items
  stay in the register as the evidence behind observations, where the assertion is only
  "CBO reports this number from that source" — which is checkable on CBO's page.
- **Field-level diffs between episode revisions are not tracked in Phase I.** The refresh
  engine records *replacements* (one object superseded by another) and compares judgments
  by claim id, not by content. Demonstration A has no refresh, so this does not bite here;
  it bites in Demonstration B and the package says so where it prints a diff.
- **The record dates itself to the source.** `createdAt` and the episode's `asOf` are
  2013-04-30, so elapsed-time rules (accreditation age, scope validity) read as they would
  have when CBO published. The real transcription date is in
  `ingestionProvenance.extractedAt`.
- **This proves the pipeline, not CBO.** Nothing here checks whether CBO was right. It
  checks that a typed, gated, reproducible record can carry a real published analysis
  without losing anything CBO said, and can say out loud what CBO left out.
