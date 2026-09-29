"""Policy validation rules (design §7.1). Registered into validate.POLICY_RULES on import.

Every rule here must tolerate a hand-edited or partially-written store: a missing or
malformed catalogue field is reported once by the structural `schema` rule, and a policy
rule must never itself raise for it. Rules read domain fields with `.get()` and skip
whatever they cannot interpret, rather than assuming the shape a clean `put()` guarantees.
A performed bias check whose evidence is a recorded gap is a recorded silence, not a
missing check — it is a weaker finding (a warning) than never having performed the check
at all (blocking), the same distinction P3 draws everywhere else between silence and gap.
"""

from __future__ import annotations

from collections import defaultdict

from docket.canon import canonical_json
from docket.kernel.findings import Finding
from docket.kernel.standards import _linchpin_flips
from docket.kernel.validate import POLICY_RULES, orphan_gaps
from docket.objects import is_content, is_exclusion_ref, is_gap_ref, is_marker, iter_refs
from docket.store import Graph


def _episodes(g: Graph, policy: dict | None) -> list[dict]:
    """The episodes a rule reads when it iterates `_episodes(g, policy)`.

    A Policy with a real `id` selects exactly the episodes whose charter names that id
    via `decisionClassPolicy` — plus any episode whose charter cannot be resolved at
    all, which fails open rather than guessing it does not belong.

    A `policy` with no `id` at all — `None`, `{}`, or any other dict lacking one — is
    not "select no episodes". It means the caller has no real Policy to read a *field*
    from: an episode whose charter never set `decisionClassPolicy`, or readiness.py's
    stand-in for a `decisionClassPolicy` that resolved to something that is not a
    Policy (the N1 fix). Matching `pol_id=None` against `charter.decisionClassPolicy`
    would only catch the first case and silently drop the second back to zero episodes,
    which is the bug this branch exists to close: with no `id` to match, every
    structure-only rule in this module (`baseline_present`, `objective_measured`,
    `linchpin_unevidenced`, ...) runs over every episode in the graph, because none of
    them reads a policy field and so none of them cares whose policy an episode names.
    The field-reading rules (`bias_checks_required`'s `requiredBiasChecks`,
    `exclusion_prohibited_reason`'s `prohibitedExclusionReasons`) call `.get(...)` on
    this same `{}`/`None` and find nothing, so widening the episode set here never
    manufactures a field-reading finding — only ever a structural one a real Policy
    would have produced anyway.
    """
    pol_id = policy.get("id") if isinstance(policy, dict) else None
    if pol_id is None:
        return list(g.all("DecisionEpisode"))
    out = []
    for ep in g.all("DecisionEpisode"):
        charter_id = ep.get("charter")
        ch = g.get(charter_id) if isinstance(charter_id, str) and g.has(charter_id) else None
        if ch is None or ch.get("decisionClassPolicy") == pol_id:
            out.append(ep)
    return out


def _objs(g: Graph, ids) -> list[dict]:
    if not isinstance(ids, list):
        return []
    return [g.get(i) for i in ids if isinstance(i, str) and g.has(i)]


def _episode_scope(g: Graph, ep_id: str) -> set[str]:
    """The episode's own id plus everything reachable forward from it."""
    if not isinstance(ep_id, str):
        return set()
    return {ep_id} | g.reachable_from(ep_id, reverse=False)


def _scope_ids(g: Graph, policy: dict) -> set[str]:
    """Every id in scope for `policy`: its episodes, plus what each reaches forward."""
    scope: set[str] = set()
    for ep in _episodes(g, policy):
        scope |= _episode_scope(g, ep.get("id"))
    return scope


def _episode_refs_ever(g: Graph, scope_ids: set[str]) -> set[str]:
    """Every id the in-scope episodes have referenced in *any* of their revisions.

    Live forward reachability is not enough for exclusion scoping. Excluding an object is
    how a human says "this is deliberately not part of the model any more", and the write
    that makes that true — dropping the id from the episode's list — is also the write
    that puts the object out of forward reach. Scoping on the live graph alone therefore
    makes an exclusion invisible to the very rules that exist to inspect it the moment it
    starts being effective: `exclusion_prohibited_reason` could not see a prohibited
    reason on any object that had actually been removed, and `silent_omission` could not
    see that an evidence item had been accounted for.

    The store is append-only, so the earlier revisions are still there to be asked. This
    walks `iter_refs` over each in-scope episode's whole history, which is exactly what
    `agent.review._ever_referenced` does for the G1 sheet; the two agree by construction.
    """
    ever: set[str] = set()
    for oid in scope_ids:
        if not g.has(oid):
            continue
        top = g.get(oid)
        if top.get("type") != "DecisionEpisode" or not isinstance(top.get("rev"), int):
            continue
        for rev in range(1, top["rev"] + 1):
            try:
                past = g.get(oid, rev)
            except (KeyError, TypeError):
                continue
            ever |= {target for _, target in iter_refs(past)}
    return ever


def _exclusion_in_scope(g: Graph, x: dict, scope_ids: set[str],
                        ever: set[str] | None = None) -> bool:
    """Whether Exclusion `x` belongs to the episode(s) behind `scope_ids`.

    True if the exclusion itself is reachable (via a ref or a $gap/$exclusion marker), or
    if what it targets is — now or in any earlier revision of an in-scope episode
    (`_episode_refs_ever`), because excluding an object is precisely what removes it from
    the live graph. A label-only target — no `id` at all, e.g. a Study or Question that
    never became a graph object — cannot be attributed to any one episode, so it is
    treated as in scope for every policy: failing safe means never letting a prohibited
    reason or a real omission hide behind an exclusion nobody can trace back to a decision.

    `ever` is the precomputed history set. Callers that loop over every Exclusion pass it
    once rather than paying for the history walk per exclusion.
    """
    if x.get("id") in scope_ids:
        return True
    target = x.get("target")
    target_id = target.get("id") if isinstance(target, dict) else None
    if target_id is not None:
        if ever is None:
            ever = _episode_refs_ever(g, scope_ids)
        return target_id in scope_ids or target_id in ever
    return True


def _norm_assertion_value(v):
    """1348 and 1348.0 are the same value; strings compare as themselves; anything
    unhashable (a list, a dict, a $gap/$exclusion marker) compares and displays via its
    canonical JSON, so a malformed assertion value can never crash the rule."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, list | dict):
        try:
            return canonical_json(v)
        except (TypeError, ValueError):
            return repr(v)
    return v


def baseline_present(g, policy):
    out = []
    for ep in _episodes(g, policy):
        alts = _objs(g, ep.get("alternatives"))
        if alts and not any(a.get("baselineFlag") for a in alts):
            out.append(Finding("baseline-present", "blocking", (ep.get("id"),),
                                "no status-quo alternative (DoDI 5000.84 §3.1.c)"))
    return out


def alternative_status_unreasoned(g, policy):
    """A screened-out/rejected Alternative must name why: an Exclusion or a Rationale."""
    out = []
    for ep in _episodes(g, policy):
        for a in _objs(g, ep.get("alternatives")):
            if a.get("status") not in ("screened-out", "rejected"):
                continue
            sr = a.get("statusReason")
            valid = (is_content(sr) and isinstance(sr, str) and g.has(sr)
                     and g.get(sr).get("type") in ("Exclusion", "Rationale"))
            if not valid:
                out.append(Finding(
                    "alternative-status-unreasoned", "blocking", (a.get("id"),),
                    "status requires a statusReason naming an existing Exclusion or Rationale",
                ))
    return out


def objective_measured(g, policy):
    out = []
    for ep in _episodes(g, policy):
        for o in _objs(g, ep.get("objectives")):
            if o.get("priority") == "primary" and not o.get("measures"):
                out.append(Finding("objective-measured", "blocking", (o.get("id"),),
                                    "primary objective has no Measure"))
    return out


def linchpin_unevidenced(g, policy):
    out = []
    for ep in _episodes(g, policy):
        for a in _objs(g, ep.get("assumptions")):
            if a.get("linchpin") and not is_content(a.get("evidence")):
                out.append(Finding(
                    "linchpin-unevidenced", "blocking", (a.get("id"),),
                    "linchpin assumption has no evidence (gap or exclusion recorded)",
                ))
    return out


def _has_sealed_run(g: Graph, ep: dict) -> bool:
    """Whether `ep` has at least one EvaluationRun to vary a linchpin against.

    An EvaluationRun is written by the kernel alone (`evaluate()`'s `sealedAt`/
    `sealedBy: kernel`), so an id in `ep["runs"]` that actually resolves to one is
    sealed by construction; a dangling or garbage entry — a hand-edited store pointing
    at nothing, or at some other type — is not a run to vary anything against, so it
    does not count."""
    run_ids = ep.get("runs")
    run_ids = run_ids if isinstance(run_ids, list) else []
    return any(isinstance(rid, str) and g.has(rid) and g.get(rid).get("type") == "EvaluationRun"
               for rid in run_ids)


def linchpin_not_varied(g, policy):
    """GAO-15-548 §7.1/§7.3: `Policy.requireAllLinchpinsVaried` was in the schema and
    set on every demo's Policy, but nothing read it — this rule is the reader.

    When the policy requires it, every linchpin Assumption in an episode that already
    has something to vary against (≥1 sealed EvaluationRun) must be named by some
    FlipAnalysis's `assumption` field. The traversal is `standards._linchpin_flips`,
    the same one DES-6's `all_linchpins_have_flip`/`some_linchpins_have_flip` use, so
    this rule and that scoring ladder can never disagree about which linchpins count
    as varied.

    Two silences are deliberate, not oversights:
    - `requireAllLinchpinsVaried` unset or false: DES-6's softer states (some/any
      varied, or listed-only) already score that record; this rule adds nothing.
    - No sealed run yet: there is nothing computed for a FlipAnalysis to vary against,
      so demanding one before the first evaluation would block a record for not having
      done work that cannot yet be done.
    """
    if not policy.get("requireAllLinchpinsVaried"):
        return []
    out = []
    for ep in _episodes(g, policy):
        if not _has_sealed_run(g, ep):
            continue
        linch, flip_by_assumption = _linchpin_flips(g, ep)
        for a in linch:
            aid = a.get("id")
            if aid not in flip_by_assumption:
                out.append(Finding(
                    "linchpin-not-varied", "blocking", (ep.get("id"), aid),
                    "policy.requireAllLinchpinsVaried is set but this linchpin "
                    "assumption has no FlipAnalysis naming it",
                ))
    return out


def model_vva(g, policy):
    out = []
    for ep in _episodes(g, policy):
        for m in _objs(g, ep.get("models")):
            v = m.get("vvaRecord")
            if not is_content(v) or not (isinstance(v, str) and g.has(v)):
                out.append(Finding("model-vva", "blocking", (m.get("id"),),
                                    "model has no VVARecord"))
                continue
            acc = g.get(v).get("accreditationDecision")
            if not is_content(acc):
                out.append(Finding("model-vva", "blocking", (m.get("id"), v),
                                    "VVARecord has no accreditation decision"))
            elif isinstance(acc, dict) and acc.get("basis") in ("interview", "verbal"):
                out.append(Finding(
                    "vva-verbal", "warning", (m.get("id"), v),
                    f"accreditation asserted by {acc.get('basis')}, not by document",
                ))
    return out


def bias_checks_required(g, policy):
    out = []
    for ep in _episodes(g, policy):
        checks = _objs(g, ep.get("biasChecks"))
        for ct in policy.get("requiredBiasChecks", []) or []:
            matching = [c for c in checks if c.get("checkType") == ct]
            performed_gap = [
                c for c in matching
                if c.get("status") == "performed" and is_gap_ref(c.get("producedEvidence"))
            ]
            ok = any(
                (c.get("status") == "performed" and is_content(c.get("producedEvidence")))
                or (c.get("status") == "waived" and c.get("waiver"))
                for c in matching
            )
            if ok:
                continue
            if performed_gap:
                for c in performed_gap:
                    out.append(Finding(
                        "bias-check-evidence-gap", "warning", (c.get("id"),),
                        f"bias check {ct} was performed but its evidence is a recorded gap",
                    ))
            else:
                out.append(Finding("bias-check-missing", "blocking", (ep.get("id"),),
                                    f"required bias check not performed: {ct}"))
    return out


def exclusion_prohibited_reason(g, policy):
    banned = {r for r in (policy.get("prohibitedExclusionReasons") or []) if isinstance(r, str)}
    scope = _scope_ids(g, policy)
    ever = _episode_refs_ever(g, scope)
    out = []
    for x in g.all("Exclusion"):
        if not _exclusion_in_scope(g, x, scope, ever):
            continue
        reason_type = x.get("reasonType")
        if isinstance(reason_type, str) and reason_type in banned:
            out.append(Finding(
                "exclusion-prohibited-reason", "blocking", (x.get("id"),),
                f"reasonType {reason_type} is prohibited (OAS AoA Handbook §4.7)",
            ))
    return out


def lexicon_mixed(g, policy):
    out = []
    for ep in _episodes(g, policy):
        scope = _episode_scope(g, ep.get("id"))
        uncertainties = [
            g.get(i) for i in scope if g.has(i) and g.get(i).get("type") == "Uncertainty"
        ]
        lexed = [u for u in uncertainties if isinstance(u.get("lexicon"), str)]
        if len({u["lexicon"] for u in lexed}) > 1:
            out.append(Finding(
                "lexicon-mixed", "blocking", tuple(sorted(u.get("id") for u in lexed)),
                "ICD 203 lexicons A and B mixed",
            ))
    return out


def claims_supported(g, policy):
    out = []
    for ep in _episodes(g, policy):
        for c in _objs(g, ep.get("claims")):
            sb = c.get("supportedBy")
            if is_gap_ref(sb):
                out.append(Finding("claim-on-gap", "warning", (c.get("id"),),
                                    "claim rests on an InsufficientEvidence object"))
            elif is_exclusion_ref(sb):
                out.append(Finding("claim-on-exclusion", "warning", (c.get("id"),),
                                    "claim rests on an excluded evidence source"))
            elif not is_content(sb) and not c.get("derivedFrom"):
                out.append(Finding("claim-unsupported", "blocking", (c.get("id"),),
                                    "claim has no supporting evidence or run"))
    return out


def silent_omission(g, policy):
    out = []
    scope = _scope_ids(g, policy)
    ever = _episode_refs_ever(g, scope)
    excluded: set[str] = set()
    for x in g.all("Exclusion"):
        if not _exclusion_in_scope(g, x, scope, ever):
            continue
        target = x.get("target")
        if isinstance(target, dict) and target.get("id"):
            excluded.add(target["id"])
    for ep in _episodes(g, policy):
        cited: set[str] = set()
        for c in _objs(g, ep.get("claims")):
            sb = c.get("supportedBy")
            if isinstance(sb, list):
                cited |= {e.get("evidence") for e in sb
                          if isinstance(e, dict) and e.get("evidence")}
        for ob in _objs(g, ep.get("observations")):
            if isinstance(ob.get("evidence"), str):
                cited.add(ob["evidence"])
        for ev_id in ep.get("evidenceRegister") or []:
            if not isinstance(ev_id, str):
                continue
            if ev_id not in cited and ev_id not in excluded:
                out.append(Finding(
                    "silent-omission", "blocking", (ep.get("id"), ev_id),
                    "evidence known to the episode is neither cited by a claim nor "
                    "excluded with a reason",
                ))
    return out


def inclusion_reason_missing(g, policy):
    """A cited Evidence object that does not say why it was included (GAO-23-106549 F3).

    The finding names **the episode, the claim and the evidence**, in that order, not the
    evidence alone. The rule does not fire on an evidence object sitting in a register: it
    fires because some *claim* of some *episode* cited it, and only that episode's claim
    is the occasion. Naming the evidence alone left every consumer that scopes findings by
    the objects they mention — `readiness_report`, and any per-episode view built on it —
    unable to tell which episode's claim caused the citation, so a shared evidence
    register reported the same finding on every episode that could reach the object. The
    episode comes first for the same reason `silent-omission` puts it first: it is the
    scoping key.
    """
    out = []
    for ep in _episodes(g, policy):
        ep_id = ep.get("id")
        for c in _objs(g, ep.get("claims")):
            sb = c.get("supportedBy")
            if not isinstance(sb, list):
                continue
            for e in sb:
                if not isinstance(e, dict):
                    continue
                ev_id = e.get("evidence")
                ev = g.get(ev_id) if isinstance(ev_id, str) and g.has(ev_id) else None
                if ev is None:
                    continue
                named = (ep_id, c.get("id"), ev.get("id"))
                where = (f"claim {c.get('id')} of episode {ep_id} cites evidence "
                         f"{ev.get('id')}, which ")
                if ("inclusionReason" in ev and not is_content(ev["inclusionReason"])
                        and not is_marker(ev["inclusionReason"])):
                    out.append(Finding("inclusion-reason-missing", "warning", named,
                                        where + "has an empty inclusionReason"))
                elif "inclusionReason" not in ev:
                    out.append(Finding(
                        "inclusion-reason-missing", "warning", named,
                        where + "does not state why it was included "
                        "(GAO-23-106549 F3)",
                    ))
    return sorted(set(out))


def value_conflicts(g, policy):
    ev_ids: set[str] = set()
    for ep in _episodes(g, policy):
        ev_ids |= {i for i in (ep.get("evidenceRegister") or []) if isinstance(i, str)}

    by_key: dict[tuple, list[tuple]] = defaultdict(list)
    # Sorted, not set order: the rows are joined into the finding's `message` below, and
    # set iteration order over strings changes with the process hash seed. Without this,
    # two runs of the same graph in two processes produce different finding text — which
    # would make every artefact that writes a value-conflict message unreproducible.
    for ev_id in sorted(ev_ids):
        if not g.has(ev_id):
            continue
        ev = g.get(ev_id)
        if ev.get("type") != "Evidence":
            continue
        for a in ev.get("assertions", []) or []:
            if not isinstance(a, dict):
                continue
            subject, field = a.get("subject"), a.get("field")
            if not isinstance(subject, str) or not isinstance(field, str):
                continue
            by_key[(subject, field)].append((ev.get("id"), a.get("locator"), a.get("value")))

    out = []
    for (subject, field), rows in sorted(by_key.items()):
        norm_values = {_norm_assertion_value(v) for _, _, v in rows}
        if len(norm_values) < 2:
            continue
        per_ev: dict[str, set] = defaultdict(set)
        for ev_id, _, v in rows:
            per_ev[ev_id].add(_norm_assertion_value(v))
        internal = sorted(e for e, vs in per_ev.items() if len(vs) > 1)
        distinct_ev_ids = {e for e, _, _ in rows}
        detail = "; ".join(f"{e}@{loc}={v}" for e, loc, v in rows)
        if internal:
            out.append(Finding(
                "value-conflict-internal", "blocking", tuple(internal),
                f"{subject}.{field} takes different values within one document: {detail}",
            ))
        if len(distinct_ev_ids) >= 2:
            out.append(Finding(
                "value-conflict", "warning", tuple(sorted(distinct_ev_ids)),
                f"{subject}.{field} disagrees across sources: {detail}",
            ))
    return out


def gap_unconfirmed(g, policy):
    """Every recorded gap needs a human signature — including the ones nothing points at.

    `orphan_gaps` (a gap no object references) is in scope for every policy, not none.
    The elicitation mapper writes one when the model reports having looked for something
    and names a field that does not exist, and no catalogue type has a field that can hold
    a free-standing gap, so reachability alone would drop it out of this rule, out of the
    G1 sheet and out of `lifecycle.c_gaps_confirmed` at once — and the record would then
    be signed asserting every gap was confirmed. Same fail-safe as a label-only Exclusion
    in `_exclusion_in_scope`: an omission nobody can attribute belongs to everybody.
    """
    scope = _scope_ids(g, policy) | orphan_gaps(g)
    return [
        Finding("gap-unconfirmed", "warning", (x.get("id"),),
                "InsufficientEvidence not confirmed by a human")
        for x in g.all("InsufficientEvidence")
        if x.get("id") in scope and not is_content(x.get("confirmedBy"))
    ]


def definition_missing(g, policy):
    out = []
    seen_charters: set[str] = set()
    for ep in _episodes(g, policy):
        charter_id = ep.get("charter")
        if not isinstance(charter_id, str) or not g.has(charter_id) or charter_id in seen_charters:
            continue
        seen_charters.add(charter_id)
        ch = g.get(charter_id)
        for d in ch.get("definitions", []) or []:
            if not isinstance(d, dict):
                continue
            if not is_content(d.get("text")):
                term = d.get("term", "<unknown>")
                out.append(Finding("definition-missing", "warning", (ch.get("id"),),
                                    f"scope term undefined: {term} (GAO-23-106549 F9)"))
    return out


def observation_duplicate(g, policy):
    """Two Observations for the same (alternative, measure) in one episode are
    ambiguous kernel input — the evaluator would otherwise have to guess which one
    to use. One finding per colliding (alternative, measure) pair, naming every id."""
    out = []
    for ep in _episodes(g, policy):
        by_key: dict[tuple, list[str]] = defaultdict(list)
        for ob in _objs(g, ep.get("observations")):
            alt, msr = ob.get("alternative"), ob.get("measure")
            if isinstance(alt, str) and isinstance(msr, str):
                by_key[(alt, msr)].append(ob.get("id"))
        for (alt, msr), ids in sorted(by_key.items()):
            if len(ids) > 1:
                out.append(Finding(
                    "observation-duplicate", "blocking", tuple(sorted(ids)),
                    f"multiple Observations for alternative {alt} measure {msr}",
                ))
    return out


def assumption_conflict(g, policy):
    scope = _scope_ids(g, policy)
    out = []
    for a in g.all("Assumption"):
        if a.get("id") not in scope:
            continue
        conflicts = a.get("conflictsWith")
        if isinstance(conflicts, list) and conflicts:
            names = ", ".join(str(c) for c in conflicts)
            out.append(Finding("assumption-conflict", "warning", (a.get("id"),),
                                "assumption conflicts with " + names))
    return out


POLICY_RULES.extend([
    baseline_present, alternative_status_unreasoned, objective_measured,
    linchpin_unevidenced, linchpin_not_varied, model_vva, bias_checks_required,
    exclusion_prohibited_reason, lexicon_mixed, claims_supported, silent_omission,
    inclusion_reason_missing, value_conflicts, gap_unconfirmed, definition_missing,
    assumption_conflict, observation_duplicate,
])
