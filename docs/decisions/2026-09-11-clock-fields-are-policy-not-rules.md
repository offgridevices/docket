# Clock fields are policy, not rules

Date: 2026-09-11. Status: accepted.

## Context

The interface needed to answer three questions a person actually asks: when is this due,
where has the time gone, and who has it been waiting on. The record could already answer
the second and the third — every object carries when it was written and by whom, and the
episode carries its transitions — but it held nothing at all for the first. There was no
deadline anywhere, and no statement of how long a stage is supposed to take.

Adding either one is easy and dangerous. A deadline that a gate reads becomes a rule that
refuses work for being late, which is not a judgement this kernel is entitled to make. An
expected time per stage that a check reads becomes a schedule masquerading as a standard.
And any new field risks the determinism guarantee: the committed demonstration outputs
have to stay byte-identical.

## Decision

Two optional schema fields, read by one module, and by no gate.

- `Charter.neededBy` is a human-authored date: when this decision is needed by.
- `Policy.expectedDaysByState` is an optional map of state to days. When it is absent the
  kernel uses one named default, and the clock reports which of the two it used.
- Neither field is set in any committed demonstration record, so the demonstration
  outputs are unchanged and the determinism check stays green.
- `src/docket/kernel/clock.py` derives everything else from the log: when the episode was
  opened, when it entered each state, how long it has sat in the one it is in, when a
  person last acted and what they did. It flags an overrun and it flags a deadline that
  has passed; the flag's wording is the clock's own.
- No gate check reads either field. They appear nowhere in the lifecycle's checks, in
  readiness, or in the renderer. Nothing the clock computes is ever written into a
  package: it is computed at request time and thrown away.

Where the clock cannot be honest it says nothing rather than estimating. With no deadline
set, how much time is left and how wide the whole span is are both absent, and the
interface draws a strip that runs to today instead of to a guess. A decision that is
signed, superseded or void is never late and never stuck.

## Consequences

The interface can say "overdue" and "nothing has happened for so many days", and mean it,
because both come from timestamps the record already kept. The kernel never refuses
anything because of time — lateness is information for a person, not a verdict. A team
that wants stage expectations can put them in their policy; a team that does not gets the
kernel's default and a flag that is advisory either way.

The cost is that a deadline only exists if somebody types one, and in the demonstrations
nobody has, so the clock's most prominent line is usually the honest one saying no
deadline is set. The Request view offers the field, and the Explain panel says in words
that expected time per stage flags a stage and never blocks anything.

## Where it is enforced

- `src/docket/kernel/clock.py` — the only module that reads either field.
- `tests/test_schema.py::test_charter_needed_by_is_optional_and_a_string` and
  `::test_policy_expected_days_by_state_is_optional_and_integer_valued` — optional, and
  typed.
- `tests/test_schema.py::test_no_demo_record_sets_the_two_new_fields` — every object of
  every committed demonstration store is checked for both field names.
- `tests/kernel/test_clock.py` — the derivations, the absent-deadline case, the terminal
  states, and the flags.
- `tests/api/test_clock.py` — the route, read-only and computed at request time.
- `scripts/determinism-check.sh` — the committed demonstration trees stay byte-identical.
- `ui/e2e/clock.spec.ts` — the card prints only what the kernel computed, and Explain
  carries the policy-not-rule sentence inside the card.

## What would reverse it

A requirement that a decision be refused, or a state be forced, because of elapsed time.
That is a lifecycle change: it would need its own check, its own refusal wording and its
own place in the gate ladder, and it would supersede this record rather than amend it.
