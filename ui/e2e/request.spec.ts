// File the request (spec §9) — the three-step wizard that replaces Intake.
//
// What is asserted here: the wizard really elicits the committed request and every card
// it draws is marked as the AI's proposal, in the order the server wrote them; the
// deadline field reaches `Charter.neededBy` on both paths (a fresh elicitation and a
// decision already open), the clock then counts to it, and clearing it puts the clock
// back; the one act refuses to fire without the one field that is a claim about a
// person; and the no-backend state disables that act and offers the one-click switch.
//
// Setting a deadline is a human revision of the charter, so it satisfies
// `charter-human-accepted` — recorded in the plan, not hidden. `charter-three-fields`
// still gates on content and the reviewer still fills the empty field, which is why the
// deadline never stands in for the Model view's own work.
//
// Three of the tests below are re-homed from the deleted `intake.spec.ts` (write order
// with an independent read-back, the requested-by refusal, the "answer recorded"
// advertisement): the screen they were written against is gone, the behaviours are not.

import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { elicitRecorded, ensureSession, loadRecordedRequest } from './_elicit';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { currentSessionId, openDecision } from './_session';

test.describe('File the request', () => {
  forEachViewport((viewport) => {
    test('the wizard elicits the recorded request; every card is drafted by the AI', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      const body = await elicitRecorded(page);
      await expect(page.getByRole('heading', { name: 'File the request' })).toBeVisible();
      await expect(page.locator('[data-object-id]')).toHaveCount(body.objects.length, { timeout: 15_000 });
      const marks = page.locator('[data-object-id] [data-mark]');
      expect(await marks.count()).toBe(body.objects.length);
      for (const obj of body.objects) {
        const card = page.locator(`[data-object-id="${obj.id}"]`);
        await expect(card.locator('[data-mark]')).toHaveAttribute('data-mark', 'agent-proposed');
        if (obj.provenance?.locator) await expect(card).toContainText(obj.provenance.locator);
      }
      await expect(page.getByText('Every object above is a proposal. Nothing here has been agreed, nothing has been computed, and the gate that decides is on the Model view.')).toBeVisible();
      // The header's episode chip is `hide-below-768` (Task 7's frame: the id is the
      // first thing off at phone width), so the id is asserted where the frame keeps it.
      if (viewport.width >= 768) await expect(page.locator('header').getByText(body.episode.id)).toBeVisible();
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      await page.getByRole('button', { name: 'Go to the model checklist' }).click();
      await expect(page).toHaveURL(/\/model$/);
      expect(errors).toEqual([]);
    });

    // The test above only ever sees step three. Steps one and two are two thirds of the
    // view and carry their own Ember (`Next`), their own controls and — with a decision
    // already open — the deadline form at the foot of the page, none of which the
    // elicitation path exercises at all.
    test('steps one and two conform at this width', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-a');

      await page.goto('/request?step=1');
      await expect(page.locator('textarea[name="request-text"]')).toBeVisible();
      await assertNoUnbracketedNumerals(page);
      await assertBrandConformance(page);
      await page.getByRole('button', { name: 'Load the recorded request' }).click();
      await expect(page.locator('textarea[name="request-text"]')).not.toHaveValue('');
      await assertNoUnbracketedNumerals(page);
      await assertBrandConformance(page);

      await page.goto('/request?step=2');
      await expect(page.locator('input[name="requested-by"]')).toBeVisible();
      // One deadline field on the page, not two: with a decision open, step two defers
      // to the form that can write the charter now.
      await expect(page.locator('[data-wizard] input[name="needed-by"]')).toHaveCount(0);
      await expect(page.locator('input[name="needed-by"]')).toHaveCount(1);
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  // [ruling M3, re-homed from `intake.spec.ts`] `body.objects` (the `/elicit` POST
  // response) never populates a card — the view's `objects` state is built exclusively
  // inside the SSE handler, in arrival order — so comparing the rendered order against
  // it is an independent check that the stream and the write are the same fact, in the
  // same order, not merely the same count.
  test('the streamed cards are the objects the server wrote, in write order', async ({ page, request }) => {
    const body = await elicitRecorded(page);
    const cardIds = await page.locator('[data-object-id]').evaluateAll((els) => els.map((el) => el.getAttribute('data-object-id') ?? ''));
    expect(cardIds).toEqual(body.objects.map((o) => o.id));

    // And read back independently, through the episode's own G1 sheet via `page.request`
    // rather than trusting the same POST response a second time: every id the stream
    // reported is really on the record.
    const sessionId = await currentSessionId(page);
    const g1 = await (await request.get(`/api/session/${sessionId}/episode/${body.episode.id}/g1`)).json();
    const onSheet = new Set<string>([
      ...g1.objects.map((o: { id: string }) => o.id),
      ...g1.gaps.map((g: { id: string }) => g.id),
    ]);
    for (const id of cardIds) {
      expect(onSheet.has(id), `${id} streamed but not on the episode's own G1 sheet`).toBe(true);
    }
  });

  // [re-homed from `intake.spec.ts`] `requestedBy` becomes `Charter.authority.signer` —
  // a claim about a person — so it has no default and the server refuses a blank one.
  test('Elicit refuses to fire without a requested-by, which has no default', async ({ page }) => {
    await page.goto('/request');
    await ensureSession(page, 'new');
    await page.goto('/request?step=1');
    await page.getByRole('button', { name: 'Load the recorded request' }).click();
    await expect(page.locator('textarea[name="request-text"]')).not.toHaveValue('');
    // Everything the recorded request fills, and nothing else: straight through step two
    // without typing the one field that is a claim about a person.
    await page.getByRole('button', { name: 'Next' }).click();
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page.locator('select[name="source-artifact"]')).not.toHaveValue('');
    await expect(page.getByRole('button', { name: /^elicit$/i })).toBeDisabled();
    await page.getByRole('button', { name: 'Previous' }).click();
    await page.locator('input[name="requested-by"]').fill('NGCV CFT');
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page.getByRole('button', { name: /^elicit$/i })).toBeEnabled();
  });

  // [re-homed from `intake.spec.ts`] This run points `DOCKET_LLM_RECORDING` at the
  // committed fixture, so the server's own key lookup must say the answer is there —
  // the view never guesses this.
  test('the committed request advertises whether its answer is actually recorded', async ({ page }) => {
    await page.goto('/request');
    await ensureSession(page, 'new');
    await expect(page.getByText('answer recorded', { exact: true })).toBeVisible();
  });

  test('step two writes the deadline the clock then counts to', async ({ page, request }) => {
    await page.goto('/request');
    await ensureSession(page, 'new');
    await loadRecordedRequest(page);
    await page.getByRole('button', { name: 'Previous' }).click();
    await page.locator('[data-wizard] input[name="needed-by"]').fill('2036-09-30');
    await page.getByRole('button', { name: 'Next' }).click();
    const accepted = page.waitForResponse((r) => /\/object\/[^/]+\/accept$/.test(r.url()));
    await page.getByRole('button', { name: /^elicit$/i }).click();
    const acceptBody = await (await accepted).json();
    expect(acceptBody.object.neededBy).toBe('2036-09-30');
    // The cards are on screen too: the deadline write is a second write, and a refusal
    // of it must never read as a failed elicitation.
    await expect(page.locator('[data-object-id]').first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'When it is due and who it waits on' })).toContainText('due in');
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const stored = await (await request.get(`/api/session/${sessionId}/object/${acceptBody.id}`)).json();
    expect(stored.object.neededBy).toBe('2036-09-30');
  });

  test('an open decision can set its deadline on the existing charter', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.goto('/request?step=2');
    const form = page.locator('[data-deadline-form]');
    await form.locator('input[name="needed-by"]').fill('2036-01-01');
    await form.getByRole('button', { name: 'Save the deadline' }).click();
    await expect(page.locator('[data-toast="done"]')).toContainText('Deadline set to 2036-01-01');
    await expect(page.getByRole('button', { name: 'When it is due and who it waits on' })).toContainText('due in');
    await expect(page.getByText('The request already on the record')).toBeVisible();
  });

  // The clear path the form's own toast promises. `accept` writes the edit onto the new
  // revision as it is given, so clearing stores an empty `neededBy` rather than removing
  // the field — and `kernel.clock` reads an unparseable deadline as no deadline, which is
  // exactly what the toast claims. Asserted on the record AND on the header chip.
  test('clearing the deadline puts the clock back to no deadline', async ({ page, request }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.goto('/request?step=2');
    const form = page.locator('[data-deadline-form]');
    await form.locator('input[name="needed-by"]').fill('2036-01-01');
    await form.getByRole('button', { name: 'Save the deadline' }).click();
    await expect(page.getByRole('button', { name: 'When it is due and who it waits on' })).toContainText('due in');

    await form.locator('input[name="needed-by"]').fill('');
    await form.getByRole('button', { name: 'Save the deadline' }).click();
    // 15 s, the timeout this suite gives every assertion that waits on a write: the toast
    // lives 4.2 s from the moment the `accept` round trip returns, so a 5 s window that
    // starts at the click is a race the whole eight-worker suite loses more often than it
    // wins (Task 18 recorded the first sighting; progress.md carried it forward).
    await expect(page.locator('[data-toast="done"]').last()).toContainText('Deadline cleared', { timeout: 15_000 });
    await expect(page.getByRole('button', { name: 'When it is due and who it waits on' })).toContainText('no deadline');

    const sessionId = await currentSessionId(page);
    const episodes = await (await request.get(`/api/session/${sessionId}/episodes`)).json();
    const charterId = episodes.episodes[0].charter;
    const stored = await (await request.get(`/api/session/${sessionId}/object/${charterId}`)).json();
    expect(stored.object.neededBy).toBe('');
  });

  test('no backend reachable in live mode disables Elicit and offers the one-click switch', async ({ page }) => {
    await page.route('**/api/health', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.backend = { ...body.backend, reachable: false };
      body.mode = 'live';
      await route.fulfill({ response, json: body });
    });
    await page.goto('/request');
    await ensureSession(page, 'new');
    await loadRecordedRequest(page);
    await expect(page.getByRole('button', { name: /^elicit$/i })).toBeDisabled();
    await expect(page.getByText('No backend reachable')).toBeVisible();
    await page.unroute('**/api/health');
    const modeSwitch = page.waitForRequest((r) => r.url().endsWith('/api/settings/mode') && r.method() === 'PUT');
    await page.getByRole('button', { name: 'Switch to recorded' }).click();
    expect((await modeSwitch).postDataJSON()).toEqual({ mode: 'recorded' });
    await expect(page.getByRole('button', { name: /^elicit$/i })).toBeEnabled({ timeout: 5_000 });
  });
});
