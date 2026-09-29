// Plan 07 Task 8, Step 6: "the key input is `type=password`; no element matches
// `/allow.?denylist/i`; a denylisted model id is disabled and names its reason."
// Written against `ui/src/components/SettingsPanel.tsx`; not run here — see
// evidence.spec.ts's header note.
//
// `GET /api/settings/models` drops denylisted ids entirely by default
// (`agent.backend.list_models`'s own `include_denylisted` gate — see that function's
// docstring: "a model picker that never shows a PRC-origin id is the point of the
// policy"). A denylisted entry only ever appears when `DOCKET_LLM_ALLOW_DENYLISTED=1`
// is set in the *server's* environment, which Task 9's shared `webServer` config does
// not set for the whole suite. This spec intercepts the route instead of depending on
// that server-side environment variable, so "a denylisted model renders disabled and
// named" is exercised deterministically regardless of how the server was started.

import { expect, test } from '@playwright/test';
import {
  assertFooterSentences,
  assertNoOverrideControl,
  assertNoUnbracketedNumerals,
  collectConsoleErrors,
  forEachViewport,
} from './_fixtures';

test.describe('Settings', () => {
  test('the key field is a password input, never pre-filled', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'open settings' }).click();
    const keyInput = page.locator('input[name="docket-api-key"]');
    await expect(keyInput).toHaveAttribute('type', 'password');
    await expect(keyInput).toHaveAttribute('autocomplete', 'off');
    // Never populated from a GET — there is nothing to populate it with.
    await expect(keyInput).toHaveValue('');
  });

  // `GET /api/settings/models` calls `agent.backend.list_models` unconditionally,
  // regardless of provider (`routes/settings.py::get_models`) — with nothing
  // configured (this run's own throwaway `DOCKET_LLM_CONFIG`, empty, and no
  // `DOCKET_LLM_PROVIDER`/`DOCKET_LLM_BASE_URL` in `playwright.config.ts`'s
  // `webServer.env`), `settings.baseUrl` resolves empty, and `httpx.get("/models", ...)`
  // (no scheme, no host) fails immediately — `get_models` turns that into a 502, on
  // purpose (`tests/api/test_settings.py::test_models_list_unreachable_is_502_not_500`
  // establishes this is the intended contract, not a bug: confirmed by trying the
  // opposite fix here first — short-circuiting before the call when `baseUrl` is
  // empty — and watching that exact test, and its malformed-entry sibling, both fail).
  // Chromium logs the resulting failed fetch to the console regardless of how
  // gracefully `SettingsPanel.tsx` handles the response — the same "deliberately
  // provoked, not a defect" noise `model.spec.ts`'s own `REFUSAL_NETWORK_NOISE`
  // exempts for a 409.
  const MODELS_502_NOISE = /status of 502/;

  // [plan 07 Task 9 Part B, Step 4] Settings is the one screen `assertNoProviderStrings`
  // is never run against — picking a provider/model is the whole point of this panel
  // (`_fixtures.ts`'s own comment on that helper) — so this runs the other five: key
  // selectors, console errors, the numeral walk, the footer, and no denylist-override
  // control, in both themes.
  forEachViewport(() => {
    test('the settings panel itself meets the honesty checks', async ({ page }) => {
      const consoleErrors = collectConsoleErrors(page);
      await page.goto('/');
      await page.getByRole('button', { name: 'open settings' }).click();
      const panel = page.getByRole('dialog', { name: 'settings' });
      await expect(panel).toBeVisible();
      await expect(panel.getByText('Status')).toBeVisible();

      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoOverrideControl(page);
      expect(
        consoleErrors.filter((e) => !MODELS_502_NOISE.test(e)),
        `console errors: ${consoleErrors.join('; ')}`,
      ).toEqual([]);
    });
  });

  test('no control anywhere in the settings panel offers the denylist override', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'open settings' }).click();
    const panel = page.getByRole('dialog', { name: 'settings' });
    await expect(panel).toBeVisible();

    const suspects = panel.locator('button, input, select, a, [role="button"], [role="switch"], [role="checkbox"]');
    const count = await suspects.count();
    for (let i = 0; i < count; i++) {
      const el = suspects.nth(i);
      const name = ((await el.getAttribute('name')) ?? '') + ((await el.getAttribute('aria-label')) ?? '');
      expect(/allow.?denylist/i.test(name)).toBe(false);
    }
    // The one sentence this rule is allowed to show instead of a control.
    await expect(panel.getByText('The override is an environment variable, deliberately not offered here.')).toBeVisible();
  });

  test('a denylisted model id renders disabled and names itself as denylisted, with a reason', async ({ page }) => {
    await page.route('**/api/settings/models', (route) =>
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          models: [
            { id: 'llama3.1:8b', denylisted: false },
            // A placeholder id and a placeholder reason, deliberately not a real model
            // family name (CLAUDE.md: "avoid PRC-origin models regardless — reviewer
            // risk with no offsetting benefit"). The UI only ever reads the
            // `denylisted`/`reason` fields the (mocked) route sends; it does not need a
            // real denylisted id or the server's real reason text to prove the
            // disabled + reason rendering works (T8 fix round, ruling M1).
            {
              id: 'example-denylisted-model:7b',
              denylisted: true,
              reason: "model id matches denylisted family 'example' (policy P8)",
            },
          ],
        }),
      }),
    );

    await page.goto('/');
    await page.getByRole('button', { name: 'open settings' }).click();

    const denylistedOption = page.locator('option', { hasText: 'example-denylisted-model:7b' });
    // [T8 spec run-in] Not `toBeDisabled()`: Playwright's actionability-based disabled
    // check is unreliable for an `<option>` inside a native, currently-closed
    // `<select>` — confirmed live (Playwright 1.63/Chromium headless) that it reports
    // "enabled" for this exact element even though `el.disabled`, the `disabled`
    // attribute, and `el.matches(':disabled')` all agree it is disabled. Asserting the
    // JS property directly is the same check, without that actionability gate.
    await expect(denylistedOption).toHaveJSProperty('disabled', true);
    await expect(denylistedOption).toContainText('denylisted');
    // The reason string the (mocked) route sent — not just the bare boolean — must
    // reach the option text a reader actually sees.
    await expect(denylistedOption).toContainText("matches denylisted family 'example'");
    // Never the override hint: an API/UI surface must not advertise the env override.
    await expect(denylistedOption).not.toContainText('DOCKET_LLM_ALLOW_DENYLISTED');
  });
});
