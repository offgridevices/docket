"""Refresh engine (design §7.7): SUSPECT marking, new episode, ICD 203 §D.6.e(7) diff.

Phase I does not track field-level diffs between episode revisions. `EpisodeDiff.changed`
only ever fires for an object that a refresh *replaced* under a new id (via the
`replacements` map `open_refresh` records on the new episode): the two ids' latest
revisions are compared field by field once, at diff time, and `pairing` says whether that
map was available. An object retained under the same id across a refresh is reported as
unchanged even if its content was independently revised in between, because nothing in
this phase's `DecisionEpisode` records which revision of a shared object was current as
of a given episode. **The identical blind spot applies to `judgmentsChanged` and
`judgmentsConsistent`**: a `Claim` id present in both episodes is always reported
`judgmentsConsistent`, with no comparison of its `text`/`supportedBy` at all — a claim
revised in place under a stable id reads as unchanged, for the same reason. Demo B's
diffs read as "this assumption was replaced by that one", never as "this object gained a
new sentence in field X", and "this judgment held" means only "this claim id survived,"
not "this claim's content was re-checked and still holds."
"""

from __future__ import annotations

import re

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.canon import canonical_json
from docket.errors import AuthorityViolation, ValidationError
from docket.kernel.lifecycle import transition
from docket.schema.generate import ID_PATTERN
from docket.store import Graph

# The required, non-cleared reference-list fields on DecisionEpisode (design §10 /
# schema/objects.yaml): everything a refresh carries forward, replacements applied.
REF_LISTS = ["objectives", "alternatives", "groundRules", "constraints", "assumptions",
             "evidenceRegister", "scenarios", "claims", "risks", "biasChecks",
             "mandateElements", "observations", "weightSets", "models"]

# A refresh opens a new model, not a continuation of the old one's sealed computation:
# no run, flip analysis or narrative from the prior episode is valid evidence about the
# new one, and a fresh episode's transition history starts empty by construction.
CLEARED = {"runs": [], "flipAnalyses": [], "narratives": [], "transitions": []}


def is_computed_bias_risk(g: Graph, oid: str) -> bool:
    """Whether `oid` is a bias indicator the *kernel* computed, rather than a Risk a
    human recorded.

    Exactly `kernel.bias.bias_indicators`' output: a `Risk` written under `KERNEL_ACTOR`
    whose `kind` is one of the `bias-*` kinds. Those are conclusions the kernel drew
    about one episode from that episode's own model — they are recomputed from scratch
    for the successor by its own `readiness_report`, and carrying the predecessor's copy
    forward would make `episode.risks` accumulate one stale indicator per refresh and
    attribute a 2020 reading to a 2023 episode. A Risk a human entered says something
    about the decision, not about a scoring run, and is carried forward as before.
    """
    if not g.has(oid):
        return False
    o = g.get(oid)
    if o.get("type") != "Risk":
        return False
    created_by = o.get("createdBy")
    kind = o.get("kind")
    return (isinstance(created_by, dict) and created_by.get("actorType") == "kernel"
            and isinstance(kind, str) and kind.startswith("bias-"))


# Fields every replacement-pair diff ignores: identity/provenance, not content.
_NON_CONTENT_FIELDS = ("id", "rev", "createdAt", "createdBy", "ingestionProvenance", "supersedes")

# Anchored on the *end* of the string and on digits only, so an id that merely contains
# "-r" somewhere (e.g. "ep-review-2020") is left untouched. `"ep-review-2020".split("-r")`
# would silently truncate to "ep" and corrupt every id derived from it afterwards; this
# only ever strips a refresh suffix this same module wrote.
_TRAILING_REVISION = re.compile(r"-r\d+$")

# `ID_PATTERN` is imported from `docket.schema.generate` — the same pattern `Graph.put`
# enforces on every write (`store.py` compiles its own copy of it as `_ID_RE`) — so a
# `replacements` value is checked against the one true id shape, not a second copy of it
# that could drift. `fullmatch`, not `match`/`search`, for the same reason `store.py`
# uses it: `pattern` is applied with `re.search` by the JSON Schema validator, so `$`
# alone would let a trailing newline through; `fullmatch` agrees with the write path.
_ID_RE = re.compile(ID_PATTERN)


def _base_id(episode_id: str) -> str:
    """`episode_id` with a trailing `-r<digits>` refresh suffix removed, if present."""
    return _TRAILING_REVISION.sub("", episode_id)


def _validate_replacements(g: Graph, prior: dict, replacements: dict) -> None:
    """Refuse a malformed or non-referential `replacements` map before it can ever
    reach `g.put(new, actor)` — which runs *after* the SUSPECT transition, so a value
    that only fails there strands the prior mid-refresh (the exact failure mode the
    round-1 compute-before-write fix exists to close).

    Every key and value must be a string matching the store's id pattern; every value
    must name an object actually in the graph; every key must be something the prior
    episode references — directly, in one of its reference-list fields, or transitively
    (`Graph.reachable_from(prior_id, reverse=False)` covers both: a reference list's
    members are its first hop). A key the prior doesn't reference isn't a replacement at
    all, just an unrelated pair riding along in the map.
    """
    reachable = g.reachable_from(prior["id"], reverse=False)
    for key in sorted(replacements, key=str):
        value = replacements[key]
        if not (isinstance(key, str) and _ID_RE.fullmatch(key)):
            raise ValidationError([f"replacements: key {key!r} is not a valid object id"])
        if not (isinstance(value, str) and _ID_RE.fullmatch(value)):
            raise ValidationError(
                [f"replacements: value {value!r} for key {key!r} is not a valid object id"]
            )
        if not g.has(value):
            raise ValidationError(
                [f"replacements: value {value!r} for key {key!r} is not in the graph"]
            )
        if key not in reachable:
            raise ValidationError(
                [f"replacements: key {key!r} is not referenced by episode {prior['id']!r}"]
            )


def affected_episodes(g: Graph, trigger_id: str) -> set[str]:
    """The ids of every `DecisionEpisode` reachable (by reference, transitively) from
    what `trigger_id` names as affected: the union of `Graph.reachable_from` over
    `RefreshTrigger.affected`, filtered to episodes.

    `reachable_from` is unfiltered graph reachability, so its raw union also picks up
    the trigger itself (it references its own `affected` list) and any `DecisionProgram`
    that lists a reached episode. Neither is a thing a refresh reopens — only an episode
    is — and only `DecisionEpisode` carries the `lifecycleState` design §7.7's "mark
    affected ... SUSPECT" transitions. Filtering to that type is what makes the result
    the set `open_refresh` (or a future Stage R caller) would actually act on. Named for
    what it returns, not for the raw graph primitive it's built from.

    An affected id that is missing from the graph, or an `affected` field that is not a
    list at all, contributes nothing rather than raising: the trigger may have been filed
    against an object that has since been removed, or hand-edited into a bad shape.
    """
    trigger = g.get(trigger_id)
    affected = trigger.get("affected")
    out: set[str] = set()
    if not isinstance(affected, list):
        return out
    for oid in affected:
        if not (isinstance(oid, str) and g.has(oid)):
            continue
        for reached in g.reachable_from(oid):
            if g.has(reached) and g.get(reached).get("type") == "DecisionEpisode":
                out.add(reached)
    return out


def _latest_episode(g: Graph, program: dict) -> dict:
    """The program's most recently listed live episode, or its most recent episode at
    all once every one of them has ended (SUPERSEDED/VOID)."""
    ids = program.get("episodes")
    eps = ([g.get(e) for e in ids if isinstance(e, str) and g.has(e)]
           if isinstance(ids, list) else [])
    if not eps:
        raise ValidationError([f"program {program.get('id')!r} names no episode to refresh"])
    live = [e for e in eps if e.get("lifecycleState") not in ("SUPERSEDED", "VOID")]
    return (live or eps)[-1]


def open_refresh(g: Graph, program_id: str, trigger_id: str, *, actor: dict, now: str,
                  replacements: dict[str, str] | None = None) -> dict:
    """Open a refresh episode for `program_id` in response to `trigger_id`.

    Computes and validates the entire successor episode — its id is free, its
    `sequence` is a real integer, every `replacements` key and value is a real id the
    prior episode actually references and that resolves to an object in the graph,
    every reference list resolved — *before* touching the graph at all. Only once all of
    that is known-good does the prior episode's `SUSPECT` transition (the first
    side-effecting write) happen, so a refusal on the new episode's shape — including a
    malformed `replacements` entry — never leaves the prior stranded mid-refresh with no
    successor. A `DRAFT` prior is refused outright: it was never live enough to need
    superseding, and — because `lifecycle.EDGES["DRAFT"]` has no `SUSPECT` or
    `SUPERSEDED` edge at all — marking one `SUSPECT` here would leave it permanently
    unable to ever reach `SUPERSEDED` either.

    Marks the program's latest live episode `SUSPECT` (a kernel transition — the
    conclusion belongs to the refresh engine, not to whoever called it) unless it is
    already `SUSPECT` (no self-edge to take; nothing to do). Creates a successor
    episode: `sequence + 1`, id `f"{base}-r{n}"`, `DRAFT`, `refreshedBecause` the
    trigger, `supersedes` the prior episode's id, `replacements` the map applied (so
    `diff_episodes` can read it back later), every non-cleared reference list copied
    across with `replacements` substituted in, and
    `runs`/`flipAnalyses`/`narratives`/`transitions` cleared. The one exception inside a
    carried-forward list is `risks`, which drops the bias indicators the *kernel*
    computed for the prior episode (`is_computed_bias_risk`) — they are conclusions
    about that episode and the successor recomputes its own. Appends the new episode to
    the program's `episodes` and the trigger to its `refreshTriggers`.

    `actor` must be human: a refresh reopens the model for G1 to approve again, and only
    a human may be the one who decided the record needed reopening — the kernel draws
    its own, narrower conclusion (`SUSPECT`) independently, below.
    """
    if not isinstance(actor, dict) or actor.get("actorType") != "human":
        raise AuthorityViolation("open_refresh requires a human actor")
    if not isinstance(program_id, str) or not g.has(program_id):
        raise ValidationError([f"program {program_id!r} is not in the graph"])
    if not isinstance(trigger_id, str) or not g.has(trigger_id):
        raise ValidationError([f"trigger {trigger_id!r} is not in the graph"])
    if replacements is None:
        replacements = {}
    elif isinstance(replacements, dict):
        replacements = dict(replacements)
    else:
        raise ValidationError(
            ["replacements: must be a dict mapping prior ids to replacing ids"]
        )
    program = g.get(program_id)
    trigger = g.get(trigger_id)
    prior = _latest_episode(g, program)

    if prior.get("lifecycleState") == "DRAFT":
        raise ValidationError(
            ["a draft episode has no standing to supersede; void it instead"]
        )

    seq = prior.get("sequence")
    if not isinstance(seq, int) or isinstance(seq, bool):
        raise ValidationError([f"{prior.get('id')!r}: sequence is not an integer"])
    n = seq + 1
    new_id = f"{_base_id(prior['id'])}-r{n}"
    if g.has(new_id):
        raise ValidationError(
            [f"{new_id!r} already exists in the graph; cannot open a refresh episode there"]
        )
    _validate_replacements(g, prior, replacements)

    new = {k: v for k, v in prior.items() if k not in ("readiness", "commitment", "plan")}
    new.update({"id": new_id, "rev": 1, "createdBy": actor, "createdAt": now, "sequence": n,
                "lifecycleState": "DRAFT", "refreshedBecause": trigger_id,
                "supersedes": prior["id"], "replacements": replacements,
                "asOf": trigger.get("detectedAt") or now, **CLEARED})
    for k in REF_LISTS:
        ids = prior.get(k)
        new[k] = [replacements.get(i, i) for i in ids] if isinstance(ids, list) else []
    # A bias indicator the kernel computed for the prior episode is a fact about the
    # prior episode. The successor's own `readiness_report` recomputes its indicators
    # from its own model; inheriting the predecessor's would leave `risks` holding one
    # stale entry per refresh, so a consumer reading `episode.risks` on a 2023 episode
    # would find indicators computed in 2020. Human-recorded Risks carry forward.
    new["risks"] = [i for i in new["risks"] if not is_computed_bias_risk(g, i)]

    # Everything above can fail on a malformed id, sequence or reference list without
    # writing anything. Only now, with the successor fully known-good, does the kernel
    # draw its own SUSPECT conclusion about the prior — the first side-effecting write.
    if prior.get("lifecycleState") != "SUSPECT":
        transition(g, prior["id"], "SUSPECT", KERNEL_ACTOR, now=now)

    stored = g.put(new, actor)
    triggers = program.get("refreshTriggers")
    triggers = triggers if isinstance(triggers, list) else []
    g.put({**program, "rev": program["rev"] + 1, "createdBy": actor, "createdAt": now,
           "episodes": (program.get("episodes") or []) + [stored["id"]],
           "refreshTriggers": sorted(set(triggers) | {trigger_id})}, actor)
    return stored


def supersede(g: Graph, prior_id: str, *, now: str) -> dict:
    """Kernel transition to `SUPERSEDED` — the refresh engine's own conclusion that the
    prior episode has ended, drawn separately from whatever opened its replacement.

    Valid from `SUSPECT` (the usual path, after `open_refresh`) or directly from
    `SIGNED` (design §5.2's edge table allows it; nothing in this module forces the
    `SUSPECT` detour on a caller who already knows the episode is done)."""
    return transition(g, prior_id, "SUPERSEDED", KERNEL_ACTOR, now=now)


def _ref_ids(ep: dict) -> set[str]:
    """The union of every id in `ep`'s non-cleared reference lists, tolerant of a list
    field that is missing, not a list, or holding a non-string entry."""
    out: set[str] = set()
    for k in REF_LISTS:
        v = ep.get(k)
        if isinstance(v, list):
            out.update(i for i in v if isinstance(i, str))
    return out


def _field_diff(g: Graph, old: str, new: str) -> list[dict]:
    """Field-by-field difference between `old` and `new`'s latest revisions, `[]` unless
    both exist and share a type — comparing a `Claim` to an `Assumption` it replaced
    would produce noise, not a diff."""
    if not (g.has(old) and g.has(new)):
        return []
    oo, on = g.get(old), g.get(new)
    if oo.get("type") != on.get("type"):
        return []
    out = []
    for f in sorted(set(oo) | set(on)):
        if f in _NON_CONTENT_FIELDS:
            continue
        if oo.get(f) != on.get(f):
            out.append({"object": f"{old}→{new}", "field": f,
                        "before": canonical_json(oo.get(f)), "after": canonical_json(on.get(f))})
    return out


def _ratings(g: Graph, ep: dict) -> dict[str, int | None]:
    """`{questionId: state}` from `ep`'s readiness report's StandardsAssessment, or `{}`
    if the episode has no readiness report, or the reference chain does not resolve."""
    readiness_id = ep.get("readiness")
    if not (isinstance(readiness_id, str) and g.has(readiness_id)):
        return {}
    sa_id = g.get(readiness_id).get("standardsAssessment")
    if not (isinstance(sa_id, str) and g.has(sa_id)):
        return {}
    ratings = g.get(sa_id).get("ratings")
    if not isinstance(ratings, list):
        return {}
    return {r["questionId"]: r["state"] for r in ratings
            if isinstance(r, dict) and "questionId" in r}


def _ranking(g: Graph, ep: dict) -> list[str]:
    """The ranking from `ep`'s last run, or `[]` if it has none / the run does not resolve."""
    runs = ep.get("runs")
    if not (isinstance(runs, list) and runs):
        return []
    last = runs[-1]
    if not (isinstance(last, str) and g.has(last)):
        return []
    ranking = g.get(last).get("ranking")
    return ranking if isinstance(ranking, list) else []


def diff_episodes(g: Graph, from_id: str, to_id: str, *, now: str) -> dict:
    """Build and store the `EpisodeDiff` from `from_id` to `to_id` (ICD 203 §D.6.e(7)).

    `added`/`removed` are reference-list ids present in only one episode. `changed` is
    field-by-field differences, paired from `to`'s `replacements` map (prior id ->
    replacing id) — never by sorting `added`/`removed` and zipping them together, which
    would silently mispair whenever a refresh makes two or more replacements whose
    alphabetical orders don't happen to line up. `pairing` records which happened:
    `"replacements"` when that map had entries to pair from, `"unknown"` when it was
    absent or empty (no pairing was attempted, and `changed` is `[]` from replacements —
    though see the module docstring for the same-id revision case, which is structurally
    still checked but never fires in Phase I). `judgmentsChanged`/`judgmentsConsistent`
    split `claims` by id membership only — **not** by comparing `text`/`supportedBy` at
    all, so a claim retained under the same id always reads `judgmentsConsistent` even
    if its content changed; see the module docstring. `ratingsChanged` compares the two
    episodes' StandardsAssessment ratings where both exist. `rankingBefore`/
    `rankingAfter` come from each episode's last run. Appends the diff id to every
    program that lists `to_id` among its episodes.

    Compute-then-write: the diff id's freedom (`g.has`) is checked and every linking
    program revision is built *before* the first `g.put`, so a refusal here — the diff
    id already taken, or nothing left to check — never leaves an `EpisodeDiff` written
    with no program pointing to it.
    """
    if not isinstance(from_id, str) or not g.has(from_id):
        raise ValidationError([f"episode {from_id!r} is not in the graph"])
    if not isinstance(to_id, str) or not g.has(to_id):
        raise ValidationError([f"episode {to_id!r} is not in the graph"])
    a, b = g.get(from_id), g.get(to_id)
    ids_a, ids_b = _ref_ids(a), _ref_ids(b)
    added, removed = sorted(ids_b - ids_a), sorted(ids_a - ids_b)

    changed = []
    replacements = b.get("replacements")
    pairing = "unknown"
    if isinstance(replacements, dict) and replacements:
        pairing = "replacements"
        for old, new in sorted(replacements.items()):
            if isinstance(old, str) and isinstance(new, str):
                changed.extend(_field_diff(g, old, new))
    # Same-id revision differences: structurally still checked (a future phase could
    # pin which revision an episode cited), but `oa`/`ob` are the same fetch from the
    # same graph today, so `oa["rev"] != ob["rev"]` never fires — see the module
    # docstring's Phase I limitation.
    for i in sorted(ids_a & ids_b):
        if not g.has(i):
            continue
        oa, ob = g.get(i), g.get(i)
        if oa["rev"] != ob["rev"]:
            for f in sorted(set(oa) | set(ob)):
                if f not in ("rev", "createdAt", "createdBy") and oa.get(f) != ob.get(f):
                    changed.append({"object": i, "field": f,
                                     "before": canonical_json(oa.get(f)),
                                     "after": canonical_json(ob.get(f))})

    claims_a = {c for c in (a.get("claims") or []) if isinstance(c, str)}
    claims_b = {c for c in (b.get("claims") or []) if isinstance(c, str)}
    judgments_changed: list[dict] = []
    judgments_consistent: list[str] = sorted(claims_a & claims_b)
    for c in sorted(claims_a - claims_b):
        before = g.get(c).get("text") if g.has(c) else None
        judgments_changed.append({"claim": c, "before": before, "after": None})
    for c in sorted(claims_b - claims_a):
        after = g.get(c).get("text") if g.has(c) else None
        judgments_changed.append({"claim": c, "before": None, "after": after})

    ra, rb = _ratings(g, a), _ratings(g, b)
    ratings_changed = [{"questionId": q, "before": ra[q], "after": rb[q]}
                        for q in sorted(set(ra) & set(rb)) if ra[q] != rb[q]]

    because = b.get("refreshedBecause")
    if not (isinstance(because, str) and because):
        raise ValidationError([f"episode {to_id!r} has no refreshedBecause trigger to diff"])

    diff_id = f"diff-{from_id}-{to_id}"
    if g.has(diff_id):
        raise ValidationError(
            [f"{diff_id!r} already exists in the graph; cannot record this diff there"]
        )
    d = {"id": diff_id, "type": "EpisodeDiff", "rev": 1,
         "createdBy": KERNEL_ACTOR, "createdAt": now, "from": from_id, "to": to_id,
         "because": because, "changed": changed, "added": added, "removed": removed,
         "judgmentsChanged": judgments_changed, "judgmentsConsistent": judgments_consistent,
         "ratingsChanged": ratings_changed, "rankingBefore": _ranking(g, a),
         "rankingAfter": _ranking(g, b), "pairing": pairing, "kernelVersion": KERNEL_VERSION}

    # Every linking revision this diff needs is built here, before the diff itself is
    # written — the same compute-then-write discipline `open_refresh` uses: a partially
    # applied refresh (a diff that exists but that no program points to) is exactly the
    # kind of stranded state a mid-function failure must not be able to produce.
    program_updates = [
        {**p, "rev": p["rev"] + 1, "createdBy": KERNEL_ACTOR, "createdAt": now,
         "diffs": p["diffs"] + [d["id"]]}
        for p in g.all("DecisionProgram")
        if isinstance(p.get("episodes"), list) and to_id in p["episodes"]
        and isinstance(p.get("diffs"), list)
    ]

    g.put(d, KERNEL_ACTOR)
    for update in program_updates:
        g.put(update, KERNEL_ACTOR)
    return d


def signer_return(g: Graph, episode_id: str, *, actor: dict, now: str, reason: str) -> dict:
    """The signer returns a package for rework — a human act, recorded, never silent.

    Files a human-authored `RefreshTrigger` of kind `signer-return` whose affected
    object is the episode, with the reason as its description, and appends it to every
    programme the episode belongs to. It rewrites no history: the package and the
    episode stay exactly as they were, and the programme's own G4 path (`open_refresh`)
    is how the rework becomes a new episode. Refuses a non-human actor
    (`AuthorityViolation`), an actor with no `actorId` to record as the `source`, a
    blank reason, and an episode that is not awaiting a signature (`ValidationError`)
    — a signed package cannot be sent back.

    The trigger names the *episode* in `affected`, not one of the objects inside it:
    what the signer is returning is the whole package. `affected_episodes` therefore
    reports nothing for it — `Graph.reachable_from` walks referrers and excludes the
    seed id itself, so an episode that names only itself reaches no episode — which is
    why `clock.signed_return_triggers` finds send-backs by kind and `affected`
    membership rather than through that helper.
    """
    if not isinstance(actor, dict) or actor.get("actorType") != "human":
        raise AuthorityViolation("signer_return requires a human actor")
    # `source` is who returned the package — a fact a reader of the queue and the
    # activity log is shown by name. An actor dict with no `actorId` would record the
    # string "None" there and read as a person called None, which is the same silent
    # stringification of a missing value this change removed from
    # `clock.signed_return_triggers`. Refuse it here, before anything is written.
    actor_id = actor.get("actorId")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValidationError(
            ["the actor has no actorId; a send-back records by name who returned the package"]
        )
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(["send back needs a named reason"])
    if not isinstance(episode_id, str) or not g.has(episode_id):
        raise ValidationError([f"episode {episode_id!r} is not in the graph"])
    ep = g.get(episode_id)
    if ep.get("lifecycleState") != "PENDING_SIGNATURE":
        raise ValidationError([
            f"episode {episode_id!r} is at {ep.get('lifecycleState')!r}; only a package "
            "awaiting a signature can be sent back"
        ])
    from docket.kernel.clock import programmes_of

    # `rt-return-{episode}-` followed by digits only, closed the way `commit`'s own
    # counter is: a bare prefix test lets `ep-1` count `rt-return-ep-1-r2-1` as its own,
    # and the next id it minted would collide with a send-back belonging to `ep-1-r2`.
    own = re.compile(rf"^rt-return-{re.escape(episode_id)}-\d+$")
    n = 1 + sum(1 for t in g.all("RefreshTrigger") if own.fullmatch(str(t.get("id", ""))))
    trigger = g.put({
        "id": f"rt-return-{episode_id}-{n}", "type": "RefreshTrigger", "rev": 1,
        "createdBy": actor, "createdAt": now, "kind": "signer-return",
        "source": actor_id, "description": reason.strip(),
        "detectedAt": now, "affected": [episode_id],
    }, actor)
    for prog in programmes_of(g, episode_id):
        existing = [t for t in (prog.get("refreshTriggers") or []) if isinstance(t, str)]
        g.put({**prog, "rev": prog["rev"] + 1, "createdBy": actor, "createdAt": now,
               "refreshTriggers": existing + [trigger["id"]]}, actor)
    return trigger


__all__ = ["affected_episodes", "diff_episodes", "is_computed_bias_risk",
           "open_refresh", "signer_return", "supersede"]
