# 2026-09-05 — a fired bias indicator caps DES-14 at "some concerns", by design

**Chosen:** the readiness report computes the bias indicators before it scores the
standards, and the indicators it fires are written into the episode as open `bias-*`
Risks. DES-14's no-concerns bar (`bias_checks_performed_no_open_risks`) requires at least
one bias check actually *performed* and no open `bias-*` Risk — so any indicator that
fired during the same readiness run holds DES-14 at state 2 until someone mitigates,
accepts or closes the Risk it raised.

**Over:** two alternatives. Scoring the standards first, so that the run's own indicators
never reach the rating they are about. And reading DES-14 as "were bias checks performed"
alone, ignoring open risks entirely.

**Why.** DES-14 comes from GAO-15-457R II.d/II.g, which is about whether the analysis
guarded against bias — not about whether a form was filled in. A computed indicator that
fired is live evidence that a specific bias is present in *this* record: an anchoring
signal on the order alternatives were entered, say. Having performed a premortem while an
anchoring indicator is still open is precisely the "some concerns" case, and the ordering
that makes that visible is the ordering that makes the rating honest. Scoring first would
mean the package could report a fired indicator on one page and "no concerns about bias"
on another, from the same run. The escape is not to suppress the indicator but to act on
it: a Risk that has been mitigated, accepted or closed no longer holds DES-14 down, and
the record shows who decided that and why.

This was emergent rather than chosen — it fell out of the order `readiness_report` happens
to call things in — so it is written down here to make it a decision that a later change
has to argue with, rather than an accident a refactor could silently reverse.

**Would reverse if:** reviewers read DES-14 as "were bias checks performed", full stop —
in which case the open-risk clause moves out of DES-14 and becomes its own readiness
warning, reported next to the indicators rather than inside the standards assessment. The
GAO-21-460 Figure 6 walk in plan 05 is the first place we would see how GAO itself grades
a record that both ran the checks and shows the symptom.

**Implemented in:** `src/docket/kernel/standards.py`
(`bias_checks_performed_no_open_risks`, DES-14 in `src/docket/standard/rules.yaml`).
Covered by the DES-14 rungs and the `an_open_bias_risk` degradation in
`tests/kernel/test_standards.py`. The ordering itself lives in plan 03b's
`readiness_report`, which must not be reordered without reversing this entry.
