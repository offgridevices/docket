"""MIL-STD-3022 VV&A record export (design §6.3, mapping table 4).

Table I's nine sections, in Table I order (pre-flight defect D15): five headings have a
dedicated `VVARecord` field, two ("Key Participants", "Resources") exist only as
`sections[]` entries (no schema field at all), and one more ("Lessons Learned") is a
field that is commonly *also* named in `sections[]`.

**Review round 1, I10 — merged by name, not interleaved as duplicates.** The first cut
of this module treated "the remaining `sections[]` entries" as "everything not consumed
by the two section-only headings", which re-emitted every field-backed heading a second
time whenever the record also named it in `sections[]` (Demo A names all eight Table I
headings in `sections[]`, producing 14 headings for 9 sections) — and, worse, put the
record's two `NOT_APPLICABLE` markers (on "Issues" and "Lessons Learned", both absent as
*fields* but present as `sections[]` exclusions) under a duplicate heading rather than
under "## Issues"/"## Lessons Learned" themselves, so the D14 count assertion passed for
the wrong reason. Fixed here: for every Table I heading, the field's own text and the
`sections[]` entry of the same name are *merged* — the field alone when only it holds
content, the `sections[]` entry alone when only it does, and *both*, labelled, when they
hold different content (identical content prints once). Only `sections[]` entries whose
name matches **no** Table I heading are interleaved afterwards.

A missing named section still renders as missing (`*(section not present in the
record)*`), never a raised exception — the whole point of D15 is that "no field" is not
the same fact as "nothing to say."

**Review round 2.** I2: `to_milstd3022_for_episode` renders *every* VVARecord forward-
reachable from an episode, each as its own top-level section, in id order — the call
`write_exports`/`build_package` use, which must never fail just because a demonstration
episode names more than one VV&A record (or none). `to_milstd3022(g, vva_id, ...)` keeps
its original one-record shape for a caller (`docket export --format milstd3022 --vva
<id>`) that already knows which record it wants; it is tolerant of `vva_id` not
resolving, but a bare `vva_id=None` never appears in the printed notice — "no VV&A
record resolves for None" was a rendering bug, not a fact about the record. I4: the
Accreditation Decision's cited `document` (an Evidence reference) now goes through
`render.evidence_title`, the same metadataLevel-gated helper the package, PROV, GSN and
the RTVM appendix already share, rather than printing `Evidence.title` in clear
regardless of classification.
"""

from __future__ import annotations

from docket.canon import canonical_json
from docket.exports._util import obj, reachable_objects
from docket.exports.rtvm import RTVM_COLUMNS, to_rtvm
from docket.kernel.render import evidence_title
from docket.objects import is_content, is_exclusion_ref, is_gap_ref
from docket.store import Graph

NOT_APPLICABLE = "This section is not applicable."  # MIL-STD-3022 §5.3, emitted verbatim

# Table I order. `None` as the field key means "no dedicated `VVARecord` field at all"
# (Key Participants, Resources — defect D15); every other heading is looked up by a
# dedicated handler in `_field_text_for` (some of them, like "Accreditation
# Methodology", combine more than one schema field).
TABLE_I_HEADINGS = (
    "Problem Statement",
    "M&S Requirements and Acceptability Criteria",
    "M&S Assumptions, Capabilities, Limitations & Risks/Impacts",
    "Accreditation Methodology",
    "Issues",
    "Key Participants",
    "Resources",
    "Lessons Learned",
)
# Retained for anyone reading the mapping table (plan 06 task 1) alongside this module —
# no longer consulted by `to_milstd3022` itself, which loops over `TABLE_I_HEADINGS`.
TABLE_I_FIELD_BACKED = (
    ("Problem Statement", "problemStatement"),
    ("M&S Requirements and Acceptability Criteria", "requirementsAndAcceptabilityCriteria"),
    ("M&S Assumptions, Capabilities, Limitations & Risks/Impacts",
     "assumptionsCapabilitiesLimitationsRisks"),
    ("Accreditation Methodology", "methodology"),
    ("Issues", "issues"),
)
TABLE_I_SECTION_BACKED = ("Key Participants", "Resources")  # no schema field — defect D15
NOT_STATED = "*(not stated)*"


def _slot_text(g: Graph, v: object) -> str:
    """A P3 slot's Markdown text, in MIL-STD-3022's own wording (pre-flight defect D14)
    — never `render.py`'s wording, which the test's literal-count assertion does not
    pin to."""
    if is_exclusion_ref(v):
        x = obj(g, v["$exclusion"])
        if x is None:
            return f"{NOT_APPLICABLE}\n(exclusion {v['$exclusion']!r} unresolved)"
        authority = x.get("authority") if isinstance(x.get("authority"), dict) else {}
        return (
            f"{NOT_APPLICABLE}\n"
            f"Reason: {x.get('reason')}\n"
            f"Authority: {authority.get('who')} ({authority.get('role')}), "
            f"{authority.get('date')}"
        )
    if is_gap_ref(v):
        x = obj(g, v["$gap"])
        if x is None:
            return f"Insufficient evidence: (gap {v['$gap']!r} unresolved)"
        where = "; ".join(str(w) for w in (x.get("whereLookedFor") or [])) or NOT_STATED
        resolve = "; ".join(
            str(i) for i in (x.get("indicatorsThatWouldResolve") or [])
        ) or NOT_STATED
        return (
            f"Insufficient evidence: sought {x.get('sought')}; looked in {where}; "
            f"not found because {x.get('whyNotFound')}; impact {x.get('impact')}; "
            f"would resolve: {resolve}"
        )
    if not is_content(v):
        return NOT_STATED
    if isinstance(v, list):
        return "\n".join(f"- {item}" for item in v) if v else NOT_STATED
    if isinstance(v, dict):
        return canonical_json(v)
    return str(v)


def _problem_statement_text(g: Graph, charter_ref: object) -> str:
    """Table I §1 from `VVARecord.problemStatement` → `Charter`: the AR 5-11 ¶4-5b(1)
    question and the ¶4-5b(2) decision to be made, the two Charter fields that together
    are what "the problem statement" means for this record."""
    ch = obj(g, charter_ref)
    if ch is None:
        return f"_[charter {charter_ref!r} unresolved]_"
    return (
        f"Question: {_slot_text(g, ch.get('question'))}\n"
        f"Decision to be made: {_slot_text(g, ch.get('decisionToBeMade'))}"
    )


def _aclr_text(g: Graph, v: object) -> str:
    """Table I §3: the four slot-bearing sub-lists of
    `assumptionsCapabilitiesLimitationsRisks`, each rendered on its own — the object
    itself is required but not a slot; each of its four properties is (mapping table 4)."""
    if is_exclusion_ref(v) or is_gap_ref(v) or not is_content(v):
        return _slot_text(g, v)
    if not isinstance(v, dict):
        return str(v)
    parts = []
    for key, label in (("assumptions", "Assumptions"), ("capabilities", "Capabilities"),
                        ("limitations", "Limitations"), ("risks", "Risks")):
        parts.append(f"**{label}**\n{_slot_text(g, v.get(key))}")
    return "\n\n".join(parts)


def _accreditation_decision_text(g: Graph, v: object, rendering: str) -> str:
    """Table I §4's second half (review round 1, C2): `accreditationDecision`'s five
    sub-fields — `authority`, `date`, `scope`, `basis`, and `document` (an Evidence
    reference, resolved to its title) — required alongside `methodology` per the
    mapping table, and previously dropped entirely.

    Review round 2, I4: the resolved document's title goes through
    `render.evidence_title` — the same metadataLevel-gated helper the package, PROV,
    GSN and the RTVM appendix use — rather than `Evidence.title` in clear, so citing a
    classified item's accreditation basis cannot say more than the rest of this same
    document does about that item.
    """
    if is_exclusion_ref(v) or is_gap_ref(v) or not is_content(v):
        return _slot_text(g, v)
    if not isinstance(v, dict):
        return str(v)
    doc = v.get("document")
    doc_text = None
    if isinstance(doc, str):
        d = obj(g, doc)
        doc_text = evidence_title(g, d, rendering) if d is not None else f"{doc} (unresolved)"
    parts = [
        f"Authority: {v.get('authority')}",
        f"Date: {v.get('date')}",
        f"Scope: {v.get('scope')}",
        f"Basis: {v.get('basis')}",
    ]
    if doc_text:
        parts.append(f"Document: {doc_text}")
    return "\n".join(parts)


def _plain_text(v: object) -> str | None:
    """`issues`/`lessonsLearned`: optional, ordinary (non-slot) fields — never a P3
    marker by schema. Returns `None` (not `NOT_STATED`) when the field itself is empty
    or absent, so `_field_text_for` can tell "nothing here" from "here, and it says
    nothing" and fall back to a `sections[]` entry of the same name (I10)."""
    if isinstance(v, list) and v:
        return "\n".join(f"- {item}" for item in v)
    if isinstance(v, str) and v:
        return v
    return None


def _field_text_for(g: Graph, v: dict, heading: str, rendering: str) -> str | None:
    """The Table I heading's own dedicated-field text, or `None` when the field holds
    nothing to say (absent, empty, or an unresolved reference) — the caller then falls
    back to (or merges with) the `sections[]` entry of the same name."""
    if heading == "Problem Statement":
        ref = v.get("problemStatement")
        if not isinstance(ref, str) or not obj(g, ref):
            return None
        return _problem_statement_text(g, ref)
    if heading == "M&S Requirements and Acceptability Criteria":
        raw = v.get("requirementsAndAcceptabilityCriteria")
        return _slot_text(g, raw) if is_content(raw) else None
    if heading == "M&S Assumptions, Capabilities, Limitations & Risks/Impacts":
        raw = v.get("assumptionsCapabilitiesLimitationsRisks")
        return _aclr_text(g, raw) if isinstance(raw, dict) and raw else None
    if heading == "Accreditation Methodology":
        methodology, accreditation = v.get("methodology"), v.get("accreditationDecision")
        if not is_content(methodology) and not is_content(accreditation):
            return None
        return (
            f"**Methodology**\n{_slot_text(g, methodology)}\n\n"
            f"**Accreditation Decision**\n"
            f"{_accreditation_decision_text(g, accreditation, rendering)}"
        )
    if heading == "Issues":
        return _plain_text(v.get("issues"))
    if heading == "Lessons Learned":
        return _plain_text(v.get("lessonsLearned"))
    return None  # Key Participants / Resources: no dedicated field at all (D15)


def _merged_heading_text(
    g: Graph, v: dict, heading: str, named_sections: dict[str, object], used: set[str],
    rendering: str,
) -> str:
    """The field's own text and the `sections[]` entry of the same name, merged: the
    field alone when only it holds content, the entry alone when only it does, both
    (labelled) when they hold different content, one copy when they agree, and the
    "not present" marker when neither does (I10)."""
    field_text = _field_text_for(g, v, heading, rendering)
    section_text = None
    if heading in named_sections:
        section_text = _slot_text(g, named_sections[heading])
        used.add(heading)
    if field_text is not None and section_text is not None:
        if field_text.strip() == section_text.strip():
            return field_text
        return (
            "**From the VV&A record's dedicated field:**\n"
            f"{field_text}\n\n"
            f"**From `sections[]` (\"{heading}\"):**\n"
            f"{section_text}"
        )
    if field_text is not None:
        return field_text
    if section_text is not None:
        return section_text
    return "*(section not present in the record)*"


def _rtvm_markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "_(no claims on record)_"
    header = "| " + " | ".join(RTVM_COLUMNS) + " |"
    sep = "|" + "|".join("---" for _ in RTVM_COLUMNS) + "|"
    body = [
        "| " + " | ".join(_escape_cell(row.get(c, "")) for c in RTVM_COLUMNS) + " |"
        for row in rows
    ]
    return "\n".join([header, sep, *body])


def _escape_cell(v: object) -> str:
    """Markdown table cells cannot hold a literal `|` or a newline without breaking the
    table's row structure (review round 1, M5) — collapse newlines to a space and
    escape pipes; no Demo A cell needs this today, but claim/evidence text is free-form
    prose and will eventually contain one."""
    return str(v).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _episode_for(g: Graph, vva_id: str) -> str | None:
    """The one `DecisionEpisode` that (transitively) references this VV&A record, or
    `None` if there is not exactly one — `to_milstd3022` has no episode parameter of its
    own (mapping table 4/9), so the RTVM appendix must find its episode by walking the
    graph backwards rather than guessing."""
    episodes = sorted(
        oid for oid in g.reachable_from(vva_id, reverse=True)
        if g.has(oid) and g.get(oid).get("type") == "DecisionEpisode"
    )
    return episodes[0] if len(episodes) == 1 else None


def _render_record(g: Graph, vva_id: str, v: dict, *, rendering: str) -> str:
    """The full Table I markdown for one already-resolved `VVARecord` — the body
    `to_milstd3022` (one named record) and `to_milstd3022_for_episode` (every
    reachable record, review round 2, I2) both build, so the two call paths cannot
    render a record differently."""
    lines = [f"# MIL-STD-3022 VV&A record — {vva_id}", ""]

    named_sections: dict[str, object] = {
        s.get("name"): s.get("content")
        for s in (v.get("sections") or [])
        if isinstance(s, dict) and isinstance(s.get("name"), str)
    }
    used_names: set[str] = set()

    for heading in TABLE_I_HEADINGS:
        lines.append(f"## {heading}")
        lines.append("")
        lines.append(_merged_heading_text(g, v, heading, named_sections, used_names, rendering))
        lines.append("")

    # Only names that match *no* Table I heading are interleaved (I10) — every heading
    # above already merged its own `sections[]` entry, so nothing here can duplicate one.
    remaining = sorted(name for name in named_sections if name not in used_names)
    for name in remaining:
        lines.append(f"## {name} _(sections[] entry)_")
        lines.append("")
        lines.append(_slot_text(g, named_sections[name]))
        lines.append("")

    lines.append("## Appendix: Requirements Traceability Matrix")
    lines.append("")
    episode_id = _episode_for(g, vva_id)
    if episode_id is None:
        lines.append(
            "_(the episode this VV&A record belongs to could not be resolved "
            "uniquely; the traceability matrix is omitted)_"
        )
    else:
        rows = to_rtvm(g, episode_id, rendering=rendering)
        lines.append(_rtvm_markdown_table(rows))
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def to_milstd3022(g: Graph, vva_id: str | None, *, rendering: str) -> str:
    """Markdown, Table I order, for the `VVARecord` named `vva_id`.

    Tolerant of `vva_id` not resolving: renders a one-line notice rather than
    raising, for the same reason `to_dmn` tolerates a missing plan — a caller that
    already knows which record it wants (`docket export --format milstd3022 --vva
    <id>`) may still name one that is absent or wrong. `vva_id=None` itself is not a
    fact about any record — `to_milstd3022_for_episode` is what `write_exports`/
    `build_package` call when no specific record was named — so it gets its own
    notice rather than interpolating a bare Python `None` into the text (review
    round 2, I2).
    """
    if vva_id is None:
        return (
            "# MIL-STD-3022 VV&A record\n\n"
            "_(no specific VV&A record was named)_\n"
        )
    v = obj(g, vva_id)
    if v is None:
        return (
            f"# MIL-STD-3022 VV&A record\n\n"
            f"_[no VV&A record resolves for {vva_id!r}]_\n"
        )
    return _render_record(g, vva_id, v, rendering=rendering)


def to_milstd3022_for_episode(g: Graph, episode_id: str, *, rendering: str) -> str:
    """Every `VVARecord` forward-reachable from `episode_id`, each as its own
    top-level section, in id order (review round 2, I2).

    The tolerant, whole-episode call `write_exports`/`build_package` use — it must
    never fail, or say "no record resolves," just because an episode names more than
    one VV&A record (two of three demos do): `to_milstd3022(g, None, ...)` used to be
    called here whenever auto-resolution found zero or several candidates, printing
    "no VV&A record resolves for None" even when records plainly existed. When zero
    records are reachable, this says so in words, naming the episode, not `None`.
    """
    records = reachable_objects(g, episode_id, "VVARecord")
    if not records:
        return (
            "# MIL-STD-3022 VV&A record\n\n"
            f"_(no VVARecord is reachable from episode {episode_id})_\n"
        )
    return "\n".join(
        _render_record(g, vva_id, v, rendering=rendering) for vva_id, v in records
    )


__all__ = [
    "NOT_APPLICABLE", "TABLE_I_FIELD_BACKED", "TABLE_I_HEADINGS", "TABLE_I_SECTION_BACKED",
    "to_milstd3022", "to_milstd3022_for_episode",
]
