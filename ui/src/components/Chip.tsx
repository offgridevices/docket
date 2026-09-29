// A small label — the building block every state chip in the app reuses (lifecycle
// state, LIVE|RECORDED, confidence). Density rule from the design spec §5: everything
// that isn't prose is a chip, a count, a cell or a glyph.
//
// v3.0 sets chips in Instrument Sans 500 (`og-label`), not mono: §5's typography roles
// give mono to "numerals, coordinates and code only", and a chip is a label. A caller
// whose chip content really is an identifier (a kernel version, an actor id, a mode)
// wraps that one value in its own `og-mono` span — the chip frame stays a label either
// way, so the mono is spent on the identifier rather than on the word beside it.

import type { ReactNode } from 'react';

export type ChipTone = 'muted' | 'fg' | 'accent';

const TONE_CLASS: Record<ChipTone, string> = {
  muted: 'text-fg-muted border-hairline',
  fg: 'text-fg border-hairline-strong',
  // `text-accent-text`, not `text-accent`: Ember (`--og-accent`, #FF6A00) as a
  // *foreground* colour fails contrast on the light ground, and the handoff ships
  // `--og-accent-text` (Ember-Deep) for exactly this case. Note this tone paints an
  // Ember *border*, never an Ember background — §5's "one Ember per surface" counts
  // fills, and a shared primitive must not be able to spend a screen's single fill.
  accent: 'text-accent-text border-accent',
};

export interface ChipProps {
  children: ReactNode;
  tone?: ChipTone;
  className?: string;
}

export function Chip({ children, tone = 'muted', className }: ChipProps) {
  return (
    <span
      className={`og-label text-b3 inline-flex items-center gap-1 border px-2 py-0.5 ${TONE_CLASS[tone]} ${className ?? ''}`}
    >
      {children}
    </span>
  );
}
