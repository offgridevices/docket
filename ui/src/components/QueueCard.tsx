// One row of "what needs you" (R7/R19), as a card: the record's own sentence, an age
// chip, whichever optional fields the reader has asked for, and exactly one button.
//
// The card computes nothing. The age it shows is `NeedsItem.ageDays`; the tone that age
// wears is the kernel's own tone for the stage the age was measured over, not a
// threshold this file invented.
import { useNavigate } from 'react-router-dom';
import type { ClockResponse, NeedsItem } from '../types/api';
import { Num } from './Num';
import { StateGlyph } from './StateGlyph';

export const BUTTON_LABEL: Record<string, string> = {
  'linchpin-unreviewed': 'Read it', 'gap-unconfirmed': 'Confirm it', 'charter-field-empty': 'Write the field',
  'gate-1': 'Approve the model', 'weights-unsaved': 'Write the weights', 'plan-unproposed': 'Ask for a plan',
  'plan-unapproved': 'Read the plan', 'gate-2': 'Approve the plan', dispatch: 'Send it to be computed',
  readiness: 'Score the record', 'blocking-finding': 'Read the finding', 'package-unrendered': 'Render the package',
  signature: 'Open the package', 'sent-back': 'Open the package', 'refresh-proposed': 'Open the refresh',
};

const AGE_TONE: Record<string, string> = {
  ok: '', wait: 'border-wait-line text-wait bg-wait-tint', stop: 'border-stop-line text-stop bg-stop-tint',
};

/** One queue card (R7/R19): a plain sentence, who it waits on, an age chip, one button.
 *
 * There is one kind of "not yet" row and the record decides it: `actionable: false` with
 * the server's own `unlocksAfter`. That covers a stage nobody has reached yet and a
 * signature a send-back is holding up alike — this file no longer holds a pairing of its
 * own, so `data-actionable` and what the card draws can never come apart. */
export function QueueCard({ item, ember, fields, clock }: { item: NeedsItem; ember: boolean; fields: Record<string, boolean>; clock: ClockResponse | null }) {
  const navigate = useNavigate();
  const age = item.ageDays;
  // Where the age is the running stage's own days — the common case, since most items
  // are dated from the moment the record entered the stage — the chip wears the tone
  // `kernel.clock` already gave that stage. Otherwise it says only "past the expected
  // days", which is a comparison, not a threshold.
  const running = clock?.stages[clock.stages.length - 1] ?? null;
  const expected = clock?.current.expected ?? 0;
  const tone = age === null ? 'ok'
    : running && age === running.days ? running.tone
      : expected && age > expected ? 'wait' : 'ok';
  if (!item.actionable) {
    return (
      <div className="grid gap-4 border border-hairline p-4 md:grid-cols-[1fr_auto]" data-queue-card data-kind={item.kind} data-actionable="false">
        <div><p className="text-b1 leading-snug text-fg-muted" data-num="label">{item.text}</p>
          <p className="mt-2"><span className="og-label inline-flex min-h-8 items-center border border-hairline px-2 text-b3">unlocks once {item.unlocksAfter}</span></p></div>
        <span className="inline-flex items-center gap-1.5 text-b3 text-fg-muted"><StateGlyph kind="doing" /> not yet</span>
      </div>
    );
  }
  return (
    <div className="grid gap-4 border border-hairline-strong bg-raised p-4 md:grid-cols-[1fr_auto]" data-queue-card data-kind={item.kind} data-actionable="true" data-object-id={item.objectId ?? undefined}>
      <div className="min-w-0">
        <p className="text-b1 leading-snug" data-num="label">{item.text}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-b3">
          {age !== null && <span className={`og-mono inline-flex min-h-8 items-center border px-2 text-m2 ${AGE_TONE[tone] || 'border-hairline'}`} data-age title="Since this became actionable; the stage's own days where nothing finer is recorded.">waiting <Num value={age} from={item.objectId ?? 'needs'} /> d</span>}
          {fields.count && item.count !== null && <span className="og-label inline-flex min-h-8 items-center border border-hairline px-2" data-count><Num value={item.count} from={item.objectId ?? 'needs'} /> of this kind</span>}
          {fields.where && item.objectId && <span className="og-mono inline-flex min-h-8 items-center border border-hairline px-2 text-m2" data-field="where" data-num="label">{item.objectId}</span>}
          {fields.stage && <span className="og-label inline-flex min-h-8 items-center border border-hairline px-2" data-field="stage">{item.route}</span>}
          {fields.who && <span className="text-fg-muted" data-field="who">waiting on {item.waitingOn}</span>}
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <button type="button" onClick={() => navigate(item.route)} data-ember={ember ? '' : undefined}
          className="og-label inline-flex min-h-11 items-center justify-center border border-hairline-strong px-4 text-b3">
          {BUTTON_LABEL[item.kind] ?? 'Go'}
        </button>
      </div>
    </div>
  );
}
