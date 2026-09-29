// Display formatting only — string-in, string-out. Nothing here does arithmetic on a
// value that came from the API; the one place that is allowed is lib/svg.ts, and only
// for pixel geometry. If a screen needs a rounded or scaled number, the kernel already
// rounded it (`canon.round6`) and the API sent what the kernel stored — format it, don't
// recompute it.

import type { Mark } from './provenance';

const CONFIDENCE_LABEL: Record<string, string> = {
  explicit: 'explicit',
  inferred: 'inferred',
  absent: 'absent',
};

/** `confidence` is one of three closed string values on an agent-authored object
 * (schema: "explicit" | "inferred" | "absent"). Anything else is passed through
 * verbatim rather than thrown on, so an unrecognised-but-real value in a recorded
 * fixture still renders instead of crashing the screen.
 *
 * The three labels are lower case, and the fallback no longer upper-cases. Under brand
 * v3.0 nothing in the interface shouts (§5), and this function fed an eyebrow on every
 * agent-proposed object — the single widest source of caps left in the app after the
 * token swap. It slipped past the conformance check only because that check needs two
 * or more words to call something shouted. */
export function confidenceLabel(confidence: string | null | undefined): string {
  if (!confidence) return '—';
  return CONFIDENCE_LABEL[confidence] ?? confidence;
}

/** `MODEL_APPROVED` -> `Model Approved`. Pure string reshaping of a lifecycle state
 * name; the set of valid states lives in `kernel.lifecycle.EDGES`, not here — this
 * function does not validate membership, it only reformats whatever string arrives. */
export function lifecycleStateLabel(state: string): string {
  return state
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

const MARK_LABEL: Record<Mark, string> = {
  'agent-proposed': 'Agent-proposed',
  'human-accepted': 'Human-accepted',
  'kernel-computed': 'Kernel-computed',
};

export function markLabel(mark: Mark): string {
  return MARK_LABEL[mark];
}

/** A run stamp footer, e.g. `run-a1b2c3 · seed 0 · docket-0.7.0`. Every part is a
 * string the kernel already produced; this only joins them with the separator the
 * spec uses everywhere a run is cited. */
export function runStampLabel(run: { id: string; seed: number | string; kernelVersion: string }): string {
  return `${run.id} · seed ${run.seed} · ${run.kernelVersion}`;
}

/** True for the exact marker string `routes/kernel.py`'s `_withhold_evidence_fields`
 * substitutes for `pointer`/`scopeOfValidity`/`reliabilitySteps`/`reviewStatus` when
 * `rendering="unclassified"` and the evidence's `classification.metadataLevel` is above
 * `U` — the register's own withholding, distinct from a gap or an exclusion. A screen
 * that finds this string where content is expected pairs it with an `eye-off` glyph
 * (design spec Screen 7) rather than printing the marker as if it were the value. */
export function isWithheldMarker(value: unknown): value is string {
  return typeof value === 'string' && /^\[withheld: .+\]$/.test(value);
}

/** `PENDING_SIGNATURE` -> `pending signature`: the plain form a label reads; the mono
 * state stays verbatim beside it under Explain. String reshaping only. */
export function plainState(state: string): string {
  return state.toLowerCase().replace(/_/g, ' ');
}
