# src/docket/agent/review.py
"""Gate G1 — the review sheet a human reads, and the three actions a human takes at it.

The human approval gate sits on the **model**, not the answer: after Stage E elicitation and
before a single number exists. This module is everything a reviewer needs to approve or
refuse that model, and the three writes that follow — confirm a gap, accept, reject.

**No backend call happens here, by design.** The sheet is derived from the graph alone. The
model already spoke at Stage E; asking it again at the gate would put a model's opinion
inside the human's decision, and a reviewer who cannot tell the model's proposal from the
model's summary of its own proposal is not reviewing anything. Everything on this sheet is
either a string copied out of a stored object or a predicate the kernel already runs.

**Nothing on this sheet is computed.** `g1_review` reads; it does not arithmetise. Every
numeral it prints is a numeral some object already holds (a `priorityRank` the model
proposed, a revision number the store assigned) or a fixed doctrine citation in the prose
below. There is no rating, no score, and no result at G1 — there cannot be, because G1 is
what has to pass before `evaluate()` may run at all.

**Every function that writes is human-only**, and refuses a non-human actor *before* it
touches the graph. `Graph.put` would refuse most of these writes anyway, three frames down,
with an error about `confirmedBy` or `reviewStatus`. Raising here instead means the message
names the boundary that was crossed rather than the field that happened to trip first.

Reading order of the sheet, and of this file: `g1_review` (structured — plan 07's API
returns this) → `g1_sheet` (Markdown, rendered from `g1_review`, nothing recomputed) →
`confirm_gaps` / `accept` / `reject`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from docket.errors import AuthorityViolation, ValidationError
from docket.kernel.lifecycle import CHECKS
from docket.kernel.queue import what_would_satisfy
from docket.kernel.validate import orphan_gaps
from docket.objects import (
    is_content,
    is_exclusion_ref,
    is_gap_ref,
    is_marker,
    iter_refs,
    iter_slots,
)
from docket.schema import catalogue
from docket.store import Graph

__all__ = [
    "G1_STATE",
    "GAP_MARK",
    "NUMERALS_IN_FIXED_PROSE",
    "RATING_RELEVANT_HEADING",
    "RATING_RELEVANT_LINE",
    "accept",
    "confirm_gaps",
    "g1_review",
    "g1_sheet",
    "reject",
]

#: The lifecycle state G1 guards. Read from here, never spelled twice.
G1_STATE = "MODEL_APPROVED"

GAP_MARK = "[gap]"
EXCLUDED_MARK = "[excluded]"
SILENT_MARK = "[nothing recorded]"

# ---- ruling R16: the rating-relevant section -------------------------------------------

RATING_RELEVANT_HEADING = "Model proposals that change how the record is scored"
RATING_RELEVANT_LINE = "these change how the record is scored."

#: The boundary claim, said plainly on the sheet so a reviewer can check it rather than
#: take it on trust. `kernel/evaluate.py` reads Observations and WeightSets and nothing
#: else; Stage E elicitation produces neither.
RATING_RELEVANT_BOUNDARY = (
    "No other model-authored value reaches a rating, and no model-authored value reaches a "
    "run, a result, a weight or an observation — evaluate() reads only Observations and "
    "WeightSets, and elicitation produces neither."
)

#: `priorityRank <= 3 -> primary` is **our convention**, applied by the elicitation mapper.
#: It is not a finding, not doctrine, and not something the source document says. It is on
#: the sheet as a convention so the human who confirms the ordering knows they are
#: confirming a convention as well as a rank.
PRIORITY_RANK_CONVENTION = (
    "convention (ours, not a finding): priorityRank <= 3 was mapped to priority "
    "\"primary\", above that to \"secondary\""
)

_WHY_PRIORITY_RANK = (
    "priority == \"primary\" is read by kernel/standards.py and by "
    "policy_rules.objective_measured, which is blocking. A model-chosen ordering moves a "
    "DES rating."
)
_WHY_BASELINE = (
    "read by policy_rules.baseline_present and by kernel/standards.py. DoDI 5000.84 "
    "§3.1.c requires a status-quo alternative; the model proposed which one it is."
)
_WHY_POINTER = (
    "the model wrote this citation. A pointer is not scored, but it is the one place a "
    "model string becomes a citation-shaped artefact — a URI or a custodian nobody checks "
    "reads exactly like a source that was consulted."
)

_OWN_PROSE_NUMERALS: tuple[str, ...] = (
    "1",           # G1
    "3",           # the priorityRank convention, and AR 5-11's three fields
    "4",           # AR 5-11 ¶4-5b
    "5",           # AR 5-11, and ¶4-5b
    "11",          # AR 5-11
    "5000",        # DoDI 5000.84 §3.1.c
    "84",          # DoDI 5000.84
)


def _check_docstring_numerals() -> frozenset[str]:
    """Numerals the gate's own docstrings bring onto the sheet.

    `whatWouldSatisfy` copies text out of `kernel/lifecycle.py`, so a check added in 03b
    whose docstring cites a numbered instruction would otherwise fail the no-computed-
    numbers guard for no real reason. Harvesting them from the same place the sheet reads
    them keeps the guard honest about what it is actually allowing.
    """
    found: set[str] = set()
    for _, check in CHECKS.get(G1_STATE, []):
        found |= set(re.findall(r"\d+", getattr(check, "__doc__", None) or ""))
    return frozenset(found)


#: Every numeral token that may appear on the rendered sheet without coming out of the
#: graph: this module's own doctrine citations, plus whatever the gate's check docstrings
#: cite. `tests/agent/test_review.py` tokenises the sheet and asserts every numeral is
#: either here or in the record — the guard behind "no computed numbers on this sheet".
NUMERALS_IN_FIXED_PROSE: tuple[str, ...] = tuple(
    sorted(set(_OWN_PROSE_NUMERALS) | _check_docstring_numerals())
)

_ALLOWED_REASON_TYPES: frozenset[str] = frozenset(
    catalogue()["types"]["Exclusion"]["fields"]["reasonType"]["enum"]
)

#: `kernel/bias.py` flags every Exclusion with `reasonType: "other"` as a selection-bias
#: indicator (`bias.py`, the `exclusion-reason-other` indicator). A rejection with a reason
#: we could have typed is a finding against us, so this module will not write one.
_REFUSED_REASON_TYPE = "other"

#: Frontend spec §4, "WHAT HAPPENS TO THE RECORD" — stated *before* the click. Formatted
#: per object, so the sentence names the actual id and the actual revision numbers.
_EFFECT_ACCEPT = (
    "a new revision (rev {rev} -> {next_rev}) authored by you; the model's confidence "
    "annotation is dropped unless you pass one, and ingestionProvenance is kept because "
    "where the text came from stays true"
)
_EFFECT_CONFIRM = (
    "confirmedBy gains your actor id and the date. The store refuses an agent that sets "
    "it, so the field's presence is your signature; the gate's gaps-confirmed check reads "
    "exactly this"
)
_EFFECT_REJECT: dict[str, str] = {
    "Evidence": (
        "reviewStatus becomes \"rejected\" and Exclusion {ex} is written against it. It "
        "stays in the evidence register — a rejected item that simply vanished is what "
        "policy_rules.silent_omission calls a blocking silent omission"
    ),
    "Alternative": (
        "status becomes \"screened-out\" with statusReason {ex} (policy_rules."
        "alternative_status_unreasoned is blocking without it), and Exclusion {ex} is "
        "written. It stays in the episode — an alternative that vanishes from the record "
        "is the failure this system exists to prevent"
    ),
    "Measure": (
        "Exclusion {ex} is written naming the reason. **The objective will still list "
        "this measure**: a Measure hangs off Objective.measures, not off any episode "
        "list, so nothing here can unhook it and policy_rules.objective_measured will go "
        "on counting it. To finish the job, revise the objective too: "
        "accept(objective, measures=[...]) without this id"
    ),
    "_default": (
        "Exclusion {ex} is written naming the type and the reason, and the id is dropped "
        "from {episodes}. The object itself is never deleted"
    ),
    #: Used when `_drop_from_episodes` would find nothing to change, so the pre-click
    #: promise cannot claim a removal that will not happen (frontend spec §4 field 6
    #: exists precisely so the record effect is stated truthfully *before* the click).
    "_nothing_dropped": (
        "Exclusion {ex} is written naming the type and the reason. **Nothing is dropped**: "
        "no episode list holds this id, so the object stays exactly where it is and only "
        "the exclusion records that you refused it"
    ),
}

#: The sentence the exclusions section carries for a rejected Measure, so the limitation
#: is on the sheet a reviewer reads and not only in a test docstring.
_MEASURE_EXCLUSION_NOTE = (
    "note: the objective still lists this measure — a Measure hangs off "
    "Objective.measures, not off an episode list, so policy_rules.objective_measured "
    "still counts it. Revise the objective with accept(objective, measures=[...]) to "
    "finish the job"
)


# ---- tolerant reading -------------------------------------------------------------------
#
# Same discipline as `kernel/lifecycle.py`: the sheet has to render over a store this
# process did not write. A dangling reference is skipped, a field of the wrong shape reads
# as absent, and nothing here raises on a graph's contents — only on being asked to review
# an episode that is not in the graph at all.


def _obj(g: Graph, ref: Any) -> dict | None:
    """The object `ref` names, or None — for any shape of `ref` at all."""
    if not isinstance(ref, str) or not g.has(ref):
        return None
    obj = g.get(ref)
    return obj if isinstance(obj, dict) else None


def _author(obj: dict | None) -> tuple[str | None, str | None]:
    """(actorType, actorId) of the revision in hand."""
    by = obj.get("createdBy") if isinstance(obj, dict) else None
    if not isinstance(by, dict):
        return None, None
    return by.get("actorType"), by.get("actorId")


def _prov(obj: dict | None) -> tuple[str | None, str | None, str | None]:
    """(sourceArtifact, locator, extractor) from `ingestionProvenance`, or three Nones."""
    prov = obj.get("ingestionProvenance") if isinstance(obj, dict) else None
    if not isinstance(prov, dict):
        return None, None, None
    return prov.get("sourceArtifact"), prov.get("locator"), prov.get("extractor")


def _text(value: Any) -> str:
    """A field rendered for a human: content, or a named silence — never `None`."""
    if is_gap_ref(value):
        return GAP_MARK
    if is_exclusion_ref(value):
        return EXCLUDED_MARK
    if not is_content(value):
        return SILENT_MARK
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(_text(v) for v in value)
    return json.dumps(value, sort_keys=True)


def _markers(value: Any, path: str = "") -> list[tuple[str, str, str]]:
    """Every `$gap` / `$exclusion` in `value`, as (path, kind, target id).

    A generic walk of the raw object rather than `iter_slots` alone: the catalogue marks
    most gap-bearing fields as slots, but a marker that lands in a non-slot field (an
    Evidence variant's `publisher`, say) is exactly the one a reviewer would otherwise
    never see. `iter_slots` still contributes — `declaredSlot` below says which of these
    paths the catalogue calls a slot.
    """
    if is_marker(value):
        kind = "gap" if is_gap_ref(value) else "exclusion"
        target = value.get("$gap") if kind == "gap" else value.get("$exclusion")
        return [(path, kind, target)] if isinstance(target, str) else []
    out: list[tuple[str, str, str]] = []
    if isinstance(value, dict):
        for k in sorted(value):
            out += _markers(value[k], f"{path}/{k}" if path else str(k))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            out += _markers(item, f"{path}/{i}" if path else str(i))
    return out


def _declared_slots(obj: dict) -> set[str]:
    try:
        return {path for path, _ in iter_slots(obj)}
    except Exception:
        return set()


def _scope(g: Graph, episode_id: str) -> list[str]:
    """The episode, everything it references transitively, and every orphan gap.

    Forward reachability first: G1 asks whether *this* record is sound, and another
    episode's broken charter is not this episode's concern.

    Then the gaps that hang off nothing. `elicit._emit_unattached_gaps` writes an
    `InsufficientEvidence` when the model reports having looked for something and routes
    it to a field that does not exist — the object is real, it says what was sought and
    why it was not found, and *nothing references it*, because no catalogue type has a
    field that can hold a free-standing gap. Scoping on reachability alone dropped it out
    of the sheet, out of `confirm_gaps`, and (before the matching kernel fix) out of the
    gate, so a record could be signed asserting every gap was confirmed by a human who
    was never shown one. An omission nobody can attribute belongs to everybody: same
    fail-safe the kernel applies to a label-only Exclusion. `kernel.lifecycle.orphan_gaps`
    is the single definition, shared with the gate so the two cannot disagree.
    """
    return sorted({episode_id} | g.reachable_from(episode_id, reverse=False)
                  | orphan_gaps(g))


def _ever_referenced(g: Graph, episode_id: str) -> set[str]:
    """Every id this episode has referenced in *any* of its revisions.

    `reject` drops a rejected id from the episode's list, which is what makes the omission
    real — but it also puts the rejected object out of forward reach, and an exclusion the
    sheet cannot find is a silent omission wearing a receipt. The store is append-only, so
    the earlier revisions are still there to be asked.
    """
    ever: set[str] = set()
    top = _obj(g, episode_id)
    if top is None or not isinstance(top.get("rev"), int):
        return ever
    for rev in range(1, top["rev"] + 1):
        try:
            past = g.get(episode_id, rev)
        except (KeyError, TypeError):
            continue
        ever |= {target for _, target in iter_refs(past)}
    return ever


# ---- one-line summaries -----------------------------------------------------------------


def _summary(obj: dict) -> str:
    """One line per object. Copied strings only; nothing here is computed or reworded."""
    t = obj.get("type")
    if t == "Charter":
        return _text(obj.get("question"))
    if t == "Objective":
        return f"{_text(obj.get('name'))} · {_text(obj.get('priority'))}"
    if t == "Alternative":
        return _text(obj.get("name"))
    if t in ("GroundRule", "Constraint", "Assumption"):
        return _text(obj.get("statement"))
    if t == "Evidence":
        classification = obj.get("classification")
        level = classification.get("level") if isinstance(classification, dict) else None
        return (f"{_text(obj.get('title'))} · {_text(level)} · "
                f"{_text(obj.get('reviewStatus'))}")
    if t == "InsufficientEvidence":
        return _text(obj.get("sought"))
    if t == "Exclusion":
        target = obj.get("target") if isinstance(obj.get("target"), dict) else {}
        return f"{_text(target.get('label'))} · {_text(obj.get('reasonType'))}"
    return f"{_text(t)} {_text(obj.get('id'))}"


def _gap_explanation(obj: dict) -> str:
    """The four `InsufficientEvidence` fields, laid out on one line.

    A gap is the one object whose *explanation is its content*: what was sought, where it
    was looked for, why it was not found, and what would resolve it. Recording that is
    more work than inventing a value, which is the point.
    """
    return (f"{_text(obj.get('sought'))} · looked in: "
            f"{_text(obj.get('whereLookedFor'))} · not found because: "
            f"{_text(obj.get('whyNotFound'))} · would be resolved by: "
            f"{_text(obj.get('indicatorsThatWouldResolve'))}")


def _explanation(obj: dict) -> str:
    """Amershi G11 — "make clear why the system did what it did", in one line.

    Precedence, and why:
    1. A gap explains itself with its four fields, whoever wrote the latest revision. A
       human confirming a gap does not stop it being a gap; `gaps[].confirmed` records the
       signature separately.
    2. Authorship next. A human-authored revision says "accepted by <you>" even if a stale
       `confidence` annotation is still on it, because saying "inferred" about a line a
       human wrote would be a lie about who decided. This line is what
       `charter-human-accepted` and `linchpins-human` are reading.
    3. Then the model's own confidence, naming the extractor and the locator, so the
       reviewer can go and look.
    """
    if obj.get("type") == "InsufficientEvidence":
        return _gap_explanation(obj)
    actor_type, actor_id = _author(obj)
    if actor_type == "human":
        return f"accepted by {_text(actor_id)}"
    if actor_type == "kernel":
        return f"computed by {_text(actor_id)}"
    _, locator, extractor = _prov(obj)
    confidence = obj.get("confidence")
    if confidence == "inferred":
        return f"inferred by {_text(extractor)} from {_text(locator)}"
    if confidence == "explicit":
        return f"quoted by {_text(extractor)} from {_text(locator)}"
    if confidence == "absent":
        # `absent` on a multi-field object is the *weakest* of its field annotations, so
        # it means "at least one field was not found", not "nothing was found". Saying the
        # stronger thing would understate what the model did read out of the source.
        return (f"at least one field was not found by {_text(extractor)} in "
                f"{_text(locator)} — the gap slots below say which")
    return f"proposed by {_text(actor_id)}"


def _if_wrong(obj: dict) -> dict:
    """Frontend spec §4 field 4. Copied from the object, or empty — never invented."""
    t = obj.get("type")
    if t == "Assumption":
        return {"statement": _text(obj.get("implicationsIfWrong")),
                "indicators": _list(obj.get("indicatorsThatWouldAlter"))}
    if t == "InsufficientEvidence":
        return {"statement": f"impact: {_text(obj.get('impact'))}",
                "indicators": _list(obj.get("indicatorsThatWouldResolve"))}
    if t == "Charter":
        return {"statement": _text(obj.get("consequencesOfErroneousOutput")),
                "indicators": []}
    if t == "Evidence":
        return {"statement": f"reviewStatus: {_text(obj.get('reviewStatus'))}",
                "indicators": []}
    return {"statement": None, "indicators": []}


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(v) for v in value]
    return []


#: Types `reject` refuses outright, and the remedy each refusal names. Offering a button
#: that writes an Exclusion and changes nothing else is worse than offering no button: the
#: store ends up asserting that something was excluded while it is still in force.
_REJECT_REFUSED: dict[str, str] = {
    "DecisionEpisode": (
        "an episode is not excluded from itself; abandon it with "
        "transition(..., 'VOID'), which records who abandoned it and when"
    ),
    "Charter": (
        "the episode's question is revised with accept(), not excluded — excluding it "
        "would leave the record without the question it answers. An episode that should "
        "not have been opened is abandoned with transition(..., 'VOID')"
    ),
    "Policy": (
        "the decision-class policy is the yardstick this record is measured against, not "
        "part of the model under review. Excluding it would leave the charter still "
        "naming it and still governed by it — including which exclusion reasons are "
        "prohibited. Change the governing policy on the charter instead"
    ),
    "InsufficientEvidence": (
        "a gap is confirmed, not excluded: use confirm_gaps(g, episode_id, actor, "
        "now=...). Rejecting one would write an exclusion saying an omission was excluded "
        "while the omission itself is still sitting in the slot, and 'gaps-confirmed' "
        "would stay unsatisfied for ever"
    ),
}

#: Types whose `reject` path revises the object itself, so the id deliberately stays in
#: the episode's list (and so a shared object needs no `episode_id` to disambiguate).
_REJECT_DEDICATED = ("Evidence", "Alternative")

#: Types the `Exclusion.target.kind` enum names directly. Rejecting one of these records a
#: typed omission that a reader can act on, so it is worth offering even where no episode
#: list changes — `Measure` is the case, and its record effect says plainly that nothing is
#: unhooked. Every other type falls back to `Category` [R15], and for those a reject is
#: only offered when it will actually remove the id from somewhere.
_TYPED_TARGET_KINDS = ("Alternative", "Evidence", "Measure", "Scenario")


def _would_drop(g: Graph, obj_id: Any) -> list[str]:
    """The episodes whose lists `reject` would actually change. Sorted, possibly empty."""
    return sorted(ep["id"] for ep in _episodes_holding(g, obj_id)
                  if any(isinstance(v, list) and obj_id in v for v in ep.values()))


def _actions(g: Graph, obj: dict) -> list[str]:
    """What *this module* will do to this object. Nothing aspirational is listed.

    `reject` is offered only where it does something: a type with a dedicated path
    (`Evidence`, `Alternative`), or an id some episode list actually holds. Everywhere
    else the reject would write an Exclusion and leave the object exactly where it was —
    a promise the record could not keep, and the frontend would have shown the promise
    before the click.
    """
    t = obj.get("type")
    if t in _REJECT_REFUSED and t != "InsufficientEvidence":
        # An episode moves by `kernel.lifecycle.transition`; a Charter is revised in
        # place; a Policy is governance, not model. None of them is accept-able from a
        # G1 sheet either, except the Charter — which is the whole point of the gate.
        return ["accept"] if t == "Charter" else []
    if t == "InsufficientEvidence":
        # Confirm and edit (frontend §4's "Confirm gap · Edit"), never reject.
        return ["confirm", "accept"] if not is_content(obj.get("confirmedBy")) else ["accept"]
    can_reject = t in _TYPED_TARGET_KINDS or bool(_would_drop(g, obj.get("id")))
    return ["accept", "reject"] if can_reject else ["accept"]


def _record_effect(g: Graph, obj: dict, actions: list[str]) -> dict[str, str]:
    """Frontend spec §4 field 6 — said before the click, echoed after.

    The sentence has to be true of *this* object in *this* graph, not true in general:
    which episodes lose the id, whether anything is dropped at all, and the fact that a
    rejected Measure stays on its objective. A pre-click promise that overstates what
    happens is worse than no promise, because the reviewer then believes the record says
    something it does not.
    """
    rev = obj.get("rev") if isinstance(obj.get("rev"), int) else 0
    oid = _text(obj.get("id"))
    obj_type = str(obj.get("type"))
    effects: dict[str, str] = {}
    for action in actions:
        if action == "accept":
            effects[action] = _EFFECT_ACCEPT.format(rev=rev, next_rev=rev + 1)
        elif action == "confirm":
            effects[action] = _EFFECT_CONFIRM
        elif action == "reject":
            dropped = _would_drop(g, obj.get("id"))
            if obj_type in _EFFECT_REJECT:
                template = _EFFECT_REJECT[obj_type]
            elif dropped:
                template = _EFFECT_REJECT["_default"]
            else:
                template = _EFFECT_REJECT["_nothing_dropped"]
            # [I6] Name every episode that loses the id. "the episode's list", singular,
            # hid the case where a second episode shares the object and loses it at this
            # episode's gate.
            if len(dropped) > 1:
                episodes = ("either " + " or ".join(dropped)
                            + " — this object is shared; you must pass episode_id=... to "
                              "say which, and only that one loses the id")
            else:
                episodes = ", ".join(dropped) if dropped else "no episode list"
            effects[action] = template.format(ex=f"ex-reject-{oid}", episodes=episodes)
    return effects


# ---- ruling R16 -------------------------------------------------------------------------


def _rating_relevant(g: Graph, ids: list[str]) -> list[dict]:
    """Model-proposed values that reach a rating, plus the model-written citations.

    Only objects whose *latest* revision is agent-authored: once a human has accepted an
    ordering, it is the human's ordering and belongs in the record, not on the list of
    things the human still has to look at.
    """
    out: list[dict] = []
    for oid in ids:
        obj = _obj(g, oid)
        if obj is None or _author(obj)[0] != "agent":
            continue
        t = obj.get("type")
        if t == "Objective" and obj.get("priorityRank") is not None:
            out.append({
                "objectId": oid, "objectType": t, "field": "priorityRank",
                "value": obj.get("priorityRank"), "kind": "rating",
                "derivedField": "priority", "derivedValue": _text(obj.get("priority")),
                "convention": PRIORITY_RANK_CONVENTION, "why": _WHY_PRIORITY_RANK,
                "readBy": ["kernel/standards.py", "policy_rules.objective_measured"],
                "summary": _summary(obj),
            })
        elif t == "Alternative" and isinstance(obj.get("baselineFlag"), bool):
            out.append({
                "objectId": oid, "objectType": t, "field": "baselineFlag",
                "value": obj.get("baselineFlag"), "kind": "rating",
                "derivedField": None, "derivedValue": None, "convention": None,
                "why": _WHY_BASELINE,
                "readBy": ["kernel/standards.py", "policy_rules.baseline_present"],
                "summary": _summary(obj),
            })
        elif t == "Evidence":
            pointer = obj.get("pointer")
            source_artifact, _, _ = _prov(obj)
            # The source-artifact entry's pointer is the caller's own argument, not a
            # model string; only the *other* evidence carries a citation the model wrote.
            if (isinstance(pointer, dict) and is_content(pointer)
                    and pointer.get("uri") != source_artifact):
                out.append({
                    "objectId": oid, "objectType": t, "field": "pointer",
                    "value": {"uri": pointer.get("uri"),
                              "custodian": pointer.get("custodian")},
                    "kind": "citation", "derivedField": None, "derivedValue": None,
                    "convention": None, "why": _WHY_POINTER,
                    "readBy": ["the reader of the record"],
                    "summary": _summary(obj),
                })
    return out


# ---- the structured sheet ----------------------------------------------------------------


def g1_review(g: Graph, episode_id: str) -> dict:
    """Everything a reviewer needs to approve or refuse the model, as data.

    Pure: reads the graph, writes nothing, computes nothing numeric. Plan 07's
    `GET /api/session/{s}/episode/{e}/g1` returns this; `g1_sheet` renders it as Markdown
    for the CLI and for a proposal figure. Deterministic — the same graph gives the same
    dict, ids in sorted order throughout.
    """
    episode = _obj(g, episode_id)
    if episode is None:
        raise ValidationError([f"episode {episode_id!r} is not in the graph"])

    ids = _scope(g, episode_id)
    ever = _ever_referenced(g, episode_id)
    scope_ids = set(ids)

    objects: list[dict] = []
    gap_attachments: dict[str, list[str]] = {}
    for oid in ids:
        obj = _obj(g, oid)
        if obj is None:                       # a dangling ref is skipped, never a traceback
            continue
        source_artifact, locator, extractor = _prov(obj)
        actor_type, _ = _author(obj)
        declared = _declared_slots(obj)
        slots = []
        for path, kind, target in _markers(obj):
            slots.append({"path": path, "kind": kind, "target": target,
                          "declaredSlot": path in declared})
            if kind == "gap":
                gap_attachments.setdefault(target, []).append(f"{oid}/{path}")
        actions = _actions(g, obj)
        objects.append({
            "id": oid,
            "type": obj.get("type"),
            "rev": obj.get("rev"),
            "authorType": actor_type,
            "confidence": obj.get("confidence"),
            "summary": _summary(obj),
            "sourceArtifact": source_artifact,
            "locator": locator,
            "extractor": extractor,
            "explanation": _explanation(obj),
            "ifWrong": _if_wrong(obj),
            "actions": actions,
            "recordEffect": _record_effect(g, obj, actions),
            "slots": slots,
        })

    gaps: list[dict] = []
    for oid in ids:
        obj = _obj(g, oid)
        if obj is None or obj.get("type") != "InsufficientEvidence":
            continue
        confirmed_by = obj.get("confirmedBy")
        attached_to = sorted(gap_attachments.get(oid, []))
        gaps.append({
            "id": oid,
            "sought": _text(obj.get("sought")),
            "whereLookedFor": _list(obj.get("whereLookedFor")),
            "whyNotFound": _text(obj.get("whyNotFound")),
            "indicatorsThatWouldResolve": _list(obj.get("indicatorsThatWouldResolve")),
            "impact": _text(obj.get("impact")),
            "confirmed": is_content(confirmed_by),
            "confirmedBy": confirmed_by if isinstance(confirmed_by, dict) else None,
            "attachedTo": attached_to,
            # An unattached gap is the model saying "I looked for this and could not find
            # it" about a field it could not name. It is still a gap and still needs a
            # human signature; it gets its own heading rather than being lost among the
            # ones that point at a slot.
            "attached": bool(attached_to),
            # True when this episode's reviewer may sign it: attached, or an orphan minted
            # by this episode's elicitation (id prefixed with the episode id).
            "confirmableHere": bool(attached_to) or oid.startswith(f"{episode_id}-"),
        })

    exclusions: list[dict] = []
    for excl in g.all("Exclusion"):
        target = excl.get("target") if isinstance(excl.get("target"), dict) else {}
        target_id = target.get("id")
        # Same scoping the kernel's own `silent_omission` uses: the exclusion is in reach,
        # or what it excludes is — extended with `ever`, because `reject` drops the
        # rejected id from the episode and the omission must survive its own recording.
        #
        # [M7] One narrowing versus the kernel: an unreachable exclusion whose target has
        # no `id` at all is not pulled onto a per-episode sheet, where the kernel treats
        # it as in scope for every policy. That is safe only because `reject` here is the
        # **only minter of Exclusions in `src/docket`**, and it always sets `target.id` —
        # so nothing this system writes can be dropped by the narrowing. A hand-authored
        # or imported label-only exclusion would be invisible per episode (it belongs to
        # no episode by construction) while the kernel still catches it store-wide. If a
        # second producer of Exclusions ever appears, revisit this line first.
        if excl.get("id") not in scope_ids and target_id not in scope_ids | ever:
            continue
        authority = excl.get("authority") if isinstance(excl.get("authority"), dict) else {}
        exclusions.append({
            "id": excl.get("id"),
            "targetKind": target.get("kind"),
            "targetId": target_id,
            "targetLabel": _text(target.get("label")),
            "reasonType": _text(excl.get("reasonType")),
            "reason": _text(excl.get("reason")),
            "authorityRole": authority.get("role"),
            "authorityWho": authority.get("who"),
            "retainedInStructure": excl.get("retainedInStructure"),
        })
    exclusions.sort(key=lambda e: str(e["id"]))

    # The checklist is *read from the gate*, never restated. If plan 03b adds or renames a
    # check, the sheet follows it for free and a reviewer never sees a checklist that
    # disagrees with the gate that will refuse them. `whatWouldSatisfy` is the check's own
    # docstring line, so even the remedy text comes from the gate.
    checks = [{"name": name,
               "satisfied": bool(check(g, episode)),
               "whatWouldSatisfy": what_would_satisfy(check, name, G1_STATE)}
              for name, check in CHECKS[G1_STATE]]

    return {
        "episode": episode_id,
        "lifecycleState": episode.get("lifecycleState"),
        "objects": objects,
        "gaps": gaps,
        "exclusions": exclusions,
        "ratingRelevant": _rating_relevant(g, ids),
        "ratingRelevantHeading": RATING_RELEVANT_HEADING,
        "ratingRelevantLine": RATING_RELEVANT_LINE,
        "ratingRelevantBoundary": RATING_RELEVANT_BOUNDARY,
        "checks": checks,
        "ready": all(c["satisfied"] for c in checks),
    }


# ---- the Markdown sheet -------------------------------------------------------------------


def _md_row(item: dict) -> list[str]:
    lines = [f"- **{item['summary']}** — `{item['id']}` (rev {item['rev']})",
             f"  - why: {item['explanation']}"]
    if item["sourceArtifact"] or item["locator"]:
        lines.append(f"  - source: {_text(item['sourceArtifact'])} — "
                     f"{_text(item['locator'])}")
    if item["ifWrong"]["statement"]:
        lines.append(f"  - if it is wrong: {item['ifWrong']['statement']}")
    for indicator in item["ifWrong"]["indicators"]:
        lines.append(f"    - would alter it: {indicator}")
    for slot in item["slots"]:
        lines.append(f"  - `{slot['path']}` is a {slot['kind']} → `{slot['target']}`")
    for action in item["actions"]:
        lines.append(f"  - you can **{action}**: {item['recordEffect'][action]}")
    return lines


#: The types the Markdown gives a named section to. Anything else falls through to the
#: catch-all, so no object can be built into `g1_review["objects"]` and then not printed.
_NAMED_SECTION_TYPES = ("Charter", "Objective", "Alternative", "GroundRule", "Constraint",
                        "Assumption", "Evidence")


def _md_gaps(gaps: list[dict]) -> list[str]:
    lines: list[str] = []
    for gap in gaps:
        lines += [
            f"- **{gap['sought']}** — `{gap['id']}` "
            f"({'confirmed' if gap['confirmed'] else 'NOT YET CONFIRMED'})",
            f"  - sought: {gap['sought']}",
            f"  - looked in: {'; '.join(gap['whereLookedFor']) or SILENT_MARK}",
            f"  - not found because: {gap['whyNotFound']}",
            "  - would be resolved by: "
            f"{'; '.join(gap['indicatorsThatWouldResolve']) or SILENT_MARK}",
            f"  - impact: {gap['impact']}",
            f"  - attached to: {'; '.join(gap['attachedTo']) or 'nothing — unattached'}",
        ]
    lines.append("")
    return lines


def _md_section(title: str, items: list[dict]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines += ["*Nothing of this kind is in the record.*", ""]
        return lines
    for item in items:
        lines += _md_row(item)
    lines.append("")
    return lines


def g1_sheet(g: Graph, episode_id: str) -> str:
    """The G1 review sheet as Markdown, rendered from `g1_review` and nothing else.

    Section order is the order a reviewer should read in: the question first, then what is
    being compared, then the rules the comparison runs under, then what is known, then what
    is *not* known, then what has been left out, then the model's rating-relevant
    proposals, and last the checklist that says whether the gate will open.

    Every numeral on this page is a copied string or a doctrine citation. Nothing is
    computed — there is nothing to compute yet, which is the whole argument for putting the
    human gate here.
    """
    review = g1_review(g, episode_id)
    by_type: dict[str, list[dict]] = {}
    for item in review["objects"]:
        by_type.setdefault(str(item["type"]), []).append(item)

    out: list[str] = [
        f"# G1 — approve the model: `{review['episode']}`", "",
        f"State: **{_text(review['lifecycleState'])}** · "
        f"gate: **{G1_STATE}** · ready: **{'yes' if review['ready'] else 'no'}**", "",
        "This is the model, before anything is computed. AR 5-11 ¶4-5b puts a human name "
        "against the question, the decision and the consequences of getting it wrong; "
        "everything below is what the model proposed for a human to accept, edit or "
        "refuse. Catching a wrong question here is cheap.", "",
    ]

    out += _md_section("Charter", by_type.get("Charter", []))
    out += _md_section("Objectives", by_type.get("Objective", []))
    out += _md_section("Alternatives", by_type.get("Alternative", []))
    out += _md_section(
        "Ground rules, constraints, assumptions",
        by_type.get("GroundRule", []) + by_type.get("Constraint", [])
        + by_type.get("Assumption", []),
    )
    out += _md_section("Evidence register", by_type.get("Evidence", []))

    # [I4] Everything the six named sections do not cover. Without this the sheet that
    # claims to be "everything a reviewer needs" quietly drops the governing Policy, and
    # would drop Scenarios, Measures and reliability steps the moment a DRAFT episode
    # carried them — an undeclared omission inside a review sheet, which is the exact
    # failure this product argues against. `DecisionEpisode` is the sheet's own subject
    # and `InsufficientEvidence` has two sections of its own below.
    rest = sorted(set(by_type) - set(_NAMED_SECTION_TYPES)
                  - {"DecisionEpisode", "InsufficientEvidence"})
    out += _md_section("Other objects in this record",
                       [item for name in rest for item in by_type[name]])

    attached = [gap for gap in review["gaps"] if gap["attached"]]
    unattached = [gap for gap in review["gaps"] if not gap["attached"]]

    out += ["## Gaps to confirm", "",
            # [M6] A gap a human fills by accepting a revision is no longer an omission,
            # so it leaves this list. Said here rather than left to be discovered.
            "Confirming a gap is you saying \"yes, this really is missing\". A gap you "
            "instead *fill* — by accepting a revision that supplies the value — leaves "
            "this list, and the earlier revision in the store still records that the "
            "model reported the field missing.", ""]
    if not attached:
        out += ["*No attached gap was recorded. On a real request that is itself worth "
                "a look.*", ""]
    out += _md_gaps(attached)

    out += ["## Unattached gaps", ""]
    if not unattached:
        out += ["*Every recorded gap points at a field.*", ""]
    else:
        out += ["The model reported looking for these and not finding them, but could not "
                "name a field to hang them on — so nothing in the record points at them. "
                "They are listed here because an omission nobody can attribute is still an "
                "omission, and the gate will not open until each one is confirmed. The "
                "\"not found because\" line carries the owner the model asked for.", ""]
        out += _md_gaps(unattached)
        foreign = [gap for gap in unattached if not gap.get("confirmableHere", True)]
        if foreign:
            out += ["The following unattached gaps were recorded by another episode's "
                    "elicitation and are not this episode's to confirm: "
                    + ", ".join(f"`{gap['id']}`" for gap in foreign)
                    + ". Confirm them at that episode's gate.", ""]

    out += ["## Exclusions", ""]
    if not review["exclusions"]:
        out += ["*Nothing has been left out of this record with a reason.*", ""]
    for excl in review["exclusions"]:
        out += [
            f"- **{excl['targetLabel']}** — `{excl['id']}` "
            f"({_text(excl['targetKind'])})",
            f"  - reason ({excl['reasonType']}): {excl['reason']}",
            f"  - authority: {_text(excl['authorityWho'])} as "
            f"{_text(excl['authorityRole'])}; retained in structure: "
            f"{'yes' if excl['retainedInStructure'] else 'NO — this is a deletion'}",
        ]
        if excl["targetKind"] == "Measure":
            out.append(f"  - {_MEASURE_EXCLUSION_NOTE}")
    out.append("")

    out += [f"## {RATING_RELEVANT_HEADING}", "",
            f"The model proposed the values below and {RATING_RELEVANT_LINE} "
            "Confirm each one, or change it.", "",
            RATING_RELEVANT_BOUNDARY, ""]
    if not review["ratingRelevant"]:
        out += ["*The model proposed no rating-relevant value in this record.*", ""]
    # The conventions are stated once, above the list, rather than repeated under every
    # row: a line a reviewer has already skipped nine times is a line they stop reading.
    # Each entry still carries its own `convention` in the dict, because the frontend
    # shows one object at a time.
    for convention in sorted({e["convention"] for e in review["ratingRelevant"]
                              if e["convention"]}):
        out += [f"- {convention}", ""]
    for entry in review["ratingRelevant"]:
        out += [
            f"- `{entry['objectId']}` **{entry['field']}** = "
            f"{_text(entry['value'])} — {entry['summary']}",
            f"  - why it is here: {entry['why']}",
            f"  - read by: {'; '.join(entry['readBy'])}",
        ]
        if entry["derivedField"]:
            out.append(f"  - the record therefore says {entry['derivedField']} = "
                       f"{entry['derivedValue']}")
    out.append("")

    out += ["## G1 checklist", "",
            "Read from `kernel.lifecycle.CHECKS` at render time, so this list cannot "
            "disagree with the gate that will refuse you.", ""]
    for check in review["checks"]:
        out += [f"- [{'x' if check['satisfied'] else ' '}] {check['name']}",
                f"  - what would satisfy it: {check['whatWouldSatisfy']}"]
    out += ["",
            f"**{'Ready' if review['ready'] else 'Not ready'}.** "
            "The gate is not this sheet: approving is "
            f"`kernel.lifecycle.transition(g, {review['episode']!r}, {G1_STATE!r}, "
            "actor, now=…)`, which records the attempt either way.", ""]
    return "\n".join(out)


# ---- the three human actions ---------------------------------------------------------------


def _human_only(actor: Any, what: str) -> None:
    """Refuse a non-human actor before the graph is touched.

    `Graph.put` would refuse most of these writes anyway — an agent may not set
    `confirmedBy`, may not move `Evidence.reviewStatus` off `draft`, may not claim
    Exclusion authority. Refusing here means the error names the boundary that was crossed
    instead of whichever field happened to trip first, and means a partial write is
    impossible: `reject` writes three objects, and two of them would land before the store
    noticed.
    """
    actor_type = actor.get("actorType") if isinstance(actor, dict) else None
    if actor_type != "human":
        raise AuthorityViolation(
            f"{what} is a human action at gate G1 and refuses actor actorType="
            f"{actor_type!r}; the approval gate sits on the model and only a human may "
            f"pass it"
        )
    # [M1] The whole point of the gate is that a *named* person accepted the model. An
    # actor with no `actorId` would write `confirmedBy: {"actorId": None}` or fall through
    # to a bare KeyError from the write below — an unsigned approval either way.
    if not is_content(actor.get("actorId")):
        raise AuthorityViolation(
            f"{what} needs an actor with an actorId: G1 records who accepted the model, "
            f"and an approval nobody signed is not an approval"
        )


def _must_exist(g: Graph, obj_id: Any) -> dict:
    obj = _obj(g, obj_id)
    if obj is None:
        raise ValidationError([f"{obj_id!r} is not in the graph"])
    return obj


def confirm_gaps(g: Graph, episode_id: str, actor: dict, *, now: str) -> list[str]:
    """Human: "yes, this really is missing." One new revision per unconfirmed gap.

    The store refuses an agent that sets `confirmedBy`, so the field's presence *is* the
    human's signature, and G1's `gaps-confirmed` check reads exactly this. Idempotent: a
    gap that already carries a confirmation is left alone rather than re-signed, so calling
    this twice does not fill the log with revisions that say nothing new.

    Returns the sorted ids actually confirmed by *this* call — an empty list means there
    was nothing left to sign, not that nothing happened.
    """
    _human_only(actor, "confirm_gaps")
    if _obj(g, episode_id) is None:
        raise ValidationError([f"episode {episode_id!r} is not in the graph"])
    confirmed: list[str] = []
    # An orphan gap is shown at every episode's gate (silence is forbidden), but it may be
    # SIGNED only by the reviewer of the episode that minted it: `elicit_into` prefixes the
    # ids it mints with the episode id, so an orphan whose id does not start with this
    # episode's prefix is another decision's omission, and a signature here would put this
    # reviewer's name on something they were never reviewing.
    orphans = orphan_gaps(g)
    for oid in _scope(g, episode_id):
        obj = _obj(g, oid)
        if obj is None or obj.get("type") != "InsufficientEvidence":
            continue
        if is_content(obj.get("confirmedBy")):
            continue
        if oid in orphans and not oid.startswith(f"{episode_id}-"):
            continue
        g.put({**obj, "rev": obj["rev"] + 1, "createdBy": actor, "createdAt": now,
               "confirmedBy": {"actorId": actor["actorId"], "date": now}}, actor)
        confirmed.append(oid)
    return sorted(confirmed)


def accept(g: Graph, obj_id: str, actor: dict, *, now: str, **edits: Any) -> dict:
    """Human: a new revision, authored by the human, with `edits` applied.

    Accepting *is* writing the revision. There is no lighter-weight "approve" that leaves
    the model's name on the object, because the two gate checks that matter here read
    authorship: `charter-human-accepted` wants a Charter whose latest revision a human
    wrote, and `linchpins-human` wants the same of every linchpin Assumption. A flag
    saying "a human looked at this" would be a claim about a person that the record could
    not check.

    Two field decisions:

    - **`confidence` is dropped** unless the caller passes one in `edits`. `confidence` is
      defined in the contract as an *agent annotation*; leaving `"inferred"` on a revision
      a human wrote would say a model inferred what a human decided.
    - **`ingestionProvenance` is kept.** It records where the text originally came from,
      which stays true no matter who revises it; `createdBy` records who wrote *this*
      revision. Both are wanted, and they answer different questions.

    Nothing else changes: the new revision is the old object plus `edits`, plus the three
    envelope fields the store requires.
    """
    _human_only(actor, "accept")
    obj = _must_exist(g, obj_id)
    new = {**obj, "rev": obj["rev"] + 1, "createdBy": actor, "createdAt": now, **edits}
    if "confidence" not in edits:
        new.pop("confidence", None)
    return g.put(new, actor)


def _episodes_holding(g: Graph, obj_id: str) -> list[dict]:
    """Every DecisionEpisode that references `obj_id`.

    Derived, not passed in, so the frontend's `POST /object/{id}/reject` route works with
    the id alone, as the spec has it.
    """
    out = []
    for ref in g.refs_to(obj_id):
        holder = _obj(g, ref)
        if holder is not None and holder.get("type") == "DecisionEpisode":
            out.append(holder)
    return out


def _drop_from_episodes(g: Graph, obj_id: str, actor: dict, now: str,
                        only: str | None = None) -> list[str]:
    """Remove `obj_id` from every list on every episode that holds it. Returns their ids.

    The object is not deleted and never will be: it stays in the store, at the revision it
    had, with an Exclusion naming it. What changes is that the episode stops claiming it as
    part of the model — which is what "rejected" has to mean if the word is to mean
    anything, and which is auditable because the store keeps the revision that still
    listed it.

    `only` restricts the change to one episode. Two episodes routinely share an object (an
    evidence register entry, or an objective carried into a re-run episode), and without
    this a rejection written about episode A would silently strip the object out of
    episode B under a reason that was never about B.
    """
    touched_episodes: list[str] = []
    for episode in _episodes_holding(g, obj_id):
        if only is not None and episode.get("id") != only:
            continue
        new = dict(episode)
        touched = False
        for key, value in episode.items():
            if isinstance(value, list) and obj_id in value:
                new[key] = [v for v in value if v != obj_id]
                touched = True
        if not touched:
            continue
        new.update(rev=episode["rev"] + 1, createdBy=actor, createdAt=now)
        g.put(new, actor)
        touched_episodes.append(episode["id"])
    return sorted(touched_episodes)


def _governing_policy(g: Graph, obj_id: str, episode_id: str | None) -> dict | None:
    """The decision-class Policy of an episode that holds `obj_id`, if one is resolvable.

    Reached the way the kernel reaches it: episode → charter → `decisionClassPolicy`. No
    new argument is needed, which matters because the frontend's reject route has only the
    object id.
    """
    holders = _episodes_holding(g, obj_id)
    if not holders:
        # A Measure hangs off an Objective, not an episode; walk up to whatever episode
        # reaches the object so the policy guard is not silently inert on such types.
        holders = [
            ep for ep in g.all("DecisionEpisode")
            if obj_id in g.reachable_from(ep.get("id"), reverse=False)
        ]
    if episode_id is not None:
        holders = [ep for ep in holders if ep.get("id") == episode_id] or holders
    for episode in holders:
        charter = _obj(g, episode.get("charter"))
        policy = _obj(g, charter.get("decisionClassPolicy")) if charter else None
        if policy is not None and policy.get("type") == "Policy":
            return policy
    return None


def reject(g: Graph, obj_id: str, actor: dict, *, now: str, reason: str,
           reason_type: str = "out-of-scope", episode_id: str | None = None) -> dict:
    """Human: refuse an object, as a first-class, typed omission — never a deletion.

    Returns the stored `Exclusion`, with one added key on the returned copy:
    `"$episodesTouched"`, the sorted ids of every episode that lost the id. It is not a
    stored field — `g.get(...)` will not have it, and putting the returned dict back would
    be refused by the schema, which is the failure you want if anyone tries. It is there so
    the caller can say what changed rather than having to guess.

    What happens depends on the type:

    - `Evidence` — a human revision with `reviewStatus: "rejected"`. It **stays** in
      `evidenceRegister`: an item that simply vanished is what
      `policy_rules.silent_omission` calls a blocking silent omission.
    - `Alternative` — a human revision with `status: "screened-out"` and `statusReason`
      naming the Exclusion (`policy_rules.alternative_status_unreasoned` is blocking
      without it). It **stays** in the episode — an alternative that vanishes from the
      record is the failure this system exists to prevent.
    - `Scenario` — the matching `target.kind`; the id leaves the episode's `scenarios`.
    - `Measure` — the matching `target.kind`, **and nothing else changes**: a Measure hangs
      off `Objective.measures`, not off any episode list, so this cannot unhook it and
      `policy_rules.objective_measured` goes on counting it. The sheet says so, before the
      click and again on the exclusion row. Finish the job with
      `accept(objective, measures=[...])`. Cascading into the objective from here would
      mean silently revising an object the human never named.
    - anything else — **[ruling R15]** `target.kind: "Category"`, with the object type in
      `target.label` and the id in `target.id`; the id leaves whichever episode list holds
      it. The enum does not grow for this.

    Refused outright: `DecisionEpisode`, `Charter`, `Policy`, `InsufficientEvidence` — each
    with the remedy named (see `_REJECT_REFUSED`).

    `reasonType` defaults to `out-of-scope`. It may never be `"other"` (`kernel/bias.py`
    treats it as a selection-bias indicator) and may never be one the governing policy
    lists in `prohibitedExclusionReasons` (`policy_rules.exclusion_prohibited_reason`
    emits a **blocking** finding for those). Writing either would be putting a finding
    against ourselves into the record on purpose.

    `episode_id` picks which episode loses the id when more than one holds the object. With
    several holders and no `episode_id`, the call is refused and names them: episode B
    should not lose an objective at episode A's gate, under a reason written about A.
    """
    _human_only(actor, "reject")
    if reason_type == _REFUSED_REASON_TYPE:
        raise ValidationError([
            "reasonType 'other' is refused here: kernel/bias.py treats it as a "
            "selection-bias indicator. Name the reason with one of "
            f"{sorted(_ALLOWED_REASON_TYPES - {_REFUSED_REASON_TYPE})}"
        ])
    if reason_type not in _ALLOWED_REASON_TYPES:
        raise ValidationError([f"{reason_type!r} is not an Exclusion reasonType"])
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(["reject() needs a reason; an untyped omission is the thing "
                               "this object exists to prevent"])
    obj = _must_exist(g, obj_id)
    obj_type = obj.get("type")
    if obj_type in _REJECT_REFUSED:
        raise ValidationError([f"a {obj_type} cannot be rejected: {_REJECT_REFUSED[obj_type]}"])

    # [M2] A double-click in the frontend deserves "already rejected by <who>", not the
    # store's append-only arithmetic.
    exclusion_id = f"ex-reject-{obj_id}"
    prior = _obj(g, exclusion_id)
    if prior is not None:
        authority = prior.get("authority") if isinstance(prior.get("authority"), dict) else {}
        raise ValidationError([
            f"{obj_id} was already rejected by {_text(authority.get('who'))} on "
            f"{_text(authority.get('date'))} ({exclusion_id}); "
            f"reason ({_text(prior.get('reasonType'))}): {_text(prior.get('reason'))}"
        ])

    # [I5] The policy the episode is actually governed by, not a hardcoded list.
    policy = _governing_policy(g, obj_id, episode_id)
    prohibited = (policy or {}).get("prohibitedExclusionReasons")
    if isinstance(prohibited, list) and reason_type in prohibited:
        raise ValidationError([
            f"reasonType {reason_type!r} is prohibited by policy "
            f"{_text((policy or {}).get('id'))} (prohibitedExclusionReasons); "
            f"policy_rules.exclusion_prohibited_reason would emit a blocking finding for "
            f"it — OAS AoA Handbook §4.7. Name a reason the policy allows"
        ])

    # [I6] Which episode loses the id.
    holders = [ep["id"] for ep in _episodes_holding(g, obj_id)]
    if episode_id is not None and episode_id not in holders:
        raise ValidationError([
            f"episode {episode_id!r} does not hold {obj_id}; it is held by "
            f"{sorted(holders) or 'no episode'}"
        ])
    if episode_id is None and len(set(holders)) > 1 and obj_type not in _REJECT_DEDICATED:
        raise ValidationError([
            f"{obj_id} is held by more than one episode ({sorted(set(holders))}); pass "
            f"episode_id=... to say which one is rejecting it. Rejecting it everywhere "
            f"would remove it from an episode under a reason that was never about that "
            f"episode"
        ])

    if obj_type == "Alternative":
        target = {"kind": "Alternative", "id": obj_id, "label": _text(obj.get("name"))}
    elif obj_type == "Evidence":
        target = {"kind": "Evidence", "id": obj_id, "label": _text(obj.get("title"))}
    elif obj_type in ("Scenario", "Measure"):
        target = {"kind": obj_type, "id": obj_id, "label": _summary(obj)}
    else:
        # [ruling R15] no enum member fits an Objective, an Assumption, a GroundRule or a
        # Constraint, so `Category` carries the type in the label and the id in `id`. The
        # label is what a reader of the exclusions section sees after the object has left
        # the episode's lists, so it has to say what was dropped, not just that something
        # was.
        target = {"kind": "Category", "id": obj_id,
                  "label": f"{_text(obj_type)}: {_summary(obj)}"}

    exclusion = g.put({
        "id": exclusion_id,
        "type": "Exclusion",
        "rev": 1,
        "createdBy": actor,
        "createdAt": now,
        "target": target,
        "reasonType": reason_type,
        "reason": reason,
        "authority": {"who": actor["actorId"], "role": "reviewer", "date": now},
        "retainedInStructure": True,
    }, actor)

    if obj_type == "Evidence":
        accept(g, obj_id, actor, now=now, reviewStatus="rejected")
        touched: list[str] = []
    elif obj_type == "Alternative":
        accept(g, obj_id, actor, now=now, status="screened-out",
               statusReason=exclusion["id"])
        touched = []
    else:
        touched = _drop_from_episodes(g, obj_id, actor, now, only=episode_id)
    # [I6] Not a stored field: the schema is `additionalProperties: false`, so putting this
    # dict back would be refused — loudly, which is the right failure. It is here so the
    # caller and the frontend can name what changed instead of inferring it.
    exclusion["$episodesTouched"] = touched
    return exclusion
