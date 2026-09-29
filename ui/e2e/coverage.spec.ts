// Task 20: nothing that existed before this rebuild is unreachable, and nothing this
// task adds breaks the brand walk.
//
// Three questions, one spec: does the coverage sheet name every control the old nine
// screens had, and does every home it names resolve to a real address; does Browse list
// every view and does Explain say something on each of them; and are the six exports
// real links to a route that actually answers.
//
// It also carries the two conformance sweeps this task owns: the Fields popover is a
// stack of 44 px targets rather than 13 px checkboxes (so a brand walk no longer has to
// close it first), and the record terms Explain prints on the map are labels, not
// measurements, so the numeral walk still passes with Explain on.
import { expect, test } from '@playwright/test';
import { COVERAGE, VIEW_PATHS } from '../src/frame/coverage';
import { ALL_SCREENS, assertBrandConformance } from './_brand';
import { assertNoUnbracketedNumerals } from './_fixtures';
import { browseTo, goTo, openDecision } from './_session';

test.describe('Coverage, Browse, Explain, exports', () => {
  test('the coverage sheet lists every inventory item with a home that resolves', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.getByRole('button', { name: 'Coverage' }).click();
    const sheet = page.getByRole('dialog', { name: 'Where everything lives' });
    await expect(sheet).toBeVisible();
    const total = COVERAGE.reduce((n, g) => n + g.items.length, 0);
    expect(total).toBeGreaterThanOrEqual(90);
    expect(await sheet.locator('[data-coverage-item]').count()).toBe(total);
    for (const g of COVERAGE) {
      for (const it of g.items) {
        if (!it.route) {
          expect(it.overlay, `${it.item} has no route, so it must name an overlay`).toBeTruthy();
          continue;
        }
        expect(
          VIEW_PATHS.some((p) => it.route === p || it.route!.startsWith(`${p}?`) || it.route!.startsWith(`${p}#`) || (p !== '/' && it.route!.startsWith(`${p}/`))),
          `${it.item} → ${it.route}`,
        ).toBe(true);
      }
    }
    // The sheet is a screen like any other: it is read at 1440 with a hundred rows on it,
    // and again on a phone, where a two-column row of long sentences is the thing most
    // likely to push the page sideways.
    await assertNoUnbracketedNumerals(page);
    await assertBrandConformance(page);
    await page.setViewportSize({ width: 360, height: 780 });
    await expect(sheet).toBeVisible();
    await assertBrandConformance(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await sheet.locator('[data-coverage-item]', { hasText: 'the six exports' }).getByRole('button').click();
    await expect(page).toHaveURL(/\/package/);
  });

  test('Browse lists every view and Explain toggles the record names everywhere', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.getByRole('button', { name: 'Browse the record' }).click();
    const menu = page.getByRole('menu', { name: 'Every view of the record' });
    expect(await menu.getByRole('menuitem').count()).toBe(ALL_SCREENS.length + 1);
    await menu.getByRole('menuitem', { name: 'Readiness' }).click();
    await expect(page).toHaveURL(/\/readiness/);
    await page.getByRole('button', { name: 'Explain', exact: true }).click();
    await expect(page.locator('[data-explain-panel]')).toBeVisible();
    await expect(page.locator('[data-explain-panel]')).toContainText('readiness-present');
    // Walking every view does two jobs: Explain says something on each of them, and the
    // address each menu item actually reaches is collected as we go. `VIEW_PATHS` is
    // plain data nothing links to `routes.tsx` at compile time, so comparing the set of
    // addresses the menu really navigates to — not a count, and not an `href` the menu
    // does not have (its items are buttons that navigate) — is what keeps the two lists
    // honest with each other.
    const reached = new Set<string>();
    for (const label of ALL_SCREENS) {
      await browseTo(page, label);
      await expect(page.locator('[data-explain-panel]'), label).not.toBeEmpty();
      reached.add(new URL(page.url()).pathname);
    }
    expect([...reached].sort()).toEqual([...VIEW_PATHS].sort());
  });

  test('a Go with an anchor lands on the block it names, and one with a step changes the step', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Model');
    const view = page.locator('#view');
    await expect(page.locator('#charter')).toBeVisible({ timeout: 15_000 });
    // Read the board to the bottom first, so bringing the charter back is a real move and
    // not the position the view happened to be in already.
    await view.evaluate((el) => el.scrollTo({ top: el.scrollHeight }));
    await expect(page.locator('#charter')).not.toBeInViewport();
    await page.getByRole('button', { name: 'Coverage' }).click();
    const sheet = page.getByRole('dialog', { name: 'Where everything lives' });
    await sheet.locator('[data-coverage-item]', { hasText: 'Charter with its three fields' }).getByRole('button').click();
    await expect(page).toHaveURL(/\/model#charter$/);
    await expect(page.locator('#charter')).toBeInViewport();

    // And a `?step=` Go, followed while the Request view is already on screen at step one.
    await goTo(page, 'Request');
    await expect(page.locator('textarea[name="request-text"]')).toBeVisible();
    await page.getByRole('button', { name: 'Coverage' }).click();
    await sheet.locator('[data-coverage-item]', { hasText: 'policy id' }).getByRole('button').click();
    await expect(page).toHaveURL(/\/request\?step=2$/);
    await expect(page.locator('input[name="policy-id"]')).toBeVisible();
  });

  test('the six exports are links on the package view and each downloads', async ({ page, request }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Package');
    const links = page.locator('[data-export]');
    // `toHaveCount`, not a bare `count()`: the view prints "choose a decision first"
    // until the session's episode has arrived, and the exports are addressed to it.
    await expect(links).toHaveCount(6, { timeout: 15_000 });
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    // Named per episode, format and rendering, so six exports are six distinct files.
    await expect(links.first()).toHaveAttribute('download', 'docket-ep-cbo-2013-prov-full');
    await expect(links.first()).toHaveAttribute('href', `/api/session/${sessionId}/episode/ep-cbo-2013/export?format=prov&rendering=full`);
    for (const f of ['prov', 'gsn', 'dmn', 'milstd3022', 'madr', 'rtvm']) {
      const r = await request.get(`/api/session/${sessionId}/episode/ep-cbo-2013/export?format=${f}&rendering=full`);
      expect(r.status(), f).toBe(200);
    }
  });

  test('the Fields popover is conformant with the popover standing open', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Model');
    await page.getByRole('button', { name: 'Fields' }).click();
    // Every choice in the popover is a checkbox to a screen reader and a 44 px target to
    // a thumb — so the brand walk runs with it open, which no spec could do before. The
    // five are `MODEL_FIELDS`, named rather than counted: a popover that rendered nothing
    // would also pass a walk, and a `toBeGreaterThan(0)` would not notice.
    await expect(page.getByRole('checkbox')).toHaveText([
      'source page', 'object id', 'how sure the draft was', 'who agreed', 'revision',
    ]);
    await assertBrandConformance(page);
    await assertNoUnbracketedNumerals(page);
  });
});
