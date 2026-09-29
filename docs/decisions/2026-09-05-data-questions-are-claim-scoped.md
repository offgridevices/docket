# 2026-09-05 — the data questions (EXE-4, EXE-5) stay claim-scoped

**Chosen:** `_cited_evidence` in `src/docket/kernel/standards.py` keeps its current
definition — *evidence cited by a Claim's `supportedBy` or by an Observation* — and the
four predicates that read it (`data_scope_all_known`, `data_scope_some_known`,
`reliability_all`, `reliability_some`) keep falling to `always → 4` when a record cites
nothing. No predicate, no ladder and no rule was changed. The resulting disagreement with
GAO-21-460 Figure 6 on **EXE-4** ("Were the data used valid for the study's purposes?") and
**EXE-5** ("Were the data used sufficiently reliable for the study's purposes?") is
reported as a measured disagreement, in `demos/validation_gao_21_460/README.md` and in
`demos/validation_gao_21_460/out/agreement.json`.

**Over:** widening `_cited_evidence` to fall back to the episode's `evidenceRegister` when
the episode has no claims and no observations.

## What was measured before deciding

The blinded GAO-21-460 walk scored **18 of 21** against Figure 6 — κ 0.710, majority
baseline 0.667, by band design 1.000, execution 0.625, presentation 1.000, with three
disagreements: EXE-3, EXE-4 and EXE-5 [out: demos/validation_gao_21_460/out/agreement.json].

The widening was then implemented as a throwaway monkey-patch in a scratch probe (no
repository file was touched) and all three scored cases were re-run:

| case | base | widened |
|---|---|---|
| GAO-21-460 | 0.857; execution 0.625; misses EXE-3, EXE-4, EXE-5; κ 0.710 | **0.952**; execution 0.875; misses EXE-3 only; κ **0.897** |
| — EXE-4 | state 4 (`always→4`) | state **1** (`data_scope_all_known→1`) |
| — EXE-5 | state 4 (`always→4`) | state **1** (`reliability_all→1`) |
| Demo A (CBO GCV 2013) | ready true; verdicts generally objective / valid / reliable | **no state changes at all** |
| GAO-15-548 control | agreement 1.000; ready false | **no state changes at all** |

Two facts came out of that probe that the framing of the choice did not contain:

1. Widening lands EXE-4 and EXE-5 on **state 1**, not state 2 — "no concerns" about the
   validity and reliability of data, on a record with zero claims, zero observations and
   zero runs.
2. Widening changes **nothing anywhere else in the repository**. Demo A and the GAO-15-548
   control both carry claims and observations, so the fallback never fires. Its entire
   measurable effect is on the one case being scored against a published key.

## Why

**1. It is the only option that keeps the GAO comparison honest.** The single property
that makes this walk worth putting in front of a reviewer is that the number was fixed
before the key was opened. A predicate widened *after* the key was read, which moves the
headline from 18 of 21 to 20 of 21 and moves nothing else in the repository, is not
distinguishable from fitting — whatever the motivation. Probe fact (2) is the whole
argument: a change whose entire measurable effect is on the scored case is a change to the
score.

**2. The naive widening contradicts a ruling already recorded.**
`docs/decisions/2026-09-05-narrative-only-records-score-state-2-on-pre-3-pre-4.md` fixes the
principle that a record with no runs caps at state 2, never 1, because "some limitations or
concerns" is the strongest honest thing to say about it. Probe fact (1) shows the widening
giving state **1** on the two data questions of a record with no runs at all. Adopting it
would make the kernel say opposite things about the same record on PRE-3 and on EXE-5.

**3. GAO and the kernel are looking at different objects here, and that is the interesting
sentence rather than a defect to paper over.** GAO answered EXE-4 and EXE-5 by interviewing
the study's authors [src: sources/gao-21-460-tactical-wheeled-vehicles-accessible.pdf],
printed p. 36 (PDF p. 41):

> To assess the 2021 MDO TWV Study, we interviewed the study's authors to better understand
> how the study was conducted, and to understand the scope, methodology, analyses,
> assumptions, limitations, data sources, and data validity and reliability steps taken as a
> part of the study.

The kernel has no interview channel. It has a record, and it scores what the record *uses*.
Registering evidence is not using it. GAO could assess the study's **plans**; the schema
scores the **record** — and on a study whose final report was not available during the
audit, those are two different things. A reviewer can check that against printed p. 36 in
thirty seconds, which makes it a stronger sentence than 20 of 21 would have been.

**4. The disagreement runs in the safe direction, and the statistics say so.** False
negatives are zero and recall on "unable to assess" is 1.00: every miss is the kernel
declining to certify, never certifying something GAO could not. For an evidence-discipline
tool that is the correct asymmetry.

**5. Vacuity already cuts the way the code cuts it.** `_all` returns `False` on an empty id
set by explicit design — a set you cannot enumerate cannot be judged "all" anything. The
resulting state 4 is not a failure verdict; it is literally "insufficient information to
determine", which is the honest description of a record that asserts nothing on the evidence
in question. The current behaviour is the right answer to the question the kernel is
actually asking.

## Cost if wrong, stated plainly

The scorer under-reports two of GAO's 21 questions on any record that documents a
data-handling process but has not yet asserted anything on it. The cost is bounded and
visible: both questions appear in the per-question table with the rule that produced them
(`always→4`), the disagreement is named in the README and in the artefact, and it lowers
our own headline number rather than inflating it. The failure mode this decision protects
against — a rule tuned after the key was read — is not bounded and is not visible.

## Would reverse if

A **second, independent published per-question key** — not GAO-21-460; there is no other
today, and the whole GAO record contains exactly one — shows the claim-scoped reading
producing a false "unable to assess" on a record with a documented data-handling process.
A single further instance of the same shape on the same key does not count, because the
same key cannot corroborate itself.

**And if it is ever reversed, the widened clause must land on state 2, gated on
`runs_exist == false`, never on state 1** — consistent with the R2 decision above. Any
patch that reaches state 1 on a record with no runs should be rejected on that ground
alone.

## Sequencing

This decision is written **after** the walk was measured and is to be committed in a change
separate from the fixture itself. The commit history is part of the evidence that the number
was not fitted; folding a rule decision into the commit that establishes the number would
destroy that property whichever way the decision went.

## Wording for the technical volume

One sentence, to be used as written:

> On two of GAO's 21 questions the kernel declined to assess where GAO assessed, because
> GAO answered them by interviewing the study's authors and the kernel scores only what the
> written record uses. We report the gap rather than widening a predicate to close it.

## Provenance line

GAO-21-460 Figure 6 is the only per-question published key in the GAO record. GAO assessed
the *study*; in GAO-21-460 GAO states it assessed only the study's design and portions of
its execution (printed p. 35), and in the related GAO-23-106549, per footnote 7 and Appendix
I, GAO did not assess or verify the Army's underlying analytical work. Nothing here is a
finding about whether the Army's analysis was right.

**No code change accompanies this decision.** The behaviour it records is at
`src/docket/kernel/standards.py` (`_cited_evidence`, `_all`, `_some`,
`data_scope_all_known`, `data_scope_some_known`, `reliability_all`, `reliability_some`) and
`src/docket/standard/rules.yaml` (the EXE-4 and EXE-5 ladders); the measurement it rests on
is pinned by
`tests/demos/test_validation_gao_21_460.py::test_the_three_disagreements_are_named_with_their_reason`.
