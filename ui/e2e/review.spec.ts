// Read and agree (spec §11) — the review card in the two homes that are addresses: the
// reading queue at `/review`, and one object at `/review/:objectId`. The third home, the
// dialog the model's own cards open, is exercised by `model.spec.ts`; all three render
// the same `ReviewCard`, which is why the six regions are asserted in the same order
// here as they are there.
//
// `page.goto('/review')` rather than `goTo(page, 'Review')`: the progress map lists the
// home, the six stages and the three registers — the review card is reached from a card,
// a remedy or the Browse menu, and has no row of its own to click.
import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { elicitRecorded } from './_elicit';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { currentSessionId, goTo, openDecision } from './_session';

/** The spec's own names for the six regions, verbatim — `data-region` carries the design
 * document's ALL-CAPS field name as the stable hook, while the heading a human reads is
 * sentence case (see `ReviewCard.tsx`). Same list as `model.spec.ts` asserts against the
 * dialog: one component, one order, three homes. */
const REGIONS = ['WHAT', 'WHY THE MODEL PROPOSED IT', 'SOURCE', 'IF IT IS WRONG', 'WHAT YOU CAN DO', 'WHAT HAPPENS TO THE RECORD'];

test.describe('Read and agree', () => {
  forEachViewport(() => {
    test('the queue shows one card at a time with the six regions, and Next walks it', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await elicitRecorded(page);
      await page.goto('/review');
      await expect(page.getByRole('heading', { name: 'Read and agree' })).toBeVisible();
      const card = page.locator('[data-review-card]');
      await expect(card).toHaveCount(1);
      expect(await card.locator('[data-region]').evaluateAll((els) => els.map((e) => e.getAttribute('data-region')))).toEqual(REGIONS);
      // Where you are, without a numeral the browser counted: one mark per card, the one
      // you are on marked current.
      await expect(page.locator('[data-review-position] [data-mark][data-current="true"]')).toHaveCount(1);
      // The one Ember fill this view is allowed is the card's own primary act, and it is
      // on the card — never on a control the frame drew around it.
      await expect(page.locator('[data-ember]')).toHaveCount(1);
      await expect(card.locator('[data-ember]')).toHaveCount(1);
      const first = await card.getAttribute('data-object-id');
      await page.getByRole('button', { name: 'Next', exact: true }).click();
      await expect(card).not.toHaveAttribute('data-object-id', first!);
      await expect(page.locator('[data-review-position] [data-mark][data-current="true"]')).toHaveCount(1);
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  test('the queue starts with what needs you: an unread linchpin or an unconfirmed absence', async ({ page, request }) => {
    const body = await elicitRecorded(page);
    await page.goto('/review');
    await expect(page.locator('[data-review-card]')).toHaveCount(1);
    // The server's own queue, read independently of the browser's copy — the claim is
    // that the reading follows `needs.items`, so the list has to come from the route and
    // not from the page under test.
    const sessionId = await currentSessionId(page);
    const needs = await (await request.get(`/api/session/${sessionId}/episode/${body.episode.id}/needs`)).json();
    const firstActionable = needs.items.find((i: { kind: string }) => ['linchpin-unreviewed', 'gap-unconfirmed'].includes(i.kind));
    expect(firstActionable, 'the elicited episode needs a person for a linchpin or an absence').toBeTruthy();
    await expect(page.locator('[data-review-card]')).toHaveAttribute('data-object-id', firstActionable.objectId);
  });

  test('Previous, Next and Skip walk the reading without agreeing to anything', async ({ page }) => {
    await elicitRecorded(page);
    await page.goto('/review');
    const card = page.locator('[data-review-card]');
    await expect(card).toHaveCount(1);
    const first = await card.getAttribute('data-object-id');
    // Nothing is behind the first card.
    await expect(page.getByRole('button', { name: 'Previous' })).toBeDisabled();
    // Skip is Next without an act: the next card, and nothing written on the way.
    await page.getByRole('button', { name: 'Skip' }).click();
    await expect(card).not.toHaveAttribute('data-object-id', first!);
    await expect(card.locator('[data-state="recorded"]')).toHaveCount(0);
    await page.getByRole('button', { name: 'Previous' }).click();
    await expect(card).toHaveAttribute('data-object-id', first!);
  });

  test('switching decisions in the header takes the reading with it', async ({ page, request }) => {
    // A session holding a freshly drafted episode AND the committed trade study's own,
    // so switching crosses two sheets that share no object.
    const body = await elicitRecorded(page, 'demo-a');
    const episode = page.locator('header').getByLabel('Episode');
    await expect(episode).toHaveValue(body.episode.id);
    const others = (await episode.locator('option').evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value)))
      .filter((v) => v && v !== body.episode.id);
    expect(others.length, 'the session holds an episode other than the one just drafted').toBeGreaterThan(0);

    // Start the reading on one of the committed episodes, and let it actually SETTLE —
    // the reading is taken once the record has answered, and switching before it has
    // would test nothing.
    await episode.selectOption(others[0]);
    await page.goto('/review');
    await expect(page.getByRole('heading', { name: 'Read and agree' })).toBeVisible();
    await expect(page.getByText('Everything drafted has been read. Return to the model checklist.')).toBeVisible({ timeout: 15_000 });
    const sessionId = await currentSessionId(page);
    const left = await (await request.get(`/api/session/${sessionId}/episode/${others[0]}/g1`)).json();
    const leftIds: string[] = [...left.objects.map((o: { id: string }) => o.id), ...left.gaps.map((g: { id: string }) => g.id)];

    // …then switch the header to the drafted one. The reading is the new decision's, not
    // a list frozen off the sheet the reviewer just left.
    await episode.selectOption(body.episode.id);
    const card = page.locator('[data-review-card]');
    await expect(card).toHaveCount(1);
    const draftedIds = new Set(body.objects.map((o) => o.id));
    expect(draftedIds.has((await card.getAttribute('data-object-id'))!)).toBe(true);
    // Nothing from the sheet we left is anywhere on the page — not a card, not a mark.
    for (const gone of leftIds) await expect(page.locator(`[data-object-id="${gone}"]`)).toHaveCount(0);
    await expect(page.locator('[data-review-position] [data-mark][data-current="true"]')).toHaveCount(1);
  });

  test('a card opened by its own address offers the way back and the next unread', async ({ page }) => {
    await elicitRecorded(page);
    await goTo(page, 'Model');
    await expect(page.locator('[data-gate="G1"]')).toBeVisible({ timeout: 15_000 });
    const id = await page.locator('[data-object-type="Assumption"]').first().getAttribute('data-object-id');
    await page.goto(`/review/${id}`);
    const card = page.locator('[data-review-card]');
    await expect(card).toHaveAttribute('data-object-id', id!);
    await page.getByRole('button', { name: 'Next unread' }).click();
    await expect(page).toHaveURL(/\/review\/.+$/);
    await expect(card).not.toHaveAttribute('data-object-id', id!);
  });

  test('/review/:id opens that object, and accepting writes a human revision', async ({ page, request }) => {
    await elicitRecorded(page);
    await goTo(page, 'Model');
    await expect(page.locator('[data-gate="G1"]')).toBeVisible({ timeout: 15_000 });
    const id = await page.locator('[data-object-type="Objective"]').first().getAttribute('data-object-id');
    await page.goto(`/review/${id}`);
    const card = page.locator('[data-review-card]');
    await expect(card).toHaveAttribute('data-object-id', id!);
    await card.getByRole('button', { name: 'Accept', exact: true }).click();
    await expect(card.locator('[data-state="recorded"]')).toContainText('createdBy.actorType: human', { timeout: 15_000 });
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const view = await (await request.get(`/api/session/${sessionId}/object/${id}`)).json();
    expect(view.object.createdBy.actorType).toBe('human');
    await page.getByRole('button', { name: 'Back to the model' }).click();
    await expect(page).toHaveURL(/\/model$/);
  });

  test('changing the wording produces a revision with your text', async ({ page, request }) => {
    await elicitRecorded(page);
    await goTo(page, 'Model');
    await expect(page.locator('[data-gate="G1"]')).toBeVisible({ timeout: 15_000 });
    const id = await page.locator('[data-object-type="Assumption"]').first().getAttribute('data-object-id');
    await page.goto(`/review/${id}`);
    const card = page.locator('[data-review-card]');
    await card.locator('[data-editable-field] textarea').fill('The nine-vehicle squad stays as written unless the Army revises the ORD.');
    // The button says which act it is about to do: accepting a draft as it stands and
    // rewording it are not the same thing, and the card renames itself when the text
    // differs from the draft's own.
    await card.getByRole('button', { name: 'Change the wording' }).click();
    await expect(card.locator('[data-state="recorded"]')).toBeVisible({ timeout: 15_000 });
    const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
    const view = await (await request.get(`/api/session/${sessionId}/object/${id}`)).json();
    expect(view.object.statement).toContain('nine-vehicle squad');
    expect(view.rev).toBeGreaterThan(1);
  });

  test('answering the reading from the queue drains it, and Finish reading ends it', async ({ page }) => {
    await elicitRecorded(page);
    await page.goto('/review');
    const card = page.locator('[data-review-card]');
    await expect(card).toHaveCount(1);
    const marks = page.locator('[data-review-position] [data-mark]');
    const cards = await marks.count();
    expect(cards, 'the elicited episode drafted something to read').toBeGreaterThan(1);
    const finish = page.getByRole('button', { name: 'Finish reading' });

    const next = page.getByRole('button', { name: 'Next', exact: true });

    /** Answer the card in hand, if it is still waiting on a person. False when it is not:
     * either it has been answered already in this reading, or an earlier act answered it
     * (confirming one recorded absence confirms every absence the episode reaches, and the
     * mark for each of them turns grey at once). The view's own mark is what says so. */
    const answer = async (): Promise<boolean> => {
      if ((await card.locator('[data-state="recorded"]').count()) > 0) return false;
      if ((await page.locator('[data-review-position] [data-mark][data-current="true"][data-answered="true"]').count()) > 0) return false;
      // A recorded absence is CONFIRMED, not accepted: accepting agrees with the words the
      // AI chose for the absence, and only confirming is the act the gate is waiting for.
      const confirm = card.getByRole('button', { name: 'Confirm gap', exact: true });
      const act = (await confirm.count()) > 0 ? confirm : card.getByRole('button', { name: 'Accept', exact: true });
      if ((await act.count()) === 0) return false;
      // A field the source never states is filled here rather than left: completing the
      // model at the gate is what accepting is for.
      const boxes = card.locator('textarea');
      for (let b = 0; b < (await boxes.count()); b++) {
        if ((await boxes.nth(b).inputValue()) === '') await boxes.nth(b).fill('The reviewer states this while reading; the source does not.');
      }
      await act.first().click();
      await expect(card.locator('[data-state="recorded"]')).toBeVisible({ timeout: 15_000 });
      return true;
    };

    // The first card, in full: the act is recorded, a toast says so, the mark for it turns
    // grey once the record has been re-read — and the card does NOT go with it. The echo
    // is the only place the reviewer learns what was written.
    const first = await card.getAttribute('data-object-id');
    expect(await answer(), 'the first card of the reading asks for something').toBe(true);
    await expect(page.locator('[data-toast="done"]').last()).toBeVisible();
    await expect(page.locator('[data-review-position] [data-mark][data-answered="true"]').first()).toBeVisible({ timeout: 15_000 });
    await expect(card).toHaveAttribute('data-object-id', first!);
    await expect(card.locator('[data-state="recorded"]')).toBeVisible();

    // …then work through the rest. `Next` is a real move: the card changes each time.
    for (let i = 0; i < cards * 2 + 4; i++) {
      if (await finish.isVisible()) break;
      if (await answer()) continue;
      if ((await next.count()) === 0 || (await next.isDisabled())) break;
      const at = await card.getAttribute('data-object-id');
      await next.click();
      await expect(card).not.toHaveAttribute('data-object-id', at!);
    }

    // Nothing is waiting any more, so the forward control is Finish reading — and the
    // answered card is still on screen with its echo until the reviewer takes it.
    await expect(finish).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('button', { name: 'Next', exact: true })).toHaveCount(0);
    await expect(card.locator('[data-state="recorded"]')).toBeVisible();
    await expect(page.getByText('Everything drafted has been read. Return to the model checklist.')).toHaveCount(0);

    await finish.click();
    await expect(card).toHaveCount(0);
    await expect(page.getByText('Everything drafted has been read. Return to the model checklist.')).toBeVisible();
    await expect(page.locator('[data-review-position]')).toHaveCount(0);
    await page.getByRole('button', { name: 'Open the model' }).click();
    await expect(page).toHaveURL(/\/model$/);
  });

  test('a decision with nothing left to read says so', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await page.goto('/review');
    await expect(page.getByText('Everything drafted has been read. Return to the model checklist.')).toBeVisible();
    await expect(page.locator('[data-review-card]')).toHaveCount(0);
    await page.getByRole('button', { name: 'Open the model' }).click();
    await expect(page).toHaveURL(/\/model$/);
  });
});
