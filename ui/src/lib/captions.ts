// Shared caption strings (plan 07 Task 7 fix round, C1) — a home for a sentence more
// than one screen needs, so a future edit updates every place it appears together
// instead of drifting.

/** Honesty rule 9's own sentence: GAO-23-106549 states its nine section×dimension
 * verdicts in prose — section headings and body text, not a grid and not per-question
 * labels — and GAO did not assess or verify the Army's underlying analytical work.
 *
 * The wording was corrected on PR #6 after a reviewer checked the report itself. It had
 * read "publishes a 3×3 verdict grid", which handed GAO the credit for an arrangement
 * that is ours: the report's only figures are two photographs and a diagram of the
 * research standards, and its verdicts appear as prose under headings
 * ("...Is Generally Objective, but Did Not Detail Supporting Analyses"). An
 * anti-overclaim caption that itself overclaims is the worst version of this bug, and it
 * had been shipping in the one sentence whose entire job is to prevent it. `Timeline.tsx`'s own bespoke 3×3 sub-episode grid (a
 * *different* grid from the Readiness screen's 36-cell one) has no server-side
 * equivalent to fetch — nothing on `GET .../program/{p}/timeline` composes this
 * sentence — so it stays a UI constant, relocated here rather than duplicated so
 * exactly one definition exists.
 *
 * The Readiness screen's own 36-cell grid does NOT use this constant: it prints the
 * *scored tailoring's own* honesty note verbatim from the server instead
 * (`ReadinessView.standardsCaptions.tailoringNote`, `kernel.render.tailoring_note()`
 * over `standard/tailorings/<name>.yaml`'s `note` field) — the kernel's own string for
 * the specific tailoring an episode was actually scored under, never this general
 * restatement and never a second hand-typed copy of it. */
export const GAO_23_106549_CAPTION =
  'GAO-23-106549 states nine section×dimension verdicts in prose, not as a grid and not ' +
  'as per-question labels. The 3×3 arrangement and the per-question layer here are ours. ' +
  "GAO did not assess or verify the Army's underlying analytical work.";
