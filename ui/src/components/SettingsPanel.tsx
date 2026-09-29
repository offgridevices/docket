// The model settings slide-over (plan Task 8, "Settings slide-over") — a slide-over,
// not a page, so a model can be swapped mid-demo without leaving the screen it was on.
// Every field here maps to exactly one route in `src/docket/api/routes/settings.py`;
// nothing is computed, and the one security-sensitive control (the API key) never
// receives a value from a GET — there is nothing to populate it with, and rendering a
// placeholder that looked like a key would teach the operator that the server keeps one.
//
// Brand v3.0 (§5, §5a) changes how this looks and nothing about what it does. Section
// headings and field labels are sentence case in `og-label`; mono is kept for the things
// that are genuinely identifiers or coordinates — a provider name, a base URL, a model
// id, an actor id, a kernel version, the key itself. The panel is the whole screen below
// 768px and the same 448px slide-over above it. Every control, the mode radios included,
// clears the 44px touch floor. No Ember anywhere: this panel asks nothing irreversible.
//
// Two properties are load-bearing and unchanged by any of that: the key field is a
// password input that is never pre-filled and never persisted, and there is no control
// of any kind offering the denylist override — one sentence naming the environment
// variable, and nothing to click.

import { useEffect, useState } from 'react';
import { KeyRound, Save, SquareMinus, X } from 'lucide-react';
import { apiDelete, ApiError, apiGet, apiPut } from '../api/client';
import { ICON_PROPS } from '../lib/icons';
import type {
  HealthResponse,
  SettingsActorResponse,
  SettingsKeyResponse,
  SettingsModeResponse,
  SettingsModelResponse,
  SettingsModelsResponse,
} from '../types/api';

export interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

// Mirrors `routes/settings.py`'s own `KNOWN_PROVIDERS` — that module keeps it as a
// literal tuple rather than a shared constant (its own comment: "this task's file
// scope does not extend to adding one"), so this is the same kind of local mirror, not
// a second source of truth this UI invented independently.
const KNOWN_PROVIDERS = ['recorded', 'openai-compatible', 'anthropic'] as const;
const MODES = ['live', 'recorded', 'auto'] as const;

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

function SaveBadge({ state, message }: { state: SaveState; message?: string | null }) {
  // Three words about what just happened — prose, so `og-label`, not mono.
  if (state === 'saving') return <span className="og-label text-b3 text-fg-muted">saving…</span>;
  if (state === 'saved') return <span className="og-label text-b3 text-fg-muted">saved</span>;
  if (state === 'error') return <span className="text-b3 text-accent-text">{message}</span>;
  return null;
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [modelSettings, setModelSettings] = useState<SettingsModelResponse | null>(null);
  const [models, setModels] = useState<SettingsModelsResponse['models']>([]);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [keyPresent, setKeyPresent] = useState(false);
  const [mode, setMode] = useState<SettingsModeResponse['mode']>('auto');
  const [actorId, setActorId] = useState('');
  const [health, setHealth] = useState<HealthResponse | null>(null);

  const [providerDraft, setProviderDraft] = useState('');
  const [baseUrlDraft, setBaseUrlDraft] = useState('');
  const [modelDraft, setModelDraft] = useState('');
  const [connectionSave, setConnectionSave] = useState<SaveState>('idle');
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const [actorDraft, setActorDraft] = useState('');
  const [actorSave, setActorSave] = useState<SaveState>('idle');
  const [actorError, setActorError] = useState<string | null>(null);

  const [keyDraft, setKeyDraft] = useState('');
  const [keySave, setKeySave] = useState<SaveState>('idle');

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    setModelsError(null);
    // [T8 spec run-in] `Promise.all` used to fail this whole load the moment any one
    // of the six requests rejected — and `GET /settings/models` always does, on a
    // fresh install with no `llm.json` and no `DOCKET_LLM_BASE_URL`: the default
    // provider is "recorded" with an empty `baseUrl`, and `list_models` (plan 04's
    // "live network: never called from a test") still tries `httpx.get(f"{baseUrl}/
    // models")` unconditionally, which throws `UnsupportedProtocol` on the empty
    // string and surfaces here as a 502. That one, genuinely-optional section (the
    // live model catalogue) must not take the API key field, the actor id and the
    // mode switch down with it — `Promise.allSettled` lets each of the six resolve or
    // fail independently, so the rest of the panel still renders whatever it has.
    Promise.allSettled([
      apiGet<SettingsModelResponse>('/settings/model'),
      apiGet<SettingsModelsResponse>('/settings/models'),
      apiGet<SettingsKeyResponse>('/settings/key'),
      apiGet<SettingsModeResponse>('/settings/mode'),
      apiGet<SettingsActorResponse>('/settings/actor'),
      apiGet<HealthResponse>('/health'),
    ])
      .then(([ms, mm, key, md, actor, h]) => {
        if (cancelled) return;
        if (ms.status === 'fulfilled') {
          setModelSettings(ms.value);
          setProviderDraft(ms.value.provider);
          setBaseUrlDraft(ms.value.baseUrl);
          setModelDraft(ms.value.model);
        } else {
          setLoadError(ms.reason instanceof Error ? ms.reason.message : String(ms.reason));
        }
        if (mm.status === 'fulfilled') {
          setModels(mm.value.models);
        } else {
          setModels([]);
          setModelsError(mm.reason instanceof Error ? mm.reason.message : String(mm.reason));
        }
        if (key.status === 'fulfilled') setKeyPresent(key.value.keyPresent);
        if (md.status === 'fulfilled') setMode(md.value.mode);
        if (actor.status === 'fulfilled') {
          setActorId(actor.value.actorId);
          setActorDraft(actor.value.actorId);
        }
        if (h.status === 'fulfilled') setHealth(h.value);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  async function saveConnection() {
    setConnectionSave('saving');
    setConnectionError(null);
    try {
      const res = await apiPut<SettingsModelResponse>('/settings/model', {
        provider: providerDraft,
        baseUrl: baseUrlDraft,
        model: modelDraft,
      });
      setModelSettings(res);
      setConnectionSave('saved');
    } catch (err) {
      setConnectionSave('error');
      setConnectionError(
        err instanceof ApiError ? (err.body.message ?? err.message) : err instanceof Error ? err.message : String(err),
      );
    }
  }

  async function saveActor() {
    setActorSave('saving');
    setActorError(null);
    try {
      const res = await apiPut<SettingsActorResponse>('/settings/actor', { actorId: actorDraft });
      setActorId(res.actorId);
      setActorDraft(res.actorId);
      setActorSave('saved');
    } catch (err) {
      setActorSave('error');
      setActorError(
        err instanceof ApiError ? (err.body.message ?? err.message) : err instanceof Error ? err.message : String(err),
      );
    }
  }

  async function saveKey() {
    setKeySave('saving');
    try {
      const res = await apiPut<SettingsKeyResponse>('/settings/key', { apiKey: keyDraft });
      setKeyPresent(res.keyPresent);
      setKeySave('saved');
    } catch {
      setKeySave('error');
    } finally {
      // Cleared in the same tick as the PUT resolves, success or failure alike — the
      // value must not sit in React state for a screenshot to catch (honesty rule 6).
      setKeyDraft('');
    }
  }

  async function deleteKey() {
    setKeySave('saving');
    try {
      const res = await apiDelete<SettingsKeyResponse>('/settings/key');
      setKeyPresent(res.keyPresent);
      setKeySave('saved');
    } catch {
      setKeySave('error');
    }
  }

  async function changeMode(next: SettingsModeResponse['mode']) {
    const prev = mode;
    setMode(next);
    try {
      await apiPut<SettingsModeResponse>('/settings/mode', { mode: next });
    } catch {
      setMode(prev);
    }
  }

  return (
    <aside
      className="fixed inset-0 z-50 w-full og-bg-sunken border-hairline p-6 overflow-y-auto flex flex-col gap-6 md:inset-y-0 md:left-auto md:right-0 md:max-w-md md:border-l"
      role="dialog"
      aria-label="settings"
    >
      <div className="flex items-center justify-between">
        <h2 className="og-display text-e2">Settings</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="close settings"
          className="-mr-2 inline-flex min-h-11 min-w-11 items-center justify-center text-fg-muted"
        >
          {/* The glyph stays small; the hit area is 44px (§5a). */}
          <X {...ICON_PROPS} size={20} aria-hidden />
        </button>
      </div>

      {loading && <p className="og-label text-b3 text-fg-muted">loading…</p>}
      {loadError && <p className="text-b3 text-accent-text">{loadError}</p>}

      {modelSettings && (
        <>
          <section className="flex flex-col gap-3 border-t border-hairline pt-4">
            <h3 className="og-label text-b2">Connection</h3>
            <label className="flex flex-col gap-1">
              <span className="og-label text-b3 text-fg-muted">provider</span>
              <select
                value={providerDraft}
                onChange={(e) => setProviderDraft(e.target.value)}
                className="og-mono text-m1 min-h-11 border border-hairline bg-transparent px-2"
              >
                {KNOWN_PROVIDERS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="og-label text-b3 text-fg-muted">base URL</span>
              <input
                type="text"
                value={baseUrlDraft}
                onChange={(e) => setBaseUrlDraft(e.target.value)}
                className="og-mono text-m1 min-h-11 border border-hairline bg-transparent px-2"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="og-label text-b3 text-fg-muted">model</span>
              {/* `data-model-id` (plan 07 Task 10): this control and the raw-object
                  drawer are the only two surfaces in the app that print a concrete model
                  id at all. The slide-over is never captured by a documentation figure — the
                  attribute is here so the rule "every element that could print a model id
                  carries it" is literally true, not because a figure is expected to
                  contain one. */}
              <select
                value={modelDraft}
                onChange={(e) => setModelDraft(e.target.value)}
                data-model-id
                className="og-mono text-m1 min-h-11 border border-hairline bg-transparent px-2"
              >
                {modelDraft && !models.some((m) => m.id === modelDraft) && (
                  <option value={modelDraft}>{modelDraft}</option>
                )}
                {models.map((m) => (
                  <option key={m.id} value={m.id} disabled={m.denylisted}>
                    {m.denylisted
                      ? `⊘ ${m.id} — denylisted${m.reason ? ` (${m.reason})` : ''}`
                      : m.id}
                  </option>
                ))}
              </select>
            </label>
            {models.some((m) => m.denylisted) && (
              <p className="text-b3 text-fg-muted inline-flex items-center gap-1">
                <SquareMinus {...ICON_PROPS} size={14} className="shrink-0" aria-hidden /> denylisted models are disabled above
              </p>
            )}
            {modelsError && (
              <p className="text-b3 text-accent-text">{modelsError}</p>
            )}
            {/* Honesty and safety in the UI #5: no toggle, no checkbox, no "advanced"
                panel. This sentence is the whole affordance. */}
            <p className="text-b2 text-fg-secondary">
              The override is an environment variable, deliberately not offered here.
            </p>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={saveConnection}
                className="og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center gap-2 self-start border border-hairline-strong px-3"
              >
                <Save {...ICON_PROPS} size={16} className="shrink-0" aria-hidden /> save
              </button>
              <SaveBadge state={connectionSave} message={connectionError} />
            </div>
          </section>

          <section className="flex flex-col gap-2 border-t border-hairline pt-4">
            <h3 className="og-label text-b2 inline-flex items-center gap-2">
              <KeyRound {...ICON_PROPS} size={16} className="shrink-0" aria-hidden /> API key
            </h3>
            <input
              type="password"
              autoComplete="off"
              name="docket-api-key"
              value={keyDraft}
              onChange={(e) => setKeyDraft(e.target.value)}
              className="og-mono text-m1 min-h-11 border border-hairline bg-transparent px-2"
            />
            <p className="text-b3 text-fg-secondary">held in memory for this session; never written to disk</p>
            <div className="flex flex-wrap items-center gap-3">
              <span className="og-label text-b3" data-num="label">
                key present: {keyPresent ? 'yes' : 'no'}
              </span>
              <button
                type="button"
                onClick={saveKey}
                disabled={!keyDraft}
                className="og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center border border-hairline-strong px-3"
              >
                save key
              </button>
              <button
                type="button"
                onClick={deleteKey}
                className="og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center border border-hairline px-3"
              >
                clear
              </button>
              <SaveBadge state={keySave} />
            </div>
          </section>

          <section className="flex flex-col gap-2 border-t border-hairline pt-4">
            <h3 className="og-label text-b2">Actor</h3>
            <input
              type="text"
              value={actorDraft}
              onChange={(e) => setActorDraft(e.target.value)}
              className="og-mono text-m1 min-h-11 border border-hairline bg-transparent px-2"
            />
            <p className="text-b3 text-fg-secondary">
              current: <span className="og-mono">{actorId}</span> — every human approval on this machine is
              attributed to this id.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={saveActor}
                className="og-label text-b3 inline-flex min-h-11 min-w-11 items-center justify-center self-start border border-hairline-strong px-3"
              >
                save actor
              </button>
              <SaveBadge state={actorSave} message={actorError} />
            </div>
          </section>

          <section className="flex flex-col gap-2 border-t border-hairline pt-4">
            <h3 className="og-label text-b2">Mode</h3>
            <div className="flex flex-wrap gap-3">
              {MODES.map((m) => (
                // The mode name is printed as the server spells it — lower case, like
                // every other value this panel echoes back. v1.2 shouted it through
                // `toUpperCase()`, which is the same violation as an ALL-CAPS literal by
                // another route (§5: nothing in the interface is uppercase).
                //
                // The radio itself covers the whole 44px label rather than sitting in it
                // at its native 13px: §5a's touch floor applies to the control, and a
                // transparent input laid over the row keeps native radio semantics —
                // keyboard focus, arrow keys, `:checked` — instead of re-implementing
                // them on a div. The visible mark beside the word is the square the
                // brand's radius-0 geometry asks for.
                <label
                  key={m}
                  className="og-label text-b3 relative inline-flex min-h-11 min-w-11 items-center gap-2 px-2"
                >
                  <input
                    type="radio"
                    name="docket-mode"
                    checked={mode === m}
                    onChange={() => changeMode(m)}
                    className="absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0"
                  />
                  <span
                    aria-hidden
                    className={`h-3 w-3 border ${
                      mode === m ? 'border-fg bg-fg' : 'border-hairline-strong'
                    }`}
                  />
                  {m}
                </label>
              ))}
            </div>
          </section>

          {health && (
            <section className="flex flex-col gap-1 border-t border-hairline pt-4">
              <h3 className="og-label text-b2">Status</h3>
              <p className="og-label text-b3 text-fg-muted">
                {/* An identifier, not a value — the same `data-num="label"` treatment
                    `kernelVersion` gets everywhere else it's printed. */}
                kernel <span className="og-mono" data-num="label">{health.kernelVersion}</span>
              </p>
              <p className="og-label text-b3 text-fg-muted">
                backend reachable: {health.backend.reachable ? 'yes' : 'no'}
              </p>
              <p className="og-label text-b3 text-fg-muted">
                denylist active: {health.denylistActive ? 'yes' : 'no'}
              </p>
              {health.configRefused && (
                <p className="text-b3 text-accent-text">{health.configRefusedMessage}</p>
              )}
            </section>
          )}
        </>
      )}
    </aside>
  );
}
