// Plan 07 Task 9 Part B: the opt-in live run. Gated on `DOCKET_LIVE_OLLAMA=1` —
// skipped otherwise, and never expected to run in CI (the checked-in
// `.github/workflows/ci.yml` runs pytest/ruff/lint/determinism/audit steps only; it
// never invokes Playwright at all today, and must never be given this variable if that
// changes). This is the one spec in the suite allowed to reach a real network
// endpoint, and only ever `127.0.0.1:11434` (a local Ollama server) — never anything
// else, per R9 ("no test may reach the network") read narrowly: this is the
// deliberate, opt-in exception the ledger's LIVE OLLAMA PROBE entry already exercised
// once by hand; this file is that probe, repeatable and driven entirely through the
// browser instead of `curl`.
//
// **Its own private `docket ui` process**, exactly like `fallback.spec.ts` and for the
// same reason: switching provider/mode is process-wide state, this suite runs
// `fullyParallel: true`, and a live model call can legitimately take minutes — nothing
// about that should touch the shared `webServer` every other spec in this run depends
// on.
//
// Model policy, restated from the ledger (`.superpowers/sdd/2026-09-05-docket-07-
// frontend/progress.md`, "Local Ollama check" and "LIVE OLLAMA PROBE" entries) so this
// file's own intent is checkable without cross-referencing it: `gemma4:e4b` is the
// only model this test may select and run. `qwen3.8:27b-mlx` and `qwen3.6:35b-mlx` are
// PRC-origin, denylisted, and must never be listed (by policy, `agent.backend.
// list_models`'s default already drops them) or used. `muse-glimmer:30b-mlx` is NOT
// denylisted (it lists, and could be selected) but its origin is unknown — this test
// selects `gemma4:e4b` explicitly, by id, never "whatever the list contains that isn't
// denylisted", so a future Ollama pull that changes what is cached locally cannot
// silently swap in a model this test never vetted.

import { type ChildProcess, spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import net from 'node:net';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import { ensureSession, loadRecordedRequest } from './_elicit';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.join(HERE, '..', '..');
const RECORDING = path.join(REPO_ROOT, 'tests', 'fixtures', 'recorded', 'elicit.json');

const OLLAMA_BASE_URL = 'http://127.0.0.1:11434/v1';
const LIVE_MODEL = 'gemma4:e4b';
// Denylisted (PRC-origin) — must never appear in the model picker at all, regardless
// of selection. Built from parts rather than written as contiguous literals, matching
// `session.spec.ts`'s own convention for a denylisted-looking id in a test — the point of
// this assertion is the shape of the policy, not these two specific family names.
const DENYLISTED_MODEL_SUBSTRINGS = [['q', 'wen3.8:27b-mlx'].join(''), ['q', 'wen3.6:35b-mlx'].join('')];

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

test.describe('live Ollama run (opt-in)', () => {
  test.skip(
    process.env.DOCKET_LIVE_OLLAMA !== '1',
    'set DOCKET_LIVE_OLLAMA=1 to run this against a real, local Ollama server; skipped otherwise (and never in CI)',
  );
  test.setTimeout(360_000); // the elicitation alone is allowed up to 300s below

  test('switches to gemma4:e4b through Settings, elicits for real, restores recorded mode', async ({
    page,
  }) => {
    const serverPort = await freeLoopbackPort();
    const baseUrl = `http://127.0.0.1:${serverPort}`;
    const stateDir = mkdtempSync(path.join(tmpdir(), 'docket-live-spec-'));

    let child: ChildProcess | null = null;
    try {
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

      // ---- 1. Point Settings at the local Ollama server and save. ----
      await page.goto(`${baseUrl}/`);
      await page.getByRole('button', { name: 'open settings' }).click();
      const panel = page.getByRole('dialog', { name: 'settings' });
      await expect(panel).toBeVisible();

      await panel.getByLabel('provider').selectOption('openai-compatible');
      await panel.getByLabel('base URL').fill(OLLAMA_BASE_URL);
      await panel.getByRole('button', { name: 'save', exact: true }).click();
      await expect(panel.getByText('saved')).toBeVisible({ timeout: 10_000 });

      // Close and reopen: `SettingsPanel.tsx` only refetches `/settings/models`
      // (against the newly-saved base URL) on open, not after a save within the same
      // session (confirmed by reading the component — `saveConnection` never calls the
      // models fetch itself).
      await page.getByRole('button', { name: 'close settings' }).click();
      await page.getByRole('button', { name: 'open settings' }).click();
      await expect(panel).toBeVisible();

      // ---- 2. No denylisted id anywhere in the picker. ----
      const modelSelect = panel.getByLabel('model');
      // `GET /settings/models` is an async fetch kicked off by the `open` effect —
      // give it a moment to land rather than reading the `<select>` on the same tick
      // the panel became visible.
      await expect(modelSelect.locator(`option:has-text("${LIVE_MODEL}")`)).toHaveCount(1, {
        timeout: 15_000,
      });
      const optionTexts = await modelSelect.locator('option').allTextContents();
      for (const denylisted of DENYLISTED_MODEL_SUBSTRINGS) {
        expect(
          optionTexts.some((t) => t.includes(denylisted)),
          `denylisted model ${denylisted} must never appear in the picker; saw: ${optionTexts.join(', ')}`,
        ).toBe(false);
      }
      expect(
        optionTexts.some((t) => t.includes(LIVE_MODEL)),
        `expected ${LIVE_MODEL} to be listed; saw: ${optionTexts.join(', ')}`,
      ).toBe(true);

      // ---- 3. Select gemma4:e4b explicitly, by id, and save again. ----
      await modelSelect.selectOption(LIVE_MODEL);
      await panel.getByRole('button', { name: 'save', exact: true }).click();
      await expect(panel.getByText('saved')).toBeVisible({ timeout: 10_000 });

      // ---- 4. Force live mode ("live" means "do not fall back" — the auto/recorded
      //         default would otherwise mask a real unreachable failure as a silent
      //         success against the recorded fixture instead). ----
      const liveRadio = panel.locator('label', { hasText: 'LIVE' }).locator('input[type="radio"]');
      await liveRadio.check();

      // ---- 5. Health reports live and reachable. ----
      await expect(panel.getByText('backend reachable: yes')).toBeVisible({ timeout: 15_000 });
      const health = await (await page.request.get(`${baseUrl}/api/health`)).json();
      expect(health.mode).toBe('live');
      expect(health.backend.reachable).toBe(true);
      expect(health.provider).toBe('openai-compatible');
      expect(health.model).toBe(LIVE_MODEL);

      await page.getByRole('button', { name: 'close settings' }).click();

      // ---- 6. Elicit for real, from the request wizard, with the committed request text. ----
      const elicitStart = Date.now();
      await page.goto(`${baseUrl}/request`);
      await ensureSession(page, 'new');
      await loadRecordedRequest(page, baseUrl);
      await expect(page.getByRole('button', { name: /^elicit$/i })).toBeEnabled();

      const elicited = page.waitForResponse(
        (r) => /\/api\/session\/[^/]+\/elicit$/.test(r.url()) && r.request().method() === 'POST',
        { timeout: 300_000 },
      );
      await page.getByRole('button', { name: /^elicit$/i }).click();
      const elicitResponse = await elicited;
      expect(elicitResponse.status(), await elicitResponse.text()).toBe(200);
      const elicitBody = await elicitResponse.json();
      const elicitMs = Date.now() - elicitStart;

      await expect(page.locator('[data-object-id]').first()).toBeVisible({ timeout: 300_000 });
      const chipCount = await page.locator('[data-object-id]').count();

      // ---- 7. The record actually says an agent wrote this, and the rail agrees. ----
      const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
      expect(sessionId).toBeTruthy();
      const episode = await (
        await page.request.get(`${baseUrl}/api/session/${sessionId}/episode/${elicitBody.episode.id}`)
      ).json();
      expect(episode.createdBy.actorType).toBe('agent');
      expect(episode.createdBy.actorId.startsWith('agent:')).toBe(true);

      const authority = await (
        await page.request.get(`${baseUrl}/api/session/${sessionId}/episode/${elicitBody.episode.id}/authority`)
      ).json();
      // The rail's MODEL count (`api.authority.authority_counts`'s `numerals.agent`)
      // is genuinely non-zero here, confirmed running this live — NOT a violation of
      // "the agent never sits in the numeric path": `tests/fixtures/recorded/
      // README.md`'s own ruling R16 names `Objective.priorityRank` as one of exactly
      // two model-authored values that are allowed to exist (the other is `Alternative.
      // baselineFlag`, a boolean, so it never reaches this integer counter) — a
      // structural ranking the model assigns while elicit()ing, confirmed by a human
      // at G1, never a computed decision value (a run, a result, a weight, an
      // observation). Nine elicited Objectives means at least nine such ranks; this
      // assertion is deliberately `toBeGreaterThan(0)`, not an exact count, since the
      // exact number depends on what the live model actually returned this run (see
      // the transcript below for what it was).
      expect(authority.numerals.agent).toBeGreaterThan(0);
      expect(authority.objects.agent).toBeGreaterThan(0);

      // ---- 8. Restore recorded mode. ----
      await page.getByRole('button', { name: 'open settings' }).click();
      await expect(panel).toBeVisible();
      const recordedRadio = panel.locator('label', { hasText: 'RECORDED' }).locator('input[type="radio"]');
      await recordedRadio.check();
      await page.getByRole('button', { name: 'close settings' }).click();
      const restoredHealth = await (await page.request.get(`${baseUrl}/api/health`)).json();
      expect(restoredHealth.mode).toBe('recorded');

      // eslint-disable-next-line no-console
      console.log(
        `[live.spec.ts transcript] elicit: ${elicitMs}ms; objects written: ${elicitBody.objects.length}; ` +
          `chips rendered: ${chipCount}; gaps: ${elicitBody.gaps.length}; ` +
          `episode: ${elicitBody.episode.id}; createdBy: ${JSON.stringify(episode.createdBy)}; ` +
          `authority: ${JSON.stringify(authority)}`,
      );
    } finally {
      child?.kill();
      rmSync(stateDir, { recursive: true, force: true });
    }
  });
});
