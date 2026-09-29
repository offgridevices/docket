// Ask about this decision (spec §7), from the client's side: the nine chips the server
// names, an answer whose cites open the stored object and whose actions navigate, the
// fallback's own chips (which ask rather than navigate), one thread per decision, and
// `/ask?q=…`. The chat reads the record and never writes to it — the activity log has
// the same number of entries after an exchange as before it, asserted here rather than
// assumed.
import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { assertNoProviderStrings, collectConsoleErrors, forEachViewport } from './_fixtures';
import { currentSessionId, openDecision } from './_session';

/** The chat body, opened if this width keeps it shut (below 1024 it is a bottom sheet;
 * at 1440 the column is open already). The header's own control is the one way in at
 * every width. */
async function openChat(page: import('@playwright/test').Page) {
  const body = page.locator('[data-chat-body]');
  if (!(await body.isVisible())) await page.getByRole('button', { name: 'Ask about this decision' }).click();
  await expect(body).toBeVisible();
  return body;
}

test.describe('Ask about this decision', () => {
  forEachViewport(() => {
    test('the nine chips, an answer with cites and actions, and nothing written', async ({ page, request }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-b');
      const sessionId = await currentSessionId(page);
      const before = (await (await request.get(`/api/session/${sessionId}/activity`)).json()).entries.length;
      const body = await openChat(page);
      expect(await body.locator('[data-chat-chip]').count()).toBe(9);
      await body.locator('[data-chat-chip]', { hasText: 'What is blocking this right now?' }).click();
      const answer = body.locator('[data-chat-message][data-who="docket"]').last();
      await expect(answer).toBeVisible({ timeout: 15_000 });
      expect(await answer.locator('[data-cite]').count()).toBeGreaterThan(0);
      await expect(answer.locator('[data-chat-action]').first()).toBeVisible();
      await answer.locator('[data-cite]').first().click();
      const raw = page.getByRole('dialog', { name: 'raw object' });
      await expect(raw).toBeVisible();
      // `RawObjectDrawer` closes on its own control, not on Escape (it is not a `Sheet`),
      // and it covers the chat column until it does.
      await raw.getByRole('button', { name: 'close' }).click();
      await expect(raw).toBeHidden();
      await answer.locator('[data-chat-action]').first().click();
      await expect(page).toHaveURL(/\/readiness/);
      const after = (await (await request.get(`/api/session/${sessionId}/activity`)).json()).entries.length;
      expect(after).toBe(before);
      await assertNoProviderStrings(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  test('a question no intent matches gets the fallback sentence and four chips, in recorded mode', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const body = await openChat(page);
    await body.getByRole('textbox', { name: 'Ask about this decision' }).fill('What is the weather on the range?');
    await body.getByRole('textbox', { name: 'Ask about this decision' }).press('Enter');
    const answer = body.locator('[data-chat-message][data-who="docket"]').last();
    await expect(answer).toContainText("I can only answer from this decision's record; try one of these.", { timeout: 15_000 });
    expect(await answer.locator('[data-chat-action]').count()).toBe(4);
    await answer.locator('[data-chat-action]').first().click();
    await expect(body.locator('[data-chat-message][data-who="you"]').last()).toContainText('What is blocking this right now?');
  });

  test('the thread belongs to the decision: switching decisions switches it', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    // The return trip adopts THIS session rather than opening a second copy of demo-a:
    // `openDecision` always selects `open:<source>`, which POSTs a new session, and a new
    // session is a new thread key by construction.
    const first = await currentSessionId(page);
    const body = await openChat(page);
    await body.locator('[data-chat-chip]', { hasText: 'When is this due?' }).click();
    await expect(body.locator('[data-chat-message]')).toHaveCount(2, { timeout: 15_000 });
    await openDecision(page, 'demo-b');
    await expect(body.locator('[data-chat-message]')).toHaveCount(0);
    await page.getByLabel('Which decision').selectOption(`session:${first}`);
    await expect(body.locator('[data-chat-message]')).toHaveCount(2);
  });

  test('after three exchanges the chips step aside, Suggestions brings them back, and Explain names the source', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const body = await openChat(page);
    const asked = ['When is this due?', 'Why is it late?', 'What changed since yesterday?', 'How long has this been sitting?'];
    for (const [i, q] of asked.entries()) {
      await body.locator('[data-chat-chip]', { hasText: q }).click();
      await expect(body.locator('[data-chat-message]')).toHaveCount(2 * (i + 1), { timeout: 15_000 });
    }
    await expect(body.locator('[data-chat-chip]')).toHaveCount(0);
    await body.getByRole('button', { name: 'Suggestions' }).click();
    await expect(body.locator('[data-chat-chip]')).toHaveCount(9);
    // Under Explain the answer says where it came from, and nothing more: the word is
    // `record`, `model` or `fallback` — never a provider or a model name.
    await expect(body.locator('[data-chat-message][data-who="docket"]').last()).not.toContainText('source:');
    await page.locator('header').getByRole('button', { name: 'Explain', exact: true }).click();
    await expect(body.locator('[data-chat-message][data-who="docket"]').last()).toContainText('source: record');
    await assertNoProviderStrings(page);
  });

  test('/ask?q= asks the question and lands on Needs', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.goto('/ask?q=How%20long%20has%20this%20been%20sitting%3F');
    await expect(page).toHaveURL(/\/$/);
    const body = page.locator('[data-chat-body]');
    await expect(body.locator('[data-chat-message][data-who="you"]').last()).toContainText('How long has this been sitting?');
    await expect(body.locator('[data-chat-message][data-who="docket"]').last()).toBeVisible({ timeout: 15_000 });
  });

  test('/ask with no question goes straight home rather than sitting on a blank view', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.goto('/ask');
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('heading', { name: 'What needs you', level: 1 })).toBeVisible();
    await expect(page.locator('[data-chat-body]').locator('[data-chat-message]')).toHaveCount(0);
  });

  test('one question at a time: the redirect owns the send and the composer waits for it', async ({ page }) => {
    // A local stub, not the network: the same route the app would have called, held open
    // long enough for the in-flight state to be observable. `busy` lives on the thread,
    // not on a hook instance, so the panel's composer knows about the redirect's send.
    let release = () => {};
    const held = new Promise<void>((resolve) => { release = resolve; });
    await page.route('**/api/session/*/episode/*/ask', async (route) => { await held; await route.continue(); });
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.goto('/ask?q=When%20is%20this%20due%3F');
    const body = page.locator('[data-chat-body]');
    await expect(body.getByText('reading the record…')).toBeVisible();
    await expect(body.getByRole('textbox', { name: 'Ask about this decision' })).toBeDisabled();
    await expect(body.getByRole('button', { name: 'Ask', exact: true })).toBeDisabled();
    release();
    await expect(body.locator('[data-chat-message][data-who="docket"]')).toHaveCount(1, { timeout: 15_000 });
    await expect(body.getByText('reading the record…')).toBeHidden();
    await expect(body.getByRole('textbox', { name: 'Ask about this decision' })).toBeEnabled();
  });

  test('a refused read is an answer too: the message is shown and the composer comes back', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const body = await openChat(page);
    const composer = body.getByRole('textbox', { name: 'Ask about this decision' });
    // A local stub of the one route the chat posts to, refusing as the API's own error
    // table would. Nothing here reaches the network.
    await page.route('**/api/session/*/episode/*/ask', (route) => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ error: 'internal', message: 'The record could not be read just now.' }),
    }));
    await composer.fill('When is this due?');
    await composer.press('Enter');
    const refused = body.locator('[data-chat-message][data-who="docket"][data-source="error"]');
    await expect(refused).toContainText('The record could not be read just now.', { timeout: 15_000 });
    await expect(composer).toBeEnabled();
    // The draft went with the question that was sent, and the next one can be typed.
    await expect(composer).toHaveValue('');
  });

  test('a half-typed question survives an answer arriving in the middle of it', async ({ page }) => {
    let release = () => {};
    const held = new Promise<void>((resolve) => { release = resolve; });
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const body = await openChat(page);
    const composer = body.getByRole('textbox', { name: 'Ask about this decision' });
    await composer.fill('Why is it late?');
    await page.route('**/api/session/*/episode/*/ask', async (route) => { await held; await route.continue(); });
    await body.locator('[data-chat-chip]', { hasText: 'When is this due?' }).click();
    // Shut while the record is being read, so a second question cannot be started on top
    // of the first — and the words already typed are still in the box, before and after.
    await expect(body.getByText('reading the record…')).toBeVisible();
    await expect(composer).toBeDisabled();
    await expect(composer).toHaveValue('Why is it late?');
    release();
    await expect(body.locator('[data-chat-message][data-who="docket"]')).toHaveCount(1, { timeout: 15_000 });
    await expect(composer).toBeEnabled();
    await expect(composer).toHaveValue('Why is it late?');
    await composer.press('Enter');
    await expect(body.locator('[data-chat-message][data-who="you"]').last()).toContainText('Why is it late?');
  });
});
