"""ReadinessReport assembly (design §6.1 ReadinessReport; §7.1 semantic readiness;
§7.3 step 4 ordering; §10 section 11).

This is the artefact the signer reads and the artefact G3 reads: one boolean, `ready`,
and every reason behind it named by object id. Three properties hold it up.

**`ready` is exactly `not blockers`.** There is no separate judgment anywhere: the
verdict is a restatement of the list, so a reader who disagrees with the verdict can
only disagree with a numbered, id-carrying line in the list.

**Nothing is dropped.** Every Finding the validator, the scope checker and the readiness
checks below produce is written into the report — blocking ones into `blockers`,
everything else (warning *and* info) into `warnings`, each entry carrying its own
`severity`. An `info` finding like `reuse-justified` is a positive fact about the record
and the package prints it; silently discarding it would make the report's silence
ambiguous between "did not happen" and "not reported".

**A rule the policy names blocks.** `Policy.blockingRules` promotes a finding to a
blocker whatever its own severity, and the promoted entry is tagged `promotedBy` so the
report says why a warning is holding the record shut.

The three design §7.1 conditions that 03a's policy predicates do not cover are
implemented here as readiness checks — `objective-run-coverage`, `accreditation-scope`
and `bias-check-evidence-unreviewed`. What each does and does not test is written on the
check itself; `accreditation-scope` in particular tests the half of "scope covers the
Charter question" that can be tested deterministically and says so.

Purity: `seed` and `now` are arguments. Every write is `KERNEL_ACTOR`. Tolerance: the
graph may be hand-edited, so every field is read with `.get()`/`isinstance` and every
reference is resolved before it is followed — a dangling id is somebody else's finding
(`ref-integrity`), never this module's traceback.
"""

from __future__ import annotations

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.errors import ValidationError
from docket.kernel.bias import bias_indicators
from docket.kernel.findings import Finding
from docket.kernel.flip import flip_summary
from docket.kernel.mandate import score_mandate
from docket.kernel.scope import check_scope
from docket.kernel.standards import score_standards
from docket.kernel.validate import KNOWN_RULES, WHOLE_STORE_RULES, validate
from docket.objects import is_content, is_gap_ref
from docket.schema import validate_object
from docket.standard import load_tailoring
from docket.store import Graph

# design §7.5: "k a policy parameter, default 1". Used only when neither the caller nor
# a resolvable Policy names one.
DEFAULT_K = 1

# A gap no linchpin assumption points at sorts after every gap one does (design §7.3
# step 4: linchpins with a short flip distance are surfaced first).
NO_LINCHPIN = 2.0
# A linchpin whose gap has no flip analysis at all: unmeasured, so it cannot be ranked
# among the measured ones — it sorts after them but ahead of the unreferenced gaps.
UNMEASURED = 1.0


def _obj(g: Graph, ref: object) -> dict | None:
    """The object `ref` names, or None — for any shape of `ref` at all."""
    if not isinstance(ref, str) or not g.has(ref):
        return None
    o = g.get(ref)
    return o if isinstance(o, dict) else None


def _resolved(g: Graph, ids: object) -> list[dict]:
    """The objects a reference list actually resolves to, order preserved."""
    if not isinstance(ids, list):
        return []
    return [o for o in (_obj(g, i) for i in ids) if o is not None]


def _oid(o: dict) -> str:
    """An object's id as a string. Every stored object has one — `Graph.put` and
    `Graph.load` both refuse anything else — but the annotation matters: `Finding.objects`
    is a tuple of ids the renderer joins into a line of text."""
    oid = o.get("id")
    return oid if isinstance(oid, str) else "<unknown>"


# ---- design §7.1 readiness checks ----------------------------------------------------


def _covered_measures(g: Graph, ep: dict) -> set[str]:
    """Every Measure some sealed EvaluationRun on this episode actually scored.

    Read from the runs' sealed Results — what was computed — and not from the plan steps,
    which say only what was asked for. A step revised after sealing would otherwise make
    a run look like it covered a measure it never scored; the Results are inside the
    seal, and `run-seal` re-derives their hashes on every validation.
    """
    covered: set[str] = set()
    for run in _resolved(g, ep.get("runs")):
        for result in _resolved(g, run.get("outputs")):
            if isinstance(result.get("measure"), str):
                covered.add(result["measure"])
    return covered


def check_objective_coverage(g: Graph, ep: dict) -> list[Finding]:
    """Design §7.1: every primary Objective has ≥1 EvaluationRun covering it.

    "Covering" is read as *at least one* of the objective's Measures scored by at least
    one run — the weaker reading on purpose, because a plan may legitimately split one
    objective's measures across steps (Demo A does exactly that). An objective with no
    Measure at all is `objective-measured`'s finding, not this one's, and is skipped
    here so the same defect is not reported twice.

    Reading coverage from the sealed Results assumes an evaluator that emits a Result per
    (alternative, measure), which MAVT — the only method kernel 0.1.0 implements — does.
    A future method that sealed only an aggregate Result per alternative would leave the
    covered set empty and fire this check on every primary objective; whoever adds one
    should widen `_covered_measures` in the same change.
    """
    covered = _covered_measures(g, ep)
    out = []
    for o in _resolved(g, ep.get("objectives")):
        if o.get("priority") != "primary":
            continue
        listed = o.get("measures")
        measures = {m for m in listed if isinstance(m, str)} if isinstance(listed, list) else set()
        if not measures or (measures & covered):
            continue
        out.append(Finding(
            "objective-run-coverage", "blocking", (_oid(o),),
            "no evaluation run on this episode scored any measure of this primary "
            "objective, so the record does not answer it (design §7.1)",
        ))
    return out


def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _programmes(g: Graph, ep: dict) -> list[dict]:
    """Every DecisionProgram this episode belongs to, by either link.

    `DecisionEpisode.program` and `DecisionProgram.episodes` are both in the schema and
    a record may carry only one of them (`open_refresh` appends to the programme's list),
    so the lineage is read from both rather than from whichever one this fixture chose.
    """
    found: dict[str, dict] = {}
    named = _obj(g, ep.get("program"))
    if named is not None and named.get("type") == "DecisionProgram":
        found[_oid(named)] = named
    ep_id = _oid(ep)
    for prog in g.all("DecisionProgram"):
        episodes = prog.get("episodes")
        if isinstance(episodes, list) and ep_id in episodes:
            found[_oid(prog)] = prog
    return [found[k] for k in sorted(found)]


def accreditation_lineage(g: Graph, ep: dict) -> set[str]:
    """The Charters an accreditation for this episode may name as its problem statement:
    this episode's own, the Charter of any earlier episode (lower `sequence`) of a
    programme this episode belongs to, and that programme's own Charter.

    Lineage, not wording. A model accredited for episode 1 of a programme is accredited
    for episode 2 — that is what a refresh *is*, and whether the accreditation has gone
    stale is the elapsed-time rule's business (`ReaccreditationRequired`, AR 5-11
    ¶4-2i(3)), not this one's. A Charter nobody in the programme adopted does not become
    this decision's problem statement by asking a similar question, and an episode that
    had not been decided yet cannot justify an accreditation, so `sequence` must be
    strictly lower and an unreadable `sequence` at either end fails closed.
    """
    accepted: set[str] = set()
    if isinstance(ep.get("charter"), str):
        accepted.add(ep["charter"])
    sequence = ep.get("sequence")
    for prog in _programmes(g, ep):
        if isinstance(prog.get("charter"), str):
            accepted.add(prog["charter"])
        for other in _resolved(g, prog.get("episodes")):
            if other.get("type") != "DecisionEpisode":
                continue
            other_seq = other.get("sequence")
            if (_is_int(other_seq) and _is_int(sequence) and other_seq < sequence
                    and isinstance(other.get("charter"), str)):
                accepted.add(other["charter"])
    return accepted


def check_accreditation_scope(g: Graph, ep: dict) -> list[Finding]:
    """Design §7.1: every Model has a VVARecord with an accreditation decision whose
    scope covers the Charter question.

    Two things are tested, and they are the two that can be tested deterministically:
    the accreditation must actually **state** a scope, and the VV&A must have been
    accredited against a problem statement in this decision's lineage (see
    `accreditation_lineage`).

    Free-text containment of the charter question inside the scope sentence is *not*
    tested, and neither is the question text anywhere else in this check. No
    deterministic string match could do it without manufacturing findings on honest
    records, and inventing one would put a judgment the kernel cannot defend into a
    report whose whole value is that every line is checkable. The controlled-vocabulary
    half of that comparison is already reported: `check_scope`'s `ModelUsePastPurpose`
    fires when a Model's `questionClass` differs from the Charter's.

    A Model with no VVARecord, a VV&A with no accreditation decision at all, and a
    `problemStatement` that names nothing in the graph are all somebody else's findings
    (`model-vva`, `ref-integrity`) and are skipped here.
    """
    accepted = accreditation_lineage(g, ep)
    out = []
    for m in _resolved(g, ep.get("models")):
        vva = _obj(g, m.get("vvaRecord"))
        if vva is None:
            continue
        acc = vva.get("accreditationDecision")
        if not is_content(acc) or not isinstance(acc, dict):
            continue
        if not is_content(acc.get("scope")):
            out.append(Finding(
                "accreditation-scope", "blocking", (_oid(m), _oid(vva)),
                "the accreditation decision states no scope, so it cannot be shown to "
                "cover the charter question (AR 5-11 ¶4-2i; MIL-STD-3022 Table I)",
            ))
        problem = vva.get("problemStatement")
        if (isinstance(problem, str) and problem not in accepted
                and _obj(g, problem) is not None):
            out.append(Finding(
                "accreditation-scope", "blocking", (_oid(m), _oid(vva), problem),
                f"the VV&A was accredited against {problem}, which is neither this "
                "episode's charter nor the charter of its programme or of an earlier "
                "episode of it (AR 5-11 ¶4-2i)",
            ))
    return out


def check_policy_resolves(g: Graph, charter: dict | None) -> list[Finding]:
    """The Charter's `decisionClassPolicy` names an object that is actually a Policy.

    The schema types the field `ref: Policy`, but ref-integrity only asks whether the id
    resolves — nothing checks what it resolves *to*. Pointed at anything else, every
    policy-dependent rule (`requiredBiasChecks`, `prohibitedExclusionReasons`,
    `blockingRules`, the tailoring, `k`) reads a missing field and no-ops in silence,
    which is the one failure mode a readiness report may not have.
    """
    if charter is None:
        return []
    ref = charter.get("decisionClassPolicy")
    target = _obj(g, ref)
    if target is None or target.get("type") == "Policy":
        return []
    return [Finding(
        "policy-unresolved", "blocking", (_oid(charter), _oid(target)),
        f"decisionClassPolicy names {_oid(target)}, which is a {target.get('type')!r}, "
        "not a Policy: no policy rule can be applied to this episode",
    )]


def check_blocking_rules_known(policy: dict | None) -> list[Finding]:
    """Every name in `Policy.blockingRules` is a rule some kernel rule actually emits.

    Nothing else in the codebase reads this list, so an unrecognised name simply never
    matches a finding: a one-character typo switches off a blocker the policy author
    asked for and the report prints a clean section. That is exactly the silence P3
    forbids everywhere else, so an unknown name is itself a blocker.
    """
    if policy is None:
        return []
    listed = policy.get("blockingRules")
    if not isinstance(listed, list):
        return []
    return [
        Finding(
            "blocking-rule-unknown", "blocking", (_oid(policy),),
            f"policy blockingRules names {name!r}, which no kernel rule emits; the "
            "promotion it asks for would never fire (see validate.KNOWN_RULES)",
        )
        for name in listed if not (isinstance(name, str) and name in KNOWN_RULES)
    ]


def check_bias_check_evidence(g: Graph, ep: dict, policy: dict) -> list[Finding]:
    """Design §7.1: required BiasChecks present **with reviewed Evidence**.

    `bias_checks_required` (03a) already blocks a required check that was never
    performed and warns when its evidence is a recorded gap. What it does not test is
    the review status of the evidence a performed check produced, which is the half that
    makes the check auditable: a premortem memo nobody read is not a performed check.

    A check `waived` under a recorded Exclusion is not covered by this rule — a waiver is
    a recorded decision not to run the check, and it produces no evidence to review. One
    reviewed evidence item satisfies the requirement; the finding names every performed
    check of that type when none of them has one.
    """
    out = []
    checks = _resolved(g, ep.get("biasChecks"))
    for check_type in policy.get("requiredBiasChecks") or []:
        if not isinstance(check_type, str):
            continue
        pairs = []
        for c in checks:
            if c.get("checkType") != check_type or c.get("status") != "performed":
                continue
            ev = _obj(g, c.get("producedEvidence")) if is_content(c.get("producedEvidence")) \
                else None
            if ev is not None:
                pairs.append((c, ev))
        if not pairs or any(ev.get("reviewStatus") == "reviewed" for _, ev in pairs):
            continue
        for c, ev in pairs:
            out.append(Finding(
                "bias-check-evidence-unreviewed", "blocking", (_oid(c), _oid(ev)),
                f"required bias check {check_type} produced evidence no reviewer has "
                f"reviewed (reviewStatus {ev.get('reviewStatus')!r}; design §7.1)",
            ))
    return out


# ---- assembly ------------------------------------------------------------------------


def _flip_summary(g: Graph, ep: dict, *, seed: int, now: str) -> tuple[dict, list[Finding]]:
    """The weight-simplex/flip summary for the episode's last run, or a blocker saying
    why there isn't one.

    `flip_analysis`/`flip_summary` refuse a run whose bound inputs have moved since it
    was sealed (`inputsHash` mismatch) — the numbers would describe a run the graph can
    no longer reproduce. That refusal is a readiness fact, not a crash: the record is not
    ready, and the reason is that the run is stale. It blocks whether or not the policy
    lists `run-inputs-changed` in `blockingRules`: the promotion list decides which
    *warnings* hold the record shut, while this is the report failing to produce a number
    it is supposed to print, which no policy can wave through.

    A multi-step plan seals one run per step and only the last is summarised, so the ones
    that were not are named in `runsNotSummarised` — a reader can see that a set of flip
    analyses was left out, instead of having to infer it from the run count. A last run id
    that names nothing is *not* quietly replaced by the previous run: the summary would
    then be presented under a run the episode did not end with.
    """
    runs = [r for r in (ep.get("runs") or []) if isinstance(r, str)]
    if not runs:
        return {}, []
    run_id, others = runs[-1], runs[:-1]
    if _obj(g, run_id) is None:
        return {}, [Finding(
            "flip-summary-unavailable", "blocking", (run_id,),
            "the episode's last run is not in the graph, so no sensitivity summary was "
            "produced (the dangling reference is also a ref-integrity finding)",
        )]
    try:
        return {**flip_summary(g, run_id, seed=seed, now=now),
                "runsNotSummarised": others}, []
    except ValidationError as exc:
        return {}, [Finding(
            "run-stale", "blocking", (run_id,),
            f"run stale; re-evaluate — the sensitivity summary refuses this run: {exc}",
        )]
    except (KeyError, IndexError, StopIteration, TypeError, ValueError, ZeroDivisionError) \
            as exc:
        return {}, [Finding(
            "flip-summary-unavailable", "blocking", (run_id,),
            "the sensitivity summary could not be computed for this run: "
            f"{type(exc).__name__}: {exc}",
        )]


def _gap_priority(g: Graph, ep: dict) -> dict[str, float]:
    """For each gap a linchpin Assumption stands on, the shortest flip distance among
    the flip analyses of that assumption (design §7.3 step 4: linchpin assumptions with
    a short flip distance *and* an InsufficientEvidence are surfaced first)."""
    flips = _resolved(g, ep.get("flipAnalyses"))
    out: dict[str, float] = {}
    for a in _resolved(g, ep.get("assumptions")):
        if not a.get("linchpin") or not is_gap_ref(a.get("evidence")):
            continue
        gap_id = a["evidence"]["$gap"]
        distances = [f["flipDistance"] for f in flips
                     if f.get("assumption") == _oid(a)
                     and isinstance(f.get("flipDistance"), int | float)
                     and not isinstance(f.get("flipDistance"), bool)]
        d = min(distances) if distances else UNMEASURED
        out[gap_id] = min(out.get(gap_id, d), d)
    return out


def _reachable_of_type(g: Graph, reach: set[str], type_name: str) -> list[str]:
    """Every id in `reach` naming an object of `type_name`, sorted.

    `reachable_from` walks references, and a reference may dangle, so the ids it returns
    are not all resolvable — resolve before reading the type.
    """
    out = []
    for i in sorted(reach):
        o = _obj(g, i)
        if o is not None and o.get("type") == type_name:
            out.append(i)
    return out


def _counts_for_episode(f: Finding, reach: set[str]) -> bool:
    """Whether Finding `f` bears on this episode. Store-integrity findings always do —
    a tampered log or a forged authorship line invalidates every reading of the store,
    this episode's included — as do findings naming no object at all."""
    return f.rule in WHOLE_STORE_RULES or not f.objects or bool(set(f.objects) & reach)


def readiness_report(
    g: Graph, episode_id: str, *, tailoring: str | None = None, k: int | None = None,
    seed: int, now: str,
) -> dict:
    """Assemble the episode's ReadinessReport and record it on the episode.

    Runs, in order: the computed bias indicators (first, because they write Risks and
    everything downstream reads the graph they leave behind), the flip summary for the
    episode's last run, the validator under the episode's Policy, the scope checker, the
    three §7.1 readiness checks above, the standards scorer and the mandate scorecard.

    `tailoring` and `k` default to the Policy's. An episode whose Policy cannot be
    resolved is still reported on — the dangling reference, or the `policy-unresolved`
    check, is itself a blocking finding, so the report says "not ready" and names the
    object — but a standard has to be chosen to score against, so with no Policy and no
    `tailoring` argument the call refuses rather than picking one.

    Validate, then write: everything that can refuse this call is settled here, before
    the first write. A hand-edited episode that no longer satisfies its own schema cannot
    carry a `readiness` link, and a tailoring name that names no file cannot be scored
    against, so both refuse before `bias_indicators` has written a Risk — otherwise the
    graph is left carrying half a readiness run and no report.
    """
    ep = _obj(g, episode_id)
    if ep is None or ep.get("type") != "DecisionEpisode":
        raise ValidationError([f"episode {episode_id!r} is not a DecisionEpisode in the graph"])
    charter = _obj(g, ep.get("charter"))
    policy = _obj(g, charter.get("decisionClassPolicy")) if charter is not None else None
    # A reference that resolves to something other than a Policy is reported by
    # `check_policy_resolves` and is not usable as one: no tailoring, no `k`, no version,
    # no promotion list. It must not silence the policy rules that read no policy field
    # either, though — a record with no baseline is still a record with no baseline.
    # `policy_rules._episodes` treats a policy with no `id` (an empty `{}`, same as
    # `None`) as "no real Policy to read a field from, run the structure-only rules over
    # every episode" — so the stand-in passed here is simply `{}`, not a fragment
    # carrying the broken reference's id: every structure-only rule reports as usual,
    # and the field-reading ones (required bias checks, prohibited exclusion reasons)
    # find nothing on `{}` to apply and say nothing, which is what `policy-unresolved`
    # is in the report to explain.
    rules_policy: dict | None = policy
    if policy is not None and policy.get("type") != "Policy":
        rules_policy = {}
        policy = None

    tailoring = tailoring if tailoring is not None else (policy or {}).get("tailoring")
    if not isinstance(tailoring, str):
        raise ValidationError([
            f"{episode_id}: no tailoring — the episode's policy does not name one and "
            "none was given, so there is no standard to score the record against"
        ])
    try:
        load_tailoring(tailoring)
    except (OSError, ValueError, KeyError) as exc:
        # An OSError's text is a local absolute path, which says nothing to the reader of
        # a refusal and leaks the machine it ran on; name the tailoring instead.
        detail = ("no tailoring of that name is installed" if isinstance(exc, OSError)
                  else f"{type(exc).__name__}: {exc}")
        raise ValidationError(
            [f"{episode_id}: tailoring {tailoring!r} cannot be loaded — {detail}"]
        ) from exc
    if k is None:
        policy_k = (policy or {}).get("aggregationK")
        k = policy_k if isinstance(policy_k, int) and not isinstance(policy_k, bool) \
            else DEFAULT_K

    n = 1 + sum(1 for o in g.all("ReadinessReport") if o.get("episode") == episode_id)
    report_id = f"rr-{episode_id}-{n}"
    errs = validate_object({**ep, "readiness": report_id})
    if errs:
        raise ValidationError(
            [f"{episode_id}: cannot record readiness on an episode that does not "
             "validate: " + "; ".join(errs)]
        )

    risks = bias_indicators(g, episode_id, now=now)

    ep = g.get(episode_id)
    reach = {episode_id} | g.reachable_from(episode_id, reverse=False)
    flip, stale = _flip_summary(g, ep, seed=seed, now=now)
    findings = [f for f in validate(g, rules_policy) + check_scope(g, episode_id)
                if _counts_for_episode(f, reach)]
    findings += check_objective_coverage(g, ep)
    findings += check_accreditation_scope(g, ep)
    findings += check_bias_check_evidence(g, ep, policy or {})
    findings += check_policy_resolves(g, charter)
    findings += check_blocking_rules_known(policy)
    findings += stale

    blocking_rules = {r for r in ((policy or {}).get("blockingRules") or [])
                      if isinstance(r, str)}
    blockers, warnings = [], []
    for f in sorted(set(findings)):
        if f.severity == "blocking":
            blockers.append(f.to_dict())
        elif f.rule in blocking_rules:
            blockers.append({**f.to_dict(), "promotedBy": "policy.blockingRules"})
        else:
            warnings.append(f.to_dict())

    sa = score_standards(g, episode_id, tailoring, k=k, now=now)
    ms = score_mandate(g, episode_id, now=now)

    priority = _gap_priority(g, ep)
    gaps = _reachable_of_type(g, reach, "InsufficientEvidence")
    gaps.sort(key=lambda i: (0 if (_obj(g, i) or {}).get("impact") == "blocking" else 1,
                             priority.get(i, NO_LINCHPIN), i))

    rr = {
        "id": report_id, "type": "ReadinessReport", "rev": 1,
        "createdBy": KERNEL_ACTOR, "createdAt": now,
        "episode": episode_id,
        "standardsAssessment": sa["id"],
        "mandateScorecard": ms["id"],
        "blockers": blockers,
        "warnings": warnings,
        "openGaps": gaps,
        "openExclusions": _reachable_of_type(g, reach, "Exclusion"),
        "flipSummary": flip,
        # Every listed check, resolvable or not: a bias check the store cannot find is a
        # hole in the bias section, and dropping the row would hide it.
        "biasChecksStatus": [{"check": b, "status": (_obj(g, b) or {}).get("status")}
                             for b in (ep.get("biasChecks") or []) if isinstance(b, str)],
        "computedBiasRisks": [r["id"] for r in risks],
        "ready": not blockers,
        "policyVersion": (policy or {}).get("version") if isinstance(
            (policy or {}).get("version"), str) else "unknown",
        "kernelVersion": KERNEL_VERSION,
        "seed": seed,
    }
    g.put(rr, KERNEL_ACTOR)
    ep = g.get(episode_id)
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": KERNEL_ACTOR, "createdAt": now,
           "readiness": rr["id"]}, KERNEL_ACTOR)
    return rr


__all__ = ["readiness_report", "accreditation_lineage", "check_objective_coverage",
           "check_accreditation_scope", "check_bias_check_evidence",
           "check_policy_resolves", "check_blocking_rules_known"]
