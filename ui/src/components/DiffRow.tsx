// One line of an `EpisodeDiff`'s content (plan Task 8 Screen 8). `EpisodeDiff.changed[]`
// pairs a field's before/after value; `added[]`/`removed[]`/`judgmentsConsistent[]` are
// bare object ids with no paired value. One component for all four shapes, because a
// reader scanning a diff wants one visual rhythm, not three different row layouts.
//
// Every string here is verbatim, kernel- or agent-authored text copied straight from the
// diff object and rendered exactly as recorded — but "verbatim" and "mono" are not the
// same claim. §5 gives mono to identifiers and code, so the object id and the field path
// keep it; `before`/`after` are a field's own *content* (a charter question, a citation),
// which is prose, and the kind ("changed", "added") is a label. Those move to the body
// and label faces.
//
// §5a's stacked treatment: below 768 px the three parts stack as a label-over-value card,
// and at 768 px and up they sit on one baseline as a table row.

import type { ReactNode } from 'react';

export type DiffRowKind = 'changed' | 'added' | 'removed' | 'consistent';

const KIND_LABEL: Record<DiffRowKind, string> = {
  changed: 'changed',
  added: 'added',
  removed: 'removed',
  consistent: 'consistent',
};

const KIND_CLASS: Record<DiffRowKind, string> = {
  changed: 'text-fg',
  added: 'text-fg',
  removed: 'text-fg-muted line-through decoration-1',
  consistent: 'text-fg-muted',
};

export interface DiffRowProps {
  kind: DiffRowKind;
  id: string;
  field?: string;
  before?: string;
  after?: string;
  /** Fields (§12) can put away the object id on a row that says something without it —
   * a `changed` row, where the field path and its before/after are the change. Default
   * on, and the caller never turns it off for `added`/`removed`/`consistent`, whose
   * whole content is the id. */
  showId?: boolean;
}

export function DiffRow({ kind, id, field, before, after, showId = true }: DiffRowProps): ReactNode {
  return (
    <li className="flex flex-col gap-0.5 border-b border-hairline py-1.5 last:border-b-0 md:flex-row md:items-baseline md:gap-3">
      <span className="og-label text-b3 text-fg-muted md:w-20 md:shrink-0">{KIND_LABEL[kind]}</span>
      {showId && <span className={`og-mono text-m1 break-words min-w-0 ${KIND_CLASS[kind]}`}>{id}</span>}
      {kind === 'changed' && field && (
        <span className="text-b3 text-fg-secondary min-w-0 break-words">
          <span className="og-mono text-m2">{field}</span>:{' '}
          {/* `before`/`after` are a field's own verbatim content (a Charter's
              `question`, a citation, ...) copied straight off the diff object — quoted
              record content, the same category every other extracted-prose field in
              this app already is, not a value a reader would compute with (plan 07
              Task 9 Part B found "Section 234" — a statutory citation inside a
              charter question — unmarked here). */}
          <span data-num="label">
            {before ?? '_[unavailable]_'} → {after ?? '_[unavailable]_'}
          </span>
        </span>
      )}
    </li>
  );
}
