// One object on the G1 board, and one object in the Intake stream — the same chip, since
// they are the same thing at two moments (the model has just proposed it; the model's
// proposal is now being reviewed).
//
// The frame, the glyph, the confidence and the locator are `Provenance`'s job, not this
// component's: every value the UI renders was written by exactly one actor and there is
// one implementation of saying so. What this adds is the object's identity line, its
// one-line summary, and a badge per gap/exclusion slot it carries.
//
// `extractor` is NOT rendered. It is on the object (`ingestionProvenance.extractor`) and
// it is in the payload, but it names the provider and model that produced the object —
// and honesty rule 3 confines those strings to the Settings slide-over and the raw-object
// drawer, which are not proposal-facing. The plan's own field tables for this chip list
// it; the honesty rule is the one marked "requirements, not guidance" and asserted by a
// test, so the rule wins and the Task 6 report records the divergence.
//
// A numeral inside a summary or a locator is never a `<Num>`: it is text the model read
// out of a source ("Option 3", "pp. 20–31", "80% of MSRs"), not a value anything
// computed, and the plan says so in as many words. The spans that hold it are marked
// `data-num="label"` — the narrowest span, per the T7 fix round's convention — and the
// chip's `title` states the distinction in words.

import type { ReactNode } from 'react';
import { HelpCircle, SquareMinus } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import type { AuthorType } from '../lib/provenance';
import { Provenance } from './Provenance';
import type { G1Slot } from '../types/api';

/** The sentence a hover reveals on every chip. Written once, here — it is the same
 * distinction on every object, and it is the reason none of this text is bracketed. */
export const NUMERAL_TITLE =
  'Verbatim from the record. A number in this text is something the model read in the source — not a value anything computed, so it is not shown in survey brackets.';

export interface ObjectChipProps {
  id: string;
  type: string;
  summary: string;
  authorType: AuthorType;
  confidence?: string | null;
  locator?: string | null;
  actorId?: string | null;
  slots?: G1Slot[];
  /** Rendered under the chip: the resolved gap and exclusion cards for `slots`. A slot is
   * content, a gap or an exclusion and never a blank cell, so the caller that can resolve
   * them passes them in rather than the chip pretending the field is empty. */
  children?: ReactNode;
  onOpen?: () => void;
}

export function ObjectChip({
  id,
  type,
  summary,
  authorType,
  confidence,
  locator,
  actorId,
  slots = [],
  children,
  onOpen,
}: ObjectChipProps) {
  const gapSlots = slots.filter((s) => s.kind === 'gap');
  const exclusionSlots = slots.filter((s) => s.kind === 'exclusion');

  return (
    <li data-object-id={id} data-object-type={type}>
      <Provenance authorType={authorType} confidence={confidence} locator={locator} actorId={actorId}>
        {/* An object id is an identifier, not a value — the numeral walk's helper has
            its own regex for exactly this shape, and marking the span says the same
            thing without depending on the id happening to sit next to whitespace in the
            serialised text. */}
        <p className="og-mono text-m2 text-fg-muted" data-num="label">
          {id}
        </p>
        {onOpen ? (
          // §5a: the glyph-sized text stays its size, the hit area grows to 44px. The
          // truncation moves onto the inner span, because a flex item is what clips
          // here now, not the button box itself.
          <button
            type="button"
            onClick={onOpen}
            title={`${summary}\n\n${NUMERAL_TITLE}`}
            className="text-b2 flex min-h-11 w-full min-w-0 items-center text-left underline underline-offset-4 decoration-hairline"
            data-num="label"
          >
            <span className="truncate">{summary}</span>
          </button>
        ) : (
          <p className="text-b2 truncate" title={`${summary}\n\n${NUMERAL_TITLE}`} data-num="label">
            {summary}
          </p>
        )}
        {(gapSlots.length > 0 || exclusionSlots.length > 0) && (
          <p className="mt-1 flex flex-wrap items-center gap-2 text-fg-muted">
            {gapSlots.map((slot) => (
              <span key={slot.path} className="og-mono text-m2 inline-flex items-center gap-1">
                {/* Smaller than the spec default: an inline badge glyph. */}
                <HelpCircle {...ICON_PROPS} size={14} aria-hidden />
                {slot.path}
              </span>
            ))}
            {exclusionSlots.map((slot) => (
              <span key={slot.path} className="og-mono text-m2 inline-flex items-center gap-1">
                <SquareMinus {...ICON_PROPS} size={14} aria-hidden />
                {slot.path}
              </span>
            ))}
          </p>
        )}
        {children}
      </Provenance>
    </li>
  );
}
