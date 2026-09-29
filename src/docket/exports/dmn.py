"""DMN 1.5 XML export (design §6.3, mapping table 3).

**Namespace verified; element ordering is believed XSD-valid but has not been validated
against the schema (review round 1, I5 — softened from the first draft's stronger
claim).** The namespace was fetched directly
(`https://www.omg.org/spec/DMN/20230324/DMN15.xsd`) and its `xsd:schema` element's
`targetNamespace` is exactly the value below. Element order (`informationRequirement`
before `authorityRequirement` within a `decision`) follows Table 11 "Decision attributes
and model associations" in the local OMG DMN 1.5 PDF
(`library/standards/omg-dmn-1-5-decision-model-and-notation.pdf`, p. 37:
`… decisionLogic, informationRequirement, knowledgeRequirement, authorityRequirement,
…`), read from that PDF rather than the XSD itself (no network access to fetch the XSD
a second time to confirm `xsd:sequence` order) — high-confidence, not certain.

Only the `decision`/`knowledgeSource`/`inputData` skeleton and the two requirement
edges the mapping table calls for are emitted — no `decisionTable`/FEEL body, since the
kernel's own MAVT evaluator is not itself expressed as a DMN decision table in Phase I.

Uses `xml.etree.ElementTree` to *build* this document. That is fine here: this module
only ever serialises XML it constructs itself. It must never be reused to *parse* a
third-party DMN file — stdlib `xml.etree` accepts external entities and expansion bombs
by default; a future ingestion path needs `defusedxml`.

`ElementTree.tostring` preserves attribute insertion order (Python ≥ 3.8) rather than
sorting it, so every attribute below is inserted in already-sorted order by hand —
otherwise two dict-iteration orders could serialise to different bytes for the same
document.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from docket.exports._util import obj, slug
from docket.store import Graph

DMN_NS = "https://www.omg.org/spec/DMN/20230324/MODEL/"


def _elem(tag: str, attrs: dict[str, str]) -> ET.Element:
    e = ET.Element(f"{{{DMN_NS}}}{tag}")
    for k in sorted(attrs):
        if attrs[k] is not None:
            e.set(k, str(attrs[k]))
    return e


def to_dmn(g: Graph, plan_id: str | None, *, rendering: str) -> str:
    """DMN 1.5 XML for `plan_id`'s steps.

    Tolerant of `plan_id` not naming a Plan in `g` (including `None`): the document is
    still well-formed, with zero `decision` elements and an explanatory comment, rather
    than raising — `write_exports` calls this for every episode `build_package` renders,
    including one with no approved plan at all, and a missing export must never make an
    otherwise-successful package build fail.

    `rendering` is accepted for the same reason every export in this package takes it
    (design decision 1) but is not otherwise consulted: a Plan's steps, measures and
    authority citations are process metadata, not evidence values, so nothing here is
    ever withheld under the unclassified rendering.
    """
    plan = obj(g, plan_id)
    root = _elem("definitions", {
        "id": f"defs-{plan_id}" if plan_id else "defs-none",
        "name": plan_id or "no-plan",
        "namespace": f"https://docket.dev/ns#{plan_id or 'no-plan'}",
    })
    if plan is None:
        # I2's "never interpolate a bare Python `None`" also applies here: `plan_id`
        # is `None` exactly when no plan was named at all (as opposed to a named-but-
        # dangling id), and the comment says so in words rather than `repr(None)`.
        if plan_id is None:
            reason = "no Plan was named for this episode"
        else:
            reason = f"no Plan resolves for {plan_id!r}"
        root.append(ET.Comment(f" {reason}; this episode has not been evaluated "
                                "under an approved plan "))
        return _serialise(root)

    steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)]

    knowledge_sources: dict[str, str] = {}  # document text -> ks id
    for step in steps:
        authority = step.get("authority") if isinstance(step.get("authority"), dict) else {}
        doc = authority.get("document")
        if isinstance(doc, str) and doc not in knowledge_sources:
            knowledge_sources[doc] = f"ks-{slug(doc)}"

    input_data: dict[str, str] = {}  # measure id -> inputData id
    for step in steps:
        for m in step.get("measures") or []:
            if isinstance(m, str):
                input_data[m] = f"input-{m}"

    for doc in sorted(knowledge_sources):
        root.append(_elem("knowledgeSource", {"id": knowledge_sources[doc], "name": doc}))
    for measure_id in sorted(input_data):
        root.append(_elem("inputData", {"id": input_data[measure_id], "name": measure_id}))

    for step in sorted(steps, key=lambda s: s.get("id") or ""):
        step_id = step.get("id")
        if not isinstance(step_id, str):
            continue
        decision = _elem("decision", {"id": step_id, "name": step_id})
        # I5: `informationRequirement` before `authorityRequirement` — Table 11's order
        # (see the module docstring), the reverse of this module's first draft.
        for m in sorted(mid for mid in (step.get("measures") or []) if isinstance(mid, str)):
            req = _elem("informationRequirement", {})
            req.append(_elem("requiredInput", {"href": f"#{input_data[m]}"}))
            decision.append(req)
        authority = step.get("authority") if isinstance(step.get("authority"), dict) else {}
        doc = authority.get("document")
        if isinstance(doc, str) and doc in knowledge_sources:
            req = _elem("authorityRequirement", {})
            req.append(_elem("requiredAuthority", {"href": f"#{knowledge_sources[doc]}"}))
            decision.append(req)
        root.append(decision)

    return _serialise(root)


def _serialise(root: ET.Element) -> str:
    # I4: registered here, immediately before `tostring`, rather than at import time —
    # `ET.register_namespace` mutates a process-global registry `ElementTree` consults
    # during serialisation, so a *different* registration anywhere else in the same
    # process (before or after this module is imported) would otherwise change these
    # bytes: `<definitions xmlns="…">` becomes `<ns0:definitions xmlns:ns0="…">` the
    # moment something else registers a different default prefix. Re-registering right
    # here, every call, makes the output depend only on `DMN_NS`, never on import order
    # or anything else running in the process.
    ET.register_namespace("", DMN_NS)
    ET.indent(root, space="  ")
    # No `xml_declaration` standalone flag: `ET.tostring` with encoding="unicode" emits
    # no <?xml ...?> prologue at all, which is what "no standalone flag" calls for —
    # a DMN consumer reads the root element's own namespace, not a prologue attribute.
    text = ET.tostring(root, encoding="unicode")
    return text.rstrip("\n") + "\n"


__all__ = ["to_dmn"]
