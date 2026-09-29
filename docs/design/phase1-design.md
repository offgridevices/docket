# Docket — system design

**What this is.** The design the Docket build followed: the principles, the architecture,
the schema, the deterministic kernel, the agent layer, the validation method and the
Decision Package. Source code cites it as `design §N.M`; the section numbers below are
kept stable for that reason, which is why the numbering starts at 2 and skips 3.

**Evidence.** Factual claims trace to a file in `sources/` or to the research notes the
design was written from; pointers are given as `[report §]`. Those research notes live in
the local research library (`library/`, never committed), so a pointer names where the
claim came from rather than a file in this repository.

---

## 0. How to read this

Section 2 is what the research established about the answer key, the OMFV decision and
the design space. Sections 4–10 are the design itself: principles (§4), architecture
(§5), schema (§6), kernel (§7), agent layer (§8), evaluation method and the two
demonstrations (§9), and the output (§10).

If you read one section, read §5 (the three layers) and then §7 (the kernel).

---

## 2. What the research established

Facts that changed between the repo as of 2026-09-02 morning and now.

### 2.1 About the answer key

1. **There are 26 GAO products that apply the "generally accepted research standards";
   21 are true answer keys, 2006–2024.** Six passed, eleven failed, the rest could not
   conclude. GAO-23-106549 is one instance of a twenty-year, stable GAO practice.
   `[gao §1; gao-derived §4]`
2. **GAO-21-460 Figure 6 is a per-question, machine-gradable answer key** — 21 labelled
   binary outcomes (14 Assessed / 7 Unable), independently transcribed twice with zero
   disagreement, cross-checked against the text layer. It is the only per-question
   published key in existence. **Lead the quantitative Phase I claim with it.**
   `[gao §2; gao-derived §2]`
3. **GAO-15-548 is a pass, on the same buyer, the same vehicle family, the same
   congressional-report genre** (A.T. Kearney, Abrams/Bradley industrial base, 2014).
   Positive control. `[gao §10]`
4. **The 21 questions are a tailored subset of a 36-question standard** (14 design / 15
   execution / 7 presentation). 43 distinct questions are named across sources; 36 in
   any single instance. Only 5 of 26 GAO applications used the full published set —
   **tailoring is the norm**, and GAO writes down every exclusion with a rationale.
   `[gao §3; gao-derived §1, §4]`
5. **GAO rates on four states**, not two: no concerns / some / significant / **could not
   determine because insufficient information**. The fourth is the one GAO lands on
   most, and it is not a failure. `[gao §6]`
6. **A pass is not a per-question AND.** GAO passes studies while naming thin questions.
   The aggregation rule must be stated. `[gao-derived §8]`
7. **GAO runs a mandate-element scorecard alongside the standards**, and they diverge.
   `[gao-derived §7]`
8. **The VV&A finding (teardown F5) cannot be expressed in the published 21.** The
   question that asks it (EXE-14) is in the 36 only. `[gao-derived §5]`
9. **The teardown originally covered five of GAO's nine findings**; F3, F7, F8 and F9
   were added and the numbering aligned on 2026-09-05. `[gao-derived §5]`
10. **The criteria are statutory, not GAO's.** §234(d) of the FY22 NDAA named
    "objectivity, validity, and reliability"; it was added in conference with no
    legislative history. `[omfv §(e)4]`

### 2.2 About the OMFV decision

11. The Army's §234 report is not public and never was. Phase I runs on a
    **reconstruction**, and every output says so in one sentence. `[omfv §(a)]`
12. The reconstruction is far richer than assumed: nine characteristics verbatim with
    Army definitions, priority order and stated provenance; **seven of the eleven
    analytical efforts named on a Distribution A Army slide**; four operational
    vignettes; the requirements chain CON → A-CDD → PSPEC public; a dated, public
    instance of a characteristic silently hardening into a numeric requirement
    (Manning, Feb→Dec 2020); a dated priority change (signature management P3→P2).
    `[omfv §(c), (d)]`
13. **The OMFV contract already requires an unclassified RTVM (CDRL A013) and a
    classified RTVM (CDRL A103) from the same public template.** The Army already splits
    claim from classified evidence; nothing keeps the two linked. `[omfv §(d)2c]`
14. **AR 5-11 already mandates the pre-use problem statement (question / decision /
    consequences of error) and re-accreditation on change of intended use.** The gate on
    the model and the scope-of-validity rule are existing Army policy with no
    mechanism. `[omfv final update; doctrine-standards §A1–A2]`
15. The Poland-bridges assumption is walkable end to end in public: rationale (Breaking
    Defense, 6 Feb 2020) → quantified threshold (Weight characteristic, 25 Feb 2020) →
    country assumption → the unevidenced generalisation GAO caught; and ERDC published
    the identical bridge-classification study for Turkey, showing what adequate looks
    like. `[omfv §(d)8, 8a]`
16. **CBO's 2013 GCV alternatives study is a public, quantitative, properly documented
    analysis of the same decision** — four named options, methodology appendix, pivotal
    assumption in a labelled box. `[omfv §(d)10b]`
17. Congress demanded requirements traceability with a funding fence in December 2019,
    in almost this project's own words. Better opening quote than anything in GAO.
    `[omfv §(d)12]`
18. Soldier touchpoints — four of the eleven efforts — have **no Army-specified method,
    sample size, instrument, or analysis standard**; the regulation that names them
    defines nothing. `[touchpoint sub-report §3.1]`
18a. **The Army's own budget books (FY2021–FY2027 R-2 exhibits, all public) supply
    dated, checkable inconsistencies that no mechanism ever reconciled**: the same
    March 2023 book states the OMFV effort's total cost as $1,348M and $1,384M on
    different pages; three irreconcilable windows for the OMFV Analysis of
    Alternatives (FY2019 start; FY2020–21 "completed"; FY2023 "formal execution");
    two Army budget books date the five concept-design awards to July 2021 against
    GAO's September; the two analyses GAO's force-structure findings rest on (TRAC,
    Maneuver Battle Lab) never appear in the program element in seven years; and the
    acronyms ARIES and CAVE are defined as analysis tools in 2020 and as vehicle
    hardware in 2025. `[omfv-rdte §3.3 a, c, d, j, k]`

### 2.3 About the design space

19. **Schema-forced fabrication is real and severe.** Making a JSON field required
    drives fabrication to 100% in 10 of 13 models; an optional "insufficient evidence"
    value rescues only frontier models; open models never take the escape.
    `[doctrine-standards §D3; PhantomFill]`
20. **Deterministic LLM inference is now achievable but only by controlling the serving
    stack down to the kernel.** "LLMs are not reproducible" is false as a flat claim.
    The surviving claim: a model-agnostic product calling a hosted endpoint cannot make,
    verify, or even detect that guarantee. `[doctrine-standards §D1–D2]`
21. **DoW doctrine demands first-class exclusion in three unrelated places** —
    MIL-STD-3022 §5.3 ("shall be retained … 'This section is not applicable'"), the Army
    CBA Guide ("Don't leave out major sections"), the OAS AoA Handbook §4.7 (screening
    reasons, approving authority, and a *prohibited* reason) — and no tool implements it.
    `[doctrine-standards §B5]`
22. **GSN v3's Dialectic Extension already provides `Challenges` and `Defeated`**; the
    Modular Extension makes cross-module evidence import a checkable context claim;
    **PROV has no negative relation at all**. `[doctrine-standards §B1–B2]`
23. **ICD 203 already requires "indicators that, if detected, would alter judgments"** —
    "what flips the decision" as a required element since 2015, plus a controlled
    seven-band uncertainty lexicon. `[doctrine-standards §A6]`
24. "Established human-AI interaction guidance" is unattributed in the problem
    statement and in both incumbent papers. **We get to name it**: Amershi et al. 2019 (the 18
    guidelines) for interaction; DoD RAI principles for governance ("explicit,
    well-defined domain of use"); NIST AI RMF + GenAI Profile for risk (which names
    automation bias and confabulation). `[doctrine-standards §C]`
25. **Two of the repo's five assumed differentiators do not survive.** "Deterministic
    solver, LLM orchestrates" is shipped by Quantellia, Aera, Lumina — keep the
    architecture, drop the novelty claim. "Exclusion of alternatives as a first-class
    object" is occupied by Tyree & Akerman 2005, ISO 42010, van Heesch 2012, MADR, LML —
    convert to a standards-compatibility claim. `[prior-art §15]`
26. OSD told Congress in 2021 that **71.4% of AoA practitioners felt bias affected
    solution selection**, and IDA found the **Ground Combat Vehicle AoA** — OMFV's
    direct predecessor — "biased toward the service position." `[prior-art §11;
    orchestrator-notes]`

---

---

## 4. Design principles

Settled before the build, refined by the research. Each is now anchored to a document the
reviewer already works with.

| # | Principle | Anchor |
|---|---|---|
| P1 | **The agent never sits in the numeric path.** A deterministic kernel computes every number, rating and ranking; the agent elicits, plans, dispatches, narrates. | Nondeterminism literature; Innoslate's LLM-assigned risk scores as the counterexample |
| P2 | **The human gate sits on the model, after elicitation, before computation.** | AR 5-11 ¶4-5b (problem statement precedes M&S use); PhantomFill; Amershi G9 |
| P3 | **Silence is prohibited.** Every expected slot holds content, an Exclusion, or an InsufficientEvidence object. Never an empty field. | MIL-STD-3022 §5.3; CBA Guide p.70; PhantomFill |
| P4 | **Evidence carries its scope of validity, and reuse past scope is an error, not a judgment.** | AR 5-11 ¶4-2i(1); DoD RAI principle 4; GAO-23-106549 finding 1 |
| P5 | **Claim, pointer and classification are separable.** A package is assessable at one level while its evidence sits higher. | CDRL A013/A103; GAO-23-106549 finding F4 |
| P6 | **Readiness is computed against a published, tailored standard with a four-state rating.** | GAO 36/21; GAO-11-82R rubric; GAO-16-820 tailoring |
| P7 | **Doctrine-shaped.** Every schema object maps to a paragraph the Army or DoW already wrote. We give machine form to prose requirements. | §6 crosswalk |
| P8 | **Model-agnostic, open format, open source.** No provider commitment; PRC-origin models avoided; the core is meant to be released as open source. | §5, §8 |
| P9 | **Reproducible by construction.** Same graph + same kernel version + same seed = byte-identical package. | CBA Guide p.68 ("arrive at the same conclusion") |
| P10 | **Honest about what is and is not shown.** Representation vs analysis; reconstruction vs report; inferred vs explicit. | GAO footnote 7; §234(d) tasking gap |

---

## 5. System architecture

### 5.1 The three layers

```
┌──────────────────────────────────────────────────────────────────────────┐
│  AGENT LAYER (LLM, swappable)                                             │
│  elicit → propose plan → dispatch → narrate → watch for refresh          │
│  may create: drafts, plans, evidence attachments, narrative              │
│  may NOT create: numbers, ratings, runs' results, commitments, state     │
├──────────────────────────────────────────────────────────────────────────┤
│  HUMAN GATES                                                              │
│  G1 model approval (before any computation)  ·  G2 plan approval         │
│  G3 package sign-off (commitment)             ·  G4 refresh acceptance   │
├──────────────────────────────────────────────────────────────────────────┤
│  DETERMINISTIC KERNEL (pure, seeded, versioned, no LLM)                   │
│  validate · evaluate · sensitivity/flip · scope-check · refresh-diff ·   │
│  standards-score · mandate-score · render                                 │
├──────────────────────────────────────────────────────────────────────────┤
│  THE GRAPH (the schema instance — the decision system of record)          │
│  typed, append-only, hashed; exports: JSON, PROV, GSN, DMN, MIL-STD-3022  │
└──────────────────────────────────────────────────────────────────────────┘
```

The graph is the only state. The kernel reads the graph and appends; the agent proposes
appends that a human accepts; the gates are graph transitions with recorded policy
checks. No side state (the incumbent's paper names "untracked side state" as the
enterprise failure mode; we take the same position and enforce it the same way).

### 5.2 Data flow for one episode

```
messy request + documents
   │  (agent) structured elicitation, ingestion provenance on every object
   ▼
DRAFT graph  ──►  G1: human reviews/edits the MODEL (question, decision,
   │                   consequences-of-error, scope, objectives, alternatives,
   │                   GRC&A, evidence register incl. InsufficientEvidence)
   ▼
APPROVED model
   │  (agent) proposes an evaluation PLAN from the decision-class policy
   ▼
G2: human approves plan  ──►  (kernel) immutable EvaluationRuns
   │                              evaluate · sensitivity · flip set
   │                              scope-check · standards-score · mandate-score
   ▼
READINESS report  ──►  (agent) drafts narrative strictly from graph objects,
   │                    every sentence cites an object id; kernel rejects
   │                    uncited sentences
   ▼
G3: signer reviews package  ──►  Commitment (conditions, stop rules) ──► SIGNED
   │
   ▼  later: evidence/assumption change, or AR 5-11 trigger fires
REFRESH: kernel marks affected claims SUSPECT, recomputes, produces diff;
         agent drafts "what changed and why"; G4 accepts ──► new episode
```

### 5.3 Program vs episode (the unified representation)

A **DecisionProgram** is an ordered sequence of **DecisionEpisodes** over one Charter.
An episode is one full pass through §5.2. A point-in-time trade study is a program with
one episode. A long-horizon program is many episodes, each triggered by a recorded
RefreshTrigger, each producing a diff against its predecessor. Same schema, same kernel;
the program adds lineage edges (`supersedes`, `refreshedBecause`) and the diff object.
This is how one representation "scales from point-in-time trade studies to long-horizon
program decisions" without two data models.

---

## 6. The schema

The product artifact. A typed, directed, append-only graph. Below: object catalog with
required fields, then the doctrine crosswalk, then serialization and exports.

### 6.1 Object catalog

Notation: `field` required; `field?` optional; `→Type` edge. Every object has `id`
(stable), `createdBy {actorType: human|agent|kernel, actorId}`, `createdAt`,
`ingestionProvenance? {sourceArtifact, locator, extractor, extractedAt}`, `rev`,
`supersedes?`. Every object *slot* on a parent that is empty must hold an `Exclusion`
or `InsufficientEvidence` (P3).

**Charter** — the AR 5-11 ¶4-5b problem statement plus the incumbent-compatible scope.
`question` · `decisionToBeMade` · `consequencesOfErroneousOutput` · `scope {included[],
excluded[]}` · `authority {signer, board, delegations}` · `successCriteria[]` ·
`decisionClassPolicy →Policy` · `mandateElements[] →MandateElement` ·
`hierarchyBinding?`.

**MandateElement** — one thing the tasking authority required the record to contain
(statute section, committee language, study guidance). `text` · `source` ·
`satisfiedBy? →Claim[]` · `status: satisfied|partial|unsatisfied|not-applicable+reason`.
Scored on the separate track GAO uses (§2.1 item 7).

**Objective** — hierarchical value model. `name` · `parent?` · `priority: primary|
secondary` · `measures[] →Measure` · `provenance →Evidence|InsufficientEvidence`
(where the objective came from — "threat analysis, market research, ABCT operational
concept" for OMFV).

**Measure** — one row of the OAS Measures Framework (Table 5-2). `task` · `attribute`
· `measure` · `metric {units, direction, aggregation}` · `criteria {threshold,
objective}` · `conditions[]` · `analysisMethod →Evaluator`.

**Alternative** — `name` · `description` · `parameters{}` · `status: candidate|
screened-out|evaluated|selected|rejected` · `statusReason →Exclusion|Rationale` ·
`baselineFlag` (DoDI 5000.84 §3.1.c requires a status-quo alternative — its absence is
a validation error). Set-based: `optionSet? →OptionSet` with `narrowingEvents[]`.

**GroundRule / Constraint / Assumption** — three types, per OAS §4.9, not one field.
Assumption carries the ICD 203 §D.6.e(3) fields: `statement` · `linchpin: bool` ·
`evidence →Evidence|InsufficientEvidence` · `implicationsIfWrong` ·
`indicatorsThatWouldAlter[]` · `sensitivityResult? →FlipAnalysis` · `variedInSensitivity:
bool` (DES-6). A linchpin assumption with `InsufficientEvidence` is a readiness blocker
by default policy — this is the Poland-bridges object.

**Evidence** — the load-bearing object. `pointer {uri, hash, custodian}` ·
`classification {level, caveats, controlledBy}` — *of the evidence, separate from any
claim that cites it* · `scopeOfValidity {builtToAnswer, conditions[], intendedUse,
accreditedFor?, validUntil?}` · `reviewStatus: draft|reviewed|rejected` + `reviewers[]`
· `reliabilitySteps[] →DataReliabilityStep` (GAO-20-283G; EXE-4/5/6) · `type` with
type-specific required fields:
- `MSStudy`: `model →Model` · `scenarios[]` · `vvaRecord →VVARecord` · `runs[]`.
- `SoldierTouchpoint`: `n` · `selectionRule` · `unit` · `instrument[]` · `dates` ·
  `analysisMethod` · `hsiPlanRef?` — each required precisely because the Army specifies
  none of them (§2.2 item 18); absence becomes a gap object, not an inference.
- `VendorFeedback`, `MarketResearch`, `ThreatAnalysis`, `Document`, `Dataset`,
  `ExpertAssessment` — each with its own minimum fields.
PROV mapping: `prov:Entity`; `scopeOfValidity.validUntil` ↔ `prov:wasInvalidatedBy`.

**Claim** — a statement the package asserts. `text` · `assessableAt {level}` ·
`supportedBy[] →Evidence` · `derivedFrom? →EvaluationRun` · `mandateElements? []`.
Rule: a Claim is *assessable* at level L if every supporting Evidence has
`pointer`+`scopeOfValidity`+`vvaRecord`(if model)+`reviewStatus` visible at L, even if
the evidence *value* is above L. This is the A013/A103 link.

**Model / Evaluator** — `definition {kind: code|lookup|rpc|rubric|simulation,
version, containerDigest?}` · `intendedUse` · `vvaRecord →VVARecord` ·
`qualificationStatus: draft|validated|qualified` · `inputs[]/outputs[] →Measure`
· `validityRegions{}`.

**VVARecord** — MIL-STD-3022 Table I fields: `problemStatement →Charter` ·
`requirementsAndAcceptabilityCriteria` · `assumptionsCapabilitiesLimitationsRisks
{assumptions[], capabilities[], limitations[], risks[]}` (four typed lists, §D.8) ·
`methodology` · `accreditationDecision {authority, date, scope}` · `issues[]` ·
`lessonsLearned?` · `sections[]` each `content|notApplicable+reason` (§5.3).
Refresh predicates (AR 5-11 ¶4-2i) are evaluated over `intendedUse`, `definition.
version`, and `accreditationDecision.date`.

**EvaluationRun** — immutable, sealed. `evaluator →Model@version` · `plan →Plan` ·
`inputsHash` · `parameterBindings{}` · `seed` · `kernelVersion` · `outputs[] →Result`
· `outputHashes[]` · `sealedAt` · `sealedBy: kernel` · `runRecordHash`. Agents cannot
create these; the kernel creates them on a human-approved Plan. PROV `Activity` with
`prov:Plan`.

**Plan** — the evaluation workflow the agent proposes and a human approves (G2).
`steps[] {evaluator, alternatives, measures, sensitivitySweeps, biasChecks}` ·
`policyBasis →Policy` · `approvedBy`. PROV `Plan`; DMN `AuthorityRequirement` binding to
the doctrine paragraph that requires each step.

**FlipAnalysis** — "what flips the decision." `parameter →Assumption|Weight|Measure`
· `currentValue` · `flipThreshold` · `flipDistance` (normalised) · `rankingBefore/After`
· `run →EvaluationRun`. Computed only by the kernel (§7.3).

**Exclusion** — first-class omission. `target: Alternative|Evidence|Study|Section|
Question` · `reasonType: enum {infeasible, dominated, out-of-scope, security-withheld,
data-unavailable, superseded, time-or-resource (PROHIBITED per OAS §4.7),
not-applicable, other}` · `reason` · `authority {who, role, date}` · `evidence? →Evidence`
· `retainedInStructure: true` (GSN Dialectic: drawn with an X, never deleted). A
`time-or-resource` exclusion is a validation error by default policy.

**InsufficientEvidence** — first-class gap. `sought` · `whereLookedFor[]` ·
`whyNotFound` · `confirmedBy {human}` · `impact: blocking|degrading|informational` ·
`indicatorsThatWouldResolve[]`. Required fields make recording a gap *more*
work-complete than inventing a value (PhantomFill). Never an enum value on another
object.

**Risk** — `uncertainty →Uncertainty` · `consequence` · `owner` · `mitigation[] →Action`
· `monitor` · `acceptanceCriteria` (ISO 31000 / incumbent-compatible).

**Uncertainty** — `kind: interval|distribution|scenarioSet` · `spec` ·
`lexiconBand?` (ICD 203 seven-band, one lexicon, mixing forbidden).

**BiasCheck** — typed action producing evidence. `type: anchoring-control|
independent-disconfirming-review|premortem|outside-view|structured-alternative-comparison
|devils-advocate` · `requiredBy →Policy` · `performedBy` · `producedEvidence →Evidence`
· `status`. Also a *computed* bias indicator set from the kernel (§7.6).

**Policy (DecisionClassPolicy)** — readiness rules per decision class: required
objects, required evidence states, required bias checks, standards tailoring
(which of the 36 apply, with reasons), aggregation rule, blocking rules. Versioned;
policy version recorded on every transition.

**StandardsAssessment** — output of the standards scorer. Per applicable question:
`questionId` (36-set) · `applicable: bool` + `tailoringReason` · `rating: 1|2|3|4`
(GAO-11-82R) · `evidence[] →objects that justify the rating` · `dimension[]` (GAO's
13→3 mapping). Plus `dimensionVerdicts {objectivity, validity, reliability}` with the
stated aggregation rule and the "generally X" qualifier text.

**ReadinessReport** — `standardsAssessment` · `mandateScorecard` · `blockers[]` ·
`openGaps[] →InsufficientEvidence` · `openExclusions[]` · `flipSummary` ·
`biasChecksStatus` · `policyVersion`.

**Commitment** — `decision →DecisionEpisode` · `selected →Alternative` · `signer
{identity, role}` · `signedAt` · `conditions[] {text, verifyBy →Action, dueDate}` ·
`stopRules[]` · `packageHash` · `dissent? []` (NASA SE Handbook Table 6.8-1 records
dissent; adopt it). Agents cannot create.

**DecisionEpisode** — `charter` · `lifecycleState: DRAFT|MODEL_APPROVED|PLAN_APPROVED|
EVALUATED|PENDING_SIGNATURE|SIGNED|SUSPECT|SUPERSEDED|VOID` · `transitions[] {from, to,
actor, policyVersion, checksSatisfied[], checksUnsatisfied[]}` · `runs[]` ·
`readiness` · `commitment?`.

**DecisionProgram** — `charter` · `episodes[]` · `refreshTriggers[] →RefreshTrigger` ·
`diffs[] →EpisodeDiff`.

**RefreshTrigger** — `kind: evidence-changed|assumption-changed|intended-use-changed|
artefact-version-changed|elapsed-time|indicator-detected|external-finding` · `source`
· `detectedAt` · `affected[] →Claim|Assumption|Evidence`.

**EpisodeDiff** — `from →Episode` · `to →Episode` · `changed[] {object, field, before,
after, because →RefreshTrigger}` · `judgmentsChanged[]` · `judgmentsConsistent[]` (ICD
203 §D.6.e(7): explain change *or* consistency).

**DecisionPackage** — the rendered artifact (§10). `episode` · `renderings {unclassified,
full}` · `hash` · `kernelVersion` · `graphSnapshotHash`.

### 6.2 Doctrine crosswalk

| Schema object | Gives machine form to | Where |
|---|---|---|
| Charter (question/decision/consequences) | AR 5-11 ¶4-5b problem statement; MIL-STD-3022 §D.6 | doctrine-standards §A1, A3 |
| MandateElement | GAO mandate-element scorecards; NDAA §234(b) elements | gao-derived §7 |
| Measure | OAS AoA Handbook Table 5-2 Measures Framework | doctrine-standards §A7 |
| GroundRule/Constraint/Assumption | OAS §4.9 GRC&A typing; CBA Guide fact/constraint/assumption | §A5, A7 |
| Assumption.linchpin / implicationsIfWrong / indicators | ICD 203 §D.6.e(3) | §A6 |
| Alternative.baselineFlag; sensitivity mandate | DoDI 5000.84 §3.1.c, §4.2.i | §A4 |
| Evidence.scopeOfValidity; refresh predicates | AR 5-11 ¶4-2i; DoD RAI principle 4 | §A2, §C |
| Evidence.classification separate from Claim | CDRL A013 / A103 RTVM split | omfv §(d)2c |
| VVARecord | MIL-STD-3022 Table I, §D.8 | §A3 |
| Exclusion (typed, authority, prohibited reasons) | MIL-STD-3022 §5.3; CBA Guide p.70; OAS §4.7; DoDI 5000.84 §4.2.g | §B5 |
| InsufficientEvidence | GAO rating state 4; PhantomFill | gao §6; §D3 |
| FlipAnalysis | "what flips the decision"; ICD 203 indicators; DoDI 5000.84 §4.2.i; CBA step 7c | — |
| Uncertainty.lexiconBand | ICD 203 §D.6.e(2) | §A6 |
| StandardsAssessment (36, tailored, 4-state) | GAO-06-938 / 16-820 / 18-230 / 11-82R | gao-derived §1 |
| EpisodeDiff | ICD 203 §D.6.e(7) | §A6 |
| Commitment.dissent | NASA SP-2016-6105 Table 6.8-1 | prior-art §11c |
| Decision record shape | ISO 42010 App. A; MADR; ISO 15288 DM-3.2 | prior-art §11c, §15 |

### 6.3 Serialization and exports

- **Canonical:** JSON documents per object, JSON Schema for validation, content-hashed,
  append-only log. Plain files in a directory are a valid store (no database required
  for Phase I). A graph view is derived.
- **Exports** (all from the same graph, all deterministic):
  - **PROV-JSON / PROV-O** — runs as Activities with Plans, evidence as Entities,
    actors as Agents, package as a Bundle; `wasInvalidatedBy` for lapsed scope.
  - **GSN v3 (with Dialectic and Modular extensions)** — Claims as Goals, Evidence as
    Solutions, Assumptions/Context nodes, Exclusions as `Defeated` elements with
    `Challenges`, cross-module evidence as away-goals with context contracts.
  - **DMN 1.5** — the Plan's steps as decisions with `AuthorityRequirement` edges to
    the doctrine paragraph that requires them.
  - **MIL-STD-3022 Appendix templates** — VVARecord rendered into the mandatory
    document sections, "This section is not applicable" retained.
  - **MADR / ISO 42010 decision record** — one-page compatibility rendering.
  - **RTVM-style traceability matrix** — unclassified and full renderings from the
    same claim→evidence edges (the A013/A103 demonstration).

### 6.4 What is deliberately not in the schema (YAGNI for Phase I)

Enterprise RBAC and access-policy inheritance beyond a classification level per object;
PLM/MBSE adapters beyond a stable-URI external reference; multi-program cross-graph
reuse; a UI beyond what the demos need. All are later work. The incumbent's paper covers
them well; we reference, not rebuild.

---

## 7. The deterministic kernel

Pure functions over the graph. No network, no LLM, no wall clock in the numeric path.
Versioned; every output records `kernelVersion` and `seed`. Implemented in Python
(uv-managed) as a library with a CLI; every function is property-tested for
determinism (same input → identical bytes) in CI.

### 7.1 Validator (structural + semantic readiness)

Input: graph, Policy. Output: list of `{rule, severity, objects}`.
- Structural: JSON Schema per object; referential integrity; append-only invariants;
  hash chain.
- P3 silence check: every required slot on Charter / Objective / Alternative / Evidence
  holds content, an Exclusion, or an InsufficientEvidence.
- Policy rules: baseline alternative present; every primary Objective has ≥1 Measure and
  ≥1 EvaluationRun covering it; every linchpin Assumption has Evidence or a blocking
  InsufficientEvidence; every Model has a VVARecord with an accreditation decision
  whose scope includes the Charter question; required BiasChecks present with reviewed
  Evidence; no `time-or-resource` Exclusion; no mixed ICD 203 lexicon; every Claim in
  the package has ≥1 supporting object.
- Output feeds the ReadinessReport blockers list. Transitions are refused while
  blocking rules fail; the refusal record is appended to the episode.

### 7.2 Evaluation engine

Default method: **multi-attribute value (MAVT) with swing weights** (Parnell/Kirkwood
lineage; the Department's decision-analysis mainstream), value functions per Measure, additive
aggregation, with alternatives scored per Measure from Evidence-backed results.
Pluggable: AHP available with rank-reversal warning surfaced as a Risk; TOPSIS/PROMETHEE
as alternates; Pugh for screening. The method is a Policy choice, recorded, and the
choice itself is a Claim with rationale.

Uncertainty: intervals propagate by interval arithmetic; distributions by Monte Carlo
with a fixed seed and recorded sample count; scenario sets enumerate. Results carry the
Uncertainty object they inherited.

### 7.3 Sensitivity and flip analysis

For each Assumption, weight, and Measure input marked `variedInSensitivity` (Policy can
require all linchpins):
1. One-at-a-time sweep across the parameter's plausible range (from its Uncertainty
   object; default ±range if absent — recorded as an assumption of the analysis).
2. Find the threshold at which the top-ranked Alternative changes (bisection on a
   monotone response, grid otherwise). Record `flipThreshold`, `flipDistance` =
   |threshold − current| / range.
3. Weight-space: sample the weight simplex (seeded), report the fraction of the simplex
   in which each Alternative is top — a robustness measure in the RDM tradition.
4. Rank the FlipAnalyses by `flipDistance`; the shortest are "what flips the decision."
   Linchpin Assumptions with short flip distance *and* InsufficientEvidence are surfaced
   first in the ReadinessReport.
Output is a FlipAnalysis per parameter plus a `flipSummary`. This is "clear 'what flips the
decision' logic," implemented as arithmetic, not narrative.

### 7.4 Scope-of-validity checker

For every Claim→Evidence edge and every Plan step→Model use:
- `evidence.scopeOfValidity.builtToAnswer` vs `charter.question` / the Objective the
  claim serves: a controlled-vocabulary match on question class (e.g. *desired
  characteristics* vs *force structure* vs *combat effectiveness*), with an explicit
  `reuseJustification` object required when they differ. No justification → error
  object `ReusePastPurpose` (this is GAO-23-106549 finding 1, detected mechanically).
- `conditions[]` vs the episode's scenario set: mismatch → warning.
- `validUntil` / accreditation date vs now: lapsed → `SUSPECT`.
- `classification.level` vs `claim.assessableAt`: if evidence is above the claim's
  level, the claim is assessable only if the evidence *metadata* (pointer, scope,
  VV&A, review) is at or below the claim level. Otherwise `NotAssessableAtLevel`.
- Model `intendedUse` vs this use → AR 5-11 ¶4-2i(1) re-accreditation flag.

### 7.5 Standards scorer

Input: graph, Policy tailoring (which of the 36 apply, with reasons). Output:
StandardsAssessment.
- Each of the 36 questions has a **scoring rule**: a deterministic predicate over graph
  objects that yields state 1/2/3/4 with the justifying objects. Examples:
  - DES-1 (design clear): Charter complete and Plan approved → 1; Plan missing steps →
    2; no Plan → 4.
  - DES-6 (assumptions varied for sensitivity): all linchpins have FlipAnalysis → 1; some
    → 2; none but assumptions listed → 3; assumptions not listed → 4.
  - EXE-3 (models appropriate for purpose): every Model use passes the scope checker
    and has accreditation covering intended use → 1; ReusePastPurpose present → 3;
    no VVARecord → 4.
    *Superseded 2026-09-05 by `docs/decisions/2026-09-05-exe-3-model-use-and-pre-4-failable.md`
    — a model question-class mismatch is `ModelUsePastPurpose`; EXE-3 keys on model use,
    and a `ReusePastPurpose` on a Document belongs to EXE-4, not here.*
  - EXE-5 (data reliability): every Evidence has ≥1 DataReliabilityStep → 1; some → 2;
    none → 4.
  - EXE-8 (models described adequately): VVARecord sections complete → 1; sections
    marked N/A with reason → 2; missing → 4.
  - EXE-14 (VV&A report signed, in the 36 only): accreditationDecision present with
    authority and date → 1; verbal/undated → 3; absent → 4.
  - PRE-2 (well-documented): package renders every mandatory section with content or
    typed exclusion → 1; any silent slot → 4.
  Rules are data (YAML), versioned, and cite the GAO-16-820 cluster definition they
  operationalise. Phase I writes rules for the 21 first, the remaining 15 second.
- **Dimension verdicts** use GAO's own 13→3 mapping and a stated rule: a dimension is
  *generally X* if no mapped question is state 3 and at most k are state 2 (k a policy
  parameter, default 1), *insufficient to conclude* if any mapped question is state 4,
  else *not X*. The "generally objective … but missing information" qualifier text is
  emitted verbatim when state-2 questions exist, matching GAO-23-106549 p.17.
- **Applicability is scored too**: an inapplicable question must carry a
  `tailoringReason`; an unreasoned exclusion is itself a finding.

### 7.6 Computed bias indicators

Not a replacement for BiasCheck actions; a set of structural signals the scorer emits
as Risks:
- Anchoring: the selected Alternative was the first entered / the baseline, and
  flipDistance on ≥1 linchpin is small.
- Confirmation: Evidence supporting the selected Alternative is `reviewed` at a higher
  rate than Evidence supporting others (GAO's "perceived bias in selection of analyses").
- Selection: Evidence objects with `status: excluded` and reason `other`/missing.
- Over-specification (GAO's 2025–26 XM30 critique): fraction of Measures with hard
  thresholds vs objectives-level criteria.
Each indicator is a Risk with an owner, never a verdict.

### 7.7 Refresh engine

On a RefreshTrigger: compute the affected set by graph reachability from the changed
object; mark affected Claims and Runs `SUSPECT`; re-run the affected Plan steps into a
new episode; produce the EpisodeDiff with `judgmentsChanged` and `judgmentsConsistent`;
evaluate the AR 5-11 predicates for every Model. The prior episode is retained
unchanged (`SUPERSEDED`).

### 7.8 Renderer

Graph snapshot → DecisionPackage (Markdown/HTML/PDF) in the fixed section order of
§10, two renderings (unclassified / full), byte-identical for the same snapshot, kernel
version and seed. Every sentence in the narrative carries an object-id citation; the
renderer refuses uncited sentences.

---

## 8. The agent layer

Model-agnostic (any instruction-following LLM with tool use; provider set by
configuration; PRC-origin models excluded by policy). The agent has exactly five
capabilities, all of which produce *proposals* into the graph with ingestion
provenance, and none of which produce a number that reaches the package.

### 8.1 Stage E — structured elicitation

Input: the messy request (memo, slide deck, prior study, emails) and the Policy for the
decision class. Output: DRAFT objects.
- Grammar-constrained decoding against the object JSON Schemas (subword-aligned; the
  degradation Tam et al. measure is an implementation artefact, per Beurer-Kellner).
- **Doctrinal definitions are the annotation guidelines** (GoLLIE): the AR 5-11 ¶4-5b
  wording, the OAS GRC&A distinctions, the CBA Guide fact/constraint/assumption
  definitions, the ICD 203 assumption fields are in the prompt verbatim, so the model
  types objects the way the Army does.
- **No required scalar field lacks an escape into InsufficientEvidence**, and the
  escape is a full object with its own required fields (PhantomFill). Elicitation
  prompts ask "where did you look and what did you not find" for every gap.
- Every extracted object records `ingestionProvenance` (source, locator, extractor
  model+version, timestamp) — the incumbent's R13, which we adopt.
- Confidence: the agent annotates each extraction `explicit|inferred|absent`; the
  kernel converts `inferred` linchpins into review flags for G1.

### 8.2 Gate G1 — approval of the model

The reviewer sees the Charter, objectives, alternatives, GRC&A, evidence register, gaps,
and the agent's explanation of each extraction (Amershi G11). They edit, accept, or
reject objects. **Nothing is computed until G1 passes.** The gate's policy check
requires: Charter's three AR 5-11 fields present and human-authored or human-accepted;
no unreviewed linchpin; every gap object confirmed by a human. This is P2, and it is
where invented inputs die.

### 8.3 Stage P — plan proposal

The agent proposes a Plan from the Policy: which evaluators cover which objectives,
which parameters are swept, which bias checks are required, with a DMN
AuthorityRequirement citation for each step. Gate G2 approves. The agent may not
execute.

### 8.4 Stage X — dispatch and read-back

The agent invokes the kernel with the approved Plan; the kernel creates immutable
EvaluationRuns. The agent reads results *as objects* and may summarise them, but every
summary sentence must cite the run and result ids, and the renderer enforces it.

### 8.5 Stage N — narrative assembly

The agent drafts the prose sections of the DecisionPackage strictly from graph objects.
Constraint: one object citation per sentence minimum; no numbers except those copied
from Result objects (the renderer diff-checks numerals against cited results). Tone and
structure follow the CBA Guide / OAS report conventions the reviewers know.

### 8.6 Stage R — refresh watch

Given a change (new evidence, a changed assumption, an indicator detected, an elapsed
accreditation), the agent files a RefreshTrigger, the kernel computes the diff, and the
agent drafts the "what changed and why" narrative per ICD 203 §D.6.e(7). Gate G4
accepts.

### 8.7 Authority boundary (stricter than the incumbent's)

| May | May not |
|---|---|
| Create DRAFT objects with provenance | Create EvaluationRuns or Results |
| Propose Plans | Approve Plans |
| Attach Evidence pointers | Set reviewStatus |
| Draft narrative citing objects | Emit an uncited sentence or an uncited number |
| File RefreshTriggers | Advance lifecycle state or create Commitments |

The incumbent's boundary allows agents to *create Evaluation Runs* (their §5.4); ours
does not. That single line is the reproducibility argument, and it is checkable.

### 8.8 Human-AI interaction guidance mapping

| Amershi 2019 | Where it lives |
|---|---|
| G1 what the system can do · G2 how well | The agent's role statement in the UI and in every package: "elicited by agent, computed by kernel v, approved by name" |
| G9 support efficient correction | G1 gate editing; object-level accept/reject |
| G10 scope services when in doubt | InsufficientEvidence as the default under uncertainty |
| G11 make clear why | Provenance and citation on every object and sentence |
| G14 update cautiously | Refresh produces a diff into a *new* episode; nothing is rewritten |
| G16 convey consequences · G17 global controls | Charter `consequencesOfErroneousOutput`; policy version and kill switch |

DoD RAI: Responsible (gates), Traceable (package), Reliable ("explicit, well-defined
domain of use" = scopeOfValidity), Governable (agent boundary). NIST AI 600-1 risks
Confabulation and Human-AI Configuration (automation bias) are named as the risks the
architecture mitigates by construction. `[doctrine-standards §C]`

---

## 9. Evaluation methodology and the two demonstrations

### 9.1 Ground truth

| Key | Use | What it gives |
|---|---|---|
| **GAO-21-460 Fig. 6** (Army TWV study, 2021) | Primary quantitative | 21 per-question labels (14 Assessed / 7 Unable), verified twice |
| **GAO-23-106549** (OMFV, 2023) | Primary narrative + demo B | 9 section×dimension verdicts; 8 discrete findings with quotes; per-question layer *inferred* (say so) |
| **GAO-15-548** (Kearney industrial base, 2015) | Positive control | A pass, same buyer and vehicle family, reconstructed from GAO's description |
| GAO-15-457R (RAND airlift) · GAO-16-820 (MHS) · GAO-18-230 | Secondary | N/A flags, an 18-of-36 tailoring, a per-standard include/exclude table |

### 9.2 Procedure

1. **Reconstruct** each study's decision record from public sources into the schema
   (agent elicitation + human G1), with every object carrying ingestion provenance to a
   file in `sources/`. Record every InsufficientEvidence honestly — the reconstruction's
   own gaps are part of the result.
2. **Score** with the standards scorer under the tailoring GAO used for that report.
3. **Compare** per question: agreement with GAO's label (GAO-21-460: Assessed ↔ state
   1, 2 **or 3**, Unable ↔ state 4 — *corrected 2026-09-05* to match the implemented
   `label_from_state` in `src/docket/eval/agreement.py`, which collapses `1|2|3 →
   assessed`); report raw agreement and Cohen's κ; precision/recall on
   "Unable." For GAO-23-106549: agreement on the 9 verdict cells and detection of each
   of the nine findings by the intended mechanism (table below).
4. **Human reconciliation** mirroring GAO's own protocol: two readers score
   independently, then reconcile; the kernel's ratings are the third reader. Report
   inter-rater agreement. `[gao §7]`
5. **Ablate**: re-run with the scope checker off, with Exclusion objects removed, with
   InsufficientEvidence collapsed to nulls. Show which findings are lost. This is the
   evidence that the objects matter, not just the checklist.

### 9.3 Finding-detection matrix (GAO-23-106549)

| GAO finding | Mechanism that detects it | Object |
|---|---|---|
| F1 evidence reused past purpose (TRAC/MBL → force structure) | Scope checker `ReusePastPurpose` | Evidence.scopeOfValidity |
| F2 second TRAC study silently excluded | Validator: study present in timeline, absent from package, no Exclusion → silence error | Exclusion |
| F3 study selection undescribed (3 additional studies) | Exclusion/inclusion reason missing on Evidence set → selection-bias Risk | Exclusion, §7.6 |
| F4 metrics withheld for security | Claim assessable at U with Evidence metadata; value classified | Claim / Evidence.classification |
| F5 VV&A asserted verbally, not in report | EXE-14 rule: no signed accreditation → state 3/4 | VVARecord |
| F6 Poland bridges assumption unevidenced | Linchpin + InsufficientEvidence + short flipDistance | Assumption |
| F7 methodology of 11 efforts not described | EXE-8 / PRE-2 rules on VVARecord and Evidence type fields (touchpoint N, instrument…) | Evidence type fields |
| F8 data-reliability steps not described | EXE-5 rule: DataReliabilityStep absent → state 4 | DataReliabilityStep |
| F9 force structure / operational concepts undefined | DES-2/3 rules: Charter scope terms without definition objects | Charter |

### 9.4 Demonstration A — point-in-time trade study

**Case: CBO, *The Army's Ground Combat Vehicle Program and Alternatives* (April 2013).**
Public, quantitative, four named options (GCV, Namer, upgraded Bradley, Puma, cancel),
a methodology appendix, and its pivotal assumption isolated in a labelled box (the
nine-dismount squad). The kernel reproduces CBO's comparison from CBO's published
inputs; the flip analysis shows the nine-dismount assumption's flip distance; the
package renders CBO's structure as a populated schema. This proves the numeric path
end to end on real public numbers, and it is the same Bradley-replacement decision as
OMFV, one generation earlier. `[omfv §(d)10b]`

Fallback if CBO's inputs prove insufficient: the GAO-15-548 Kearney case as a
qualitative point study.

### 9.5 Demonstration B — long-horizon program with refresh cycles

**Case: the OMFV requirements decision program, 2019–2023.** Episodes:
1. Feb 2020 — nine characteristics published (CON), priority-ordered, provenance stated.
2. Dec 2020 — updated CON: Survivability narrowed, **Manning hardened to numeric
   constraints** (a public, dated refresh with a diff).
3. 2021 — Phase 2 analytical efforts (seven named on the Army timeline; four
   touchpoints; two TRAC studies — one excluded).
4. Mar 2023 — §234 report (reconstructed); **GAO grading as an external
   RefreshTrigger**.
5. Jun 2023 — downselect; later XM30 requirement-priority changes (signature management
   P3→P2) as further refresh events.

Each episode is scored; the diffs show what changed and why; the readiness report at
episode 4 is compared to GAO's verdicts; the Poland-bridges chain is the worked
example. The positive control (GAO-15-548) is run through the same pipeline and should
score high — showing the scorer is not a hammer that sees only nails.

**Inconsistency-detection sub-demo (from the budget books).** Ingest the seven annual
R-2 exhibits as dated Evidence objects and let the validator surface: the same-document
cost contradiction ($1,348M vs $1,384M, March 2023); the three AoA windows; the
July-vs-September 2021 award date (now two Army budget books plus five award notices
against GAO); the A-CDD quarter carried wrong for four consecutive years; and the
ARIES/CAVE identity change. These are five checkable, public, dated facts that a
typed record with stable identifiers would have caught on entry, and a reviewer can
verify each in seconds from the cited pages. `[omfv-rdte §3.3]`

### 9.6 What Phase I proves, and what it does not

Proves: the schema surfaces the gaps an outside referee found, mechanically, with a
stated agreement rate; the numeric path is reproducible (byte-identical re-runs in CI);
the agent stays out of numbers; refresh produces auditable diffs; the same
representation serves one episode and many.

Does not prove: that the Army's analysis was right or wrong (GAO did not either);
anything about the classified metrics; per-question GAO-23-106549 labels (inferred);
cycle-time or rework effects (that is later work, on real cases).

---

## 10. The output: the Decision Package

Fixed section order, every section with content or a typed Exclusion / gap, two
renderings from one graph.

1. **Cover** — decision id, episode, program, kernel version, graph hash, policy
   version, signer block.
2. **Problem statement** — question · decision to be made · consequences of erroneous
   output · scope (in/out) · authority. (AR 5-11 ¶4-5b)
3. **Mandate elements** — what was required to be addressed and where each is
   addressed (scorecard).
4. **Objectives and measures** — hierarchy with provenance; Measures Framework table.
5. **Alternatives** — evaluated, selected, and **screened-out with reason type,
   authority, date** (the exclusions are printed, not footnoted).
6. **Ground rules, constraints, assumptions** — three lists; linchpins flagged; each
   assumption with evidence or gap, implications if wrong, indicators that would alter.
7. **Evidence register** — every item: pointer, type, classification, scope of
   validity, VV&A / accreditation status, review status, reliability steps.
   *Unclassified rendering shows this metadata for classified items; values omitted.*
8. **Evaluation results** — per method, with uncertainty; run ids and hashes.
9. **What flips the decision** — ranked flip analyses; weight-space robustness.
10. **Bias checks** — required, performed, evidence produced; computed indicators as
    risks.
11. **Readiness** — per-question ratings on the tailored standard with justification
    objects; dimension verdicts with the stated rule; blockers; open gaps; open
    exclusions.
12. **Risks** — with owners, mitigations, monitors.
13. **Refresh log** — triggers, diffs, what changed and what stayed consistent.
14. **Commitment** — selected alternative, conditions with due dates and verifying
    actions, stop rules, dissent, signatures, package hash.
15. **Traceability matrix** — claims × evidence, unclassified and full renderings (the
    A013/A103 demonstration).
16. **Machine annex** — graph snapshot, PROV bundle, GSN export, run manifests.
