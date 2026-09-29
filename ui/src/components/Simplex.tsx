// The weight-simplex robustness figure (design spec Screen 5, "the weight simplex... a
// triangle with simplexRobustness shaded per alternative"; plan Task 7 Step 3), reading
// `flip_summary`'s `simplexRobustness` — `{alternative: fraction}`, the share of `n`
// random weight draws over the step's own measures for which that alternative came out
// on top (`kernel.flip.flip_summary`).
//
// Rendered as one bar per alternative rather than a literal three-corner triangle: a
// triangle has exactly three corners, and `lib/svg.ts`'s `simplexPoint` (the plan's own
// three-part barycentric primitive) is only meaningful for a three-alternative step.
// Demo A's actual steps carry five alternatives (gcv, namer, puma, retain-bradley,
// upgraded-bradley — verified against the committed package's evaluation-results
// table), and `simplexRobustness` never carries more than the alternative fractions
// themselves — no per-draw point data, no measure-vertex coordinates. Stretching five
// fractions onto three triangle corners, or inventing a fourth/fifth vertex position,
// would be drawing a value the server did not give us; a bar per alternative uses
// exactly the values `simplexRobustness` provides and nothing else, for any number of
// alternatives. `simplexPoint` stays in `lib/svg.ts` for a future exactly-three-
// alternative record — see the Task 7 report.

//
// Brand v3.0 (§5, §5a): the bars carry no Ember. v1.2 filled every bar with the accent,
// which lit one point per alternative on a screen allowed exactly one in total — and
// Compute asks nothing of a human, so its answer is none. Length already says which
// alternative held the most of the simplex; tone was never carrying that claim. The
// track is also fluid now (`fluidSvg`) rather than a fixed 160px, so it is legible at
// 360px and on a projector, and the caption is body text rather than mono: it is the
// kernel's sentence about the figure, not a numeral or an identifier.

import { barWidth, fluidSvg } from '../lib/svg';
import { Num } from './Num';

/** The track's own coordinate system, not a width on screen — `fluidSvg` turns it into a
 * `viewBox` and the browser scales it to the space the row gives. */
const TRACK_PX = 160;
const TRACK_H = 12;
// I1 (plan 07 Task 7 fix round): the denominator is 1 by definition —
// `simplexRobustness` is "the fraction of the simplex in which each alternative ranks
// first" (`render.py`'s own sentence, `demos/a_cbo_gcv_2013/out/package-full.md`), a
// share of `nSimplex` draws, not a value to be normalised against the largest fraction
// in this run. Normalising to the winner (the previous behaviour) drew a 0.526 share as
// a *full* bar — telling the reader the winner took every draw.
const DENOMINATOR = 1;

export interface SimplexProps {
  /** `ReadinessReport.flipSummary.simplexRobustness` (or the same field inline on a
   * fresh `POST .../dispatch` response's `flipSummaries[i]`) — `{alternative:
   * fraction}`, fractions summing to ~1 across the run's alternatives. */
  simplexRobustness: Record<string, number>;
  /** `flipSummary.simplexRobustnessText` (plan 07 Task 7 fix round, I2) — the API's own
   * `str()` form per alternative, preferred by `<Num>` over re-stringifying the parsed
   * float. */
  simplexRobustnessText?: Record<string, string>;
  nSimplex: number;
  seed: number;
  /** The object this `simplexRobustness` is provenance-attributed to (plan 07 Task 7
   * fix round, M3) — the `ReadinessReport` id when the summary came from `GET
   * .../readiness` (the case every committed fixture reaches), or the run id when it
   * arrived inline on a fresh `POST .../dispatch` response (no separate stored object
   * holds that copy yet). Never the run id when a readiness report id is available:
   * `simplexRobustness` lives on `ReadinessReport.flipSummary`, not on the run itself. */
  from: string;
}

export function Simplex({ simplexRobustness, simplexRobustnessText, nSimplex, seed, from }: SimplexProps) {
  const entries = Object.entries(simplexRobustness);
  if (entries.length === 0) {
    return <p className="text-b3 text-fg-muted">no simplex robustness on this run</p>;
  }

  return (
    <div className="flex flex-col gap-2" data-testid="simplex">
      {/* The kernel's own phrasing (`render.py`'s "fraction of the simplex in which
          each alternative ranks first"), not a screen-authored paraphrase — I1. */}
      <p className="text-b3 text-fg-secondary">
        weight simplex — fraction of the simplex in which each alternative ranks first
      </p>
      <ol className="flex flex-col gap-1.5">
        {entries.map(([alt, fraction]) => (
          // Wraps rather than overflows: at 360px the alternative id takes the first
          // line and the track and its value the second (§5a, "any row of controls
          // wraps"), and the track itself never grows past a width where an 8-unit-tall
          // bar would read as a block.
          <li key={alt} className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="og-mono text-b3 shrink-0 md:w-40">{alt}</span>
            <div className="min-w-[120px] max-w-[240px] flex-1">
              <svg {...fluidSvg(TRACK_PX, TRACK_H)} aria-hidden>
                <rect x={0} y={2} width={TRACK_PX} height={8} fill="none" stroke="var(--og-hairline-strong)" />
                {/* `--og-fg`, never Ember — see this file's header. */}
                <rect x={0} y={2} width={barWidth(fraction, DENOMINATOR, TRACK_PX)} height={8} fill="var(--og-fg)" />
              </svg>
            </div>
            <Num value={fraction} from={from} valueText={simplexRobustnessText?.[alt]} />
          </li>
        ))}
      </ol>
      {/* `n`/`seed` are the Monte Carlo draw's own identity, not an analytical value —
          same `data-num="label"` treatment as `RunSeal.tsx`'s seed/kernelVersion line;
          narrow spans around each digit-bearing token (fix round 1, M2), not the whole
          line. */}
      <p className="og-label text-m2 text-fg-secondary">
        n-simplex <span className="og-mono" data-num="label">{nSimplex}</span> · seed{' '}
        <span className="og-mono" data-num="label">{seed}</span>
      </p>
    </div>
  );
}
