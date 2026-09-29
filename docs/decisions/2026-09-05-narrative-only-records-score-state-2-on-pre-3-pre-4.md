# 2026-09-05 — narrative-only records score state 2, never 1, on PRE-3 and PRE-4

**Chosen:** `PRE-3` gains `{when: claims_exist_no_silence, state: 2}` and `PRE-4` gains
`{when: claims_exist, state: 2}`, both inserted immediately before the closing
`{when: always, state: 4}` clause. A reconstruction that presents claims supported by
cited, reviewed evidence but carries no evaluation run scores **2 — never 1** — GAO's
own level-2 label, which the kernel's rating scale carries verbatim, is "some
limitations or concerns" (GAO-11-82R, Enclosure II, p. 35; `research-standards-36.yaml`
`rating_scale`). What the scorer actually prints for such a record (a `complete_graph()`
fixture with its `runs` list emptied, `k=99`, `dimension_verdicts` on the objectivity
dimension) is:

> generally objective, but the record does not thoroughly describe: PRE-3: Are the
> conclusions sound?; PRE-4: Are the study results presented in the report in a clear
> manner?

That "does not thoroughly describe" text is the qualifier's actual, generic wording — it
names the state-2 questions by id and canonical text but does not distinguish *why* they
are at 2. **"Not reproducible from runs in the record" is our gloss on that reason for
this specific case, not a label the code emits or that GAO uses**; the qualifier itself
is reason-blind and would say the same thing if a claim were merely under-evidenced. State
1 on both questions is untouched: it still requires a run
(`conclusions_sound`/`results_clear`/`runs_exist` all read the episode's own `runs`
list), results with units and raw values, and a claim derived from that run
(`results_support_claims`, `results_clear`). The two new clauses are gated differently on
purpose: `PRE-3` reads `claims_exist_no_silence` because it is mapped to all three
dimensions and a `silence` finding on the record is exactly the kind of concern PRE-3 is
supposed to catch; `PRE-4` reads the plainer `claims_exist` because PRE-4 is a
presentation question and supported-ness or silence are what PRE-1 and PRE-2
already test.

**Over:** leaving both at 4. `PRE-3` is mapped to **all three** dimensions
(`research-standards-36.yaml` `dimension_mapping`: objectivity, validity *and*
reliability — see `tests/test_standard.py`'s
`assert dm["reliability"]["question_ids"] == ["DES-6", "EXE-5", "PRE-2", "PRE-3"]`), so
leaving it at 4 makes every narrative record read `insufficient_to_conclude` on
objectivity, validity and reliability alike, off the back of a single unscored question.

**Why this is honest.** State 4 means "insufficient information to determine" — the
scorer has nothing to go on. A record that states its conclusions and cites the evidence
behind them gives a reader enough to judge whether those conclusions follow from what is
described; what it does not give is a computation to re-run. That is a concern about
reproducibility, not an absence of information, and GAO's own vocabulary draws exactly
this distinction. GAO-23-106549 defines "generally objective" as a qualified pass, not a
clean one — printed p. 17 (verified against `sources/gao-23-106549.pdf`, Appendix I:
Objectives, Scope, and Methodology):

> For example, we drew conclusions that the report was generally objective when
> available information presented in the report was consistent with our definition of
> objectivity but was missing information that would have addressed the generally
> accepted research standards.

That is the same shape of judgment this clause encodes: available information is
consistent with the definition, something is still missing, and the resulting rating is
a qualified "some concerns," not "no information at all." This is a
**representation-level** reading, consistent with the honesty constraint that runs
through this repository: per footnote 7 (printed p. 9, verified against the same PDF —
*"We did not independently assess or verify the analytical efforts supporting the
report"*) and Appendix I, GAO does not verify the Army's underlying analytical work
either; it assesses what the report says about itself. Scoring a narrative record on
what it presents, rather than refusing to score it at all because it presents without a
run, keeps that same posture.

**Cost if wrong, stated plainly:** presentation is credited to a record that has no
results. The cost is bounded — state 2, not state 1 — and when the verdict is
`generally_X` the dimension qualifier names every state-2 question by id and canonical
text, so the credit is visible in the artefact, not buried in an aggregate. (When the
verdict is `not_X` or `insufficient_to_conclude` instead, `qualifier` is `None`
(`standards.py`'s `dimension_verdicts`) — no credit is being reported in those cases
either, so this is not a gap, but the "named in the artefact" property specifically
describes the `generally_X` case.)

**Would reverse if:** the blinded GAO-21-460 walk (plan 05 Task 3) or the GAO-15-548
control (plan 05 Task 4) shows this clause moving a label away from a rating GAO itself
left at "unable to assess." It cannot today on a no-claims record: `claims_exist` is
false and all four presentation questions stay at 4, matching Figure 6's four "unable to
assess" labels
(`tests/kernel/test_standards.py::test_r2_leaves_a_record_with_no_claims_at_four`). The
GAO-21-460 reconstruction itself does not exist yet — plan 05 Task 3 is not dispatched —
so "it has no claims" is a prediction from the plan's skeleton table, not a verified
property of a committed fixture; re-check this paragraph once that fixture lands. If it
turns out to have claims, or the GAO-15-548 control disagrees, this clause becomes
load-bearing on the one published per-question key this project has, and must be
re-argued. Short of that, the reversal point is Shreyash's sign-off: this decision was
accepted by the orchestrator on 2026-09-05 as an exception to the fixture-discipline rule
("fix fixtures, never rules, unless the rule is demonstrably wrong") specifically because
the rule was judged wrong, not because a target needed to be reachable — but the sign-off
that makes it stick is human, not the executor that proposed it, and it can be reversed
on nothing more than his reading of the file.

A separate, narrower follow-up: the qualifier text itself (`"…but the record does not
thoroughly describe: …"`) does not distinguish *why* a question is at state 2 — a
narrative record with no run and a record with a run but under-evidenced claims would
read identically. Making the qualifier reason-aware is a `dimension_verdicts` change,
not a `rules.yaml` change, and is out of scope for this task; it belongs to whoever owns
`dimension_verdicts` next.

**Provenance line.** GAO-23-106549 states nine section×dimension verdicts in prose, not
as a grid and not as per-question labels. Any per-question reading of that report —
including the reading this clause encodes — is ours, not GAO's.

**Implemented in** `src/docket/standard/rules.yaml` (PRE-3, PRE-4); covered by
`tests/kernel/test_standards.py::test_narrative_only_record_scores_two_not_four_on_pre3_and_pre4`,
`::test_narrative_only_record_with_silence_drops_pre3_not_pre4`,
`::test_pre4_claims_exist_is_load_bearing_when_reliability_steps_are_gapped`,
`::test_narrative_only_record_with_silence_and_gapped_reliability_steps_is_insufficient_everywhere`,
`::test_r2_leaves_a_record_with_no_claims_at_four`, and
`::test_r2_does_not_soften_a_record_that_has_runs`, which is also the complete-episode
fixture in `tests/kernel/conftest.py` both rules must still pass at state 1.

**Correction (PR #6, 2026-09-09).** This note previously read "publishes a 3×3
section×dimension verdict grid". A reviewer checked the report: its only figures are
two photographs and a diagram of the research standards, and the verdicts appear as
prose under section headings. The 3×3 arrangement is ours. The substance of the note —
that the per-question mapping is ours, not GAO's — is unchanged and is the point.
