// Compute (Task 13): the sealed runs, the ranking, what flips the decision, and the one
// act that hands the approved plan to the kernel.
//
// Four of the five tests are the four states the record can actually be in; the fifth is
// the Fields control, which only Demo A has anything to show for. Demo A is
// `PENDING_SIGNATURE` with sealed runs and a ranked `flip_summary`, so it proves the read
// side — including the one claim this view makes that nothing else can check for it: the
// flip rows appear in the server's own `flip_summary.ranked` order, cross-checked against
// `GET .../readiness` fetched directly, never recomputed here. Demo B's `ep-omfv-2020-02-r5`
// is `PLAN_APPROVED` with no runs, so it is the only committed fixture from which "Run the
// plan" is reachable — the second test asserts it carries the view's single Ember, and the
// third presses it and reads the kernel's answer (a refusal, on this fixture: see that
// test's own header). A fresh elicitation is DRAFT, which is the pre-gate sentence with no
// button at all.
//
// The old spec's "dispatch before the plan is approved renders the authority message" test
// is gone with the screen it was written against: it drove a mocked `runs: []` episode to
// make the old screen render its button before the gate, and this view only ever renders
// "Run the plan" at `PLAN_APPROVED`, so the state that test staged is no longer reachable
// from the interface at all.
import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { goTo, openDecision } from './_session';

interface ReadinessStub { flipSummary?: { run: string; ranked: string[] } }

test.describe('Compute', () => {
  forEachViewport(() => {
    test('Demo A: sealed runs, ranked results and the flip list in the server’s order', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-a');
      await goTo(page, 'Compute');
      await expect(page.getByRole('heading', { name: 'Compute' })).toBeVisible();
      await expect(page.locator('[data-sev="done"]').first()).toContainText('Every planned step has a sealed run.');
      const seals = page.locator('[data-testid="run-seal"]');
      await expect(seals.first()).toBeVisible({ timeout: 15_000 });
      await expect(seals.first().getByText(/^record [0-9a-f]{12}…$/)).toBeVisible();
      await expect(seals.first().getByText(/^inputs [0-9a-f]{12}…$/)).toBeVisible();
      await expect(page.locator('[data-testid="result-table"]').first()).toBeVisible();
      const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
      const readiness = (await (await page.request.get(`/api/session/${sessionId}/episode/ep-cbo-2013/readiness`)).json()) as ReadinessStub;
      const runSection = page.locator(`[data-testid="run-section"][data-run-id="${readiness.flipSummary!.run}"]`);
      expect(await runSection.locator('[data-testid="flip-row"]').evaluateAll((els) => els.map((el) => el.getAttribute('data-flip-id')))).toEqual(readiness.flipSummary!.ranked);
      await expect(page.getByRole('button', { name: 'Run the plan' })).toHaveCount(0);
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  test('Demo B r5: the plan is approved, nothing has run, and Run the plan is the one Ember', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Compute');
    await expect(page.locator('[data-sev="wait"]').first()).toContainText('The plan is approved and nothing has run.');
    const run = page.getByRole('button', { name: 'Run the plan' });
    await expect(run).toHaveAttribute('data-ember', '');
    expect(await page.locator('[data-ember]').count()).toBe(1);
    // Switching the decision in the header leaves nothing of the last one behind — the
    // first revision names no plan at all, so the act and the sentence that offered it
    // must both go. (No committed Demo B episode has runs, so this is as far as the
    // fixtures can prove the same point about the run sections themselves.) That episode
    // is SUPERSEDED, which is not a state gate 2 is still ahead of, so it gets the
    // no-plan sentence and never the pre-gate one.
    await page.locator('header').getByLabel('Episode').selectOption('ep-omfv-2020-02');
    await expect(page.getByRole('button', { name: 'Run the plan' })).toHaveCount(0);
    await expect(page.locator('[data-sev="wait"]')).toHaveCount(0);
    await expect(page.getByText('This episode has no plan to dispatch yet.')).toBeVisible();
    await expect(page.getByText(/Nothing is computed before the model is approved/)).toHaveCount(0);
  });

  // The four fields, exercised where they can be seen: Demo A is the only fixture with
  // sealed runs to hide the hashes of, parameter bindings to print and non-aggregate
  // results to list. The numeral walk runs again with the two off-by-default fields ON,
  // because those are numerals no other test ever puts on screen.
  test('the Fields control hides the hashes and the sweeps, and shows the bindings and every result', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Compute');
    await expect(page.locator('[data-testid="run-seal"]').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('[data-testid="every-result"]')).toHaveCount(0);
    await page.getByRole('button', { name: 'Fields' }).click();
    await page.getByRole('checkbox', { name: 'record and input hashes' }).uncheck();
    await page.getByRole('checkbox', { name: 'parameter bindings' }).check();
    await page.getByRole('checkbox', { name: 'every result, not only aggregates' }).check();
    await page.getByRole('checkbox', { name: 'sensitivity sweeps' }).uncheck();
    // The seal becomes one line naming the run, never nothing: a run that has been sealed
    // is still a fact when nobody is reading its hashes.
    await expect(page.locator('[data-testid="run-seal"]')).toHaveCount(0);
    await expect(page.getByText(/^sealed run · run-/).first()).toBeVisible();
    await expect(page.locator('[data-testid="every-result"]').first()).toBeVisible();
    await expect(page.locator('[data-testid="every-result"]').first().locator('[data-num]').first()).toBeVisible();
    await expect(page.getByText(/"weightSet"/).first()).toBeVisible();
    await expect(page.locator('[data-testid="flip-row"]')).toHaveCount(0);
    // The popover is closed before the brand walk simply to leave the view as a reader
    // would leave it; since Task 20 its choices are 44 px targets, so `coverage.spec.ts`
    // runs the walk with one standing open.
    await page.getByRole('button', { name: 'Fields' }).click();
    await assertNoUnbracketedNumerals(page);
    await assertBrandConformance(page);
  });

  // WHAT THIS TEST CANNOT DO, AND WHY. The brief's third test pressed Run the plan and
  // followed the decision to `EVALUATED`. No committed fixture can do that, and the wall is
  // not this view's: every approved Demo B plan compares `alt-omfv-concept`, and the record
  // holds no Observation for it on the one published measure — which is Demo B's whole
  // point (a concept with no public data), not a hole in the fixture. Checked against the
  // API directly, on a fresh session per plan, for all four approved plans (`pl-omfv-r5`
  // and `pl-omfv-r4-{ce,dc,fs}`): every one answers 422 "no Observation for alternative
  // alt-omfv-concept on measure m-weight-bridges". Demo A's only episode is already
  // `PENDING_SIGNATURE` with its runs sealed, and a freshly elicited episode cannot reach a
  // proposed plan at all (`_fixtures.ts`'s `openDemoASeeded`: no route lets a human name an
  // evaluator). So this test drives every part of the act that IS reachable — the button,
  // the POST, the stream it listens on, and the kernel's own answer — and asserts the
  // refusal is shown in the kernel's words and that the record did not move. The sealed-run
  // path is covered against Demo A's committed runs by the first test; a live dispatch is
  // owed to a fixture whose plan can actually be evaluated.
  test('Demo B r5: running the plan asks the kernel, and its refusal is shown in the kernel’s own words', async ({ page, request }) => {
    test.setTimeout(180_000);
    const errors = collectConsoleErrors(page);
    const refused = 'no Observation for alternative alt-omfv-concept on measure m-weight-bridges';
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Compute');
    // The POST is held for two seconds so the window in which a second press would be
    // possible is long enough to assert on: while the kernel is being asked, the act is
    // out of reach. (The other half of that rule — the button staying out of reach after a
    // SUCCESSFUL dispatch, until the header's episode has caught up with the runs it just
    // sealed — cannot be reached on any fixture; see this test's header.)
    await page.route('**/api/session/*/plan/*/dispatch', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 2_000));
      await route.continue();
    });
    const act = page.locator('button[data-ember]');
    await expect(act).toHaveText('Run the plan');
    const dispatched = page.waitForResponse((r) => /\/dispatch$/.test(r.url()));
    await act.click();
    await expect(act).toHaveText('computing…');
    await expect(act).toBeDisabled();
    expect((await dispatched).status()).toBe(422);
    await expect(page.locator('[data-toast="stop"]')).toContainText(refused);
    await expect(page.locator('[data-state="error"]')).toContainText(refused);
    await expect(page.locator('[data-testid="run-seal"]')).toHaveCount(0);
    // Nothing was written, so the act is offered again rather than held.
    await expect(act).toHaveText('Run the plan');
    await expect(act).toBeEnabled();
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const ep = await (await request.get(`/api/session/${sessionId}/episode/ep-omfv-2020-02-r5`)).json();
    expect(ep.lifecycleState).toBe('PLAN_APPROVED');
    expect(ep.runs.length).toBe(0);
    // The refusal IS this test, and the browser logs the refused POST as a console error
    // of its own. Its wording is Chromium's, not this app's, so it is COUNTED rather than
    // matched: exactly one error, no more, and no assertion that would drift the day the
    // browser rewords itself.
    expect(errors).toHaveLength(1);
  });

  // The brief's own regex for this sentence was `before anything can be computed`; the
  // sentence itself is the source of truth and it reads differently, so the sentence
  // stays as the screen this view replaces worded it and the regex follows it.
  test('a decision before gate 2 explains what must happen first, with no button', async ({ page }) => {
    const { elicitRecorded } = await import('./_elicit');
    await elicitRecorded(page);
    await goTo(page, 'Compute');
    await expect(page.getByText(/Nothing is computed before the model is approved/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Run the plan' })).toHaveCount(0);
  });
});
