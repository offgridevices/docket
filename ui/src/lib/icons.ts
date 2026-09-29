// Shared Lucide icon defaults (design spec §5: "24 px, 1.5 px stroke,
// `stroke-linecap: butt`, monochrome `currentColor`, never two colours"). Lucide's own
// default is a *round* linecap, which fights the brand's radius-0 rule and was applied
// nowhere in the app until this file existed (plan 07 Task 5 fix round 1, M2) — every
// call site spread the size/stroke props but never the cap, so every glyph in the SSR
// probe came back `stroke-linecap="round"`.
//
// Size is deliberately smaller than 24px at a few call sites — a corner glyph on a
// dense card, a small header control — and that is a legitimate per-context choice the
// spec doesn't forbid; what it does forbid is an unexamined default. Spread this object
// first, then override `size` explicitly, so every deviation is visible in the diff
// rather than a bare number.

export const ICON_PROPS = {
  size: 24,
  strokeWidth: 1.5,
  strokeLinecap: 'butt' as const,
};
