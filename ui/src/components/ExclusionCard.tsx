// The typed, first-class omission — "retainedInStructure: true" is the schema's own
// promise that leaving something out is recorded in the same place a value would have
// gone, not dropped from the document (design spec: "First-class omission.
// `time-or-resource` is PROHIBITED by default policy"). Plan Task 8 Screen 7: "reason
// type · reason · authority" — this card prints exactly those three, plus what was
// excluded and from where.
//
// `fields` is `null` when the marker's `target` does not resolve — same rule as
// GapCard: name the id and say so, never render nothing.

import { ShieldOff } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import type { Exclusion } from '../types/objects';

export interface ExclusionCardProps {
  id: string | null;
  fields: Exclusion | null;
}

export function ExclusionCard({ id, fields }: ExclusionCardProps) {
  return (
    <div className="border border-hairline-strong p-3 flex flex-col gap-1" data-slot="exclusion">
      {/* Card header: "exclusion" is a label, the id beside it is an identifier (§5).
          The old `normal-case tracking-normal` pair on the id undid the caps and
          tracking v1.2's `.og-mono` forced; v3.0's `.og-mono` forces neither, so they
          are dropped rather than left as a no-op. */}
      <p className="og-label text-b3 inline-flex flex-wrap items-center gap-2 text-fg-muted">
        {/* Smaller than the spec default: an inline card-header glyph. */}
        <ShieldOff {...ICON_PROPS} size={18} aria-hidden /> exclusion
        {id && <span className="og-mono text-m2">· {id}</span>}
      </p>
      {!fields ? (
        <p className="text-b2 text-fg-muted">
          the exclusion record{id ? <span className="og-mono text-m2"> {id}</span> : null} does not resolve in
          this graph
        </p>
      ) : (
        <dl className="flex flex-col gap-1 text-b2">
          <div>
            <dt className="og-label text-b3 text-fg-muted">reason type</dt>
            <dd className="og-mono text-b3">{fields.reasonType}</dd>
          </div>
          {/* `reason`, the authority's date and the target label are verbatim record
              prose and citations ("MIL-STD-3022 §5.3", "four of the Army's eight AoA
              categories") — the same label carve-out `GapCard` applies, narrowest span,
              added by plan 07 Task 6 for the same reason. */}
          <div>
            <dt className="og-label text-b3 text-fg-muted">reason</dt>
            <dd data-num="label">{fields.reason}</dd>
          </div>
          <div>
            <dt className="og-label text-b3 text-fg-muted">authority</dt>
            <dd data-num="label">
              {fields.authority.who} ({fields.authority.role}), {fields.authority.date}
            </dd>
          </div>
          <div>
            <dt className="og-label text-b3 text-fg-muted">target</dt>
            <dd data-num="label">
              {fields.target.kind} · {fields.target.label}
            </dd>
          </div>
        </dl>
      )}
    </div>
  );
}
