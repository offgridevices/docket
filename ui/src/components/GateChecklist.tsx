import { Check, Circle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../api/useWorkspace';
import { checkPlain, type Remedy } from '../lib/checks';
import { plainState } from '../lib/format';
import { ICON_PROPS } from '../lib/icons';
import { Sev } from './Sev';

export interface GateCheck { name: string; satisfied: boolean; whatWouldSatisfy?: string }
/** A refused attempt. Read off the record's own transition history wherever possible —
 * `unsatisfied` from `checksUnsatisfied`, `at` and `actorId` from the attempt — so the
 * red card survives leaving the view and coming back. `message` is present only for an
 * attempt made in this browser just now, where the server's own words are worth
 * printing; the record does not keep them. */
export interface Refusal { message?: string; unsatisfied: string[]; at?: string; actorId?: string }

/** A gate as a checklist (R9): the check in plain language with the record's own name
 * beside it under Explain, the gate's own sentence for what would satisfy it, a green
 * tick when it is met, one remedy for the first thing still missing, the refusal
 * explained before you press and kept in red afterwards.
 *
 * No count is printed. How many checks are met is a number this browser would have to
 * work out by filtering a list, and the honesty rule is that a numeral on screen is a
 * value the server sent; the ticks say it without one.
 *
 * The Ember: this button carries the view's one fill, and only when the gate is open
 * and every check is met. An unpassable gate lights nothing — pressing it is still
 * allowed (the refusal is the point), it is simply not the act being recommended. */
export function GateChecklist({ gate, to, verb, checks, open, onApprove, refusal, busy, remedies, actor }: {
  gate: 'G1' | 'G2' | 'G3'; to: string; verb: string; checks: GateCheck[]; open: boolean;
  onApprove: () => Promise<void>; refusal: Refusal | null; busy: boolean; remedies: Record<string, Remedy | null>; actor: string;
}) {
  const navigate = useNavigate();
  const { explain } = useWorkspace();
  const pass = checks.every((c) => c.satisfied);
  const firstUnmet = checks.find((c) => !c.satisfied && remedies[c.name]);
  return (
    <div className="border border-hairline bg-raised p-4" data-gate={gate}>
      <h3 className="og-label text-b1" data-num="label">{verb}{explain && <span className="og-mono text-m2 text-fg-muted"> {gate}</span>}</h3>
      <p className="mb-3 text-b3 text-fg-secondary">{open ? 'Only a person may pass this gate. The kernel checks the record; you decide, and nothing is written until you press.' : 'This decision is already past this gate, so the checklist is read-only.'}</p>
      {checks.map((c) => {
        // One remedy, on the first thing still missing: a column of buttons reads as a
        // list of chores, and the checks below it are not independent of the one above.
        const remedy = firstUnmet?.name === c.name ? remedies[c.name] : null;
        return (
          <div key={c.name} className="grid grid-cols-[26px_1fr] gap-3 border-t border-hairline py-3 first:border-t-0" data-check={c.name} data-satisfied={c.satisfied ? 'true' : 'false'}>
            <span className="grid h-[22px] w-[22px] place-items-center">{c.satisfied ? <Check {...ICON_PROPS} size={20} className="text-done" aria-hidden /> : <Circle {...ICON_PROPS} size={20} className="text-fg-muted" aria-hidden />}</span>
            <div className="min-w-0">
              <div className={`og-label text-b3 ${c.satisfied ? 'text-fg-secondary' : ''}`}>{checkPlain(c.name)}{explain && <span className="og-mono text-m2 text-fg-muted"> {c.name}</span>}</div>
              {c.whatWouldSatisfy && <p className="mt-0.5 max-w-[68ch] text-b3 text-fg-secondary" data-num="label">{c.satisfied ? 'Satisfied. ' : 'What would satisfy it: '}{c.whatWouldSatisfy}</p>}
              {remedy && open && (
                <p className="mt-2" data-remedy="first"><button type="button" onClick={() => navigate(remedy.route)} className="og-label inline-flex min-h-11 items-center border border-hairline-strong px-3 text-b3">{remedy.label}</button></p>
              )}
            </div>
          </div>
        );
      })}
      <div className="mt-4 border-t border-hairline-strong pt-4">
        {refusal && (
          <div className="mb-3 border border-stop-line border-l-[3px] border-l-stop bg-stop-tint p-4" data-refusal>
            <h4 className="og-label text-b2"><Sev kind="blocking">The gate refused and the refusal is now part of the record.</Sev></h4>
            <p className="og-mono mt-1 break-words text-m1">{refusal.unsatisfied.join(' · ')}</p>
            {refusal.message && <p className="mt-1 text-b3" data-num="label">{refusal.message}</p>}
            <p className="mt-1 text-b3 text-fg-secondary">Attempted by <span className="og-mono text-m2" data-model-id>{refusal.actorId ?? actor}</span>{refusal.at ? <> on <span className="og-mono text-m2" data-num="label">{refusal.at}</span></> : null}. The attempt is kept; refusals are never silent.</p>
          </div>
        )}
        {!refusal && !pass && open && <p className="mb-3 text-b3 text-fg-secondary">If you press the button now it will refuse, and name <span className="og-mono text-m2 break-words">{checks.filter((c) => !c.satisfied).map((c) => c.name).join(' and ')}</span>. The attempt is recorded either way.</p>}
        {/* `data-num="label"`: a gate's verb names the gate ("Pass gate 2"), and a gate's
            number is its name, not a value read out of the record — the same carve-out
            the heading above already takes. Gate 1's verb carried no digit, so this only
            became load-bearing when gate 2 arrived (Task 12). */}
        <button type="button" onClick={() => void onApprove()} disabled={!open || busy} data-ember={open && pass ? '' : undefined} data-num="label"
          className="og-label inline-flex min-h-11 items-center justify-center border border-hairline-strong px-4 text-b3">
          {busy ? 'working…' : `${verb} — move to ${plainState(to)}`}
        </button>
        {open && pass && <p className="mt-2 text-b3 text-fg-secondary">What happens: the decision moves to <span className="og-mono text-m2">{to}</span>, attributed to <span className="og-mono text-m2" data-model-id>{actor}</span>, and the attempt is written to the log.</p>}
      </div>
    </div>
  );
}
