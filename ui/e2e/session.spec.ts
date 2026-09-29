// How a decision gets opened, and what the app says when it cannot be.
//
// These four behaviours were written for the Home screen (`home.spec.ts`, deleted when
// the application frame replaced the old shell) and are re-homed here rather than left
// for the task that rewrites Home: none of them is about Home's layout, all of them are
// about honesty at the moment a session is created — a deep link that must not linger in
// the address bar, a refused model configuration that must not leak the server's message
// or the model id it names, an unbuilt demo store, and a 409 printed as the server wrote
// it. They read the frame's own surfaces where the old spec read the old shell's.
//
// The three cards themselves are now the Needs view's own start cards (Task 8, which
// replaced Home): the selectors below moved from `[data-card=...]` to `[data-start=...]`
// with every assertion unchanged.

import { expect, test } from '@playwright/test';
import {
  assertNoProviderStrings,
  assertNoUnbracketedNumerals,
  collectConsoleErrors,
} from './_fixtures';

const DEMO_A_NOT_BUILT =
  "Demo A's store has not been built. Run `uv run python -m demos.a_cbo_gcv_2013.run`.";

test.describe('opening a decision', () => {
  test('a session id on the URL is adopted and then removed from the address bar', async ({
    page,
    request,
  }) => {
    // `docket ui --demo a` creates the session server-side and opens the browser on
    // `/?session=<id>` (`cli._open_browser_when_healthy`). Same call, same URL.
    const created = await request.post('/api/session', { data: { source: 'demo-a' } });
    expect(created.status()).toBe(200);
    const { id } = await created.json();

    await page.goto(`/?session=${id}`);
    // The frame's own episode chip, which is the surface the old header's episode line
    // became.
    await expect(page.locator('header').getByText('ep-cbo-2013')).toBeVisible({ timeout: 15_000 });
    // One-time hand-off, not a permanent override: a reload must not keep re-adopting it.
    expect(new URL(page.url()).search).toBe('');
  });

  test('a refused config prints the fixed sentence, never the message or the model id', async ({
    page,
  }) => {
    // [ruling C1] Built at runtime, not written as a contiguous literal in this file —
    // the same convention `tests/api/test_agent_routes.py` uses for a denylisted-looking
    // id (`DENYLIST_FAMILIES[0]`-derived), here reproduced without a source-code import
    // by assembling the characters instead. The point of this test is that the app must
    // print NEITHER the server's message NOR the model id it names, whatever they are —
    // so the exact family does not matter, only that the shape is realistic.
    const family = ['q', 'w', 'e', 'n'].join('');
    const modelId = `${family}3.8:27b-mlx`;
    const message =
      `model '${modelId}' matches the PRC-origin denylist family '${family}' ` +
      'and is excluded by policy (design P8).';

    await page.route('**/api/health', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.configRefused = true;
      body.configRefusedMessage = message;
      await route.fulfill({ response, json: body });
    });

    const consoleErrors = collectConsoleErrors(page);
    await page.goto('/');

    await expect(
      page.getByText('The configured model was refused by policy. Open Settings for the reason.'),
    ).toBeVisible();
    // The server's own message, and the model id it names, are absent verbatim —
    // `configRefusedMessage` is confined to the Settings slide-over. Asserted against the
    // whole page, frame included, not just the view column.
    await expect(page.getByText(message, { exact: false })).toHaveCount(0);
    await expect(page.getByText(modelId, { exact: false })).toHaveCount(0);

    await assertNoUnbracketedNumerals(page);
    await assertNoProviderStrings(page);
    expect(consoleErrors).toEqual([]);
  });

  test('an unbuilt store shows the plan sentence and a Build now action', async ({ page }) => {
    await page.route('**/api/health', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.demoStores = { ...body.demoStores, 'demo-a': false };
      await route.fulfill({ response, json: body });
    });

    await page.goto('/');
    await expect(page.locator('[data-start="demo-a"]')).toContainText(DEMO_A_NOT_BUILT);
    await expect(
      page.locator('[data-start="demo-a"]').getByRole('button', { name: 'Build now' }),
    ).toBeVisible();

    // The frame's own decision switcher says the same thing rather than silently
    // offering a store that is not there.
    await expect(page.getByLabel('Which decision').locator('option', { hasText: 'not built' })).toHaveCount(1);
  });

  test('Build now surfaces the 409 verbatim', async ({ page }) => {
    const message = 'demo store not built: /repo/demos/a_cbo_gcv_2013/out/graph';
    await page.route('**/api/health', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.demoStores = { ...body.demoStores, 'demo-a': false };
      await route.fulfill({ response, json: body });
    });
    await page.route('**/api/session', async (route) => {
      if (route.request().method() !== 'POST') return route.fallback();
      await route.fulfill({ status: 409, json: { error: 'demo-store-missing', message } });
    });

    await page.goto('/');
    await page.locator('[data-start="demo-a"]').getByRole('button', { name: 'Build now' }).click();

    // Verbatim: the same bytes the body carried, not a rewritten apology.
    await expect(page.locator('[data-start="demo-a"]').getByText(message, { exact: true })).toBeVisible();
  });
});
