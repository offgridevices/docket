# Fonts vendored into this UI

Self-hosted via `@fontsource/*` npm packages (see `ui/package.json`), imported once in
`ui/src/brand/fonts.css`. Vendored rather than loaded from `fonts.googleapis.com` at
runtime so the demo works with no internet at an event and so screenshots are
reproducible. All three are Google Fonts, redistributed here under their original open
licences:

| Family | Weight/style used | Licence | Upstream |
|---|---|---|---|
| Instrument Sans | 400, 500 | SIL Open Font License 1.1 | https://fonts.google.com/specimen/Instrument+Sans |
| Newsreader | 400 italic | SIL Open Font License 1.1 | https://fonts.google.com/specimen/Newsreader |
| JetBrains Mono | 400, 500 | Apache License 2.0 | https://fonts.google.com/specimen/JetBrains+Mono |

**Brand v3.0 (2026-09-08)** retired Archivo 900 and Inter Tight: display and body are now
one face, Instrument Sans, in sentence case. Both retired packages were uninstalled from
`ui/package.json`, so nothing OFL-licensed is vendored here that is not in the table
above. See `docs/decisions/2026-09-08-demo-ui-rebuilt-on-brand-v3.md`.

**Note (plan 07 Task 5, fix round 1):** the plan's original ruling was "if `NOTICE.md`
exists, append the four font licences there; if it does not, leave this file and note it
in the ledger." `NOTICE.md` does exist, but it is scoped — by its own opening paragraph —
to third-party *documents in `sources/`*, cited per-item from a `.source.md` sidecar;
there is no sidecar convention for a vendored code dependency's licence, so appending a
full font-licence section there would not fit its structure. The task-5 review flagged
this as needing a plan-owner ruling (M5) rather than silence; the ruling that came back
keeps this file as the detailed record and adds one line to `NOTICE.md` pointing here
("UI typefaces: OFL-licensed, see `ui/src/brand/FONTS.md`."), so a reader of `NOTICE.md`
is not left wondering whether front-end dependencies were considered at all.
