import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { elicitRecorded } from './_elicit';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { goTo, openDecision } from './_session';

const NOISE = /status of 409/;
const REGIONS = ['WHAT', 'WHY THE MODEL PROPOSED IT', 'SOURCE', 'IF IT IS WRONG', 'WHAT YOU CAN DO', 'WHAT HAPPENS TO THE RECORD'];

test.describe('Every object in the model', () => {
  forEachViewport(() => {
    test('every object the review sheet lists is a card; the checklist names what is missing', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await elicitRecorded(page);
      const g1 = page.waitForResponse((r) => /\/episode\/[^/]+\/g1$/.test(r.url()));
      await goTo(page, 'Model');
      const review = await (await g1).json();
      await expect(page.getByRole('heading', { name: 'Every object in the model' })).toBeVisible();
      const rendered = new Set(await page.locator('[data-object-id]').evaluateAll((els) => els.map((e) => e.getAttribute('data-object-id') ?? '')));
      for (const o of review.objects as { id: string }[]) expect(rendered.has(o.id), o.id).toBe(true);
      for (const g of review.gaps as { id: string }[]) expect(rendered.has(g.id), g.id).toBe(true);
      const list = page.locator('[data-gate="G1"]');
      await expect(list.locator('[data-check][data-satisfied="false"]').first()).toBeVisible();
      await expect(list.locator('[data-check="gaps-confirmed"]')).toContainText('every recorded absence has been confirmed by a person');
      await expect(list.locator('[data-check="gaps-confirmed"]')).toContainText('What would satisfy it');
      await expect(list.locator('[data-remedy]')).toHaveCount(1);
      const approve = list.getByRole('button', { name: /^Approve the model/ });
      await expect(approve).not.toHaveAttribute('data-ember', '');
      await expect(list).toContainText('If you press the button now it will refuse');
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  test('Explain shows the record check name beside the plain sentence', async ({ page }) => {
    await elicitRecorded(page);
    await goTo(page, 'Model');
    await expect(page.locator('[data-check="gaps-confirmed"] .og-mono')).toBeHidden();
    await page.getByRole('button', { name: 'Explain', exact: true }).click();
    await expect(page.locator('[data-check="gaps-confirmed"]').getByText('gaps-confirmed')).toBeVisible();
  });

  test('the empty charter field is typed inline and accepting it satisfies charter-three-fields', async ({ page, request }) => {
    await elicitRecorded(page);
    await goTo(page, 'Model');
    const field = page.locator('[data-charter-field="consequencesOfErroneousOutput"]');
    await expect(field.locator('textarea')).toHaveValue('');
    await expect(field.locator('textarea')).toHaveAttribute('placeholder', 'the record does not say — type it here');
    await field.locator('textarea').fill('Industry designs to characteristics the Army does not actually need.');
    const accepted = page.waitForResponse((r) => /\/accept$/.test(r.url()));
    await page.getByRole('button', { name: 'Save the charter' }).click();
    const body = await (await accepted).json();
    expect(body.object.consequencesOfErroneousOutput).toContain('Industry designs');
    await expect(page.locator('[data-check="charter-three-fields"]')).toHaveAttribute('data-satisfied', 'true', { timeout: 15_000 });
    await expect(page.locator('[data-check="charter-human-accepted"]')).toHaveAttribute('data-satisfied', 'true');
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const stored = await (await request.get(`/api/session/${sessionId}/object/${body.id}`)).json();
    expect(stored.object.createdBy.actorType).toBe('human');
  });

  test('a card opens the review dialog with its six regions in order', async ({ page }) => {
    await elicitRecorded(page);
    await goTo(page, 'Model');
    // The gate exists on no other view: waiting for it is what says the request view's
    // own chips (same `data-object-type`, different order) are off the page.
    await expect(page.locator('[data-gate="G1"]')).toBeVisible({ timeout: 15_000 });
    await page.locator('[data-object-type="Assumption"]').first().getByRole('button', { name: /Read it|Open it/ }).click();
    const dialog = page.locator('[data-review-dialog]');
    await expect(dialog).toBeVisible();
    expect(await dialog.locator('[data-region]').evaluateAll((els) => els.map((e) => e.getAttribute('data-region')))).toEqual(REGIONS);
    await dialog.getByRole('button', { name: 'Accept', exact: true }).click();
    await expect(dialog.locator('[data-state="recorded"]')).toContainText('createdBy.actorType: human', { timeout: 15_000 });
    await page.keyboard.press('Escape');
    // `.last()`: the elicitation's own toast ("the AI drafted the model") is still on
    // screen this soon after, and both are `done`.
    await expect(page.locator('[data-toast="done"]').last()).toBeVisible();
  });

  test('pressing the gate too early refuses in red and keeps the button beneath; fixing the checks lights it', async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await elicitRecorded(page);
    await goTo(page, 'Model');
    const list = page.locator('[data-gate="G1"]');
    const refused = page.waitForResponse((r) => /\/transition$/.test(r.url()));
    await list.getByRole('button', { name: /^Approve the model/ }).click();
    expect((await refused).status()).toBe(409);
    const card = list.locator('[data-refusal]');
    await expect(card).toBeVisible();
    await expect(card).toContainText('gaps-confirmed');
    await expect(card).toContainText('The gate refused and the refusal is now part of the record.');
    await expect(list.getByRole('button', { name: /^Approve the model/ })).toBeVisible();
    // the first remedy: confirm the absences. Since Task 11 the remedy is an address —
    // `/review/<gap>`, the Review view — not an overlay over this board.
    await list.locator('[data-remedy]').getByRole('button').click();
    await expect(page).toHaveURL(/\/review\//);
    await expect(page.locator('[data-review-card]')).toBeVisible();
    // The way back is a way back, so the same remedy works twice.
    await page.getByRole('button', { name: 'Back to the model' }).click();
    await expect(page).toHaveURL(/\/model$/);
    await list.locator('[data-remedy]').getByRole('button').click();
    await expect(page.locator('[data-review-card]')).toBeVisible();
    await page.getByRole('button', { name: 'Back to the model' }).click();
    // …and the refusal is still on screen after all that: it is the record's, not this
    // page's, so leaving the view and coming back does not erase it.
    await expect(page.locator('[data-refusal]')).toContainText('gaps-confirmed');
    expect(errors.filter((e) => !NOISE.test(e))).toEqual([]);
  });

  test('rejecting an objective writes an Exclusion, and the recorded echo stays until you close it', async ({ page, request }) => {
    await elicitRecorded(page);
    await goTo(page, 'Model');
    await expect(page.locator('[data-gate="G1"]')).toBeVisible({ timeout: 15_000 });
    const objective = page.locator('[data-object-type="Objective"]').first();
    await expect(objective).toBeVisible({ timeout: 15_000 });
    const objectiveId = await objective.getAttribute('data-object-id');
    await objective.getByRole('button', { name: /Agree or change it|Open it/ }).click();

    const dialog = page.locator('[data-review-dialog]');
    await expect(dialog).toBeVisible();
    // Region 6 states the consequence BEFORE the click, and the confirm step carries the
    // same sentence — a reviewer must not be told one thing before the click and shown
    // another at the point of no return.
    const rejectDd = dialog.locator('dt', { hasText: 'Reject' }).locator('xpath=./following-sibling::dd[1]');
    const effect = (await rejectDd.innerText()).trim();
    expect(effect.length).toBeGreaterThan(0);
    await dialog.getByRole('button', { name: 'Reject', exact: true }).click();
    const confirming = dialog.locator('[data-state="confirm"]');
    await expect(confirming).toContainText(effect);

    const rejected = page.waitForResponse((r) => /\/object\/[^/]+\/reject$/.test(r.url()) && r.request().method() === 'POST');
    await confirming.getByRole('button', { name: 'Confirm Reject', exact: true }).click();
    const exclusionId = (await (await rejected).json()).id as string;
    // The object is gone from the sheet the moment the record is re-read, and the dialog
    // must NOT go with it: the echo is the only place the reviewer learns what was written.
    const recorded = dialog.locator('[data-state="recorded"]');
    await expect(recorded).toContainText(`Exclusion written: ${exclusionId}`, { timeout: 15_000 });
    await expect(recorded).toBeVisible();

    await page.locator('[data-review-dialog] button[aria-label="close review"]').click();
    await expect(page.locator(`[data-object-id="${objectiveId}"]`)).toHaveCount(0);
    await expect(page.locator(`[data-object-id="${exclusionId}"]`)).toBeVisible({ timeout: 15_000 });

    // Read the record back through the API, not the DOM: the Exclusion's authority is the
    // server's own actor, never anything the client could have named.
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const health = await (await request.get('/api/health')).json();
    const stored = await (await request.get(`/api/session/${sessionId}/object/${exclusionId}`)).json();
    expect(stored.object.authority.who).toBe(health.actorId);
  });

  test('an id that is on no sheet this decision reaches says so, and offers the way back', async ({ page }) => {
    await elicitRecorded(page);
    // The Review view answers this address now, so the answer is a state of the page and
    // not a sheet over it — but it is still stated, never a blank screen.
    await page.goto('/review/obj-not-in-this-decision');
    const said = page.locator('[data-state="error"]');
    await expect(said).toBeVisible();
    await expect(said).toContainText('has no object obj-not-in-this-decision on its review sheet');
    await expect(page.locator('[data-review-card]')).toHaveCount(0);
    await page.getByRole('button', { name: 'Back to the model' }).click();
    await expect(page).toHaveURL(/\/model$/);
  });

  test('a charter the browser cannot read says so, offers a retry, and gives the ladder its remedy back', async ({ page }) => {
    await elicitRecorded(page);
    // The one read the inline charter block makes, refused. Interception only — nothing
    // here reaches the network.
    await page.route(/\/api\/session\/[^/]+\/object\/ch-[^/]+$/, (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'boom', message: 'the charter could not be read' }) }));
    await goTo(page, 'Model');
    const block = page.locator('[data-object-type="Charter"]');
    await expect(block).toContainText('the charter could not be read');
    await expect(block.getByRole('button', { name: 'retry' })).toBeVisible();
    // …and the checklist stops pretending the act is inline on a block nobody can see.
    await expect(page.locator('[data-gate="G1"] [data-remedy]')).toContainText('Write the missing charter field');
  });

  test('a decision already past the gate shows the checklist read-only', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.goto('/model');
    const list = page.locator('[data-gate="G1"]');
    await expect(list).toContainText('This decision is already past this gate, so the checklist is read-only.');
    await expect(list.getByRole('button', { name: /^Approve the model/ })).toBeDisabled();
    expect(await list.locator('[data-check][data-satisfied="true"]').count()).toBe(5);
    await expect(page.locator('[data-panel="scoring"]')).toBeVisible();
  });
});
