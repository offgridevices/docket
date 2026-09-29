// Readiness (Task 14): the record scored against the standard — thirty-six cells tinted
// by the state the kernel gave each question, the blockers as red rows naming their own
// rule, the gate ladder, and the two honesty captions the server writes.
//
// Five tests, one per state the record can be in. Demo A is
// `PENDING_SIGNATURE` with a stored report that has no blockers, so it proves the read
// side at every viewport: the tint per cell is cross-checked against the server's own
// `ratings[]` (never a number this spec invents), the state line is the server's own
// `readyText`, and the view carries no Ember at all — the kernel scores the record, so
// nothing here is a human act asking for the screen's one fill. Demo B's
// `ep-omfv-2020-02-r5` is the not-ready case: 146 stored blockers of a handful of rules,
// each a red row, and the tailoring's own honesty note beside the grid. A freshly
// elicited DRAFT episode has no report at all, which is the offer to score one. The last
// two are the state the kernel withdraws in words — a report the record has moved under:
// once as every superseded Demo B revision already has it on record, and once
// constructed, for the one pair of values (withdrawn sentence, stored `ready: true`) that
// nothing in the record reaches.
//
// The blocker count is read off `GET .../readiness` rather than hardcoded, for the same
// reason the old spec read the applicable count off the server: a fixture change must not
// silently pass a stale assertion.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { goTo, openDecision } from './_session';

const HERE = path.dirname(fileURLToPath(import.meta.url));

/** The sentence `kernel.render.ready_text` substitutes for the stored `ready` boolean
 * when the record has moved under the report — read out of the kernel, never retyped
 * here, the same rule `_fixtures.footerSentences` follows for the footer: a spec must
 * fail when the source of a mandated sentence changes, not merely when a second copy of
 * it does. */
function stalenessSentence(): string {
  const src = readFileSync(path.join(HERE, '..', '..', 'src', 'docket', 'kernel', 'render.py'), 'utf8');
  const match = src.match(/return "(unavailable[^"]*)"/);
  if (!match) throw new Error('kernel.render.ready_text no longer returns a one-line staleness sentence; this helper needs updating');
  return match[1];
}

interface Rating { applicable: boolean; state: number | null }
interface ReadinessStub { ready: boolean; blockers: unknown[]; standardsAssessment: { ratings: Rating[] } | null; standardsCaptions: { ratingScale: string; tailoringNote: string | null }; readyText: string }

test.describe('Readiness', () => {
  forEachViewport(() => {
    test('Demo A: thirty-six cells tinted by state, exactly the applicable count lit, three verdicts, the standing captions', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-a');
      await goTo(page, 'Readiness');
      await expect(page.getByRole('heading', { name: 'Readiness' })).toBeVisible();
      const cells = page.locator('[data-testid="grid-cell"]');
      await expect(cells.first()).toBeVisible({ timeout: 15_000 });
      expect(await cells.count()).toBe(36);
      const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
      const body = (await (await page.request.get(`/api/session/${sessionId}/episode/ep-cbo-2013/readiness`)).json()) as ReadinessStub;
      const ratings = body.standardsAssessment!.ratings;
      const applicable = ratings.filter((r) => r.applicable).length;
      expect(await page.locator('[data-testid="grid-cell"][data-cell-state]:not([data-cell-state="na"])').count()).toBe(applicable);
      expect(await page.locator('[data-testid="grid-cell"][data-cell-state="na"]').count()).toBe(36 - applicable);
      for (const s of [1, 2, 3]) {
        expect(await page.locator(`[data-testid="grid-cell"][data-cell-state="${s}"]`).count()).toBe(ratings.filter((r) => r.applicable && r.state === s).length);
      }
      expect(await page.locator('[data-testid="verdict-card"]').count()).toBe(3);
      await expect(page.getByText(body.standardsCaptions.ratingScale)).toBeVisible();
      await expect(page.locator('[data-ready-line]')).toContainText(body.readyText);
      await expect(page.locator('[data-ready-line] [data-sev="done"]')).toBeVisible();
      expect(await page.locator('[data-ember]').count()).toBe(0);
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  test('Demo B r5: every blocker is a red row with its rule, and the same count the status row shows', async ({ page }) => {
    // The numeral walk runs on THIS page above all others: 146 rows of kernel-authored
    // finding text is where an unmarked numeral is likeliest to appear, and the old spec
    // walked the not-ready page for exactly that reason. [review fix round 1, Minor 4]
    const errors = collectConsoleErrors(page);
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Readiness');
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const body = (await (await page.request.get(`/api/session/${sessionId}/episode/ep-omfv-2020-02-r5/readiness`)).json()) as ReadinessStub;
    expect(body.ready).toBe(false);
    const rows = page.locator('[data-blocker]');
    await expect(rows.first()).toBeVisible({ timeout: 15_000 });
    expect(await rows.count()).toBe(body.blockers.length);
    await expect(rows.first().locator('[data-sev="blocking"]')).toBeVisible();
    await expect(page.locator('[data-ready-line] [data-sev="blocking"]')).toBeVisible();
    await expect(page.getByTestId('tailoring-note')).toBeVisible();
    // The walk runs BEFORE Explain is switched on, and that ordering is load-bearing:
    // under Explain the frame's own map prints each view's record term ("G1 ·
    // MODEL_APPROVED", "G2 · PLAN_APPROVED"), and `G1` is an identifier the shared
    // walk's id regex does not exempt because it carries no hyphen. That is the frame's
    // question to answer, not this view's — reported in the task report. Everything this
    // view puts on the page is present either way; Explain only adds the rule ids
    // asserted below, which carry no digits at all.
    await assertNoUnbracketedNumerals(page);
    await page.getByRole('button', { name: 'Explain', exact: true }).click();
    await expect(rows.first().locator('.og-mono[data-rule]')).toBeVisible();
    expect(errors).toEqual([]);
  });

  // The staleness case, and it needs no fixture of its own: every SUPERSEDED Demo B
  // revision is already in it. Their reports' `blockers` lists were frozen when the graph
  // was smaller, so `validate` now raises blocking findings those reports never saw, and
  // `ready_text` withdraws the stored boolean in words for all four of them (checked
  // against the API: `ep-omfv-2020-02`, `-r2`, `-r3` and `-r4` all answer with the
  // substitution; only `-r5`, the current revision, still states its own `False`).
  //
  // What the glyph must do here is the whole point: the sentence says the answer is
  // unavailable, so the mark beside it may say neither "ready" nor "not ready". It waits.
  // [review fix round 1, Important 1]
  test('a report the record has moved under is withdrawn in words, and the glyph waits with it', async ({ page }) => {
    const stale = stalenessSentence();
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Readiness');
    await expect(page.locator('[data-ready-line]')).toBeVisible({ timeout: 15_000 });
    await page.locator('header').getByLabel('Episode').selectOption('ep-omfv-2020-02');
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const body = (await (await page.request.get(`/api/session/${sessionId}/episode/ep-omfv-2020-02/readiness`)).json()) as ReadinessStub;
    // The fixture is asserted to be in the state this test is about, before the view is
    // asked anything: a fixture that quietly stopped being stale would otherwise leave
    // this test passing on the wrong branch.
    expect(body.readyText).toBe(stale);
    const line = page.locator('[data-ready-line]');
    await expect(line).toContainText(stale, { timeout: 15_000 });
    await expect(line.locator('[data-sev="wait"]')).toBeVisible();
    expect(await line.locator('[data-sev="done"]').count()).toBe(0);
    expect(await line.locator('[data-sev="blocking"]').count()).toBe(0);
  });

  // The other half of the same rule, which no committed fixture reaches: a report whose
  // stored `ready` is TRUE and whose sentence has since been withdrawn. That is the pair
  // that reads worst — a green tick beside a sentence taking it back — and no act this
  // interface offers can produce it, because every human write that could raise a new
  // blocking finding is typed so that it cannot (rejecting an object writes an
  // `Exclusion` and leaves the object in the register, since an item that simply
  // vanished is `silent_omission`, itself blocking — `agent.review.reject`'s own
  // docstring; a full recorded elicitation into a Demo A session was checked live and
  // left `readyText` at `"True"`). So this one pair is constructed, out of the server's
  // own body with a single field replaced.
  test('a withdrawn sentence never carries the ready tick, whatever the stored boolean says', async ({ page }) => {
    const stale = stalenessSentence();
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.route('**/api/session/*/episode/*/readiness', async (route) => {
      const response = await route.fetch();
      const body = (await response.json()) as Record<string, unknown>;
      expect(body.ready).toBe(true);
      await route.fulfill({ response, json: { ...body, readyText: stale } });
    });
    await goTo(page, 'Readiness');
    const line = page.locator('[data-ready-line]');
    await expect(line).toContainText(stale, { timeout: 15_000 });
    await expect(line.locator('[data-sev="wait"]')).toBeVisible();
    expect(await line.locator('[data-sev="done"]').count()).toBe(0);
  });

  test('a decision with no report offers to score it, once, and the button is not Ember', async ({ page }) => {
    const { elicitRecorded } = await import('./_elicit');
    await elicitRecorded(page);
    await goTo(page, 'Readiness');
    await expect(page.getByText('No readiness report has been produced for this decision.')).toBeVisible();
    const score = page.getByRole('button', { name: 'Score the record against the standard' });
    await expect(score).toBeVisible();
    await expect(score).not.toHaveAttribute('data-ember', '');
  });
});
