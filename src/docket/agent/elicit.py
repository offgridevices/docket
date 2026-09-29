# src/docket/agent/elicit.py
"""Stage E: structured elicitation of a decision request into DRAFT graph objects.

`elicit()` sends one request through a `Backend` against `ELICITATION_SCHEMA` and maps the
validated response onto DRAFT objects that `validate_object()` accepts. `elicit_into()` also
puts them, plus a DRAFT `DecisionEpisode`, into a `Graph`.

The agent never sits in the numeric path: this module produces no Observation, WeightSet,
Result, or measure value. The only two model-authored values that can ever move a rating are
`Objective.priorityRank` and `Alternative.baselineFlag`; they are copied verbatim (never
computed here) and are flagged as model-proposed, rating-relevant fields at the G1 gate
(ruling R16) — this module does not gate on them itself.

Every required non-slot field the model cannot supply is never invented. It comes from a
caller argument, a fixed constant, or (only for the source-artifact Evidence entry, when the
model's response has no `isSourceArtifact: true` item at all) `source_title` /
`source_custodian` / `source_classification` / `source_evidence_type`. Every other missing
required value becomes a `{"$gap": id}` reference plus a first-class `InsufficientEvidence`
object, and every `gaps[]` entry the model supplies is emitted — never dropped, even a second
entry sharing an `owner` with an earlier one (it is emitted unattached).

Conventions applied here (conventions, not findings — mirrored in
tests/fixtures/recorded/README.md, ruling R16):
- `priorityRank <= 3 -> priority: "primary"`, else `"secondary"`. The model chooses the rank;
  a human confirms it at G1, where it is flagged as rating-relevant.
- `Alternative.status = "candidate"` always — an agent may not screen anything out.
- `Assumption.variedInSensitivity = False` always — the model never claims a sensitivity
  analysis happened.
- `Evidence.classification.metadataLevel` = the same value as `classification.level` — the
  conservative reading; a human relaxes it at G1.
- `InsufficientEvidence.impact = "degrading"` for every gap this module creates — a human
  raises it to `"blocking"` at G1 if warranted.
- A synthesised source-artefact Evidence (only when the model's response has no
  `isSourceArtifact: true` item) is typed `source_evidence_type`, a caller kwarg defaulting
  to `"Document"` — a documented default, never an invented literal (ruling R4/I3).

Idempotency: `elicit()` is a pure function of its recorded input — the same request, backend
recording, and caller arguments produce byte-identical objects with the same ids every time.
`elicit_into()` guards against re-running into a graph that already holds some or all of
those ids: before the first `put`, it checks every generated object id and the episode id
against the graph with `g.has(...)` and refuses **all-or-nothing** (nothing is written) if
any collide, naming the colliding ids and, when an existing `DecisionEpisode` already
references one of them, that episode's id too. This is not request-specific — two entirely
different elicitations into the same graph can collide on the purely-ordinal ids
(`InsufficientEvidence`/`GroundRule`/`Constraint`), which is why those three id families are
scoped by `id_prefix` (an `elicit_into()`-only concern, set to `f"{episode_id}-"`) rather than
left to collide by accident; slug-derived ids (Charter, Objective, Alternative, Assumption,
Evidence) are not episode-scoped, so eliciting the same source artefact or the same named
objective into two different episodes is refused by the same all-or-nothing check, not
silently duplicated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docket.agent.prompts import system_prompt
from docket.errors import AuthorityViolation, ValidationError
from docket.objects import is_gap_ref
from docket.schema import catalogue

__all__ = ["ELICITATION_SCHEMA", "slug", "elicit", "elicit_into"]

# ---- the response schema --------------------------------------------------------------

QUESTION_CLASSES: list[str] = catalogue()["question_classes"]  # never hand-copy the enum
LEVELS: list[str] = catalogue()["classification_levels"]
EVIDENCE_TYPES: list[str] = [
    t for t in catalogue()["types"]["Evidence"]["fields"]["evidenceType"]["enum"]
    if t != "BudgetExhibit"  # the elicit schema omits it; its two extra required fields have
                             # no source and are not slots (see the mapping table, ruling R4)
]

CONFIDENCE_ENUM = ["explicit", "inferred", "absent"]

#: Every string field the model fills directly (as opposed to an item-level tag) is this
#: shape: a value the model may leave null, its confidence, and a locator into the request.
FIELD: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["value", "confidence", "locator"],
    "properties": {
        "value": {"type": ["string", "null"]},
        "confidence": {"enum": CONFIDENCE_ENUM},
        "locator": {"type": "string"},
    },
}

# Every array item also carries an item-level confidence/locator pair (the "envelope"
# confidence in the mapping table), independent of any FIELD-shaped sub-field's own tag.
_ITEM_ENVELOPE = {"confidence": {"enum": CONFIDENCE_ENUM}, "locator": {"type": "string"}}


def _item_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [*required, "confidence", "locator"],
        "properties": {**properties, **_ITEM_ENVELOPE},
    }


ELICITATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["charter", "objectives", "alternatives", "groundRules", "constraints",
                 "assumptions", "evidence", "gaps"],
    "properties": {
        "charter": {
            "type": "object",
            "additionalProperties": False,
            "required": ["question", "decisionToBeMade", "consequencesOfErroneousOutput",
                         "questionClass", "scopeIncluded", "scopeExcluded"],
            "properties": {
                "question": FIELD,
                "decisionToBeMade": FIELD,
                "consequencesOfErroneousOutput": FIELD,
                "questionClass": {"enum": QUESTION_CLASSES},
                "scopeIncluded": {"type": "array", "items": {"type": "string"}},
                "scopeExcluded": {"type": "array", "items": {"type": "string"}},
            },
        },
        "objectives": {
            "type": "array",
            "items": _item_schema(
                {
                    "name": {"type": "string"},
                    "priorityRank": {"type": ["integer", "null"]},
                    "provenanceText": {"type": "string"},
                },
                ["name", "priorityRank", "provenanceText"],
            ),
        },
        "alternatives": {
            "type": "array",
            "items": _item_schema(
                {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "isBaseline": {"type": "boolean"},
                },
                ["name", "description", "isBaseline"],
            ),
        },
        "groundRules": {
            "type": "array",
            "items": _item_schema({"statement": {"type": "string"}}, ["statement"]),
        },
        "constraints": {
            "type": "array",
            "items": _item_schema(
                {
                    "statement": {"type": "string"},
                    "kind": {"enum": ["physical", "programmatic", "policy", None]},
                    "implications": FIELD,
                },
                ["statement", "kind", "implications"],
            ),
        },
        "assumptions": {
            "type": "array",
            "items": _item_schema(
                {
                    "statement": {"type": "string"},
                    "linchpin": {"type": "boolean"},
                    "rationale": FIELD,
                    "implicationsIfWrong": FIELD,
                    "indicators": {"type": "array", "items": {"type": "string"}},
                    "evidenceTitle": {"type": ["string", "null"]},
                },
                ["statement", "linchpin", "rationale", "implicationsIfWrong", "indicators",
                 "evidenceTitle"],
            ),
        },
        "evidence": {
            "type": "array",
            "items": _item_schema(
                {
                    "title": {"type": "string"},
                    "evidenceType": {"enum": EVIDENCE_TYPES},
                    "isSourceArtifact": {"type": "boolean"},
                    "uri": {"type": ["string", "null"]},
                    "custodian": {"type": ["string", "null"]},
                    "publisher": {"type": ["string", "null"]},
                    "published": {"type": ["string", "null"]},
                    "builtToAnswer": {"type": ["string", "null"]},
                    "questionClass": {"enum": [*QUESTION_CLASSES, None]},
                    "intendedUse": {"type": ["string", "null"]},
                    "classificationLevel": {"enum": LEVELS},
                },
                ["title", "evidenceType", "isSourceArtifact", "uri", "custodian", "publisher",
                 "published", "builtToAnswer", "questionClass", "intendedUse",
                 "classificationLevel"],
            ),
        },
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["owner", "sought", "whereLookedFor", "whyNotFound",
                             "indicatorsThatWouldResolve"],
                "properties": {
                    "owner": {"type": "string"},
                    "sought": {"type": "string"},
                    "whereLookedFor": {
                        "type": "array", "items": {"type": "string"}, "minItems": 1,
                    },
                    "whyNotFound": {"type": "string"},
                    "indicatorsThatWouldResolve": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

# The user prompt deliberately contains no clock value: recording keys are computed over the
# prompt, and a date in the prompt would rot every fixture daily.
USER_TEMPLATE = (
    "Request (source artifact: {source_artifact}):\n"
    "---\n"
    "{request_text}\n"
    "---\n"
    'Policy id: {policy_id}. Produce the JSON object. For every required field you cannot '
    'support from the request, set value to null, confidence to "absent", and add a gaps[] '
    "entry whose owner names the field."
)

# ---- slug / id de-duplication [ruling R5] ----------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    """Lowercase, non-alphanumerics collapsed to '-', trimmed, <= 40 chars."""
    s = _SLUG_RE.sub("-", str(text).lower()).strip("-")[:40].strip("-")
    return s or "x"


def _unique(prefix: str, text: str, used: set[str]) -> str:
    """`slug` truncates at 40 characters, so two long, similar names collide and the second
    `put` would fail the store's append-only rev check. Suffix within one elicitation."""
    base = f"{prefix}{slug(text)}"
    oid, n = base, 1
    while oid in used:
        n += 1
        oid = f"{base}-{n}"
    used.add(oid)
    return oid


# ---- confidence -------------------------------------------------------------------------

_CONF_ORDER = {"absent": 0, "inferred": 1, "explicit": 2}


def _weakest(*confs: str) -> str:
    return min(confs, key=lambda c: _CONF_ORDER.get(c, 0))


# ---- context and envelope ----------------------------------------------------------------


@dataclass
class _Ctx:
    source_artifact: str
    extractor: str
    now: str
    actor: dict
    id_prefix: str = ""
    # owner -> every gaps[] entry the model filed under that owner, in response order. A
    # match consumes (pops) the head; anything left over after mapping is unattached [I2].
    gap_lookup: dict[str, list[dict]] = field(default_factory=dict)


def _envelope(oid: str, otype: str, ctx: _Ctx, *, locator: str,
              confidence: str | None = None, **fields: Any) -> dict:
    obj: dict[str, Any] = {
        "id": oid,
        "type": otype,
        "rev": 1,
        "createdBy": ctx.actor,
        "createdAt": ctx.now,
        "ingestionProvenance": {
            "sourceArtifact": ctx.source_artifact,
            "locator": locator or "(no locator given)",
            "extractor": ctx.extractor,
            "extractedAt": ctx.now,
        },
        **fields,
    }
    if confidence is not None:
        obj["confidence"] = confidence
    return obj


# ---- gaps ---------------------------------------------------------------------------------


def _make_gap(owner: str, gaps: list[dict], ctx: _Ctx, *, locator: str = "") -> str:
    """Create (and append to `gaps`) the InsufficientEvidence object for `owner`, returning
    its id. If the model supplied a matching `gaps[]` entry (by `owner`), the FIRST
    unconsumed one becomes the object (popped off `ctx.gap_lookup[owner]`, so a later
    duplicate on the same owner is left for `_emit_unattached_gaps` rather than reused or
    dropped [I2]); otherwise one is synthesised."""
    entries = ctx.gap_lookup.get(owner)
    entry = entries.pop(0) if entries else None
    gid = f"{ctx.id_prefix}gap-{len(gaps) + 1}"
    if entry is not None:
        sought = entry["sought"]
        where = entry["whereLookedFor"] or [ctx.source_artifact]
        why = entry["whyNotFound"]
        indicators = list(entry.get("indicatorsThatWouldResolve") or [])
    else:
        sought = f"a value for {owner}"
        where = [ctx.source_artifact]
        why = "model returned no value and no gap entry naming this field"
        indicators = []
    gaps.append(_envelope(
        gid, "InsufficientEvidence", ctx, locator=locator,
        sought=sought, whereLookedFor=where, whyNotFound=why, impact="degrading",
        indicatorsThatWouldResolve=indicators,
    ))
    return gid


def _field(item: dict, owner: str, gaps: list[dict], *, ctx: _Ctx) -> tuple[object, str]:
    """Return (content-or-gap-marker, confidence) for a {value, confidence, locator} field.

    A null value or `confidence: "absent"` becomes `{"$gap": id}`. If the model supplied a
    matching `gaps[]` entry (by `owner`), that entry becomes the InsufficientEvidence object;
    otherwise one is synthesised with `whyNotFound: "model returned no value and no gap entry
    naming this field"` and `impact: "degrading"`.
    """
    value = item.get("value")
    confidence = item.get("confidence", "absent")
    if value is None or confidence == "absent":
        gid = _make_gap(owner, gaps, ctx, locator=item.get("locator") or "")
        return {"$gap": gid}, "absent"
    return value, confidence


def _emit_unattached_gaps(gaps: list[dict], ctx: _Ctx) -> None:
    """Every `gaps[]` entry the model filed that never matched a field is still emitted,
    never dropped — including every entry beyond the first sharing an `owner` with one that
    did match [I2]. It is unattached to any object; `whyNotFound` names the owner the model
    aimed it at, so the G1 sheet can say what the model meant, not just "unattached" [M3]."""
    for owner, entries in ctx.gap_lookup.items():
        for entry in entries:
            gid = f"{ctx.id_prefix}gap-{len(gaps) + 1}"
            why = (f"{entry['whyNotFound']} (model routed this to {owner!r}, which matched "
                   f"no field)")
            gaps.append(_envelope(
                gid, "InsufficientEvidence", ctx, locator="",
                sought=entry["sought"],
                whereLookedFor=entry["whereLookedFor"] or [ctx.source_artifact],
                whyNotFound=why, impact="degrading",
                indicatorsThatWouldResolve=list(entry.get("indicatorsThatWouldResolve") or []),
            ))


# ---- Evidence -----------------------------------------------------------------------------


def _variant_required_fields(evidence_type: str) -> list[str]:
    spec = catalogue()["types"]["Evidence"]["variants"].get(evidence_type, {})
    return [k for k, v in (spec.get("fields") or {}).items()
            if isinstance(v, dict) and v.get("required")]


def _evidence_scope(built: str | None, qclass: str | None, intended: str | None,
                     owner_prefix: str, gaps: list[dict], ctx: _Ctx, *,
                     locator: str) -> object:
    """`scopeOfValidity` is a whole-object slot: if any of the three is missing, the whole
    object becomes a gap [ruling R4]."""
    if built and qclass and intended:
        return {"builtToAnswer": built, "questionClass": qclass, "intendedUse": intended}
    gid = _make_gap(f"{owner_prefix}.scopeOfValidity", gaps, ctx, locator=locator)
    return {"$gap": gid}


def _variant_extra_fields(evidence_type: str, item: dict, owner_prefix: str,
                           gaps: list[dict], ctx: _Ctx, *, locator: str) -> dict:
    """Every variant-specific required field the elicit schema has no source for becomes a
    gap, except `Document.publisher`/`.published`, which come from the model when given."""
    out: dict[str, Any] = {}
    for fname in _variant_required_fields(evidence_type):
        value = item.get(fname) if evidence_type == "Document" else None
        if value:
            out[fname] = value
        else:
            out[fname] = {"$gap": _make_gap(f"{owner_prefix}.{fname}", gaps, ctx,
                                             locator=locator)}
    return out


def _build_evidence_item(item: dict, idx: int, is_source: bool, *, source_artifact: str,
                          source_custodian: str, gaps: list[dict], ctx: _Ctx,
                          used_ids: set[str]) -> dict:
    owner_prefix = f"evidence:{idx}"
    locator = item.get("locator") or ""
    evidence_type = item["evidenceType"]

    if is_source:
        oid = f"ev-src-{slug(Path(source_artifact).stem)}"
        used_ids.add(oid)
        pointer = {"uri": source_artifact, "custodian": source_custodian}
    else:
        oid = _unique("ev-", item["title"], used_ids)
        uri, custodian = item.get("uri"), item.get("custodian")
        if uri and custodian:
            pointer = {"uri": uri, "custodian": custodian}
        else:
            gid = _make_gap(f"{owner_prefix}.pointer", gaps, ctx, locator=locator)
            pointer = {"$gap": gid}

    level = item["classificationLevel"]
    scope = _evidence_scope(item.get("builtToAnswer"), item.get("questionClass"),
                             item.get("intendedUse"), owner_prefix, gaps, ctx, locator=locator)
    reliability_gid = _make_gap(f"{owner_prefix}.reliabilitySteps", gaps, ctx, locator=locator)
    variant_fields = _variant_extra_fields(evidence_type, item, owner_prefix, gaps, ctx,
                                           locator=locator)

    return _envelope(
        oid, "Evidence", ctx, locator=locator, confidence=item.get("confidence"),
        title=item["title"], evidenceType=evidence_type, pointer=pointer,
        classification={"level": level, "metadataLevel": level},
        scopeOfValidity=scope, reviewStatus="draft",
        reliabilitySteps={"$gap": reliability_gid},
        **variant_fields,
    )


def _synthesise_source_evidence(*, source_artifact: str, source_title: str | None,
                                 source_custodian: str, source_classification: str,
                                 source_evidence_type: str, gaps: list[dict], ctx: _Ctx,
                                 used_ids: set[str]) -> dict:
    """The model's response had no `isSourceArtifact: true` evidence item. GroundRule.source
    / Constraint.source / Objective.provenance all point at the source-artifact Evidence, so
    one must exist regardless; it is built entirely from caller-supplied, documented
    defaults, never invented content — including its type, `source_evidence_type`
    (default `"Document"`) [ruling R4/I3]."""
    oid = f"ev-src-{slug(Path(source_artifact).stem)}"
    used_ids.add(oid)
    owner_prefix = "evidence:src"
    scope_gid = _make_gap(f"{owner_prefix}.scopeOfValidity", gaps, ctx)
    reliability_gid = _make_gap(f"{owner_prefix}.reliabilitySteps", gaps, ctx)
    variant_fields = _variant_extra_fields(source_evidence_type, {}, owner_prefix, gaps, ctx,
                                           locator="")
    return _envelope(
        oid, "Evidence", ctx, locator="", confidence="absent",
        title=source_title or source_artifact, evidenceType=source_evidence_type,
        pointer={"uri": source_artifact, "custodian": source_custodian},
        classification={"level": source_classification, "metadataLevel": source_classification},
        scopeOfValidity={"$gap": scope_gid}, reviewStatus="draft",
        reliabilitySteps={"$gap": reliability_gid},
        **variant_fields,
    )


# ---- the mapper -----------------------------------------------------------------------


def elicit(backend, *, request_text: str, policy_id: str, actor: dict, now: str,
           source_artifact: str, requested_by: str,
           source_title: str | None = None,
           source_custodian: str = "docket repository (sources/)",
           source_classification: str = "U",
           source_evidence_type: str = "Document",
           id_prefix: str = "") -> list[dict]:
    """Elicit DRAFT objects from `request_text` via `backend`. Does NOT put them — the
    caller does, so tests can inspect. Returns objects in dependency order: gaps, then the
    source-artifact Evidence, then other Evidence, then Charter, Objectives, Alternatives,
    GroundRules, Constraints, Assumptions.

    `id_prefix` scopes the purely-ordinal ids (`InsufficientEvidence`/`GroundRule`/
    `Constraint`) so that two elicitations sharing a graph do not collide on them; it is an
    `elicit_into()`-only concern (set to `f"{episode_id}-"`) and defaults to unscoped for
    direct callers.
    """
    if actor.get("actorType") != "agent":
        raise AuthorityViolation(
            f"elicit() produces DRAFT proposals only and refuses actor "
            f"actorType={actor.get('actorType')!r}; only an agent actor may call it"
        )
    actor_id = actor.get("actorId")
    if not isinstance(actor_id, str) or not actor_id.startswith("agent:"):
        raise AuthorityViolation(
            f"elicit() requires createdBy.actorId of the form 'agent:<model>' (the ledger's "
            f"actor-id convention); got {actor_id!r}"
        )
    if not requested_by or not requested_by.strip():
        raise ValidationError(
            ["requested_by must not be blank: it becomes Charter.authority.signer, a "
             "required non-slot field with no other source (ruling R4)"]
        )

    system = system_prompt()
    user = USER_TEMPLATE.format(source_artifact=source_artifact, request_text=request_text,
                                 policy_id=policy_id)
    resp = backend.complete_json(system=system, user=user, schema=ELICITATION_SCHEMA)

    ctx = _Ctx(source_artifact=source_artifact, extractor=backend.extractor, now=now,
               actor=actor, id_prefix=id_prefix)
    for g in resp.get("gaps", []):
        ctx.gap_lookup.setdefault(g["owner"], []).append(g)

    used_ids: set[str] = set()
    gaps: list[dict] = []

    # -- Evidence: source artifact, then the rest, in the model's own order/index.
    evidence_items = resp.get("evidence", [])
    source_idx = next((i for i, it in enumerate(evidence_items)
                        if it.get("isSourceArtifact")), None)

    if source_idx is not None:
        source_evidence = _build_evidence_item(
            evidence_items[source_idx], source_idx, True,
            source_artifact=source_artifact, source_custodian=source_custodian,
            gaps=gaps, ctx=ctx, used_ids=used_ids,
        )
    else:
        source_evidence = _synthesise_source_evidence(
            source_artifact=source_artifact, source_title=source_title,
            source_custodian=source_custodian, source_classification=source_classification,
            source_evidence_type=source_evidence_type,
            gaps=gaps, ctx=ctx, used_ids=used_ids,
        )
    source_evidence_id = source_evidence["id"]

    other_evidence: list[dict] = []
    title_to_evidence_id: dict[str, str] = {source_evidence["title"]: source_evidence_id}
    for idx, item in enumerate(evidence_items):
        if idx == source_idx:
            continue
        obj = _build_evidence_item(
            item, idx, False, source_artifact=source_artifact,
            source_custodian=source_custodian, gaps=gaps, ctx=ctx, used_ids=used_ids,
        )
        other_evidence.append(obj)
        title_to_evidence_id.setdefault(item["title"], obj["id"])

    # -- Charter
    charter_resp = resp["charter"]
    q_content, q_conf = _field(charter_resp["question"], "charter.question", gaps, ctx=ctx)
    d_content, d_conf = _field(charter_resp["decisionToBeMade"], "charter.decisionToBeMade",
                                gaps, ctx=ctx)
    c_content, c_conf = _field(charter_resp["consequencesOfErroneousOutput"],
                                "charter.consequencesOfErroneousOutput", gaps, ctx=ctx)
    charter_locator = (charter_resp["question"].get("locator")
                        or charter_resp["decisionToBeMade"].get("locator")
                        or charter_resp["consequencesOfErroneousOutput"].get("locator") or "")
    if is_gap_ref(q_content):
        charter_id = _unique("ch-", Path(source_artifact).stem, used_ids)
    else:
        charter_id = _unique("ch-", q_content, used_ids)
    charter_obj = _envelope(
        charter_id, "Charter", ctx, locator=charter_locator,
        confidence=_weakest(q_conf, d_conf, c_conf),
        question=q_content, decisionToBeMade=d_content,
        consequencesOfErroneousOutput=c_content,
        questionClass=charter_resp["questionClass"],
        scope={"included": list(charter_resp.get("scopeIncluded") or []),
               "excluded": list(charter_resp.get("scopeExcluded") or [])},
        authority={"signer": requested_by},
        decisionClassPolicy=policy_id,
    )

    # -- Objectives
    objectives: list[dict] = []
    for o in resp.get("objectives", []):
        oid = _unique("obj-", o["name"], used_ids)
        rank = o.get("priorityRank")
        priority = "primary" if (rank is not None and rank <= 3) else "secondary"
        extra = {"priorityRank": rank} if rank is not None else {}
        objectives.append(_envelope(
            oid, "Objective", ctx, locator=o.get("locator") or "", confidence=o.get("confidence"),
            name=o["name"], priority=priority, provenance=source_evidence_id, **extra,
        ))

    # -- Alternatives
    alternatives: list[dict] = []
    for a in resp.get("alternatives", []):
        aid = _unique("alt-", a["name"], used_ids)
        alternatives.append(_envelope(
            aid, "Alternative", ctx, locator=a.get("locator") or "", confidence=a.get("confidence"),
            name=a["name"], description=a["description"], status="candidate",
            baselineFlag=bool(a["isBaseline"]),
        ))

    # -- GroundRules
    groundrules: list[dict] = []
    for idx, gr in enumerate(resp.get("groundRules", [])):
        gid = f"{ctx.id_prefix}gr-{idx + 1}"
        groundrules.append(_envelope(
            gid, "GroundRule", ctx, locator=gr.get("locator") or "",
            confidence=gr.get("confidence"),
            statement=gr["statement"], source=source_evidence_id,
        ))

    # -- Constraints
    constraints: list[dict] = []
    for idx, c in enumerate(resp.get("constraints", [])):
        cid = f"{ctx.id_prefix}con-{idx + 1}"
        kind = c.get("kind")
        confidence = c.get("confidence") if kind else "inferred"
        kind = kind or "policy"
        implications_content, _ = _field(c["implications"], f"constraint:{idx}.implications",
                                          gaps, ctx=ctx)
        constraints.append(_envelope(
            cid, "Constraint", ctx, locator=c.get("locator") or "", confidence=confidence,
            statement=c["statement"], kind=kind, source=source_evidence_id,
            implications=implications_content,
        ))

    # -- Assumptions
    assumptions: list[dict] = []
    for idx, a in enumerate(resp.get("assumptions", [])):
        aid = _unique("as-", a["statement"], used_ids)
        locator = a.get("locator") or ""
        rationale_content, _ = _field(a["rationale"], f"assumption:{idx}.rationale", gaps,
                                       ctx=ctx)
        impl_content, _ = _field(a["implicationsIfWrong"], f"assumption:{idx}.implicationsIfWrong",
                                  gaps, ctx=ctx)
        indicators = list(a.get("indicators") or [])
        if indicators:
            indicators_content: object = indicators
        else:
            gid = _make_gap(f"assumption:{idx}.indicatorsThatWouldAlter", gaps, ctx,
                             locator=locator)
            indicators_content = {"$gap": gid}
        evidence_title = a.get("evidenceTitle")
        evidence_id = title_to_evidence_id.get(evidence_title) if evidence_title else None
        if evidence_id is not None:
            evidence_content: object = evidence_id
        else:
            gid = _make_gap(f"assumption:{idx}.evidence", gaps, ctx, locator=locator)
            evidence_content = {"$gap": gid}
        assumptions.append(_envelope(
            aid, "Assumption", ctx, locator=locator, confidence=a.get("confidence"),
            statement=a["statement"], linchpin=bool(a["linchpin"]),
            rationale=rationale_content, evidence=evidence_content,
            implicationsIfWrong=impl_content, indicatorsThatWouldAlter=indicators_content,
            variedInSensitivity=False,
        ))

    _emit_unattached_gaps(gaps, ctx)

    return [*gaps, source_evidence, *other_evidence, charter_obj, *objectives, *alternatives,
            *groundrules, *constraints, *assumptions]


_EPISODE_REF_FIELDS = ("charter", "objectives", "alternatives", "groundRules", "constraints",
                       "assumptions", "evidenceRegister")


def _find_referencing_episode(g, colliding_ids: set[str]) -> str | None:
    """The id of an existing `DecisionEpisode` that already references one of
    `colliding_ids`, or `None`. Used to make an all-or-nothing refusal name not just the
    colliding ids but the episode a caller would otherwise silently corrupt [I1]."""
    for ep in g.all("DecisionEpisode"):
        refs: set[str] = set()
        for fname in _EPISODE_REF_FIELDS:
            v = ep.get(fname)
            if isinstance(v, str):
                refs.add(v)
            elif isinstance(v, list):
                refs.update(x for x in v if isinstance(x, str))
        if refs & colliding_ids:
            return ep["id"]
    return None


def elicit_into(g, backend, *, request_text: str, policy_id: str, actor: dict, now: str,
                 source_artifact: str, requested_by: str, episode_id: str,
                 sequence: int = 1, as_of: str | None = None, program: str | None = None,
                 **source_kw: Any) -> dict:
    """`elicit()` plus: put everything, put a DRAFT `DecisionEpisode` at `episode_id`, and
    return the stored episode.

    All-or-nothing [ruling I1]: `elicit()` is called with `id_prefix=f"{episode_id}-"` so
    the purely-ordinal ids it mints do not collide with another episode's, and then every
    generated id plus `episode_id` is checked against `g` with `g.has(...)` *before* the
    first `put`. If any already exist, nothing is written and the refusal names every
    colliding id and, when an existing `DecisionEpisode` already references one of them,
    that episode's id too — the store is append-only, so writing some-but-not-all of these
    objects would leave permanent, unremovable orphans.
    """
    objs = elicit(backend, request_text=request_text, policy_id=policy_id, actor=actor,
                   now=now, source_artifact=source_artifact, requested_by=requested_by,
                   id_prefix=f"{episode_id}-", **source_kw)

    all_ids = [o["id"] for o in objs] + [episode_id]
    colliding = [oid for oid in all_ids if g.has(oid)]
    if colliding:
        ref_episode = _find_referencing_episode(g, set(colliding))
        msg = (f"elicit_into refuses to write ({episode_id!r}): the following id(s) "
               f"already exist in the graph, so the write is refused all-or-nothing "
               f"(nothing was written): {colliding}")
        if ref_episode is not None:
            msg += f"; already referenced by existing episode {ref_episode!r}"
        raise ValidationError([msg])

    for o in objs:
        g.put(o, actor)

    by_type: dict[str, list[str]] = {}
    for o in objs:
        by_type.setdefault(o["type"], []).append(o["id"])

    ctx = _Ctx(source_artifact=source_artifact, extractor=backend.extractor, now=now,
               actor=actor)
    episode: dict[str, Any] = _envelope(
        episode_id, "DecisionEpisode", ctx, locator="",
        sequence=sequence,
        asOf=as_of or now,
        charter=by_type.get("Charter", [None])[0],
        lifecycleState="DRAFT",
        transitions=[],
        objectives=by_type.get("Objective", []),
        alternatives=by_type.get("Alternative", []),
        groundRules=by_type.get("GroundRule", []),
        constraints=by_type.get("Constraint", []),
        assumptions=by_type.get("Assumption", []),
        evidenceRegister=by_type.get("Evidence", []),
        scenarios=[],
        claims=[],
        risks=[],
        biasChecks=[],
        mandateElements=[],
        observations=[],
        weightSets=[],
        models=[],
        runs=[],
        flipAnalyses=[],
        narratives=[],
    )
    if program is not None:
        episode["program"] = program

    return g.put(episode, actor)
