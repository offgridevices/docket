"""Type registry, P3 slot helpers, and reference walking driven by the catalogue."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from docket.schema import catalogue

# One private copy of the catalogue, taken at import and never mutated: catalogue() hands
# out a deep copy on every call, and the ref walker runs on every object of every
# validation.
_TYPE_SPECS: dict[str, dict] = catalogue()["types"]

TYPES: frozenset[str] = frozenset(_TYPE_SPECS)

AGENT_FORBIDDEN_TYPES: frozenset[str] = frozenset({
    "EvaluationRun", "Result", "FlipAnalysis", "StandardsAssessment", "MandateScorecard",
    "ReadinessReport", "Commitment", "EpisodeDiff", "DecisionPackage",
    # Policy is the gate the agent is measured against; it may not author its own parameters.
    "Policy",
})

LIFECYCLE_STATES = ("DRAFT", "MODEL_APPROVED", "PLAN_APPROVED", "EVALUATED",
                    "PENDING_SIGNATURE", "SIGNED", "SUSPECT", "SUPERSEDED", "VOID")

# Every agent actor id begins with this, by the ledger's defect-17 convention
# (`agent:<model>`): `agent.elicit.elicit`, `agent.cli._actor_for` and
# `api.config.agent_actor` all build ids that way, and `elicit` already refuses a
# `createdBy.actorId` that does not.
AGENT_ID_PREFIX = "agent:"


def _actor_id(actor: Any) -> str | None:
    return actor.get("actorId") if isinstance(actor, dict) else None


def id_says_agent(actor: Any) -> bool:
    """The actor id claims an agent — `agent:<model>` — whatever the dict declares."""
    actor_id = _actor_id(actor)
    return isinstance(actor_id, str) and actor_id.startswith(AGENT_ID_PREFIX)


def is_agent_actor(actor: Any) -> bool:
    """Whether this actor is an agent, derived rather than taken on the dict's word.

    Authorship used to be whatever `actorType` said, and the whole boundary rode on a
    single self-declared string: an actor presenting
    `{"actorType": "human", "actorId": "agent:recorded"}` was a human as far as
    `Graph.put` was concerned, and could sign, approve and drive a lifecycle edge
    [T9 review M1]. Reading the id as well closes that: an id beginning `agent:` **is**
    an agent here, whatever the dict declares.

    Fails toward "agent", which is the safe direction — the agent is the actor class
    with fewer permissions, so an ambiguous actor is held to the stricter rule.
    `actor_class_mismatch` refuses the ambiguity outright at the write path; this is
    what audits a store where the write path was bypassed.
    """
    declared = actor.get("actorType") if isinstance(actor, dict) else None
    return declared == "agent" or id_says_agent(actor)


def actor_class_mismatch(actor: Any) -> str | None:
    """A description of a disagreement between `actorType` and the `actorId` prefix, or None.

    Both directions are a malformed actor, not a permitted one:

    * `{"actorType": "human", "actorId": "agent:x"}` — the lie the boundary was defeated
      by, an agent wearing a human's permissions.
    * `{"actorType": "agent", "actorId": "x"}` — an agent hiding from an audit that
      indexes authorship by id, and a breach of the `agent:<model>` naming convention
      the rest of the codebase relies on.

    A `kernel` actor is held to the same rule as a human: nothing but an agent may carry
    an `agent:` id.
    """
    if not isinstance(actor, dict):
        return None  # not an actor at all; the schema rule reports the shape
    declared = actor.get("actorType")
    actor_id = _actor_id(actor)
    if declared not in ("human", "agent", "kernel"):
        return None  # an unknown actor type is the schema's finding, not this one's
    if id_says_agent(actor) and declared != "agent":
        return (f"actor {actor_id!r} declares actorType {declared!r}: an actorId "
                f"beginning {AGENT_ID_PREFIX!r} is an agent")
    if declared == "agent" and not id_says_agent(actor):
        return (f"agent actor declares actorId {actor_id!r}: an agent's actorId must "
                f"begin {AGENT_ID_PREFIX!r}")
    return None


def is_exclusion_ref(v: Any) -> bool:
    return isinstance(v, dict) and set(v) == {"$exclusion"}


def is_gap_ref(v: Any) -> bool:
    return isinstance(v, dict) and set(v) == {"$gap"}


def is_marker(v: Any) -> bool:
    return is_exclusion_ref(v) or is_gap_ref(v)


def marker_target(v: Any) -> str | None:
    if is_exclusion_ref(v):
        return v["$exclusion"]
    if is_gap_ref(v):
        return v["$gap"]
    return None


def is_content(v: Any) -> bool:
    if v is None or is_marker(v):
        return False
    if isinstance(v, str | list | dict):
        return len(v) > 0
    return True


def _spec_for(type_name: str, obj: dict) -> dict:
    """Merge base fields with the active variant's fields.

    An unknown type has no fields: rule_schema reports it, and nothing downstream should
    crash on a store written by a different docket version.
    """
    spec = _TYPE_SPECS.get(type_name)
    if spec is None:
        return {}
    fields = dict(spec.get("fields") or {})
    variants = spec.get("variants")
    if variants:
        active = obj.get(spec["discriminator"])
        if active in variants:
            fields.update(variants[active].get("fields") or {})
    return fields


def _walk(fields: dict, value: Any, path: str, refs: list, slots: list) -> None:
    for name, fs in fields.items():
        if isinstance(fs, str):
            fs = {"type": fs}
        if name not in value:
            continue
        v = value[name]
        p = f"{path}/{name}" if path else name
        if fs.get("slot"):
            slots.append((p, v))
        if is_marker(v):
            refs.append((p, marker_target(v)))
            continue
        _walk_value(fs, v, p, refs, slots)


def _walk_value(fs: dict, v: Any, p: str, refs: list, slots: list) -> None:
    if "ref" in fs:
        if isinstance(v, str):
            refs.append((p, v))
        return
    if "oneOfTypes" in fs:
        for alt in fs["oneOfTypes"]:
            if alt.get("type") == "object" and isinstance(v, dict):
                _walk(alt.get("properties") or {}, v, p, refs, slots)
            elif alt.get("type") == "array" and isinstance(v, list):
                for i, item in enumerate(v):
                    _walk_value(alt.get("items", {}), item, f"{p}/{i}", refs, slots)
        return
    t = fs.get("type")
    if t == "array" and isinstance(v, list):
        item_spec = fs.get("items", {"type": "string"})
        if isinstance(item_spec, str):
            item_spec = {"type": item_spec}
        for i, item in enumerate(v):
            ip = f"{p}/{i}"
            if is_marker(item):
                refs.append((ip, marker_target(item)))
            else:
                _walk_value(item_spec, item, ip, refs, slots)
    elif t == "object" and isinstance(v, dict) and fs.get("properties"):
        _walk(fs["properties"], v, p, refs, slots)


def iter_refs(obj: dict) -> Iterator[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    _walk(_spec_for(obj.get("type"), obj), obj, "", refs, [])
    if obj.get("supersedes"):
        refs.append(("supersedes", obj["supersedes"]))
    yield from refs


def iter_slots(obj: dict) -> Iterator[tuple[str, Any]]:
    slots: list[tuple[str, Any]] = []
    _walk(_spec_for(obj.get("type"), obj), obj, "", [], slots)
    yield from slots


def _top_level_slots() -> dict[str, tuple[str, ...]]:
    out = {}
    for name, spec in _TYPE_SPECS.items():
        fields = (spec.get("fields") or {}).items()
        out[name] = tuple(k for k, v in fields if isinstance(v, dict) and v.get("slot"))
    return out


SLOTS: dict[str, tuple[str, ...]] = _top_level_slots()
