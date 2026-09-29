// The determinism affordance (plan Task 8 Screen 9): calls `POST .../verify`
// (`docket.api.verify.verify_determinism`) and prints exactly what the response says —
// this component computes nothing, it re-renders the server's own words. `identical:
// true` -> "identical bytes ✓" with both hashes in mono; `false` -> the two hashes side
// by side and "The graph changed since this package was rendered." Either way, the
// response's own `scope` string is printed next to the result, unconditionally — the
// sentence that keeps a green result from being read as a claim about the model.
//
// Brand v3.0 (§5, §5a): the trigger is a button, so its label is `og-label` rather than
// mono, and its hit area is 44px however small the glyph and the word inside it are. The
// two hashes stay mono — they are the only part of this panel that is a coordinate
// rather than a sentence.

import { useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { apiPost, ApiError, ApiUnreachable } from '../api/client';
import { ICON_PROPS } from '../lib/icons';
import type { VerifyResponse } from '../types/api';
import { ErrorState } from './ErrorState';

export interface VerifyButtonProps {
  sessionId: string;
  episodeId: string;
  rendering: 'full' | 'unclassified';
}

export function VerifyButton({ sessionId, episodeId, rendering }: VerifyButtonProps) {
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [noPackage, setNoPackage] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleVerify() {
    setLoading(true);
    setError(null);
    setNoPackage(null);
    try {
      const res = await apiPost<VerifyResponse>(
        `/session/${sessionId}/episode/${episodeId}/verify`,
        { rendering },
      );
      setResult(res);
    } catch (err) {
      setResult(null);
      if (err instanceof ApiError && err.status === 409 && err.body.error === 'no-package') {
        setNoPackage(err.body.message ?? 'no package has been built for this rendering yet');
      } else {
        setError(err instanceof Error ? err : new Error(String(err)));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={handleVerify}
        disabled={loading}
        className="og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center gap-2 self-start border border-hairline-strong px-3"
      >
        {/* Smaller than the spec default: an inline button glyph. The 44px floor is on
            the button, not on the glyph (§5a). */}
        <RotateCcw {...ICON_PROPS} size={16} className="shrink-0" aria-hidden />
        {loading ? 'verifying…' : 'Verify the bytes'}
      </button>

      {noPackage && <p className="text-b2 text-fg-muted">{noPackage}</p>}

      {error &&
        (error instanceof ApiUnreachable ? (
          <ErrorState message={error.message} onRetry={handleVerify} />
        ) : (
          <ErrorState
            message={error.message}
            route={`/session/${sessionId}/episode/${episodeId}/verify`}
            onRetry={handleVerify}
          />
        ))}

      {result && (
        <div
          className="border border-hairline p-3 flex flex-col gap-1"
          data-state={result.identical ? 'identical' : 'drifted'}
          data-testid="verify-result"
        >
          {result.identical ? (
            <p className="og-label text-b2">identical bytes ✓</p>
          ) : (
            <p className="text-b2">The graph changed since this package was rendered.</p>
          )}
          <p className="og-label text-m2 tracking-normal text-fg-muted">
            this render · <span className="og-mono">{result.hash}</span>
          </p>
          <p className="og-label text-m2 tracking-normal text-fg-muted">
            stored package · <span className="og-mono">{result.priorHash}</span>
          </p>
          {/* The server's own sentence for why the two hashes do or do not match —
              prose, so body text rather than mono. */}
          <p className="text-b3 text-fg-muted">{result.reason}</p>
          <p className="text-b2 text-fg-secondary">{result.scope}</p>
        </div>
      )}
    </div>
  );
}
