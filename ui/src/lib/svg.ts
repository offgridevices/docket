// The one file in `ui/src` allowed to do arithmetic on a value that came from the API
// (see "Honesty and safety in the UI" #1 in the plan). Every other component only ever
// copies a string or number it received — no `toFixed`, no unit conversion, no percentage
// math. Here, and only here, a value already computed and rounded by the kernel is turned
// into a *pixel position* so an SVG can be drawn; the value on screen (inside a `<Num>`)
// is still the untouched string the API sent. Task 7's hand-drawn charts (the flip curve,
// the weight simplex, the readiness grid) are the callers; nothing in Task 5 draws a
// data-driven chart yet, so this module is intentionally small until then.

/** Clamp `v` into `[lo, hi]`. Used before scaling anything to pixels so a value just
 * outside its documented range (a rounding artefact, a 100.00001%) can't push a bar off
 * the edge of its track. */
export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** Linear map from a value's own range `[domainMin, domainMax]` to a pixel span
 * `[0, trackPx]`, clamped at both ends. This is geometry, not a claim about the value —
 * the number itself is never displayed from here. */
export function scaleToTrack(
  value: number,
  domainMin: number,
  domainMax: number,
  trackPx: number,
): number {
  if (domainMax === domainMin) return 0;
  const t = clamp((value - domainMin) / (domainMax - domainMin), 0, 1);
  return t * trackPx;
}

/** Geometry for the `i`th band of a fixed-height stacked diagram — e.g.
 * `AuthorityRail`'s three-band "who may write what" figure. No API value is involved
 * here (the diagram is static architecture, not per-episode data), but honesty rule #1
 * says SVG geometry is *confined* to this file, and the band maths used to live inline
 * in `AuthorityRail.tsx` — moved here (plan 07 Task 5 fix round 1, M1) so that claim is
 * enforceable by a lint rule scoped to this path, not just true by inspection. */
export interface BandRect {
  x: number;
  y: number;
  width: number;
  height: number;
  textX: number;
  titleY: number;
  detailY: number;
}

export function bandRect(i: number, bandHeight: number, width: number): BandRect {
  const y = i * bandHeight;
  return {
    x: 0.5,
    y: y + 0.5,
    width: width - 1,
    height: bandHeight - 1,
    textX: 16,
    titleY: y + 26,
    detailY: y + 46,
  };
}

/** Total diagram height for `count` stacked bands of `bandHeight` each. */
export function stackedHeight(count: number, bandHeight: number): number {
  return count * bandHeight;
}

// ---- Task 7: Compute and Readiness charts ---------------------------------------------
//
// Added by plan 07 Task 7 (not in that task's listed file ownership, but the plan's own
// Step 1 assigns exactly these four primitives to this file, and the honesty rule above
// requires every pixel computation to live here rather than spread across FlipChart.tsx /
// Simplex.tsx / StateGrid.tsx — see the Task 7 report for the deviation note). Purely
// additive: nothing above this line changed.

/** Bar length for one alternative's `Result.value` against the largest value in the
 * SAME response (`max` — never a computed total, a percentage or a sum across runs).
 * `barWidth(v, max, px) === scaleToTrack(v, 0, max, px)`, spelled out under the plan's
 * own name for this specific chart (Compute Screen 5, "Ranking and results"). */
export function barWidth(v: number, max: number, px: number): number {
  return Math.round(scaleToTrack(v, 0, max, px));
}

/** The largest of `values` — the *only* place `Math.max` over API-sourced numbers is
 * allowed to run, so a chart component itself never reduces an array of `value`s (which
 * the honesty rule's lint pattern targets by name). Returns 0 for an empty array so a
 * caller can pass it straight to `barWidth` without a separate empty-array branch. */
export function maxOf(values: number[]): number {
  return values.length === 0 ? 0 : Math.max(...values);
}

/** Where a flip threshold or a run's current value sits along a parameter's own `range`
 * (`FlipAnalysis.range`), scaled to a track `px` wide. `thresholdX(t, [lo,hi], px) ===
 * scaleToTrack(t, lo, hi, px)`; kept as its own name because the plan's Step 1 names it
 * and a `FlipChart` row reads better calling `thresholdX` twice (current, threshold)
 * than `scaleToTrack` twice with the range spread out at each call site. */
export function thresholdX(t: number, [lo, hi]: [number, number], px: number): number {
  return Math.round(scaleToTrack(t, lo, hi, px));
}

/** Unused; see `Simplex.tsx`'s own header for why (fix round 1, M8: kept rather than
 * dropped, per the plan's own Step 1 assignment, for a future exactly-three-alternative
 * record — not a projection any current caller is invited to reach for).
 *
 * Barycentric point inside an equilateral triangle of side `side` for a three-part
 * weight `w` (three numbers summing to ~1 — e.g. three `simplexRobustness` fractions, or
 * three measure weights). Triangle apex up: `v0`/`v1` are the bottom-left/bottom-right
 * corners, `v2` the apex, laid out in a `[0, side] x [0, triangleHeight]` box so a caller
 * can size an `<svg viewBox="0 0 side triangleHeight">` around it directly.
 *
 * Only meaningful for exactly three parts — `Simplex.tsx` uses this for a three-
 * alternative run and falls back to a bar per alternative otherwise (see its own header
 * comment): a triangle has three corners, and stretching a fourth or fifth weight onto
 * one of them would not be a value the server gave us, it would be a projection this
 * file invented. */
export function simplexPoint(w: [number, number, number], side: number): [number, number] {
  const triangleHeight = (side * Math.sqrt(3)) / 2;
  const v0: [number, number] = [0, triangleHeight];
  const v1: [number, number] = [side, triangleHeight];
  const v2: [number, number] = [side / 2, 0];
  const [w0, w1, w2] = w;
  return [
    w0 * v0[0] + w1 * v1[0] + w2 * v2[0],
    w0 * v0[1] + w1 * v1[1] + w2 * v2[1],
  ];
}

// ---- brand v3.0: every drawn thing is fluid ------------------------------------------
//
// §5a ("Layout: fluid to 360 px") makes a fixed `width`/`height` on an `<svg>` a defect:
// a chart drawn at a hardcoded 140px is 140px on a 4K projector and 140px on a 360px
// phone, which is either invisible or an overflow. The fix is the same three properties
// every time — a `viewBox` that carries the drawing's own coordinate system, `width:
// 100%` so the element takes the space its column gives it, and `height: auto` so the
// aspect ratio survives. Spelled once here rather than at each call site so a chart
// cannot be added later with only two of the three.
//
// This is not arithmetic on an API value: it hands the browser the same numbers the
// drawing already used, in the attribute that makes them relative rather than absolute.

export interface FluidSvgProps {
  viewBox: string;
  style: { width: string; height: string };
}

/** `viewBox` + fluid sizing for a drawing laid out in a `width` x `height` box. The
 * aspect ratio is left at SVG's default (`xMidYMid meet`), so a track that gets wider
 * also gets proportionally taller and every stroke, dot and bar end stays the shape it
 * was drawn as — a stretched `preserveAspectRatio="none"` would turn the run marker on
 * a flip track into an ellipse the moment the column widened. */
export function fluidSvg(width: number, height: number): FluidSvgProps {
  return {
    viewBox: `0 0 ${width} ${height}`,
    style: { width: '100%', height: 'auto' },
  };
}

export interface CellRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Unused; see `StateGrid.tsx`'s own header for why (fix round 1, M8: kept rather than
 * dropped, per the plan's own Step 1 assignment — `StateGrid` lays the grid out with
 * CSS grid utilities instead, for native hover/focus/`title` semantics).
 *
 * Grid cell rect for question index `i` in a fixed-`cols`-wide grid of `size`x`size`
 * cells with `gap` spacing between them — the readiness grid's 36 questions, laid out
 * left to right, top to bottom, in the array order the server sent (this function reads
 * only `i`, `cols`, `size`, `gap`; it never reorders anything). */
export function cellRect(i: number, cols: number, size: number, gap: number): CellRect {
  const col = i % cols;
  const row = Math.floor(i / cols);
  const stride = size + gap;
  return { x: col * stride, y: row * stride, width: size, height: size };
}

// ---- Task 8: the clock card's time strip ---------------------------------------------

/** The whole a strip is drawn against, from the parts it is drawn from. The clock's
 * `spanDays` is null whenever the charter names no deadline (`kernel.clock`: "with no
 * deadline there is no honest number for how much time is left"), and the card then
 * draws an open-ended strip that runs to today — whose length is the sum of the stage
 * days the server already computed. That sum is arithmetic on API values, so it lives
 * here with every other one rather than inside the card, and it is never printed: each
 * stage still shows its own `days` through `<Num>`. */
export function sumOf(values: number[]): number {
  return values.reduce((total, v) => total + v, 0);
}

/** A segment's share of a strip, 0–100 with one decimal — layout only; the days
 * themselves are printed beside the strip through `<Num>`. */
export function percentOf(part: number, whole: number): number {
  if (whole <= 0) return 0;
  return Math.round(clamp(part / whole, 0, 1) * 1000) / 10;
}
