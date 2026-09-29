// One GET behind `{data, error, loading, apiAbsent, refresh}` — the shape every read in
// this app has had since `useG1.ts` first defined it, lifted out of that file so the
// workspace hooks (the clock, the queue, the activity log, the authority rail) share one
// implementation rather than four copies of the same effect.
//
// Nothing here polls. The record only changes when this browser changes it, and the
// re-read after a write is explicit: a mutating action bumps `useWorkspace().recordVersion`,
// which every workspace hook passes in `deps`.
import { useCallback, useEffect, useState } from 'react';
import { apiGet, ApiUnreachable } from './client';

export interface Fetched<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  apiAbsent: boolean;
  refresh: () => void;
}

/** One GET, re-run when `path` or any of `deps` changes; `null` path = nothing. */
export function useFetched<T>(path: string | null, deps: unknown[] = []): Fetched<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);
  useEffect(() => {
    if (!path) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    apiGet<T>(path)
      // The previous episode's data is dropped on an error, not left on screen under a
      // new episode's heading — a stale board next to a fresh error is how a reviewer
      // ends up acting on the wrong record.
      .then((res) => { if (!cancelled) { setData(res); setError(null); } })
      .catch((err: unknown) => { if (!cancelled) { setData(null); setError(err instanceof Error ? err : new Error(String(err))); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps]);
  return { data, error, loading, apiAbsent: error instanceof ApiUnreachable, refresh };
}
