# GAO-21-460 validation — per-question agreement

Blinded reconstruction of the Army's 2021 MDO TWV Study from GAO's description of it; scored under tailoring `gao-21-460`, kernel 0.1.0.

GAO-21-460 Figure 6 is the only per-question published key in the GAO record. GAO assessed the *study*, and this reconstruction is built from GAO's description of the study, not from the study's own documents.

- Agreement: **0.857** (18/21) vs majority baseline 0.667
- Cohen's kappa: **0.710**
- 'Unable to assess' precision/recall: 0.70 / 1.00
- By band: design 1.000, execution 0.625, presentation 1.000
- Disagreements: EXE-3, EXE-4, EXE-5
- `ready`: false — blockers model-vva, objective-run-coverage, silent-omission. A study that had not reported is not a signable record, and the report says so rather than hiding it.
- Presentation-band caveat: two sentences inside the pages the blinded builder had to read state that the study had not reported — printed p. 14, "As the study is not yet complete, we were not able to examine the consistency and verifiability of data measurement as well as the description and documentation of the models used for the study", and printed p. 35, "The 2021 MDO TWV Study final report was not available during the time of our audit so we were able to assess only the design portion and portions of the execution of the study against the standards." Both are load-bearing (the first is why every VV&A section is a gap; the second is why the episode has no claims and no runs), so they were disclosed, not redacted. The presentation band is therefore close to deterministic given the visible text; the design and execution bands carry the information, which is why `by_band` is reported.

| question | band | kernel state | rule | kernel label | GAO label | match |
|---|---|---|---|---|---|---|
| DES-1 | design | 1 | `charter_complete_and_plan_approved→1` | assessed | assessed | yes |
| DES-2 | design | 1 | `charter_question_and_terms_defined→1` | assessed | assessed | yes |
| DES-3 | design | 1 | `scope_defined_and_terms_defined→1` | assessed | assessed | yes |
| DES-4 | design | 1 | `assumptions_all_have_rationale→1` | assessed | assessed | yes |
| DES-5 | design | 1 | `assumptions_all_evidenced_and_consistent→1` | assessed | assessed | yes |
| DES-6 | design | 2 | `any_assumption_varied→2` | assessed | assessed | yes |
| DES-7 | design | 1 | `constraints_discussed→1` | assessed | assessed | yes |
| DES-8 | design | 1 | `scenarios_have_rationale→1` | assessed | assessed | yes |
| DES-9 | design | 1 | `scenarios_cover_conditions→1` | assessed | assessed | yes |
| EXE-1 | execution | 1 | `methodology_covers_objectives→1` | assessed | assessed | yes |
| EXE-2 | execution | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| EXE-3 | execution | 4 | `always→4` | unable_to_assess | assessed | NO |
| EXE-4 | execution | 4 | `always→4` | unable_to_assess | assessed | NO |
| EXE-5 | execution | 4 | `always→4` | unable_to_assess | assessed | NO |
| EXE-6 | execution | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| EXE-7 | execution | 2 | `ms_limitations_some→2` | assessed | assessed | yes |
| EXE-8 | execution | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| PRE-1 | presentation | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| PRE-2 | presentation | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| PRE-3 | presentation | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| PRE-4 | presentation | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
