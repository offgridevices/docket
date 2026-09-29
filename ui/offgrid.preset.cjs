/* Copied from the OffGrid brand handoff v3.0
   (offgridevices/offgrid-brand, handoffs/2026-09-08-brand-v3.0/handoff/tokens/
   tailwind.preset.js). Adoption: docs/decisions/2026-09-08-demo-ui-rebuilt-on-brand-v3.md.

   FOUR EDITS:

   1. `.cjs`, because this repo's ui/package.json is "type": "module" and Tailwind's
      config loader wants an explicit CommonJS file.

   2. ember '#FF6A00' and 'ember-deep' '#A84A00'. The handoff's own preset says
      '#E8743C'/'#B8531F' and disagrees with its tokens.css, its tokens.json `value`
      fields and its README table. Ruling: docs/decisions/2026-09-08-ember-is-ff6a00.md.

   3. `darkMode` is deleted. The UI ships light only, so a `dark:` variant would be a
      variant nothing can ever satisfy: docs/decisions/2026-09-08-demo-ui-is-light-only.md.

   4. The upstream file declares `surface` and `raised` TWICE in one object literal — once
      as raw tones ('#EFEAE0', '#FBF9F3') and again as semantic vars. In JavaScript the
      later key wins, so the raw pair is unreachable dead code that reads as if it were
      usable. The semantic pair is what components consume and is what survives here; the
      two dead raw keys are dropped rather than left to mislead. Reported upstream.
      The other raw v2.1 tones (ground, ink, ink-2, ink-3) do not collide and are kept.
*/

/** OffGrid · Tailwind preset · v3.0
 *  Two layers of colour are exposed:
 *
 *  1. RAW palette (bg-pitch, text-bone, bg-ember, …) — fixed hex. Use only when a
 *     SPECIFIC tone is required regardless of context. This app has no such case.
 *  2. SEMANTIC palette (bg-canvas, text-fg, border-hairline, …) — resolves to a CSS
 *     custom property defined in src/brand/tokens.css. Components use these.
 */
module.exports = {
  theme: {
    extend: {
      colors: {
        // ── RAW palette ────────────────────────────────────
        pitch:        '#1B1813',
        bark:         '#3A2E22',
        coal:         '#100D09',
        bone:         '#F1ECE0',
        sand:         '#D9C9A8',
        ember:        '#FF6A00',
        dim:          '#9A9082',
        linen:        '#E5DDC9',
        paper:        '#FAF7EF',
        'ember-deep': '#A84A00',
        ground:       '#F7F4EC',   // page
        ink:          '#1B1813',   // primary type
        'ink-2':      '#5C554A',
        'ink-3':      '#6B6456',

        // ── SEMANTIC palette (via CSS vars) ────────────────
        canvas:            'var(--og-bg)',
        surface:           'var(--og-bg-sunken)',
        raised:            'var(--og-bg-raised)',
        deepest:           'var(--og-bg-deepest)',
        fg:                'var(--og-fg)',
        'fg-secondary':    'var(--og-fg-secondary)',
        'fg-muted':        'var(--og-fg-muted)',
        accent:            'var(--og-accent)',
        'accent-text':     'var(--og-accent-text)',
        'on-accent':       'var(--og-on-accent)',
        hairline:          'var(--og-hairline-color)',
        'hairline-strong': 'var(--og-hairline-strong)',

        // ── SEMANTIC STATE (plan 2026-09-11; src/brand/semantic.css) ──
        act:          'var(--c-act)',
        'act-text':   'var(--c-act-text)',
        'act-tint':   'var(--c-act-tint)',
        'act-line':   'var(--c-act-line)',
        stop:         'var(--c-stop)',
        'stop-tint':  'var(--c-stop-tint)',
        'stop-line':  'var(--c-stop-line)',
        wait:         'var(--c-wait)',
        'wait-tint':  'var(--c-wait-tint)',
        'wait-line':  'var(--c-wait-line)',
        done:         'var(--c-done)',
        'done-tint':  'var(--c-done-tint)',
        'done-line':  'var(--c-done-line)',
        ai:           'var(--c-ai)',
        'ai-tint':    'var(--c-ai-tint)',
        'ai-line':    'var(--c-ai-line)',
      },
      fontFamily: {
        display:   ['"Instrument Sans"', 'system-ui', 'sans-serif'],
        body:      ['"Instrument Sans"', 'system-ui', 'sans-serif'],
        editorial: ['Newsreader', 'Georgia', 'serif'],
        mono:      ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        d1: ['118px', { lineHeight: '0.92', letterSpacing: '-0.045em' }],
        d2: ['76px',  { lineHeight: '0.96', letterSpacing: '-0.042em' }],
        d3: ['62px',  { lineHeight: '1.02', letterSpacing: '-0.038em' }],
        d4: ['42px',  { lineHeight: '1.10', letterSpacing: '-0.030em' }],
        b1: ['21px',  { lineHeight: '1.50' }],
        b2: ['16px',  { lineHeight: '1.62' }],
        b3: ['14px',  { lineHeight: '1.55' }],
        e1: ['44px',  { lineHeight: '1.18', letterSpacing: '-0.01em' }],
        e2: ['24px',  { lineHeight: '1.40', letterSpacing: '-0.01em' }],
        m1: ['13px',  { lineHeight: '1.40', letterSpacing: '0.06em' }],
        m2: ['11px',  { lineHeight: '1.40', letterSpacing: '0.06em' }],
      },
      borderRadius: { DEFAULT: '0', none: '0', sm: '0', md: '0', lg: '0' }, // right angles only
      maxWidth: { content: '1280px' },
      spacing: { gutter: '80px', section: '160px' },
    },
  },
};
