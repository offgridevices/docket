// Plan 07 Task 9 Part B, Step 2: "health-driven recorded fallback, end to end." One
// spec, driven entirely through the real API and a real browser — no mocked route
// anywhere in this file — proving the whole chain a demo actually depends on when a
// live backend goes dark mid-event: health notices, the request wizard reacts, the one-click switch
// works, and an elicitation still succeeds against the committed recording.
//
// **Runs its own, private `docket ui` process, on its own port** — NOT the shared
// `webServer` every other spec in this suite talks to. This is deliberate, not extra
// ceremony: `PUT /api/settings/mode` and `PUT /api/settings/model` are PROCESS-WIDE
// state (`app.state.mode_override`, the on-disk model config), and this suite runs with
// `fullyParallel: true` across several workers hitting the ONE shared server at once. To
// exercise the two health states below this test needs `mode_override` away from
// `"recorded"` for a real (if brief) window — during which `routes/agent.py::
// _settings_for` would stop forcing every OTHER, concurrently-running spec's elicit/
// accept/dispatch call to the recorded backend too, and hand them this test's own
// deliberately-broken `openai-compatible` config instead. A private server removes the
// shared-state hazard entirely rather than racing it. The extra ~1–2s of process
// start-up is the cost of that; `test.setTimeout` below accounts for it.
//
// Two health states appear here, and the plan's own sentence names both without
// distinguishing them, so this file's own header does (confirmed by reading
// `views/Request.tsx`'s actual `unreachable` check, not assumed):
//
// 1. **No override at all** (`mode_override` unset, i.e. `"auto"`) + an unreachable
//    `openai-compatible` base URL: `resolve_settings()`'s own default is `"recorded"`
//    whenever nothing answers (`routes/health.py::_mode`), so `GET /api/health` reports
//    `backend.reachable: false`, `mode: "recorded"` — automatically, with nobody having
//    asked for anything. This is the scenario the plan's Step 2 sentence states
//    literally, and it is also `tests/api/test_recorded_fallback.py`'s own scenario (a
//    raw `TestClient`, no browser, no real subprocess) — this file re-proves the
//    identical health contract through a real, live `uvicorn` process and a real
//    browser, which a `TestClient` cannot: the process boundary, the real 2s probe
//    timeout, and a real socket refusal are all exercised here, not simulated.
// 2. **An explicit `mode: "live"` override** (a human told Settings "no, really, use
//    the live one") over the SAME unreachable base URL: `_settings_for`'s own
//    docstring is explicit that `"live"` means "do not fall back," so `mode` stays
//    `"live"` even though nothing answers — and THIS is the state `Request.tsx`'s own
//    `unreachable` check reads (`!reachable && mode === "live"`; in `mode: "recorded"`,
//    `unreachable` is always `false`, because "there is nothing to reach" once
//    recorded mode has already taken over — read straight from the component, not
//    assumed). Disabling ELICIT and offering the one-click switch is a rescue from an
//    operator's explicit, now-wrong choice, not a spontaneous reaction to reachability
//    alone — there is nothing to rescue from once recorded mode already applies on its
//    own, per (1).
//
// The "closed" port is bound then immediately closed (never merely "probably free") —
// the same discipline `tests/api/test_recorded_fallback.py` uses — so the refusal this
// test depends on is guaranteed, not timing-dependent.

import { type ChildProcess, spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import net from 'node:net';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import { assertNoUnbracketedNumerals, collectConsoleErrors } from './_fixtures';
import { ensureSession, loadRecordedRequest } from './_elicit';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.join(HERE, '..', '..');
const RECORDING = path.join(REPO_ROOT, 'tests', 'fixtures', 'recorded', 'elicit.json');

interface HealthPayload {
  mode: string;
  backend: { reachable: boolean; error: string | null };
}

/** A free loopback port: bind it, read back the OS-assigned port, close it. Used both
 * for the "always refused" backend port below (bind-then-close means a `connect()`
 * moments later gets ECONNREFUSED, not a timeout) and for picking this test's own
 * private server's port (bind-then-close-then-immediately-reuse is the standard,
 * accepted way to ask the OS for a free port when nothing else on this machine is
 * racing for one — this worktree's own test suite is the only thing running). */
async function freeLoopbackPort(): Promise<number> {
  const server = net.createServer();
  const port = await new Promise<number>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (address === null || typeof address === 'string') {
        reject(new Error('freeLoopbackPort: server.address() did not return a port'));
        return;
      }
      resolve(address.port);
    });
  });
  await new Promise<void>((resolve, reject) => {
    server.close((err) => (err ? reject(err) : resolve()));
  });
  return port;
}

async function waitForHealth(baseUrl: string, deadlineMs: number): Promise<void> {
  const deadline = Date.now() + deadlineMs;
  for (;;) {
    try {
      const res = await fetch(`${baseUrl}/api/health`);
      if (res.ok) return;
    } catch {
      // connection refused while the process is still starting — keep polling
    }
    if (Date.now() > deadline) {
      throw new Error(`${baseUrl}/api/health never answered within ${deadlineMs}ms`);
    }
    await new Promise((r) => setTimeout(r, 100));
  }
}

test.describe('health-driven recorded fallback', () => {
  test.setTimeout(60_000);

  test('an unreachable live backend falls back to recorded automatically, then the request wizard offers a rescue from an explicit live override, and recorded elicitation still works', async ({
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page);
    const closedPort = await freeLoopbackPort();
    const closedUrl = `http://127.0.0.1:${closedPort}/v1`;
    const serverPort = await freeLoopbackPort();
    const baseUrl = `http://127.0.0.1:${serverPort}`;
    const stateDir = mkdtempSync(path.join(tmpdir(), 'docket-fallback-spec-'));

    let child: ChildProcess | null = null;
    try {
      // A PRIVATE `docket ui` — see the file header on why this test does not touch
      // the shared `webServer`. No `DOCKET_UI_MODE`: `mode_override` starts unset
      // ("auto"), which is exactly what step 1 below needs.
      child = spawn(
        'uv',
        ['run', 'docket', 'ui', '--no-open', '--port', String(serverPort)],
        {
          cwd: REPO_ROOT,
          env: {
            ...process.env,
            DOCKET_STATE_DIR: stateDir,
            DOCKET_UI_ACTOR: 'shreyash',
            DOCKET_LLM_RECORDING: RECORDING,
            DOCKET_LLM_CONFIG: path.join(stateDir, 'llm-config.json'),
          },
          stdio: 'pipe',
        },
      );
      let startupOutput = '';
      child.stdout?.on('data', (d) => (startupOutput += d.toString()));
      child.stderr?.on('data', (d) => (startupOutput += d.toString()));
      child.once('exit', (code) => {
        if (code !== null && code !== 0) {
          // eslint-disable-next-line no-console
          console.error(`private docket ui exited early (${code}):\n${startupOutput}`);
        }
      });
      await waitForHealth(baseUrl, 20_000);

      // ---- 1. No override, unreachable openai-compatible: the automatic fallback ----
      const putModel = await fetch(`${baseUrl}/api/settings/model`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: 'openai-compatible', baseUrl: closedUrl }),
      });
      expect(putModel.ok, await putModel.text()).toBe(true);

      // Polled, not a single read: the plan's own budget is "under three seconds" (the
      // probe's own timeout is 2s), and a fresh `PUT` may race the next poll interval.
      const deadline = Date.now() + 3000;
      let health: HealthPayload;
      for (;;) {
        health = (await (await fetch(`${baseUrl}/api/health`)).json()) as HealthPayload;
        if (!health.backend.reachable) break;
        if (Date.now() > deadline) {
          throw new Error(
            `health never reported unreachable within 3s: ${JSON.stringify(health)}`,
          );
        }
        await new Promise((r) => setTimeout(r, 100));
      }
      expect(health.backend.reachable).toBe(false);
      expect(health.mode).toBe('recorded');

      // ---- 2. An explicit `live` override over the same unreachable backend: the
      //         state the request wizard's own `unreachable` check reads. ----
      const putLive = await fetch(`${baseUrl}/api/settings/mode`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'live' }),
      });
      expect(putLive.ok).toBe(true);
      const liveHealth = (await (await fetch(`${baseUrl}/api/health`)).json()) as HealthPayload;
      expect(liveHealth.mode).toBe('live'); // "live" means "do not fall back" — verbatim
      expect(liveHealth.backend.reachable).toBe(false);

      await page.goto(`${baseUrl}/request`);
      await ensureSession(page, 'new');
      await loadRecordedRequest(page, baseUrl);

      await expect(page.getByRole('button', { name: /^elicit$/i })).toBeDisabled();
      await expect(page.getByText('No backend reachable').first()).toBeVisible();

      // ---- 3. The one-click switch. ----
      const modeSwitch = page.waitForRequest(
        (r) => r.url().endsWith('/api/settings/mode') && r.method() === 'PUT',
      );
      await page.getByRole('button', { name: 'Switch to recorded' }).click();
      const switchReq = await modeSwitch;
      expect(switchReq.postDataJSON()).toEqual({ mode: 'recorded' });

      // No reload needed here (unlike `request.spec.ts`'s mocked version, which unroutes
      // a `page.route` interception first): the server-side mode really changed, so the
      // next `health.refetch()` the switch triggers reads the real, new value.
      await expect(page.getByRole('button', { name: /^elicit$/i })).toBeEnabled({
        timeout: 5_000,
      });

      // ---- 4. Elicit in recorded mode actually succeeds, end to end, against the
      //         committed recording — the whole point of the fallback. ----
      const elicited = page.waitForResponse(
        (r) => /\/api\/session\/[^/]+\/elicit$/.test(r.url()) && r.request().method() === 'POST',
      );
      await page.getByRole('button', { name: /^elicit$/i }).click();
      const elicitResponse = await elicited;
      expect(elicitResponse.status(), await elicitResponse.text()).toBe(200);
      await expect(page.locator('[data-object-id]').first()).toBeVisible({ timeout: 15_000 });

      await assertNoUnbracketedNumerals(page);
      // Every request in this flow is expected to succeed by the end (this is a
      // private server nobody else's refused calls could pollute) — a console error
      // at any point is a real regression, with no exemption needed.
      expect(consoleErrors).toEqual([]);
    } finally {
      child?.kill();
      rmSync(stateDir, { recursive: true, force: true });
    }
  });
});
