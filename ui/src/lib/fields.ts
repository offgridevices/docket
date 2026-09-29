// The Fields control (spec §12): which fields a card list shows, minimal by default,
// remembered per list in localStorage under `docket.fields.<list>` — never in the record.
import { useCallback, useState } from 'react';

export interface FieldSpec {
  key: string;
  label: string;
  default: boolean;
}

function storageKey(list: string): string {
  return `docket.fields.${list}`;
}

function read(list: string, spec: FieldSpec[]): Record<string, boolean> {
  const base = Object.fromEntries(spec.map((f) => [f.key, f.default]));
  try {
    const raw = window.localStorage.getItem(storageKey(list));
    if (!raw) return base;
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    for (const f of spec) if (typeof parsed[f.key] === 'boolean') base[f.key] = parsed[f.key] as boolean;
  } catch {
    // an unreadable entry is the default set, not an error
  }
  return base;
}

export interface Fields {
  shown: Record<string, boolean>;
  toggle: (key: string) => void;
}

export function useFields(list: string, spec: FieldSpec[]): Fields {
  const [shown, setShown] = useState<Record<string, boolean>>(() => read(list, spec));
  // The write happens here, on the toggle, and nowhere else: a stored entry means a
  // person chose something. An effect keyed on `shown` cannot say that — it also runs on
  // mount, so merely opening a page would write today's defaults down as a preference,
  // and a later change to a list's defaults would then silently never reach anyone who
  // had once opened it. A "skip the first run" ref does not save that approach either:
  // `main.tsx` mounts the app inside `<StrictMode>`, which in development mounts,
  // unmounts and remounts every component, so the second mount's effect passes the
  // guard and writes anyway.
  const toggle = useCallback((key: string) => {
    const next = { ...shown, [key]: !shown[key] };
    setShown(next);
    try {
      window.localStorage.setItem(storageKey(list), JSON.stringify(next));
    } catch {
      // storage full or disabled: the choice lasts the session
    }
  }, [list, shown]);
  return { shown, toggle };
}
