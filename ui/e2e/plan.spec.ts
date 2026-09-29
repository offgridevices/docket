// The plan view (Task 12): every step cites its paragraph, the proposal names who
// approved it, and gate 2 is the same checklist gate 1 is.
//
// WHAT THE THIRD TEST CANNOT DO, AND WHY. The task brief asked for a live walk that
// proposes a plan, approves it and passes gate 2 in the browser. That walk is not
// reachable with the committed fixtures, and the wall is not this view's: a freshly
// elicited episode carries no `Model` object (elicitation writes none, and no route
// anywhere in `src/docket/api/` authors one), so `agent.plan._select_evaluator` refuses
// with 422 — "A human must name the evaluator; the agent will not pick between models."
// Confirmed live against a throwaway server before this file was written, and it is the
// same wall `choreography.spec.ts`'s own third test already asserts on
// (`stoppedAt: 'plan-propose'`, `stopReason` containing "evaluator") and that
// `_fixtures.ts`'s `openDemoASeeded` header documents at length.
//
// So the third test drives every act that IS reachable through this view — a person
// setting the weights, the AI asked for a proposal, the gate pressed — and asserts the
// refusals are shown in the server's own words rather than swallowed. The "Approve the
// plan" Ember and the gate Ember are covered against Demo A/Demo B's committed, already
// approved plans instead. Closing that gap needs a route that lets a human name an
// evaluator; it is not this view's to invent.
import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { elicitRecorded } from './_elicit';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { goTo, openDecision } from './_session';

/** The third test's refusals ARE the test, and the browser logs every non-2xx response
 * as a console error of its own — the same carve-out `choreography.spec.ts` takes for
 * its own deliberate 409. Three codes, all expected: 404 is `WeightsPanel` reading back
 * a weight set that does not exist yet (its own header calls that the first-visit
 * state, not an error), 422 is the AI refusing to pick an evaluator, 409 is the gate
 * refusing.
 *
 * Counted, not merely tolerated. The console message carries no URL
 * (`collectConsoleErrors` keeps `msg.text()`, and Chromium puts the path in
 * `msg.location()`), so a bare pattern filter would also swallow a SECOND, unrelated 404
 * somewhere else in the walk. Each of the three is asserted to appear exactly once. */
const EXPECTED_REFUSALS = /status of (404|409|422)/;

test.describe('The plan', () => {
  forEachViewport(() => {
    test('Demo A: every step cites its paragraph; the gate is read-only past PLAN_APPROVED', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-a');
      await goTo(page, 'Plan');
      await expect(page.getByRole('heading', { name: 'The plan' })).toBeVisible();
      const steps = page.locator('[data-plan-step]');
      await expect(steps.first()).toBeVisible({ timeout: 15_000 });
      expect(await steps.count()).toBeGreaterThan(0);
      for (const step of await steps.all()) await expect(step.locator('[data-authority]')).toContainText(/paragraph/);
      await expect(page.locator('[data-gate="G2"]')).toContainText('This decision is already past this gate, so the checklist is read-only.');
      expect(await page.locator('[data-gate="G2"] [data-check][data-satisfied="true"]').count()).toBe(4);
      // The gate's own sentence for each check, served verbatim from the predicate's
      // docstring — the same text the Needs queue prints for the same check.
      await expect(page.locator('[data-gate="G2"] [data-check="plan-steps-have-authority"]')).toContainText('Every step cites the doctrine paragraph that requires it');
      await expect(page.locator('[data-panel="proposal"]')).toContainText('Approved by');
      // Past the gate there is nothing to recommend: no Ember at all on this view.
      await expect(page.locator('[data-ember]')).toHaveCount(0);
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  test('Demo B r5: approved plan, nothing run — the view points at Compute', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Plan');
    await expect(page.locator('[data-gate="G2"] [data-check="plan-approved-by-human"]')).toHaveAttribute('data-satisfied', 'true');
    await expect(page.getByText('Every step is planned; none has run. The next act is on the Compute view.')).toBeVisible();
    await expect(page.locator('[data-panel="proposal"]')).toContainText('pl-omfv-r5');
  });

  // Demo B's session holds eight episodes and only some of them name a plan — the one
  // fixture in the repo that can prove this view never leaves one episode's steps under
  // another episode's heading. `ep-omfv-2020-02` (the first revision) names no plan at
  // all, so switching to it must empty the panel, not keep the last one that loaded.
  test('Demo B: switching the episode in the header never leaves the last plan on screen', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-b');
    await goTo(page, 'Plan');
    await expect(page.locator('[data-plan-step]').first()).toBeVisible({ timeout: 15_000 });
    await page.locator('header').getByLabel('Episode').selectOption('ep-omfv-2020-02');
    await expect(page.locator('[data-panel="proposal"]')).toContainText('No plan yet');
    await expect(page.locator('[data-plan-step]')).toHaveCount(0);
    await expect(page.locator('[data-panel="proposal"]')).not.toContainText('pl-omfv-r5');
    // …and back again: the panel refills from the episode in hand, not from a cache.
    await page.locator('header').getByLabel('Episode').selectOption('ep-omfv-2020-02-r3');
    await expect(page.locator('[data-panel="proposal"]')).toContainText('pl-omfv-r3', { timeout: 15_000 });
  });

  test('a fresh elicitation: weights through the panel, then the refusals the record keeps', async ({ page, request }) => {
    test.setTimeout(240_000);
    const errors = collectConsoleErrors(page);
    const body = await elicitRecorded(page);
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const ep = body.episode.id;
    // reach MODEL_APPROVED through the API, as the demo script does after minute four
    const g1 = await (await request.get(`/api/session/${sessionId}/episode/${ep}/g1`)).json();
    await request.post(`/api/session/${sessionId}/episode/${ep}/confirm-gaps`, { data: {} });
    for (const o of g1.objects.filter((o: { actions: string[] }) => o.actions.includes('accept'))) await request.post(`/api/session/${sessionId}/object/${o.id}/accept`, { data: {} });
    const charter = g1.objects.find((o: { type: string }) => o.type === 'Charter');
    await request.post(`/api/session/${sessionId}/object/${charter.id}/accept`, { data: { edits: { consequencesOfErroneousOutput: 'Industry designs to the wrong characteristics.' } } });
    expect((await request.post(`/api/session/${sessionId}/episode/${ep}/transition`, { data: { to: 'MODEL_APPROVED' } })).status()).toBe(200);
    await page.reload();
    await goTo(page, 'Plan');

    // Act one: a person sets the weights. Equal share per objective with the remainder
    // folded into the first, exactly as `_fixtures.ts`'s `equalWeights` does at the API
    // level — the fixture's own arithmetic, typed into the form the way a human would
    // type numbers that happen to be equal. The panel itself computes nothing.
    const weights = page.locator('[data-panel="weights"]');
    await expect(weights).toBeVisible();
    const inputs = await weights.locator('input[type="number"]').all();
    expect(inputs.length).toBeGreaterThan(0);
    const share = Number((1 / inputs.length).toFixed(6));
    for (let i = 0; i < inputs.length; i++) {
      await inputs[i].fill(String(i === 0 ? Number((1 - share * (inputs.length - 1)).toFixed(6)) : share));
    }
    await weights.getByTestId('weight-name').fill('Equal weight on every objective');
    await weights.getByRole('button', { name: 'Save weights' }).click();
    // The panel reads the written set back — its button becomes "Revise weights" only
    // once the server has answered with a stored `WeightSet`.
    await expect(weights.getByRole('button', { name: 'Revise weights' })).toBeVisible({ timeout: 15_000 });

    // Act two: the AI is asked for a plan, and refuses in its own words. A live episode
    // names no Model, so the agent will not pick an evaluator — see this file's header.
    await page.locator('#propose').getByRole('button', { name: 'Ask the AI to propose a plan' }).click();
    await expect(page.locator('[data-toast="stop"]')).toContainText('A human must name the evaluator', { timeout: 30_000 });
    await expect(page.locator('[data-plan-step]')).toHaveCount(0);

    // Act three: the gate, pressed while it cannot pass. The checklist says so before
    // the press, in the gate's own words, and the refusal is in the record after it.
    const gate = page.locator('[data-gate="G2"]');
    await expect(gate.locator('[data-check="plan-present"]')).toHaveAttribute('data-satisfied', 'false');
    await expect(gate.locator('[data-check="plan-present"]')).toContainText('The episode names a plan, and the store holds it.');
    await expect(page.locator('[data-ember]')).toHaveCount(0);
    await gate.getByRole('button', { name: /^Pass gate 2/ }).click();
    await expect(gate.locator('[data-refusal]')).toContainText('plan-present', { timeout: 15_000 });
    const after = await (await request.get(`/api/session/${sessionId}/episode/${ep}`)).json();
    expect(after.lifecycleState).toBe('MODEL_APPROVED');
    expect(after.transitions.filter((t: { refused: boolean; to: string }) => t.refused && t.to === 'PLAN_APPROVED').length).toBe(1);

    await assertNoUnbracketedNumerals(page);
    await assertNoProviderStrings(page);
    await assertBrandConformance(page);
    for (const code of [404, 409, 422]) {
      expect(errors.filter((e) => e.includes(`status of ${code}`)),
        `exactly one ${code} in this walk`).toHaveLength(1);
    }
    expect(errors.filter((e) => !EXPECTED_REFUSALS.test(e))).toEqual([]);
  });
});
