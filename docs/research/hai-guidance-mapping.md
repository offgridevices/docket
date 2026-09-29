# Human-AI interaction guidance → the mechanism that satisfies it

*2026-09-06. Ours, not the government's. Design §8.8; plan 04 Task 9.*

Docket is meant to offer "agentic capabilities that produce structured artifacts and
reproducible outputs, while maintaining human control and predictable behavior per
**established human-AI interaction guidance**". The phrase is common in Army problem
statements for this kind of tool and is unattributed: the reference literature that
uses it (SAE 2025-01-0455 and the related GVSETS papers) names no human-AI interaction
*guidance document* — those are the papers that were checked, and the check was for a
named standard, not for the subject matter. So the referent is ours to choose — and
choosing a strong one, then showing the code that enforces it, is worth more than
asserting compliance.

This file is the mapping. One row per clause we can actually read: the clause, the
mechanism, and the test that proves the mechanism is real. Then what the mapping does
**not** prove, then the clauses we do **not** satisfy, stated plainly, then the guidance
that is not on disk at all and is therefore not claimed.

**Rules this file follows.** A clause is cited only if the document is on this machine and
the page was checked against it. Titles, editions and page numbers appear; the private
research library's file paths do not, and nothing from it is copied here beyond the short
quotations below. Where the copy on hand cannot be read (a scanned PDF), no page is
claimed and the row says so. Code is cited by **file and function**, never by line
number: several of these files are under active edit and a line number is a citation with
a shelf life of hours. Tests are cited by node id and all of them pass at the time of
writing.

The unqualified "the test" below means `tests/agent/test_authority_e2e.py`, the end-to-end
authority-boundary test written alongside this file. Rows proved by some other test name
that test instead; rows proved by no test at all say **not proved by test**, which is the
honest reading of "partially satisfied".

---

## The three referents, and why these three

1. **Amershi et al., "Guidelines for Human-AI Interaction," CHI 2019** — the only
   widely-recognised artifact literally carrying that title, validated (18 guidelines
   distilled from 150+ candidate recommendations and tested in a modified heuristic
   evaluation). It is what an HCI-literate reviewer will think of when reading that
   phrase. The 18 guidelines and their one-line definitions are Table 1, PDF p. 3.
2. **The five DoW AI Ethical Principles** — the governance-side referent a DEVCOM reviewer
   expects named. The operative wording is quoted below from the CDAO AI Assurance
   Toolkit's own restatement; the 2019 Defense Innovation Board recommendation on disk is
   the provenance of that wording, not the wording in force. The February 2020 adoption
   memorandum itself is **not** on disk; see "not on disk" below.
3. **NIST AI RMF 1.0 (AI 100-1) and the Generative AI Profile (AI 600-1)** — the risk
   taxonomy that OMB guidance points agencies at, and the one that names our exact failure
   modes: *Confabulation* and *Human-AI Configuration*.

A fourth, Army-specific and directly binding on an Army user, is added below: the Army
Chief Information Officer's **ADS-GOV-AI-024**, 27 June 2024.

---

## A. Amershi et al. 2019 — "Guidelines for Human-AI Interaction"

All quotations from Table 1, PDF p. 3.

| Guideline | The clause | Mechanism | Proved by |
|---|---|---|---|
| **G1** Make clear what the system can do | "Help the user understand what the AI system is capable of doing." | The boundary is a list, not a disposition: `AGENT_FORBIDDEN_TYPES` (`src/docket/objects.py`) is enforced on every write in `Graph._check_agent_authority` (`src/docket/store.py`) and restated to the model itself as the first part of its own system prompt (`src/docket/agent/prompts/authority.md`). Which actor class a write belongs to is derived from the actor id, not taken on the dict's word (`objects.is_agent_actor` / `objects.actor_class_mismatch`), so an id beginning `agent:` is an agent whatever it declares. What the agent can do is what the store lets it do. | `test_a_the_agent_may_not_write_an_evaluation_run`, `test_c_the_agent_may_not_write_a_commitment`, `test_defeat_1_to_4_an_agent_id_declaring_itself_human_is_refused_at_the_write_path` |
| **G2** Make clear how well the system can do what it can do | "Help the user understand how often the AI system may make mistakes." | Every elicited field carries a model-supplied confidence band and a locator into the source text, plus `ingestionProvenance` naming the extractor (`_envelope`, `src/docket/agent/elicit.py`). Computed values carry none of this, because they are not estimates. Accepting a field drops the model's confidence and keeps the provenance (`accept`, `src/docket/agent/review.py`). | `tests/agent/test_review.py::test_accept_drops_the_model_confidence_and_keeps_provenance` — *not proved by the authority test* |
| **G9** Support efficient correction | "Make it easy to edit, refine, or recover when the AI system is wrong." | This is the gate, and it is the reason the gate sits where it does. G1 presents the model — not the answer — for human accept / reject / gap-confirmation before anything is computed (`g1_review`, `src/docket/agent/review.py`); all three actions refuse a non-human actor by name (`_human_only`, same file). Catching a wrong question is cheap; catching a wrong answer is not. | `tests/agent/test_review.py::test_the_human_actions_refuse_an_agent_actor`, `::test_g1_is_refused_before_the_human_acts_and_passes_after` — *not proved by the authority test* |
| **G10** Scope services when in doubt | "Engage in disambiguation or gracefully degrade the AI system's services when uncertain about a user's goals." | Absence is a typed object, not an empty field: a slot the model cannot fill takes a `{"$gap": …}` marker pointing at an `InsufficientEvidence` object, and the validator refuses an empty slot outright (`rule_silence`, `src/docket/kernel/validate.py`). Only a human may sign a gap as real (`Graph._check_agent_authority`; `confirm_gaps`, `src/docket/agent/review.py`). | `tests/agent/test_elicit.py::test_gaps_never_dropped_a_second_entry_sharing_an_owner_is_emitted_unattached`, `tests/agent/test_review.py::test_an_unattached_gap_holds_the_gate_shut_all_the_way_to_the_end` — *not proved by the authority test* |
| **G11** Make clear why the system did what it did | "Enable the user to access an explanation of why the AI system behaved as it did." | Every gate attempt **a human or the kernel makes** — passed or refused — appends a record naming the actor, the time, the policy version and each check's result (`transition`, `src/docket/kernel/lifecycle.py`). An agent's attempt is refused *earlier*, by the store, and therefore leaves no record: `Graph.put` rejects an agent revision touching `lifecycleState` or `transitions` before the gate can write anything, so the attempt never becomes a write. Beyond the gate record: every plan step carries a doctrine citation and a stored `Rationale`, and the whole authorship graph exports as W3C PROV with each actor's type (`_add_agent`, `src/docket/exports/prov.py`). | `test_a_refused_human_attempt_is_written_down_which_is_why_the_agent_s_absence_matters` (the human half) and `test_b_the_agent_may_not_drive_the_human_only_model_approved_edge` (the agent half — nothing written) |
| **G14** Update and adapt cautiously | "Limit disruptive changes when updating and adapting the AI system's behaviors." | The refresh cycle. `check_scope` re-derives staleness from the record (AR 5-11 ¶4-2i(3)'s three-year re-accreditation rule and evidence whose `scopeOfValidity.validUntil` has passed) in `src/docket/kernel/scope.py`; `detect` turns those findings into *proposals* a human files, never edits (`src/docket/agent/refresh_watch.py`). `SUSPECT` and `SUPERSEDED` are kernel-only edges (`KERNEL_ONLY`, `src/docket/kernel/lifecycle.py`). | `tests/agent/test_refresh_watch.py::test_elapsed_accreditation_becomes_an_elapsed_time_proposal`; `test_f_no_agent_ever_moved_the_episode_or_wrote_a_transition` |
| **G16** Convey the consequences of user actions | "Immediately update or convey how user actions will impact future behaviors of the AI system." | The review sheet states, before the click, exactly what each available action will write — including the cases where an action would change nothing (`_record_effect`, surfaced as `recordEffect` by `g1_review`, `src/docket/agent/review.py`). | `tests/agent/test_review.py::test_reject_is_offered_only_where_it_would_do_something`, `::test_the_rejected_measure_note_is_on_the_exclusion_row` — *not proved by the authority test* |
| **G17** Provide global controls | "Allow the user to globally customize what the AI system monitors and how it behaves." | The `Policy` object holds the decision-class parameters the whole gate runs on (aggregation, required bias checks, prohibited exclusion reasons, blocking rules) and is on the forbidden list: the agent is measured against it and may not author it (`AGENT_FORBIDDEN_TYPES`, `src/docket/objects.py`, comment in place). Provider and model are a human-set configuration surface with a policy check at every resolution point (`check_model_policy`, `src/docket/agent/backend.py`). | `test_f_the_log_holds_no_agent_authored_object_of_a_forbidden_type` (Policy is in the audited set) |

**One paragraph on the shape of the claim.** Six of these eighteen guidelines are about
telling the user something; docket's answer in every case is to make the thing structural
rather than to say it in the interface. G1 is a refusal list the store enforces, not a
sentence in an onboarding panel. G9 is a gate that will not open, not an undo button. G11
is a transition record that is written even when the gate says no. This is the strongest
form the mapping can take, and it is also the form that survives someone else reading the
saved record without our UI in front of them.

---

## B. The five DoW AI Ethical Principles

**Which wording, and why.** The operative set is now named the **DoW AI Ethical
Principles** and its wording differs materially from the 2019 recommendation it grew from.
The text quoted below is the CDAO restatement, from the *AI Assurance Toolkit* v4.0.0,
Appendix 2 "Defense AI Guide on Risk (DAGR)", §3 "Key Concepts" — a public web
application, captured on this machine 2026-09-02, not a paginated document, so it is
cited by appendix and section and no page. The adoption memorandum itself is not on disk.
The Defense Innovation Board's 2019 recommendation — *AI Principles: Recommendations on
the Ethical Use of Artificial Intelligence by the Department of Defense*, p. 8 — is the
provenance of the wording, and where the two differ the difference is noted in the row.

| Principle (CDAO restatement) | The clause | Mechanism | Proved by |
|---|---|---|---|
| 1. Responsible | "DoW personnel will exercise appropriate levels of judgment and care while remaining responsible for the development, deployment, and use of AI capabilities." (The 2019 wording also said "and outcomes"; the adopted text does not, so the weaker clause is the one quoted.) | The three human gates. `MODEL_APPROVED`, `PLAN_APPROVED`, `SIGNED` and `VOID` are human-only edges (`HUMAN_ONLY`, checked in `transition`, `src/docket/kernel/lifecycle.py`), and the store refuses an agent revision that touches `lifecycleState` or `transitions` before the gate is even consulted (`Graph._check_agent_authority`, `src/docket/store.py`). A `Commitment` — the signature object — is on the forbidden list. | `test_b_the_agent_may_not_drive_the_human_only_model_approved_edge`, `test_c_the_agent_may_not_write_a_commitment`, `test_f_no_agent_ever_moved_the_episode_or_wrote_a_transition` |
| 2. Equitable | "Deliberate steps must be taken to minimize unintended bias in AI capabilities." (The 2019 wording ran "…to avoid unintended bias in the development and deployment of combat or non-combat AI systems **that would inadvertently cause harm to persons**" — that trailing qualifier is what made this row an analogy, and it is not in the adopted text.) | Bias is checked against the *record*, not the model: `bias_indicators` (`src/docket/kernel/bias.py`) writes typed `Risk` objects for anchoring, confirmation, selection and over-specification patterns, and the governing policy can require named bias checks before a plan is allowed to run. This addresses analytic bias in the study; it is not a fairness audit of the language model. | `tests/kernel/test_bias.py` — *not proved by the authority test; see the caveat below* |
| 3. Traceable | "…including transparent and auditable methodologies, data sources, and design procedure and documentation." | The append-only, hash-chained store: every object revision carries its author and lands in a log entry chained to its predecessor (`Graph.put`, `src/docket/store.py`), verified on load and re-checkable by anyone holding the directory (`rule_log_chain`, `src/docket/kernel/validate.py`). The Decision Package and the PROV, GSN, DMN, MADR and RTVM exports are all pure functions of that store. On top of the chain, `rule_authority` (`src/docket/kernel/validate.py`) re-derives all eight agent write-path rules from the saved directory — every revision, not only the head, and with the predecessor comparisons the revision rules need — so the boundary is checkable by someone holding nothing else. | `test_f_the_hash_chain_still_verifies_in_memory`, `test_f_the_saved_store_reloads_clean_and_re_validates`, `test_the_boundary_is_checkable_from_the_store_alone`, and one `test_defeat_*` per rule |
| 4. Reliable | "DoW AI capabilities will have **explicit, well-defined uses**, and the safety, security, and effectiveness of such capabilities will be subject to testing and assurance **within those defined uses** across their entire lifecycle." | Scope of validity is a stored, checkable property of every piece of evidence and every model, not a policy assertion: `Evidence.scopeOfValidity` (what it was built to answer, its question class, its `intendedUse`, when it lapses) and `Model.vvaRecord`, both read by `check_scope` (`src/docket/kernel/scope.py`), which refuses reuse past purpose and flags accreditation older than three years. | `tests/kernel/test_scope.py::test_lapsed_and_model_use_and_reaccreditation`, `::test_reuse_past_purpose_and_justification` — *not proved by the authority test* |
| 5. Governable | "…the ability to detect and avoid unintended consequences, and the ability to disengage/deactivate deployed systems that demonstrate unintended behavior." | Partial. `VOID` is reachable from every state and is human-only, and `SUSPECT` is the kernel's own detection edge when a record's inputs move. There is no runtime kill switch for the agent process itself; there is a boundary that makes an ungoverned agent write nothing. | `test_f_no_agent_ever_moved_the_episode_or_wrote_a_transition`, `test_blast_radius_void_is_the_one_edge_a_forgery_does_not_shut` — **partial, see below** |

Principle 4 is the single strongest sentence available to describe Docket, and the adopted
wording makes it stronger than the 2019 wording did: "explicit, well-defined **uses**"
maps onto `Evidence.scopeOfValidity.intendedUse` and `Model.intendedUse` more literally
than "domain of use" ever did. The architecture satisfies it *by construction*, because
the scope of validity is a stored property the kernel reads, not a statement in a system
description. It is also the same idea as AR 5-11's intended-use accreditation, which
means the AI-governance clause and the Army M&S regulation are asking for the same object.

**Where the RAI implementing documents sit.** The *Responsible Artificial Intelligence
Strategy and Implementation Pathway* (June 2022) is on disk, but the copy is a scanned
image: only the cover page extracts as text, so **no page pinpoint is claimed from it**.
The CDAO AI Assurance Toolkit (formerly the DoD RAI Toolkit), version 4.0.0, is on disk as
a 2026-09-02 capture of its public pages; its Statements of Concern worksheet (Appendix 1)
is the instrument that would carry a mapping like this one into an actual assessment. It
is a web application, not a paginated document, so it is cited by worksheet name and no
page.

---

## C. NIST AI RMF 1.0 and the Generative AI Profile

| Clause | Where | Mechanism | Proved by |
|---|---|---|---|
| The four functions **GOVERN, MAP, MEASURE, MANAGE** | NIST AI 100-1, AI RMF 1.0, §5 "AI RMF Core", p. 20 | The crosswalk the compliance table would use. GOVERN is the `Policy` object plus the gate definitions; MAP is elicitation and the charter; MEASURE is the deterministic evaluation and flip analysis; MANAGE is the refresh cycle. This is a framing, not an enforcement point, and nothing in the code claims AI RMF conformance. | **not proved by test** — a crosswalk, not a check |
| Risk 2, **Confabulation**: "confidently stated but erroneous or false content…by which users may be misled or deceived" | NIST AI 600-1, risk list p. 4; §2.2 p. 6 | Structural, not behavioural. The agent is not asked not to confabulate; it is removed from the path in which a confabulation could become a *result*. **No language-model output reaches a run or a result** — `EvaluationRun` and `Result` are on the store's forbidden list and an agent may not author one under any circumstances. The solver's *inputs* — `Observation`, `WeightSet` — are a different case, stated exactly below: a number a model proposes is a proposal, and it takes a human at G1 to make it the record's. Separately, a numeral the agent writes into prose must match a value on an object the sentence cites: `check_citations` (`src/docket/kernel/render.py`) is run by `narrate` (`src/docket/agent/narrate.py`) before any draft is stored, and a draft that fails it is discarded rather than repaired. | `test_d_a_fabricated_numeral_is_refused_and_nothing_is_written`; `test_a_the_agent_may_not_write_an_evaluation_run`; `test_defeat_9_an_agent_proposed_number_is_a_proposal_and_is_labelled_as_one` |
| Risk 7, **Human-AI Configuration**: arrangements "which can result in the human inappropriately anthropomorphizing GAI systems or experiencing algorithmic aversion, **automation bias, over-reliance**…" | NIST AI 600-1, risk list p. 4 | Mitigated by where the gate is, not by a warning label. The human is asked to approve the *model of the problem* — the charter, objectives, measures, alternatives, assumptions and gaps — before any number exists to defer to. The sheet separately flags the two model-proposed fields that could move a rating, so over-reliance has a named surface rather than a diffuse one. And the record marks which objects the model wrote, so a reviewer can tell a proposal from a decision. | `test_b_…`, `test_e_the_agent_may_not_dispatch_an_unapproved_plan`; `tests/agent/test_review.py::test_rating_relevant_names_the_citation_the_model_wrote_itself` |

**The confabulation claim, stated exactly, because it is the one a technical reviewer will
test.** *No language-model output reaches a run or a result: the store refuses those types
outright, from the write path and from a saved store alike.* A number a model proposes as
an `Observation` or a `WeightSet` — the solver's two inputs — is a **proposal**. Those two
types are deliberately not on the forbidden list, because forbidding them would forbid a
future elicitation stage from proposing anything numeric at all; what the record
guarantees instead is that the proposal carries the model's name, that the package prints
that name, and that a human accepts it at G1 before the episode leaves `DRAFT`. Today the
question is moot in practice: `agent/elicit.py` produces no `Observation`, `WeightSet`,
`Result` or measure value at all, which is stated in its module docstring and held there
by `tests/agent/test_elicit.py`. The numeric path itself contains no model output.

The narrative stage is the one place model prose reaches the page, and it is the one place
with a kernel check standing in front of it — on the `narrate` path. `check_citations` is
**not** a store rule: `Graph.put` does not call it, so prose written straight into the
store bypasses it. That gap is on the unsatisfied list below rather than hidden here.

---

## D. Army CIO guidance on generative AI — ADS-GOV-AI-024

Memorandum, Department of the Army Chief Information Officer, *Chief Information Officer
Guidance on Generative Artificial Intelligence and Large Language Models*, SAIS-ADS,
27 June 2024. Directly applicable to an Army user of this tool.

| Clause | Where | Mechanism | Proved by |
|---|---|---|---|
| "…these tools must be accompanied by a robust review process which may include the critical thinking skills of human expertise." | ¶3.e, p. 1 | Gate G1 is that review process, and it is mandatory rather than advisory: the episode cannot leave `DRAFT` until a human has accepted the charter's three AR 5-11 fields, every linchpin assumption and every open gap (`CHECKS["MODEL_APPROVED"]`, `src/docket/kernel/lifecycle.py`). | `test_b_the_refusal_is_not_the_edge_rule_wearing_the_authority_rule_s_coat`; `tests/agent/test_review.py::test_g1_is_refused_before_the_human_acts_and_passes_after` |
| "System Users should distrust and verify all outputs prior to use." | ¶5.b(3), p. 3 | Verification is mechanised where it can be: every model-written sentence is checked against the objects it cites before storage, and every model-written field arrives with a locator into the source text so the human verifying it knows where to look. | `test_d_a_fabricated_numeral_is_refused_and_nothing_is_written` |
| "System Users should label any document that was created—in whole or in part—with outputs from Gen AI tools. System Users should apply their best judgment when determining whether to add a citation, based on factors including the importance of transparency for a particular use case." | ¶5.b(4), p. 3 | **Satisfied at the document level.** The rendered Decision Package carries a standing **AI assistance** bullet on its Cover, and a structured `aiAssistance` block in the Machine annex, both computed from the record by `ai_assistance_summary` (`src/docket/kernel/render.py`): the distinct agent actor ids that authored anything the episode reaches, the human gate crossings by gate and actor, whether any agent-authored `EvaluationRun` is reachable, and — when nothing is agent-authored — the explicit line "No AI assistance is recorded in this episode." Underneath it the store labels everything anyway: `createdBy.actorType` is on every object revision and every log entry, and the PROV export renders it as a typed agent (`_add_agent`, `src/docket/exports/prov.py`). The second sentence of the paragraph is the one that makes docket's position defensible rather than deficient — it leaves the citation judgment to the user, and docket hands that user the authorship of every object rather than a blanket disclaimer. | `tests/kernel/test_render.py::test_ai_assistance_label_names_the_agent_and_the_human_gate`, `::test_ai_assistance_label_says_so_explicitly_when_nothing_is_agent_authored` |

---

## What this does not prove

The mapping above is about mechanism. None of it is evidence about the things a reviewer
would most want measured, and nothing written about Docket may let the two blur.

**The current build measures none of these.** The quality of a live model's elicitation inside the
boundary — every agent test in this repository replays a committed recording, so what is
proved is the boundary, not the proposals. Reviewer behaviour at the gate — whether a
human presented with a review sheet reads it, and what they do with a rating-relevant
field they do not understand. And whether the gate changes outcomes — nothing here shows
that a decision made through this record is a better decision than one made without it.
Those are questions for a study with human subjects in it, and no amount of kernel work
answers them.

**What the GAO record does and does not say.** The demonstrations in this repository are
built on published GAO products, and three constraints on reading them hold everywhere,
this document included.

- GAO **did not assess or verify the Army's underlying analytical work** (GAO-23-106549
  footnote 7 and Appendix I). Every finding is a *representation* failure — what the
  report told a reader — not an analysis failure. The Army had no comments on the draft
  and GAO made no recommendations. Nothing in docket may be described as detecting bad
  analysis; it detects a record that does not say what it did.
- The Army's report did **not** lack sensitivity analysis. GAO credited the
  combat-effectiveness section for varying assumptions across the four vehicles (engine
  power, infantry carried). Sensitivity was partially present, not missing, and a claim
  that docket supplies something absent would be false.
- GAO-23-106549 publishes **nine verdicts in prose** (three sections × objectivity /
  validity / reliability) and nine findings, **not** per-question labels. Arranging those
  verdicts as a 3×3 grid is ours, and any per-question reading of that product is ours and
  must be labelled as such. Across the twenty-year practice there are 26 GAO products
  applying the "generally accepted research standards" and 21 true answer keys
  (2006–2024); **GAO-21-460 Figure 6 is the only per-question published key** (14 Assessed
  / 7 Unable to assess).

---

## What docket does not satisfy, or satisfies only partly

Stated plainly, because a mapping table that has no such section is not a mapping, it is
marketing.

1. **There is no per-section AI-assistance attribution inside the narrative body.** The
   document-level label exists (ADS-GOV-AI-024 ¶5.b(4), above): a Cover bullet and a
   machine-readable block, both read from the record. What does not exist is a marker on
   each narrative section saying which of them a model drafted. The authorship is
   recoverable object by object from the store and from the PROV export, so this is a
   presentation gap rather than a record gap — but a reader skimming the prose cannot see
   it without leaving the prose.

2. **Governable is only half met.** There is no runtime disengagement control over the
   agent process — no kill switch, no rate limiter, no circuit breaker on repeated
   refusals. What exists is an authority boundary that makes a misbehaving agent unable to
   write anything consequential, plus a human-only `VOID` edge from every state. That is
   containment, not deactivation, and the two should not be conflated in anything we write.

3. **Twelve of Amershi's eighteen guidelines are unaddressed**, and three of them are real
   gaps rather than inapplicable ones. G3–G8, G12, G13, G15 and G18 concern timing, social
   norms, invocation and dismissal, memory, personalisation, granular feedback and change
   notification. Named individually because an AI-governance reviewer will look for them:
   **G6** ("Mitigate social biases. Ensure the AI system's language and behaviors do not
   reinforce undesirable and unfair stereotypes and biases") is not addressed at all — it
   is the same gap admitted under Equitable, from the HCI side; **G15** (granular feedback)
   and **G18** (notify users about changes) are simply not built. Any description of Docket
   should claim six, not eighteen.

4. **Equitable is answered for the study, not for the model.** `bias_indicators` detects
   analytic bias patterns in the decision record — anchoring on an incumbent, confirmation,
   selection through exclusions, over-specified requirements. Nothing in docket evaluates
   the language model for demographic or representational bias, and nothing should be read
   as claiming it does.

5. **The AI RMF crosswalk is a framing, not a control.** No code checks any AI RMF
   subcategory, no artefact is emitted in an AI RMF format, and a GOVERN/MAP/MEASURE/MANAGE
   table about Docket must be presented as a map of where our mechanisms would sit — not
   as a conformance claim.

6. **The citation check is not enforced at the store boundary.** `check_citations` runs on
   the `narrate` path, before a draft becomes an object. A `Narrative` written straight
   through `Graph.put` is not checked, and the validator has no citation rule. Two related
   limits follow from the same fact, and both are inherent rather than unbuilt: the store
   does not parse a narrative's prose, so an agent-written sentence that contains the JSON
   of an evaluation run, or a number nobody can source, is accepted as the text it is. The
   controls that do cover it are the citation check on the path a narrative is actually
   written by, and G1 — and the reason it is tolerable is that prose is not the numeric
   path: a run written out longhand in a sentence is a string that nothing reads, while the
   sealed objects the kernel and the exports do read cannot be agent-authored at all.

7. **Authorship is a credential, and impersonation is out of scope.** The boundary binds
   the actor a write presents. An actor id beginning `agent:` is treated as an agent
   whatever its `actorType` claims, and a dict whose two halves disagree is refused as
   malformed — so the obvious lie is closed. What is not closed, and cannot be closed by a
   validator, is a process that presents a genuine human's actor dict: to the store that
   is a human. Where it is actually controlled is the API, which never reads an actor from
   a request body and builds both actors server-side from configuration; outside the API
   it is a machine-access question.

8. **Tamper-evident, not tamper-proof, and the qualifier matters.** The log is append-only
   and hash-chained, and `Graph.load` refuses a careless edit outright. A forger who
   re-chains the log and the manifest produces a store that loads clean — every forgery in
   the end-to-end test does. So the chain proves the store is **internally consistent**,
   and proves it has not changed only against a log head retained elsewhere. Signing log
   entries would make it evidence of authorship; that is not Phase I. What survives the
   re-chaining is `rule_authority`, which reads the authorship the forger left in place.

9. **Nothing here measures a live model.** Every agent test in this repository replays a
   committed recording. See "what this does not prove", above.

**One property, not a defect, worth stating before it is discovered on stage.** An
`authority` finding is *store-scoped by design*: it is in `WHOLE_STORE_RULES`, so it
refuses every lifecycle gate but `VOID`, refuses `evaluate()`, and makes a regenerated
`ReadinessReport` not-ready — for every episode in the store, not only the one whose
object was forged. A record whose authorship line cannot be trusted cannot be read at all.
The cost is that an ordinary scoping bug in one study (an `Exclusion` whose `authority.who`
is wrong) shuts the gate in an unrelated study on the same programme; the refusal names
the offending object so it is diagnosable, and the cure is a correcting revision. `VOID`
is exempt because abandoning a record must stay possible precisely when the record cannot
be trusted.

---

## Not on disk — not claimed

These are named because a reviewer may expect them, and each line says what would be
needed before it could be cited. Nothing below is quoted, paraphrased or relied on.

| Document | Why it would matter | What is needed |
|---|---|---|
| The February 2020 Secretary of Defense memorandum adopting the five AI ethical principles | It is the instrument that makes the principles binding | The adopted **wording** is available, via the CDAO AI Assurance Toolkit's restatement, and is what Section B quotes; the memorandum itself is not on disk. Obtain the public memorandum before citing an adoption date or an issuing authority |
| A change to DoDD 3000.09, or any successor, on human-machine teaming outside weapon systems | Would be the natural home for a human-control clause covering decision-support AI | None found; the directive on disk expressly does not apply (below) |
| ISO 9241-210 (human-centred design) and ISO/IEC 42001 (AI management systems) | The international framings a commercial reviewer might use | Both are paywalled; neither is on disk and neither is claimed |
| NIST SP 1270 (bias in AI) | Would support the Equitable row with something more specific than the RMF | Not on disk |
| A named referent for the phrase "established human-AI interaction guidance" | It would settle the question rather than leaving us to choose | Not published. SAE 2025-01-0455 and the related GVSETS papers were checked and name no guidance document, though the human-AI decision-making research literature is cited in at least one recent paper |
| Army AI policy above the CIO memorandum (an AR or DA Pam on AI use) | Would bind more strongly than an ADS memorandum | Not found on disk; AR 5-11 governs models and simulations, not AI interaction |

---

## Documents on disk that do **not** apply

- **DoDD 3000.09, *Autonomy in Weapon Systems*, 25 January 2023.** ¶1.1.b(7), p. 3:
  the directive "does not apply to…Autonomous or semi-autonomous systems that are not
  weapon systems." Docket is a decision-record tool; the directive is out of scope and
  should not be cited as though it governed us. Its ¶1.2.a language about
  "appropriate levels of human judgment over the use of force" is the ancestor of the
  Responsible principle and is worth knowing, but it is not our authority.

---

## One caveat about the ground moving

The *Artificial Intelligence Strategy for the Department of War*, Secretary of War
memorandum, 9 January 2026, p. 5, carries a section headed "Clarifying 'Responsible AI' at
the DoW — Out with Utopian Idealism, In with Hard-Nosed Realism," and directs the CDAO
"to ensure all existing AI policy guidance at the Department aligns with the directives
laid out in this memorandum." The five ethical principles are not rescinded in that text,
but the framing around them is being rewritten, and a 2019 Defense Innovation Board
recommendation is not a safe thing to lean the whole argument on in September 2026 — which
is why Section B quotes the adopted wording instead.

The same page carries two concrete directives that cut *for* this architecture rather than
against it. The Secretary directs the CDAO "to establish benchmarks for model objectivity
as a primary procurement criterion within 90 days," and the Under Secretary for
Acquisition and Sustainment "to incorporate standard 'any lawful use' language into any
DoW contract through which AI services are procured within 180 days." A model-agnostic
design with the model outside the numeric path is the design that survives both: a
benchmark-driven procurement criterion implies the model will be swapped, and a product
whose guarantees do not depend on which model is in the slot is the one that keeps its
guarantees through the swap.

The practical consequence for how Docket is described: lead with the mechanism, not the doctrine.
"Every number in the package is computed by a deterministic solver and every sentence
citing one is checked against the object it cites" is true regardless of which framework
is in force this quarter. "We comply with RAI" is a sentence whose referent may change
before anyone reads it.

---

## Related records in this repository

- [src: docs/decisions/2026-09-04-agent-may-not-create-evaluation-runs.md] — the decision
  the whole boundary rests on.
- `tests/agent/test_authority_e2e.py` — the end-to-end proof, and the source of every
  test node id cited above; its `test_defeat_*` section re-runs the twenty-one defeat
  attempts of the T9 review with each outcome pinned.
- The private research library's doctrine-and-standards report, §C, is where the choice of
  these three referents was first argued; it is not committed to this repository.
