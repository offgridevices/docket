// The three-band "who may write what" figure — Figure 1 of the technical volume.
// Moved verbatim out of `AuthorityRail.tsx` (deleted with the old shell in the frame
// task) and exported, so the chat column's authority counters can open it as a sheet.
// The band titles are sentence case now: v3.0 takes authority from size, never caps.
//
// It is static because the *architecture* it draws does not change per episode; only
// the counters that open it do. No API value feeds it — but the geometry still lives in
// `lib/svg.ts` (`bandRect`, `stackedHeight`) rather than inline, so "SVG geometry is
// confined to one file" is true of the whole tree.

import { bandRect, stackedHeight } from '../lib/svg';

const BANDS = [
  {
    title: 'The AI proposes',
    detail: 'DRAFT objects · confidence: explicit / inferred / absent · never lifecycleState, never a Result',
    dashed: true,
  },
  {
    title: 'A person decides',
    detail: 'accept · reject · confirm gap · every gate transition (G1–G3)',
    dashed: false,
  },
  {
    title: 'The kernel computes',
    detail: 'EvaluationRun · Result · ReadinessReport · DecisionPackage · every numeral in the record',
    dashed: false,
  },
] as const;

const BAND_HEIGHT = 64;
const WIDTH = 720;

export function AuthorityDiagram() {
  const height = stackedHeight(BANDS.length, BAND_HEIGHT);

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${height}`}
      className="w-full max-w-3xl"
      role="img"
      aria-label="Authority diagram: the AI proposes, a person decides, the kernel computes"
    >
      <title>Who may write what</title>
      {BANDS.map((band, i) => {
        const rect = bandRect(i, BAND_HEIGHT, WIDTH);
        return (
          <g key={band.title}>
            <rect
              x={rect.x}
              y={rect.y}
              width={rect.width}
              height={rect.height}
              fill="none"
              stroke="var(--og-hairline-strong)"
              strokeDasharray={band.dashed ? '4 3' : undefined}
            />
            <text x={rect.textX} y={rect.titleY} className="og-mono" fontSize={12} fill="var(--og-fg)">
              {band.title}
            </text>
            <text x={rect.textX} y={rect.detailY} fontSize={12} fill="var(--og-fg-muted)">
              {band.detail}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
