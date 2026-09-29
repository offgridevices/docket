// Activity (spec §18) — the record's own append-only log, one plain sentence per entry.
//
// Every sentence on this screen is `kernel/clock.py`'s `describe_log_entry` output,
// written by the server and printed verbatim. The browser composes nothing: it does not
// summarise an entry, does not count entries, and does not decide what an entry means.
// The two numerals a row can print (`seq`, `rev`) are server values through `Num`.
//
// **No Ember.** Reading the log is not a human act, so this view spends none of §5's
// single Ember plane. The four toggles are outline controls, and the only colour on the
// screen sits on a glyph, a hairline or a tint (§10).
//
// Reads go through `useFetched`: `Loading` on ANY read in flight (switching the header's
// episode, or the episode toggle, must never leave the last log on screen under the new
// heading), `ErrorState` with retry on error, defensive `?? []` on the one list.

import { useState } from 'react';
import { Check } from 'lucide-react';
import { useActivity } from '../api/useActivity';
import { useSession } from '../api/useSession';
import { useWorkspace } from '../api/useWorkspace';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FieldsControl } from '../components/FieldsControl';
import { IdChip } from '../components/IdChip';
import { Loading } from '../components/Loading';
import { Num } from '../components/Num';
import { Sev } from '../components/Sev';
import { ViewHead } from '../components/ViewHead';
import { ICON_PROPS } from '../lib/icons';
import { useFields, type FieldSpec } from '../lib/fields';
import type { ActivityEntry } from '../types/api';

/** `hash` is not offered: `describe_log_entry` does not carry the log line's own
 * `entryHash` out of the kernel, and a Fields row for a value the route never sends
 * would be a promise this view cannot keep. */
export const ACTIVITY_FIELDS: FieldSpec[] = [
  { key: 'seq', label: 'log position', default: false },
  { key: 'rev', label: 'revision', default: true },
];

const LAYERS: [ActivityEntry['layer'], string][] = [
  ['human', 'People'],
  ['agent', 'The AI'],
  ['kernel', 'The kernel'],
];

/** An on/off control that is a 44 px target at every width (§5a).
 *
 * Not a bare `<input type="checkbox">` in a 44 px label — `FieldsControl`'s pattern —
 * because that box is 13 px and these four toggles are on screen while the brand walk
 * runs, where `FieldsControl`'s live inside a popover the specs close first. Scaling a
 * native checkbox to 44 px instead would make a form control the loudest mark on a
 * screen whose whole job is reading. So it is the bordered outline control this app
 * already uses for a choice (`Evidence`'s rendering group), carrying the checkbox role
 * and `aria-checked` so it is still a checkbox to a screen reader and to a spec. */
function Toggle({ label, on, onChange }: { label: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={`og-label text-b3 inline-flex min-h-11 items-center gap-1.5 border px-3 ${on ? 'border-hairline-strong text-fg' : 'border-hairline text-fg-muted'}`}
    >
      <Check {...ICON_PROPS} size={16} aria-hidden className={on ? '' : 'invisible'} /> {label}
    </button>
  );
}

/** Who acted, as a mark and an actor id. The id stays mono and verbatim (§5) and carries
 * two attributes. `data-model-id`: an agent's actor id is built from the configured
 * model id, and the documentation figures mask every element carrying that attribute.
 * `data-num="label"`: an actor id is an identifier, not a value — and the kernel's own
 * (`docket-kernel/0.1.0`) carries a version number no reader would ever compute with. */
function Who({ entry }: { entry: ActivityEntry }) {
  if (entry.refused) {
    return (
      <Sev kind="blocking">
        <span className="og-mono break-all text-m2" data-model-id data-num="label">{entry.actorId}</span>
      </Sev>
    );
  }
  if (entry.layer === 'agent') {
    return (
      <Sev kind="ai">
        <span className="og-mono break-all text-m2" data-model-id data-num="label">{entry.actorId}</span>
      </Sev>
    );
  }
  // A filled square for a person, an outlined one for the kernel: the same two marks the
  // rest of the app uses for "a person did this" and "ordinary code did this".
  const mark = entry.layer === 'kernel' ? 'border border-fg' : 'bg-done';
  return (
    <span className="inline-flex items-center gap-2">
      <span aria-hidden className={`inline-block h-2.5 w-2.5 shrink-0 ${mark}`} />
      <span className="og-mono break-all text-m2" data-model-id data-num="label">{entry.actorId}</span>
    </span>
  );
}

export function Activity() {
  const { sessionId, episodeId, settled } = useSession();
  const { openOverlay } = useWorkspace();
  const fields = useFields('activity', ACTIVITY_FIELDS);
  const [thisEpisode, setThisEpisode] = useState(true);
  const [show, setShow] = useState<Record<string, boolean>>({ human: true, agent: true, kernel: true });
  const scoped = thisEpisode ? episodeId : null;
  // While "This episode only" is on, the read waits for the session to have read its
  // episodes. `episodeId` is null both before that read and when there genuinely is no
  // episode, and the two mean opposite things here: without the wait, a hard load or a
  // deep link to /activity would fetch — and briefly print — the WHOLE session's log
  // under a heading about to say "this episode". `settled` is what distinguishes them
  // (the same reason `Timeline` waits on it before saying anything about a decision).
  const held = thisEpisode && !settled;
  const activity = useActivity(held ? null : sessionId, scoped);

  if (!sessionId) {
    return <ViewHead eyebrow="activity" title="Activity" sentence="Choose a decision in the header first." />;
  }

  const entries = activity.data?.entries ?? [];

  return (
    <div>
      <ViewHead
        eyebrow={`activity · ${scoped ?? (held ? 'this episode' : 'whole session')}`}
        title="Activity"
        sentence="The record's own append-only log, newest first: who did what, when, and whether the kernel refused it."
        right={<FieldsControl list="activity" spec={ACTIVITY_FIELDS} shownOverride={fields} />}
      />

      {/* The three layer toggles hide rows in this browser and nothing more — the log
          itself is never filtered by who acted. The episode toggle is different: it is
          the route's own `?episode=` parameter, so the heading above says which log is
          on screen. */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {LAYERS.map(([layer, label]) => (
          <Toggle key={layer} label={label} on={!!show[layer]} onChange={(v) => setShow((s) => ({ ...s, [layer]: v }))} />
        ))}
        {(episodeId || held) && <Toggle label="This episode only" on={thisEpisode} onChange={setThisEpisode} />}
      </div>

      {(held || activity.loading) && <Loading label="the log" />}
      {!held && activity.error && (
        <ErrorState
          message={activity.error.message}
          route={`session/${sessionId}/activity`}
          onRetry={activity.refresh}
        />
      )}
      {!held && !activity.loading && !activity.error && activity.data && entries.length === 0 && (
        <EmptyState eyebrow="Activity" message="Nothing has been written to this record yet." />
      )}

      {!held && !activity.loading && !activity.error && entries.length > 0 && (
        // The table scrolls inside its own container, never the page (§5a). Below 768 px
        // the four cells stack down the row instead, so at 360 there is nothing wide
        // enough to scroll at all.
        <div role="table" className="overflow-x-auto border-t border-hairline text-b3">
          {entries.map((entry) => (
            <div
              key={entry.seq}
              role="row"
              className={`grid gap-x-3 gap-y-1 border-b border-hairline px-1 py-2 md:grid-cols-[150px_170px_minmax(0,1fr)_auto] ${show[entry.layer] ? '' : 'hidden'} ${entry.refused ? 'bg-stop-tint' : ''}`}
              data-activity-row
              data-seq={entry.seq}
              data-layer={entry.layer}
              data-refused={entry.refused ? '' : undefined}
            >
              {/* The stamp is the named revision's own `createdAt` — a date, not a value
                  anyone computes with; the log position beside it is a server value. */}
              <span role="cell" className="og-mono text-m2 text-fg-secondary" data-num="label">
                {entry.at ?? '_[no stamp]_'}
                {fields.shown.seq && <> · #<Num value={entry.seq} from="log" /></>}
              </span>
              <span role="cell" className="min-w-0">
                <Who entry={entry} />
              </span>
              {/* The server's own sentence, verbatim. Marked as a label for the numeral
                  walk: a sentence the kernel wrote can legitimately state a count
                  ("scored the record: ready, 2 blocking"), and it is the kernel's
                  count, not one this browser reached. */}
              <span role="cell" className="min-w-0 break-words" data-num="label">{entry.what}</span>
              <span role="cell" className="inline-flex flex-wrap items-center gap-2">
                <IdChip id={entry.id} onOpen={() => openOverlay({ kind: 'raw', id: entry.id })} />
                {fields.shown.rev && (
                  <span className="og-mono text-m2 text-fg-muted">rev <Num value={entry.rev} from={entry.id} /></span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
