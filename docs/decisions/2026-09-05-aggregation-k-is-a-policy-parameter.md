# 2026-09-05 — `aggregationK` is a policy parameter, and the GAO-comparison policies set it to 21

**Status: pending Shreyash's sign-off.** This entry records a decision the executor took
and measured; it is not settled until he reads it. Everything needed to reverse it is
below, including the measured result under the old value.

**Chosen:** `k` — the number of state-2 questions a dimension may carry and still read
`generally_X` — stays exactly where the design put it, as a **per-Policy field**
(`Policy.aggregationK`, required, read by `readiness_report` and passed to
`dimension_verdicts`). The kernel default is untouched: `DEFAULT_K = 1` in
`src/docket/kernel/readiness.py` still applies to every policy that does not name a value,
and every other policy in the repository — `pol-cbo` in `demos/a_cbo_gcv_2013`, `pol-twv`
in `demos/validation_gao_21_460`, the budget-book policy, the API's default fixture — is
left at 1. The policies that exist **to be compared against a GAO product** set it to 21,
which is the count of applicable questions in the GAO tailorings and therefore means
"`generally_X` holds unless a mapped question reaches state 3 or 4". Today that is one
policy: `pol-kearney` in `demos/control_gao_15_548`. Plan 05 Task 5's `pol-omfv` is
expected to be the second.

The reason is written into the policy's own `name` field, where a reader of the rendered
package meets it, and quotes GAO's own aggregation rule — GAO-23-106549, printed p. 17
(PDF p. 20; verified with `pdftotext -f 20 -l 20 sources/gao-23-106549.pdf`, whose page
footer reads `Page 17`, with PDF 19 → 16 and PDF 21 → 18 confirming the offset):

> For example, we drew conclusions that the report was generally objective when available
> information presented in the report was consistent with our definition of objectivity
> but was missing information that would have addressed the generally accepted research
> standards.

That is a rule about *missing information*, not a count of it. GAO nowhere says "one
missing item is a qualified pass and two is a failure". Encoding a count where GAO
encoded a kind is the substitution this value exists to avoid.

**Over:** three alternatives, all rejected.

1. **Leaving `pol-kearney` at the kernel default `k = 1`.** Measured, and this is the
   whole case. Scoring the GAO-15-548 control at `k = 1` gives
   `{objectivity: not_objective, validity: not_valid, reliability: not_reliable}` — for a
   study GAO examined against these same standards and concluded, printed p. 7, was "both
   reasonable and sound for its intended purposes". At the policy's `k = 21` the same
   record reads `generally_objective` / `generally_valid` / `generally_reliable` with
   every state-2 question named in the qualifier. Pinned as a test:
   `tests/demos/test_control_gao_15_548.py::test_the_kernel_default_k_would_fail_a_study_gao_passed`.
   The three questions that do it are DES-4, PRE-3 and PRE-4 on objectivity — two of
   which (PRE-3, PRE-4) are at 2 only because the study is narrative and has no evaluation
   run, which is a fact about the genre, not about the study's quality.
2. **Changing `DEFAULT_K` in the kernel.** Rejected: it would move every record in the
   repository, including ones nobody re-checked, to make one control pass. The value is
   already a policy field precisely so this is a policy question. A kernel edit would also
   put the change out of sight of the artefact a reviewer reads, whereas
   `Policy.aggregationK` is rendered into the package with the policy's `name` beside it.
3. **A `k: null` "no cap" sentinel.** Rejected in the plan 05 pre-flight (ruling R3) and
   again here: a sentinel adds a code path and hides the number. `21` is a number a
   reviewer can see, argue with and change, and it is the same number as the count of
   applicable questions, which is exactly what "no cap on state-2 questions" means for
   these tailorings.

**Why this is honest.** Three properties, and the third is the one that matters.

* **Nothing is hidden by raising `k`.** When the verdict is `generally_X`,
  `dimension_verdicts` in `src/docket/kernel/standards.py` attaches a qualifier that names
  **every** state-2 question by id and canonical text. Raising `k` moves where the weight
  sits — from a threshold in the aggregate to a sentence in the artefact — it does not
  remove information. When the verdict is `not_X` or `insufficient_to_conclude` the
  qualifier is `None`, so the only case where credit is being reported is the case where
  the reasons are printed.
* **The floor stays in place.** `k` caps state-2 questions only. A single state-3 question
  still forces `not_X`, and a single state-4 question still forces
  `insufficient_to_conclude`, whatever `k` is. Measured on the same control: withdrawing
  the sensitivity credit GAO gave the study takes DES-6 from 2 to 3 and reliability from
  `generally_reliable` to `not_reliable` at `k = 21`
  (`::test_des_6_rests_on_the_sensitivity_analysis_gao_credited`). The parameter cannot
  turn a real failure into a pass.
* **It was chosen from GAO's text before the score, and it is asymmetric in the direction
  that costs us.** The value makes a *positive* control pass. It does not help any negative
  case: plan 05 Task 3's GAO-21-460 reconstruction reaches GAO's "unable to assess" labels
  through state 4, which `k` does not touch, and Task 5's Demo B is expected to fail on
  state-4 questions for the same reason. A dial that only ever produces "generally X" for
  records GAO also passed, and never rescues a record GAO failed, is doing the work the
  aggregation rule is supposed to do.

**Cost if wrong, stated plainly:** a record with many small concerns and no large one can
read `generally_X` where a stricter reader would say `not_X`. The bound is the qualifier
sentence, which lists them all; the exposure is a reader who reads the verdict and not the
sentence. There is a second, smaller cost: `k` now differs between policies in the same
repository, so two records can carry the same states and different verdicts. That is
intended — the GAO-comparison policies are comparing against GAO's rule, and a
decision-support policy for a live Army study need not — but it has to be visible, which
is why the value and its reason are on the Policy object rather than in a constant.

**Would reverse if:** any of these.

1. Shreyash reads the GAO-23-106549 p. 17 passage as a count rather than as a kind. It is
   his call; this entry exists so the call is available to be made.
2. A GAO-comparison case is found where `k = 21` produces `generally_X` and GAO's own
   published verdict for the same material is `not X` or "unable to assess". That would be
   the parameter rescuing a record GAO failed, which is the failure mode it must not have.
   Today no such case exists: the GAO-15-548 control is the only one scored at 21, and
   GAO's verdict for it is a pass.
3. Plan 05 Task 5's Demo B is found to need `k = 21` to reach GAO-23-106549's 3×3 grid *on
   a cell GAO marked* `could not conclude`. Reaching a `generally objective` cell with it
   is the intended use; reaching a `could not conclude` cell with it would mean the value
   is being fitted to the target rather than derived from GAO's rule, and the ledger's own
   test for a fitted reading (2026-09-05, claim-scoped readings) would fail.

**What this decision does not do.** It does not change any rule in
`src/docket/standard/rules.yaml`, any predicate, or `DEFAULT_K`. The only edit it
authorises is the value of `aggregationK` on a policy object inside a demo, together with
the sentence on that policy's `name` explaining it.

**Related, measured while writing this:** `aggregationK` is the only field on
`pol-kearney` that changes the control's result at all. Setting `blockingRules` to Demo
A's four-rule promotion list and `requireAllLinchpinsVaried` to `true` leaves every
per-question state, every dimension verdict, the single blocker and the empty warning list
untouched. `requireAllLinchpinsVaried` is in fact read nowhere in `src/docket` outside the
schema and an API fixture — a separate finding, noted here so it is not lost, and belonging
to whoever owns the policy rules next.

**Implemented in** `demos/control_gao_15_548/build.py` (`pol-kearney`), disclosed in
`demos/control_gao_15_548/README.md` and `demos/control_gao_15_548/expected.yaml`
(`aggregation_k_rationale`); covered by
`tests/demos/test_control_gao_15_548.py::test_the_kernel_default_k_would_fail_a_study_gao_passed`
and `::test_a_passed_study_scores_generally_objective_valid_and_reliable`.

**Provenance line.** GAO-15-548 published no per-question ratings for the study this
parameter is exercised on (printed p. 24) and does not use the
objectivity/validity/reliability frame at all; that frame is Section 234(d)'s by way of
GAO-23-106549. Every per-question state and every dimension verdict `k` aggregates is
ours, not GAO's.
