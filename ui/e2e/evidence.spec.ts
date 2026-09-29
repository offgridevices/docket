import { expect, test } from '@playwright/test';
import { assertBrandConformance } from './_brand';
import { assertFooterSentences, assertNoOverrideControl, assertNoProviderStrings, assertNoUnbracketedNumerals, collectConsoleErrors, forEachViewport } from './_fixtures';
import { goTo, openDecision } from './_session';

interface Item { id: string; object: unknown | null; slots?: Record<string, { kind: string }> }

async function markerCount(page: import('@playwright/test').Page, episodeId: string): Promise<number> {
  const sessionId = await page.evaluate(() => sessionStorage.getItem('docket-session-id'));
  const body = (await (await page.request.get(`/api/session/${sessionId}/episode/${episodeId}/evidence`)).json()) as { items: Item[] };
  return body.items.reduce((n, it) => n + Object.values(it.slots ?? {}).filter((s) => s.kind !== 'content').length, 0);
}

test.describe('Evidence', () => {
  forEachViewport(() => {
    test('Demo A: every register slot renders content, a gap card or an exclusion card — never blank', async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto('/');
      await openDecision(page, 'demo-a');
      await goTo(page, 'Evidence');
      await expect(page.getByRole('heading', { name: 'Evidence' })).toBeVisible();
      const rows = page.locator('[data-mark]');
      await expect(rows.first()).toBeVisible({ timeout: 15_000 });
      for (const cell of await page.locator('[data-evidence-row] dd').all()) expect((await cell.innerText()).trim().length).toBeGreaterThan(0);
      for (const gap of await page.locator('[data-slot="gap"]').all()) { await expect(gap).toContainText('sought'); await expect(gap).toContainText('why not'); }
      for (const ex of await page.locator('[data-slot="exclusion"]').all()) { await expect(ex).toContainText('reason type'); await expect(ex).toContainText('authority'); }
      await assertFooterSentences(page);
      await assertNoUnbracketedNumerals(page);
      await assertNoProviderStrings(page);
      await assertNoOverrideControl(page);
      await assertBrandConformance(page);
      expect(errors).toEqual([]);
    });
  });

  for (const [source, episodeId] of [['demo-a', 'ep-cbo-2013'], ['demo-b', 'ep-omfv-2020-02-r5']] as const) {
    test(`every server-reported marker becomes a gap or exclusion card — ${source}`, async ({ page }) => {
      await page.goto('/');
      await openDecision(page, source);
      await goTo(page, 'Evidence');
      await expect(page.locator('[data-mark]').first()).toBeVisible({ timeout: 15_000 });
      const expected = await markerCount(page, episodeId);
      expect(await page.locator('[data-slot="gap"], [data-slot="exclusion"]').count()).toBe(expected);
    });
  }

  // Demo B's default (highest-sequence) episode is `ep-omfv-2020-02-r5`, whose
  // committed fixture carries zero `claims` — `kernel.scope.check_scope`'s findings
  // are all derived from a claim's `supportedBy[]` or from a model's own accreditation
  // record, so an episode with no claims and no accreditation issue produces no scope
  // finding at all, on any item, regardless of what this view renders (verified
  // directly against `GET .../ep-omfv-2020-02-r5/evidence`: `findings: []` and every
  // item's `scopeFindings: []`). Demo A's `ep-cbo-2013` is used here instead — its
  // register carries three `reuse-justified` (info) findings and every item states a
  // `U` classification — so this assertion exercises real content rather than an
  // episode this task's own fixture cannot satisfy.
  test('scope findings print with their severity glyph, and Fields can hide the classification chip', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Evidence');
    await expect(page.locator('[data-mark]').first()).toBeVisible({ timeout: 15_000 });
    expect(await page.locator('[data-scope-finding] [data-sev]').count()).toBeGreaterThan(0);
    await expect(page.locator('[data-classification]').first()).toBeVisible();

    // The server-marker-count invariant every rendering of this register must hold,
    // whatever Fields shows or hides: `ep-cbo-2013` carries one `reliabilitySteps`
    // marker among its seven (verified against the API directly), so hiding that
    // field's own pair must relocate its card, never drop it. [review fix round 1,
    // Important 1 / Minor 7]
    const expectedMarkers = await markerCount(page, 'ep-cbo-2013');
    expect(await page.locator('[data-slot="gap"], [data-slot="exclusion"]').count()).toBe(expectedMarkers);

    await page.getByRole('button', { name: 'Fields' }).click();
    await page.getByRole('checkbox', { name: 'classification' }).uncheck();
    await expect(page.locator('[data-classification]')).toHaveCount(0);

    await page.getByRole('checkbox', { name: 'reliability steps' }).uncheck();
    expect(await page.locator('[data-slot="gap"], [data-slot="exclusion"]').count()).toBe(expectedMarkers);

    await page.getByRole('checkbox', { name: 'reliability steps' }).check();
    expect(await page.locator('[data-slot="gap"], [data-slot="exclusion"]').count()).toBe(expectedMarkers);
  });

  // [review fix round 1, Important 2] Every evidence object in both committed demo
  // stores states `classification.metadataLevel: "U"` (verified directly against the
  // fixture JSON under `demos/*/out/graph/objects`) — `_withhold_evidence_fields`
  // only substitutes a `[withheld: <level>]` marker once `metadataLevel` is above
  // `U`, so neither store's `unclassified` rendering actually withholds anything
  // today. This intercepts the view's own `?rendering=unclassified` request and
  // raises one item's reported field to the shape that route produces once a store
  // does carry a classified item — proving the half of the contract this view owns:
  // the toggle asks the server for that rendering, and a withheld field it returns
  // renders its marker.
  test('choosing unclassified rendering asks the server for it, and a withheld field shows its marker', async ({ page }) => {
    await page.goto('/');
    await openDecision(page, 'demo-a');
    await goTo(page, 'Evidence');
    await expect(page.locator('[data-mark]').first()).toBeVisible({ timeout: 15_000 });

    await page.route('**/api/session/*/episode/*/evidence?rendering=unclassified', async (route) => {
      const response = await route.fetch();
      const body = (await response.json()) as { items: { object: Record<string, unknown> | null }[] };
      const item = body.items.find((it) => it.object);
      if (!item?.object) throw new Error('fixture carries no resolvable item to withhold');
      item.object.pointer = '[withheld: S]';
      item.object.classification = { ...(item.object.classification as Record<string, unknown>), metadataLevel: 'S' };
      await route.fulfill({ response, json: body });
    });

    await page.getByRole('button', { name: 'unclassified' }).click();
    await expect(page.getByText('[withheld: S]').first()).toBeVisible({ timeout: 15_000 });
  });
});
