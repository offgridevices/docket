// `GET /api/session/{s}/episode/{e}/needs` — `kernel.queue.needs`: what needs a person,
// and what stops sign-off. Re-read after every write (`recordVersion`), because the list
// drains as the record changes and a stale queue is an act somebody has already done.
import { useFetched, type Fetched } from './useFetched';
import { useWorkspace } from './useWorkspace';
import type { NeedsResponse } from '../types/api';

export function useNeeds(sessionId: string | null, episodeId: string | null): Fetched<NeedsResponse> {
  const { recordVersion } = useWorkspace();
  return useFetched<NeedsResponse>(
    sessionId && episodeId ? `/session/${sessionId}/episode/${episodeId}/needs` : null,
    [recordVersion],
  );
}
