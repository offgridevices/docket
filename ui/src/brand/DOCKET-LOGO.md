# Docket logo system - Bracket mark

**Status:** adopted 2026-09-12  
**Parent brand:** OffGrid v3.0 (`tokens.css`, `logo/mark-ember.svg`)  
**Source:** `ui/scripts/gen-docket-logo.mjs` generates every file under `logo/docket/`  
**Regenerate:** `npm run gen:logo` from `ui/`

The Bracket mark is the Docket product identity: kernel survey brackets scaled to the
icon. Every computed value in the app lives inside brackets; the mark is that rule made
visible. The OffGrid beacon ring (`mark-ember.svg`) stays the parent-brand mark in the
footer; the header and favicon use Docket.

---

## 1. Geometry (200 x 200 artboard)

| Part | Size | Position |
|------|------|----------|
| Bracket arm (length) | 48 | along each outer edge |
| Bracket arm (thickness) | 16 | |
| Frame inset | 44 | from each edge |
| Center square | 48 x 48 | centered at (100, 100) |
| Clear space | 12 min | around the outer frame |

Safe zone for masked icons (iOS, Android adaptive): keep the full bracket frame inside the
center **80%** of any square crop.

Colors: `--og-ember` `#FF6A00` brackets, `--og-bone` `#F1ECE0` or `--og-ink` `#1B1813`
center depending on ground. See `gen-docket-logo.mjs` for the variant table.

---

## 2. Asset index

All files live in `ui/src/brand/logo/docket/`. Do not edit by hand.

### Mark only (transparent)

| File | Use |
|------|-----|
| `docket-mark-ember.svg` | Default. Header, dark surfaces |
| `docket-mark-ember-on-bone.svg` | Light / bone surfaces |
| `docket-mark-ink.svg` | Monochrome on white or bone |
| `docket-mark-bone.svg` | Monochrome on pitch |

### Square 1:1

| File | Use |
|------|-----|
| `docket-icon-pitch.svg` | **Default app icon** |
| `docket-icon-bone.svg` | Light store listings, print |
| `docket-icon-raised.svg` | In-app on warm paper |
| `docket-icon-ground.svg` | Matches page ground |
| `docket-icon-transparent.svg` | Compositing, slides |

### Favicon and PWA (generated into `ui/public/`)

`npm run gen:logo` writes these from the pitch app icon and OG artboard:

| File | Size | Use |
|------|------|-----|
| `favicon.svg` | 32 viewBox | Modern browser tab (vector) |
| `favicon-16.png` | 16 | Legacy tab icon |
| `favicon-32.png` | 32 | Legacy tab icon |
| `apple-touch-icon.png` | 180 | iOS home screen |
| `icon-192.png` | 192 | PWA manifest |
| `icon-512.png` | 512 | PWA manifest / splash |
| `icon-1024.png` | 1024 | App store / high-DPI |
| `og-image.png` | 1200x630 | Open Graph link previews |
| `site.webmanifest` | — | PWA install metadata |

Source SVGs in `logo/docket/`: `docket-favicon-pitch.svg`, `docket-icon-pitch.svg`,
`docket-social-og.svg`. `index.html` links every asset above.

### Lockups (mark + wordmark)

Wordmark: Instrument Sans 400, sentence case `Docket`, letter-spacing `-0.04em`.
Horizontal gap from mark to wordmark: 44 px (matches OffGrid `wordmark.svg`). Stacked gap
from mark to wordmark: 40 px. All lockups use `dominant-baseline="middle"` for optical
vertical centering.

| File | Aspect |
|------|--------|
| `docket-lockup-horizontal-pitch.svg` | 3:1 horizontal, pitch |
| `docket-lockup-horizontal-bone.svg` | 3:1 horizontal, bone |
| `docket-lockup-horizontal-transparent.svg` | 3:1 horizontal, transparent |
| `docket-lockup-stacked-pitch.svg` | 5:6 stacked, pitch |
| `docket-lockup-stacked-bone.svg` | 5:6 stacked, bone |

### Wide / social

| File | Size | Platform |
|------|------|----------|
| `docket-social-og.svg` | 1200 x 630 | Open Graph, Slack |
| `docket-social-banner-3x1.svg` | 1500 x 500 | Twitter/X header |
| `docket-social-16x9.svg` | 1600 x 900 | Slides, YouTube |
| `docket-social-1x1.svg` | 1080 x 1080 | Square social |
| `docket-social-9x16.svg` | 1080 x 1920 | Story, mobile splash |

### Monochrome

| File | Use |
|------|-----|
| `docket-mono-ink.svg` | Print on white |
| `docket-mono-bone-on-pitch.svg` | Reversed on dark |
| `docket-mono-transparent-ink.svg` | Watermark |

---

## 3. Choosing a variant

| Context | File |
|---------|------|
| App header (24 px) | `docket-mark-ember.svg` |
| App Store / dock icon | `docket-icon-pitch.svg` |
| Browser tab | `ui/public/favicon.svg` (generated from `docket-favicon-pitch.svg`) |
| Proposal cover | `docket-lockup-horizontal-pitch.svg` |
| Link preview | `docket-social-og.svg` |
| Footer (parent brand) | `logo/wordmark.svg` (OffGrid, not Docket) |

---

## 4. Rules

1. Radius 0, no shadows, no gradients.
2. Do not rotate, skew, or outline the mark.
3. Do not change bracket thickness or center proportions outside `gen-docket-logo.mjs`.
4. Do not place on `#FFFFFF`; use bone or ground tokens.
5. One Ember per surface (brackets only).
6. Wordmark is sentence case **Docket**, never caps.
7. Minimum size: 16 px square.

---

## 5. Raster export

```bash
rsvg-convert -w 1024 -h 1024 src/brand/logo/docket/docket-icon-pitch.svg -o docket-icon-1024.png
```

Standard sizes: 16, 32, 48, 72, 96, 120, 152, 167, 180, 192, 256, 512, 1024.

---

## 6. Related

- Icon exploration (superseded): `logo/docket-variants/README.md`
- Decision: `docs/decisions/2026-09-12-docket-bracket-mark-adopted.md`
- OffGrid parent marks: `logo/mark-ember.svg`, `logo/mark-ink.svg`
