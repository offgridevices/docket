# GAO-21-460 (Accessible Version)

| | |
|---|---|
| Local file | `gao-21-460-tactical-wheeled-vehicles-accessible.pdf`, not committed; fetch it to this name beside this note |
| Title | Tactical Wheeled Vehicles: Army Should Routinely Update Strategy and Improve Communication with Industry — Accessible Version |
| Publisher | U.S. Government Accountability Office |
| Published | 2021-07-15 |
| Pages | 51 |
| Landing page | https://www.gao.gov/products/gao-21-460 |
| Direct file | https://files.gao.gov/assets/gao-21-460.pdf |
| Release status | **Public.** Report to Congressional Committees, no distribution limitation. Release check on pp. 1–2: `no-CUI-marking`. See the marking note below — page 3 carries an unfilled template placeholder that looks like a CUI banner. |
| Retrieved | 2026-09-02, via headless Chrome (gao.gov returns HTTP 403 to plain scripted requests) |

**Marking note — the page-3 placeholder is not a CUI marking.** Page 3 of this
edition opens with the literal line:

> `CUI//SSI SENSITIVITY CATEGORY [IF REQUIRED] - DRAFT`

This is an **unfilled GAO template placeholder, not an applied marking**. The
`[IF REQUIRED]` prompt and the `DRAFT` token are both still present — a real
banner would name a category and would not say `DRAFT`. The document is a
published Report to Congressional Committees, distributed from gao.gov with no
distribution limitation.

Checked, not assumed. A `pypdf` scan of **all 51 pages** looking for banner-shaped
lines (a line that is exactly `CUI`, or begins `CUI//` or
`CONTROLLED UNCLASSIFIED INFORMATION//`) returned:

```
pages: 51
banner-marks: 1 | other CUI mentions: 0
  BANNER page 3 | 'CUI//SSI SENSITIVITY CATEGORY [IF REQUIRED] - DRAFT'
```

One hit, on one page, and it is the placeholder quoted above. No other page in
the document carries a banner and there are no other CUI mentions anywhere in
the text. The same scan over the standard print rendering of the same report
(`library/gao/gao-21-460-tactical-wheeled-vehicles.pdf`, 43 pp.) returns **zero**
hits, which confirms the stray line is an artefact of producing the Section 508
edition rather than anything about the report's release status.

**Page offset: printed = PDF − 5.** This edition carries five pages of front
matter before printed page 1, so the report's own printed page *N* is PDF page
*N + 5*. Verified page by page, not assumed: every extracted page's text carries
its own `Page N GAO-21-460` footer, and the check was run over PDF pp. 11, 14,
16, 17, 18, 19, 40, 41 (= printed 6, 9, 11, 12, 13, 14, 35, 36). Figure 6 is
printed p. 39 = PDF p. 44; its linearised text is printed pp. 40–41 = PDF
pp. 45–46. Every locator in `demos/validation_gao_21_460/` carries both numbers.

**The only per-question published answer key in the whole GAO record.** Figure 6
colour-codes each of the 21 research-standard questions Assessed / Unable to
assess — 14 and 7 respectively. This is the Section 508 / WCAG 2.0 AA remediated
edition, in which figures and tables are rendered as linearised text; the
standard print rendering is 43 pages and extracts far less cleanly.

Used by: the validation run.
