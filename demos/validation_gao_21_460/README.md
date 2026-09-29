# Validation walk — GAO-21-460, blinded, scored against Figure 6

The Army's 2021 Multi-Domain Operations Tactical Wheeled Vehicle Study, rebuilt as a
docket record **from GAO's description of it only**, by an agent that had never seen
GAO's answer key; then scored by a deterministic rule set that was written before the
reconstruction existed; then compared, question by question, with GAO-21-460 Figure 6.

Figure 6 is the **only per-question published key in the whole GAO record**. There are 26
GAO products that apply these "generally accepted research standards" and 21 true answer
keys (2006–2024). GAO-23-106549 publishes a 3×3 verdict grid and nine findings, not
per-question labels; any per-question reading of *that* report is ours and is labelled as
such elsewhere in this repository.

```
uv run python -m demos.validation_gao_21_460.run
uv run pytest -q tests/demos/test_validation_gao_21_460.py
```

---

## 1. The blinding protocol, as executed

**Who was blinded.** Exactly one agent: the author of `build.py`. It was a fresh agent
with no prior context in this workstream. The author of this README, the reviewer and
every other agent on this plan are unblinded and were never reused as the builder.

**What it was given, and nothing else.** `study_description.txt` (below),
`src/docket/schema/objects.yaml` and the per-type JSON schemas,
`demos/a_cbo_gcv_2013/build.py` as the pattern, `src/docket/store.py`,
`src/docket/errors.py`, `src/docket/kernel/validate.py`, and a **fixture table written by an
unblinded author** (see the boundary below). It was told, in these words, not to open the GAO
PDF, `ground_truth.yaml`, anything under `src/docket/standard/`, `docs/design/`,
`.superpowers/` or anything under `library/`, and not to run the scorer, `readiness_report`
or `run.py` — seeing per-question states would let it reverse-engineer the key.

**Where the blind stops — the boundary a hostile reader will find first.** The fixture table
handed to the builder was not a bare list of ids. It supplied the object list, most field
values, every verbatim quotation, the gap-versus-content split for each field, and the single
most consequential instruction in the walk — *"do not add Claims, Observations, Runs or a
Commitment."* It was written by an **unblinded** author who had read the plan's expected
per-question consequences and who reasons explicitly, elsewhere in the same brief, about the
`model_vva` → `models_scope_ok` → EXE-3 ladder. So:

> The blind protects against the **builder** fitting the fixture to the key. It does not, by
> construction, protect against the **brief** doing so.

That is a property of the design, not an accident of this run, and it is stated here rather
than left to be discovered. The builder's own contribution was transcription fidelity against
the eight extracted pages, and the schema-required fields the brief had missed — roughly a
dozen of them, listed in §6.

**The evidence that the channel was not exploited, and it is checkable.** The brief predicted
**20 of 21** with the execution band at or above 0.75. The measurement came in at **18 of 21**
with the execution band at 0.625, and the brief's per-question expectations are wrong on
**exactly EXE-4 and EXE-5** — the two questions a ladder-aware author fitting a fixture to the
key would have got right first. A reconstruction reverse-engineered from the ladders plus the
key would not have missed those two. The shortfall is the strongest available evidence about
the brief, and it is the reason it is reported here rather than repaired.

**`study_description.txt`** is a mechanical `pypdf` extraction of eight printed pages —
6, 9, 11, 12, 13, 14, 35, 36 (PDF 11, 14, 16, 17, 18, 19, 40, 41; **printed = PDF − 5**,
verified page by page against each page's own `Page N GAO-21-460` footer). Figure 6 and
its linearised text are printed pp. 39–41 (PDF 44–46), which the extraction does not touch.

**The denylist, and why each entry is on it.**

| Withheld | Why |
|---|---|
| `sources/gao-21-460-tactical-wheeled-vehicles-accessible.pdf` | contains Figure 6 |
| `demos/validation_gao_21_460/ground_truth.yaml` | is the key |
| `src/docket/standard/research-standards-36.yaml` | **carries the key**: every question has a `usage` map, and `usage["GAO-21-460"]` reads `assessed` / `unable_to_assess` / `not_in_figure_6` — seven `unable_to_assess`, the exact answer. This is a leak channel through a source file that looks like a schema, and it is the least obvious entry on this list |
| `src/docket/standard/tailorings/gao-21-460.yaml`, `src/docket/standard/rules.yaml`, `src/docket/kernel/standards.py`, `tests/kernel/test_standards.py` | the ladders and predicates let a builder reverse-engineer which fixture shapes reach which state; the test module also holds a walk table |
| `library/**` | holds the derived Figure 6 transcription |
| the plan file and the SDD ledger | both state expected per-question consequences outright |

**How it was enforced, not merely asked for.**

* `ground_truth.yaml` is written by a different, unblinded step. `build.py` never reads it
  and never names it; `run.py` is the only module that opens it.
* A grep gate over the blinded side, run as a test
  (`test_the_key_is_never_read_by_the_fixture`,
  `test_the_extracted_description_is_the_eight_study_pages_and_nothing_else`): the strings
  `unable_to_assess`, `unable to assess`, **`unable to access`**, **`unable to be
  accessed`**, **`not_in_figure_6`**, `ground_truth`, `Figure 6`, `answer key`, `14/7` must
  not appear in `build.py` — the three bolded strings are GAO's own wording in the
  linearised Figure 6 text and the third value in `research-standards-36.yaml`'s `usage`
  map, so each can only have come from the key channel; the eight page markers in
  `study_description.txt` must be
  exactly printed pp. 6, 9, 11, 12, 13, 14, 35, 36; and Figure 6's caption and legend words
  must not appear in it.
* The builder's transcript was audited for reads of denylisted paths. **No hit.** Two reads
  outside its allow-list were disclosed by the builder itself and are recorded here for
  completeness: two lines of `src/docket/schema/generate.py` (an id regex) and the
  `[tool.ruff]` block of `pyproject.toml` (line length). Neither carries any label.

**Disclosed deviation from the protocol as written.** The protocol predicted zero
occurrences of the phrase "Appendix II" in the extracted description. There are two, both
cross-references rather than content — printed p. 6, *"A full list of the generally
accepted research standards by which we assessed portions of the Army's 2021 MDO TWV Study
are included in appendix II"*, and printed p. 35, *"Appendix II provides a list of these
standards and associated questions."* Both are on pages the fixture needs and neither
reproduces a label; following the pointer would have required opening the PDF, which the
protocol forbids and the transcript audit confirms did not happen. The test asserts the
count is exactly two rather than pretending it is zero.

---

## 2. The residual leak — disclosed, not denied

Two sentences **inside the pages the blinded builder had to read** telegraph seven of the
twenty-one labels:

> printed p. 14 (PDF 19): *"As the study is not yet complete, we were not able to examine
> the consistency and verifiability of data measurement as well as the description and
> documentation of the models used for the study."*

> printed p. 35 (PDF 40): *"The 2021 MDO TWV Study final report was not available during
> the time of our audit so we were able to assess only the design portion and portions of
> the execution of the study against the standards."*

Both are load-bearing. The first is why every VV&A section in the record is a gap; the
second is why the episode has no claims and no runs at all. Redacting them would have
produced a fixture that does not match the source, which is a worse failure than a
disclosed leak. So they stayed in, and the consequence is stated plainly: **the
presentation band is close to deterministic given the visible text.** All four presentation
questions were always going to reach `always → 4`. `by_band` is reported for exactly this
reason, and the informative part of the comparison is the **design** and **execution**
bands. Any sentence built on the headline number — in the validation report or in the
proposal — must carry this caveat.

---

## 3. What was measured

Read from `out/agreement.json`, kernel 0.1.0, tailoring `gao-21-460`, seed 21460,
`now` fixed at 2021-05-01.

| statistic | value |
|---|---|
| Agreement with Figure 6 | **0.857** (18 of 21) |
| Majority baseline (always "assessed", 14/21) | 0.667 |
| Cohen's κ | **0.710** |
| By band | design 1.000, execution 0.625, presentation 1.000 |
| "Unable to assess" precision / recall | 0.70 / 1.00 |
| Confusion (positive = unable_to_assess) | tp 7, fp 3, fn 0, tn 11 |

Every one of GAO's seven "unable to assess" labels is caught (recall 1.00); all
three misses run the other way — the kernel declines to assess three questions GAO
assessed. The scorer is conservative here, which is the direction an evidence-discipline
tool should err in, and it is still a disagreement.

**This walk did not hit its brief's expectation, and the number was not adjusted to fit.**
The commissioning brief expected 20 of 21 with the execution band at or above 0.75. The
measured result is 18 of 21 with the execution band at 0.625. No fixture
value was changed and no rule was touched after the key was read. The three disagreements
are named below with the rule that produced each.

### Per-question

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
| EXE-3 | execution | 4 | `always→4` | unable_to_assess | assessed | **NO** |
| EXE-4 | execution | 4 | `always→4` | unable_to_assess | assessed | **NO** |
| EXE-5 | execution | 4 | `always→4` | unable_to_assess | assessed | **NO** |
| EXE-6 | execution | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| EXE-7 | execution | 2 | `ms_limitations_some→2` | assessed | assessed | yes |
| EXE-8 | execution | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| PRE-1 | presentation | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| PRE-2 | presentation | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| PRE-3 | presentation | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |
| PRE-4 | presentation | 4 | `always→4` | unable_to_assess | unable_to_assess | yes |

The kernel's four states are **not** GAO's labels. Figure 6 publishes two —
"Assessed" and "Unable to assess" — and `label_from_state` collapses `1|2|3 → assessed`,
`4 → unable_to_assess`. Nothing in the table above should be read as GAO having rated
anything 1, 2, 3 or 4.

---

## 4. The three disagreements

All three are the kernel saying "unable to assess" where GAO said "assessed", and all
three fall off the end of their ladder for a structural reason that traces back to the
same fact: **the Army's study had not reported**, so the record carries no claims and no
observations.

**EXE-3 — "Were the models used to support the analyses appropriate for their intended
purpose?"** This one was predicted before the key was opened, and it was kept rather than
engineered away. GAO's description names two methods: the Logistics Battle Command
simulation, whose accreditation the description does record (Army modelling officials, an
internal verification and validation process by experts not on the project, printed p. 13),
and the **capabilities based assessment**, for which the description records no
accreditation at all. The record therefore carries `mdl-cba` with `vva-cba` whose
`accreditationDecision` is a gap object. The policy rule `model_vva` emits a blocking
`model-vva` finding, `models_scope_ok` is false, and EXE-3 walks to `always → 4`.

**The reciprocal case, for anyone comparing the two reconstructions:** the GAO-15-548
positive control (`demos/control_gao_15_548`) records its models' `accreditationDecision`
with `basis: "document"` rather than as a gap, because GAO-15-548 printed p. 2 says GAO
had the study's documentation — "interim and final study briefings, backup slides that
detail the methodological elements of the study, and the final report to the congressional
defense committees" — and found the method sound. Here the same field is a gap or an
interview-basis assertion because GAO-21-460 printed p. 35 says the study's **final report
was not available** during the audit. Different evidence on the page, different record;
the treatments are principled rather than convenient, and both are labelled as ours.

The alternative was to drop `mdl-cba` — but `Plan.steps[].evaluator` is a required
reference and not a slot, so the mobility and launch-and-support steps would have had no
evaluator, which the schema forbids. Dropping it would also have been a fidelity error:
GAO's description does name the capabilities based assessment as the study's method
(printed pp. 12–13). The fixture is right on the source and disagrees with GAO. That is
reported, not repaired.

**EXE-4 — "Were the data used valid for the study's purposes?"** and **EXE-5 — "Were the
data used sufficiently reliable for the study's purposes?"** Both ladders read evidence
*cited by a claim or an observation* (`data_scope_all_known` / `data_scope_some_known`;
`reliability_all` / `reliability_some`). This record has neither, so the cited-evidence set
is empty, neither the "all" nor the "some" clause can fire, and both questions reach
`always → 4`. The record does hold four real `DataReliabilityStep` objects transcribed off
printed p. 13 — the Future Operational Environment Directorate's validation of two Mobility
criteria, subject-matter-expert review of the mobility percentages, program-manager
validation of the vehicle counts, and the Capabilities Developments Integration
Directorates' workshops — and every dataset in the register names the steps that back it.
The kernel does not reach them, because nothing in the record *asserts* anything on their
basis.

That is a genuine limitation of the schema's reading and it is worth stating as one: the
kernel scores data validity and reliability at the point where evidence is *used to support
a claim*. GAO could assess both from interviews with the officials who ran the study,
without a report. A record that captures the study's data-handling process but has not yet
reported is, to this kernel, not yet assessable on those two questions. Two candidate
readings follow — that the predicates should fall back to the episode's evidence register
when no claim exists, or that GAO and the kernel are measuring different things at this
point in a study's life — and neither was acted on here, because changing a rule after
seeing the key is exactly the move this walk exists to rule out.

---

## 5. Why the presentation band cannot have been gamed

`claims_exist` is false (there are no claims), `claims_all_supported` is false, and
`runs_exist` is false. All four presentation questions reach `always → 4`, which
`label_from_state` maps to `unable_to_assess` — GAO's own four presentation labels. The
narrative-only clauses added to PRE-3 and PRE-4 elsewhere in this plan are gated on
`claims_exist` and are unreachable here. **No rule was changed to hit this number**, and
no rule change of that shape could have reached it.

---

## 6. The reconstruction's own honesty list

Everything in the record that is not straight off a GAO page:

* **`ch-twv-2021.consequencesOfErroneousOutput` is reconstructed.** GAO-21-460 does not
  state the consequences of the study being wrong, and the G1 charter check requires
  content in that field — a gap marker refuses the transition. Rather than let the schema
  force a plausible-sounding fabrication with no marker, the sentence is written, it says
  inside itself that it is a reconstruction from the study's stated purpose (printed
  pp. 6, 9), and `confidence` is set to `inferred`. In kernel 0.1.0 `confidence` is an
  object-level envelope field, so **one reconstructed field marks the whole Charter
  inferred** — coarser than the truth, and stated here rather than hidden.
* **`pl-twv.approvedBy.date` is inferred.** The description gives no date for FCC OPORD
  19-014. The date used, 2020-04-30, is the Army Deputy Chief of Staff G-8 tasking memo
  named alongside it in the same appendix (printed p. 35). The Plan is marked `inferred`.
  Dropping `approvedBy` was the alternative, and it stops the run at G2.
* **`vva-lbc.accreditationDecision.date` is the audit year, 2021**, not a date GAO prints.
  That object is marked `inferred`.
* **The three Objectives' `provenance` is an inference.** All three name
  `ev-g8-memo-2020-04-30`. Printed p. 12 says the study's *objective* "addresses Army G-8's
  direction"; printed p. 11 lists the three lines of effort without attributing the
  three-way split to the memo. The link is defensible at the level of the study objective
  and is not stated for the split, so all three Objectives carry `confidence: "inferred"`
  and a comment saying which half is inferred.
* **`ev-gao-21-460.published` is 2021-07-15, and the day is not on its cited page.** The
  cover reads only "July 2021"; the exact day comes from the report's landing page, recorded
  in the committed source sidecar. Noted in a comment at the point of use.

Eight of the 43 objects are `confidence: "inferred"` — `ch-twv-2021`, `pl-twv`, `pol-twv`,
`vva-lbc`, `ws-twv` and the three Objectives. Every other object is `explicit`.
* **Schema-forced fields.** `Policy.method` must be one of `mavt / ahp / topsis / pugh`,
  none of which is a capabilities-based assessment; `mavt` is a forced choice.
  `Model.definition.version` is required and is not a slot, so both models carry the
  literal string "unversioned in the public description" where a gap marker belongs.
  `Measure.metric.direction` on `m-lsp-vehicles` is `min`; the description states no
  direction of goodness for a count of vehicles needed to close a gap.
  `Evidence.classification` is required and not a slot, so the three unpublished Army
  documents carry `U` with the caveat "not publicly released; its release status has not
  been verified by this project" rather than a level nobody published.
* **`ws-twv`'s equal weights are ours, not the Army's.** `Plan.steps[].weightSet` is
  required; the description never says the three lines of effort were weighted or
  combined. The WeightSet's own name says so, its provenance is the gap `gap-weights`, and
  it is marked `inferred`. Nothing is computed from it — there are no runs.
* **Ten `InsufficientEvidence` objects**, each with `whereLookedFor`,
  `indicatorsThatWouldResolve` and a human `confirmedBy`, covering: the G-8 memo, FCC OPORD
  19-014, the study's own data files and model documentation, the dataset schemas, the
  evaluation thresholds, the consequences of and indicators against the 90 percent
  readiness assumption, both accreditation records, and the weighting. Recording a gap in
  this schema costs more work than inventing a value would. That is deliberate.
* **`priorityRank` and `deviations` are omitted, not emptied.** Printed p. 11 lists the
  three lines of effort without ranking them, and the description says nothing about
  deviations from the plan. An absent optional field says nothing; `[]` would have
  asserted "followed as written".

---

## 7. `ready` is false, and why

`readiness_report` returns `ready: false` with three blocking rules, and the artefact names
all three rather than hiding them:

* **`silent-omission`**, once per evidence-register entry — no claim cites anything,
  because there are no claims.
* **`objective-run-coverage`**, once per primary objective — no runs.
* **`model-vva`** on `mdl-cba` — the capabilities based assessment has no accreditation
  decision in GAO's description.

One warning: **`vva-verbal`** on `mdl-lbc` / `vva-lbc` — the Logistics Battle Command
accreditation is an interview statement, not a document (printed p. 13).

All four are honest consequences of a study that had not reported. A record in that state
is not a signable one, and the correct output is a refusal with reasons, not a green tick.
All three dimension verdicts read `insufficient_to_conclude`.

---

## 8. What this shows, and what it does not

**It shows:** an agent that never saw Figure 6 transcribed the study from GAO's prose into
the schema — working from a fixture table an unblinded author wrote, so the builder's own
contribution was fidelity to the eight extracted pages and the schema-forced fields, not the
choice of what to record (§1); a deterministic rule set written before that reconstruction
existed assigned a state to each of 21 questions; collapsing those states onto GAO's two
labels agrees with GAO on 18 of 21, against a majority baseline of 0.667 and with
κ = 0.710. Every state, label, justifying object id and firing rule is in
`out/agreement.json`. That the unblinded brief did not fit the fixture to the key is not
asserted — it is evidenced by the brief having predicted 20 of 21 and having been wrong on
exactly the two questions a fitted fixture would have got right (§1).

**It does not show:**

* that the *choice of what to record* was blind. The fixture table came from an unblinded
  brief (§1); only the transcription was blind;
* that our four states equal GAO's labels — Figure 6 publishes **two**, and
  `label_from_state` collapses `1|2|3 → assessed`, `4 → unable_to_assess`;
* that we reproduced the Army's study — we reproduced **GAO's description** of it;
* that the schema would find what GAO found in the Army's actual study documents, which we
  have never seen;
* that the presentation band was independently predicted — see §2;
* that the kernel "reproduces GAO". It shows that the schema's **representation-level**
  reading of GAO's own description agrees with GAO's published labels to the measured
  degree, and disagrees on three named questions for reasons that are stated;
* anything about GAO-23-106549, which publishes no per-question key.

**And on GAO's scope.** In GAO-21-460 GAO states it assessed only the study's design and
portions of its execution (printed p. 35). In the related GAO-23-106549, per footnote 7 and
Appendix I, GAO **did not assess or verify the Army's underlying analytical work**. Neither
is a finding about whether the Army's analysis was right, and nothing in this directory
should be read as one.

---

## Files

| file | what it is | blinded side? |
|---|---|---|
| `study_description.txt` | mechanical extraction of eight printed pages; the builder's only view of the source | input to the blinded side |
| `build.py` | the reconstruction: 21-question fixture, 43 objects, every value with a printed-page locator | **blinded** |
| `ground_truth.yaml` | GAO's Figure 6 labels, transcribed three ways with zero disagreement | unblinded |
| `run.py` | gates, scores, compares; the only module that opens the key | unblinded |
| `out/agreement.json` | every statistic, per-question state, rule and justification | generated |
| `out/report.md` | the same comparison as a table | generated |
| `out/graph/` | the saved store | generated |
| `out/package-full.md` | the rendered decision package | generated |
