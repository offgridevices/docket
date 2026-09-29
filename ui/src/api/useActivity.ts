// `GET /api/session/{s}/activity` — the append-only log in plain language, newest first.
//
// `episodeId` is the route's own `?episode=` filter (the Activity view's "This episode
// only" toggle): the entries whose object that episode reaches, plus the episode itself.
// Left null, the read is the whole session's log.
import { useFetched, type Fetched } from './useFetched';
import { useWorkspace } from './useWorkspace';
import type { ActivityResponse } from '../types/api';

export function useActivity(sessionId: string | null, episodeId: string | null = null): Fetched<ActivityResponse> {
  const { recordVersion } = useWorkspace();
  const path = sessionId
    ? `/session/${sessionId}/activity${episodeId ? `?episode=${encodeURIComponent(episodeId)}` : ''}`
    : null;
  return useFetched<ActivityResponse>(path, [recordVersion]);
}
