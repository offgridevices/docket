"""Standards scorer (design §7.5): YAML clauses over named predicates; four-state
ratings; dimension verdicts.

Every predicate here must tolerate a hand-edited or partially-written store, exactly
like the policy rules and the scope checker: a missing or malformed field is reported
once by the structural `schema` rule, and a predicate must never itself raise for it.
Fields are read with `.get()` and checked with `isinstance` rather than assumed to have
the shape a clean `put()` guarantees; a predicate given a garbage `ep` returns
`(False, [])` rather than crashing the scorer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.kernel.findings import Finding
from docket.kernel.scope import check_scope
from docket.kernel.validate import WHOLE_STORE_RULES, validate
from docket.objects import is_content, is_exclusion_ref
from docket.standard import load_rules, load_standard, load_tailoring
from docket.store import Graph

Pred = Callable[[Graph, dict, "Context"], tuple[bool, list[str]]]
PREDICATES: dict[str, Pred] = {}


@dataclass
class Context:
    policy: dict
    findings: list[Finding] = field(default_factory=list)
    scope: list[Finding] = field(default_factory=list)
    args: dict = field(default_factory=dict)
    # Every id forward-reachable from the episode, plus the episode's own id. `validate()`
    # and `check_scope()` run over the whole store, so a Finding they raise may name an
    # object that belongs to a different episode entirely; `_has_finding` and
    # `conclusions_sound` use `reach` to ignore those instead of letting one episode's
    # problems silently degrade another's rating.
    reach: set[str] = field(default_factory=set)


def build_context(g: Graph, episode_id: str) -> Context:
    ep = g.get(episode_id)
    charter_id = ep.get("charter")
    charter = g.get(charter_id) if isinstance(charter_id, str) and g.has(charter_id) else {}
    policy_id = charter.get("decisionClassPolicy")
    policy = g.get(policy_id) if isinstance(policy_id, str) and g.has(policy_id) else {}
    if isinstance(episode_id, str):
        reach = {episode_id} | g.reachable_from(episode_id, reverse=False)
    else:
        reach = set()
    return Context(policy=policy, findings=validate(g, policy), scope=check_scope(g, episode_id),
                    reach=reach)


def pred(name: str):
    def deco(fn: Pred):
        PREDICATES[name] = fn
        return fn
    return deco


def _objs(g, ids):
    if not isinstance(ids, list):
        return []
    return [g.get(i) for i in ids if isinstance(i, str) and g.has(i)]


def _existing_ids(g, ids):
    """The subset of a raw reference list that actually resolves, for predicates whose
    truth condition (`bool(ids)` — "listed", not "resolved") must not change but whose
    justification must never name a dangling id."""
    if not isinstance(ids, list):
        return []
    return sorted(i for i in ids if isinstance(i, str) and g.has(i))


def _all(items, cond, ids):
    """True iff every id in `ids` resolves to an object in the graph and every resolved
    object satisfies `cond`. A dangling id fails the clause outright: a listed
    assumption (or measure, or constraint...) the store cannot find cannot be judged
    "all" anything, so it must not be silently dropped the way `_objs`'s own filtering
    would drop it. Justification is always the resolved objects' own ids, never a raw,
    possibly-dangling id — see `score_question`'s belt-and-suspenders filter too.
    """
    items = list(items)
    ok = bool(ids) and len(items) == len(ids) and all(cond(x) for x in items)
    return ok, _ids(items)


def _some(items, cond, ids):
    items = list(items)
    return any(cond(x) for x in items), _ids(items)


def _ref(g, oid):
    return g.get(oid) if isinstance(oid, str) and g.has(oid) else None


def _charter(g, ep):
    return _ref(g, ep.get("charter")) or {}


def _plan(g, ep):
    return _ref(g, ep.get("plan"))


def _cited_evidence(g, ep) -> list[dict]:
    """Evidence cited either by a Claim's supportedBy or by an Observation."""
    seen: dict[str, dict] = {}
    for c in _objs(g, ep.get("claims")):
        sb = c.get("supportedBy")
        if isinstance(sb, list):
            for e in sb:
                if isinstance(e, dict):
                    ev_id = e.get("evidence")
                    if isinstance(ev_id, str) and g.has(ev_id):
                        seen[ev_id] = g.get(ev_id)
    for o in _objs(g, ep.get("observations")):
        ev_id = o.get("evidence")
        if isinstance(ev_id, str) and g.has(ev_id):
            seen[ev_id] = g.get(ev_id)
    return [seen[k] for k in sorted(seen)]


def _claims_evidence(g, ep) -> list[dict]:
    """Evidence cited by a Claim's supportedBy only (not Observations)."""
    seen: dict[str, dict] = {}
    for c in _objs(g, ep.get("claims")):
        sb = c.get("supportedBy")
        if isinstance(sb, list):
            for e in sb:
                if isinstance(e, dict):
                    ev_id = e.get("evidence")
                    if isinstance(ev_id, str) and g.has(ev_id):
                        seen[ev_id] = g.get(ev_id)
    return [seen[k] for k in sorted(seen)]


def _counts_for_episode(ctx, f) -> bool:
    """Whether Finding `f` bears on this episode: a store-integrity finding always does;
    anything else does when it names no object at all, or names one this episode reaches.
    A Finding entirely about another episode's objects does not count."""
    return (f.rule in WHOLE_STORE_RULES or not f.objects
            or bool(set(f.objects) & ctx.reach))


def _has_finding(ctx, rule):
    return any(f.rule == rule and _counts_for_episode(ctx, f)
               for f in ctx.findings + ctx.scope)


def _ids(objs):
    return [o.get("id") for o in objs if isinstance(o, dict) and o.get("id")]


# ---- design ---------------------------------------------------------------
@pred("always")
def _always(g, ep, ctx):
    return True, []


@pred("charter_complete")
def _charter_complete(g, ep, ctx):
    ch = _charter(g, ep)
    ok = all(is_content(ch.get(k))
             for k in ("question", "decisionToBeMade", "consequencesOfErroneousOutput"))
    return ok, [ch["id"]] if ch.get("id") else []


@pred("charter_partial")
def _charter_partial(g, ep, ctx):
    ch = _charter(g, ep)
    ok = any(is_content(ch.get(k))
             for k in ("question", "decisionToBeMade", "consequencesOfErroneousOutput"))
    return ok, [ch["id"]] if ch.get("id") else []


@pred("charter_complete_and_plan_approved")
def _cc_pa(g, ep, ctx):
    ok, ids = PREDICATES["charter_complete"](g, ep, ctx)
    plan = _plan(g, ep)
    approved = plan is not None and is_content(plan.get("approvedBy"))
    return ok and approved, ids + ([plan["id"]] if plan and plan.get("id") else [])


@pred("charter_question_stated")
def _cq(g, ep, ctx):
    ch = _charter(g, ep)
    return is_content(ch.get("question")), [ch["id"]] if ch.get("id") else []


def _terms_defined(ch):
    defs = ch.get("definitions")
    defs = defs if isinstance(defs, list) else []
    return all(is_content(d.get("text")) for d in defs if isinstance(d, dict))


@pred("charter_question_and_terms_defined")
def _cqt(g, ep, ctx):
    ch = _charter(g, ep)
    ok = is_content(ch.get("question")) and _terms_defined(ch)
    return ok, [ch["id"]] if ch.get("id") else []


@pred("scope_defined")
def _scope_defined(g, ep, ctx):
    ch = _charter(g, ep)
    scope = ch.get("scope")
    included = scope.get("included") if isinstance(scope, dict) else None
    return bool(included), [ch["id"]] if ch.get("id") else []


@pred("scope_defined_and_terms_defined")
def _sdt(g, ep, ctx):
    ch = _charter(g, ep)
    scope = ch.get("scope")
    included = scope.get("included") if isinstance(scope, dict) else None
    ok = bool(included) and _terms_defined(ch) and not _has_finding(ctx, "definition-missing")
    return ok, [ch["id"]] if ch.get("id") else []


@pred("assumptions_listed")
def _al(g, ep, ctx):
    ids = ep.get("assumptions")
    ids = ids if isinstance(ids, list) else []
    return bool(ids), _existing_ids(g, ids)


@pred("assumptions_all_have_rationale")
def _aar(g, ep, ctx):
    ids = ep.get("assumptions")
    ids = ids if isinstance(ids, list) else []
    return _all(_objs(g, ids), lambda a: is_content(a.get("rationale")), list(ids))


@pred("assumptions_all_evidenced_and_consistent")
def _aaec(g, ep, ctx):
    ids = ep.get("assumptions")
    ids = ids if isinstance(ids, list) else []
    ok, rids = _all(_objs(g, ids), lambda a: is_content(a.get("evidence")), list(ids))
    return ok and not _has_finding(ctx, "assumption-conflict"), rids


@pred("assumptions_some_evidenced")
def _ase(g, ep, ctx):
    ids = ep.get("assumptions")
    ids = ids if isinstance(ids, list) else []
    return _some(_objs(g, ids), lambda a: is_content(a.get("evidence")), list(ids))


def _linchpin_flips(g, ep):
    """The episode's linchpin Assumptions, and a map of assumption id -> the id of the
    FlipAnalysis that varied it (first one found wins)."""
    flip_by_assumption: dict[str, str] = {}
    for f in _objs(g, ep.get("flipAnalyses")):
        aid, fid = f.get("assumption"), f.get("id")
        if isinstance(aid, str) and isinstance(fid, str):
            flip_by_assumption.setdefault(aid, fid)
    linch = [a for a in _objs(g, ep.get("assumptions")) if a.get("linchpin")]
    return linch, flip_by_assumption


@pred("all_linchpins_have_flip")
def _alhf(g, ep, ctx):
    # At DES-6 state 1 this is the only clause that fires, so it has to name both halves
    # of what it found: the flip analyses *and* the linchpins they cover. A renderer
    # asked "why state 1?" otherwise gets a bare list of flip ids with nothing to say
    # which assumptions they discharge.
    linch, flip_by_assumption = _linchpin_flips(g, ep)
    ok = bool(linch) and all(a.get("id") in flip_by_assumption for a in linch)
    fids = {flip_by_assumption[a["id"]] for a in linch if a.get("id") in flip_by_assumption}
    return ok, sorted(fids) + _ids(linch)


@pred("some_linchpins_have_flip")
def _slhf(g, ep, ctx):
    linch, flip_by_assumption = _linchpin_flips(g, ep)
    hits = [a for a in linch if a.get("id") in flip_by_assumption]
    fids = {flip_by_assumption[a["id"]] for a in hits}
    return bool(hits), sorted(fids)


@pred("any_assumption_varied")
def _aav(g, ep, ctx):
    ids = ep.get("assumptions")
    ids = ids if isinstance(ids, list) else []
    return _some(_objs(g, ids), lambda a: bool(a.get("variedInSensitivity")), list(ids))


@pred("constraints_listed")
def _cl(g, ep, ctx):
    ids = ep.get("constraints")
    ids = ids if isinstance(ids, list) else []
    return bool(ids), _existing_ids(g, ids)


@pred("constraints_discussed")
def _cd(g, ep, ctx):
    ids = ep.get("constraints")
    ids = ids if isinstance(ids, list) else []
    return _all(_objs(g, ids), lambda c: is_content(c.get("implications")), list(ids))


@pred("scenarios_listed")
def _sl(g, ep, ctx):
    ids = ep.get("scenarios")
    ids = ids if isinstance(ids, list) else []
    return bool(ids), _existing_ids(g, ids)


@pred("scenarios_have_rationale")
def _shr(g, ep, ctx):
    ids = ep.get("scenarios")
    ids = ids if isinstance(ids, list) else []
    return _all(_objs(g, ids), lambda s: is_content(s.get("rationale")), list(ids))


@pred("scenarios_cover_conditions")
def _scc(g, ep, ctx):
    ch = _charter(g, ep)
    want = ch.get("conditionsOfInterest")
    want = set(want) if isinstance(want, list) else set()
    have: set[str] = set()
    scen_ids = ep.get("scenarios")
    scen_ids = scen_ids if isinstance(scen_ids, list) else []
    for s in _objs(g, scen_ids):
        conds = s.get("conditions")
        if isinstance(conds, list):
            have |= {c for c in conds if isinstance(c, str)}
    ids = ([ch["id"]] if ch.get("id") else []) + _existing_ids(g, scen_ids)
    return bool(want) and want <= have, ids


@pred("plan_exists")
def _pe(g, ep, ctx):
    plan = _plan(g, ep)
    return plan is not None, [plan["id"]] if plan and plan.get("id") else []


@pred("plan_followed")
def _pf(g, ep, ctx):
    plan = _plan(g, ep)
    if plan is None:
        return False, []
    steps = plan.get("steps")
    steps = steps if isinstance(steps, list) else []
    steps_run = set()
    for r in _objs(g, ep.get("runs")):
        step = r.get("step")
        if isinstance(step, str):
            steps_run.add(step)
    ok = all(isinstance(s, dict) and s.get("id") in steps_run for s in steps)
    ids = ([plan["id"]] if plan.get("id") else []) + _existing_ids(g, ep.get("runs"))
    return ok, ids


@pred("deviations_documented")
def _dd(g, ep, ctx):
    """DES-11's no-concerns bar: the Plan carries a `deviations` list, and every entry in
    it states a reason.

    The list must be *present*. An explicit `[]` is a human saying "the plan was followed
    as written"; an absent field says nothing at all, and reading silence as "no
    deviations" would let DES-11 answer "no concerns" from a field nobody filled in. The
    empty list is the shortest complete answer, not the absence of one.
    """
    plan = _plan(g, ep)
    if plan is None:
        return False, []
    deviations = plan.get("deviations")
    if not isinstance(deviations, list):
        return False, []
    ok = all(isinstance(d, dict) and is_content(d.get("reason")) for d in deviations)
    return ok, [plan["id"]] if plan.get("id") else []


@pred("mandate_elements_covered")
def _mec(g, ep, ctx):
    ids = ep.get("mandateElements")
    ids = ids if isinstance(ids, list) else []

    def ok_one(m):
        return (m.get("status") in ("satisfied", "not-applicable")
                and bool(m.get("satisfiedBy") or m.get("statusReason")))

    return _all(_objs(g, ids), ok_one, list(ids))


@pred("mandate_elements_some")
def _mes(g, ep, ctx):
    ids = ep.get("mandateElements")
    ids = ids if isinstance(ids, list) else []
    return _some(_objs(g, ids), lambda m: m.get("status") in ("satisfied", "partial"), list(ids))


@pred("limitations_identified_and_mitigated")
def _lim(g, ep, ctx):
    ch = _charter(g, ep)
    lims = ch.get("limitations")
    lims = lims if isinstance(lims, list) else []
    ok = bool(lims) and all(isinstance(x, dict) and is_content(x.get("mitigation"))
                             for x in lims)
    return ok, [ch["id"]] if ch.get("id") else []


@pred("limitations_some")
def _lims(g, ep, ctx):
    ch = _charter(g, ep)
    lims = ch.get("limitations")
    return bool(lims), [ch["id"]] if ch.get("id") else []


@pred("bias_checks_performed_no_open_risks")
def _bcpnor(g, ep, ctx):
    """DES-14 no-concerns bar: at least one BiasCheck actually `performed`, not merely
    required or waived, and no open bias-kind Risk. Assumptions listed with no performed
    check at all is "some concerns" (DES-14's state-2 fallback, `assumptions_listed`),
    not "no concerns"."""
    check_ids = ep.get("biasChecks")
    check_ids = check_ids if isinstance(check_ids, list) else []
    performed = [c for c in _objs(g, check_ids) if c.get("status") == "performed"]
    risk_ids = ep.get("risks")
    risk_ids = risk_ids if isinstance(risk_ids, list) else []
    risks = [r for r in _objs(g, risk_ids)
             if isinstance(r.get("kind"), str) and r["kind"].startswith("bias-")
             and r.get("status") == "open"]
    assumption_ids = ep.get("assumptions")
    ok = bool(assumption_ids) and bool(performed) and not risks
    return ok, _ids(performed) + _ids(risks)


# ---- execution --------------------------------------------------------------
@pred("methodology_covers_objectives")
def _mco(g, ep, ctx):
    plan = _plan(g, ep)
    if plan is None:
        return False, []
    steps = plan.get("steps")
    steps = steps if isinstance(steps, list) else []
    covered: set[str] = set()
    for s in steps:
        if isinstance(s, dict):
            measures = s.get("measures")
            if isinstance(measures, list):
                covered |= {m for m in measures if isinstance(m, str)}
    prim = [o for o in _objs(g, ep.get("objectives")) if o.get("priority") == "primary"]
    ok = bool(prim) and all(bool(set(o.get("measures") or []) & covered) for o in prim)
    ids = ([plan["id"]] if plan.get("id") else []) + _ids(prim)
    return ok, ids


def _addressed(g, ep):
    prim = [o for o in _objs(g, ep.get("objectives")) if o.get("priority") == "primary"]
    claims = _objs(g, ep.get("claims"))
    hit = {}
    for o in prim:
        oid = o.get("id")
        found = False
        for c in claims:
            addresses = c.get("addresses")
            addresses = addresses if isinstance(addresses, list) else []
            if oid in addresses and (is_content(c.get("supportedBy")) or c.get("derivedFrom")):
                found = True
                break
        hit[oid] = found
    return prim, hit


@pred("objectives_addressed")
def _oa(g, ep, ctx):
    prim, hit = _addressed(g, ep)
    return bool(prim) and all(hit.values()), _ids(prim)


@pred("objectives_some_addressed")
def _osa(g, ep, ctx):
    prim, hit = _addressed(g, ep)
    return any(hit.values()), _ids(prim)


@pred("model_evidence_reuse_past_purpose")
def _merpp(g, ep, ctx):
    """A ReusePastPurpose finding whose evidence is itself a modelling & simulation
    study — the F1 shape, where the reused artefact *is* a model's output rather than a
    document. EXE-3 asks about the models; reuse of a Document belongs to EXE-4, so this
    predicate deliberately looks only at `MSStudy` evidence."""
    evidence_ids: set[str] = set()
    claim_ids: set[str] = set()
    for f in ctx.scope:
        if f.rule != "ReusePastPurpose":
            continue
        hits = set()
        for oid in f.objects:
            if not isinstance(oid, str) or not g.has(oid):
                continue
            o = g.get(oid)
            if o.get("type") == "Evidence" and o.get("evidenceType") == "MSStudy":
                hits.add(oid)
        if not hits:
            continue
        evidence_ids |= hits
        claim_ids |= {oid for oid in f.objects
                      if isinstance(oid, str) and g.has(oid)
                      and g.get(oid).get("type") == "Claim"}
    return bool(evidence_ids), sorted(evidence_ids | claim_ids)


@pred("models_scope_ok")
def _mso(g, ep, ctx):
    """EXE-3's no-concerns bar, about *models*: models exist, none is used past its
    intended purpose, none needs reaccreditation, none is missing a VV&A record, and no
    reused M&S study underpins a claim. A `ReusePastPurpose` finding against a Document
    does not fail this — that is EXE-4's business (data scope), and attributing a
    document's reuse to a model question is a fidelity error in the §9.1 comparison."""
    models = _objs(g, ep.get("models"))
    reuse_ms, _ = PREDICATES["model_evidence_reuse_past_purpose"](g, ep, ctx)
    ok = (bool(models) and not _has_finding(ctx, "ModelUsePastPurpose")
          and not _has_finding(ctx, "ReaccreditationRequired")
          and not _has_finding(ctx, "model-vva")
          and not reuse_ms)
    return ok, _ids(models)


@pred("findings_present")
def _fp(g, ep, ctx):
    # The generic, YAML-parameterised hook — so it takes the same episode scoping as
    # every other findings-reading predicate. Both rules it is wired to today come from
    # `check_scope`, which is already episode-scoped; the first `validate()`-sourced rule
    # routed through here would otherwise leak another episode's problems into this one.
    rule = ctx.args.get("rule") if isinstance(ctx.args, dict) else None
    hits = [f for f in ctx.findings + ctx.scope
            if f.rule == rule and _counts_for_episode(ctx, f)]
    return bool(hits), sorted({o for f in hits for o in f.objects if isinstance(o, str)})


@pred("data_scope_all_known")
def _dsak(g, ep, ctx):
    evs = _cited_evidence(g, ep)
    ok, ids = _all(evs, lambda e: is_content(e.get("scopeOfValidity")), _ids(evs))
    return ok and not _has_finding(ctx, "ReusePastPurpose"), ids


@pred("data_scope_some_known")
def _dssk(g, ep, ctx):
    evs = _cited_evidence(g, ep)
    return _some(evs, lambda e: is_content(e.get("scopeOfValidity")), _ids(evs))


@pred("reliability_all")
def _ra(g, ep, ctx):
    evs = _cited_evidence(g, ep)
    return _all(evs, lambda e: is_content(e.get("reliabilitySteps")), _ids(evs))


@pred("reliability_some")
def _rs(g, ep, ctx):
    evs = _cited_evidence(g, ep)
    return _some(evs, lambda e: is_content(e.get("reliabilitySteps")), _ids(evs))


def _lims_ok(e):
    lims = e.get("limitations")
    lims = lims if isinstance(lims, list) else []
    return bool(lims) and all(isinstance(x, dict) and is_content(x.get("impact")) for x in lims)


@pred("limitations_all_explained")
def _lae(g, ep, ctx):
    evs = _cited_evidence(g, ep)
    return _all(evs, _lims_ok, _ids(evs))


@pred("limitations_some_explained")
def _lse(g, ep, ctx):
    evs = _cited_evidence(g, ep)
    return _some(evs, _lims_ok, _ids(evs))


def _ms_lims_ok(m):
    lims = m.get("limitations")
    lims = lims if isinstance(lims, list) else []
    return bool(lims) and all(isinstance(x, dict) and is_content(x.get("justification"))
                               for x in lims)


@pred("ms_limitations_all_justified")
def _mlaj(g, ep, ctx):
    ms = _objs(g, ep.get("models"))
    return _all(ms, _ms_lims_ok, _ids(ms))


@pred("ms_limitations_some")
def _mls(g, ep, ctx):
    ms = _objs(g, ep.get("models"))
    return _some(ms, lambda m: bool(m.get("limitations")), _ids(ms))


def _vva_sections(g, m):
    v = m.get("vvaRecord") if isinstance(m, dict) else None
    if not is_content(v) or not isinstance(v, str) or not g.has(v):
        return None
    secs = g.get(v).get("sections")
    return secs if isinstance(secs, list) else []


@pred("models_documented_all")
def _mda(g, ep, ctx):
    ms = _objs(g, ep.get("models"))
    ok = bool(ms)
    for m in ms:
        secs = _vva_sections(g, m)
        ok = ok and secs is not None and bool(secs) and all(
            isinstance(s, dict) and is_content(s.get("content")) for s in secs)
    return ok, _ids(ms)


@pred("models_documented_na_reasoned")
def _mdnr(g, ep, ctx):
    ms = _objs(g, ep.get("models"))
    ok = bool(ms)
    for m in ms:
        secs = _vva_sections(g, m)
        ok = ok and secs is not None and bool(secs) and all(
            isinstance(s, dict) and (is_content(s.get("content"))
                                      or is_exclusion_ref(s.get("content")))
            for s in secs)
    return ok, _ids(ms)


@pred("models_documented_some")
def _mds(g, ep, ctx):
    ms = _objs(g, ep.get("models"))

    def any_content(m):
        secs = _vva_sections(g, m)
        return bool(secs) and any(isinstance(s, dict) and is_content(s.get("content"))
                                   for s in secs)

    return any(any_content(m) for m in ms), _ids(ms)


@pred("observations_evidenced")
def _oe(g, ep, ctx):
    obs = _objs(g, ep.get("observations"))
    return _all(obs, lambda o: is_content(o.get("evidence")), _ids(obs))


@pred("observations_some_evidenced")
def _ose(g, ep, ctx):
    obs = _objs(g, ep.get("observations"))
    return _some(obs, lambda o: is_content(o.get("evidence")), _ids(obs))


def _baseline(g, ep):
    return [a for a in _objs(g, ep.get("alternatives")) if a.get("baselineFlag")]


@pred("baseline_present")
def _bp(g, ep, ctx):
    b = _baseline(g, ep)
    return bool(b), _ids(b)


@pred("baseline_identified_and_used")
def _biu(g, ep, ctx):
    b = _baseline(g, ep)
    runs = _objs(g, ep.get("runs"))
    if not b or not runs:
        return False, _ids(b)
    base_id = b[0].get("id")

    def ranked(r):
        ranking = r.get("ranking")
        return isinstance(ranking, list) and base_id in ranking

    ok = all(ranked(r) for r in runs)
    return ok, _ids(b) + _ids(runs)


@pred("baseline_data_verified")
def _bdv(g, ep, ctx):
    b = _baseline(g, ep)
    if not b:
        return False, []
    base_id = b[0].get("id")
    obs = [o for o in _objs(g, ep.get("observations")) if o.get("alternative") == base_id]

    def ok_one(o):
        ev_id = o.get("evidence")
        if not (isinstance(ev_id, str) and g.has(ev_id)):
            return False
        return is_content(g.get(ev_id).get("reliabilitySteps"))

    ok = bool(obs) and all(ok_one(o) for o in obs)
    return ok, _ids(obs)


@pred("vv_documented")
def _vvd(g, ep, ctx):
    steps: list[dict] = []
    for e in _cited_evidence(g, ep):
        rs = e.get("reliabilitySteps")
        if isinstance(rs, list):
            steps += _objs(g, rs)
    return _all(steps, lambda s: is_content(s.get("documentation")), _ids(steps))


def _acc(g, m):
    v = m.get("vvaRecord") if isinstance(m, dict) else None
    if not is_content(v) or not isinstance(v, str) or not g.has(v):
        return None
    acc = g.get(v).get("accreditationDecision")
    return acc if is_content(acc) and isinstance(acc, dict) else None


def _vva_signed_one(g, m):
    a = _acc(g, m)
    return (a is not None and a.get("basis") == "document" and a.get("document")
            and a.get("authority") and a.get("date"))


@pred("vva_signed")
def _vs(g, ep, ctx):
    ms = _objs(g, ep.get("models"))
    return _all(ms, lambda m: _vva_signed_one(g, m), _ids(ms))


@pred("vva_asserted_undocumented")
def _vau(g, ep, ctx):
    """A model whose accreditation was asserted at all (an accreditationDecision
    exists) but does not meet `vva_signed`'s strict bar — basis interview/verbal, or
    basis `document` with no `document` evidence ref — is "asserted, undocumented",
    not "no information": EXE-14 state 3, not 4."""
    ms = _objs(g, ep.get("models"))

    def asserted_undocumented(m):
        return _acc(g, m) is not None and not _vva_signed_one(g, m)

    return _some(ms, asserted_undocumented, _ids(ms))


@pred("measures_exist")
def _me(g, ep, ctx):
    ms: list[str] = []
    for o in _objs(g, ep.get("objectives")):
        measures = o.get("measures")
        if isinstance(measures, list):
            ms += [m for m in measures if isinstance(m, str)]
    return bool(ms), _existing_ids(g, ms)


@pred("measures_have_criteria")
def _mhc(g, ep, ctx):
    ids: list[str] = []
    for o in _objs(g, ep.get("objectives")):
        measures = o.get("measures")
        if isinstance(measures, list):
            ids += [m for m in measures if isinstance(m, str)]
    ms = _objs(g, ids)
    return _all(ms, lambda m: is_content(m.get("criteria")), ids)


# ---- presentation -------------------------------------------------------------
@pred("runs_exist")
def _re(g, ep, ctx):
    ids = ep.get("runs")
    ids = ids if isinstance(ids, list) else []
    return bool(ids), _existing_ids(g, ids)


@pred("results_support_claims")
def _rsc(g, ep, ctx):
    run_ids = ep.get("runs")
    run_ids = run_ids if isinstance(run_ids, list) else []
    claims = [c for c in _objs(g, ep.get("claims")) if c.get("derivedFrom")]

    def ok_one(c):
        df = c.get("derivedFrom")
        if df not in run_ids or not g.has(df):
            return False
        run = g.get(df)
        result_ref = c.get("resultRef")
        outputs = run.get("outputs")
        outputs = outputs if isinstance(outputs, list) else []
        return not result_ref or result_ref in outputs

    ok = bool(claims) and all(ok_one(c) for c in claims)
    return ok, _ids(claims)


@pred("conclusions_sound")
def _cs(g, ep, ctx):
    blocking = [f for f in ctx.findings + ctx.scope
                if f.severity == "blocking" and _counts_for_episode(ctx, f)]
    ok, ids = PREDICATES["results_support_claims"](g, ep, ctx)
    return (ok and not blocking,
            ids + sorted({o for f in blocking for o in f.objects if isinstance(o, str)}))


@pred("results_clear")
def _rc(g, ep, ctx):
    """PRE-4's no-concerns bar: results the record actually presents, in units, traced
    back to a raw observation, and carried into at least one Claim.

    Every Result the kernel writes hardcodes its `units`, so a predicate that tested only
    that could never fail while the kernel is the author — a rating that cannot fail
    carries no information. The parts a *record* can get wrong are the ones that count:
    a per-measure Result that lost its raw value or the unit it was measured in, and a
    run whose numbers no Claim ever states. Presenting results is a claim about them.
    """
    run_ids = _existing_ids(g, ep.get("runs"))
    if not run_ids:
        return False, []
    runs = [g.get(i) for i in run_ids]

    res_ids: list[str] = []
    for r in runs:
        outputs = r.get("outputs")
        if isinstance(outputs, list):
            res_ids += [i for i in outputs if isinstance(i, str)]
    resolved = [g.get(i) for i in res_ids if g.has(i)]
    results_ok = bool(res_ids) and len(resolved) == len(res_ids) and all(
        is_content(r.get("units"))
        and (r.get("aggregate") is True
             or (is_content(r.get("raw")) and is_content(r.get("rawUnits"))))
        for r in resolved
    )

    qualifying = []
    for c in _objs(g, ep.get("claims")):
        df = c.get("derivedFrom")
        if not (isinstance(df, str) and df in run_ids):
            continue
        outputs = g.get(df).get("outputs")
        outputs = outputs if isinstance(outputs, list) else []
        if isinstance(c.get("resultRef"), str) and c["resultRef"] in outputs:
            qualifying.append(c)

    return results_ok and bool(qualifying), _ids(qualifying) + run_ids


@pred("commitment_exists")
def _ce(g, ep, ctx):
    cid = ep.get("commitment")
    ok = isinstance(cid, str) and g.has(cid)
    return ok, [cid] if ok else []


@pred("recommendation_supported")
def _rsup(g, ep, ctx):
    cid = ep.get("commitment")
    run_ids = ep.get("runs")
    run_ids = run_ids if isinstance(run_ids, list) else []
    if not (isinstance(cid, str) and g.has(cid) and run_ids):
        return False, []
    com = g.get(cid)
    last_id = run_ids[-1]
    if not (isinstance(last_id, str) and g.has(last_id)):
        return False, [com["id"]] if com.get("id") else []
    last = g.get(last_id)
    selected = com.get("selected")
    alt = g.get(selected) if isinstance(selected, str) and g.has(selected) else None
    ranking = last.get("ranking")
    ranking = ranking if isinstance(ranking, list) else []
    top_matches = bool(ranking) and ranking[0] == selected
    reasoned = False
    if alt is not None:
        sr = alt.get("statusReason")
        reasoned = isinstance(sr, str) and g.has(sr) and g.get(sr).get("type") == "Rationale"
    ok = top_matches or reasoned
    return ok, [i for i in (com.get("id"), last.get("id")) if i]


@pred("alternatives_exist")
def _ae(g, ep, ctx):
    ids = ep.get("alternatives")
    ids = ids if isinstance(ids, list) else []
    return bool(ids), _existing_ids(g, ids)


@pred("options_range")
def _or(g, ep, ctx):
    alts = [a for a in _objs(g, ep.get("alternatives"))
            if a.get("status") in ("evaluated", "selected", "rejected")]
    ok = len(alts) >= 3 and any(a.get("baselineFlag") for a in alts)
    return ok, _ids(alts)


@pred("stakeholders_informed")
def _si(g, ep, ctx):
    ok = bool(ep.get("distribution"))
    eid = ep.get("id")
    return ok, [eid] if ok and isinstance(eid, str) else []


# ---- presentation: claim/evidence chain (design §7.5, moved here from plan 05) ----
@pred("claims_exist")
def _claims_exist(g, ep, ctx):
    claims = _objs(g, ep.get("claims"))
    return bool(claims), _ids(claims)


@pred("claims_exist_no_silence")
def _claims_exist_no_silence(g, ep, ctx):
    ok, ids = PREDICATES["claims_exist"](g, ep, ctx)
    return ok and not _has_finding(ctx, "silence"), ids


@pred("claims_exist_no_silence_no_blocking_gaps")
def _claims_exist_no_silence_no_blocking_gaps(g, ep, ctx):
    ok, ids = PREDICATES["claims_exist_no_silence"](g, ep, ctx)
    if not ok:
        return False, ids
    # `ctx.reach` already holds exactly this set, computed once per scoring pass.
    gap_ids = sorted(
        i for i in ctx.reach
        if g.has(i) and g.get(i).get("type") == "InsufficientEvidence"
        and g.get(i).get("impact") == "blocking"
    )
    return not gap_ids, ids + gap_ids


@pred("claims_all_supported")
def _claims_all_supported(g, ep, ctx):
    claims = _objs(g, ep.get("claims"))
    if not claims:
        return False, []
    ok_sb = all(is_content(c.get("supportedBy")) for c in claims)
    evs = _claims_evidence(g, ep)
    ok_ev = bool(evs) and all(is_content(e.get("reliabilitySteps")) for e in evs)
    return ok_sb and ok_ev, _ids(claims) + _ids(evs)


# ---- scoring ------------------------------------------------------------------
def score_question(g: Graph, ep: dict, ctx: Context, qid: str, rules_by_q: dict) -> dict:
    rule = rules_by_q[qid]
    for clause in rule["clauses"]:
        ctx.args = clause.get("args") or {}
        ok, ids = PREDICATES[clause["when"]](g, ep, ctx)
        if ok:
            # Belt and suspenders: every predicate is expected to justify only with ids
            # that resolve, but the StandardsAssessment schema types `justification` as
            # `ref: any`, so `rule_ref_integrity` would flag a dangling one on the
            # assessment itself. Filtering here, once, means no individual predicate's
            # oversight can leak a dangling ref into a persisted object.
            justification = sorted({i for i in ids if isinstance(i, str) and g.has(i)})
            return {"questionId": qid, "applicable": True, "state": int(clause["state"]),
                    "justification": justification,
                    "rule": f"{clause['when']}→{clause['state']}"}
    raise AssertionError(f"no clause matched for {qid}")


# ---- qualifier reasons ------------------------------------------------------------
# `dimension_verdicts`'s qualifier names, per state-2 question, *why* the record earned
# state 2 — the reason the fired rule (a rating's `rule`, e.g. `"claims_exist→2"`) gives
# for its predicate. Keyed by predicate name, not by question: the same predicate means
# the same thing wherever in rules.yaml it fires, so one phrase per predicate is enough
# to cover every question it appears on. Every predicate named at a `state: 2` clause in
# rules.yaml must have an entry here — `test_every_state_two_predicate_has_a_reason`
# in tests/kernel/test_standards.py derives that set from the YAML itself
# and fails if this mapping falls short, so `_DEFAULT_STATE2_REASON` stays a fail-safe
# for a predicate rules.yaml does not yet name, never the load-bearing case for one it
# does.
STATE2_REASONS: dict[str, str] = {
    "charter_complete": "the charter is complete but the plan is not shown as approved",
    "charter_question_stated": "the question is stated but not every term is defined",
    "scope_defined": "the scope is defined but not every term is defined",
    "assumptions_listed": "assumptions are listed without rationale",
    "assumptions_some_evidenced": "only some assumptions are evidenced",
    "some_linchpins_have_flip": "not every linchpin assumption was varied",
    "any_assumption_varied": "sensitivity covered some assumptions",
    "constraints_listed": "constraints are listed without their implications discussed",
    "scenarios_listed": ("scenarios are listed without a stated rationale or full "
                          "coverage of the conditions of interest"),
    "mandate_elements_some": "only some mandate elements are satisfied",
    "limitations_some": "limitations are noted but not all have a stated mitigation",
    "plan_exists": "a plan exists but does not demonstrably cover the primary objectives",
    "objectives_some_addressed": ("only some primary objectives are addressed by a "
                                   "supported claim"),
    "findings_present": ("a specific finding raised a concern here that the record has "
                          "not resolved"),
    "data_scope_some_known": "only some cited evidence states its scope of validity",
    "reliability_some": "only some cited evidence describes its reliability steps",
    "limitations_some_explained": ("only some cited evidence explains the impact of its "
                                    "limitations"),
    "ms_limitations_some": "only some models explain their limitations",
    "models_documented_na_reasoned": ("model documentation relies on reasoned "
                                       "not-applicable sections rather than full content"),
    "observations_some_evidenced": "only some observations cite evidence",
    "baseline_present": "a baseline alternative exists but is not shown ranked in every run",
    "measures_exist": "measures exist but do not all state acceptance criteria",
    "runs_exist": "runs exist but the record does not yet show them supporting the claims",
    "claims_all_supported": "claims are backed by evidence but not tied to a run's sealed results",
    "claims_exist_no_silence": "claims are presented but no evaluation run exists in the record",
    "results_support_claims": ("results support the claims, but a blocking finding remains "
                                "unresolved elsewhere in the record"),
    "claims_exist": "claims are presented but no evaluation run exists in the record",
    "alternatives_exist": ("alternatives exist but do not include at least three evaluated "
                            "options with a baseline"),
}
_DEFAULT_STATE2_REASON = "the record does not thoroughly describe this item"


def _state2_reason(rule: object) -> str:
    """The reason phrase for a state-2 rating's fired rule (`"<predicate>→2"`), or the
    default when `rule` is not a recognised, well-formed rule string — a hand-built
    rating list (`dimension_verdicts` is called directly by tests with those) may carry
    no `rule` at all."""
    name = rule.split("→", 1)[0] if isinstance(rule, str) else None
    return STATE2_REASONS.get(name, _DEFAULT_STATE2_REASON)


def dimension_verdicts(ratings: list[dict], k: int = 1) -> dict:
    dm = load_standard()["dimension_mapping"]
    by_q = {r["questionId"]: r for r in ratings if r.get("applicable")}
    out = {}
    for dim in ("objectivity", "validity", "reliability"):
        mapped = [by_q[q] for q in dm[dim]["question_ids"] if q in by_q]
        # An applicable rating whose state is missing, None or not an integer is not
        # "no concerns" — it is exactly the "insufficient information" case, so it reads
        # as state 4. `dimension_verdicts` is called directly by 03a's and 03b's tests
        # with hand-built rating lists, so it cannot rely on score_standards' shape.
        states = [s if isinstance(s := r.get("state"), int) and not isinstance(s, bool) else 4
                  for r in mapped]
        label = {"objectivity": "objective", "validity": "valid",
                 "reliability": "reliable"}[dim]
        if not mapped:
            # No applicable question maps to this dimension at all — a tailoring that
            # excludes every one of them, say. That is exactly the "cannot conclude"
            # case, never a vacuous "generally X": there is nothing to conclude from.
            verdict = "insufficient_to_conclude"
        elif any(s == 4 for s in states):
            verdict = "insufficient_to_conclude"
        elif any(s == 3 for s in states) or sum(1 for s in states if s == 2) > k:
            verdict = f"not_{label}"
        else:
            verdict = f"generally_{label}"
        twos = [(r["questionId"], r.get("rule"))
                for r, s in zip(mapped, states, strict=True) if s == 2]
        qual = None
        if verdict.startswith("generally") and twos:
            concerns = "; ".join(f"{q} ({_state2_reason(rule)})" for q, rule in twos)
            qual = f"{verdict.replace('_', ' ')}, with concerns: {concerns}"
        out[dim] = {"verdict": verdict, "qualifier": qual,
                    "mapped": [r["questionId"] for r in mapped], "states": states}
    return out


def score_standards(g: Graph, episode_id: str, tailoring_name: str, *, k: int, now: str) -> dict:
    ep = g.get(episode_id)
    ctx = build_context(g, episode_id)
    tailoring = load_tailoring(tailoring_name)
    rules_by_q = {r["question"]: r for r in load_rules()}
    ratings = []
    for qid, t in tailoring["questions"].items():
        if t["applicable"]:
            ratings.append(score_question(g, ep, ctx, qid, rules_by_q))
        else:
            ratings.append({"questionId": qid, "applicable": False,
                             "tailoringReason": t["tailoringReason"], "state": None,
                             "justification": [], "rule": "tailored-out"})
    n = 1 + sum(1 for o in g.all("StandardsAssessment") if o.get("episode") == episode_id)
    sa = {"id": f"sa-{episode_id}-{tailoring_name}-{n}", "type": "StandardsAssessment", "rev": 1,
          "createdBy": KERNEL_ACTOR, "createdAt": now, "episode": episode_id,
          "tailoring": tailoring_name, "ratings": ratings,
          "dimensionVerdicts": dimension_verdicts(ratings, k),
          "aggregationRule": ("generally X if no mapped question is state 3 and at most "
                              f"k={k} are state 2; insufficient if any state 4; else not X "
                              "(GAO-11-82R; GAO-23-106549 pp. 7-8)"),
          "k": k, "kernelVersion": KERNEL_VERSION}
    g.put(sa, KERNEL_ACTOR)
    return sa
