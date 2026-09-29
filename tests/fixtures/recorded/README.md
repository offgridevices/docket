# Recorded backend fixtures

This directory holds the JSON files `RecordedBackend` reads from. Each file maps
`recording_key(system, user, schema)` to `{"response": ..., "note": ...}`. The key is a
SHA-256 hash over the system prompt, the user prompt, and the canonical form of the JSON
schema only — nothing else. In particular, `now` and `seed` never appear in a prompt, so
a recording is date-stable: replaying it next year produces the same key it did today,
and a fixture does not rot on the clock.

**Responses are hand-authored plausible model outputs.** They exist to exercise the
mapping code, the schema validation, and the authority boundary that sits downstream of
a backend — not to measure a model. Live-model output quality is not measured anywhere
in the Phase I test suite, and no claim about live-model quality belongs in the proposal
on the strength of these fixtures.

**[ruling R9]** `RecordedBackend` is the only backend any test in this repository may
construct (a guard test enforces this — see `tests/agent/test_backend.py::
test_only_this_module_constructs_a_live_backend`). Keep one file per prompt→response
case: two cases that share a section and a context pack will hash to the same key and
cannot coexist in one file. Negative tests (a validation failure that should exhaust
retries, or a narration that should fail citation-checking) need a recorded response for
**every** retry prompt in the sequence, because each retry rewrites the user prompt with
the validation errors appended and therefore produces a new key. If a fixture is missing
a key for one of those retries, the test will fail with `RecordingMissing`, not with the
error it was meant to demonstrate.

**[ruling R10]** Fixtures named `narrate*.json` are coupled to Demo A's *computed*
values (results, flip thresholds, and similar numbers that come out of the kernel, not
out of a source document). If Demo A's inputs or the kernel change, those computed
values change too, and these fixtures will start failing as `RecordingMissing` rather
than as a meaningful test failure. Re-record them with
`uv run python -m docket.agent.record <path-to-recording.json>` (see Task 8) and read the
values back out of the graph — never hand-type a number into a recorded response.

**[ruling R2]** No committed fixture, default, or doc in this repository may name a
denylisted (PRC-origin) model — a test enforces this
(`test_no_committed_fixture_default_or_doc_names_a_denylisted_model`). When a fixture
needs a model name at all (for example, in provenance metadata being tested), prefer
`muse-glimmer:30b-mlx` or `gemma4:e4b`.

**[ruling N3]** `default.json` (an empty `{}`) is committed so `DEFAULT_RECORDING`
resolves to a real, constructible fixture out of the box; it holds no recordings, so any
actual lookup against it still raises `RecordingMissing`, naming the key that's missing.

## Conventions elicitation applies (conventions, not findings) — [ruling R16]

`src/docket/agent/elicit.py` maps a model's elicitation response onto DRAFT graph objects.
Six of its mappings are conventions the pipeline applies, not anything the model asserted
or a finding about the source document. They are recorded here, and mirrored in
`elicit.py`'s module docstring, so a reader of `elicit.json` (or any other elicitation
fixture) does not mistake a convention for a claim in the response itself:

- `priorityRank <= 3 → priority: "primary"`, else `"secondary"`. The model chooses the
  rank (it is one of the two model-authored values that can move a rating — the other is
  `Alternative.baselineFlag`; see the G1 sheet's rating-relevant section); the convention
  that turns a rank into a priority label is docket's, and a human confirms it at G1.
- `Alternative.status = "candidate"` always — an agent may not screen anything out.
- `Assumption.variedInSensitivity = false` always — the model never claims a sensitivity
  analysis happened.
- `Evidence.classification.metadataLevel` is set equal to `classification.level` — the
  conservative reading ("the metadata is no less protected than the item"); a human relaxes
  it at G1.
- `InsufficientEvidence.impact = "degrading"` for every gap `elicit()` creates, whether
  matched from the model's own `gaps[]` entry or synthesised because a required field had
  neither a value nor a gap entry; a human raises it to `"blocking"` at G1 if warranted.
- A synthesised source-artefact `Evidence` (only when the model's response has no
  `isSourceArtifact: true` item) is typed `source_evidence_type`, a caller kwarg defaulting
  to `"Document"` — a documented default, never an invented literal [ruling I3].
