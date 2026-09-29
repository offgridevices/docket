// The token layer itself, asserted directly rather than through a screen. If this file
// fails, every other visual test in the suite is failing for the same reason and fixing
// them one by one is wasted work — start here.
//
// Brand v3.0, light only: docs/decisions/2026-09-08-demo-ui-rebuilt-on-brand-v3.md and
// docs/decisions/2026-09-08-demo-ui-is-light-only.md.

import { expect, test } from '@playwright/test';

test.describe('brand tokens', () => {
  test('the ground is warm paper, the accent is Ember, and no theme machinery survives', async ({
    page,
  }) => {
    await page.goto('/');

    // Light-only means there is nothing to switch: no attribute, no stored preference.
    await expect(page.locator('html')).not.toHaveAttribute('data-theme', /.*/);
    expect(await page.evaluate(() => window.localStorage.getItem('og-theme'))).toBeNull();

    const vars = await page.evaluate(() => {
      const s = getComputedStyle(document.documentElement);
      const v = (name: string) => s.getPropertyValue(name).trim();
      return {
        bg: v('--og-bg'),
        accent: v('--og-accent'),
        accentText: v('--og-accent-text'),
        radius: v('--og-radius'),
        bodyBackground: getComputedStyle(document.body).backgroundColor,
      };
    });

    // The ember ruling: docs/decisions/2026-09-08-ember-is-ff6a00.md. Asserted here
    // rather than trusted, because the handoff ships both values and a careless
    // re-copy of tokens.css would silently reintroduce #E8743C.
    expect(vars.accent.toUpperCase()).toBe('#FF6A00');
    expect(vars.accentText.toUpperCase()).toBe('#A84A00');

    // Warm paper, never #FFFFFF.
    expect(vars.bg.toUpperCase()).toBe('#F7F4EC');
    expect(vars.bodyBackground).toBe('rgb(247, 244, 236)');
    expect(vars.bodyBackground).not.toBe('rgb(255, 255, 255)');

    expect(vars.radius).toBe('0');
  });

  test('only the three v3.0 faces are loaded — no Archivo, no Inter Tight', async ({ page }) => {
    await page.goto('/');
    const families = await page.evaluate(() =>
      Array.from(document.fonts).map((f) => f.family.replace(/["']/g, '')),
    );
    const allowed = new Set(['Instrument Sans', 'Newsreader', 'JetBrains Mono']);

    expect(families.length, 'no faces loaded at all — is fonts.css imported?').toBeGreaterThan(0);
    for (const family of new Set(families)) {
      expect(allowed, `${family} is not one of the three v3.0 faces`).toContain(family);
    }
  });

  test('display type is sentence case at weight 400, and mono does not reshape what it is given', async ({
    page,
  }) => {
    await page.goto('/');
    const styles = await page.evaluate(() => {
      const probe = (cls: string) => {
        const el = document.createElement('span');
        el.className = cls;
        el.textContent = 'probe';
        document.body.appendChild(el);
        const s = getComputedStyle(el);
        const out = { transform: s.textTransform, weight: s.fontWeight, family: s.fontFamily };
        el.remove();
        return out;
      };
      return { display: probe('og-display'), mono: probe('og-mono'), label: probe('og-label') };
    });

    // v3.0: "authority comes from size, never from weight or caps".
    expect(styles.display.transform).toBe('none');
    expect(styles.display.weight).toBe('400');
    expect(styles.mono.transform).toBe('none');
    expect(styles.label.weight).toBe('500');
    expect(styles.display.family).toContain('Instrument Sans');
    expect(styles.label.family).toContain('Instrument Sans');
    expect(styles.mono.family).toContain('JetBrains Mono');
  });

  test('the five semantic tokens resolve on the root', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() => {
      const s = getComputedStyle(document.documentElement);
      const get = (n: string) => s.getPropertyValue(n).trim().toUpperCase();
      return {
        act: get('--c-act'), actText: get('--c-act-text'), stop: get('--c-stop'),
        wait: get('--c-wait'), done: get('--c-done'), ai: get('--c-ai'),
        stopTint: get('--c-stop-tint'),
      };
    });
    expect(v.act).toBe('#FF6A00');
    expect(v.actText).toBe('#A84A00');
    expect(v.stop).toBe('#B3261E');
    expect(v.wait).toBe('#8A5F00');
    expect(v.done).toBe('#2E6B3F');
    expect(v.ai).toBe('#2F5F8F');
    expect(v.stopTint).toBe('#F4DFDB');
  });
});
