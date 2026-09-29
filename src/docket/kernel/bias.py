"""Computed bias indicators (design §7.6). Each is a Risk with an owner, never a
verdict — the kernel names a pattern in the record, a human decides what it means.

Every check here reads domain fields with `.get()`/`isinstance` and skips whatever it
cannot interpret, exactly like the scope checker and the policy rules: a missing or
malformed field is reported once by the structural `schema` rule, and this module must
never itself raise for it, including on a dangling reference (skipped, not followed —
ref-integrity is a different rule's job).
"""

from __future__ import annotations

from docket import KERNEL_ACTOR
from docket.kernel.findings import Finding
from docket.kernel.scope import check_scope
from docket.kernel.validate import validate
from docket.objects import is_content
from docket.store import Graph

_NUMBER = int | float


def _is_number(x: object) -> bool:
    """A real int/float, not a bool (bool is an int subclass in Python)."""
    return isinstance(x, _NUMBER) and not isinstance(x, bool)


def _policy_for(g: Graph, ep: dict) -> dict | None:
    charter_id = ep.get("charter")
    if not isinstance(charter_id, str) or not g.has(charter_id):
        return None
    policy_id = g.get(charter_id).get("decisionClassPolicy")
    if not isinstance(policy_id, str) or not g.has(policy_id):
        return None
    return g.get(policy_id)


def _ref_list(g: Graph, ids: object) -> list[str]:
    """The subset of `ids` that are strings resolving to a real object, order preserved."""
    if not isinstance(ids, list):
        return []
    return [i for i in ids if isinstance(i, str) and g.has(i)]


def _selected(g: Graph, ep: dict) -> str | None:
    """Commitment.selected, else the Alternative marked `status: selected`, else the
    top of the most recent run's ranking. None of these need exist."""
    commitment_id = ep.get("commitment")
    if isinstance(commitment_id, str) and g.has(commitment_id):
        selected = g.get(commitment_id).get("selected")
        if isinstance(selected, str):
            return selected
    for a in _ref_list(g, ep.get("alternatives")):
        if g.get(a).get("status") == "selected":
            return a
    runs = _ref_list(g, ep.get("runs"))
    if runs:
        ranking = g.get(runs[-1]).get("ranking")
        if isinstance(ranking, list) and ranking and isinstance(ranking[0], str):
            return ranking[0]
    return None


def _risk(ep_id: str, kind: str, statement: str, consequence: str,
          evidence: list[str], now: str) -> dict:
    return {
        "id": f"risk-bias-{ep_id}-{kind.removeprefix('bias-')}",
        "type": "Risk",
        "rev": 1,
        "createdBy": KERNEL_ACTOR,
        "createdAt": now,
        "statement": statement,
        "kind": kind,
        "consequence": consequence,
        "owner": "unassigned",
        "status": "open",
        "evidence": sorted({e for e in evidence if isinstance(e, str)}),
    }


def _anchoring_and_confirmation(g: Graph, episode_id: str, ep: dict, now: str) -> list[dict]:
    sel = _selected(g, ep)
    alt_ids = _ref_list(g, ep.get("alternatives"))
    if not sel or not alt_ids or not g.has(sel):
        return []
    alts = [g.get(a) for a in alt_ids]
    s = g.get(sel)
    risks: list[dict] = []

    entered_orders = [a.get("enteredOrder") for a in alts if _is_number(a.get("enteredOrder"))]
    sel_order = s.get("enteredOrder")
    first = (
        _is_number(sel_order) and bool(entered_orders) and sel_order == min(entered_orders)
    )
    short = [
        fa["id"] for fa in (g.get(f) for f in _ref_list(g, ep.get("flipAnalyses")))
        if is_content(fa.get("assumption"))
        and _is_number(fa.get("flipDistance"))
        and fa["flipDistance"] < 0.1
    ]
    if (first or s.get("baselineFlag")) and short:
        risks.append(_risk(
            episode_id, "bias-anchoring",
            f"selected alternative {sel} was the first entered or the baseline and a "
            "linchpin assumption flips the ranking within 10% of its range",
            "the selection may reflect the order of consideration rather than the evidence",
            [sel, *short], now,
        ))

    obs = [g.get(o) for o in _ref_list(g, ep.get("observations"))]

    def rate(alt_id_set: set[str]) -> float | None:
        evs = []
        for o in obs:
            ev_ref = o.get("evidence")
            if (o.get("alternative") in alt_id_set and is_content(ev_ref)
                    and isinstance(ev_ref, str) and g.has(ev_ref)):
                evs.append(g.get(ev_ref))
        if not evs:
            return None
        return sum(1 for e in evs if e.get("reviewStatus") == "reviewed") / len(evs)

    other_ids = {a.get("id") for a in alts if isinstance(a.get("id"), str) and a.get("id") != sel}
    r_sel, r_oth = rate({sel}), rate(other_ids)
    if r_sel is not None and r_oth is not None and r_sel - r_oth > 0.25:
        risks.append(_risk(
            episode_id, "bias-confirmation",
            f"evidence for {sel} is reviewed at rate {r_sel:.2f} vs {r_oth:.2f} for the others",
            "perceived bias in the selection and vetting of analyses (GAO-23-106549 p. 11)",
            [sel], now,
        ))
    return risks


def _selection(g: Graph, episode_id: str, findings: list[Finding], now: str) -> dict | None:
    sel_ids = [
        x.get("id") for x in g.all("Exclusion")
        if x.get("reasonType") == "other" and isinstance(x.get("id"), str)
    ]
    sel_ids += [
        o for f in findings if f.rule in ("silent-omission", "inclusion-reason-missing")
        for o in f.objects if o != episode_id
    ]
    if not sel_ids:
        return None
    return _risk(
        episode_id, "bias-selection",
        "evidence excluded without a typed reason, or included without a stated reason",
        "perceived bias in the selection of analyses (GAO-23-106549 F2/F3)",
        sel_ids, now,
    )


def _hard_specified(m: dict) -> bool:
    """A measure is hard-specified when it states a threshold with nothing to contrast
    it against: design §7.6 is thresholds *vs* objectives-level criteria, so a measure
    that legitimately states both (the doctrinally normal OAS Table 5-2 shape) does not
    count — only a threshold with no `criteria.objective` does."""
    criteria = m.get("criteria")
    if not is_content(criteria) or not isinstance(criteria, dict):
        return False
    return is_content(criteria.get("threshold")) and not is_content(criteria.get("objective"))


def _over_specification(g: Graph, episode_id: str, ep: dict, now: str) -> dict | None:
    measure_ids: list[str] = []
    for oid in _ref_list(g, ep.get("objectives")):
        for m in g.get(oid).get("measures") or []:
            if isinstance(m, str):
                measure_ids.append(m)
    ms = [g.get(m) for m in measure_ids if g.has(m)]
    if len(ms) < 2:
        return None
    hard = [m["id"] for m in ms if _hard_specified(m)]
    if len(hard) / len(ms) <= 0.8:
        return None
    return _risk(
        episode_id, "bias-over-specification",
        f"{len(hard)} of {len(ms)} measures carry a hard threshold with no "
        "objectives-level criteria to contrast it against",
        "requirements over-specified relative to objectives-level criteria "
        "(GAO-25-107569 XM30 critique; design §7.6)",
        hard, now,
    )


_ENVELOPE_FIELDS = ("id", "rev", "createdBy", "createdAt")


def _write_risk_idempotent(g: Graph, risk: dict) -> dict:
    """Write `risk`, but idempotently.

    A repeat call (e.g. a second `readiness_report`) recomputes the same indicators
    against a graph that may not have changed at all, and the Risk id is
    content-independent (`risk-bias-{episode}-{kind}`), so a naive `g.put` of a fresh
    `rev: 1` candidate would collide with the store's append-only check. If a Risk with
    this id already exists and its content (everything but the envelope fields) is
    unchanged, skip the write entirely and return the stored object as-is — including
    its original `createdAt`, since nothing new actually happened. If the content
    differs, write the next kernel revision instead of a rev-1 stub.
    """
    rid = risk["id"]
    if g.has(rid):
        existing = g.get(rid)
        new_body = {k: v for k, v in risk.items() if k not in _ENVELOPE_FIELDS}
        old_body = {k: v for k, v in existing.items() if k not in _ENVELOPE_FIELDS}
        if new_body == old_body:
            return existing
        risk = {**risk, "rev": existing["rev"] + 1}
    return g.put(risk, KERNEL_ACTOR)


def bias_indicators(g: Graph, episode_id: str, *, now: str) -> list[dict]:
    """Fire the computed bias indicators for `episode_id` and record every one that
    fires as an open, unassigned Risk on the episode: a fresh Risk is written, an
    existing one whose content changed is revised, and an existing one whose content is
    unchanged is left alone (see `_write_risk_idempotent`). Returns the current stored
    state of every indicator that fires on this call, not any pre-existing bias-kind
    Risk that doesn't fire this time."""
    ep = g.get(episode_id)
    policy = _policy_for(g, ep)
    findings = validate(g, policy) + check_scope(g, episode_id)

    candidates = _anchoring_and_confirmation(g, episode_id, ep, now)
    selection_risk = _selection(g, episode_id, findings, now)
    if selection_risk is not None:
        candidates.append(selection_risk)
    over_spec_risk = _over_specification(g, episode_id, ep, now)
    if over_spec_risk is not None:
        candidates.append(over_spec_risk)

    risks = [_write_risk_idempotent(g, r) for r in candidates]

    ep_latest = g.get(episode_id)
    existing_risk_ids = ep_latest.get("risks") or []
    to_append = [r["id"] for r in risks if r["id"] not in existing_risk_ids]
    if to_append:
        g.put({
            **ep_latest,
            "rev": ep_latest["rev"] + 1,
            "createdBy": KERNEL_ACTOR,
            "createdAt": now,
            "risks": existing_risk_ids + to_append,
        }, KERNEL_ACTOR)
    return risks
