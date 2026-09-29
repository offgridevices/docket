// The classification block on an Evidence row: `stamp` glyph for the level, `eye-off`
// when this rendering has withheld a value because of it (plan Task 8 Screen 7). A
// demo-only banner elsewhere on the page already says these levels are schema fields,
// not real markings (Honesty and safety in the UI #4) — this component only displays
// what the record says, it never claims a marking.
//
// Type roles (§5): the chip frame and the word "meta" are labels (`og-label`); the
// level, the metadata level, the controlling authority and the caveats are the record's
// own closed marking tokens, which is what mono is for.

import { EyeOff, Stamp } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import type { Evidence } from '../types/objects';

export interface ClassificationChipProps {
  classification: Evidence['classification'];
  /** True when `_withhold_evidence_fields` has substituted a `[withheld: <level>]`
   * marker for one or more of this row's other fields *because of* this classification
   * — the glyph that says "a value here is hidden at this rendering". */
  withheld?: boolean;
}

export function ClassificationChip({ classification, withheld = false }: ClassificationChipProps) {
  const metaDiffers = classification.metadataLevel !== classification.level;
  return (
    <span className="inline-flex flex-col gap-0.5">
      <span className="og-label text-b3 inline-flex flex-wrap items-center gap-1 border border-hairline-strong px-2 py-0.5 w-fit">
        {/* Smaller than the spec default: an inline chip glyph. */}
        <Stamp {...ICON_PROPS} size={14} aria-hidden />
        <span className="og-mono text-m2">{classification.level}</span>
        {metaDiffers && (
          <span className="text-fg-muted">
            / meta <span className="og-mono text-m2">{classification.metadataLevel}</span>
          </span>
        )}
        {withheld && (
          <>
            {/* Not Ember. "A value is withheld at this rendering" is information, not a call
                on a human, and a register can have many withheld rows — Ember here lit an
                unbounded number of points on screens whose §5 answer is "none". The glyph
                plus its sr-only sentence carry the meaning without the accent. */}
            <EyeOff {...ICON_PROPS} size={14} className="text-fg-secondary" aria-hidden />
            <span className="sr-only">a value on this row is withheld at this rendering</span>
          </>
        )}
      </span>
      {(classification.caveats?.length || classification.controlledBy) && (
        <span className="og-mono text-m2 text-fg-muted">
          {classification.controlledBy}
          {classification.controlledBy && classification.caveats?.length ? ' · ' : ''}
          {classification.caveats?.join(', ')}
        </span>
      )}
    </span>
  );
}
