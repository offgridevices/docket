// "What flips the decision" (design spec Screen 5; plan Task 7 Step 3). `flips` arrives
// already in the order the caller decided (ideally `flip_summary.ranked` — shortest
// `flipDistance` first, ascending — mapped back to the full `FlipAnalysis` objects by
// the screen that fetched them); this component only ever maps over that array in the
// order it received it. Re-sorting here would make the browser the authority on "what
// flips first", which is precisely the claim the topic asks us to evidence with a
// kernel-sealed number, not a client-side comparator.
//
// The one numeral this component does not print through `<Num>` alone is the little
// range track beside each row: `thresholdX` (lib/svg.ts) places two marks — the run's
// `currentValue` and the flip's `flipThreshold` — along the parameter's own `range`, in
// pixels; the values themselves are still printed verbatim, in mono brackets, right next
// to the track.
//
// Brand v3.0, three changes to how this draws (§5, §5a):
//
//   * The track carries NO Ember. v1.2 marked the flip threshold with an accent dot,
//     which made one lit point per row on a screen that is allowed exactly one in total
//     — and Compute asks nothing of a human, so its answer is none. The two marks are
//     told apart by SHAPE, which is what the brand asks for anyway and what survives a
//     greyscale print: the run's current value is a filled dot, the threshold a tick
//     across the track.
//   * The SVG is fluid — a `viewBox` and `width: 100%`, never a fixed `width`/`height`
//     attribute (`fluidSvg`, lib/svg.ts), so the track is legible at 360px and on a
//     projector.
//   * Below 768px the table stops being a table: each row stacks as label-over-value
//     (§5a's own rule for a table on a narrow screen), which is one DOM row per flip
//     either way — `data-flip-id` order is the claim this screen makes and must not be
//     duplicated across a narrow copy and a wide copy.
//
// Type roles (§5): mono is for numerals, ids and coordinates. The parameter's own
// descriptive label and this panel's caption are prose, so they are body text now, not
// mono; `kind`/`target`/`direction` are verbatim record identifiers and stay mono.

import type { ReactNode } from 'react';
import { Activity } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import { fluidSvg, thresholdX } from '../lib/svg';
import type { FlipAnalysis } from '../types/objects';
import { Num } from './Num';

/** The track's own coordinate system, not a pixel width on screen any more: `fluidSvg`
 * turns it into a `viewBox`, and the browser scales it to whatever the column gives. */
const TRACK_PX = 140;
const TRACK_H = 14;

/** A `FlipAnalysis` plus the API's own text form of its numeric fields
 * (`docket.api.serialize.object_view`'s `valueText`, plan 07 Task 7 fix round I2) —
 * `Compute.tsx`'s `fetchFlipAnalysis` attaches this alongside the object itself. */
export type FlipAnalysisView = FlipAnalysis & {
  valueText?: {
    currentValue?: string;
    flipThreshold?: string;
    flipDistance?: string;
    range?: { lo?: string; hi?: string };
  };
};

export interface FlipChartProps {
  /** Full `FlipAnalysis` objects, already in the order this screen wants shown. */
  flips: FlipAnalysisView[];
  /** True when `flips`' order is `flip_summary.ranked` (shortest flip distance first) —
   * shown in the panel's own caption so a reader knows whether the order is a claim
   * about "what flips first" or simply the graph's own id order (the fallback before a
   * `flip_summary` exists for this run). Never asserted when it isn't true. */
  ranked?: boolean;
}

const COLUMNS = ['parameter', 'range', 'current', 'flip threshold', 'flip distance', 'direction'];

/** One cell. Below 768px it is a block carrying its own column name above the value —
 * the stacked label-over-value card §5a asks a table row to become — and at 768px and up
 * it is an ordinary `<td>` under the header row. */
function Cell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <td className="block py-1 md:table-cell md:py-2 md:pr-3 md:align-top">
      <span className="og-label block text-m2 text-fg-muted md:hidden">{label}</span>
      {children}
    </td>
  );
}

export function FlipChart({ flips, ranked = false }: FlipChartProps) {
  if (flips.length === 0) {
    return <p className="text-b3 text-fg-muted">no flip analyses on this run</p>;
  }

  return (
    <div className="flex flex-col gap-1">
      <p className="text-b3 text-fg-secondary">
        {ranked ? 'shortest flip distance first' : 'graph order — not yet ranked by flip distance'}
      </p>
      {/* The table scrolls sideways inside its own box rather than pushing the view column
          sideways (§5a; the same wrapper the episodes table uses). At and above 768 the
          rows stop stacking and the fixed-width flip track joins four text columns, whose
          min-content width is wider than the view column is at exactly 768 — where the
          column's own `overflow-x: hidden` used to clip the right-hand end of every row in
          silence. `colour.spec.ts` measures the column at all three widths and would fail
          if this went back. */}
      <div className="overflow-x-auto">
      <table className="block w-full text-left md:table" data-testid="flip-chart">
        <thead className="hidden md:table-header-group">
          <tr className="og-label text-m2 text-fg-muted">
            {COLUMNS.map((column) => (
              <th key={column} className="pr-3 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="block md:table-row-group">
          {flips.map((f) => {
            const [lo, hi] = [f.range.lo, f.range.hi];
            const currentX = thresholdX(f.currentValue, [lo, hi], TRACK_PX);
            const thresholdXPos = f.flipThreshold === null ? null : thresholdX(f.flipThreshold, [lo, hi], TRACK_PX);
            const vt = f.valueText;
            return (
              <tr
                key={f.id}
                className="block border-t border-hairline py-2 md:table-row md:py-0"
                data-testid="flip-row"
                data-flip-id={f.id}
              >
                <Cell label="parameter">
                  <p className="text-b3 inline-flex items-center gap-1">
                    {/* `shrink-0`: a flex item with a long label beside it is squashed
                        otherwise — the glyph was rendering 5px wide at 360px. */}
                    <Activity {...ICON_PROPS} size={14} className="shrink-0" aria-hidden />
                    {/* `parameter.label` is a kernel-authored descriptive sentence, not
                        a decision value — it can legitimately quote a share ("60
                        percent") as part of naming the weight, the same way a
                        Narrative sentence quotes a number in prose
                        (`render.check_citations` is what governs those, server-side).
                        `data-num="label"` because it is literally a label, not a
                        result this screen is asserting: verbatim kernel prose, the
                        honesty rule's own carve-out (fix round 1, M2). Prose, so it is
                        body text and not mono (§5). */}
                    <span data-num="label">{f.parameter.label}</span>
                  </p>
                  <p className="og-mono text-m2 text-fg-secondary">
                    {f.parameter.kind} · {f.parameter.target}
                  </p>
                </Cell>
                <Cell label="range">
                  {/* The track never exceeds its drawn width by much: a stacked cell is
                      the whole column at 360px, and a range line three times its own
                      height reads as a bar rather than a track. */}
                  <div className="max-w-[220px]">
                    <svg {...fluidSvg(TRACK_PX, TRACK_H)} aria-hidden>
                      <line x1={0} y1={7} x2={TRACK_PX} y2={7} stroke="var(--og-hairline-strong)" />
                      {/* Shape, not colour, tells the two marks apart (§5): the run's
                          current value is a filled dot, the flip threshold a tick across
                          the track. Neither is Ember — see this file's header. */}
                      <circle cx={currentX} cy={7} r={3} fill="var(--og-fg)" />
                      {thresholdXPos !== null && (
                        <line
                          x1={thresholdXPos}
                          y1={1}
                          x2={thresholdXPos}
                          y2={13}
                          stroke="var(--og-fg)"
                          strokeWidth={1.5}
                        />
                      )}
                    </svg>
                  </div>
                  <p className="og-mono text-m2 text-fg-secondary">
                    <Num value={lo} from={f.id} valueText={vt?.range?.lo} /> –{' '}
                    <Num value={hi} from={f.id} valueText={vt?.range?.hi} /> ({f.range.source})
                  </p>
                </Cell>
                <Cell label="current">
                  <Num value={f.currentValue} from={f.id} valueText={vt?.currentValue} />
                </Cell>
                <Cell label="flip threshold">
                  {f.flipThreshold === null ? (
                    <span className="og-mono text-m2 text-fg-muted">—</span>
                  ) : (
                    <Num value={f.flipThreshold} from={f.id} valueText={vt?.flipThreshold} />
                  )}
                </Cell>
                <Cell label="flip distance">
                  {f.flipDistance === null ? (
                    <span className="og-mono text-m2 text-fg-muted">—</span>
                  ) : (
                    <Num value={f.flipDistance} from={f.id} valueText={vt?.flipDistance} />
                  )}
                </Cell>
                <Cell label="direction">
                  <span className="og-mono text-m2">{f.direction}</span>
                  {f.assumption && (
                    <p className="text-b3 text-fg-secondary">
                      assumes <span className="og-mono text-m2">{f.assumption}</span>
                    </p>
                  )}
                </Cell>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </div>
  );
}
