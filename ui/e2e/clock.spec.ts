// The clock card (spec §7): when is it due, where has the time gone, who has it been
// waiting on — every part of it a value `kernel.clock` computed and this card printed.
//
// Demo A's record is stamped 2013-04-30 throughout and its charter names no `neededBy`,
// so the honest answers are "no deadline set" and "thousands of days in pending
// signature". Both are asserted here rather than worked around: a card that quietly
// invented a deadline, or estimated the span it draws, would pass a friendlier test.
//
// One departure from the task brief's literal spec text: the stuck flag is asserted as
// "No one has acted for", which is `kernel.clock`'s own sentence for it. The card never
// rewrites a flag — it prints the text the server sent — so the assertion has to be the
// server's words.

import { expect, test } from '@playwright/test';
import { assertNoUnbracketedNumerals, forEachViewport } from './_fixtures';
import { openDecision } from './_session';

test.describe('the clock', () => {
  forEachViewport(() => {
    test('the card answers due, where the time went and who it waits on, from the record', async ({ page }) => {
      await page.goto('/');
      await openDecision(page, 'demo-a');
      const card = page.locator('#clock');
      await expect(card).toBeVisible();
      await expect(card.locator('[data-due]')).toContainText('No deadline set');
      await expect(card.getByRole('button', { name: 'Set one' })).toBeVisible();
      const segments = card.locator('[data-segment]');
      await expect(segments).toHaveCount(5);
      await expect(segments.last()).toHaveAttribute('data-running', 'true');
      await expect(segments.last()).toHaveAttribute('data-tone', 'stop');
      await expect(card.locator('[data-waiting]')).toContainText('Waiting on');
      await expect(card.locator('[data-waiting]')).toContainText('shreyash');
      const flags = card.locator('[data-flag]');
      await expect(flags).toHaveCount(2);
      await expect(card.locator('[data-flag="stuck"]')).toContainText('No one has acted for');
      await expect(card.locator('[data-flag="no-deadline"]').getByRole('button', { name: 'Go' })).toBeVisible();
      await expect(card).toContainText('Times come from the record’s own log. The deadline and the expected time per stage are policy fields.');
      await assertNoUnbracketedNumerals(page);
    });
  });

  test('Explain adds the policy-not-rule line inside the card, and a flag navigates', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.getByRole('button', { name: 'Explain', exact: true }).click();
    await expect(page.locator('#clock')).toContainText('never blocks anything');
    await page.locator('#clock [data-flag="no-deadline"]').getByRole('button', { name: 'Go' }).click();
    await expect(page).toHaveURL(/\/request$/);
  });

  test('the header time chip lands on the card', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/package');
    await openDecision(page, 'demo-a');
    await page.getByRole('button', { name: 'When it is due and who it waits on' }).click();
    await expect(page).toHaveURL(/\/#clock$/);
    await expect(page.locator('#clock')).toBeInViewport();
  });
});
