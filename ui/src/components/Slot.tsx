// The slot renderer, written once and used by every screen that reads a P3 field
// (Evidence today; Model/Plan tomorrow). Every P3 slot is content **or** a gap **or**
// an exclusion, and a blank cell is the one thing it may never be (plan Task 8):
//
//   if content   -> render whatever the caller passed as `children`
//   if a $gap    -> GapCard
//   if $exclusion -> ExclusionCard
//
// There is no fourth branch and no null return. "Silence is prohibited" is a property
// of the schema; this component is where a reader can see that it held.

import type { ReactNode } from 'react';
import type { Exclusion, InsufficientEvidence } from '../types/objects';
import { ExclusionCard } from './ExclusionCard';
import { GapCard } from './GapCard';

export type SlotView =
  | { kind: 'content'; value: unknown }
  | { kind: 'gap'; target: string | null; targetObject: InsufficientEvidence | null }
  | { kind: 'exclusion'; target: string | null; targetObject: Exclusion | null };

/** Resolve one field path against an already-fetched `ObjectView` (or the looser shape
 * `EvidenceItem` shares with it — `slots`/`object`, nothing more is required). A slot
 * field currently holding real content never appears in `slots` (the server only lists
 * markers — see `types/api.ts`'s `SlotEntry` doc), so "not found in `slots`" *is* "this
 * field is content" — there is no third source to consult and no ambiguity to guess at. */
export function resolveSlot(
  view: { slots?: { path: string; kind: 'gap' | 'exclusion'; target: string | null; targetObject: unknown }[]; object?: Record<string, unknown> | null },
  path: string,
): SlotView {
  const marker = view.slots?.find((s) => s.path === path);
  if (marker) {
    return marker.kind === 'gap'
      ? { kind: 'gap', target: marker.target, targetObject: marker.targetObject as InsufficientEvidence | null }
      : { kind: 'exclusion', target: marker.target, targetObject: marker.targetObject as Exclusion | null };
  }
  return { kind: 'content', value: view.object?.[path] };
}

/** The raw value behind a slot, or `undefined` when the slot is a gap/exclusion — a
 * small typed escape hatch for a caller building `children` from `slot.value` without
 * repeating the `slot.kind === 'content' ? slot.value : undefined` narrowing at every
 * call site. Reading this when `kind !== 'content'` is always `undefined`, which is
 * correct: `<Slot>` never renders those `children` in that case anyway. */
export function slotValue(slot: SlotView): unknown {
  return slot.kind === 'content' ? slot.value : undefined;
}

export interface SlotProps {
  slot: SlotView;
  children?: ReactNode;
}

export function Slot({ slot, children }: SlotProps) {
  if (slot.kind === 'content') return <>{children}</>;
  if (slot.kind === 'gap') return <GapCard id={slot.target} fields={slot.targetObject} />;
  return <ExclusionCard id={slot.target} fields={slot.targetObject} />;
}
