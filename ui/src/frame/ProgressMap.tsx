import { NavLink } from 'react-router-dom';
import { ColourKey } from '../components/ColourKey';
import { Num } from '../components/Num';
import { StateGlyph, type GlyphKind } from '../components/StateGlyph';
import { useWorkspace } from '../api/useWorkspace';
import { ICON_PROPS } from '../lib/icons';
import { STAGE_KEYS, VIEWS, type ViewDef } from '../routes';
import type { NeedsResponse } from '../types/api';

const STATE_INDEX: Record<string, number> = { DRAFT: 1, MODEL_APPROVED: 2, PLAN_APPROVED: 3, EVALUATED: 4, PENDING_SIGNATURE: 5, SIGNED: 6 };
const STAGE_INDEX: Record<string, number> = { request: 0, model: 1, plan: 2, compute: 3, readiness: 4, package: 5 };

/** This row's number, as the server counted it (`needs.byRoute`, kernel/queue.py) — never
 * a filter of `items` run in the browser, which was a count this file computed and then
 * printed through `Num` as though the record had said it. The home row is the whole queue,
 * which is `count`; every other row is its own route's entry, with the review cards already
 * folded into `/model` server-side. */
function countFor(view: ViewDef, needs: NeedsResponse | null): number {
  if (!needs) return 0;
  return view.group === 'home' ? needs.count : (needs.byRoute[view.path] ?? 0);
}

/** Display sequencing only (the gate ladder is the truth): which stage the state sits at. */
export function stageState(view: ViewDef, needs: NeedsResponse | null, state: string | null, hasEpisode: boolean): GlyphKind {
  if (countFor(view, needs) > 0) return 'needs';
  if (view.group === 'register') return hasEpisode ? 'done' : 'later';
  if (view.group === 'home') return needs && needs.count > 0 ? 'needs' : 'done';
  const here = state && STATE_INDEX[state] ? STATE_INDEX[state] : 0;
  const idx = STAGE_INDEX[view.key];
  if (!hasEpisode) return 'later';
  if (view.key === 'request') return 'done';
  if (idx < here) return 'done';
  if (idx === here) return 'doing';
  return 'later';
}

const LABEL: Record<GlyphKind, string> = { done: 'done', needs: 'needs you', doing: 'in progress', later: 'not yet' };

function Row({ view, needs, state, hasEpisode }: { view: ViewDef; needs: NeedsResponse | null; state: string | null; hasEpisode: boolean }) {
  const { explain } = useWorkspace();
  const kind = stageState(view, needs, state, hasEpisode);
  const count = countFor(view, needs);
  const Icon = view.icon;
  return (
    <NavLink to={view.path} end={view.path === '/'} data-state={kind} data-map-row={view.key} title={`${view.label} · ${LABEL[kind]} · ${view.record}`}
      className={({ isActive }) => `map__row flex min-h-11 w-full items-center gap-2 border-l-2 px-1.5 text-b3 ${isActive ? 'border-l-fg bg-surface text-fg' : 'border-l-transparent text-fg-secondary'} ${kind === 'later' ? 'text-fg-muted' : ''}`}>
      <StateGlyph kind={kind} />
      <Icon {...ICON_PROPS} size={18} className="shrink-0 text-fg-muted" aria-hidden />
      {/* The record term is a name — "G1 · MODEL_APPROVED" — so the digit in it is part
          of a gate's name, not a value this row measured. Marked as a label, the same
          way every other verbatim identifier on screen is; extending the numeral walk's
          object-id exemption to cover bare gate names instead would weaken that walk
          everywhere to say something true only here. */}
      <span className="min-w-0 truncate">{view.label}{explain && <span className="og-mono text-m2 text-fg-muted" data-num="label"> {view.record}</span>}</span>
      <span className={`ml-auto og-mono text-m2 ${kind === 'needs' ? 'text-act-text' : 'text-fg-muted'}`}>
        {count > 0 ? <Num value={count} from={needs?.episode ?? 'needs'} /> : kind === 'later' ? <span aria-hidden>·</span> : ''}
      </span>
    </NavLink>
  );
}

export function ProgressMap({ needs, episodeState, hasEpisode }: { needs: NeedsResponse | null; episodeState: string | null; hasEpisode: boolean }) {
  const home = VIEWS.find((v) => v.key === 'needs')!;
  const stages = STAGE_KEYS.map((k) => VIEWS.find((v) => v.key === k)!);
  const registers = VIEWS.filter((v) => v.group === 'register');
  return (
    <nav className="map border-r border-hairline px-3 py-4" aria-label="Where this decision stands">
      <div className="map__group mb-4">
        <span className="map__head og-label block px-1.5 pb-1.5 text-b3 text-fg-muted">Where this decision stands</span>
        <Row view={home} needs={needs} state={episodeState} hasEpisode={hasEpisode} />
        {stages.map((v) => <Row key={v.key} view={v} needs={needs} state={episodeState} hasEpisode={hasEpisode} />)}
      </div>
      <div className="map__group mb-4">
        <span className="map__head og-label block px-1.5 pb-1.5 text-b3 text-fg-muted">Registers</span>
        {registers.map((v) => <Row key={v.key} view={v} needs={needs} state={episodeState} hasEpisode={hasEpisode} />)}
      </div>
      <div className="map__key px-1.5">
        <span className="map__head og-label block pb-1.5 text-b3 text-fg-muted">What the colours mean</span>
        <ColourKey compact />
      </div>
    </nav>
  );
}
