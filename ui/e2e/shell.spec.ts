// The application frame at every width (spec §4, Appendix B §2/§3).
import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { assertFooterSentences, assertNoUnbracketedNumerals, collectConsoleErrors } from './_fixtures';
import { currentSessionId, goTo, openDecision } from './_session';

const WIDTHS = [
  { width: 1440, height: 900 }, { width: 1024, height: 768 },
  { width: 768, height: 1024 }, { width: 360, height: 780 },
];

test.describe('frame', () => {
  for (const size of WIDTHS) {
    test(`at ${size.width}px the page never scrolls and the footer is in view`, async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.setViewportSize(size);
      await page.goto('/');
      await openDecision(page, 'demo-a');
      await expect(page.getByRole('button', { name: /needs you/ })).toBeVisible();
      const scroll = await page.evaluate(() => ({
        doc: document.documentElement.scrollHeight, inner: window.innerHeight,
        wide: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      }));
      expect(scroll.doc, 'the document itself must not scroll').toBe(scroll.inner);
      expect(scroll.wide).toBeLessThanOrEqual(0);
      await expect(page.locator('footer')).toBeInViewport();
      await assertFooterSentences(page);
      const header = await page.locator('header').boundingBox();
      expect(header!.height).toBeLessThanOrEqual(120);
      const settings = await page.getByRole('button', { name: 'open settings' }).boundingBox();
      expect(settings!.width).toBeGreaterThanOrEqual(44);
      expect(settings!.height).toBeGreaterThanOrEqual(44);
      await assertNoUnbracketedNumerals(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  }

  test('the map is a side column at 1440 and a strip at 360, with the same rows', async ({ page, request }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const map = page.getByRole('navigation', { name: 'Where this decision stands' });
    await expect(map).toBeVisible();
    expect(await map.getByRole('link').count()).toBe(10);
    expect(await map.evaluate((el) => getComputedStyle(el).flexDirection)).not.toBe('row');
    await expect(map.locator('[data-colour-key]')).toBeVisible();
    // The number on a row is the server's (`needs.byRoute`, kernel/queue.py), never a
    // filter this browser ran over `items`: Demo A's one act is the signature, and the
    // Package row prints exactly what the route says sits there.
    const session = await currentSessionId(page);
    const queue = await (await request.get(`/api/session/${session}/episode/ep-cbo-2013/needs`)).json();
    expect(queue.byRoute['/package']).toBe(1);
    const printed = await map.locator('[data-map-row="package"] [data-num]').innerText();
    expect(printed.replace(/\D/g, '')).toBe(String(queue.byRoute['/package']));

    await page.setViewportSize({ width: 360, height: 780 });
    await expect(map).toBeVisible();
    expect(await map.getByRole('link').count()).toBe(10);
    expect(await map.evaluate((el) => el.scrollWidth > el.clientWidth), 'the strip scrolls sideways').toBe(true);
    await expect(map.locator('[data-colour-key]')).toBeHidden();
  });

  test('the chat is a column at 1440 and a sheet opened from the header below 1024', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const chat = page.getByRole('complementary', { name: 'Ask about this decision' });
    await expect(chat).toBeVisible();
    await expect(chat.getByText('Reads this decision. Never writes to it.')).toBeVisible();
    await chat.getByRole('button', { name: 'Collapse the chat' }).click();
    await expect(chat.getByText('Reads this decision. Never writes to it.')).toBeHidden();
    const box = await chat.boundingBox();
    expect(box!.width).toBeLessThanOrEqual(60);

    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(chat).toBeHidden();
    await page.getByRole('button', { name: 'Ask about this decision' }).click();
    await expect(chat).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollHeight === window.innerHeight)).toBe(true);
  });

  test('the header counters read the queue: Demo A needs one signature and nothing blocks it', async ({ page, request }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const needs = page.getByRole('button', { name: /needs you/ });
    await expect(needs).toContainText('1');
    await expect(needs.locator('[data-num]')).toHaveClass(/text-act-text/);
    // Scoped to the header (Task 19): the chat's suggested questions include "What is
    // blocking this right now?", so a page-wide /blocking/ matches two buttons.
    const blocking = page.locator('header').getByRole('button', { name: /blocking/ });
    // Zero, and the title of this test has said so all along. The SIGNED gate still wants
    // `commitment-present` and `commitment-package-hash`, and the one act that satisfies
    // both is the signature the queue is already asking for — an act is not its own
    // obstruction, so the counter does not hold it against itself.
    await expect(blocking).toContainText('0');
    await expect(blocking.locator('[data-num]')).not.toHaveClass(/text-stop/);
    await expect(page.locator('header').getByText('ep-cbo-2013')).toBeVisible();
    await expect(page.locator('header').getByText('pending signature')).toBeVisible();
    await blocking.click();
    const sheet = page.getByRole('dialog', { name: 'What is blocking this decision' });
    await expect(sheet).toBeVisible();
    await expect(sheet).toContainText('Nothing is blocking this decision right now.');
    await expect(sheet).not.toContainText('commitment-present');
    // `aria-modal` is a promise about the keyboard, so it is tested as one: focus moves
    // into the panel on open and comes back to the control that opened it on close.
    expect(await sheet.evaluate((el) => el.contains(document.activeElement))).toBe(true);
    await page.keyboard.press('Escape');
    await expect(sheet).toHaveCount(0);
    await expect(blocking).toBeFocused();
  });

  test('the time chip carries the clock tone and opens the clock', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await openDecision(page, 'demo-a');
    const chip = page.getByRole('button', { name: 'When it is due and who it waits on' });
    await expect(chip).toContainText('no deadline');
    await expect(chip).toContainText('waiting on');
    await expect(chip).toHaveAttribute('data-tone', 'stop');
  });

  test('branding assets are served for browser, PWA and social', async ({ page }) => {
    for (const asset of [
      '/favicon.svg',
      '/favicon-16.png',
      '/favicon-32.png',
      '/apple-touch-icon.png',
      '/icon-192.png',
      '/icon-512.png',
      '/icon-1024.png',
      '/og-image.png',
      '/site.webmanifest',
    ]) {
      const response = await page.request.get(asset);
      expect(response.ok(), `${asset} should be served`).toBeTruthy();
    }

    const manifest = await (await page.request.get('/site.webmanifest')).json();
    expect(manifest.name).toBe('Docket');
    expect(manifest.theme_color).toBe('#1B1813');
    expect(manifest.icons.map((i: { sizes: string }) => i.sizes)).toContain('512x512');
  });

  test('Explain shows the record term beside the episode state and the colour key on the view', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await expect(page.locator('header').getByText('PENDING_SIGNATURE')).toBeHidden();
    await page.getByRole('button', { name: 'Explain', exact: true }).click();
    await expect(page.locator('header').getByText('PENDING_SIGNATURE')).toBeVisible();
    await expect(page.locator('#view [data-colour-key]')).toBeVisible();
    await expect(page.locator('#view')).toContainText('Expected time per stage is a policy setting, not a rule');
    // With Explain on, the map prints every view's record term beside its label —
    // "G1 · MODEL_APPROVED" — and the panel prints the view's own lines, which name gates
    // and clause numbers. All of those are names, so the numeral walk must still pass on
    // the frame; before Task 20 the bare `G1` tripped it on every view.
    await assertNoUnbracketedNumerals(page);
    await assertBrandConformance(page);
    // And on a view whose own Explain lines carry numerals of their own.
    await goTo(page, 'Readiness');
    await expect(page.locator('[data-explain-panel]')).toContainText('readiness-present');
    await assertNoUnbracketedNumerals(page);
  });

  // Ember, as the browser reports it (docs/decisions/2026-09-08-ember-is-ff6a00.md).
  const EMBER = 'rgb(255, 106, 0)';

  test('the view marks the one Ember act, and an open overlay takes it from the page', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await openDecision(page, 'demo-a');
    // Demo A sits at PENDING_SIGNATURE, ready, with a full package once it is rendered —
    // so the act the lifecycle is heading towards is the signature: the Package view's
    // `Sign`, the one element on that view carrying `data-ember`.
    await page.goto('/package');
    await page.getByRole('button', { name: 'Render the package' }).click();
    const ember = page.locator('[data-ember]');
    await expect(ember).toBeVisible({ timeout: 15_000 });
    const fill = () => ember.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(await fill(), 'the frame paints the view\'s primary act Ember').toBe(EMBER);

    // …and takes it back while a sheet is open: the act behind an overlay is not the act
    // in front of one.
    await page.getByRole('button', { name: 'open settings' }).click();
    expect(await fill(), 'an open overlay unpaints the Ember').not.toBe(EMBER);
    await page.getByRole('button', { name: 'close settings' }).click();
    await expect(ember).toBeVisible();
    expect(await fill(), 'closing the overlay gives it back').toBe(EMBER);
  });

  test('Browse the record is a flat list of every view', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await page.getByRole('button', { name: 'Browse the record' }).click();
    const menu = page.getByRole('menu', { name: 'Every view of the record' });
    const items = menu.getByRole('menuitem');
    expect(await items.count()).toBe(12);   // eleven views + the Explain toggle
    // `role="menu"` is a keyboard contract: the first item takes focus, the arrows walk
    // the list, and Escape hands focus back to the trigger.
    await expect(items.first()).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await expect(items.nth(1)).toBeFocused();
    await page.keyboard.press('End');
    await expect(items.last()).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(menu).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Browse the record' })).toBeFocused();

    await page.getByRole('button', { name: 'Browse the record' }).click();
    await menu.getByRole('menuitem', { name: 'Activity' }).click();
    await expect(page).toHaveURL(/\/activity$/);
  });
});
