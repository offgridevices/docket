# Insufficient evidence — how to record a gap

A gap is a reportable state, not a blank. When GAO rates a study against its generally
accepted research standards it keeps a fourth state for exactly this case: its analysts
determined whether the evidence had no, some or significant limitations, "or (4) we could not
determine the extent of limitations or concerns because there was not sufficient information"
(GAO-11-82R, Encl. II, printed pp. 35-36). The catalogue type is `InsufficientEvidence`
(`src/docket/schema/objects.yaml`).

A required field that the request does not support is NOT filled with a plausible value. It is recorded as a gap object with all four parts:
1. `sought` — exactly what was needed. Illustration, not a value: the sample size of the Maneuver Battle Lab soldier touchpoint.
2. `whereLookedFor` — every place in the request you searched (section, page, table). At least one entry, and "the whole document" is not an answer.
3. `whyNotFound` — "not stated", "stated as classified", "referenced but not included", or the specific reason.
4. `indicatorsThatWouldResolve` — what document or statement would close the gap.

Each gap also names its `owner`: the dotted path of the field the gap belongs to.
Illustration, not a value: `charter.consequencesOfErroneousOutput`, `assumption:<n>.evidence`,
`evidence:<n>.pointer`. Two further catalogue fields on `InsufficientEvidence` are not yours:
`impact` is set for you by the pipeline, and `confirmedBy` is a human confirmation recorded at
the review gate — you never confirm a gap.

Mark `confidence: "absent"` on the field's owner. A gap is more work than a value, on purpose: a required field drives fabrication (PhantomFill, arXiv 2607.20492); a gap that is fuller than a guess removes the incentive.
Also tag every extracted value: `explicit` (quoted or directly stated), `inferred` (derived by you — say from what), `absent` (gap).
