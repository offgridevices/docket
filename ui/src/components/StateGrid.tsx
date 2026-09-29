// The 36-question readiness grid (design spec Screen 6; plan Task 7 Step 4). One
// `StateMark` per `StandardsAssessment.ratings[]` entry, in the array order the server
// already sends — DES-1..14, EXE-1..15, PRE-1..7 (`kernel.standards.score_standards`
// iterates the tailoring's own question order; this component does not re-sort).
//
// Laid out with a CSS grid, not raw SVG rects: `lib/svg.ts`'s `cellRect` (plan Step 1)
// stays available for a caller that needs literal pixel rects, but 36 same-size cells
// with native hover/focus/`title` semantics is exactly what Tailwind's grid utilities
// already give for free, and every other tabular screen in this app (`Slot`/`GapCard`/
// `SectionList`) is plain DOM for the same reason — see the Task 7 report.
//
// Brand v3.0 (§5a): the grid stays a GRID at every width. It is the claim this screen
// makes — 36 questions, scored, in one shape you can take in at once — and a list of 36
// rows would be a different claim. `repeat(auto-fit, minmax(44px, 1fr))` is what does
// that without a media query: the columns reflow themselves as the space narrows and no
// cell is ever smaller than the 44px touch floor. The nine fixed columns it replaces
// could not narrow at all.
//
// Honesty rule 9's "standing caption, not a tooltip": the GAO-11-82R rating-scale
// sentence is printed here as body text under the grid's title — fix round 1 (C1): as
// the server's own string (`ReadinessView.standardsCaptions.ratingScale`,
// `kernel.render.rating_scale_legend()`), passed in as a prop, never a second
// hand-typed copy — never a `title` attribute, and never reworded. The scored
// tailoring's own honesty note (`standardsCaptions.tailoringNote`, e.g.
// gao-23-106549's caveat that GAO stated its verdicts in prose, not per-question
// labels) prints the same way, whenever the server sends one.
//
// Task 14: each cell carries the tint of its own state (`CELL_TINT`) and says which one
// it is in `data-cell-state`, so the grid can be read as a shape from across a room and
// checked one cell at a time from a test. The glyph is unchanged and still carries the
// state on its own — the tint is a second reading of the same fact, never the only one.

import type { StandardsAssessment } from '../types/objects';
import { Num } from './Num';
import { RATING_SCALE_LABEL, StateMark, type RatingState } from './StateMark';

const LEVELS: RatingState[] = [1, 2, 3, 4];

/** The tint a cell carries for the state the kernel gave its question (Task 14; the
 * colour decision doc). Tone on a plane, under a hairline of the same family — never on
 * the sentence beside it, and never Ember: this grid is a reading of the record, not an
 * act. Level 4 stays neutral on purpose. "Indeterminate — insufficient information" is
 * not a worse answer than level 3, and tinting it would say it was; the same reason
 * `StateMark` refuses to draw it in accent. A question the tailoring made inapplicable
 * takes the page's own ground, so the grid reads as "these are the ones that were
 * scored" at a glance. The glyph still carries the state for a reader who cannot see
 * the tint (§10: colour never carries a claim alone). */
const CELL_TINT: Record<string, string> = {
  '1': 'bg-done-tint border-done-line',
  '2': 'bg-wait-tint border-wait-line',
  '3': 'bg-stop-tint border-stop-line',
  '4': 'bg-raised border-hairline-strong',
  na: 'bg-canvas border-hairline text-fg-muted',
};

/** The legend row (fix round 1, I3): every glyph the grid can show, beside its level
 * number and the standard's own words — without this, four undifferentiated shapes and
 * a caption naming levels 1–4 in prose have no rendered mapping between them. */
function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2" aria-label="rating scale legend">
      {LEVELS.map((lvl) => (
        <li key={lvl} className="flex items-center gap-2">
          <StateMark state={lvl} applicable />
          <span className="text-b3 text-fg-secondary">
            <span className="og-mono" data-num="label">{lvl}</span>{' '}
            {RATING_SCALE_LABEL[lvl]}
          </span>
        </li>
      ))}
    </ul>
  );
}

export interface StateGridProps {
  ratings: StandardsAssessment['ratings'];
  aggregationRule?: string;
  /** `ReadinessView.standardsCaptions.ratingScale` — the renderer's own sentence. */
  ratingScaleCaption: string;
  /** `ReadinessView.standardsCaptions.tailoringNote` — `null` when the scored
   * tailoring has none (`full-36`, `gao-15-548`, `gao-21-460`, `published-21`); present
   * for `gao-23-106549`. Printed as standing body text, the same treatment as the
   * rating-scale caption, never a tooltip. */
  tailoringNote?: string | null;
  /** `StandardsAssessment.id` — the object `<Num>` cites for each cell's visible state
   * (fix round 1, C2): the state is a kernel-authored assessment result the package
   * already prints in its own per-question table, not a label. */
  assessmentId: string;
  /** The two Fields of the Readiness view that live inside a cell (Task 14): the object
   * ids a rating was drawn from (`ratings[i].justification`) and the scoring rule that
   * produced it (`ratings[i].rule`). Off by default — a grid of 36 cells is a shape to
   * take in at once, and both are detail a reader asks for rather than reads. */
  showJustification?: boolean;
  showRule?: boolean;
}

export function StateGrid({
  ratings,
  aggregationRule,
  ratingScaleCaption,
  tailoringNote,
  assessmentId,
  showJustification = false,
  showRule = false,
}: StateGridProps) {
  const detail = showJustification || showRule;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="og-display text-b1">Readiness grid</h2>
        {/* Standing captions — body text (Instrument Sans, v3.0's one body face), not a
            tooltip. Verbatim standard prose whose digits are level names, not values
            (fix round 1, C2). */}
        <p className="text-b2 text-fg-secondary mt-1" data-num="label">
          {ratingScaleCaption}
        </p>
        {tailoringNote && (
          <p
            className="text-b2 text-fg-secondary"
            data-testid="tailoring-note"
            data-num="label"
          >
            {tailoringNote}
          </p>
        )}
      </div>

      <Legend />

      {ratings.length === 0 ? (
        <p className="text-b3 text-fg-muted">no ratings on this assessment</p>
      ) : (
        <div
          className="grid gap-2"
          style={{
            // Six columns at 768px and up, the width §5a's own table names as the
            // grid's full form. `auto-fit` fits as many floor-width columns as the box
            // allows, so the box is what fixes the column count: 6 cells with five 8px
            // gutters between them. Layout arithmetic on constants, not on anything the
            // API sent. With a per-cell detail switched on the floor grows — a scoring
            // rule broken one character to a line is not a reading of anything — and
            // the shape stays six across rather than becoming a list.
            gridTemplateColumns: `repeat(auto-fit, minmax(${detail ? '128px' : '44px'}, 1fr))`,
            maxWidth: detail ? 'calc(6 * 136px + 5 * 8px)' : 'calc(6 * 52px + 5 * 8px)',
          }}
          role="list"
          aria-label="readiness grid, one cell per standard question"
        >
          {ratings.map((r) => {
            // `na` covers both halves of the schema's own pairing (not applicable, and
            // a state the store failed to record) — the same fail-closed reading
            // `StateMark` makes of the identical condition, so the tint and the glyph
            // can never disagree about which cell was scored.
            const cellState = r.applicable && r.state !== null ? String(r.state) : 'na';
            return (
              <div
                key={r.questionId}
                role="listitem"
                className={`flex min-h-11 min-w-0 flex-col items-center gap-1 border p-0.5 text-m2 ${CELL_TINT[cellState]}`}
                data-testid="grid-cell"
                data-cell-state={cellState}
              >
                {/* `tracking-normal` overrides `.og-mono`'s own 0.04em and `text-m2`'s
                    0.06em: a question id has to fit a 44px-floor cell without wrapping,
                    and the tracking the mono face carries for a run of numerals is what
                    would push `EXE-15` onto a second line. */}
                <span className="og-mono whitespace-nowrap tracking-normal text-fg-secondary">
                  {r.questionId}
                </span>
                <StateMark
                  state={r.state}
                  applicable={r.applicable}
                  tailoringReason={r.tailoringReason}
                  questionId={r.questionId}
                />
                {r.applicable && r.state !== null && (
                  <Num value={r.state} from={assessmentId} />
                )}
                {/* Both are kernel-authored coordinates into the record — a run of object
                    ids, and the scoring rule's own name with the state it yields
                    (`charter_complete_and_plan_approved→1`) — so both are mono, and both
                    are marked: the digit in a rule name is part of the rule's name, not a
                    value anything computed. `break-all`, because neither is prose and a
                    cell is narrow at 360px. */}
                {showRule && (
                  <span className="og-mono w-full break-all text-center tracking-normal text-fg-secondary" data-num="label">
                    {r.rule}
                  </span>
                )}
                {showJustification && r.justification.length > 0 && (
                  <span className="og-mono w-full break-all text-center tracking-normal text-fg-muted" data-num="label">
                    {r.justification.join(', ')}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {aggregationRule && (
        <p className="og-label text-m2 text-fg-secondary" data-num="label">
          Aggregation rule: <span className="og-mono">{aggregationRule}</span>
        </p>
      )}
    </div>
  );
}
