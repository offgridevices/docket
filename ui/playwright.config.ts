// Plan 07 Task 9 Part A. `@playwright/test` is not yet installed in this worktree (no
// network access when this file was written — see `e2e/README.md` for the install
// line); this config is written against its documented API and has not been run.
//
// `testDir` points at `./e2e`, not `./tests/e2e`: Tasks 6-8 already wrote their
// per-screen specs there (see the ledger's ruling, `.superpowers/sdd/
// 2026-09-05-docket-07-frontend/progress.md`, "T6-T8 write their Playwright specs under
// ui/e2e/ but do not run them — T9 installs Playwright and runs every spec") — that
// ruling supersedes the plan text's literal `ui/tests/e2e/` path, and `ui/e2e/*.spec.ts`
// already exist on disk (`evidence.spec.ts`, `timeline.spec.ts`, `package.spec.ts`,
// `settings.spec.ts`), each importing `@playwright/test` directly. Matching the real
// location means this config finds them the moment the dependency is installed, with no
// further edits.
//
// Two projects: `smoke` runs the per-screen and choreography specs (Task 9 Part B) at a
// laptop-ish viewport; `figures` is the deliberately larger, DPR-2, forced-light profile
// the documentation figures use and is never part of the default `smoke` run.
//
// `webServer` starts the real API+UI on port 8766 (not the demo's own default 8765 —
// `ui/vite.config.ts`'s own dev-proxy target already reserves 8766 for exactly this) in
// `recorded` mode, against a throwaway state directory, with a fixed actor — a
// Playwright run must never touch a developer's real `~/.local/share/docket` sessions
// and must never reach a live LLM (R9: no test may reach the network).
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

const HERE = path.dirname(fileURLToPath(import.meta.url));

// The committed recording the agent routes replay in recorded mode. `DOCKET_LLM_RECORDING`
// otherwise defaults to `tests/fixtures/recorded/default.json`, which is committed EMPTY
// on purpose (`tests/fixtures/recorded/README.md`, ruling N3) — so without this the
// Intake screen's ELICIT button 503s with `RecordingMissing` and the G1 choreography has
// no DRAFT episode to run against. Set here rather than in `docket ui` because which
// fixture a demo replays is a property of the run, not of the command (flagged for Task 9
// Part B / Task 10 in the Task 6 report: `make demo` needs the same variable).
const RECORDING = path.join(HERE, '..', 'tests', 'fixtures', 'recorded', 'elicit.json');

// [plan 07 Task 9 Part B] A run's own throwaway state directory — `DOCKET_STATE_DIR`
// itself, below, and also where `DOCKET_LLM_CONFIG` now points (added this task): before
// this, the webServer left `DOCKET_LLM_CONFIG` unset, so `PUT /api/settings/model`
// (`fallback.spec.ts`'s own mechanism for switching the provider live) persisted to
// `~/.config/docket/llm.json` — a REAL file on whoever's machine runs this suite, never
// cleaned up and never isolated between runs. `tests/api/conftest.py` already isolates
// this per pytest; the browser-driven server had no equivalent. One directory for both,
// so a fresh `DOCKET_STATE_DIR` also means a fresh model config, matching "green twice on
// fresh state dirs".
const STATE_DIR = process.env.DOCKET_STATE_DIR ?? '.playwright-state';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8766',
  },
  projects: [
    // [plan 07 Task 10] The two projects are disjoint by file, not merely by intent:
    // without `testIgnore`, `--project=smoke` would run `figures.spec.ts` at 1440 x 900,
    // DPR 1 and silently overwrite the figure PNGs with smaller ones; and
    // without `testMatch`, `--project=figures` would re-run all 54 smoke tests at DPR 2
    // for nothing.
    {name: 'smoke',   testIgnore: /figures\.spec\.ts/,
                      use: {...devices['Desktop Chrome'], viewport: {width: 1440, height: 900}}},
    {name: 'figures', testMatch: /figures\.spec\.ts/,
                      use: {...devices['Desktop Chrome'], viewport: {width: 1600, height: 1000},
                            deviceScaleFactor: 2}},
  ],
  webServer: {command: 'uv run docket ui --no-open --port 8766',
              url: 'http://127.0.0.1:8766/api/health', reuseExistingServer: !process.env.CI,
              // `DOCKET_STATE_DIR` defers to the invoking shell so a run can be given a
              // fresh, throwaway state directory (`DOCKET_STATE_DIR=/tmp/... npx
              // playwright test`) and prove it is not carrying sessions over from the
              // last one; `.playwright-state` stays the default for a bare run.
              //
              // No `DOCKET_LLM_PROVIDER` here (removed this task): `DOCKET_UI_MODE=
              // recorded` already forces every agent-stage route to the recorded
              // backend regardless of provider (`routes/agent.py::_settings_for`), and
              // `resolve_settings()`'s own precedence falls back to `"recorded"` by
              // default with no provider configured at all — so removing the fixed env
              // var changes nothing for every test that never touches Settings, and is
              // what makes `PUT /api/settings/model` (`fallback.spec.ts`) able to
              // change what `GET /api/health` actually probes: a fixed env var here
              // would outrank anything that route persists to the config file, on
              // every request, permanently.
              env: {DOCKET_UI_MODE: 'recorded',
                    DOCKET_STATE_DIR: STATE_DIR,
                    DOCKET_UI_ACTOR: process.env.DOCKET_UI_ACTOR ?? 'shreyash',
                    DOCKET_LLM_RECORDING: RECORDING,
                    DOCKET_LLM_CONFIG: path.join(STATE_DIR, 'llm-config.json')}},
});
