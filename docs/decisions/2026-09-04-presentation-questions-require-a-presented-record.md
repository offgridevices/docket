# 2026-09-04 — presentation questions require a presented record

**Note on dating.** This decision landed in plan 03a Task 5, before plan 05 existed;
this file is the record of that choice, not the edit — the rule change itself is
already at `src/docket/standard/rules.yaml` HEAD (`PRE-1`, `PRE-2`, `PRE-4`). Plan 05
Task 2 writes this file down because the review of R2 (the separate, later
narrative-only clause on `PRE-3`/`PRE-4`; see
`docs/decisions/2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md`)
depends on knowing what was already in place and why.

**Chosen:** `PRE-2` (canonical text, `research-standards-36.yaml:1141`: *"Does the report
present an assessment that is well documented?"*) reaches state 1 only when claims
exist, no `silence` finding touches the episode, and no reachable `InsufficientEvidence`
has `impact: blocking` (`claims_exist_no_silence_no_blocking_gaps`); state 2 when claims
exist and there is no silence (`claims_exist_no_silence`); otherwise 4. `PRE-1`
(canonical text, `:1111`: *"Do the results of the modeling support the report
findings?"* — validity) and `PRE-4` (objectivity) each gain
`{when: claims_all_supported, state: 2}` before their closing `always`: a claim is
"supported" when every claim in the episode carries content in `supportedBy` and every
evidence item it cites carries content (not a gap) in `reliabilitySteps`. A narrative
study whose claims cite reviewed evidence with recorded reliability steps is therefore
not scored as if nothing were presented, even with no evaluation run behind it.

**Over:** rating presentation from the presence of evaluation runs alone. Under that
reading, a study still in progress and a study that never intends to run a computation
score identically — both "insufficient information" — which erases the distinction
between a record with nothing to say and a record that says something but has not
computed it.

**Why.** A study that has not yet produced a report has nothing to present, and must
not score "well documented" on an empty record. GAO-21-460 is the case that makes this
concrete: the 2021 MDO TWV Study was still underway when GAO wrote its report, and GAO
says so directly. Printed p. 35 (verified against
`sources/gao-21-460-tactical-wheeled-vehicles-accessible.pdf`):

> The 2021 MDO TWV Study final report was not available during the time of our audit so
> we were able to assess only the design portion and portions of the execution of the
> study against the standards.

GAO's own Figure 6 marks seven of the **twenty-one** questions "unable to assess" for
that study — three execution questions and all four presentation questions, not "no
limitations or concerns" and not "significant limitations or concerns" (GAO-11-82R,
Enclosure II, p. 35 — a different source's four-level scale, carried in
`research-standards-36.yaml`'s `rating_scale`), but a distinct label for "there is
nothing here to rate." Verified against the accessible text alternative of Figure 6,
printed pp. 40-41 of `sources/gao-21-460-tactical-wheeled-vehicles-accessible.pdf`
(the figure's own legend reads `Assessed` / `Unable to assess`; the accessible text
alternative says "unable to **access**," a defect in the source's alt text, not a
different label):

> 2) Execution: Is the study well executed? … b) Are the study's objectives addressed?
> (unable to access) … f) Were any data limitations identified and were the impact of
> the limitations adequately explained? (unable to access) … h) Have the models used in
> the study been described and documented adequately? (unable to access) …
> 3) Presentation of results: … (all were unable to be accessed)

A record with no claims at all reproduces that same absence: `claims_exist` is false, so
every clause down to `always` fails and the question lands at 4. That is the honest
floor. The clauses added here only ever fire once a claim exists — once the record has
said *something* — which is the condition GAO-21-460 did not meet for these questions
and a narrative-only reconstruction does.

**Would reverse if:** GAO ever rates presentation on a study plan alone, with no claims
or stated conclusions of any kind. Nothing in GAO-21-460, GAO-15-548, or GAO-23-106549
does this; all three either have a report with claims to assess or explicitly withhold a
rating on the sections that lack one.

**Provenance line.** GAO-21-460 Figure 6 is the only per-question published key this
project has (14 Assessed / 7 Unable to assess). GAO-23-106549 states nine
section×dimension verdicts in prose, not as a grid and not as per-question labels; the mapping
of either report onto `PRE-1`/`PRE-2`/`PRE-4` in `src/docket/standard/rules.yaml` is
ours.

**Implemented in** `src/docket/kernel/standards.py` (`claims_exist`,
`claims_exist_no_silence`, `claims_exist_no_silence_no_blocking_gaps`,
`claims_all_supported`) and `src/docket/standard/rules.yaml` (`PRE-1`, `PRE-2`, `PRE-4`);
covered by `tests/kernel/test_standards.py::test_pre1_and_pre2_with_supported_claim_and_no_runs`
and `::test_pre2_no_claims_scores_4`.

**Correction (PR #6, 2026-09-09).** This note previously read "publishes a 3×3
section×dimension verdict grid". A reviewer checked the report: its only figures are
two photographs and a diagram of the research standards, and the verdicts appear as
prose under section headings. The 3×3 arrangement is ours. The substance of the note —
that the per-question mapping is ours, not GAO's — is unchanged and is the point.
