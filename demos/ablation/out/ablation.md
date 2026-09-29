# Ablations — what Demo B's readiness reading loses per mechanism

Generated from `ablation.json` by `demos/ablation/run.py`; nothing below is typed by hand. Per GAO-23-106549's own scope limit (footnote 7; Appendix I), none of this speaks to whether the Army's underlying analysis was right — only to which representation failures a reading can still detect once a mechanism is removed.

### ep-omfv-2020-02-r4-fs — force structure designs and operational concepts

One table: every finding rule or question id this section's baseline carries, or that some variant gained, against every variant. `yes`/`—` is a finding present/absent; a rating or verdict cell shows `before → after` where a variant changed it and the baseline value otherwise.

| item | kind | baseline | scope-off | no-exclusions | gaps-collapsed | silence-off | gaps-collapsed-silence-off |
|---|---|---|---|---|---|---|---|
| `ReusePastPurpose` | finding | yes | lost | yes | yes | yes | yes |
| `bias-check-missing` | finding | yes | yes | yes | yes | yes | yes |
| `definition-missing` | finding | yes | yes | yes | yes | yes | yes |
| `inclusion-reason-missing` | finding | yes | yes | yes | yes | yes | yes |
| `linchpin-unevidenced` | finding | yes | yes | yes | yes | yes | yes |
| `objective-measured` | finding | yes | yes | yes | yes | yes | yes |
| `objective-run-coverage` | finding | yes | yes | yes | yes | yes | yes |
| `ref-integrity` | finding | — | — | — | gained | — | gained |
| `schema` | finding | — | — | — | gained | — | gained |
| `silence` | finding | — | — | — | gained | — | — |
| `silent-omission` | finding | yes | yes | yes (+) | yes | yes | yes |
| `vva-verbal` | finding | yes | yes | yes | yes | yes | yes |
| DES-1 | rating | 1 | 1 | 1 | 1 | 1 | 1 |
| DES-2 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| DES-3 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| DES-4 | rating | 1 | 1 | 1 | 1 | 1 | 1 |
| DES-5 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| DES-6 | rating | 3 | 3 | 3 | 3 | 3 | 3 |
| DES-7 | rating | 1 | 1 | 1 | 1 | 1 | 1 |
| DES-8 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| DES-9 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| EXE-1 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| EXE-2 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| EXE-3 | rating | 3 | 3 → 1 | 3 | 3 | 3 | 3 |
| EXE-4 | rating | 2 | 2 → 1 | 2 | 2 | 2 | 2 |
| EXE-5 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| EXE-6 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| EXE-7 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| EXE-8 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| PRE-1 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| PRE-2 | rating | 2 | 2 | 2 | 2 → 4 | 2 | 2 → 1 |
| PRE-3 | rating | 2 | 2 | 2 | 2 → 4 | 2 | 2 |
| PRE-4 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| objectivity | verdict | generally_objective | generally_objective | generally_objective | generally_objective → insufficient_to_conclude | generally_objective | generally_objective |
| reliability | verdict | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude |
| validity | verdict | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude |

Gained findings, bucketed (ruling R9 — a `schema` or `silence` finding produced by emptying a slot is never counted as evidence that the exclusion or gap object itself mattered), and the substitution count:

| variant | schema | silence | other | substitutions |
|---|---|---|---|---|
| scope-off | 0 | 0 | 0 | 0 |
| no-exclusions | 0 | 0 | 1 | 0 |
| gaps-collapsed | 1 | 1 | 1 | 135 |
| silence-off | 0 | 0 | 0 | 0 |
| gaps-collapsed-silence-off | 1 | 0 | 1 | 135 |

What each variant's loss means, in plain English:

- **scope-off**: the record no longer says whether evidence built to answer one question was reused to answer another, or whether a claim's evidence carries the metadata its classification level requires — only that a claim exists
- **no-exclusions**: the record no longer states *why* a study or a measure was left out; whatever silence that omission was covering is no longer distinguishable from an omission nobody explained
- **gaps-collapsed**: the record no longer says what was sought, where it was looked for, why it was not found, or what would resolve it — the questions a linchpin's rating still shows were asked, with every trace of the asking removed (gap objects lost: gap-234-report, gap-additional-studies, gap-ce-metrics-pointer, gap-con-inputs, gap-def-force-structure, gap-def-operational-concepts, gap-model-docs, gap-poland-data, gap-reliability-steps, gap-touchpoint-fields, gap-trac-aoa-model, gap-unnamed-efforts, gap-vendor-events, gap-weights)
- **silence-off**: an empty required field is no longer reported at all — the record can go quiet on a slot the schema requires and nothing downstream of the structural rules will say so
- **gaps-collapsed-silence-off**: the record no longer says what was sought, where it was looked for, why it was not found, or what would resolve it — the questions a linchpin's rating still shows were asked, with every trace of the asking removed; an empty required field is no longer reported at all — the record can go quiet on a slot the schema requires and nothing downstream of the structural rules will say so (gap objects lost: gap-234-report, gap-additional-studies, gap-ce-metrics-pointer, gap-con-inputs, gap-def-force-structure, gap-def-operational-concepts, gap-model-docs, gap-poland-data, gap-reliability-steps, gap-touchpoint-fields, gap-trac-aoa-model, gap-unnamed-efforts, gap-vendor-events, gap-weights)

### ep-omfv-2020-02-r4-ce — combat effectiveness

One table: every finding rule or question id this section's baseline carries, or that some variant gained, against every variant. `yes`/`—` is a finding present/absent; a rating or verdict cell shows `before → after` where a variant changed it and the baseline value otherwise.

| item | kind | baseline | scope-off | no-exclusions | gaps-collapsed | silence-off | gaps-collapsed-silence-off |
|---|---|---|---|---|---|---|---|
| `NotAssessableAtLevel` | finding | yes | lost | yes | yes | yes | yes |
| `bias-check-missing` | finding | yes | yes | yes | yes | yes | yes |
| `definition-missing` | finding | yes | yes | yes | yes | yes | yes |
| `inclusion-reason-missing` | finding | yes | yes | yes | yes | yes | yes |
| `linchpin-unevidenced` | finding | yes | yes | yes | yes | yes | yes |
| `objective-measured` | finding | yes | yes | yes | yes | yes | yes |
| `objective-run-coverage` | finding | yes | yes | yes | yes | yes | yes |
| `ref-integrity` | finding | — | — | — | gained | — | gained |
| `schema` | finding | — | — | — | gained | — | gained |
| `silence` | finding | — | — | — | gained | — | — |
| `silent-omission` | finding | yes | yes | yes (+) | yes | yes | yes |
| `vva-verbal` | finding | yes | yes | yes | yes | yes | yes |
| DES-1 | rating | 1 | 1 | 1 | 1 | 1 | 1 |
| DES-2 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| DES-3 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| DES-4 | rating | 1 | 1 | 1 | 1 | 1 | 1 |
| DES-5 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| DES-6 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| DES-7 | rating | 1 | 1 | 1 | 1 | 1 | 1 |
| DES-8 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| DES-9 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| EXE-1 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| EXE-2 | rating | 1 | 1 | 1 | 1 | 1 | 1 |
| EXE-3 | rating | 1 | 1 | 1 | 1 | 1 | 1 |
| EXE-4 | rating | 1 | 1 | 1 | 1 | 1 | 1 |
| EXE-5 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| EXE-6 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| EXE-7 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| EXE-8 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| PRE-1 | rating | 4 | 4 | 4 | 4 | 4 | 4 |
| PRE-2 | rating | 2 | 2 | 2 | 2 → 4 | 2 | 2 → 1 |
| PRE-3 | rating | 2 | 2 | 2 | 2 → 4 | 2 | 2 |
| PRE-4 | rating | 2 | 2 | 2 | 2 | 2 | 2 |
| objectivity | verdict | generally_objective | generally_objective | generally_objective | generally_objective → insufficient_to_conclude | generally_objective | generally_objective |
| reliability | verdict | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude |
| validity | verdict | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude | insufficient_to_conclude |

Gained findings, bucketed (ruling R9 — a `schema` or `silence` finding produced by emptying a slot is never counted as evidence that the exclusion or gap object itself mattered), and the substitution count:

| variant | schema | silence | other | substitutions |
|---|---|---|---|---|
| scope-off | 0 | 0 | 0 | 0 |
| no-exclusions | 0 | 0 | 1 | 0 |
| gaps-collapsed | 1 | 1 | 1 | 135 |
| silence-off | 0 | 0 | 0 | 0 |
| gaps-collapsed-silence-off | 1 | 0 | 1 | 135 |

What each variant's loss means, in plain English:

- **scope-off**: the record no longer says whether evidence built to answer one question was reused to answer another, or whether a claim's evidence carries the metadata its classification level requires — only that a claim exists
- **no-exclusions**: the record no longer states *why* a study or a measure was left out; whatever silence that omission was covering is no longer distinguishable from an omission nobody explained
- **gaps-collapsed**: the record no longer says what was sought, where it was looked for, why it was not found, or what would resolve it — the questions a linchpin's rating still shows were asked, with every trace of the asking removed (gap objects lost: gap-234-report, gap-additional-studies, gap-ce-metrics-pointer, gap-con-inputs, gap-def-force-structure, gap-def-operational-concepts, gap-model-docs, gap-poland-data, gap-reliability-steps, gap-touchpoint-fields, gap-trac-aoa-model, gap-unnamed-efforts, gap-vendor-events, gap-weights)
- **silence-off**: an empty required field is no longer reported at all — the record can go quiet on a slot the schema requires and nothing downstream of the structural rules will say so
- **gaps-collapsed-silence-off**: the record no longer says what was sought, where it was looked for, why it was not found, or what would resolve it — the questions a linchpin's rating still shows were asked, with every trace of the asking removed; an empty required field is no longer reported at all — the record can go quiet on a slot the schema requires and nothing downstream of the structural rules will say so (gap objects lost: gap-234-report, gap-additional-studies, gap-ce-metrics-pointer, gap-con-inputs, gap-def-force-structure, gap-def-operational-concepts, gap-model-docs, gap-poland-data, gap-reliability-steps, gap-touchpoint-fields, gap-trac-aoa-model, gap-unnamed-efforts, gap-vendor-events, gap-weights)
