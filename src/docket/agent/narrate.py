# src/docket/agent/narrate.py
"""Stage N: the agent drafts narrative prose for one Decision Package section.

`narrate()` builds a *context pack* — ids and copied kernel/record values, straight off
the graph, never computed here — asks the backend for sentences with `cites`, and runs
`kernel.render.check_citations` on the draft **before** anything is written. A draft that
fails is fed back to the model, verbatim, with the renderer's own error text (which names
the offending sentence) appended to the *original* prompt; the context pack itself never
changes between attempts, so the ids and values on offer stay exactly what was offered the
first time. Only a draft that survives `check_citations` unmodified is ever stored, and it
is stored exactly as the model wrote it: this module does not "fix up" a rejected sentence,
round a number, or invent a citation on the model's behalf.

The agent never sits in the numeric path (CLAUDE.md). A narrative sentence may *quote* a
number the kernel or the record already computed and stored; it may not introduce one. The
one and only place a numeral may legitimately come from is the context pack, and the
context pack is itself nothing but a filtered, verbatim copy of fields already sitting on
graph objects — `check_citations` is the actual enforcement (it re-reads the cited objects
from the graph, not from anything this module hands back), so a wrong or fabricated numeral
is rejected regardless of how the context pack happened to be built.

`context_pack()` is section-scoped, on purpose: a narrator asked to write the
`evaluation-results` section is shown evaluation results and nothing else, so it cannot
smuggle in a number from, say, the readiness report just because that number happens to sit
somewhere in the graph. A slot holding a `{"$gap": id}` or `{"$exclusion": id}` marker is
passed through as the marker itself, never flattened into prose — the model sees exactly
the same P3 structure a human reviewer would, and the excluded/gapped id becomes its own
citable pack entry (`marker_target`) rather than disappearing.

A never-clean draft (every attempt, out to the fixed retry cap, still fails
`check_citations`) raises `docket.errors.UncitedSentenceError` — the structured form, with
`narrative_id` and `sentence` set — and writes nothing at all: no partial Narrative, no
episode revision. `render_package`'s own `UncitedSentenceError` (raised later, if a bad
Narrative ever reached the graph some other way) is the same exception type for the same
reason: a citation failure is a citation failure, wherever it is caught.
"""

from __future__ import annotations

import re
from typing import Any

from docket.agent.dispatch import read_back
from docket.agent.prompts import load_prompt
from docket.canon import canonical_json
from docket.errors import UncitedSentenceError, ValidationError
from docket.kernel.render import SECTIONS, check_citations
from docket.objects import marker_target
from docket.store import Graph

__all__ = [
    "CITATION_RULE",
    "NARRATIVE_SCHEMA",
    "PARTS",
    "RENDERINGS",
    "VALID_SECTIONS",
    "context_pack",
    "narrate",
    "retry_prompt",
    "system_prompt",
    "user_prompt",
]

#: The dict `narrate()` returns: the stored `Narrative` object exactly as `Graph.put`
#: wrote it. Not a distinct runtime type — this codebase's other agent stages
#: (`elicit()`, `dispatch()`, `read_back()`) all return plain dicts too — but named so a
#: caller's own type hints can say what shape to expect.
NarrateResult = dict[str, Any]

#: The 16 package sections a `Narrative.section` may name (design §10, `objects.yaml`'s
#: `package_sections`). Imported from the renderer rather than restated, so the two lists
#: cannot drift apart. `context_pack()` refuses anything outside this set by name; only
#: six of the sixteen have a context-pack builder below (the others return `{}` — nothing
#: to narrate against — rather than raising, since the section name itself is still a
#: valid one).
VALID_SECTIONS: tuple[str, ...] = tuple(key for key, _ in SECTIONS)

#: One retry loop, capped, on top of `Backend.complete_json`'s own (separate) schema-retry
#: loop. Two attempts to correct a citation failure, three attempts total — the brief's
#: cap. Not a parameter: exposing it would let a caller silently loosen the bound the
#: fixtures below are written against.
MAX_RETRIES = 2

#: `{"sentences": [{"text": ..., "cites": [...]}]}` — the only shape the backend may
#: return. `additionalProperties: False` at both levels, `minItems` on both arrays: an
#: empty narrative or a citation-less sentence is a schema failure, not something
#: `check_citations` has to catch.
NARRATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sentences"],
    "properties": {
        "sentences": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "cites"],
                "properties": {
                    "text": {"type": "string", "minLength": 1},
                    "cites": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    },
}

#: This module's own prompt-part order — distinct from `docket.agent.prompts.PARTS`
#: (Stage E's list, substituted into `elicitation-system.md`). `authority` is shared
#: verbatim between the two stages (the same five capabilities and five refusals apply
#: to a narrator as to an elicitor) and stays first; `narrate/citation-rule` is this
#: stage's own addition, registered at the end. It lives in a subdirectory
#: (`prompts/narrate/citation-rule.md`) rather than beside the Stage-E parts so that
#: `tests/agent/test_prompts.py`'s directory-listing and placeholder-substitution checks
#: — which are about `elicitation-system.md` and its own `PARTS` — are not touched by a
#: file neither of them ever loads.
PARTS: tuple[str, ...] = ("authority", "narrate/citation-rule")

#: Kept as a public constant, matching the brief's naming, even though `system_prompt()`
#: below composes it from `PARTS` rather than concatenating it inline: a caller (or a
#: test) that wants "the rule text alone" without `authority.md` in front of it can read
#: this instead of reaching into the prompts directory itself.
CITATION_RULE: str = load_prompt("narrate/citation-rule")


def system_prompt() -> str:
    """`authority.md` plus this stage's citation rule, in `PARTS` order."""
    return "\n\n".join(load_prompt(p) for p in PARTS)


# ---- context pack -----------------------------------------------------------------


def _obj(g: Graph, ref: object) -> dict | None:
    """The object `ref` names, or `None` for any shape of `ref` at all — the same
    tolerant-resolution pattern `render.py`/`readiness.py`/`plan.py` each keep their own
    copy of. A context pack must never raise over a dangling reference; it just leaves
    that object out."""
    if not isinstance(ref, str) or not g.has(ref):
        return None
    o = g.get(ref)
    return o if isinstance(o, dict) else None


def _ref_ids(ids: object) -> list[str]:
    return [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []


def _copy_fields(o: dict, fields: tuple[str, ...]) -> dict:
    """`{field: o[field]}` for every `field` actually present on `o` — a slot holding a
    `$gap`/`$exclusion` marker, or plain content, is copied through unchanged either way;
    this function never inspects or flattens the value, only selects which keys travel."""
    return {f: o[f] for f in fields if f in o}


#: The two renderings `render_package`/`build_package` know (design §7.8). Restated here
#: rather than imported from `api.routes.kernel` (another agent's module, and the wrong
#: dependency direction for `agent/` to take on `api/`) — this is the same closed pair,
#: just named locally.
RENDERINGS: tuple[str, ...] = ("full", "unclassified")


def _withheld(g: Graph, ev_id: object, rendering: str) -> bool:
    """Whether a value backed by evidence `ev_id` must be kept out of the context pack
    under `rendering` — identical rule to `kernel.render._withheld`: only under
    `unclassified`, and only when the evidence's *value* classification level is
    anything other than `U`. This is the one place graph content reaches a live,
    potentially hosted model backend [ruling I2] — `dispatch()`/`read_back()` stay
    internal to the kernel/agent boundary — so the default below is the safe one."""
    if rendering == "full" or not isinstance(ev_id, str) or not g.has(ev_id):
        return False
    return g.get(ev_id)["classification"]["level"] != "U"


def _obs_by_alt(g: Graph, ep: dict) -> dict[str, list[dict]]:
    """Every `Observation` on the episode, grouped by the alternative it observed —
    mirrors `render_package`'s own `obs_by_alt`, needed for the identical aggregate-
    Result taint rule (`_evaluation_results_pack` below)."""
    out: dict[str, list[dict]] = {}
    for oid in _ref_ids(ep.get("observations")):
        o = _obj(g, oid)
        if o is not None:
            out.setdefault(o.get("alternative"), []).append(o)
    return out


def _tainted_level(g: Graph, alt: object, obs_by_alt: dict[str, list[dict]],
                    rendering: str) -> str | None:
    """The classification level that makes an aggregate Result for `alt` unsafe to
    quote verbatim under `rendering` — the same taint rule
    `render._evaluation_results_body`/`_cite_withheld_level` apply to a `Result`: an
    aggregate is tainted by *any* observation behind the same alternative, regardless
    of measure. `None` means the value is safe to show as-is."""
    for o in obs_by_alt.get(alt, []):
        ev = o.get("evidence")
        if _withheld(g, ev, rendering):
            return g.get(ev)["classification"]["level"]
    return None


def _pull_marker_target(g: Graph, pack: dict[str, dict], value: object) -> None:
    """If `value` is a `$gap`/`$exclusion` marker whose target resolves, add that target
    as its own pack entry — a P3 marker is passed through where it sits (never flattened
    into prose), but the object it points at still needs to be citable in its own right,
    or a narrator could describe a gap without ever having an id to cite for it."""
    target = marker_target(value)
    if target is None:
        return
    t = _obj(g, target)
    if t is None:
        return
    if t.get("type") == "InsufficientEvidence":
        pack[target] = _copy_fields(t, ("sought", "whereLookedFor", "whyNotFound", "impact"))
    elif t.get("type") == "Exclusion":
        pack[target] = _copy_fields(t, ("reasonType", "reason", "target"))


def _problem_statement_pack(g: Graph, ep: dict, rendering: str) -> dict[str, dict]:
    ch = _obj(g, ep.get("charter"))
    if ch is None:
        return {}
    fields = ("question", "decisionToBeMade", "consequencesOfErroneousOutput",
              "questionClass", "scope", "definitions")
    entry = _copy_fields(ch, fields)
    pack = {ch["id"]: entry}
    for f in ("question", "decisionToBeMade", "consequencesOfErroneousOutput"):
        if f in entry:
            _pull_marker_target(g, pack, entry[f])
    return pack


def _evaluation_results_pack(g: Graph, ep: dict, rendering: str) -> dict[str, dict]:
    """[ruling I2] An aggregate Result tainted by even one non-`U` observation behind
    the same alternative — the identical rule `render._evaluation_results_body` applies
    — is shown with `value` replaced by the `[withheld: <level>]` marker, never the real
    number and never a stub number a model could paste into a sentence as though it
    were real. `alternative`/`units` stay visible: neither is itself a classified value."""
    obs_by_alt = _obs_by_alt(g, ep)
    pack: dict[str, dict] = {}
    for run_id in sorted(_ref_ids(ep.get("runs"))):
        if not g.has(run_id):
            continue
        rb = read_back(g, run_id)
        pack[run_id] = {"ranking": rb["ranking"]}
        for res_id, res in sorted(rb["results"].items()):
            if not res.get("aggregate"):
                continue
            level = _tainted_level(g, res.get("alternative"), obs_by_alt, rendering)
            value = f"[withheld: {level}]" if level is not None else res["value"]
            pack[res_id] = {"alternative": res["alternative"], "value": value,
                            "units": res["units"]}
    return pack


def _what_flips_pack(g: Graph, ep: dict, rendering: str) -> dict[str, dict]:
    pack: dict[str, dict] = {}
    for run_id in sorted(_ref_ids(ep.get("runs"))):
        if not g.has(run_id):
            continue
        rb = read_back(g, run_id)
        for f in rb["flips"]:
            fid = f["id"]
            pack[fid] = {"label": f["label"], "flipThreshold": f["flipThreshold"],
                        "flipDistance": f["flipDistance"], "direction": f["direction"]}
            fa = _obj(g, fid)
            a = _obj(g, fa.get("assumption")) if fa is not None else None
            if a is not None:
                pack[a["id"]] = _copy_fields(a, ("statement",))
    return pack


def _readiness_pack(g: Graph, ep: dict, rendering: str) -> dict[str, dict]:
    rr = _obj(g, ep.get("readiness"))
    if rr is None:
        return {}
    pack = {rr["id"]: _copy_fields(rr, ("ready", "blockers", "warnings", "openGaps"))}
    sa = _obj(g, rr.get("standardsAssessment"))
    if sa is not None:
        pack[sa["id"]] = _copy_fields(sa, ("dimensionVerdicts", "ratings"))
    return pack


def _alternatives_pack(g: Graph, ep: dict, rendering: str) -> dict[str, dict]:
    pack: dict[str, dict] = {}
    alt_ids = sorted(_ref_ids(ep.get("alternatives")))
    for aid in alt_ids:
        a = _obj(g, aid)
        if a is None:
            continue
        pack[aid] = _copy_fields(a, ("name", "description", "status", "baselineFlag"))
    for x in g.all("Exclusion"):
        target = x.get("target") if isinstance(x.get("target"), dict) else {}
        if target.get("kind") == "Alternative" and target.get("id") in alt_ids:
            pack[x["id"]] = _copy_fields(x, ("target", "reasonType", "reason"))
    return pack


_GRCA_FIELDS = ("statement", "linchpin", "rationale", "implicationsIfWrong")


def _grca_pack(g: Graph, ep: dict, rendering: str) -> dict[str, dict]:
    pack: dict[str, dict] = {}
    for field in ("groundRules", "constraints", "assumptions"):
        for oid in sorted(_ref_ids(ep.get(field))):
            o = _obj(g, oid)
            if o is None:
                continue
            entry = _copy_fields(o, _GRCA_FIELDS)
            pack[oid] = entry
            for v in entry.values():
                _pull_marker_target(g, pack, v)
    return pack


_PACK_BUILDERS = {
    "problem-statement": _problem_statement_pack,
    "evaluation-results": _evaluation_results_pack,
    "what-flips": _what_flips_pack,
    "readiness": _readiness_pack,
    "alternatives": _alternatives_pack,
    "grca": _grca_pack,
}


def context_pack(
    g: Graph, episode_id: str, section: str, *, rendering: str = "unclassified",
) -> dict[str, dict]:
    """The objects a narrator drafting `section` may talk about, each as
    `{id: {selected fields}}` — sorted, deterministic, and the *only* place a numeral in
    that narrative may legitimately come from. Skips a dangling reference rather than
    raising; refuses (`ValidationError`) only when `section` itself is not one of the 16
    package sections or `rendering` is not one of `RENDERINGS`.

    **[ruling I2] `rendering` defaults to `"unclassified"`, not `"full"`.** This is the
    one place graph content reaches a live, potentially hosted model backend — a caller
    must ask for `"full"` explicitly to get an above-`U` value into the pack at all.
    Under `"unclassified"`, any value tainted by non-`U` evidence — currently, an
    aggregate `Result` in the `evaluation-results` pack, mirroring
    `kernel.render._withheld`/`_cite_withheld_level` exactly — is replaced by the
    `[withheld: <level>]` marker, never a stub number a model could paste into a
    sentence as though it were the real value. `render_package`'s own two renderings
    are the model this follows; a value `render_package` would show in one rendering
    and hide in the other is shown or hidden here the same way.

    Six sections have a builder; the other ten (`cover`, `mandate-elements`,
    `objectives-and-measures`, `evidence-register`, `bias-checks`, `risks`,
    `refresh-log`, `commitment`, `traceability`, `machine-annex`) are still valid
    `Narrative.section` values — the renderer already assembles their bodies from
    objects directly and nobody has asked an agent to narrate them — so they return an
    empty pack rather than being refused outright.
    """
    if section not in VALID_SECTIONS:
        raise ValidationError(
            [f"narrate: unknown section {section!r}; valid package sections: "
             f"{list(VALID_SECTIONS)}"]
        )
    if rendering not in RENDERINGS:
        raise ValidationError(
            [f"narrate: unknown rendering {rendering!r}; valid renderings: {list(RENDERINGS)}"]
        )
    ep = _obj(g, episode_id)
    if ep is None:
        raise ValidationError([f"narrate: episode {episode_id!r} is not in the graph"])
    builder = _PACK_BUILDERS.get(section)
    return builder(g, ep, rendering) if builder is not None else {}


# ---- prompts ------------------------------------------------------------------------

_SECTION_SHAPE = {
    "problem-statement": (
        "State the question to be answered, the decision to be made, and the "
        "consequences of an erroneous answer (AR 5-11 ¶4-5b)."
    ),
    "evaluation-results": (
        "State each run's ranking and the aggregate score behind it, for the "
        "alternatives the context names."
    ),
    "what-flips": (
        "State which weight or assumption, moved by how much, reverses the ranking, "
        "and which assumption (if any) that parameter is bound to."
    ),
    "readiness": (
        "State whether the record is ready — no blocking findings — and the "
        "standards verdicts behind that call."
    ),
    "alternatives": (
        "Describe each alternative under consideration, and name any that were "
        "excluded and why."
    ),
    "grca": (
        "State the ground rules, constraints and assumptions the analysis rests on, "
        "including a linchpin assumption's rationale and its consequence if wrong "
        "(ICD 203 §D.6.e(3))."
    ),
}


def user_prompt(
    g: Graph, episode_id: str, section: str, *,
    context: dict | None = None, rendering: str = "unclassified",
) -> str:
    """The section name, the doctrinal shape expected of it, and the canonical JSON of
    its context pack. No clock value and no seed: the recording key is computed over
    this text, and a timestamp would rot every fixture daily.

    `context`, when given, is used in place of a freshly computed `context_pack(...)` —
    for a caller that already built one (a preview screen, a retry loop that wants to
    guarantee byte-identical context across attempts) and wants `narrate()` to act on
    that exact pack rather than recomputing it. `rendering` (default `"unclassified"`,
    [ruling I2]) is ignored when `context` is supplied directly — it only controls what
    a freshly computed pack withholds."""
    pack = context if context is not None else context_pack(g, episode_id, section,
                                                             rendering=rendering)
    shape = _SECTION_SHAPE.get(section, "Write only what the context below supports.")
    return (
        f"Section: {section}\n"
        f"Expected shape: {shape}\n\n"
        f"Context (the only objects and values you may cite or quote):\n"
        f"{canonical_json(pack)}"
    )


def retry_prompt(base: str, errors: list[str]) -> str:
    """A fixed, deterministic format: the original prompt (so the allowed ids and
    values are in front of the model again, unchanged) plus the renderer's own error
    text (which names the offending sentence) for every failed sentence."""
    return (base + "\n\nThe renderer rejected your previous draft:\n- "
            + "\n- ".join(errors)
            + "\nRewrite it. Every numeral must appear in a cited object.")


# ---- narrate --------------------------------------------------------------------------

_SENTENCE_INDEX = re.compile(r"^sentence (\d+) ")


def _offending_sentence(candidate: dict, errors: list[str]) -> str | None:
    """The text of the first sentence a `check_citations` error names, read back off
    `candidate` itself rather than parsed out of the error string (which quotes the text
    with `repr`, and would have to be un-repr'd to recover it exactly)."""
    sentences = candidate.get("sentences") or []
    for e in errors:
        m = _SENTENCE_INDEX.match(e)
        if m:
            i = int(m.group(1))
            if 0 <= i < len(sentences):
                return sentences[i].get("text")
    return None


def _next_narrative_id(g: Graph, ep: dict, section: str) -> str:
    """`nar-{episode}-{section}-{n}`, `n` one more than however many Narratives this
    episode already carries for this exact section — deterministic, id-pattern valid,
    and computed from the graph as it stands *before* this call's own draft is written."""
    existing = 0
    for nid in _ref_ids(ep.get("narratives")):
        n = _obj(g, nid)
        if n is not None and n.get("section") == section:
            existing += 1
    return f"nar-{ep['id']}-{section}-{existing + 1}"


def narrate(
    g: Graph,
    episode_id: str,
    *,
    section: str,
    backend: Any,
    actor: dict,
    now: str,
    context: dict | None = None,
    rendering: str = "unclassified",
) -> NarrateResult:
    """Draft, citation-check, and (only if clean) store a `Narrative` for `section`.

    Builds `context` (or accepts a caller-supplied one), asks `backend` for sentences
    against `NARRATIVE_SCHEMA`, and runs `kernel.render.check_citations` on the draft
    *before* writing anything. A rejected draft is re-prompted with the renderer's own
    error text (`retry_prompt`) — the context pack itself is never rebuilt or edited
    between attempts, so a retry cannot smuggle in an id or a value the first attempt
    was not already shown. Up to `MAX_RETRIES` retries (three attempts total); a draft
    that is never clean raises `UncitedSentenceError` (with `narrative_id` and
    `sentence` set) and writes nothing — no partial `Narrative`, no episode revision.

    **[ruling I2] `rendering` defaults to `"unclassified"`** and is forwarded to
    `context_pack(...)` whenever this call builds its own pack (i.e. `context` is not
    supplied) — a caller must ask for `rendering="full"` explicitly before any
    above-`U` value reaches the backend's prompt. Ignored when `context` is supplied
    directly, since that pack is used exactly as given.

    On success, returns the stored `Narrative` exactly as `Graph.put` wrote it, and the
    episode has one more revision: `narratives` gains this id, and nothing else on the
    episode changes — not `lifecycleState`, not `transitions` — which is what keeps this
    an agent-authored revision `Graph.put`'s own authority check will accept.
    """
    ep = g.get(episode_id)
    pack = context if context is not None else context_pack(g, episode_id, section,
                                                              rendering=rendering)
    base = user_prompt(g, episode_id, section, context=pack)
    sys_prompt = system_prompt()
    nid = _next_narrative_id(g, ep, section)

    prompt = base
    errors: list[str] = []
    candidate: dict[str, Any] = {}
    for _attempt in range(MAX_RETRIES + 1):
        resp = backend.complete_json(system=sys_prompt, user=prompt, schema=NARRATIVE_SCHEMA)
        candidate = {
            "id": nid, "type": "Narrative", "rev": 1, "createdBy": actor, "createdAt": now,
            "ingestionProvenance": {
                "sourceArtifact": episode_id, "locator": f"section {section}",
                "extractor": backend.extractor, "extractedAt": now,
            },
            "episode": episode_id, "section": section, "sentences": resp["sentences"],
        }
        errors = check_citations(g, candidate)
        if not errors:
            stored = g.put(candidate, actor)
            ep = g.get(episode_id)
            g.put({**ep, "rev": ep["rev"] + 1, "createdBy": actor, "createdAt": now,
                   "narratives": [*ep["narratives"], stored["id"]]}, actor)
            return stored
        prompt = retry_prompt(base, errors)

    raise UncitedSentenceError(
        f"{nid}: {MAX_RETRIES + 1} drafts failed citation checking: " + "; ".join(errors),
        narrative_id=nid, sentence=_offending_sentence(candidate, errors),
    )
