// "Ranking and results" (design spec Screen 5; plan Task 7 Step 3) — the demo's first
// numerals. One bar row per alternative, in the server's own `ranking` order (`read_back`
// / `EvaluationRun.ranking` — never re-sorted here). The bar's *length* is pixel
// geometry computed by `lib/svg.ts`'s `barWidth`/`maxOf`; the number beside it is the
// same `Result.value` the bar represents, printed through `<Num>` with the result's own
// id as its provenance — the bar and the numeral must never be able to disagree, because
// they are drawn from the same `entries` array this component builds once, not
// recomputed independently.
//
// Only the *aggregate* result per alternative is shown as a bar (`Result.aggregate ===
// true` — `kernel.evaluate`'s one weighted value per alternative, the same figure the
// committed demo packages print in "## 7. Evaluation results"); the per-measure,
// non-aggregate `Result`s a run also seals are not repeated here, to keep this panel to
// exactly what the plan describes ("a bar row per alternative") rather than a second,
// uninvited measures breakdown.

import { Num } from './Num';
import { barWidth, maxOf } from '../lib/svg';

export interface ResultEntry {
  alternative: string;
  value: number;
  units: string;
  measure?: string;
  aggregate: boolean;
  /** `read_back`'s own `str(value)` (plan 07 Task 7 fix round, I2) — `<Num>` prefers
   * this over re-stringifying the parsed float, so `36.0` never renders as `36`. */
  valueText?: string;
}

// The bar track's *coordinate space*, not its rendered width. `barWidth` still measures
// against this number exactly as before — the `<svg>` then declares it as a `viewBox` and
// lets CSS pick the real width, so the track narrows with the row instead of forcing the
// page to scroll sideways at 360 px (§5a: "overflow is a bug"). `preserveAspectRatio
// ="none"` is what makes the box stretch horizontally only, which is the one axis a bar
// track has meaning on; the height stays the 14 px the row was always drawn at.
const TRACK_PX = 220;

export interface ResultTableProps {
  /** `read_back(g, runId).results` — keyed by `Result` id. */
  results: Record<string, ResultEntry>;
  /** `read_back(g, runId).ranking` (== `EvaluationRun.ranking`) — alternative ids, best
   * first, exactly as the kernel sealed them. */
  ranking: string[];
}

export function ResultTable({ results, ranking }: ResultTableProps) {
  const rows = ranking
    .map((alt) => {
      const entry = Object.entries(results).find(
        ([, r]) => r.alternative === alt && r.aggregate,
      );
      return entry ? { resultId: entry[0], ...entry[1] } : null;
    })
    .filter((r): r is { resultId: string } & ResultEntry => r !== null);

  if (rows.length === 0) {
    return <p className="og-label text-b3 text-fg-muted">no aggregate results on this run</p>;
  }

  const max = maxOf(rows.map((r) => r.value));

  return (
    <ol className="flex flex-col gap-2" data-testid="result-table">
      {rows.map((r, i) => (
        // §5a's stacked treatment. Under 768 px the row becomes a label-over-value
        // card — rank and alternative on top, bar and numeral beneath, separated by a
        // hairline the way the brand's own `.spec` table separates its pairs. At 768 px
        // and up `md:contents` dissolves the two wrappers so the four parts become
        // direct children of the row flexbox again and it reads as a table, exactly as
        // it did before. No second markup tree, and nothing hidden at either width.
        <li
          key={r.resultId}
          className="flex flex-col gap-1 border-b border-hairline py-2 last:border-b-0 md:flex-row md:items-center md:gap-3 md:border-b-0 md:py-0"
        >
          <div className="flex min-w-0 items-baseline gap-2 md:contents">
            {/* Row position, not an API value — same `data-num="label"` exemption as
                `AppShell.tsx`'s nav index (honesty rule 2's "object counts"
                carve-out). */}
            <span className="og-mono text-m2 text-fg-muted shrink-0 md:w-6" data-num="label">
              {i + 1}
            </span>
            <span className="og-mono text-b3 min-w-0 truncate md:w-40 md:shrink-0">{r.alternative}</span>
          </div>
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <svg
              viewBox={`0 0 ${TRACK_PX} 14`}
              preserveAspectRatio="none"
              className="h-3.5 w-full min-w-0 max-w-[220px]"
              aria-hidden
            >
              <rect x={0} y={2} width={TRACK_PX} height={10} fill="none" stroke="var(--og-hairline-strong)" />
              <rect x={0} y={2} width={barWidth(r.value, max, TRACK_PX)} height={10} fill="var(--og-fg)" />
            </svg>
            <Num value={r.value} from={r.resultId} units={r.units} valueText={r.valueText} />
          </div>
        </li>
      ))}
    </ol>
  );
}
