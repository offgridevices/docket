import { Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Num } from '../components/Num';
import { ICON_PROPS } from '../lib/icons';
import type { ClockResponse, NeedsResponse } from '../types/api';

/** Who the decision is waiting on, in a word: "you" for a reviewer's act, else the
 * queue's own phrase before its first comma or dash. */
export function waitingOn(needs: NeedsResponse | null, state: string | null): string {
  if (state === 'SIGNED') return 'nobody';
  const first = needs?.items.find((i) => i.actionable);
  if (!first) return 'nobody';
  if (/^you\b/.test(first.waitingOn)) return 'you';
  return first.waitingOn.split(/ — |, |;/)[0];
}

/**
 * When it is due and who it has been waiting on — every part of it a value the server
 * sent, printed as it arrived.
 *
 * Nothing here is derived. The overdue case prints `kernel.clock`'s own `overdue` flag
 * sentence ("Overdue by 12 days") rather than negating `dueIn` into a magnitude this
 * file invented, and the waiting clause is rendered only when the record actually holds
 * a last human act — a null is a fact about the record, not a zero.
 *
 * Below 520 px the chip keeps its words and drops its numerals: a clock glyph beside a
 * bare bracketed number tells a reader nothing about what was counted.
 */
export function TimeChip({ clock, needs, episodeState }: { clock: ClockResponse; needs: NeedsResponse | null; episodeState: string | null }) {
  const navigate = useNavigate();
  const tone = clock.tone;
  const line = tone === 'stop' ? 'border-stop-line' : tone === 'wait' ? 'border-wait-line' : 'border-hairline-strong';
  const glyph = tone === 'stop' ? 'text-stop' : tone === 'wait' ? 'text-wait' : 'text-fg-muted';
  const from = clock.episode;
  const overdue = clock.flags.find((f) => f.kind === 'overdue') ?? null;
  const last = clock.lastHumanAct;
  return (
    <button type="button" onClick={() => navigate('/#clock')} data-tone={tone} aria-label="When it is due and who it waits on"
      title="When it is due, and who it has been waiting on. Opens the clock card."
      className={`status__time og-mono text-m1 inline-flex min-h-11 flex-wrap items-center gap-2 border bg-canvas px-2.5 text-fg-secondary ${line}`}>
      <Clock {...ICON_PROPS} size={16} className={glyph} aria-hidden />
      {clock.dueIn === null ? <span>no deadline</span>
        : overdue ? (
          <>
            <span className="only-below-520">overdue</span>
            {/* The kernel's own sentence, verbatim — the label carve-out, the same one
                Home takes for `kernel.render`'s ready line. */}
            <span className="hide-below-520" data-num="label">{overdue.text}</span>
          </>
        ) : (
          <>
            <span className="only-below-520">due {clock.deadline}</span>
            <span className="hide-below-520">due in <Num value={clock.dueIn} from={from} /> d</span>
          </>
        )}
      {episodeState === 'SIGNED' ? <span>signed</span>
        : last ? (
          <>
            <span className="only-below-520">waiting</span>
            {/* The phrase sheds words as the room runs out, widest first: who it waits on
                is the longest part of the chip and the first thing to go below 1280. */}
            <span className="hide-below-520">
              waiting<span className="hide-below-1280"> on {waitingOn(needs, episodeState)}</span>{' '}
              <Num value={last.daysAgo} from={from} /> d
            </span>
          </>
        ) : null}
    </button>
  );
}
