"""Requirements Traceability Matrix export (design §6.3, mapping table 6).

One row per (Claim, supporting-evidence) pair, sorted by `(claim_id, evidence_id)`. The
fixed column order is also the CSV header — this module is the single definition of it,
reused by `milstd3022.py`'s Table I appendix so the two never drift apart.
"""

from __future__ import annotations

import csv
import io

from docket.exports._util import obj, sorted_ref_ids
from docket.kernel.render import evidence_pointer, evidence_title, metadata_withheld
from docket.kernel.scope import check_scope
from docket.objects import is_exclusion_ref, is_gap_ref
from docket.store import Graph

RTVM_COLUMNS = [
    "claim_id", "claim_text", "section", "level", "evidence_id", "evidence_title",
    "evidence_level", "metadata_level", "pointer", "scope_built_to_answer", "vva_status",
    "review_status", "reliability_steps", "reuse_justification", "assessable_at_U",
]


def _marker_text(
    v: object, *, gap_prefix: str = "gap", excl_prefix: str = "excluded",
) -> str | None:
    if is_exclusion_ref(v):
        return f"{excl_prefix}:{v['$exclusion']}"
    if is_gap_ref(v):
        return f"{gap_prefix}:{v['$gap']}"
    return None


def _vva_status(g: Graph, e: dict) -> str:
    """Only the `MSStudy` variant carries `vvaRecord` at all; every other
    `evidenceType` prints the literal `n/a` — blank would read as "we did not look".
    Not consulted at all when `metadata_withheld` fires — the caller (`_row_for`)
    overrides this with the withholding marker before this is ever reached, review
    round 1 C1: whether an accreditation decision exists is itself metadata."""
    if e.get("evidenceType") != "MSStudy":
        return "n/a"
    vva_ref = e.get("vvaRecord")
    marker = _marker_text(vva_ref)
    if marker is not None:
        return marker
    v = obj(g, vva_ref) if isinstance(vva_ref, str) else None
    if v is None:
        return "_[unresolved]_"
    acc = v.get("accreditationDecision")
    marker = _marker_text(acc)
    if marker is not None:
        return marker
    if isinstance(acc, dict):
        return f"{acc.get('authority')} ({acc.get('date')})"
    return ""


def _scope_built_to_answer(sov: object) -> str:
    marker = _marker_text(sov)
    if marker is not None:
        return marker
    if isinstance(sov, dict):
        return str(sov.get("builtToAnswer") or "")
    return ""


def _reliability_steps(steps: object) -> str:
    marker = _marker_text(steps)
    if marker is not None:
        return marker
    if isinstance(steps, list):
        return str(len(steps))
    return ""


def _not_assessable_pairs(g: Graph, episode_id: str) -> set[tuple[str, str]]:
    return {
        (f.objects[0], f.objects[1])
        for f in check_scope(g, episode_id)
        if f.rule == "NotAssessableAtLevel" and len(f.objects) >= 2
    }


def _row_for(
    g: Graph, cid: str, c: dict, entry: object, not_assessable: set[tuple[str, str]],
    rendering: str,
) -> dict:
    base = {
        "claim_id": cid, "claim_text": c.get("text"), "section": c.get("section"),
        "level": (c.get("assessableAt") or {}).get("level")
        if isinstance(c.get("assessableAt"), dict) else None,
    }
    if not isinstance(entry, dict):
        return {**base, **dict.fromkeys(
            ("evidence_id", "evidence_title", "evidence_level", "metadata_level", "pointer",
             "scope_built_to_answer", "vva_status", "review_status", "reliability_steps",
             "reuse_justification"), ""
        ), "assessable_at_U": True}

    ev_id = entry.get("evidence")
    e = obj(g, ev_id) if isinstance(ev_id, str) else None
    reuse = entry.get("reuseJustification")
    reuse_text = reuse.get("text", "") if isinstance(reuse, dict) else ""

    if e is None:
        return {**base, "evidence_id": ev_id or "", "evidence_title": "", "evidence_level": "",
                "metadata_level": "", "pointer": "", "scope_built_to_answer": "",
                "vva_status": "", "review_status": "", "reliability_steps": "",
                "reuse_justification": reuse_text, "assessable_at_U": True}

    cls = e.get("classification") if isinstance(e.get("classification"), dict) else {}
    # I4 (review round 2): `evidence_title` is the single, metadataLevel-gated
    # definition of "is this evidence's title visible" the package's own evidence
    # register, PROV and GSN also call — this column used to narrow to the *value*
    # classification (`_withheld`) and blank to `""` when it fired, which disagreed
    # with the package on both axes: a different field decided visibility, and a
    # blank cell reads as "we did not look" where a `[withheld: <level>]` marker
    # reads as "there is something here you may not see."
    title = evidence_title(g, e, rendering)
    assessable_u = (cid, ev_id) not in not_assessable

    # Review round 1, C1: the package's own evidence register withholds *six* columns
    # whenever `classification.metadataLevel != "U"` under the unclassified rendering —
    # not `pointer` alone. `render.metadata_withheld` is the single shared definition of
    # that gate (I8); every one of the five columns it covers here becomes the same
    # `[withheld: <level>]` marker `render.evidence_pointer` already used for `pointer`,
    # so the RTVM never states in clear what the package next to it withholds.
    withheld_level = metadata_withheld(g, e, rendering)
    if withheld_level is not None:
        marker = f"[withheld: {withheld_level}]"
        scope_built_to_answer = vva_status = review_status = reliability_steps = marker
    else:
        scope_built_to_answer = _scope_built_to_answer(e.get("scopeOfValidity"))
        vva_status = _vva_status(g, e)
        review_status = e.get("reviewStatus")
        reliability_steps = _reliability_steps(e.get("reliabilitySteps"))

    return {
        **base,
        "evidence_id": ev_id,
        "evidence_title": title,
        "evidence_level": cls.get("level"),
        "metadata_level": cls.get("metadataLevel"),
        "pointer": evidence_pointer(g, e, rendering),
        "scope_built_to_answer": scope_built_to_answer,
        "vva_status": vva_status,
        "review_status": review_status,
        "reliability_steps": reliability_steps,
        "reuse_justification": reuse_text,
        "assessable_at_U": assessable_u,
    }


def to_rtvm(g: Graph, episode_id: str, *, rendering: str) -> list[dict]:
    ep = obj(g, episode_id) or {}
    not_assessable = _not_assessable_pairs(g, episode_id)

    rows: list[dict] = []
    for cid in sorted_ref_ids(ep.get("claims")):
        c = obj(g, cid)
        if c is None:
            continue
        sb = c.get("supportedBy")
        entries = sb if isinstance(sb, list) and sb else [None]
        for entry in entries:
            rows.append(_row_for(g, cid, c, entry, not_assessable, rendering))

    rows.sort(key=lambda r: (str(r.get("claim_id") or ""), str(r.get("evidence_id") or "")))
    return rows


def rtvm_csv(rows: list[dict]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=RTVM_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in RTVM_COLUMNS})
    return buf.getvalue()


__all__ = ["RTVM_COLUMNS", "rtvm_csv", "to_rtvm"]
