// One question's state on the GAO-11-82R rating scale (design spec's readiness grid;
// plan Task 7). The glyph carries the fill degree the plan specifies — 1 outline, 2
// quarter, 3 solid, 4 a neutral outline + help-circle, not-applicable a diagonal slash —
// and the label text next to it is the scale's own doctrinal wording, never a colour
// standing in for "pass"/"fail": level 3 ("significant limitations or concerns") is not
// styled as a failure, and level 4 ("indeterminate") is **never Ember** (fix round 1,
// I3) — Ember is this app's colour for a refusal (`ErrorState.tsx`) and its primary
// approve action, and colouring "indeterminate" the same way a reader decodes as "this
// failed" is exactly the inversion `kernel.render`'s own docstring warns against
// ("indeterminate, not a failing grade"). Level 4 is a plain neutral outline circle plus
// the help glyph — visually distinct from level 1's bare outline by the badge alone, no
// colour claim either way.
//
// The four labels below are the GAO-11-82R rating scale's own `label` text, byte-for-
// byte from `src/docket/standard/research-standards-36.yaml`'s `rating_scale.levels`
// block (source: "GAO-11-82R, Enclosure II, p. 35 (PDF p. 35)") — the same data
// `kernel.render._rating_scale_legend()` reads to print the identical sentence at the
// foot of every rendered package's Readiness section (confirmed byte-identical across
// all three committed demo packages' "## 10. Readiness" section). No API route exposes
// this text (`StandardsAssessment` carries `ratings[].state` as a bare integer, never
// the scale's label for it), so it is hardcoded here rather than fetched — a verbatim
// copy of the standard's own fixed scale, not a caption this project wrote about GAO's
// work. If `research-standards-36.yaml`'s `rating_scale` block ever changes, this
// constant must change with it (flagged in the Task 7 report).

import { Circle, CircleSlash2, HelpCircle } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';

export type RatingState = 1 | 2 | 3 | 4;

export const RATING_SCALE_LABEL: Record<RatingState, string> = {
  1: 'no limitations or concerns',
  2: 'some limitations or concerns',
  3: 'significant limitations or concerns',
  4: 'indeterminate — insufficient information',
};

const SIZE = 16;

/** A quarter-filled circle for state 2 — a static pie-slice path (literal numbers for a
 * 16px glyph, no runtime trigonometry on any value), matching `ICON_PROPS`' 1.5px
 * stroke and `currentColor` fill so it sits in the same glyph row as the lucide icons
 * either side of it. */
function QuarterCircle() {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" aria-hidden focusable="false">
      <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8,8 L8,1.5 A6.5,6.5 0 0 1 14.5,8 Z" fill="currentColor" />
    </svg>
  );
}

function SolidCircle({ className }: { className?: string }) {
  return (
    <svg width={SIZE} height={SIZE} viewBox="0 0 16 16" aria-hidden focusable="false" className={className}>
      <circle cx="8" cy="8" r="6.5" fill="currentColor" />
    </svg>
  );
}

export interface StateMarkProps {
  /** `StandardsAssessment.ratings[i].state` — `null` exactly when `applicable` is
   * `false` (the schema's own pairing; a hand-edited store that violates it renders as
   * not-applicable here, the same fail-closed choice `docket.kernel.lifecycle`'s
   * `_tolerant` checks make). */
  state: RatingState | null;
  applicable: boolean;
  /** `StandardsAssessment.ratings[i].tailoringReason` — shown on hover, and only on
   * hover: honesty rule 9 reserves the standing caption for the GAO sentence itself,
   * not for a per-cell detail like this one. */
  tailoringReason?: string | null;
  questionId?: string;
}

export function StateMark({ state, applicable, tailoringReason, questionId }: StateMarkProps) {
  if (!applicable || state === null) {
    return (
      <span
        className="inline-flex flex-col items-center gap-0.5 text-fg-secondary"
        title={tailoringReason ?? undefined}
        data-state="not-applicable"
        data-question={questionId}
      >
        <CircleSlash2 {...ICON_PROPS} size={SIZE} aria-hidden />
        {/* `tailoringReason` is verbatim kernel prose (`standard/tailorings/<name>.yaml`'s
            own reasoning, e.g. "Not among the 21 questions GAO published in ...") and
            can carry digits that are not a decision value — fix round 1, C2. */}
        <span className="sr-only" data-num="label">
          {questionId ? `${questionId}: ` : ''}not applicable{tailoringReason ? ` — ${tailoringReason}` : ''}
        </span>
      </span>
    );
  }

  const glyph =
    state === 1 ? (
      <Circle {...ICON_PROPS} size={SIZE} aria-hidden />
    ) : state === 2 ? (
      <QuarterCircle />
    ) : state === 3 ? (
      <SolidCircle />
    ) : (
      // §5 (brand v3.0): rating 4 is `--og-fg` SOLID plus the help glyph — never Ember.
      // It was a hollow outline under v1.2, when Ember still marked this state; the
      // solid fill is what now distinguishes "indeterminate" from rating 1's empty
      // outline without spending the screen's one accent on it. `text-fg` on the
      // wrapping span gives both marks their colour; no accent class here at all.
      <span className="relative inline-flex" aria-hidden>
        <SolidCircle />
        <HelpCircle {...ICON_PROPS} size={10} className="absolute -right-1 -bottom-1 bg-canvas" />
      </span>
    );

  // Fix round 1, I3: the same doctrinal sentence as both the visible `title` (a sighted
  // reader hovering a cell) and the `sr-only` text (a screen-reader user) — one string,
  // two audiences, never two different summaries of the same cell.
  const doctrinal = `${questionId ? `${questionId}: ` : ''}state ${state} — ${RATING_SCALE_LABEL[state]}`;

  return (
    <span
      className="inline-flex flex-col items-center gap-0.5 text-fg"
      title={doctrinal}
      data-state={state}
      data-question={questionId}
    >
      {glyph}
      {/* Re-states a value already visible in bracketed form elsewhere in this cell
          (`StateGrid`'s own `<Num value={r.state} .../>`, fix round 1, C2) — marked
          rather than reworded, honesty rule 2's carve-out for a label, not a second,
          unbracketed appearance of the number. */}
      <span className="sr-only" data-num="label">
        {doctrinal}
      </span>
    </span>
  );
}
