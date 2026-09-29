// One rung per lifecycle edge the current state could move to, built entirely from
// `episode_view(g, eid).gateLadder` (src/docket/api/serialize.py), which itself calls the
// predicates in `kernel.lifecycle.CHECKS` — this component restates nothing, so it cannot
// drift from the gate it is drawing (same rule as the G1 sheet, plan 04 Task 4).
//
// Brand v3.0 (§5): the ladder carries no Ember fill. A blocked rung is Ember AS TEXT
// (`--og-accent-text`) beside the `octagon-alert` glyph the state table gives it, which
// is a colour on a glyph and a word, not a lit plane — the screen's one Ember belongs to
// the action a human can take (the approve bar), and this ladder is a reading of the
// record, not an action. Shape carries the state anyway: filled shield passed, hollow
// shield pending, octagon blocked.

import { OctagonAlert, Shield, ShieldCheck } from 'lucide-react';
import { ICON_PROPS } from '../lib/icons';
import type { GateRung } from '../types/api';

const ICON: Record<GateRung['state'], typeof Shield> = {
  passed: ShieldCheck,
  available: Shield,
  blocked: OctagonAlert,
};

const ICON_CLASS: Record<GateRung['state'], string> = {
  passed: 'text-fg',
  available: 'text-fg-muted',
  // `text-accent-text`, not `text-accent` — see Chip.tsx: Ember as a foreground colour
  // fails contrast in light mode; `accent-text` is the handoff's own escape hatch.
  blocked: 'text-accent-text',
};

export interface GateLadderProps {
  rungs: GateRung[];
}

export function GateLadder({ rungs }: GateLadderProps) {
  if (rungs.length === 0) {
    return <p className="text-b3 text-fg-muted">no gate history yet</p>;
  }

  return (
    <ol className="flex flex-col gap-2">
      {rungs.map((rung) => {
        const Icon = ICON[rung.state];
        return (
          <li key={rung.to} className="flex items-start gap-3 border border-hairline p-3" data-state={rung.state}>
            {/* Smaller than the spec default: an inline list icon. */}
            <Icon {...ICON_PROPS} size={18} className={`shrink-0 ${ICON_CLASS[rung.state]}`} aria-hidden />
            <div>
              {/* `rung.to` is a lifecycle state name (`MODEL_APPROVED`) and the check
                  names below are lowercase-kebab (`gaps-confirmed`): verbatim
                  identifiers, so mono. "human-only" is our own word for the edge, so it
                  is not — §5's rule is that a string which is neither a number nor an
                  identifier nor code is not mono. */}
              <p className="text-b3">
                <span className="og-mono text-m1">{rung.to}</span>
                {rung.humanOnly ? ' · human-only' : ''}
              </p>
              <ul className="og-mono text-m2 text-fg-muted">
                {rung.checks.map((check) => (
                  <li key={check.name}>
                    {check.satisfied ? '✓' : '·'} {check.name}
                  </li>
                ))}
              </ul>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
