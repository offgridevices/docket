// The three provenance marks, one implementation (design spec §5; plan Task 5 Step 4).
// Every value the UI renders was written by exactly one actor, and the mark says which:
//
//   agent-proposed   1px dashed hairline · circle-dashed glyph · confidence chip + locator
//   human-accepted   1px solid hairline-strong · user-check glyph · actorId
//   kernel-computed  no border, the value carries it · cpu glyph in the eyebrow
//
// This component only decides *how to frame* content that has already been fetched —
// it does not fetch, and it does not compute; `children` is whatever the caller already
// has (usually a <Num> for a kernel-computed value, or plain text for an agent/human one).

import type { ReactNode } from 'react';
import { CircleDashed, Cpu, UserCheck } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import { markOf, type AuthorType, type Mark } from '../lib/provenance';
import { confidenceLabel, markLabel } from '../lib/format';

const FRAME_CLASS: Record<Mark, string> = {
  'agent-proposed': 'border border-dashed border-hairline',
  'human-accepted': 'border border-solid border-hairline-strong',
  'kernel-computed': 'border-0',
};

const GLYPH: Record<Mark, typeof CircleDashed> = {
  'agent-proposed': CircleDashed,
  'human-accepted': UserCheck,
  'kernel-computed': Cpu,
};

export interface ProvenanceProps {
  authorType: AuthorType;
  confidence?: string | null;
  locator?: string | null;
  actorId?: string | null;
  children: ReactNode;
  className?: string;
}

export function Provenance({ authorType, confidence, locator, actorId, children, className }: ProvenanceProps) {
  const mark = markOf({ authorType });
  const Glyph = GLYPH[mark];

  return (
    <div className={`relative p-4 ${FRAME_CLASS[mark]} ${className ?? ''}`} data-mark={mark}>
      <span className="absolute right-3 top-3 text-fg-muted" aria-hidden>
        {/* Smaller than the spec's 24px default: a corner glyph on a dense card. */}
        <Glyph {...ICON_PROPS} size={16} />
      </span>
      {/* The mark is otherwise a purely visual signal (border style, corner glyph) —
          this gives it an accessible name too. */}
      <span className="sr-only">{markLabel(mark)}</span>
      {children}
      {mark === 'agent-proposed' && (
        <p className="text-m2 text-fg-muted mt-2">
          <span className="og-mono">{confidenceLabel(confidence)}</span>
          {locator ? (
            <>
              {' · '}
              {/* A locator is a verbatim citation into a source ("pp. 20–31",
                  "printed p. 14 (PDF p. 17)"). Its digits are page numbers the model
                  copied, not a value anything computed, so the span carries the
                  numeral walk's own label carve-out (plan 07 Task 7 fix round, C2:
                  label marks on verbatim prose, dates and citations, narrowest span).
                  Added by Task 6, whose G1 board is the first screen to render a
                  locator that has one — the mark can only remove text from the walk,
                  never add any, so no earlier screen's spec changes behaviour.

                  Not mono under v3.0 (§5: "if a string is neither a number nor an
                  identifier nor code, it is not mono"). A citation is prose that
                  happens to contain page numbers, not an identifier — the reason it
                  needs the label carve-out in the first place is the reason it is not
                  set in the numeral face. */}
              <span data-num="label">{locator}</span>
            </>
          ) : null}
        </p>
      )}
      {mark === 'human-accepted' && actorId && (
        // `data-model-id` (plan 07 Task 10's masking rule): an actor id is `actorType:
        // actorId`'s id half, and for an agent-authored object that string is built from
        // the configured model id (`api.config.agent_actor_for_settings`). On the
        // committed demo stores every one of these is a human ("shreyash"), but the
        // attribute marks the element that COULD carry a model name so the documentation
        // figures paint a solid box over it instead of printing one — the ledger's
        // standing ruling, "no concrete model name anywhere in published copy".
        <p className="og-mono text-m2 text-fg-muted mt-2" data-model-id>
          {actorId}
        </p>
      )}
    </div>
  );
}
