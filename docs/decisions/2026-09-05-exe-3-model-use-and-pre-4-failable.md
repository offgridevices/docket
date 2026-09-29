# 2026-09-05 — EXE-3 scores model use, not evidence reuse; and PRE-4 has to be failable

Two rule-fidelity decisions in the standards scorer, taken together because both were
found the same way: by asking what a reviewer who knows the GAO questions would say the
rating *means*, and finding the code answering a different question.

---

## 1. EXE-3 is about models

**Chosen:** the scope checker emits a model-scoped finding, `ModelUsePastPurpose`, when a
Model is used outside the question class it was built for (AR 5-11 ¶4-2i(1)), and EXE-3 is
keyed on that plus three other model conditions: accreditation older than three years
(`ReaccreditationRequired`, ¶4-2i(3)), a missing VV&A record (`model-vva`), and reuse of a
modelling & simulation study — evidence whose `evidenceType` is `MSStudy` — behind a claim
without a recorded reuse justification. Reuse of a *Document* past its purpose no longer
touches EXE-3; it lands on EXE-4, the data-scope question.

**Over:** the previous rule, where EXE-3 fell to state 3 on any `ReusePastPurpose`
finding, and the model loop emitted `ReaccreditationRequired` for both the intended-use
mismatch and the elapsed-time lapse.

**Why.** EXE-3's canonical text (GAO-16-820 App. I, "Models") asks whether the *models*
used to support the analyses were appropriate for their intended purpose. Under the old
rule you could change one field on an unrelated document — its scope-of-validity question
class — touch no model at all, and watch EXE-3 drop to 3 with a Claim and a document named
as the justification. Our §9.1 deliverable is a labelled comparison of our per-question
reading against GAO's own published grid and findings, so a downgrade attributed to the
wrong artefact is not cosmetic: it is the comparison being wrong about which part of the
record failed. GAO-23-106549's F1 concerns the Army's reuse of TRAC's modelling work,
which is an `MSStudy`, so keeping the M&S-study path inside EXE-3 keeps the mechanism that
actually detects F1 attached to the question F1 belongs to. Splitting ¶4-2i(1) from
¶4-2i(3) into two rule names follows from the same reasoning: two different defects, two
different remedies, and a rating that says which one it saw.

**Would reverse if:** GAO's own per-question key — the GAO-21-460 Figure 6 walk scheduled
in plan 05, the only published per-question key we have — shows model-question downgrades
driven by data reuse rather than by model use. That would make the broader reading GAO's,
not ours, and the narrower rule the fidelity error.

**Note on provenance.** GAO-23-106549 states nine section×dimension verdicts in prose, not
as a grid and not as per-question labels. Any per-question mapping of that report, including
the page and finding numbers cited in `src/docket/standard/rules.yaml`, is ours and is
labelled as such in that file and on the `gao-23-106549` tailoring.

---

## 2. PRE-4 has to be a rating the record can fail

**Chosen:** PRE-4 ("are the study results presented in the report in a clear manner?")
reaches state 1 only when runs exist, every Result they produced is present and carries
units, every per-measure Result still carries the raw value and the unit it was measured
in, **and** at least one Claim is derived from one of those runs and cites a Result that
run actually produced.

**Over:** the previous rule — every Result has a truthy `units`.

**Why.** The kernel writes every Result itself and hardcodes `units` on all of them, so
the old bar could not fail while the kernel was the author: an episode with runs and zero
claims scored "no concerns" on how clearly its results were presented, and that state 1
then fed the objectivity dimension. A rating that cannot fail carries no information, and
in an assessment whose whole point is to be sceptical of the record it inflates the
verdict. The parts a *record* can get wrong are the ones the rule now tests: a per-measure
Result that lost the raw observation or its unit, and a set of numbers no claim ever
states. Presenting a result is making a claim about it; if nothing in the package says
what the run showed, the results were not presented.

**Would reverse if:** the renderer starts emitting the results table directly from the
run, with no Claim in between, and reviewers read that table as the presentation. Then the
Claim condition would be testing our authoring convention rather than the record's
clarity, and it should be replaced by a check on the rendered package.

---

**Both:** implemented in `src/docket/kernel/scope.py`, `src/docket/kernel/standards.py` and
`src/docket/standard/rules.yaml`; covered by the EXE-3 ladder and the PRE-4 tests in
`tests/kernel/test_standards.py`, and by the complete-episode fixture in
`tests/kernel/conftest.py`, which is the record both rules must still pass.

**Correction (PR #6, 2026-09-09).** This note previously read "publishes a 3×3
section×dimension verdict grid". A reviewer checked the report: its only figures are
two photographs and a diagram of the research standards, and the verdicts appear as
prose under section headings. The 3×3 arrangement is ours. The substance of the note —
that the per-question mapping is ours, not GAO's — is unchanged and is the point.
