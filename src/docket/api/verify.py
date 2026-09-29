"""The determinism affordance (plan 07 Task 4): re-render a package at its own stored
`renderedAt` and compare hashes against the kernel's own `latest_package_hash` — never a
locally recomputed idea of "the latest package," and never `Graph.snapshot_hash()`.

This is not a claim that an LLM is deterministic — it is a claim that the *kernel* is,
and that a `DecisionPackage` is a pure function of the graph. `scope` says which, in the
words the route returns, so nobody reads a green "identical" as a reproducibility promise
about the model.

`src/docket/exports/` landed in this tree mid-task (plan 06 Task 1, concurrent with this
one) and now provides `kernel.render.latest_package(g, episode_id, rendering=...) -> dict
| None` directly — the exact "recover the object `latest_package_hash` selected" helper
this module would otherwise have had to reinvent. Delegating to it, rather than keeping
a second, API-layer copy of that log-walk, is exactly the "do not re-derive a question the
gate already answers" rule the plan states for this file.

**A defect this module exposed rather than hid, found during plan 07 Task 4 and fixed
upstream — see the Task 4 report's "Defects found."** Before the fix,
`docket.exports.prov.to_prov` enumerated *every* `DecisionPackage` for the episode
already in the graph, and `docket.exports.madr.to_madr` embedded `latest_package(...)`'s
own hash — both self-referential the moment the package being verified was itself
already sealed into the graph, which it always is by the time anything calls `/verify`.
`verify_package` was, and still is, implemented exactly as specified (re-render via
the stable public `render_package`, compare against `latest_package_hash`) and reports
whatever the kernel actually produces; it does not special-case the graph to hide the
package being verified from the exports it re-renders, which would be a second, narrower
definition of "the record" invented at the API layer to make a red light go green.

**`recordUnchanged`/`reason` (fix round 1, I3).** `identical` alone cannot distinguish
"the record changed" from "the record is fine and only the rendering format changed" —
exactly the ambiguity a real probe against Demo A's stale committed package hit:
`identical: false` with the two `graphSnapshotHash` values equal. `recordUnchanged` is
that one extra, already-server-computed boolean comparison, and `reason` spells it out
in words the UI prints verbatim rather than asking anyone to diff two hex strings by eye.

**One render-and-hash primitive (plan 06 Task 2, ruling R4 M11 fix).** The actual
"re-render at `rendering`/`now` and hash it" step below now calls
`docket.kernel.verify.render_hashes` — the same primitive
`docket.kernel.verify.verify_determinism` (the CI gate's and `docket verify`'s entry
point) builds on — instead of keeping a second, API-local copy of that computation. The
comparison semantics here stay this module's own (against the *prior sealed* package's
`renderedAt`/hash, not a second fresh render of the current graph), because that is what
"did the already-published package survive a re-render" means for a reviewer looking at
a session; `verify_determinism` answers the narrower, CI-shaped question of whether one
render pass is reproducible at all. Sharing the primitive is what keeps those two
questions from silently drifting into two different definitions of "identical".
"""
from __future__ import annotations

from docket import KERNEL_VERSION
from docket.kernel.render import content_snapshot_hash, latest_package, latest_package_hash
from docket.kernel.verify import render_hashes
from docket.store import Graph


class NoPackageBuilt(Exception):
    """No `DecisionPackage` has been built yet for this episode/rendering. The route
    maps this to 409, not 500 — "render a package before verifying it" is an ordinary,
    expected state at a demo, not a server fault."""


def verify_package(g: Graph, episode_id: str, *, rendering: str = "full") -> dict:
    """Re-render `episode_id` at `rendering` using the *stored* package's own
    `renderedAt` (never the wall clock — otherwise the cover section prints today's
    date, the bytes differ, and "identical" reports false for a reason that has nothing
    to do with determinism) and compare the resulting hash against
    `kernel.render.latest_package_hash`.

    `graphSnapshotHash`/`priorGraphSnapshotHash` are both `content_snapshot_hash`
    values — the content-only view that excludes `DecisionPackage` objects — never
    `Graph.snapshot_hash()`. Since kernel C2, `graphSnapshotHash` no longer means "the
    whole graph": `g.snapshot_hash()` includes every `DecisionPackage` already built,
    so it would differ from a stored package's `graphSnapshotHash` on any graph that has
    ever had a package built against it, even when nothing else has changed — a false
    "drift" reading with no reproducibility content at all. See
    `kernel.render.content_snapshot_hash`'s own "R6" docstring note.
    """
    prior_hash = latest_package_hash(g, episode_id, rendering=rendering)
    if prior_hash is None:
        raise NoPackageBuilt(
            f"no {rendering!r} package has been built for {episode_id}; "
            "render one before verifying it"
        )
    prior = latest_package(g, episode_id, rendering=rendering)
    again = render_hashes(g, episode_id, rendering=rendering, now=prior["renderedAt"])["package"]
    identical = again == prior_hash
    graph_snapshot_hash = content_snapshot_hash(g)
    record_unchanged = graph_snapshot_hash == prior.get("graphSnapshotHash")
    if identical:
        reason = "identical"
    elif record_unchanged:
        reason = "record unchanged; rendering changed"
    else:
        reason = "record changed"
    return {
        "identical": identical,
        "recordUnchanged": record_unchanged,
        "reason": reason,
        "hash": again,
        "priorHash": prior_hash,
        "graphSnapshotHash": graph_snapshot_hash,
        "priorGraphSnapshotHash": prior.get("graphSnapshotHash"),
        "kernelVersion": KERNEL_VERSION,
        "scope": "kernel rendering only; model outputs are not re-run",
    }


__all__ = ["NoPackageBuilt", "verify_package"]
