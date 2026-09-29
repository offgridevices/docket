# Budget books — where the public OMFV/XM30 record contradicts itself

    uv run python -m demos.budget_books.run
    uv run pytest -q tests/demos/test_budget_books.py

Seven annual Army RDT&E R-2 exhibits — President's Budget FY2021 through FY2027 — plus
three published documents, ingested as `Evidence` objects carrying typed, dated,
page-cited assertions. Nothing is scored. Nothing is computed. The only rule this record
exists to exercise is `value_conflicts`.

## What a value conflict is here

One thing — one line item, one date, one definition — stated at two different values.
The kernel keys each assertion on `(subject, field)` and reports when the values behind
one key disagree. It reports two kinds:

- **`value-conflict-internal`** (blocking): one document states two values. That is a
  document contradicting itself.
- **`value-conflict`** (warning): two documents state different values. Budget years
  change; two books disagreeing is normal and interesting, not necessarily an error.

The kernel names every page it read and stops there. It does not decide which figure is
right, and neither does this README.

## The conflicts the kernel found

Full tables, every value with its locator, are in [`out/report.md`](out/report.md);
the machine-readable form is [`out/conflicts.json`](out/conflicts.json). In that file,
read `rows` rather than `message`: the kernel's message lists every page that states the
subject, including pages in other documents, which is right for a cross-document finding
and misleading for an internal one. `rows` is filtered to the documents the finding names.

The two internal conflicts are referred to by subject key throughout, because
`out/report.md` orders them the way the kernel does — by subject key — and a bare "#1"
would point at different things in the two files.

### Within one document — two, both blocking

**`omfv-mta-total-cost-fy21-24.costM` — the same March 2023 book states two totals for
the same effort.**

| Value | Locator |
|---|---|
| $1,348M | PB2024 PE 0603645A R-2/R-2A, volume pp. 2a-99, 2a-101 (extract PDF pp. 60, 61) |
| $1,384M | PB2024 PE 0605625A R-2/R-2A, volume pp. 3d-268, 3d-270 (extract PDF pp. 74, 76) |

PE 0603645A prints "The total cost of the OMFV Middle Tier of Acquisition effort is
$1,348 million RDT&E from FY21 to FY24." PE 0605625A prints "The total cost of the
Optionally Manned Fighting Vehicle Middle Tier of Acquisition effort is $1,384 million
RDT&E from FY2021 to FY2024." Same quantity, same window, same book, both pages headed
`Date: March 2023`. They sit on different program elements — PE 0603645A in Budget
Activity 4, PE 0605625A in Budget Activity 5 — and each figure is repeated on that
element's R-2 and again on its R-2A. Repetition is what makes this the strongest of the
five: it is not one mistyped digit on one sheet.

**`omfv-aoa.window` — PB2021 gives two different windows for the Analysis of
Alternatives.**

| Value | Locator |
|---|---|
| started FY2019 | PB2021 PE 0604100A R-2A, volume p. 451 (extract PDF p. 75) |
| 2Q2020–1Q2021, completion | PB2021 PE 0605625A R-4A, volume p. 506 (extract PDF p. 92); R-2A, volume p. 500 (extract PDF p. 86) |

The Analysis of Alternatives program element lists the OMFV among "several Analyses of
Alternatives started in FY 2019"; the OMFV's own R-4A schedule in the same book runs the
AoA from 2Q FY2020 to 1Q FY2021, and its R-2A funds "completion of the AoA" in FY2021.

This second finding is **reported, not suppressed.** An earlier draft of the plan expected
exactly one internal conflict; there are two, and hiding the second to make the count
match would be the exact failure this product exists to prevent.

### Across documents — six warnings

`omfv-mta-total-cost-fy21-24.costM` ($1,432.1M in PB2023, $1,348M and $1,384M in PB2024,
$1,330M in PB2025) · `omfv-aoa.window` (four recorded windows, three accounts of when it
happened, across four books) · `omfv-phase2-award.date` · `omfv-acdd.quarter` ·
`aries.definition` · `cave.definition`. Every row, with both locators, is in
[`out/report.md`](out/report.md).

### Two subjects the rule read and did not report

`omfv-mta-total-cost-fy21-25` — $1,536M, PB2027 PE 0605625A R-2/R-2A, volume pp. 3d-306,
3d-308 (extract PDF pp. 50, 52). It is a **five-year** window, FY2021–FY2025, not the
four-year FY2021–FY2024 window the other four figures describe, so it lives under its own
subject key and produces no finding. That is the clearest available demonstration that
the subject key is doing real work: a scope difference is not a contradiction, and the
schema is what keeps the two apart.

`omfv-concept-design` — 4Q FY2021 to 1Q FY2023, printed identically in all six books that
carry the row: PB2022 volume p. 463 (extract PDF p. 92), PB2023 p. 2e-268 (p. 84), PB2024
p. 3d-281 (p. 87), PB2025 p. 3d-204 (p. 77), PB2026 p. 3d-339 (p. 74), PB2027 p. 3d-320
(p. 64), every one on PE 0605625A's R-4A.

This one is recorded for the opposite reason to the five-year cost window: it is
uncontested, and it is the Army statement most directly comparable with the award date.
It sits one line below the A-CDD row on sheets the record already cites, and 4Q FY2021 is
July to September 2021 — a window compatible with the July the R-3 exhibits print *and*
with the September GAO gives. The award-date disagreement should be read beside it.

All six are recorded rather than a sample of two, and that is a deliberate discipline
rather than thoroughness for its own sake: every one of these sheets is already in the
record for its A-CDD row, and a record that reads a page for one line and passes over the
line below it is committing the omission this product exists to catch. Six books, one
value, no finding.

## The five facts, in order of strength

Design §9.5 asks for a small number of checkable, public, dated facts a reviewer can
verify from the cited pages. These five are ordered strongest first:

1. **The same-book cost contradiction** ($1,348M vs $1,384M, PB2024, extract PDF pp. 60
   and 74, repeated on 61 and 76). Two program elements, one book, one month, each figure
   printed twice.
2. **The ARIES and CAVE identity change.** In December 2020 ARIES is "performance M&S" and
   CAVE is "Immersive Simulation modeling" (industry-day briefing, PDF p. 18, slide footer
   20); by PB2026 ARIES is the "Augmented Reality Integrated Environment for Situational
   Awareness", a crew display overlay, and CAVE is the "Commanders Aperture Visual
   Enhancement", a 360-degree camera and sensor system (extract PDF p. 65, volume
   p. 3d-330). Same acronyms, different things — a reader tracing the analysis programme
   by name would follow the wrong thread.
3. **The A-CDD quarter carried forward differently for four consecutive years.** PB2022
   and PB2023 schedule the Abbreviated Capability Development Document 1Q–2Q FY2022
   (extract PDF pp. 92 and 84); PB2024 through PB2027 all print 2Q–2Q FY2022 (extract PDF
   pp. 87, 77, 74, 64). GAO's 2023 annual assessment says the Army approved it in July
   2022, which is 4Q FY2022 (GAO-23-106059 printed p. 128).
4. **The Phase 2 award date.** Two Army R-3 exhibits date a **Product Development** award
   July 2021 (extract PDF pp. 89 and 80). GAO-23-106549 says the Army awarded the five
   concept-design contracts in September 2021 (printed p. 5, PDF p. 8). Both are stated;
   neither is called wrong here. Note what the exhibits do *not* say: the R-3 line is
   labelled "Product Development", not "concept design" or "Phase 2", so identifying it
   with the five concept-design awards is this record's inference and not the exhibit's
   words. The Army's own schedule row for that phase — `omfv-concept-design`, 4Q FY2021,
   on the R-4A sheets above — is compatible with both dates.
5. **The Analysis of Alternatives windows.** FY2019 (extract PDF p. 75), 2Q FY2020–1Q
   FY2021 (p. 92, with "completion" funded on p. 86), "formal execution" in FY2023
   (pp. 77 in both PB2023 and PB2024), and "started FY2023, continuing to FY2025"
   (p. 52). Four recorded windows; three accounts of when it happened.

## What this shows, and what it does not

**It shows** that the schema catches internal inconsistency in the public record
mechanically: give the kernel typed assertions with subjects, fields, values and
locators, and it finds the places the record disagrees with itself and names the pages.
No model is in that path. The rule is forty-odd lines of grouping and comparison.

**It does not show automated extraction.** A human read each cited page and chose the
subject keys; the kernel compares only what it is handed, and two pages keyed differently
would produce no finding at all. Every object here carries
`ingestionProvenance.extractor: "human"` for that reason. The mechanical part is the
comparison, not the reading.

**It does not show** that the Army's figures are wrong. Appropriations change between
budget years, and a total restated in a later book is usually a fact about the
appropriation, not an error. R-2 exhibits also contain routine typographical errors, so a
single-page discrepancy is weak evidence on its own — the cases worth anything are the
ones repeated across pages or across years, which is why the PB2024 pair leads and why
each figure's locator names every page it appears on.

**It does not adjudicate.** The kernel reports the disagreement and stops. Deciding which
figure a decision record should rely on is a human's job, and the record's contribution is
that the human is now looking at both figures and both page numbers instead of one.

Two sentences hold the line on the two claims that could most easily be overstated:

> Do not assert the Army failed to do an AoA. Assert only that the public record contains
> three accounts of when the OMFV Analysis of Alternatives happened.

and, for the award date: state the Army record's date and footnote the conflict; do not
assert GAO is wrong.

## Locators are dual, and why

The extract sidecars say "Page numbering is that of the source volumes". So the page
number printed at the bottom of a sheet is a page of the Army's *volume*, not a page of
the committed extract — the extract is a page-exact selection out of several volumes.
Given only one of the two numbers, a reviewer cannot open the right page.

Every locator therefore carries both:

    PB2024 PE 0603645A R-2/R-2A, volume pp. 2a-99, 2a-101 (extract PDF pp. 60, 61)
                                 ^^^^^^^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^^^^^^^^^^
                                 printed in the footer     where to open the file

From FY2023 onward the Army prints the volume page as `Volume 2a - 99`, so the locator
reads `2a-99`. The FY2021 and FY2022 books print a bare number, so the locator reads
`451`. Open `sources/army-rdte-r2-fy2024-omfv-xm30-extract.pdf` at page 60 and the footer
reads `Volume 2a - 99`; the sentence is four lines above it.

The December 2020 industry-day briefing has its own hazard: the slide footers run one or
two ahead of the PDF page index, so its locator reads `PDF p. 18 (slide footer 20)`.

## What this record is not

It is **not a readiness record.** The evidence register holds ten items and no claim cites
any of them, so `silent-omission` fires ten times — once per register entry — and every
one of those findings is blocking. That is correct behaviour and it is the honest state of
this graph: it is an ingestion whose purpose is the conflict rule, not a decision package.
The episode stays in `DRAFT`, no lifecycle gate is driven, `readiness_report` is never
called, and nothing here is signed.

The `Policy` object carries `method: "mavt"` because the catalogue requires a method.
Nothing in this record is evaluated, ranked or aggregated; the field is schema-forced and
means nothing here.

`Evidence.programElement` is a single string in the catalogue, so the two books whose
assertions come from two program elements record them joined —
`"PE 0603645A; PE 0605625A"`. Also schema-forced, also disclosed rather than worked around.

## Provenance and release

| Source | Committed | Release |
|---|---|---|
| Seven R-2 extracts, PB FY2021–FY2027 | yes, `sources/army-rdte-r2-fy20NN-omfv-xm30-extract.pdf` | Public. Every page carries the header `UNCLASSIFIED`; the sidecars record `no-CUI-marking`. Congressional budget justification books are published in full. |
| GAO-23-106549 | yes, `sources/gao-23-106549.pdf` | Public. Report to congressional committees. |
| December 2020 industry-day briefing | yes, `sources/army-2020-12-09-omfv-industry-day-briefing.pdf` | Public. Distribution Statement A on every slide. |
| GAO-23-106059 | **sidecar only**, `sources/gao-23-106059.source.md` | Public. The 24.7 MB PDF is deliberately not committed; the sidecar carries the landing page. |

Every figure in this record was re-read from the committed extract at the page its
locator names. The local research library is not a source and nothing was copied from it.
The one exception is disclosed: GAO-23-106059's page number (printed p. 128, PDF p. 138)
could not come from a committed artefact, because the PDF is deliberately not committed —
it is checkable at the public landing page in the sidecar, and it is the only assertion in
this record whose locator cannot be checked against a file in this repository.

Every classification is `U`, because every source is public.

### One row is missing on purpose

The plan wanted a fifth source on the award date: the SAM.gov notices for the five Phase 2
concept-design awards. No such notice is in hand — the retrieved SAM.gov set has the Phase
2 *solicitation* and the June 2023 Phase 3/4 *awards*, but not the Phase 2 award notices —
so citing them would have meant inventing a notice ID and a URL. The row is left out until
someone retrieves the notices and does the release check. The conflict stands on the three
sourced values without it.

## Reproducibility

`NOW` and `SEED` are constants; nothing reads a clock, the network or the environment, and
no absolute path is written into `out/`. Two runs produce byte-identical output, and
`tests/demos/test_budget_books.py` asserts it.

That property is the kernel's, not a model's. There is no model anywhere in this
demonstration.
