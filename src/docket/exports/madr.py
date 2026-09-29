"""One-page MADR / ISO 42010 decision record export (design §6.3, mapping table 5).

**Deviation from the task brief's mapping table (pre-flight defect D18, revisited).**
"More Information" quotes `render.content_snapshot_hash(g)` — the graph's *content*
hash, excluding `DecisionPackage` objects — rather than "the latest built package's
hash." The literal ask (quote a specific `DecisionPackage.hash`) cannot be honoured
without breaking kernel C2 (`tests/kernel/test_render.py
test_c2_two_consecutive_full_builds_are_byte_identical`): two consecutive
`build_package` calls on an unchanged record must produce byte-identical text, and
`to_madr` is one of the six exports the Machine annex hashes into a *new* package's own
text. If its content depended on `render.latest_package(...)`, the first
`build_package` call would change what the *second* call's MADR says (a package now
exists that did not before), and the two builds would disagree — the exact class of bug
`render._content_snapshot` already excludes `DecisionPackage` objects to prevent.
`content_snapshot_hash(g)` is the value the build *will* store as the new package's own
`graphSnapshotHash`; it is knowable in advance and does not depend on build history. A
reader who wants a specific sealed `DecisionPackage.hash` should read
`render.latest_package_hash` (or plan 07's package-listing API) directly, not this
generated document.
"""

from __future__ import annotations

from docket import KERNEL_VERSION
from docket.exports._util import obj, reachable_objects, ref_ids
from docket.kernel.render import _cite_withheld_level, content_snapshot_hash, episode_exclusions
from docket.store import Graph

_PRIMARY_RANK_CUTOFF = 3  # plan 04 R16's convention, not a schema rule — label it as one


def _obs_by_alt(g: Graph, ep: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for oid in ep.get("observations") or []:
        o = obj(g, oid)
        if o is not None:
            out.setdefault(o.get("alternative"), []).append(o)
    return out


def _section_exclusion(g: Graph, episode_id: str, label: str) -> dict | None:
    """The `Section`-targeted `Exclusion` named `label`, scoped to `episode_id` via
    `render.episode_exclusions` — the same membership rule (forward-reachable **or**
    referenced by nothing at all) `render_package`'s own `section_excl` lookup and
    "Other exclusions on record" list use (review round 2, R1).

    Round 1 (C3) scoped this to *only* `reachable_objects(g, episode_id,
    "Exclusion")` — forward-reachable from the episode — which stopped a same-named
    Exclusion belonging to a different episode (Demo B's three sub-episodes share one
    graph) from leaking in, but a wholly unreferenced Exclusion (no slot, no
    `statusReason`, nothing but a bare `{"kind": "Section", "label": ...}` target —
    Demo A's own `ex-no-commitment`) is not forward-reachable either, so it silently
    vanished from the MADR while the package right beside it kept printing it and its
    authority. `episode_exclusions` restores that legitimate case without reopening
    the leak: an Exclusion referenced only from outside this episode's reach is still
    excluded.
    """
    for x in episode_exclusions(g, episode_id):
        target = x.get("target") if isinstance(x.get("target"), dict) else {}
        if target.get("kind") == "Section" and target.get("label") == label:
            return x
    return None


def _alt_sort_key(a: dict) -> tuple:
    order = a.get("enteredOrder")
    has_order = isinstance(order, int) and not isinstance(order, bool)
    return (0 if has_order else 1, order if has_order else 0, a.get("id", ""))


def to_madr(g: Graph, episode_id: str, *, rendering: str) -> str:
    ep = obj(g, episode_id) or {}
    ch = obj(g, ep.get("charter")) or {}
    obs_by_alt = _obs_by_alt(g, ep)

    lines: list[str] = []
    title = ch.get("question") if isinstance(ch.get("question"), str) else "_[unavailable]_"
    lines.append(f"# {title}")
    lines.append("")

    lines.append("## Status")
    lines.append("")
    lines.append(str(ep.get("lifecycleState") or "_[unavailable]_"))
    lines.append("")

    lines.append("## Context")
    lines.append("")
    scope = ch.get("scope") if isinstance(ch.get("scope"), dict) else {}
    lines.append(f"**In scope:** {'; '.join(scope.get('included') or []) or '_[unavailable]_'}")
    lines.append(f"**Out of scope:** {'; '.join(scope.get('excluded') or []) or '—'}")
    coe = ch.get("consequencesOfErroneousOutput")
    coe_text = coe if isinstance(coe, str) else "_[unavailable]_"
    lines.append(f"**Consequences of erroneous output:** {coe_text}")
    lines.append("")

    lines.append("## Decision Drivers")
    lines.append("")
    lines.append(
        f"_(primary drivers: Objectives with `priorityRank` <= {_PRIMARY_RANK_CUTOFF} — "
        "a convention, plan 04 ruling R16, not a schema rule)_"
    )
    for oid, o in ((i, obj(g, i)) for i in ref_ids(ep.get("objectives"))):
        if o is None:
            continue
        rank = o.get("priorityRank")
        is_primary = o.get("priority") == "primary" or (
            isinstance(rank, int) and not isinstance(rank, bool) and rank <= _PRIMARY_RANK_CUTOFF
        )
        if is_primary:
            lines.append(f"- **{o.get('name')}** ({oid}, rank {rank})")
    lines.append("")

    lines.append("## Considered Options")
    lines.append("")
    alts = sorted(
        (o for o in (obj(g, i) for i in ref_ids(ep.get("alternatives"))) if o is not None),
        key=_alt_sort_key,
    )
    for a in alts:
        line = f"- **{a.get('name')}** ({a.get('id')}) [{a.get('status')}]: {a.get('description')}"
        reason_ref = a.get("statusReason")
        reason = obj(g, reason_ref)
        if reason is not None and reason.get("type") == "Exclusion":
            authority = reason.get("authority") if isinstance(reason.get("authority"), dict) else {}
            line += (
                f" — screened out: {reason.get('reasonType')} "
                f"({authority.get('who')}, {authority.get('date')}): {reason.get('reason')}"
            )
        lines.append(line)
    lines.append("")

    lines.append("## Decision Outcome")
    lines.append("")
    commitment = obj(g, ep.get("commitment"))
    if commitment is not None:
        signer = commitment.get("signer") if isinstance(commitment.get("signer"), dict) else {}
        lines.append(
            f"Selected: **{commitment.get('selected')}** — signed by "
            f"{signer.get('identity')} ({signer.get('role')}) at {commitment.get('signedAt')}."
        )
    else:
        excl = _section_exclusion(g, episode_id, "commitment")
        if excl is not None:
            authority = excl.get("authority") if isinstance(excl.get("authority"), dict) else {}
            lines.append(
                f"No commitment on record — {excl.get('reasonType')} "
                f"({authority.get('who')}, {authority.get('date')}): {excl.get('reason')}"
            )
        else:
            lines.append("*no decision recorded*")
    lines.append("")

    lines.append("## Consequences")
    lines.append("")
    risks = [r for r in (obj(g, i) for i in ref_ids(ep.get("risks"))) if r is not None]
    if risks:
        for r in risks:
            lines.append(f"- [{r.get('kind')}] {r.get('statement')} — {r.get('consequence')}")
    else:
        lines.append("_(no risks on record)_")
    lines.append("")

    lines.append("## Confirmation")
    lines.append("")
    rr = obj(g, ep.get("readiness"))
    sa = obj(g, rr.get("standardsAssessment")) if rr is not None else None
    verdicts = sa.get("dimensionVerdicts") if sa is not None and isinstance(
        sa.get("dimensionVerdicts"), dict
    ) else None
    if verdicts:
        for dim, v in sorted(verdicts.items()):
            v = v if isinstance(v, dict) else {}
            lines.append(f"- **{dim}:** {v.get('verdict', '_[unavailable]_')}")
    else:
        lines.append("_(no readiness report on record)_")
    lines.append("")

    lines.append("## Pros / Cons of the Options")
    lines.append("")
    # Review round 1, C3: scoped to the episode's own reachable Results, not
    # `g.all("Result")` — a graph-wide scan would list another episode's numbers
    # against this episode's alternatives the day two episodes share a graph (Demo B).
    episode_results = [r for _rid, r in reachable_objects(g, episode_id, "Result")]
    for a in alts:
        aid = a.get("id")
        results = sorted(
            (r for r in episode_results if r.get("alternative") == aid and r.get("aggregate")),
            # M7: (run, id) is a total order — (run,) alone ties whenever the same
            # alternative has two aggregate Results from the same run, and falls back
            # to whatever order `reachable_objects` happened to return.
            key=lambda r: (r.get("run", ""), r.get("id", "")),
        )
        if not results:
            lines.append(f"- **{a.get('name')}**: _(not evaluated)_")
            continue
        for r in results:
            level = _cite_withheld_level(g, r["id"], rendering, obs_by_alt)
            value = f"[withheld: {level}]" if level else f"{r.get('value')} {r.get('units')}"
            lines.append(f"- **{a.get('name')}** (run {r.get('run')}): {value}")
    lines.append("")

    lines.append("## More Information")
    lines.append("")
    # M4: labelled so a reader comparing this against the package/annex can see it is
    # the same value — verified equal to both the Machine annex's "graph snapshot
    # hash" line and the stored DecisionPackage.graphSnapshotHash, for both renderings.
    lines.append(
        f"Rendering: {rendering} · "
        f"graph snapshot hash (this package's `graphSnapshotHash`): "
        f"{content_snapshot_hash(g)} · kernel: {KERNEL_VERSION}"
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["to_madr"]
