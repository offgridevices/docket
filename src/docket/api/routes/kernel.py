"""Kernel routes: readiness, the authority rail, the evidence register, packages, the
determinism affordance, and exports (plan 07 Task 4).

Every mutating route here holds the session lock for the call and saves afterwards
(`sessions.writing`); every kernel call receives `now` from the one clock the API is
allowed to read (`_now`, below — the kernel itself never reads a clock, `now` always
arrives as an argument, which is the whole reproducibility contract). None of these
routes accept an actor from the client: `readiness_report`/`build_package` write only as
`KERNEL_ACTOR` internally, and no route in this file needs a human actor at all (that
requirement lands on `routes/program.py`'s `/refresh`, the one write here that reopens a
model for a human to approve again).
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from docket.api.authority import authority_counts
from docket.api.serialize import object_view
from docket.api.sessions import writing
from docket.api.verify import NoPackageBuilt, verify_package
from docket.kernel.readiness import readiness_report
from docket.kernel.render import (
    build_package,
    rating_scale_legend,
    readiness_ready_text,
    render_package,
    tailoring_note,
)
from docket.kernel.scope import check_scope
from docket.store import Graph

router = APIRouter()

_RENDERINGS = ("full", "unclassified")


def _now() -> str:
    """UTC wall-clock timestamp for API-driven kernel calls. See
    `docket.api.sessions._now`'s docstring: the kernel never reads a clock, `now` always
    arrives as a plain string argument, and the API — a server, not the kernel — is
    allowed one. Each route module that needs the clock defines this the same one-line
    way rather than importing another module's private helper.
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_rendering(rendering: str) -> None:
    if rendering not in _RENDERINGS:
        raise ValueError(f"rendering must be one of {_RENDERINGS}, got {rendering!r}")


# ---- readiness -------------------------------------------------------------------


class ReadinessRequest(BaseModel):
    seed: int = 0
    tailoring: str | None = None
    k: int | None = None


def _flip_summary_view(fs: object) -> object:
    """`fs` (`ReadinessReport.flipSummary`) with a `simplexRobustnessText` sibling next
    to `simplexRobustness` — plan 07 Task 7 fix round, I2: the same `str()` form
    `kernel.render._what_flips_body` already prints for each alternative's fraction
    (`f"{a}: {v}"`), so `<Num>` on the Compute/Readiness screens never has to
    re-stringify a `JSON.parse`d float. `fs` is a bare dict on `ReadinessReport`
    (`additionalProperties: true` in the schema, not a typed ref), so this tolerates
    anything a hand-edited store might hold there rather than assuming the shape."""
    if not isinstance(fs, dict):
        return fs
    sr = fs.get("simplexRobustness")
    if not isinstance(sr, dict):
        return fs
    return {**fs, "simplexRobustnessText": {k: str(v) for k, v in sr.items()}}


def _readiness_view(g: Graph, rr: dict) -> dict:
    """`rr` with `standardsAssessment`/`mandateScorecard` resolved to the objects they
    name, rather than left as bare ids — "the report ... plus its StandardsAssessment
    and MandateScorecard resolved" (plan 07 Task 4).

    Plan 07 Task 7 fix round (C1/I2/I5, per the review's Q7 answer): adds
    `standardsCaptions` (the renderer's own rating-scale sentence and the scored
    tailoring's own honesty note, `None` when it has none — never a second copy
    hand-typed in the UI), `applicableQuestions`/`totalQuestions` (a plain count over
    `sa["ratings"]`, computed here rather than by the browser — "no arithmetic in the
    browser" says nothing about the API refusing to count), `readyText` (the exact
    string `render.py` would print for "Ready (no blocking findings)", staleness
    substitution included, so the screen and the package can never disagree about it),
    and `tailoring`/`k`/`createdAt` restated at the top level so the Readiness screen's
    ready line does not have to reach into `standardsAssessment` for them.
    """
    sa_id, ms_id = rr.get("standardsAssessment"), rr.get("mandateScorecard")
    sa = g.get(sa_id) if isinstance(sa_id, str) and g.has(sa_id) else None
    ms = g.get(ms_id) if isinstance(ms_id, str) and g.has(ms_id) else None
    ratings = (
        sa.get("ratings") if isinstance(sa, dict) and isinstance(sa.get("ratings"), list) else []
    )
    tailoring_name = sa.get("tailoring") if isinstance(sa, dict) else None
    episode_id = rr.get("episode")
    return {
        **rr,
        "standardsAssessment": sa,
        "mandateScorecard": ms,
        "flipSummary": _flip_summary_view(rr.get("flipSummary")),
        "standardsCaptions": {
            "ratingScale": rating_scale_legend(),
            "tailoringNote": tailoring_note(tailoring_name)
            if isinstance(tailoring_name, str) else None,
        },
        "applicableQuestions": sum(
            1 for r in ratings if isinstance(r, dict) and r.get("applicable")
        ),
        "totalQuestions": len(ratings),
        "readyText": readiness_ready_text(g, episode_id, rr)
        if isinstance(episode_id, str) and g.has(episode_id) else str(rr.get("ready")),
        "tailoring": tailoring_name,
        "k": sa.get("k") if isinstance(sa, dict) else None,
        "createdAt": rr.get("createdAt"),
    }


@router.post("/session/{s}/episode/{e}/readiness")
def post_readiness(s: str, e: str, body: ReadinessRequest, request: Request) -> dict:
    session = request.app.state.sessions.get(s)
    with writing(session) as g:
        rr = readiness_report(g, e, tailoring=body.tailoring, k=body.k, seed=body.seed,
                               now=_now())
    return _readiness_view(session.graph, rr)


@router.get("/session/{s}/episode/{e}/readiness")
def get_readiness(s: str, e: str, request: Request):
    """The report stored at `episode["readiness"]` — that is the contract, this never
    recomputes on GET."""
    g = request.app.state.sessions.get(s).graph
    ep = g.get(e)
    rr_id = ep.get("readiness")
    if not isinstance(rr_id, str) or not g.has(rr_id):
        return JSONResponse(status_code=404, content={
            "error": "no-readiness",
            "message": f"no readiness report has been produced for episode {e}",
        })
    return _readiness_view(g, g.get(rr_id))


# ---- authority rail ----------------------------------------------------------------


@router.get("/session/{s}/episode/{e}/authority")
def get_authority(s: str, e: str, request: Request) -> dict:
    g = request.app.state.sessions.get(s).graph
    if not g.has(e):
        raise KeyError(e)
    return authority_counts(g, e)


# ---- evidence register ---------------------------------------------------------------

# The four fields `kernel.render._evidence_register_row` (render.py:545-561) withholds
# behind a single `[withheld: <level>]` marker whenever `rendering != "full"` and the
# evidence's `classification.metadataLevel` is neither `None` nor `"U"`. That function
# builds one Markdown table cell per field and returns a single row string, not
# structured data, so it cannot be imported and reused verbatim here — the *condition*
# and the *marker text* are copied from it exactly instead (fix round 1, I1). If that
# rule ever changes, this must change with it.
_WITHHOLD_FIELDS = ("pointer", "scopeOfValidity", "reliabilitySteps", "reviewStatus")


def _withhold_evidence_fields(e: dict, rendering: str) -> tuple[dict, str | None]:
    """`(evidence, withheld_level)`: `evidence` unchanged, and `withheld_level` `None`,
    unless `rendering != "full"` and the metadata level is above `U` — in which case
    `evidence` is a copy with `_WITHHOLD_FIELDS` replaced by the same
    `f"[withheld: {level}]"` marker `_evidence_register_row` prints, and
    `withheld_level` is that level (so the caller can also drop those fields' P3 slots,
    which `object_view` would otherwise still resolve from the *unwithheld* object).
    `classification` itself is never touched — the level and metadata level are exactly
    what tells a reader why the rest is hidden.
    """
    cls = e.get("classification") if isinstance(e.get("classification"), dict) else {}
    meta_level = cls.get("metadataLevel")
    if rendering == "full" or meta_level in (None, "U"):
        return e, None
    marker = f"[withheld: {meta_level}]"
    return {**e, **dict.fromkeys(_WITHHOLD_FIELDS, marker)}, meta_level


def _claims_citing_evidence(g: Graph, ep: dict) -> dict[str, list[dict]]:
    """`{evidence_id: [{"claim": ..., "reuseJustification": ..., "assessableAt": ...},
    ...]}` — resolved from the episode's `Claim.supportedBy[]` entries, never from
    `Evidence` itself: `reuseJustification` and `assessableAt` are fields of a *Claim*
    (`schema/objects.yaml`, the claim's own `supportedBy[].reuseJustification` and
    `assessableAt`), not of the `Evidence` object a claim cites, so the evidence
    register cannot surface them by resolving `evidenceRegister` alone (fix round 1,
    I2). `scopeFindings` can already flag a *problem* with a reuse justification
    (`check_scope`'s `reuse-justified`/`ReusePastPurpose`); this is the justification
    text itself, for the same screen to show it, not just complain about its absence.
    """
    out: dict[str, list[dict]] = {}
    for cid in ep.get("claims") or []:
        if not isinstance(cid, str) or not g.has(cid):
            continue
        c = g.get(cid)
        for entry in c.get("supportedBy") or []:
            if not isinstance(entry, dict):
                continue
            eid = entry.get("evidence")
            if not isinstance(eid, str):
                continue
            out.setdefault(eid, []).append({
                "claim": cid,
                "reuseJustification": entry.get("reuseJustification"),
                "assessableAt": c.get("assessableAt"),
            })
    return out


@router.get("/session/{s}/episode/{e}/evidence")
def get_evidence(s: str, e: str, request: Request, rendering: str = "full") -> dict:
    """The episode's evidence register, each item resolved through `object_view` (so a
    reader sees classification vs. metadata level, scope of validity, and reliability
    steps exactly as stored, withheld under `rendering="unclassified"` exactly as the
    package renderer withholds them), the per-item findings `kernel.scope.check_scope`
    already produces for it, and the claims that cite it with their reuse
    justification and assessability (`citedBy`). Findings that name no evidence item at
    all (e.g. `ModelUsePastPurpose`, keyed on a Model id) still appear in the top-level
    `findings` list — nothing is dropped, the same rule `readiness_report` follows."""
    _check_rendering(rendering)
    g = request.app.state.sessions.get(s).graph
    ep = g.get(e)
    findings = check_scope(g, e)
    findings_dicts = [f.to_dict() for f in findings]
    cited_by = _claims_citing_evidence(g, ep)
    items = []
    for eid in ep.get("evidenceRegister") or []:
        if not isinstance(eid, str):
            continue
        item_findings = [f.to_dict() for f in findings if eid in f.objects]
        item_cited_by = cited_by.get(eid, [])
        if g.has(eid):
            view = object_view(g, eid)
            withheld_object, withheld_level = _withhold_evidence_fields(g.get(eid), rendering)
            if withheld_level is not None:
                view["object"] = withheld_object
                view["slots"] = [s for s in view["slots"] if s["path"] not in _WITHHOLD_FIELDS]
            items.append({**view, "scopeFindings": item_findings, "citedBy": item_cited_by})
        else:
            items.append({"id": eid, "object": None, "scopeFindings": item_findings,
                          "citedBy": item_cited_by})
    return {"episode": e, "items": items, "findings": findings_dicts}


# ---- package / verify -----------------------------------------------------------------


@router.post("/session/{s}/episode/{e}/package")
def post_package(s: str, e: str, request: Request, rendering: str = "full") -> dict:
    _check_rendering(rendering)
    session = request.app.state.sessions.get(s)
    with writing(session) as g:
        pkg, text = build_package(g, e, rendering=rendering, now=_now(),
                                   out_dir=session.path / "packages")
    return {**pkg, "text": text}


@router.get("/session/{s}/package/{pkg}/text")
def get_package_text(s: str, pkg: str, request: Request) -> PlainTextResponse:
    g = request.app.state.sessions.get(s).graph
    p = g.get(pkg)  # KeyError -> 404 (global handler) if the id is unknown
    if p.get("type") != "DecisionPackage":
        raise KeyError(pkg)
    text = render_package(g, p["episode"], rendering=p["rendering"], now=p["renderedAt"])
    return PlainTextResponse(text, media_type="text/markdown")


class VerifyRequest(BaseModel):
    rendering: str = "full"


_DEFAULT_VERIFY_REQUEST = VerifyRequest()


@router.post("/session/{s}/episode/{e}/verify")
def post_verify(s: str, e: str, request: Request, body: VerifyRequest = _DEFAULT_VERIFY_REQUEST):
    g = request.app.state.sessions.get(s).graph
    if not g.has(e):
        raise KeyError(e)
    _check_rendering(body.rendering)
    try:
        return verify_package(g, e, rendering=body.rendering)
    except NoPackageBuilt as exc:
        return JSONResponse(status_code=409, content={"error": "no-package", "message": str(exc)})


# ---- export (plan 06) -----------------------------------------------------------------

_EXPORT_MEDIA_TYPES = {
    "json": "application/json", "xml": "application/xml",
    "csv": "text/csv", "md": "text/markdown",
}


@router.get("/session/{s}/episode/{e}/export")
def get_export(s: str, e: str, request: Request, format: str = "prov", rendering: str = "full"):
    """PROV-JSON, GSN, DMN, MIL-STD-3022, MADR or RTVM for this episode, via
    `docket.exports.export_text` (plan 06 Task 1).

    Guarded, not a hard import: `docket.exports` landed in this tree over the course of
    this task (this route table originally read `kernel.exports`, per the plan text
    written before plan 06 dispatched — reconciled here rather than left permanently
    501 against a module that now exists). If a future refactor ever removes it again,
    this degrades to 501 instead of 500 — a missing plan must not stop the server from
    booting for the event.
    """
    try:
        from docket import exports as export_module
    except ImportError:
        return JSONResponse(status_code=501, content={
            "error": "not-built", "plan": "06 Task 1",
            "message": "exports are not implemented until plan 06 lands",
        })
    if format not in export_module.EXPORTS:
        raise ValueError(f"format must be one of {sorted(export_module.EXPORTS)}, got {format!r}")
    _check_rendering(rendering)
    g = request.app.state.sessions.get(s).graph
    if not g.has(e):
        raise KeyError(e)
    text = export_module.export_text(g, name=format, episode_id=e, rendering=rendering)
    media_type = _EXPORT_MEDIA_TYPES.get(export_module.EXPORTS[format].extension, "text/plain")
    return PlainTextResponse(text, media_type=media_type)
