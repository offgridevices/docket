# The demo UI carries five semantic state colours

Date: 2026-09-11. Status: settled by Shreyash, 2026-09-11 (round-two brief, R24).

**Chosen:** five semantic tokens — act (Ember), stop (red `#B3261E`), wait (amber
`#8A5F00`), done (green `#2E6B3F`), AI (blue `#2F5F8F`) — each with a text/icon value
above 4.5:1 on the paper ground, a tint and a hairline, defined in
`ui/src/brand/semantic.css` and exposed through Tailwind as `text-stop`, `bg-stop-tint`,
`border-stop-line` and their siblings. Colour lives on glyphs, provenance marks, 3 px left
borders, chips, tints and outline buttons — never on running prose except the two header
counters, and never as a second filled button. **The rule that survives intact is that
only one Ember-filled element exists per view**: the act to do next, else the most severe
blocking finding, else none. `assertSingleEmber` keeps counting fills; `assertNoStopFill`
refuses a red plane.

**Over:** staying monotone (brand v3.0's one-accent rule, which the UI followed until
this round); and a conventional red/amber/green dashboard palette with red fills.

**Why.** The one-accent rule was written for marketing surfaces. A working tool needs
state colour that people learn once, so that status reads at a glance without reading a
sentence — Shreyash's own words when testing the first round: "very monotone … be very
intentional about why." Every placement is enumerated in the round-two brief (spec
Appendix B §1) and the key is printed on the product itself, at the foot of the map, in
the Explain panel and in the Coverage sheet. Numbers never carry colour; their meaning is
in the sentence beside them.

**Would reverse if:** the brand owner objects to state colour on a product surface, or
the projector test shows the tints indistinguishable at the back of the room. Reversal is
one file (`semantic.css`) plus the Tailwind mapping; every component consumes the tokens
by name.
