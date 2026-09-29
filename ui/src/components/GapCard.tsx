// The first-class gap, rendered — never a blank cell. `InsufficientEvidence` (design
// spec, "First-class gap. Required fields make recording a gap more work-complete than
// inventing a value (PhantomFill)") is deliberately over-specified so that recording
// "we don't have this" takes four fields, not zero: `sought`, `whereLookedFor`,
// `whyNotFound`, `indicatorsThatWouldResolve` (plan Task 8 Screen 7: "sought · looked
// in · why not · would resolve"). This card prints exactly those four, plus `impact`,
// which is the one field a reader needs to know how much the gap matters.
//
// `fields` is `null` when the marker's `target` does not resolve in this graph (a
// hand-edited store, or a dangling id) — `ref-integrity`'s finding to report, not this
// component's to hide: it still names the id and says so, rather than rendering nothing.

import { HelpCircle } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import type { InsufficientEvidence } from '../types/objects';

export interface GapCardProps {
  id: string | null;
  fields: InsufficientEvidence | null;
}

export function GapCard({ id, fields }: GapCardProps) {
  return (
    <div className="border border-dashed border-hairline p-3 flex flex-col gap-1" data-slot="gap">
      {/* Card header: "gap" is a label, the id beside it is an identifier — §5's two
          faces, split at exactly that seam. `normal-case`/`tracking-normal` are gone
          from the id span: they existed only to undo the caps and tracking v1.2's
          `.og-mono` forced on, and v3.0's `.og-mono` forces neither. */}
      <p className="og-label text-b3 inline-flex flex-wrap items-center gap-2 text-fg-muted">
        {/* Smaller than the spec default: an inline card-header glyph. */}
        <HelpCircle {...ICON_PROPS} size={18} aria-hidden /> gap
        {id && <span className="og-mono text-m2">· {id}</span>}
      </p>
      {!fields ? (
        <p className="text-b2 text-fg-muted">
          the gap record{id ? <span className="og-mono text-m2"> {id}</span> : null} does not resolve in this
          graph
        </p>
      ) : (
        // Every `<dd>` below is verbatim record prose and routinely carries a page
        // number, a section mark or a quantity the model read in a source ("pp. 33–34",
        // "the 11 analytical efforts", "80% of MSRs"). None of it is a computed value, so
        // none of it is a `<Num>`; each value cell carries the numeral walk's label
        // carve-out instead, on the narrowest span that holds it (plan 07 Task 7 fix
        // round, C2 — applied here by Task 6, the first screen to put a real gap record
        // in front of the walk).
        <dl className="flex flex-col gap-1 text-b2">
          <div>
            <dt className="og-label text-b3 text-fg-muted">sought</dt>
            <dd data-num="label">{fields.sought}</dd>
          </div>
          <div>
            <dt className="og-label text-b3 text-fg-muted">looked in</dt>
            <dd data-num="label">{fields.whereLookedFor.join('; ')}</dd>
          </div>
          <div>
            <dt className="og-label text-b3 text-fg-muted">why not</dt>
            <dd data-num="label">{fields.whyNotFound}</dd>
          </div>
          <div>
            <dt className="og-label text-b3 text-fg-muted">would resolve</dt>
            <dd data-num="label">{fields.indicatorsThatWouldResolve.join('; ')}</dd>
          </div>
          {/* `impact` is a sentence the recorder wrote about how much the gap matters
              — prose, so body type rather than the numeral face (§5). */}
          <p className="text-b3 text-fg-secondary" data-num="label">
            {fields.impact}
          </p>
        </dl>
      )}
    </div>
  );
}
