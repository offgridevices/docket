# The demo UI ships light only

Date: 2026-09-08. Status: settled by Shreyash, 2026-09-08. Closes open decision 3 in
`docs/design/frontend-design.md`.

**Chosen:** one theme. `ui/src/brand/tokens.css` carries the light semantic ramp and
nothing else — no `prefers-color-scheme` block, no `[data-theme="dark"]` block. There is
no theme toggle in the header, no `src/lib/theme.ts`, and no `data-theme` attribute. The
Playwright suites run light only; `THEMES` in `ui/e2e/_fixtures.ts` loses its dark member.

**Over:** light by default with the toggle retained (brand-compliant, keeps dark test
coverage); and keeping the dark tokens in the stylesheet but unreachable.

**Why.** Readability, decided by the person who demonstrates it. A single theme also
removes a class of demo failure — no OS preference, stale `localStorage` or mis-set
attribute can put a projector into dark at the wrong moment — and it makes every
screenshot in Volume 2 light without a per-figure override, which is what prints. Dark
screenshots print as ink blocks.

**This is a deliberate deviation from the brand, not an oversight.** Handoff v3.0 requires
both modes and says so twice: *"Don't fight the user's OS preference"* and *"Test both
modes for any new screen before it ships."* The deviation is recorded rather than absorbed
because a reader coming to this repository from the brand repo will otherwise read it as a
mistake. It is also narrow: it binds this demo UI only, and says nothing about the
website or any other OffGrid surface.

Note that the brand's own documents disagree about the default. Quick rule 10 of the
handoff README says *"Dark by default. Light by preference"*, while the v2.1 banner at the
top of the same file, the versioning table and `tokens.css` §2 all make light the default.
Rule 10 appears to be stale text carried over from v1.2. Light-only is therefore a
deviation from the dual-mode requirement, but it is not a deviation from the default.

**Would reverse if:** the event turns out to be in a darkened room where a light projector
is genuinely worse, or the brand owner objects to a product surface shipping single-mode.
Reversal is cheap by construction — the deleted blocks are one copy from the handoff and
the components consume semantic tokens throughout, so nothing but `tokens.css`, the header
and the test fixture would change.
