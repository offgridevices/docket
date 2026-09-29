// `GET /api/session/{s}/episode/{e}/authority` — who authored what, counted by layer.
import { useFetched, type Fetched } from './useFetched';
import { useWorkspace } from './useWorkspace';
import type { AuthorityCounts } from '../types/api';

export function useAuthority(sessionId: string | null, episodeId: string | null): Fetched<AuthorityCounts> {
  const { recordVersion } = useWorkspace();
  return useFetched<AuthorityCounts>(
    sessionId && episodeId ? `/session/${sessionId}/episode/${episodeId}/authority` : null,
    [recordVersion],
  );
}
