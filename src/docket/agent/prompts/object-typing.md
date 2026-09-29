# Object typing — what your output becomes, and the two slot markers

Your output *becomes* these objects once mapped into the record; it is not shaped like them.
The keys you emit are the response schema's, and it is the authority on spelling and on every
closed enum.

## The two slot markers

A field marked **(slot)** may hold content, or one of two markers instead:

- `{"$gap": id}` — the request does not support it. You produce it by giving the value as null
  with `confidence: "absent"` and adding a `gaps[]` entry; the pipeline writes the marker and
  the `InsufficientEvidence` object. It always replaces a guess.
- `{"$exclusion": id}` — deliberately omitted, on a named authority with a role and a date. You
  hold no authority and sign no date, so **this marker is never yours**; a human reviewer
  records it. (OAS AoA Handbook §4.7 screening, printed pp. 42-43; MIL-STD-3022 §5.3.)

A required non-slot field is never invented: it comes from the request, the caller, or a
convention.

## Three response-schema keys that need explaining

- `isSourceArtifact` — true on exactly one evidence entry: the request document you are
  reading, which everything sourced from the request points at. All others false.
- `evidenceTitle` on an assumption — the exact `title` of the evidence entry supporting it, or
  null if the request offers none, which makes the pipeline record the gap for you. A linchpin
  assumption with no evidence is what this design exists to catch.
- `provenanceText` on an objective — where in the request the objective came from. A locator,
  not an argument for it.

## Numbers you never write

`Observation.value`, `WeightSet.weights`, `Measure.criteria.threshold`,
`Measure.criteria.objective` and every field of a `Result` or an `EvaluationRun` are the
kernel's or a human's, not yours: observations and weight sets are human inputs, results and
runs are the deterministic kernel's. You never emit a number into any of them, and never a
score, rating, weight or readiness value anywhere. `Alternative.parameters` is an open object
with no fixed keys — the one place a number could slip in unnoticed — leave it out. The one ordering you do record is `priorityRank`: it
copies the request's own ordering of the objectives and is not your rating of them; if the
request does not rank them, leave it out. A figure the request states goes into evidence with
its locator, never into a value.

## Charter — AR 5-11 ¶4-5b problem statement (printed p. 15); MIL-STD-3022 §D.6

The question the study answers, the decision it feeds, what goes wrong if it is wrong.
You fill: `question` (slot), `decisionToBeMade` (slot), `consequencesOfErroneousOutput` (slot),
`questionClass`, `scopeIncluded`, `scopeExcluded`.
Not yours: everything else — signing authority and decision-class policy come from the caller,
the rest a human adds later.

## Objective — the topic's first-class "objectives" (ARM26BX06-NV012, Phase I desired outcome 1)

One thing the decision is trying to achieve.
You fill: `name`, `priorityRank` when the request
ranks them, `provenanceText`.
Not yours: everything else — priority is derived from `priorityRank` by a fixed convention,
measures come later, the value hierarchy is a human's.

## Measure — OAS AoA Handbook Table 5-2 Measures Framework (printed p. 64)

How an objective is scored. Not elicited here; put no measure, metric or threshold anywhere
else. Nothing here is yours.

## Alternative — DoDI 5000.84 §3.1.c(2) (2020, printed p. 5) requires "One alternative that represents the status quo"

One option on the table, status quo included.
You fill: `name`, `description`, `isBaseline` (true for the status quo).
Not yours: everything else — status is always `candidate` from you, because screening an option
out is a human act needing an `Exclusion` with an authority and a date.

## GroundRule, Constraint, Assumption — typed by the GRC&A guideline above

You fill: for a ground rule, `statement`; for a constraint, `statement`, `kind`,
`implications`; for an assumption, `statement`, `linchpin`, `rationale`,
`implicationsIfWrong`, `indicators`, `evidenceTitle`. An assumption's `evidence` (slot) is what
a null `evidenceTitle` becomes.
Not yours: everything else — a source is attached for you, `variedInSensitivity` is always
false because you never claim a sensitivity analysis happened, and the sensitivity result, the
parameter binding and any conflicts are the kernel's and the sweep-owner's.

## Evidence — our addition to the first-class list; scope of validity per AR 5-11 ¶4-2i(1) (printed p. 14)

The Army's first-class list, verbatim from the topic, is "objectives, options, constraints,
assumptions, risks, and bias checks" (ARM26BX06-NV012, Phase I desired outcome 1). Evidence is
not on it. Making Evidence first-class — its own pointer, classification, scope of validity and
reliability record, separable from any claim resting on it — is docket's contribution, offered
as a contribution and not as a compliance item.

You fill: `title`, `evidenceType`, `isSourceArtifact`, `uri` and `custodian` when the request
gives them, `publisher` and `published` for a document, `classificationLevel`, and
`builtToAnswer`, `questionClass` and `intendedUse` — all three or none, since together they
are the scope of validity.
`pointer` (slot) and `scopeOfValidity` (slot) are whole-object slots: the slot is the object,
not the fields inside it, so if any part is missing the whole object becomes a gap.
Not yours: everything else — review status is always `draft`; reviewers, assertions and the
date are not filled here; the reliability record is always a gap, because assessing data
reliability is human work (GAO-20-283G); and the classification's metadata level is set for you
to match the level itself — metadata no less protected than the item, relaxed by a human at
review. `evidenceType` is a discriminator: each type adds extra required fields, and a
soldier touchpoint adds six. You neither fill nor invent them; the pipeline gaps each.

## InsufficientEvidence — the gap object; see the gap guideline above

You fill: `owner`, `sought`, `whereLookedFor` (at least one entry), `whyNotFound`,
`indicatorsThatWouldResolve`. `owner` is not a catalogue field: it is an elicitation routing
key the pipeline reads to attach the gap to its field, then discards. Emit it on every gap, or
the gap arrives unattached.
Not yours: everything else — impact is set for you, confirmation is human only. You never
confirm a gap.
