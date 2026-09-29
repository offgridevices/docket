// The clock card (R23, spec §7): when it is due, where the time went, who it has been
// waiting on, and what the record flags about it. Every value is `kernel.clock`'s, and
// the only arithmetic on this screen is the strip's own pixel geometry (`lib/svg.ts`).
//
// Three places this card deliberately says less than it could:
//   - `dueIn`, `spanDays` and `remainingDays` are null together when the charter names
//     no deadline. The strip then runs to today rather than to a guessed end, and the
//     due line says so and offers the field, instead of inventing a date.
//   - the overdue line prints the kernel's own `overdue` flag sentence rather than
//     negating `dueIn` into a magnitude this file computed.
//   - a null `lastHumanAct` renders no numeral at all: nobody having acted is a fact
//     about the record, not a zero.
import { Calendar, Check, Clock, Inbox, OctagonAlert, TriangleAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../api/useWorkspace';
import { EXPECTED_TIME_NOTE } from '../frame/ExplainPanel';
import { ICON_PROPS } from '../lib/icons';
import { percentOf, sumOf } from '../lib/svg';
import type { ClockFlag, ClockResponse, Tone } from '../types/api';
import { Num } from './Num';

const SEG: Record<Tone, string> = { ok: 'bg-done-line', wait: 'bg-wait-line', stop: 'bg-stop-line' };
const TEXT: Record<Tone, string> = { ok: 'text-done', wait: 'text-wait', stop: 'text-stop' };
const FLAG_ICON: Record<string, typeof Clock> = { overdue: OctagonAlert, stuck: Clock, blocking: OctagonAlert, absences: TriangleAlert, refresh: Inbox, 'no-deadline': Calendar };

export const CLOCK_CAPTION = 'Times come from the record’s own log. The deadline and the expected time per stage are policy fields.';

function Flag({ flag }: { flag: ClockFlag }) {
  const navigate = useNavigate();
  const Icon = FLAG_ICON[flag.kind] ?? Clock;
  return (
    <div className="flex items-center gap-2 border-b border-hairline py-1.5 text-b3" data-flag={flag.kind}>
      <Icon {...ICON_PROPS} size={18} className={`shrink-0 ${flag.severity === 'ok' ? 'text-fg-muted' : TEXT[flag.severity]}`} aria-hidden />
      {/* The flag's own sentence, verbatim — the label carve-out, because the kernel
          wrote the number inside it ("No one has acted for 4884 days") and this card
          neither recomputes nor reformats it. */}
      <span className="min-w-0 flex-1" data-num="label">{flag.text}</span>
      <button type="button" onClick={() => navigate(flag.route)} className="og-label inline-flex min-h-11 min-w-11 items-center justify-center border border-hairline-strong px-2.5 text-b3">Go</button>
    </div>
  );
}

/** The clock card (R23): the due line, the time strip, the waiting line, the flags. */
export function ClockCard({ clock }: { clock: ClockResponse }) {
  const navigate = useNavigate();
  const { explain } = useWorkspace();
  const from = clock.episode;
  // The strip's whole: the span to the deadline where there is one, else the time the
  // record has actually been open — which is where the "today" mark then lands.
  const total = sumOf(clock.stages.map((s) => s.days));
  const span = clock.spanDays ?? total;
  const overdue = clock.flags.find((f) => f.kind === 'overdue') ?? null;
  // Read as the pair `kernel.clock` returns: a deadline the charter does not name has no
  // number of days left either, and neither is ever estimated. Taken together here so
  // the due line cannot reach a date branch with no date and print an empty bracket.
  const { deadline, dueIn } = clock;
  const last = clock.lastHumanAct;
  return (
    <section id="clock" className="min-w-0 border border-hairline-strong bg-raised p-4" aria-label="Clock">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="og-label inline-flex items-center gap-2 text-b2"><Clock {...ICON_PROPS} size={18} aria-hidden /> Clock</span>
        <span className="text-m1 text-fg-muted">{clock.current.plain}{explain && <span className="og-mono text-m2"> {clock.current.state}</span>}</span>
      </div>
      <p className="flex items-start gap-2 text-[clamp(18px,2vw,22px)] leading-snug" data-due>
        {deadline === null || dueIn === null ? (
          <><Calendar {...ICON_PROPS} size={20} className="mt-1 shrink-0" aria-hidden /><span>No deadline set{' '}
            <button type="button" onClick={() => navigate('/request?step=2')} className="og-label inline-flex min-h-11 min-w-11 items-center border border-hairline-strong px-2.5 align-middle text-b3">Set one</button></span></>
        ) : dueIn < 0 ? (
          <><OctagonAlert {...ICON_PROPS} size={20} className="mt-1 shrink-0 text-stop" aria-hidden />
            <span>{overdue && <span data-num="label">{overdue.text} · </span>}was due <Num value={deadline} from={from} /></span></>
        ) : (
          <><Calendar {...ICON_PROPS} size={20} className={`mt-1 shrink-0 ${clock.tone === 'wait' ? 'text-wait' : ''}`} aria-hidden /><span>Due <Num value={deadline} from={from} /> · in <Num value={dueIn} from={from} /> days</span></>
        )}
      </p>
      <div className="mt-3" data-strip>
        <div className="relative flex h-[18px] border border-hairline-strong bg-surface">
          {clock.stages.map((s) => (
            <span key={s.state} data-segment={s.state} data-running={s.running} data-tone={s.tone}
              title={`${s.plain} · ${s.days} days${s.expected ? ` · expected ${s.expected}` : ''}${s.running ? ' · still running' : ''}`}
              className={`h-full min-w-[4px] border-r border-raised ${SEG[s.tone]} ${s.running ? 'border-r-2 border-r-fg border-dashed' : ''}`}
              style={{ width: `${percentOf(s.days, span)}%` }} />
          ))}
          {clock.remainingDays !== null && clock.remainingDays > 0 && <span className="h-full" style={{ width: `${percentOf(clock.remainingDays, span)}%` }} title="to the deadline" />}
          {/* Today, and (when there is one) the deadline. Marks, not captions: the row
              below already names both dates, and a caption hung off a mark sitting at
              100% would be clipped by the view column's own overflow rule. */}
          <span className="absolute -bottom-1 -top-1 w-0 border-l-2 border-fg" style={{ left: `${percentOf(total, span)}%` }} title={`today ${clock.now}`} />
          {clock.deadline && <span className="absolute -bottom-1 -top-1 w-0 border-l-2 border-dotted border-fg" style={{ left: '100%' }} title={`due ${clock.deadline}`} />}
        </div>
        <div className="og-mono mt-2 flex justify-between text-m2 text-fg-muted">
          <span>opened <span data-num="label">{clock.openedAt.slice(0, 10)}</span></span>
          <span>{clock.deadline ? <>due <span data-num="label">{clock.deadline}</span></> : <>today <span data-num="label">{clock.now.slice(0, 10)}</span></>}</span>
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-3.5 gap-y-1">
          {clock.stages.map((s) => (
            <li key={s.state} className="inline-flex items-center gap-1.5 text-m1 text-fg-secondary" title={`expected ${s.expected || '—'} days`}>
              <span aria-hidden className={`inline-block h-2.5 w-2.5 ${SEG[s.tone]} ${s.running ? 'outline outline-2 outline-dashed -outline-offset-2 outline-fg' : ''}`} />
              {s.plain}{explain && <span className="og-mono text-m2"> {s.state}</span>} <Num value={s.days} from={from} /> d
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-3 flex items-start gap-2 text-b3" data-waiting>
        {clock.current.state === 'SIGNED' || !last ? (
          <><Check {...ICON_PROPS} size={16} className="mt-0.5 shrink-0 text-done" aria-hidden /><span>Nothing is waiting.</span></>
        ) : (
          <><Clock {...ICON_PROPS} size={16} className={`mt-0.5 shrink-0 ${clock.current.expected && last.daysAgo > clock.current.expected ? 'text-stop' : 'text-wait'}`} aria-hidden />
            {/* "a person", not a name: the clock knows when the record last moved and
                who moved it, and it does not know who owes the next act — the queue
                does, and says so on the card that asks for it. */}
            <span>Waiting on a person since <Num value={last.at.slice(0, 10)} from={from} /> · <Num value={last.daysAgo} from={from} /> days · last act: <span data-num="label">{last.what}</span>
              <span className="og-mono block text-m2 text-fg-secondary" data-model-id>{last.actorId}</span></span></>
        )}
      </p>
      <div className="mt-3 border-t border-hairline" data-flags>
        {clock.flags.length === 0 ? <div className="flex items-center gap-2 py-1.5 text-b3"><Check {...ICON_PROPS} size={18} className="text-done" aria-hidden />Nothing is overdue and nothing is stuck.</div>
          : clock.flags.map((f) => <Flag key={f.kind} flag={f} />)}
      </div>
      {explain && <p className="mt-2 border-l-2 border-hairline-strong bg-surface px-3 py-2 text-b3 text-fg-secondary">{EXPECTED_TIME_NOTE}</p>}
      <p className="mt-3 text-m1 text-fg-muted">{CLOCK_CAPTION}{clock.expectedSource === 'default' ? ' No policy field is set on this record; the kernel default is in use.' : ''}</p>
    </section>
  );
}
