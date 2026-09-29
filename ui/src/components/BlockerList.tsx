// The findings a `ReadinessReport` carries, one row each.
//
// In the server's order, always. `kernel.readiness` assembles `blockers` and `warnings`
// itself and the rendered package prints them in that same order; re-sorting them here
// by severity or by rule would put this view and the package's own Readiness section
// into disagreement about which finding a reader met first.
//
// Every entry of `blockers` stops sign-off, whatever its own `severity` says: a policy's
// `blockingRules` promotes a finding into that list while it keeps the `warning` or
// `info` severity it was raised with, and carries `promotedBy` to say so
// (`kernel.queue._grouped_blockers` makes the same reading of the same list). So the row
// takes its mark from the LIST it is in, not from the finding's own severity field — a
// promoted warning drawn as amber would tell a reader it was survivable.

import { useWorkspace } from '../api/useWorkspace';
import { IdChip } from './IdChip';
import { Sev } from './Sev';

/** One entry of `ReadinessReport.blockers` / `warnings`. Every field is optional here,
 * unlike `kernel.findings.Finding`'s own shape: the schema declares both lists as open
 * objects (`additionalProperties`), the caller reaches this component through a cast,
 * and a hand-edited store missing a field must render the rest of the row rather than
 * take the view down with it. [review fix round 1, Minor 5] */
export interface Finding {
  rule?: string;
  severity?: 'blocking' | 'warning' | 'info';
  objects?: string[];
  message?: string;
  promotedBy?: string;
}

/** `ReadinessReport.blockers` / `warnings`, one row each, in the server's order.
 * A blocker is red with a 3 px left rule; a warning is amber without one. */
export function BlockerList({ findings, kind }: { findings: Finding[]; kind: 'blocker' | 'warning' }) {
  const { explain, openOverlay } = useWorkspace();
  if (findings.length === 0) {
    return <p className="text-b3 text-fg-muted">{kind === 'blocker' ? 'nothing blocks sign-off' : 'no warnings'}</p>;
  }
  return (
    <ol className="flex flex-col gap-2">
      {findings.map((f, i) => (
        // The key is the rule plus the position, not the rule alone: one rule raises one
        // finding per object it is unhappy with (Demo B has 146 blockers under a handful
        // of rules), so a rule id is not unique in this list and never was.
        <li
          key={`${f.rule ?? ''}:${i}`}
          className={`border bg-raised p-3 text-b3 ${kind === 'blocker' ? 'border-stop-line border-l-[3px] border-l-stop' : 'border-wait-line'}`}
          data-blocker={kind === 'blocker' ? '' : undefined}
          data-warning={kind === 'warning' ? '' : undefined}
        >
          <p className="og-label">
            <Sev kind={kind === 'blocker' ? 'blocking' : 'warning'}>
              {kind === 'blocker' ? 'Blocks sign-off' : 'Worth knowing'}
            </Sev>
            {/* The rule that raised it is a coordinate into the kernel, not a sentence a
                reader needs — it appears under Explain, where the record's own names
                belong. */}
            {explain && f.rule && <span className="og-mono text-m2 text-fg-muted" data-rule> {f.rule}</span>}
          </p>
          {/* Verbatim kernel-authored text, which can carry a section number of its own
              ("GAO-23-106549 F9") that is nothing this interface computed. */}
          <p className="mt-1" data-num="label">{f.message ?? ''}</p>
          {/* Not gated by Explain: that this finding is only binding because a policy
              said so is the reason it is in this list at all, and a reader deciding what
              to do about it needs it. `promotedBy` is NOT the name of a rule: the one
              line that writes it (`kernel.readiness`, `"promotedBy":
              "policy.blockingRules"`) always writes the same field path — the list the
              finding's own rule name was found in. So the sentence names that list, and
              the value stays mono beside it as the coordinate into the policy it is.
              [review fix round 1, Minor 2] */}
          {f.promotedBy && (
            <p className="mt-1 text-fg-secondary">
              promoted to a blocker by the policy&apos;s blocking-rules list{' '}
              <span className="og-mono text-m2">{f.promotedBy}</span>
            </p>
          )}
          {(f.objects ?? []).length > 0 && (
            <p className="mt-1 flex flex-wrap gap-1">
              {(f.objects ?? []).map((id) => (
                <IdChip key={id} id={id} onOpen={() => openOverlay({ kind: 'raw', id })} />
              ))}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
