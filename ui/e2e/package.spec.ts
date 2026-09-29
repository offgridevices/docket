// The package (Task 15): read it in full, sign it, dissent, or send it back. Every spec
// walks the brand checks and the numeral walk at every viewport; the three acts are proved
// against the record through the API, never against the screen alone.
import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { goTo, openDecision } from './_session';

test.describe('The package', () => {
  forEachViewport(() => {
    test('Demo A: sixteen sections, a toggle that changes the hash, a verify result, and Sign as the one Ember', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-a');
      await goTo(page, 'Package');
      await expect(page.getByRole('heading', { name: 'The package' })).toBeVisible();
      await page.getByRole('button', { name: 'Render the package' }).click();
      const sections = page.getByTestId('package-section');
      await expect(sections.first()).toBeVisible({ timeout: 15_000 });
      expect(await sections.count()).toBe(16);
      const hashLine = page.locator('[data-package-hash]');
      const fullHash = await hashLine.innerText();
      await page.getByRole('button', { name: 'unclassified', exact: true }).click();
      await page.getByRole('button', { name: 'Render it again' }).click();
      await expect(hashLine).not.toHaveText(fullHash, { timeout: 15_000 });
      await page.getByRole('button', { name: 'full', exact: true }).click();
      // Not `toHaveText(fullHash)` after this render: the cover prints the render time, so
      // two full renders a second apart hash differently by design. Determinism is what
      // `Verify the bytes` proves — it re-renders at the stored package's own `renderedAt`.
      const again = page.waitForResponse((r) => /\/package\?rendering=full$/.test(r.url()));
      await page.getByRole('button', { name: 'Render it again' }).click();
      expect((await again).status()).toBe(200);
      await page.getByRole('button', { name: 'Verify the bytes' }).click();
      const result = page.getByTestId('verify-result');
      await expect(result).toBeVisible({ timeout: 10_000 });
      await expect(result).toContainText('identical bytes');
      await expect(result).toContainText('kernel rendering only; model outputs are not re-run');
      const sign = page.getByRole('button', { name: 'Sign', exact: true });
      await expect(sign).toHaveAttribute('data-ember', '');
      expect(await page.locator('[data-ember]').count()).toBe(1);
      await expect(page.getByRole('button', { name: 'Send back for rework' })).toBeVisible();
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  test('Demo A: signing writes the commitment and the decision reads SIGNED', async ({ page, request }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Package');
    await page.getByRole('button', { name: 'Render the package' }).click();
    await expect(page.getByTestId('package-section').first()).toBeVisible({ timeout: 15_000 });
    await page.getByRole('button', { name: 'Sign', exact: true }).click();
    const sheet = page.getByRole('dialog', { name: 'Sign this decision' });
    await expect(sheet).toContainText('What happens: a Commitment object is written in your name');
    await sheet.getByLabel('Your role').fill('Milestone Decision Authority');
    await sheet.getByLabel('Stop rules').fill('Stop if unit cost exceeds the ceiling.');
    await sheet.getByRole('button', { name: 'Add a dissent' }).click();
    await sheet.getByLabel('Who dissents').fill('CBO');
    await sheet.getByLabel('The dissent').fill('The cost estimate is optimistic.');
    const signed = page.waitForResponse((r) => /\/sign$/.test(r.url()));
    await sheet.getByRole('button', { name: 'Sign', exact: true }).click();
    expect((await signed).status()).toBe(200);
    await expect(page.locator('[data-commitment]')).toContainText('Signed. The signature binds to the package hash shown above.', { timeout: 15_000 });
    await expect(page.locator('[data-commitment]')).toContainText('CBO');
    // The episode chip's plain state — `getByText('signed')` alone also matches the time
    // chip, which says the same word once the decision is signed.
    await expect(page.locator('header')).toContainText('· signed');
    expect(await page.locator('[data-ember]').count()).toBe(0);
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const ep = await (await request.get(`/api/session/${sessionId}/episode/ep-cbo-2013`)).json();
    expect(ep.lifecycleState).toBe('SIGNED');
    expect(ep.commitment).toMatch(/^cm-ep-cbo-2013-/);
  });

  test('Demo A: sending it back files a signer-return trigger and returns to Needs', async ({ page, request }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Package');
    await page.getByRole('button', { name: 'Send back for rework' }).click();
    const sheet = page.getByRole('dialog', { name: 'Send this package back' });
    await sheet.getByRole('button', { name: 'Send it back' }).click();
    await expect(sheet.locator('[data-field-error]')).toContainText('needs a named reason');
    await sheet.getByLabel('Why it is going back').fill('The cost section cites a superseded estimate.');
    const sent = page.waitForResponse((r) => /\/send-back$/.test(r.url()));
    await sheet.getByRole('button', { name: 'Send it back' }).click();
    expect((await sent).status()).toBe(200);
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator('[data-queue-card][data-kind="sent-back"]')).toBeVisible({ timeout: 15_000 });
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const trig = await (await request.get(`/api/session/${sessionId}/object/rt-return-ep-cbo-2013-1`)).json();
    expect(trig.object.kind).toBe('signer-return');
    // Back on the package, the sent-back state is read from the queue: no Sign is offered,
    // and the reason is printed verbatim.
    await goTo(page, 'Package');
    const block = page.locator('[data-decision-block]');
    await expect(block).toContainText('Sent back for rework on', { timeout: 15_000 });
    await expect(block).toContainText('The cost section cites a superseded estimate.');
    await expect(page.getByRole('button', { name: 'Sign', exact: true })).toHaveCount(0);
    expect(await page.locator('[data-ember]').count()).toBe(0);
  });

  test('Demo B r5: no package can be signed yet, and the view says why', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Package');
    await expect(page.getByText('This decision is not yet awaiting a signature.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign', exact: true })).toHaveCount(0);
    expect(await page.locator('[data-ember]').count()).toBe(0);
  });
});
