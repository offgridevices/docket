import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { plainState } from '../lib/format';
import type { EpisodeView } from '../types/api';

/** `ep-id · plain state`, the mono state under Explain; a select when the session
 * holds more than one episode (the inventory's episode selector, once). */
export function EpisodeChip({ episode }: { episode: EpisodeView | null }) {
  const { episodes, setEpisodeId } = useSession();
  const { explain } = useWorkspace();
  if (!episode) return <span className="og-label text-b3 text-fg-muted">no decision open</span>;
  const label = (
    <>
      <span className="og-mono text-m2" data-num="label">{episode.id}</span> · {plainState(episode.lifecycleState)}
      {explain && <span className="og-mono text-m2 text-fg-muted"> {episode.lifecycleState}</span>}
    </>
  );
  if (episodes.length <= 1) return <span className="inline-flex min-h-11 max-w-[176px] items-center overflow-hidden whitespace-nowrap border border-hairline-strong px-2 text-b3 lg:max-w-[340px]">{label}</span>;
  return (
    <span className="inline-flex min-h-11 max-w-[176px] items-center gap-2 overflow-hidden whitespace-nowrap border border-hairline-strong px-2 text-b3 lg:max-w-[340px]">
      <select aria-label="Episode" value={episode.id} onChange={(e) => setEpisodeId(e.target.value)} className="og-mono text-m2 min-h-11 bg-transparent">
        {episodes.map((ep) => <option key={ep.id} value={ep.id}>{ep.id}</option>)}
      </select>
      <span>· {plainState(episode.lifecycleState)}{explain && <span className="og-mono text-m2 text-fg-muted"> {episode.lifecycleState}</span>}</span>
    </span>
  );
}
