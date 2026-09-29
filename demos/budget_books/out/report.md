# Value conflicts in the public OMFV/XM30 budget record

A *value conflict* here is one thing — one line item, one date, one definition —
stated at two different values, either on two pages of the same document or
across two documents. The kernel reports the disagreement and names every page it
read. It does not decide which figure is right, and neither does this file.

Kernel input: the record built by `demos/budget_books/build.py`, `now` = 2026-09-05T00:00:00Z.

Locators are dual. `volume p. 3d-268` is the page number printed in the footer of
the source volume; `extract PDF p. 74` is where that sheet sits in the committed
extract. Open the extract at the extract page and read the volume page off the
bottom of the sheet.

## Conflicts within one document — 2 (blocking)

### 1. `omfv-aoa.window` — within `ev-pb2021`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2021` | started FY2019 | PB2021 PE 0604100A R-2A, volume p. 451 (extract PDF p. 75) |
| `ev-pb2021` | 2Q2020-1Q2021, completion | PB2021 PE 0605625A R-4A, volume p. 506 (extract PDF p. 92); R-2A, volume p. 500 (extract PDF p. 86) |

### 2. `omfv-mta-total-cost-fy21-24.costM` — within `ev-pb2024`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2024` | 1348 | PB2024 PE 0603645A R-2/R-2A, volume pp. 2a-99, 2a-101 (extract PDF pp. 60, 61) |
| `ev-pb2024` | 1384 | PB2024 PE 0605625A R-2/R-2A, volume pp. 3d-268, 3d-270 (extract PDF pp. 74, 76) |

## Conflicts across documents — 6 (warning)

### 1. `omfv-acdd.quarter`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2022` | 1Q-2Q FY2022 | PB2022 PE 0605625A R-4A, volume p. 463 (extract PDF p. 92) |
| `ev-pb2023` | 1Q-2Q FY2022 | PB2023 PE 0605625A R-4A, volume p. 2e-268 (extract PDF p. 84) |
| `ev-pb2024` | 2Q-2Q FY2022 | PB2024 PE 0605625A R-4A, volume p. 3d-281 (extract PDF p. 87) |
| `ev-pb2025` | 2Q-2Q FY2022 | PB2025 PE 0605625A R-4A, volume p. 3d-204 (extract PDF p. 77) |
| `ev-pb2026` | 2Q-2Q FY2022 | PB2026 PE 0605625A R-4A, volume p. 3d-339 (extract PDF p. 74) |
| `ev-pb2027` | 2Q-2Q FY2022 | PB2027 PE 0605625A R-4A, volume p. 3d-320 (extract PDF p. 64) |
| `ev-gao-23-106059` | 2022-07 (4Q FY2022) | GAO-23-106059 printed p. 128 (PDF p. 138), OMFV programme profile — the PDF is a deliberate sidecar-only source; see sources/gao-23-106059.source.md |

### 2. `omfv-phase2-award.date`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2022` | 2021-07 | PB2022 PE 0605625A R-3, volume p. 460 (extract PDF p. 89) |
| `ev-pb2023` | 2021-07 | PB2023 PE 0605625A R-3, volume p. 2e-264 (extract PDF p. 80) |
| `ev-gao-23-106549` | 2021-09 | GAO-23-106549, Highlights page (PDF p. 2) and printed p. 5 (PDF p. 8) |

### 3. `aries.definition`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2026` | Augmented Reality Integrated Environment for Situational Awareness - crew display overlay | PB2026 PE 0605625A R-2A, volume p. 3d-330 (extract PDF p. 65) |
| `ev-industry-day-2020-12` | performance M&S: highlights sensitivities between functional requirements | Industry Day briefing, PDF p. 18 (slide footer 20) |

### 4. `cave.definition`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2026` | Commanders Aperture Visual Enhancement - 360-degree camera/sensor system | PB2026 PE 0605625A R-2A, volume p. 3d-330 (extract PDF p. 65) |
| `ev-industry-day-2020-12` | Immersive Simulation modeling; first-person perspective of the design | Industry Day briefing, PDF p. 18 (slide footer 20) |

### 5. `omfv-aoa.window`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2021` | started FY2019 | PB2021 PE 0604100A R-2A, volume p. 451 (extract PDF p. 75) |
| `ev-pb2021` | 2Q2020-1Q2021, completion | PB2021 PE 0605625A R-4A, volume p. 506 (extract PDF p. 92); R-2A, volume p. 500 (extract PDF p. 86) |
| `ev-pb2023` | formal execution FY2023 | PB2023 PE 0605625A R-2A, volume p. 2e-261 (extract PDF p. 77) |
| `ev-pb2024` | formal execution FY2023 | PB2024 PE 0605625A R-2A, volume p. 3d-271 (extract PDF p. 77) |
| `ev-pb2025` | started FY2023, continuing to FY2025 | PB2025 PE 0604100A R-2A, volume p. 2b-33 (extract PDF p. 52) |

### 6. `omfv-mta-total-cost-fy21-24.costM`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2023` | 1432.1 | PB2023 PE 0605625A R-2/R-2A, volume pp. 2e-257, 2e-259 (extract PDF pp. 73, 75) |
| `ev-pb2024` | 1348 | PB2024 PE 0603645A R-2/R-2A, volume pp. 2a-99, 2a-101 (extract PDF pp. 60, 61) |
| `ev-pb2024` | 1384 | PB2024 PE 0605625A R-2/R-2A, volume pp. 3d-268, 3d-270 (extract PDF pp. 74, 76) |
| `ev-pb2025` | 1330 | PB2025 PE 0605625A R-2/R-2A, volume pp. 3d-191, 3d-192 (extract PDF pp. 64, 65) |

## Subjects the rule read and did not report

A subject with one value across every page that states it is not a conflict.
`omfv-mta-total-cost-fy21-25` is here on purpose: it is a five-year window,
not the four-year one, and keeping it under its own subject key is what stops
the rule reporting a scope difference as a disagreement.
`omfv-concept-design` is here for the opposite reason: it is the Army
statement most directly comparable with the award date, it is uncontested,
and the award-date conflict above should be read beside it.

### `omfv-concept-design.window`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2022` | 4Q FY2021 - 1Q FY2023 | PB2022 PE 0605625A R-4A, volume p. 463 (extract PDF p. 92) |
| `ev-pb2023` | 4Q FY2021 - 1Q FY2023 | PB2023 PE 0605625A R-4A, volume p. 2e-268 (extract PDF p. 84) |
| `ev-pb2024` | 4Q FY2021 - 1Q FY2023 | PB2024 PE 0605625A R-4A, volume p. 3d-281 (extract PDF p. 87) |
| `ev-pb2025` | 4Q FY2021 - 1Q FY2023 | PB2025 PE 0605625A R-4A, volume p. 3d-204 (extract PDF p. 77) |
| `ev-pb2026` | 4Q FY2021 - 1Q FY2023 | PB2026 PE 0605625A R-4A, volume p. 3d-339 (extract PDF p. 74) |
| `ev-pb2027` | 4Q FY2021 - 1Q FY2023 | PB2027 PE 0605625A R-4A, volume p. 3d-320 (extract PDF p. 64) |

### `omfv-mta-total-cost-fy21-25.costM`

| Document | Value | Locator |
|---|---|---|
| `ev-pb2027` | 1536 | PB2027 PE 0605625A R-2/R-2A, volume pp. 3d-306, 3d-308 (extract PDF pp. 50, 52) |


## Everything else the validator said

This record is an ingestion, not a readiness record. No claim cites any
register entry, so `silent-omission` fires once per evidence object and the
record is deliberately not ready.

| Rule | Findings |
|---|---|
| `silent-omission` | 10 |
