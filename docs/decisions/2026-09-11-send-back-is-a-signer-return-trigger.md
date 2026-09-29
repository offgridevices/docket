# Send back is a signer-return trigger

Date: 2026-09-11. Status: accepted.

## Context

A signer who reads a package and will not sign it has to be able to hand it back. The
obvious ways of building that are all wrong for this record. Reopening the episode would
rewrite history — the package that was read would stop being the package the record says
was read. A status field on the episode would carry the fact but not the reason, the name
or the moment. A queue entry held outside the record would be a to-do list, and this
product's whole argument is that there is no to-do list: what needs a person is derived
from the record and drains as the record changes.

The record already had an object for "a reason to look again", and a human path for
turning one into a new episode. Send back needed to be that, not something new.

## Decision

`src/docket/kernel/refresh.py::signer_return` files a human-authored refresh trigger of
kind `signer-return`, whose affected object is the episode itself and whose description
is the reason the signer typed. The identifier follows the record's own scheme,
`rt-return-<episode>-<n>`, counted so a second return gets its own. When the episode
belongs to a programme, the trigger is appended to that programme's list of triggers, in
the same revision style as every other write.

It refuses more than it accepts: a non-human actor, an actor with no id to record by
name, a blank reason, an episode the graph does not hold, and any episode not awaiting a
signature — so a signed package cannot be sent back. The episode and the package are left
exactly as they were. The programme's existing refresh path is how the rework becomes a
new episode, with the old one superseded rather than deleted.

The signing path is closed against it from the other side: while a signer-return newer
than the latest full package is filed and not yet opened as a refresh, signing is refused
outright, using the same predicate the queue uses to show the return. The queue and the
signature can therefore never disagree about whether a package is standing returned.

## Consequences

The record carries who returned the package, when and why, in an object of a type it
already had. The queue shows the return as the act to do next; the views show the
signature waiting on it rather than competing with it. The programme's timeline shows the
trigger on the connector where every other trigger sits. Nothing is deleted, nothing is
reopened, and the package the signer refused stays readable exactly as they read it.

The cost is that a send-back does not by itself change the episode's state, so a reader
looking only at the lifecycle state sees a decision still awaiting a signature. That is
true, and the queue, the timeline and the package view all say why.

## Where it is enforced

- `src/docket/kernel/refresh.py::signer_return` and
  `src/docket/kernel/clock.py::signed_return_triggers` — the write and the predicate.
- `tests/kernel/test_refresh.py::test_signer_return_files_a_human_trigger_naming_the_episode`,
  `::test_signer_return_refuses_an_agent_a_blank_reason_and_a_wrong_state`,
  `::test_signer_return_refuses_a_signed_package`,
  `::test_signer_return_refuses_an_actor_with_no_id`.
- `tests/api/test_send_back.py` — the route: the trigger is filed and the queue shows it,
  the write is persisted and history is unchanged, a second return gets its own id, a
  blank reason and an unknown episode and an episode not awaiting a signature are each
  refused by name, and a non-human actor is refused even under a simulated regression.
- `tests/test_schema.py::test_refresh_trigger_accepts_signer_return_naming_an_episode`.
- `ui/e2e/package.spec.ts` — sending it back files the trigger and returns the reader to
  What needs you, proved against the record through the API rather than against the
  screen.

## What would reverse it

A requirement that a returned package move the episode into a state of its own. That
would be a lifecycle change with its own gate and its own checks, and it would supersede
this record rather than amend it.
