// `GET /api/session/{s}/episode/{e}/clock` — `kernel.clock.clock`: when it is due, where
// the time went, who it has been waiting on. Every number in it is the server's.
import { useFetched, type Fetched } from './useFetched';
import { useWorkspace } from './useWorkspace';
import type { ClockResponse } from '../types/api';

export function useClock(sessionId: string | null, episodeId: string | null): Fetched<ClockResponse> {
  const { recordVersion } = useWorkspace();
  return useFetched<ClockResponse>(
    sessionId && episodeId ? `/session/${sessionId}/episode/${episodeId}/clock` : null,
    [recordVersion],
  );
}
