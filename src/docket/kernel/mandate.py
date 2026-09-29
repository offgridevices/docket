"""Mandate-element scorecard — the separate track GAO runs alongside the standards
(design §2.1 item 7, §7.1/§10).

Every mandate element is read with `.get()`/`isinstance` rather than assuming the shape
a clean `put()` guarantees: this runs over a graph that may have been hand-edited or
written by an older kernel version, and it must never raise for a dangling reference or
a missing field — that is the structural `schema`/`ref-integrity` rules' job, reported
once, not this function's job to detect twice by crashing.
"""

from __future__ import annotations

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.objects import is_content
from docket.store import Graph


def _row_status(m: dict, supported: bool) -> object:
    """The element's declared status, reconciled against whether it is actually
    supported. A non-string/missing `status` is passed through unchanged: it is not
    this function's job to invent a value for it, and `g.put` will reject the row at
    write time via the MandateScorecard schema rather than this function guessing.
    """
    status = m.get("status")
    if status == "not-applicable":
        if is_content(m.get("statusReason")):
            return "not-applicable"
        return "not-applicable-unreasoned"
    if status in ("satisfied", "partial"):
        return status if supported else "asserted-unsupported"
    return status


def _claim_actually_supports(g: Graph, claim_id: str) -> bool:
    """Whether `claim_id` is real support, not just a claim that says so.

    A claim derived from an EvaluationRun is supported by the deterministic
    computation itself. Otherwise every cited `supportedBy[].evidence` must resolve to
    an `Evidence` object whose `reviewStatus` is not `rejected`/`draft` — a `$gap`/
    `$exclusion` marker in the (slotted) `supportedBy` field is not content at all, and
    a dangling or unreadable evidence reference is treated as unsupported rather than
    silently ignored (fail closed, not fail open).
    """
    c = g.get(claim_id)
    if is_content(c.get("derivedFrom")):
        return True
    sb = c.get("supportedBy")
    if not is_content(sb) or not isinstance(sb, list) or not sb:
        return False
    for entry in sb:
        if not isinstance(entry, dict):
            return False
        ev_id = entry.get("evidence")
        if not isinstance(ev_id, str) or not g.has(ev_id):
            return False
        if g.get(ev_id).get("reviewStatus") in ("rejected", "draft"):
            return False
    return True


def score_mandate(g: Graph, episode_id: str, *, now: str) -> dict:
    """Score every MandateElement the episode names against what actually satisfies it.

    A row's status is the element's declared status when at least one cited Claim
    actually supports it (every one of its cited evidence items is reviewed, or the
    claim is derived from a run), else `"asserted-unsupported"`. `not-applicable` with
    no `statusReason` is `"not-applicable-unreasoned"`.
    """
    ep = g.get(episode_id)
    rows = []
    for mid in ep.get("mandateElements") or []:
        if not isinstance(mid, str) or not g.has(mid):
            continue
        m = g.get(mid)
        cited = [
            c for c in (m.get("satisfiedBy") or []) if isinstance(c, str) and g.has(c)
        ]
        supported = bool(cited) and any(_claim_actually_supports(g, c) for c in cited)
        rows.append({"element": mid, "status": _row_status(m, supported), "satisfiedBy": cited})
    n = 1 + sum(1 for o in g.all("MandateScorecard") if o.get("episode") == episode_id)
    ms = {
        "id": f"ms-{episode_id}-{n}",
        "type": "MandateScorecard",
        "rev": 1,
        "createdBy": KERNEL_ACTOR,
        "createdAt": now,
        "episode": episode_id,
        "rows": rows,
        "kernelVersion": KERNEL_VERSION,
    }
    g.put(ms, KERNEL_ACTOR)
    return ms
