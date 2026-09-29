"""Resolve graph objects into the shapes the UI reads. No arithmetic, no judgment: every
field here is copied from the graph or computed by the kernel's own predicates
(`kernel.lifecycle.CHECKS`), never restated by hand, so a rename in the kernel is
reflected here for free instead of producing a checklist that quietly disagrees with the
gate it describes.
"""
from __future__ import annotations

from collections import defaultdict

from docket.kernel.lifecycle import CHECKS, EDGES, HUMAN_ONLY
from docket.kernel.queue import what_would_satisfy
from docket.objects import LIFECYCLE_STATES, is_marker, iter_slots, marker_target
from docket.store import Graph


def slot_view(g: Graph, value: object) -> dict:
    """Classify a single field value as content, a gap marker or an exclusion marker.

    A marker's target is resolved eagerly (`targetObject`) so the UI can render the
    `InsufficientEvidence`/`Exclusion` inline without a second round trip; a dangling
    target (a hand-edited store) resolves to `None` rather than raising — that is
    `ref-integrity`'s finding to report, not this function's to crash on.
    """
    if is_marker(value):
        target = marker_target(value)
        kind = "gap" if value.get("$gap") is not None else "exclusion"
        return {
            "kind": kind,
            "target": target,
            "targetObject": g.get(target) if isinstance(target, str) and g.has(target) else None,
        }
    return {"kind": "content", "value": value}


def _value_text(obj: dict) -> dict:
    """A sibling map, `str()` of every numeric leaf directly on `obj` or one level
    inside a nested dict (e.g. `FlipAnalysis.range.{lo,hi}`) — plan 07 Task 7 fix round,
    I2. `kernel.render` already prints these values with a plain `str()`/f-string, never
    a custom format (`_flip_row`'s `f"{f.get('currentValue')}"`, `_evaluation_results_
    body`'s `f"{res.get('value')} ..."`); this mirrors that exactly, so `<Num>` can
    prefer the API's own text form instead of re-stringifying a `JSON.parse`d float at a
    different precision than the rendered package (`36.0` must not become `"36"`).
    `bool` is excluded first (`bool` is an `int` subclass in Python). Nested one level
    only: no object in this schema carries a float two levels deep that this app needs
    to display individually.
    """
    out: dict = {}
    for key, value in obj.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            out[key] = str(value)
        elif isinstance(value, dict):
            nested = _value_text(value)
            if nested:
                out[key] = nested
    return out


def object_view(g: Graph, oid: str, *, rev: int | None = None) -> dict:
    """The envelope, its authorship (lifted out for the provenance marks the spec's §2
    computes from `authorType` + `confidence` alone, with no further round trip), every
    gap/exclusion slot it carries, and who references it.

    `revisions` always enumerates every revision through the object's *current* latest —
    not the revision being viewed — so a revision picker still shows every entry while
    browsing an old one; `g.get(oid)` (no `rev`) raises `KeyError` first when `oid` is
    entirely unknown, which is what turns into the route's 404.

    `valueText` (plan 07 Task 7 fix round, I2): the renderer's own `str()` form of every
    numeral `obj` carries, keyed the same way `obj` itself is shaped — additive, next to
    `object`, never inside it, so `view.object` stays exactly what the graph stored.
    """
    latest = g.get(oid)
    obj = g.get(oid, rev) if rev is not None else latest
    slots = [{"path": path, **slot_view(g, value)}
             for path, value in iter_slots(obj) if is_marker(value)]
    created_by = obj.get("createdBy") or {}
    return {
        "id": oid,
        "rev": obj.get("rev"),
        "type": obj.get("type"),
        "object": obj,
        "authorType": created_by.get("actorType"),
        "authorId": created_by.get("actorId"),
        "confidence": obj.get("confidence"),
        "provenance": obj.get("ingestionProvenance"),
        "slots": slots,
        "revisions": list(range(1, (latest.get("rev") or 1) + 1)),
        "referencedBy": g.refs_to(oid),
        "valueText": _value_text(obj),
    }


def _passed_states(ep: dict) -> list[str]:
    """The `to` state of every transition this episode actually completed, in the order
    it completed them. A refused attempt (`refused: True`) never moved the state, so it
    is not "passed" — it still shows up wherever the caller renders `transitions`
    directly, which is what "refusals are shown, not hidden" asks for."""
    passed: list[str] = []
    for record in ep.get("transitions") or []:
        if not record.get("refused") and record.get("to") not in passed:
            passed.append(record["to"])
    return passed


def _gate_ladder(g: Graph, ep: dict) -> list[dict]:
    frm = ep.get("lifecycleState")
    available = EDGES.get(frm, set())
    passed = _passed_states(ep)
    # Every state this episode has already reached, plus every state it could reach
    # next — sorted by the lifecycle's own canonical order so the ladder renders left to
    # right the way the states actually happen, not in a set's arbitrary order.
    candidates = {s for s in available} | set(passed)
    ordered = [s for s in LIFECYCLE_STATES if s in candidates]
    ladder = []
    for state in ordered:
        # The gate's own sentence for what each check wants, from the one definition in
        # the repo (`kernel.queue.what_would_satisfy`, the same text the Needs queue and
        # the G1 sheet print) — so a ladder and a queue can never disagree about the
        # predicate that will actually refuse.
        checks = [{"name": name, "satisfied": bool(check(g, ep)),
                   "whatWouldSatisfy": what_would_satisfy(check, name, state)}
                  for name, check in CHECKS.get(state, [])]
        if state in passed:
            status = "passed"
        elif state in available and all(c["satisfied"] for c in checks):
            status = "available"
        else:
            status = "blocked"
        ladder.append({"to": state, "state": status, "checks": checks,
                       "humanOnly": state in HUMAN_ONLY})
    return ladder


def _counts(g: Graph, ep: dict) -> dict[str, int]:
    """How many objects of each type the episode's reference lists resolve to.

    Generic over field names on purpose: a reference list is any list field whose string
    items resolve to graph objects, so a field added to `DecisionEpisode` later is
    counted without this function being told its name.
    """
    counts: dict[str, int] = defaultdict(int)
    for value in ep.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, str) and g.has(item):
                counts[g.get(item)["type"]] += 1
    return dict(counts)


def episode_view(g: Graph, eid: str) -> dict:
    """The episode object plus the gate ladder, resolved reference counts and readiness.

    `gateLadder` calls the predicates in `lifecycle.CHECKS[state]` directly rather than
    restating the list of check names, so a check renamed in the kernel is reflected
    here for free and a reviewer never sees a checklist that disagrees with the gate.
    """
    ep = g.get(eid)
    return {
        **ep,
        "gateLadder": _gate_ladder(g, ep),
        "counts": _counts(g, ep),
        "readiness": ep.get("readiness"),
        "transitions": ep.get("transitions") or [],
    }
