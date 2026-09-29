"""Small, tolerant helpers shared by every exporter in this package (design §6.3).

Deliberately independent of `kernel.render`'s own `_obj`/`_ref_ids` (which are not on
this task's reuse list) — these are three-line, self-evident helpers, and keeping a
local copy here means a bug in one exporter's reference handling cannot be confused
with a change to the renderer's. Every exporter in this package must tolerate a
hand-edited or partially-built graph exactly like `kernel.render` does: a dangling id,
a wrong-typed field or a missing object prints as an explicit marker, never a raw
`KeyError`/`TypeError`.
"""

from __future__ import annotations

from docket.store import Graph


def obj(g: Graph, ref: object) -> dict | None:
    """The object `ref` names, or `None` — for any shape of `ref` at all."""
    if not isinstance(ref, str) or not g.has(ref):
        return None
    o = g.get(ref)
    return o if isinstance(o, dict) else None


def ref_ids(ids: object) -> list[str]:
    """Every string entry of `ids`, in stored order, tolerant of `ids` not being a
    list at all."""
    return [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []


def sorted_ref_ids(ids: object) -> list[str]:
    """`ref_ids`, sorted — every exporter's row order is fixed by object id, never by
    the episode's own (potentially meaningful, but here irrelevant) storage order."""
    return sorted(ref_ids(ids))


def slug(text: object) -> str:
    """A deterministic, lower-case, hyphenated id fragment from arbitrary text — used
    wherever an exporter needs a stable id for something the graph names only by a
    free-text label (a DMN knowledge-source document, a GSN exclusion target with no
    `target.id`). Never empty: unlabelled input slugs to `"unlabelled"` rather than an
    empty string, so a synthetic id built from it is never a bare `-`."""
    s = str(text if text is not None else "").strip().lower()
    out: list[str] = []
    prev_dash = False
    for ch in s:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-") or "unlabelled"


def reachable_objects(g: Graph, episode_id: str, *types: str) -> list[tuple[str, dict]]:
    """`(id, object)` pairs, sorted by id, for every object of any of `types` that is
    forward-reachable from `episode_id` (the episode itself included in the walk).

    "Forward-reachable" is `Graph.reachable_from(..., reverse=False)`: it follows the
    schema-declared reference fields transitively (episode -> run -> Result, episode ->
    evidenceRegister -> Evidence, ...), which is exactly the set every exporter in this
    package means by "everything the episode's record actually names."
    """
    reach = {episode_id} | g.reachable_from(episode_id, reverse=False)
    out = []
    for oid in sorted(reach):
        o = obj(g, oid)
        if o is not None and o.get("type") in types:
            out.append((oid, o))
    return out
