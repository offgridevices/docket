// The two persistent header cards (R15/R24): the only prose that carries colour.
import type { LucideIcon } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import { Num } from '../components/Num';

export function Counter({ label, count, tone, icon: Icon, onClick, title, from }: {
  label: string; count: number; tone: 'act' | 'stop'; icon: LucideIcon; onClick: () => void; title: string; from: string;
}) {
  const lit = count > 0;
  const colour = tone === 'act' ? 'text-act-text' : 'text-stop';
  const line = tone === 'act' ? 'border-act-line' : 'border-stop-line';
  return (
    <button type="button" onClick={onClick} title={title} data-counter={tone}
      className={`og-label inline-flex min-h-11 items-center gap-2 border bg-canvas px-3 text-b3 ${lit ? line : 'border-hairline-strong'}`}>
      <Icon {...ICON_PROPS} size={16} className={lit ? colour : 'text-fg-muted'} aria-hidden />
      {/* Not `hide-below-520`: the words are the button's accessible name, and a
          counter called "[ 1 ]" would be unusable by anyone not looking at it. */}
      <span className="quiet-below-520">{label}</span>
      <Num value={count} from={from} className={lit ? colour : ''} />
    </button>
  );
}
