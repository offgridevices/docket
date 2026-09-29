# OMFV (XM30) Phase 3/4 contract awards, 26 June 2023 — STUB, file not committed

| | |
|---|---|
| Title | Army awards of the OMFV Phase 3 / Phase 4 (Detailed Design, Prototype Build and Test) contracts |
| Publisher | Department of the Army / Department of War (press release and daily contract announcement) |
| Published | June 2023. **Month sourced, day NOT sourced** — see "The date" below. |
| Landing page | https://www.defense.gov/News/Contracts/ (the daily contract announcement for 26 June 2023) |
| Direct file | **not retrieved.** The exact article URL for the 26 June 2023 announcement has not been opened by this project and is deliberately not guessed. |
| Release status | **Believed a public press release. NOT CONFIRMED by retrieval.** Human release-status call outstanding (plan 05 human-only item 4). |
| Retrieved | not retrieved as of 2026-09-06 |

**Why this stub exists.** `demos/b_omfv_2019_2023` records a June 2023 refresh of the
OMFV requirements episode. CLAUDE.md: *"If a document's release status is unclear, do not
commit it — write a stub in `sources/` with the URL and ask."* Nothing is committed here
and no text is quoted from the release.

**What the demonstration actually relies on, and where it is already sourced.** The two
facts the demonstration needs — that Phase 3/4 product development was awarded in
**June 2023**, and that the performers are **General Dynamics Land Systems** and
**American Rheinmetall Vehicles** — are both printed in a source this repository has
already committed and verified:

> `sources/army-rdte-r2-fy2025-omfv-xm30-extract.pdf`, Exhibit R-3 (RDT&E Project Cost
> Analysis, PB 2025 Army), PE 0605625A *Manned Ground Vehicle* / Project CF6 *Optionally
> Manned Fighting Vehicle (OMFV)*, source-volume page **Volume 3d - 201**, extract PDF
> **p. 74**: Product Development, contract method C/FFP, performing activity
> *"General Dynamics Land Systems & American Rheinmetall Vehicles : Sterling Heights, MI
> & Slidell, LA"*, FY 2023 award date **Jun 2023**.

So the fixture cites the budget exhibit, not this stub, for the vendor names and the
award month. This stub remains the record of the press release itself, which the
demonstration names as the *trigger's* public occasion and quotes nowhere.

**The date: the month is sourced, the day is not.** The R-3 exhibit prints **`Jun 2023`**
— a month, with no day. No source this repository holds prints **26** June. The nearest
independent check runs the other way: GAO-23-106549, published 27 June 2023, says at
printed p. 10 that the Army *"has not yet awarded contracts for a detailed design, but
plans to do so by the third quarter of fiscal year 2023"*. So:

* `2023-06-26` — in this file's name, in `demos/b_omfv_2019_2023/build.py` (`NOW5`,
  `AS_OF[5]`) and in episode 5's `asOf` — is a **working date**, held pending the
  release-status call below. It is not asserted as sourced anywhere.
* What the demonstration's chronology argument actually needs is only that the award came
  *before* GAO's report, and the exhibit's month together with GAO's 27 June cover date
  give that without the day.
* If retrieval settles on a different day in June 2023, episode 5's `asOf` moves within
  the month and nothing else in the demonstration changes. If it settles on a date after
  27 June, the run order of episode 5 and `rt-gao-grading` swaps, and that would be a real
  correction.

This repository's sourcing rule is to verify every date against the primary source. The
month is verified; the day is flagged here rather than quietly carried.

**What is NOT sourced and is therefore not asserted anywhere.** The identities of the
Phase 2 concept-design vendors that were *not* selected. `demos/b_omfv_2019_2023` records
that exclusion by label only (`ex-phase2-concepts-not-selected`), with no `id` and no
name, because naming them would need a second source this project does not hold.

Used by: `demos/b_omfv_2019_2023` (episode 5, `rt-downselect`).
