import type { ReactNode } from 'react';
import { Check, Clock, Info, OctagonAlert, Shield, TriangleAlert, Diamond } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';

export type SevKind = 'blocking' | 'stop' | 'warning' | 'wait' | 'passed' | 'done' | 'info' | 'ai';
const TONE: Record<SevKind, string> = {
  blocking: 'text-stop', stop: 'text-stop', warning: 'text-wait', wait: 'text-wait',
  passed: 'text-done', done: 'text-done', info: 'text-fg-secondary', ai: 'text-ai',
};
const GLYPH: Record<SevKind, typeof Info> = {
  blocking: OctagonAlert, stop: OctagonAlert, warning: TriangleAlert, wait: Clock,
  passed: Shield, done: Check, info: Info, ai: Diamond,
};
/** A severity/state glyph carrying the colour; the sentence beside it stays ink (R24). */
export function Sev({ kind, children }: { kind: SevKind; children: ReactNode }) {
  const Glyph = GLYPH[kind];
  return (
    <span className="inline-flex items-start gap-2 text-b3" data-sev={kind}>
      <Glyph {...ICON_PROPS} size={18} className={`mt-0.5 shrink-0 ${TONE[kind]}`} aria-hidden />
      <span>{children}</span>
    </span>
  );
}
