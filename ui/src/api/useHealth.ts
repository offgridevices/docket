// `GET /api/health`, polled lightly so the header's LIVE|RECORDED chip and health dot
// stay current without a live connection. When the API is absent entirely (no server
// running — e.g. this scaffold, built and opened before Task 1's routes exist, or the
// static bundle opened outside `docket ui`), `error` is an `ApiUnreachable` and callers
// render the placeholder state the plan requires, rather than a spinner or a guess.

import { useCallback, useEffect, useState } from 'react';
import { apiGet, ApiUnreachable } from './client';
import type { HealthResponse } from '../types/api';

const POLL_MS = 15_000;

export interface UseHealthResult {
  data: HealthResponse | null;
  loading: boolean;
  /** Non-null exactly when the most recent fetch failed. `apiAbsent` narrows this to
   * "no server answered at all", the case the rail and header must fall back for. */
  error: Error | null;
  apiAbsent: boolean;
  refetch: () => void;
}

export function useHealth(): UseHealthResult {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiGet<HealthResponse>('/health')
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  useEffect(() => {
    const id = window.setInterval(refetch, POLL_MS);
    return () => window.clearInterval(id);
  }, [refetch]);

  return { data, loading, error, apiAbsent: error instanceof ApiUnreachable, refetch };
}
