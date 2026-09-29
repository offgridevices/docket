// One sealed `EvaluationRun` (design spec Screen 5, "Runs sealed"; plan Task 7 Step 3).
//
// Brand v3.0 (§5): mono is the seal's own material — hashes, a seed, a version, a
// timestamp, an id. The words AROUND them ("sealed run", "record", "inputs", "seed",
// "sealed by") are our labels, so they are `og-label` and not mono; v1.2 set the whole
// card in mono, which left nothing for the numerals to stand out against. `text-m2`
// carries the mono size ramp's own 0.06em tracking, which belongs to a run of numerals
// and not to a word, so every label at that size also takes `tracking-normal`; the mono
// spans inside keep their own. The card's
// elevation is still tone plus a hairline, never a shadow.
// Every field here is verbatim, kernel-authored identity/seal metadata — a hash, a seed,
// a version string, an actor id, a timestamp — not an analytical value, so it renders as
// plain `og-mono` text rather than through `<Num>` (the same precedent
// `screens/Package.tsx`'s header bar and `components/GateLadder.tsx` already set for
// `pkg.hash`/`pkg.kernelVersion`/`object.rev`: an identifier is not a decision value a
// reviewer would quote as a result, even though it is made of digits). `<Num>` is
// reserved for `Result.value` and `FlipAnalysis`'s numeric fields elsewhere on this
// screen (`ResultTable.tsx`, `FlipChart.tsx`).
//
// `runRecordHash`/`inputsHash` are truncated to their first 12 characters — the plan's
// own spec for this card — with the full value in a `title` attribute and a data
// attribute for a test to read; truncating a string for display is not the "arithmetic
// on a value" the honesty rule is about (there is no numeral to preserve fidelity of).
//
// Every digit-bearing token (`evaluatorVersion`, the hashes, `seed`, `kernelVersion`,
// `sealedAt`) is individually marked `data-num="label"` — honesty rule 2's own
// carve-out for "ids and object counts" (`ui/e2e/_fixtures.ts`'s
// `assertNoUnbracketedNumerals` already treats a hyphenated object id this way; a
// run's own identity fields are the same kind of thing, just not hyphenated). Fix round
// 1 (M2) narrowed these from whole-line marks to per-token spans, so the walk cannot be
// defeated by wrapping a line that happens to carry ordinary prose beside a digit. This
// is a marker on identity metadata, not on an analytical value — nothing here goes
// through `<Num>` instead of this, because `<Num>` carries `from` provenance semantics
// that make no sense applied to a run naming its own seed.

import { Lock } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import type { EvaluationRun } from '../types/objects';

export interface RunSealProps {
  run: EvaluationRun;
}

export function RunSeal({ run }: RunSealProps) {
  return (
    <div className="border border-hairline p-3 flex flex-col gap-1" data-testid="run-seal">
      <p className="og-label text-m2 tracking-normal inline-flex flex-wrap items-center gap-2 text-fg-secondary">
        <Lock {...ICON_PROPS} size={16} className="shrink-0" aria-hidden /> sealed run
        <span className="og-mono">· {run.id}</span>
      </p>
      {/* Narrow spans around each digit-bearing token (fix round 1, M2), not the whole
          line: `step`/`evaluator`/`method` are hyphenated ids the numeral walk's own
          `OBJECT_ID_RE` already exempts; only `evaluatorVersion` (a bare "0.1.0") needs
          the `data-num="label"` carve-out. */}
      <p className="og-label text-m2 tracking-normal text-fg-secondary">
        step <span className="og-mono">{run.step}</span> ·{' '}
        <span className="og-mono">{run.evaluator}</span> ·{' '}
        <span className="og-mono" data-num="label">{run.evaluatorVersion}</span> ·{' '}
        <span className="og-mono">{run.method}</span>
      </p>
      <p
        className="og-label text-m2 tracking-normal"
        title={run.runRecordHash}
        data-full-hash={run.runRecordHash}
        data-num="label"
      >
        record <span className="og-mono">{run.runRecordHash.slice(0, 12)}…</span>
      </p>
      <p
        className="og-label text-m2 tracking-normal"
        title={run.inputsHash}
        data-full-hash={run.inputsHash}
        data-num="label"
      >
        inputs <span className="og-mono">{run.inputsHash.slice(0, 12)}…</span>
      </p>
      <p className="og-label text-m2 tracking-normal text-fg-secondary">
        seed <span className="og-mono" data-num="label">{run.seed}</span> · kernel{' '}
        <span className="og-mono" data-num="label">{run.kernelVersion}</span>
      </p>
      <p className="og-label text-m2 tracking-normal text-fg-secondary">
        sealed by <span className="og-mono">{run.sealedBy}</span> ·{' '}
        <span className="og-mono" data-num="label">{run.sealedAt}</span>
      </p>
    </div>
  );
}
