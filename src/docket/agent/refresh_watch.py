# src/docket/agent/refresh_watch.py
"""Stage R: the refresh watch — deterministic, LLM-free detection of the things that can
make a decision record stale, and the `RefreshTrigger` objects an actor may file to say so.

`detect()` calls no backend and writes nothing. Every proposal it returns is a mechanical
translation of a `kernel.scope.check_scope` finding, or a plain, case-insensitive substring
match between an assumption's `indicatorsThatWouldAlter` and the title of Evidence the
episode has not yet registered. CLAUDE.md's boundary applies here exactly: the agent
proposes, a human decides. A `RefreshTrigger` is a proposal that something moved, not a
conclusion that the record is stale — only `kernel.refresh.open_refresh` (human-actor-only,
and never called from this module) actually reopens an episode, and only the kernel's own
transition ever marks one SUSPECT.

`file_trigger()`/`file_all()` write the triggers a caller chooses to file. `RefreshTrigger`
is not in `docket.objects.AGENT_FORBIDDEN_TYPES`, so an agent actor may file one — filing the
proposal is not the same act as opening the refresh, and the store's own authority boundary
(`Graph._check_agent_authority`) is what actually keeps an agent from doing the latter.

[ruling R11] `ModelUsePastPurpose` is deliberately absent from `FINDING_TO_KIND`: a model
used outside its intended question class is a defect the record already had at G1 (an
`Charter`/`Model` mismatch that was always there), not a signal that the world moved since
G1 passed. Filing a refresh trigger for it would reopen an episode to fix a mistake instead
of catching a change. [pre-flight defect 13] The plan text's editorial false start
("-> artefact-version-changed? No -> elapsed-time") is not reproduced here at all.
"""

from __future__ import annotations

import re
from typing import Any

from docket.errors import ValidationError
from docket.kernel.scope import check_scope
from docket.schema import catalogue
from docket.store import Graph

__all__ = ["FINDING_TO_KIND", "REFRESH_AFFECTED_TYPES", "VALID_KINDS", "detect",
           "file_trigger", "file_all"]

# [ruling R11] check_scope already implements both predicates this module maps onto a
# RefreshTrigger kind; the wording (and the AR 5-11 / GAO-23-106549 citations) comes from
# the finding's own `message`, never restated here. `ModelUsePastPurpose` has no entry —
# see the module docstring.
FINDING_TO_KIND: dict[str, str] = {
    "ReaccreditationRequired": "elapsed-time",   # AR 5-11 ¶4-2i(3), 3-year staleness
    "scope-lapsed": "evidence-changed",          # scopeOfValidity.validUntil has passed
}

# [pre-flight defects 14/16] Read from the catalogue rather than hand-copied, so a future
# change to RefreshTrigger's `kind` enum or `affected` ref list is picked up here for
# free — the same discipline `kernel/scope.py` applies to LEVELS and `elicit.py` applies
# to QUESTION_CLASSES. A private, import-time copy: `catalogue()` hands out a deep copy
# on every call.
_RT_FIELDS: dict[str, Any] = catalogue()["types"]["RefreshTrigger"]["fields"]
VALID_KINDS: frozenset[str] = frozenset(_RT_FIELDS["kind"]["enum"])
REFRESH_AFFECTED_TYPES: frozenset[str] = frozenset(_RT_FIELDS["affected"]["items"]["ref"])

#: Below this length a match is noise — "a" or "the" inside a title proves nothing about
#: an indicator [ruling R11's worked example].
_MIN_INDICATOR_LEN = 4


def _indicator_matches(needle: str, title: str) -> bool:
    """Case-insensitive match requiring a non-letter boundary (or string start/end) on
    both sides of `needle` within `title` — the same discipline `backend.py`'s own
    `DENYLIST`/`DOC_SCAN_DENYLIST` regexes apply to family-name matching [fix round 1,
    issue I1]. A bare substring test let indicator "rice" (>= `_MIN_INDICATOR_LEN`) fire
    on the "rice" inside "2026 Steel Price Index Update" (via "P-rice"); this still
    matches "Rice price index, 2026" (start-of-string / space boundary) and
    "rice-yield update" (start-of-string / hyphen boundary), because a hyphen and a
    string edge are both non-letters."""
    pattern = r"(?<![a-zA-Z])" + re.escape(needle) + r"(?![a-zA-Z])"
    return re.search(pattern, title, re.IGNORECASE) is not None


def _date_key(s: object) -> tuple[int, int, int] | None:
    """`YYYY`, `YYYY-MM`, or `YYYY-MM-DD` (a trailing `T...` dropped) -> `(y, m, d)`, or
    `None` for anything else. A private mirror of `kernel.scope._date_key` [pre-flight
    defect 14]: this module reads a date `check_scope` never itself parses
    (`Evidence.createdAt`), so it needs the same tolerant parser, not a second, subtly
    different one. Never raises: an unparsable value means "unknown", not "in scope."""
    if not isinstance(s, str):
        return None
    parts = s.split("T", 1)[0].split("-")
    if not 1 <= len(parts) <= 3:
        return None
    try:
        y = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 1
        d = int(parts[2]) if len(parts) > 2 else 1
    except ValueError:
        return None
    return (y, m, d)


def _scope_proposals(g: Graph, episode_id: str, now: str) -> list[dict]:
    """Map every `check_scope` finding whose rule is in `FINDING_TO_KIND` onto a
    proposal. A proposal whose `affected` list is empty once filtered to
    `REFRESH_AFFECTED_TYPES` is dropped entirely: an unaffected trigger is noise."""
    out: list[dict] = []
    for f in check_scope(g, episode_id):
        kind = FINDING_TO_KIND.get(f.rule)
        if kind is None:
            continue
        affected = [i for i in f.objects
                    if g.has(i) and g.get(i).get("type") in REFRESH_AFFECTED_TYPES]
        if not affected:
            continue
        out.append({"kind": kind, "source": f"kernel.scope.check_scope:{f.rule}",
                    "description": f.message, "detectedAt": now, "affected": affected})
    return out


def _candidate_evidence(g: Graph, ep: dict) -> list[dict]:
    """Evidence the episode has not yet registered, and that appeared after the
    episode's `asOf`. [pre-flight defect 15 / the brief's date discipline] An unparsable
    `asOf` or `createdAt` means "unknown," so the item is skipped rather than counted as
    new either way — the same convention `kernel/scope.py` applies to every date it
    cannot parse."""
    as_of_key = _date_key(ep.get("asOf"))
    if as_of_key is None:
        return []
    register = {i for i in (ep.get("evidenceRegister") or []) if isinstance(i, str)}
    out: list[dict] = []
    for ev in g.all("Evidence"):
        if ev["id"] in register:
            continue
        created_key = _date_key(ev.get("createdAt"))
        if created_key is None or created_key <= as_of_key:
            continue
        out.append(ev)
    return out


def _indicator_proposals(g: Graph, episode_id: str, now: str) -> list[dict]:
    """[ruling R11] The one predicate this module adds beyond `check_scope`: a
    case-insensitive, boundary-checked match ([fix round 1, issue I1] — see
    `_indicator_matches`) between an assumption's `indicatorsThatWouldAlter` and the
    title of Evidence the episode has not seen. `indicatorsThatWouldAlter` is a slot
    [pre-flight defect 15] and may hold a `{"$gap": ...}` marker (or any other non-list
    shape in a hand-edited store); anything that is not a `list` is skipped rather than
    iterated."""
    ep = g.get(episode_id)
    candidates = _candidate_evidence(g, ep)
    if not candidates:
        return []
    out: list[dict] = []
    for aid in ep.get("assumptions") or []:
        if not isinstance(aid, str) or not g.has(aid):
            continue
        a = g.get(aid)
        indicators = a.get("indicatorsThatWouldAlter")
        if not isinstance(indicators, list):
            continue
        for ev in candidates:
            title = str(ev.get("title") or "")
            for ind in indicators:
                if not isinstance(ind, str):
                    continue
                needle = ind.strip()
                if len(needle) < _MIN_INDICATOR_LEN or not _indicator_matches(needle, title):
                    continue
                out.append({
                    "kind": "indicator-detected",
                    "source": ev["id"],
                    "description": (
                        f"evidence {ev['id']!r} titled {ev['title']!r} matches an "
                        f"indicator that would alter assumption {a['id']}: {ind!r}"),
                    "detectedAt": now,
                    "affected": [a["id"], ev["id"]],
                })
    return out


def detect(g: Graph, program_id: str, *, now: str, episode_id: str | None = None) -> list[dict]:
    """Deterministic, LLM-free refresh-trigger proposals for `program_id` — or, if
    `episode_id` is given, for that one episode alone (the CLI resolves `--episode` to
    its program and passes both, per the interim ruling on the plan/CLI scope mismatch).

    Calls no backend and writes nothing: every entry is `{"kind", "source",
    "description", "detectedAt", "affected"}` and carries no envelope (no `id`, `rev`,
    `createdBy`) — it has not been filed, and giving it one would suggest otherwise.

    Sorted by `(kind, source, tuple(affected))` for determinism: the same graph and
    `now` always return byte-identical output, which is what lets a caller print
    proposals and then file exactly what it printed.
    """
    if not isinstance(program_id, str) or not g.has(program_id):
        raise ValidationError([f"program {program_id!r} is not in the graph"])
    program = g.get(program_id)
    episode_ids = [e for e in (program.get("episodes") or []) if isinstance(e, str)]
    if episode_id is not None:
        if not isinstance(episode_id, str) or not g.has(episode_id):
            raise ValidationError([f"episode {episode_id!r} is not in the graph"])
        episode_ids = [episode_id]

    proposals: list[dict] = []
    for eid in episode_ids:
        if not g.has(eid):
            continue
        proposals.extend(_scope_proposals(g, eid, now))
        proposals.extend(_indicator_proposals(g, eid, now))

    proposals.sort(key=lambda p: (p["kind"], p["source"], tuple(p["affected"])))
    return proposals


def file_trigger(g: Graph, program_id: str, *, kind: str, source: str, description: str,
                 detected_at: str, affected: list[str], actor: dict, now: str) -> dict:
    """Write a `RefreshTrigger` at `rt-{program_id}-{n}` and append it to
    `program["refreshTriggers"]`, in a new revision by `actor`.

    Agents MAY file a RefreshTrigger — it is a proposal that something moved, not a
    conclusion that the record is stale. `RefreshTrigger` is not in
    `docket.objects.AGENT_FORBIDDEN_TYPES`. Only a human may open the refresh
    (`kernel.refresh.open_refresh`, which this module never calls), and only the kernel
    may mark an episode SUSPECT.

    Refuses (`ValidationError`, before any write — compute-then-write, the same
    discipline `kernel.refresh.open_refresh` uses) an unknown `program_id`, an unknown
    `kind` (naming the seven valid kinds), a missing content field, or an `affected` id
    that is absent from the graph or not one of `REFRESH_AFFECTED_TYPES`
    [pre-flight defect 16: `description` and `detected_at` are catalogue-required and
    both are parameters here, unlike the plan overview's stale signature].
    """
    errors: list[str] = []
    if not isinstance(program_id, str) or not g.has(program_id):
        errors.append(f"program {program_id!r} is not in the graph")
    if kind not in VALID_KINDS:
        errors.append(f"kind {kind!r} is not a RefreshTrigger kind; valid kinds: "
                      f"{sorted(VALID_KINDS)}")
    if not isinstance(source, str) or not source:
        errors.append("source is required")
    if not isinstance(description, str) or not description:
        errors.append("description is required")
    if not isinstance(detected_at, str) or not detected_at:
        errors.append("detected_at is required")
    if not isinstance(affected, list) or not affected:
        errors.append("affected must be a non-empty list of object ids")
    else:
        for oid in affected:
            if not isinstance(oid, str) or not g.has(oid):
                errors.append(f"affected id {oid!r} is not in the graph")
            elif g.get(oid).get("type") not in REFRESH_AFFECTED_TYPES:
                errors.append(
                    f"affected id {oid!r} is a {g.get(oid).get('type')!r}, not one of "
                    f"{sorted(REFRESH_AFFECTED_TYPES)}")
    if errors:
        raise ValidationError(errors)

    program = g.get(program_id)
    existing = [i for i in (program.get("refreshTriggers") or []) if isinstance(i, str)]
    trigger_id = f"rt-{program_id}-{1 + len(existing)}"

    trigger = {
        "id": trigger_id, "type": "RefreshTrigger", "rev": 1, "createdBy": actor,
        "createdAt": now, "kind": kind, "source": source, "description": description,
        "detectedAt": detected_at, "affected": list(affected),
    }
    stored = g.put(trigger, actor)
    g.put({**program, "rev": program["rev"] + 1, "createdBy": actor, "createdAt": now,
          "refreshTriggers": existing + [trigger_id]}, actor)
    return stored


def file_all(g: Graph, program_id: str, proposals: list[dict], *, actor: dict,
            now: str) -> list[dict]:
    """`file_trigger` for every proposal in `proposals` (e.g. `detect(...)`'s own
    output), in order. Returns the stored triggers in the same order.

    Each proposal is filed with its own `file_trigger` call — an append-only write, like
    every other write in this store — so a refusal partway through leaves the earlier
    ones filed rather than rolling them back; a caller that wants all-or-nothing should
    validate every proposal against `VALID_KINDS`/`REFRESH_AFFECTED_TYPES` itself first.
    """
    return [
        file_trigger(g, program_id, kind=p["kind"], source=p["source"],
                    description=p["description"], detected_at=p["detectedAt"],
                    affected=p["affected"], actor=actor, now=now)
        for p in proposals
    ]
