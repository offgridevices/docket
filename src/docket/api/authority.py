"""The authority rail's numbers, computed server-side (plan 07 Task 4).

The persistent authority rail is the visible form of a settled architectural fact
(CLAUDE.md: "the agent never sits in the numeric path") — so the browser must not be the
one adding these up about itself. Every field here is a plain count over objects the
episode's record reaches, or a re-check of an invariant the store already enforces at
write time (`Graph._check_agent_authority`, via `AGENT_FORBIDDEN_TYPES`); nothing here
computes a decision value.
"""
from __future__ import annotations

from docket import KERNEL_VERSION
from docket.kernel.validate import rule_authority
from docket.store import Graph

_ACTOR_TYPES = ("human", "agent", "kernel")

# Envelope and run-metadata fields that are bookkeeping, not a number the object's
# author is making a claim with. `rev` is a counter every object carries regardless of
# content; `createdAt`/`createdBy`/`ingestionProvenance`/`supersedes`/`confidence` name
# who wrote the object and when, not what it found; `seed`/`kernelVersion` name the run
# that produced a value rather than being a value themselves. Counting any of these
# would inflate every actor's total by the same constant amount without changing what
# the rail exists to answer: whether *any* number an agent wrote reached this record —
# an answer the store already makes 0 by construction (`AGENT_FORBIDDEN_TYPES` plus the
# write-path rules in `store.py`), so this counter is a readout of an enforced property,
# not a promise resting on the API layer's own arithmetic.
_EXCLUDED_TOP_LEVEL_FIELDS = frozenset({
    "rev", "id", "type", "createdAt", "createdBy", "supersedes",
    "ingestionProvenance", "confidence", "seed", "kernelVersion",
})


def _numeric_leaves(value: object, *, top: bool = False) -> int:
    """Every numeric leaf inside `value`, at any depth: dict values and list items
    alike. `bool` is excluded — Python's `bool` is an `int` subclass, and a flag like
    `linchpin: true` is not a number the rail should be counting. Only at the *top*
    level of an object are `_EXCLUDED_TOP_LEVEL_FIELDS` skipped before recursing, so an
    object's own bookkeeping never counts as one of "its" numerals while a same-named
    field nested inside a sub-object (there is none in the schema today) is not
    special-cased away, the same way `render._numbers_in` treats nested values.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int | float):
        return 1
    if isinstance(value, dict):
        total = 0
        for key, v in value.items():
            if top and key in _EXCLUDED_TOP_LEVEL_FIELDS:
                continue
            total += _numeric_leaves(v)
        return total
    if isinstance(value, list):
        return sum(_numeric_leaves(v) for v in value)
    return 0


def authority_counts(g: Graph, episode_id: str) -> dict:
    """Object and numeral counts, by the actor type that authored each object this
    episode's record reaches, plus a live re-check of the agent-authority boundary
    itself scoped to the same reach.

    `reach` is forward reachability from the episode — the same definition
    `readiness.py`'s own per-episode scoping uses ("this episode's record", not the
    whole store). `agentForbiddenWrites` reuses `kernel.validate.rule_authority` rather
    than re-deriving the boundary here: `put()` refuses an agent that authors a
    forbidden type in process, but a saved store can be hand-edited and the log chain is
    unkeyed, so a forgery can re-chain cleanly — `rule_authority` is what makes that
    boundary checkable from the store alone, and this counter is a readout of it, not a
    second definition of it.
    """
    reach = {episode_id} | g.reachable_from(episode_id, reverse=False)
    objects = {"human": 0, "agent": 0, "kernel": 0}
    numerals = {"human": 0, "agent": 0, "kernel": 0}
    for oid in sorted(reach):
        if not g.has(oid):
            continue  # a dangling reference is ref-integrity's finding, not this one's
        obj = g.get(oid)
        author = obj.get("createdBy")
        actor_type = author.get("actorType") if isinstance(author, dict) else None
        if actor_type not in _ACTOR_TYPES:
            # A hand-edited or partially-written store can hold anything here at all;
            # an unrecognised actor type is `rule_schema`'s finding to report, not
            # something this counter silently folds into one of the three real buckets.
            continue
        objects[actor_type] += 1
        numerals[actor_type] += _numeric_leaves(obj, top=True)

    forbidden = [f for f in rule_authority(g) if set(f.objects) & reach]

    return {
        "episode": episode_id,
        "objects": objects,
        "numerals": numerals,
        "agentForbiddenWrites": len(forbidden),
        "kernelVersion": KERNEL_VERSION,
        "explanation": (
            "Numeric leaves in the objects this episode reaches, counted by the actor "
            "who wrote each object. Agent-authored numerals reaching a run, a result, "
            "a rating or a commitment are refused by the store at write time "
            "(AGENT_FORBIDDEN_TYPES); agentForbiddenWrites re-checks that same boundary "
            "against the store itself, which is how a hand-edited store's forged "
            "authorship is still caught."
        ),
    }


__all__ = ["authority_counts"]
