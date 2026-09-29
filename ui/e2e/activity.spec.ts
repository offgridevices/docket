// Activity (spec §18) — the record's own append-only log, one plain sentence per entry.
//
// Every row this view prints is a `describe_log_entry` sentence the server wrote
// (`kernel/clock.py`), so this spec reads the same route the view reads and requires the
// two to agree, rather than hand-writing the sentences a browser must never compose.
//
// The default read is `?episode=<current>` — the "This episode only" toggle — so the
// count assertion queries the route WITH that parameter. Demo A's store proves the
// filter does something: its two rendered packages point at the episode and nothing
// points back, so the whole-session log is strictly longer than this episode's.

import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { goTo, openDecision } from './_session';

interface Entry { seq: number; layer: string; what: string; refused: boolean }

async function entries(page: import('@playwright/test').Page, query = ''): Promise<Entry[]> {
  const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
  return (await (await page.request.get(`/api/session/${sessionId}/activity${query}`)).json()).entries as Entry[];
}

test.describe('Activity', () => {
  forEachViewport(() => {
    test('Demo A: every log entry is a row with a plain sentence, newest first', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-a');
      await goTo(page, 'Activity');
      await expect(page.getByRole('heading', { name: 'Activity' })).toBeVisible();
      const rows = page.locator('[data-activity-row]');
      await expect(rows.first()).toBeVisible({ timeout: 15_000 });
      const log = await entries(page, '?episode=ep-cbo-2013');
      expect(await rows.count()).toBe(log.length);
      await expect(rows.first()).toContainText(log[0].what);
      const seqs = await rows.evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-seq'))));
      expect(seqs).toEqual([...seqs].sort((a, b) => b - a));
      await page.getByRole('checkbox', { name: 'The AI' }).uncheck();
      expect(await page.locator('[data-activity-row][data-layer="agent"]:visible').count()).toBe(0);
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  test('the episode toggle is the ?episode= filter, and says which log is on screen', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Activity');
    const rows = page.locator('[data-activity-row]');
    await expect(rows.first()).toBeVisible({ timeout: 15_000 });
    const mine = (await entries(page, '?episode=ep-cbo-2013')).length;
    const whole = (await entries(page)).length;
    expect(whole).toBeGreaterThan(mine);
    expect(await rows.count()).toBe(mine);
    await expect(page.getByText('ep-cbo-2013', { exact: false }).first()).toBeVisible();
    await page.getByRole('checkbox', { name: 'This episode only' }).uncheck();
    await expect(rows).toHaveCount(whole, { timeout: 15_000 });
    await expect(page.getByText('activity · whole session')).toBeVisible();
    // The three layer toggles are the other kind: they hide rows in this browser and
    // never change what was read. Demo A's log is people and the kernel, so putting
    // people away has to leave fewer rows on screen and no human row at all.
    await page.getByRole('checkbox', { name: 'People' }).uncheck();
    expect(await page.locator('[data-activity-row][data-layer="human"]:visible').count()).toBe(0);
    expect(await page.locator('[data-activity-row]:visible').count()).toBeLessThan(whole);
    expect(await rows.count()).toBe(whole);
  });

  test('a refused gate attempt is marked in red and says the refusal is on the record', async ({ page }) => {
    const { elicitRecorded } = await import('./_elicit');
    await elicitRecorded(page);
    await goTo(page, 'Model');
    const refused = page.waitForResponse((r) => /\/transition$/.test(r.url()));
    await page.locator('[data-gate="G1"]').getByRole('button', { name: /^Approve the model/ }).click();
    expect((await refused).status()).toBe(409);
    await goTo(page, 'Activity');
    const row = page.locator('[data-activity-row][data-refused]').first();
    await expect(row).toBeVisible({ timeout: 15_000 });
    await expect(row.locator('[data-sev="blocking"]')).toBeVisible();
  });
});
