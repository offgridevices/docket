// needs you · blocking · the time chip · where answers come from.
import { CircleAlert, OctagonAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useHealth } from '../api/useHealth';
import { useWorkspace } from '../api/useWorkspace';
import type { ClockResponse, NeedsResponse } from '../types/api';
import { Counter } from './Counter';
import { TimeChip } from './TimeChip';

export function StatusRow({ needs, clock, episodeState }: { needs: NeedsResponse | null; clock: ClockResponse | null; episodeState: string | null }) {
  const navigate = useNavigate();
  const { openOverlay } = useWorkspace();
  const { data: health, apiAbsent } = useHealth();
  const mode = apiAbsent || !health ? 'API absent' : health.mode;
  const from = needs?.episode ?? 'needs';
  return (
    <div className="status flex flex-wrap items-center gap-2 px-[clamp(14px,2.2vw,30px)] pb-1.5" aria-label="Status of this decision">
      <Counter label="needs you" count={needs?.count ?? 0} tone="act" icon={CircleAlert} from={from}
        title="Everything waiting on a person in this decision" onClick={() => navigate('/')} />
      <Counter label="blocking" count={needs?.blocking.count ?? 0} tone="stop" icon={OctagonAlert} from={from}
        title="Everything that stops this decision moving on" onClick={() => openOverlay({ kind: 'blockers' })} />
      {clock && <TimeChip clock={clock} needs={needs} episodeState={episodeState} />}
      <span className="status__spacer flex-1" />
      {/* Where the answers come from, at every width. The chip the old shell carried was
          never hidden and never subtle, and that is the point of it: a reader must be
          able to see, without asking, whether what they are looking at came from a live
          model or a recording. Below 1024 the row scrolls sideways rather than dropping
          this. */}
      <button type="button" onClick={() => openOverlay({ kind: 'settings' })} title="Where the answers come from. Opens Settings."
        className="status__mode og-mono text-m2 inline-flex min-h-11 items-center gap-2 border border-hairline-strong bg-canvas px-2.5" data-mode={mode}>
        <span aria-hidden className={`inline-block h-2 w-2 ${mode === 'recorded' ? 'border border-fg' : 'bg-fg'}`} />{mode}
      </button>
    </div>
  );
}
