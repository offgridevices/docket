# sources — provenance notes for the public documents Docket cites

Every factual claim in the demonstrations, the research standard and the docs cites
a document here. The repository commits only each document's `.source.md` note: where
it came from, its release status, and what is quoted from it. The documents themselves
are third-party downloads and are not committed (`.gitignore` excludes everything in
this folder but the notes and this README). Fetch a document from the URL in its note —
`scripts/fetch-source.mjs` handles the sites that refuse scripted downloads — and save it
beside its note under the same name.

**Public releases only.** If a document's release status is unclear, do not cite it —
leave a note with the URL, and ask.

Each document gets a sibling `<name>.source.md` recording: the URL it came from,
the date retrieved, the publisher, and its release status.

## Index

| File | What | Cited by |
|---|---|---|
| `gao-23-106549.pdf` | GAO grading of the Army's §234 OMFV report | teardown; Demo B |
| `gao-21-460-tactical-wheeled-vehicles-accessible.pdf` | GAO per-question key (Fig. 6) | validation run |
| `gao-15-548-army-combat-vehicles-industrial-base-study.pdf` | GAO pass on the A.T. Kearney study | positive control |
| `gao-06-938-defense-transportation-mobility-capabilities-study.pdf` | the standard's earliest published form — 36 sub-questions, the 14/15/7 split | the 36-question standard |
| `gao-11-82r-additional-information-is-needed-for-dod-s.pdf` | the 2010 restatement and the four-level rating scale | the 36-question standard; the scorer's legend |
| `gao-15-457r-air-force-s-airlift-study-met-mandate.pdf` | a tailored application of the standard | tailoring-is-the-norm evidence |
| `gao-16-820-dod-needs-further-analysis-of-the-size.pdf` | the 36 questions outside the transportation domain | the 36-question standard |
| `gao-18-230-dod-needs-to-improve-the-accuracy-of.pdf` | a later application with recorded exclusions | tailoring and exclusion evidence |
| `gao-16-86-actions-needed-to-identify-and-sustain-critical.pdf` | cited in the standard's per-question usage notes | the 36-question standard |
| `gao-24-106982-agencies-need-additional-guidance-to-assess-their.pdf` | the most recent product in the corpus | the 36-question standard |
| `cbo-2013-04-gcv-program-and-alternatives.pdf` | CBO GCV alternatives study | Demo A |
| `army-2020-02-25-omfv-characteristics-for-industry-comment.md` | the nine characteristics, verbatim | Demo B ep. 1 |
| `army-2020-04-09-omfv-industry-day-narrative.pdf` | priority order; M&S approach | Demo B ep. 1 |
| `army-2020-12-09-omfv-industry-day-briefing.pdf` | updated CON; seven named efforts | Demo B ep. 2–3 |
| `acc-dta-2022-10-25-omfv-phase-3-4-industry-qa-01-140.pdf` | the Army answering industry in writing | teardown; Demo B |
| `army-rdte-r2-fy2021..fy2027-omfv-xm30-extract.pdf` | budget exhibits | budget-book sub-demo |
| `arxiv-2607-20492-phantomfill.source.md` | schema-forced fabrication in language models (abstract-page stub) | the agent's gap discipline; the schema's `InsufficientEvidence` |

Four entries are sidecar-only, with no file: `gao-23-106059.source.md` (at the
edge of the ~25 MB rule — 24.7 MB, and only two of 259 pages are cited),
`breaking-defense-2020-02-06-polish-bridge-problem.source.md` (copyrighted press
— URL and two quoted sentences only), `arxiv-2607-20492-phantomfill.source.md`
(an author preprint, not redistributed — URL and the one quoted finding only) and
`army-2023-06-26-omfv-phase-3-4-award.source.md` (**release status not confirmed
by retrieval — an outstanding human call**; the award month is sourced from the
FY2025 R-3 exhibit, the day is not).

**Not promoted, and why.** Two documents the research plan expected here are
deliberately absent. The FY2020 Consolidated Appropriations Act joint explanatory
statement (Congressional Record, 17 December 2019, granule
`CREC-2019-12-17-pt2-PgH10613`) is a US Government work and would be promotable, but
the granule itself is not on this machine — only a research note quoting it — so the
appropriations quotation is not used. The OMFV Requirements
Verification Traceability Matrix template (ACC-DTA attachment 0026 to
`W56HZV-20-R-0142`) **must not be promoted**: the workbook's own cells carry
"Distribution Statement: D", "CUI Category(ies): CTI, EXPT, SSEL" and Export Control
and FOUO instructions. It is not public and it does not belong in this repository.
