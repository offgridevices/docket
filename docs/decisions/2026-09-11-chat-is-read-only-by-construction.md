# The chat is read-only by construction

Date: 2026-09-11. Status: accepted.

## Context

The combined design puts an assistant beside every view, always open, reading the whole
decision. A chat that could also write would be a second authority path into the record —
one that no gate guards, that no provenance mark labels, and that a reader could not tell
apart from a person's own act after the fact. The product's whole claim is that the model
proposes and a person decides; an assistant that could quietly change something would
retract that claim on every screen at once.

"Read-only by policy" was not enough. A rule that lives in a prompt, or in a reviewer's
memory, is a rule that a later change can break without anyone noticing. The property had
to be structural, so that breaking it would mean rewriting code that visibly has no
business being touched.

## Decision

The chat cannot write, because there is nothing in it to write with.

- `src/docket/agent/ask.py` never imports the store's write path. It answers nine intents
  deterministically from exactly the same code the queue, the clock, the readiness report
  and the flip summary already use — the same numbers, never a second computation — and
  every paragraph it returns cites at least one object id.
- `src/docket/api/routes/ask.py` never enters `sessions.writing`. It takes the session
  lock to read, and the only file it appends to is the session's own `chat.jsonl`, which
  is session-local and is never part of the record.
- The model path receives context, not tools. When the configured mode is live and a
  backend answers, a question no intent matches is sent with the gate-one sheet, the
  readiness summary and the clock as context, and an instruction to cite ids. The reply
  passes the renderer's own citation check or it is replaced by the fallback sentence
  with the suggested questions. In recorded mode the fallback answers directly, and any
  backend failure becomes the fallback too.
- The client makes exactly two kinds of request: one for the suggested questions, one to
  ask. A thread lives in memory, one per decision and episode, and switching decisions
  switches the thread.

## Consequences

The chat can be wrong, and it cannot change anything. Every action it offers is a
navigation: an answer's citations open the stored object, and its buttons take a reader
to the view where the act actually lives, where the usual gate and the usual attribution
apply. Nothing the assistant says is ever evidence — the object it cites is.

The cost is that the assistant cannot do a thing for you, however small. It cannot
confirm an absence, tick a check or fill a field, and the round trip through the view is
sometimes tedious. That tedium is the price of the boundary, and it is deliberate.

Threads are not persisted across machines, and a transcript in a session directory is a
convenience for debugging, not a record.

## Where it is enforced

- `tests/api/test_ask.py::test_ask_answers_from_the_record_and_never_writes` — the
  graph's head entry hash and its snapshot hash are captured, every suggested question is
  asked and then one that matches no intent, and both hashes are identical afterwards.
- `tests/api/test_ask.py::test_model_path_with_the_recorded_backend_is_checked_and_writes_nothing`
  — the same proof across the model path, including a reply whose numeral is uncited
  being replaced by the fallback, over ten calls in all.
- `tests/api/test_ask.py::test_recorded_mode_never_resolves_a_backend`.
- `tests/agent/test_ask.py` — the intent router and the nine answers.
- `ui/e2e/chat.spec.ts` — the chips the server names, citations that open the stored
  object, actions that navigate, one thread per decision, and the activity log's own
  count unchanged across an exchange.

## What would reverse it

An explicit decision to give the assistant a write path — which would need its own gate,
its own provenance mark and its own place in the authority diagram before it could be
built, and would supersede this record rather than amend it.
