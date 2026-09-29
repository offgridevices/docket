import type { AuthorType } from '../lib/provenance';
import { Num } from './Num';
import { Term } from './Term';

/** One drafted or agreed object (R19): a state chip, the title, the fields Fields
 * asked for, one act. Provenance: dashed blue diamond = drafted by the AI; filled
 * green square = agreed by a person.
 *
 * `linchpin` is the queue's reading, not a field of this object on the sheet: it marks
 * an assumption the answer depends on that no person has read yet, which is exactly
 * what `kernel.queue.needs` reports and what the gate's `linchpins-human` check wants. */
export function ObjectCard({ id, type, title, authorType, confidence, locator, actorId, rev, linchpin = false, fields, act, onOpen, onRaw }: {
  id: string; type: string; title: string; authorType: AuthorType; confidence?: string | null; locator?: string | null;
  actorId?: string | null; rev?: number; linchpin?: boolean; fields: Record<string, boolean>; act: string; onOpen: () => void; onRaw?: () => void;
}) {
  const agent = authorType === 'agent';
  return (
    <div className={`flex min-w-0 flex-col gap-2 border bg-raised p-3 ${agent ? 'border-dashed border-ai-line' : 'border-hairline-strong'}`} data-object-id={id} data-object-type={type} data-linchpin={linchpin ? 'true' : undefined}>
      <div className="flex flex-wrap items-center gap-2">
        <span aria-hidden className={`inline-block h-2.5 w-2.5 border ${agent ? 'rotate-45 border-dashed border-ai' : 'border-done bg-done'}`} data-mark={agent ? 'agent-proposed' : 'human-accepted'} />
        <span className={`og-label inline-flex min-h-8 items-center border px-2 text-b3 ${agent ? 'border-dashed border-ai-line bg-ai-tint text-ai' : 'border-done-line bg-done-tint text-done'}`}>{agent ? <Term k="draft" /> : <Term k="accepted" />}</span>
        {linchpin && <span className="og-label inline-flex min-h-8 items-center border border-fg px-2 text-b3"><Term k="linchpin" /></span>}
      </div>
      <p className="text-b3 leading-snug" data-num="label">{title}</p>
      <div className="flex flex-wrap gap-1.5 text-m2">
        {fields.id && <span className="og-mono break-words border border-hairline px-1.5" data-num="label">{id}</span>}
        {fields.page && locator && <span className="border border-hairline px-1.5" data-num="label"><Term k="locator" plain={`page ${locator}`} /></span>}
        {fields.confidence && confidence && <span className="og-mono border border-hairline px-1.5">{confidence}</span>}
        {fields.agreed && <span className="og-mono break-words border border-hairline px-1.5" data-model-id>{agent ? 'nobody yet' : actorId ?? '—'}</span>}
        {fields.rev && rev !== undefined && <span className="og-mono border border-hairline px-1.5">rev <Num value={rev} from={id} /></span>}
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onOpen} className="og-label inline-flex min-h-11 items-center border border-hairline-strong px-3 text-b3">{act}</button>
        {onRaw && <button type="button" onClick={onRaw} className="og-label inline-flex min-h-11 items-center text-b3 underline underline-offset-4">Open the stored object</button>}
      </div>
    </div>
  );
}
