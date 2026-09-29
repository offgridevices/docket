# The demo UI rebuilds on brand v3.0

Date: 2026-09-08. Status: settled by Shreyash, 2026-09-08.

**Chosen:** rebuild `ui/` against the OffGrid brand handoff **v3.0**
(`offgridevices/offgrid-brand`, `handoffs/2026-09-08-brand-v3.0/handoff/`), replacing the
v1.2 tokens the UI was built on. The token files are copied into `ui/` with a provenance
header, as v1.2 already was — not pulled at build time and not added as a submodule.

**Over:** staying on v1.2 and hand-patching the parts that had visibly drifted; and
vendoring the brand repo as a git submodule.

**Why.** v1.2 is two major versions stale. Between it and v3.0 the brand executed the
"BONE" pivot (v2.0) and the software pivot (v3.0), and three things changed that the UI
cannot express under v1.2:

1. **Light became the canonical expression**, not dark. `tokens.css` §2 now resolves the
   semantic tokens to the warm-paper ramp by default.
2. **Display type is Instrument Sans 400 in sentence case** — "authority comes from size,
   never from weight or caps". Archivo 900 uppercase and Inter Tight are both retired.
   Every nav item, button and label in the app is currently uppercase; under v3.0 none of
   them are.
3. **Mono is demoted to numerals, coordinates and code only.** §5 of the frontend design
   put "every object id, numeral, label, hash, state, eyebrow" in JetBrains Mono. Ids,
   hashes, counts and raw JSON keep it; eyebrows and labels move to Instrument Sans 500.

A submodule was rejected because the brand repo is private and CI must build without
credentials for it; the handoff's own guidance is to "copy the assets you need into the
consuming repo at build time rather than depending on this repo at runtime".

Two edits to the copied files are deliberate and are recorded in their headers: the remote
Google Fonts `@import` is removed in favour of self-hosted `@fontsource` (the demo must run
with no internet — see `Makefile`), and the accent hex is resolved per
`2026-09-08-ember-is-ff6a00.md`.

**Also settled here: the UI becomes responsive to 360 px.** This reverses the Phase I
scope cut recorded in §3 and §9 of `docs/design/frontend-design.md`, which listed "mobile
layout" as out of scope. The reversal is cheap because v3.0 prescribes the technique
rather than leaving it open — its reference page is built on fluid `clamp()` gutters and
`auto-fit` grids, and states the rule directly: *"Gutter is FLUID. `--og-gutter` is the
ceiling, never a fixed value — a shell that cannot narrow is the wrong thing to copy."*

**Would reverse if:** the brand owner issues a v4 that moves again before the
2026-10-21 close, in which case the figures freeze at v3.0 and the update waits for
Phase II — a proposal figure that disagrees with the running software is worse than a
figure one version behind. It would also reverse if self-hosting Instrument Sans turned
out to break the offline demo, which would send the type question back open.
