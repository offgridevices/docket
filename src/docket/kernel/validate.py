"""Validator. Structural rules (this file, plan 02) + policy rules (added in plan 03)."""

from __future__ import annotations

from collections.abc import Callable

from docket.canon import content_hash
from docket.kernel.evaluate import inputs_hash_for
from docket.kernel.findings import Finding
from docket.objects import (
    AGENT_FORBIDDEN_TYPES,
    actor_class_mismatch,
    is_agent_actor,
    is_content,
    is_exclusion_ref,
    is_gap_ref,
    is_marker,
    iter_refs,
    iter_slots,
)
from docket.schema import validate_object
from docket.store import GENESIS, Graph

Rule = Callable[[Graph], list[Finding]]


def rule_schema(g: Graph) -> list[Finding]:
    out = []
    for o in g.all():
        errs = validate_object(o)
        if errs:
            out.append(Finding("schema", "blocking", (o["id"],), "; ".join(errs)))
    return out


def rule_ref_integrity(g: Graph) -> list[Finding]:
    out = []
    for o in g.all():
        missing = sorted({t for _, t in iter_refs(o) if not g.has(t)})
        if missing:
            out.append(
                Finding(
                    "ref-integrity", "blocking", (o["id"],),
                    f"dangling references: {', '.join(missing)}",
                )
            )
    return out


def rule_marker_type(g: Graph) -> list[Finding]:
    out = []
    for o in g.all():
        for path, v in iter_slots(o):
            if not is_marker(v):
                continue
            target_id = v.get("$gap") or v.get("$exclusion")
            if not g.has(target_id):
                continue  # ref-integrity reports it
            target = g.get(target_id)
            want = "InsufficientEvidence" if is_gap_ref(v) else "Exclusion"
            if target["type"] != want:
                out.append(
                    Finding(
                        "marker-type", "blocking", (o["id"],),
                        f"{path}: marker points at {target['type']}, expected {want}",
                    )
                )
        # nested markers in arrays of items (e.g. VVARecord sections) are covered by iter_slots
    return out


def rule_silence(g: Graph) -> list[Finding]:
    """P3: every slot holds content, an Exclusion, or an InsufficientEvidence.

    Empty content is silence.
    """
    out = []
    for o in g.all():
        empty = [path for path, v in iter_slots(o) if not is_content(v) and not is_marker(v)]
        if empty:
            out.append(
                Finding(
                    "silence", "blocking", (o["id"],),
                    "empty required slot(s): " + ", ".join(empty),
                )
            )
    return out


def rule_log_chain(g: Graph) -> list[Finding]:
    prev = GENESIS
    for e in g.log():
        body = {k: v for k, v in e.items() if k != "entryHash"}
        if e["prevHash"] != prev or content_hash(body) != e["entryHash"]:
            return [
                Finding("log-chain", "blocking", (e["id"],), f"log chain broken at seq {e['seq']}")
            ]
        prev = e["entryHash"]
    return []


def _author_of(obj) -> dict | None:
    """The `createdBy` dict on `obj`, or None for any shape that is not one."""
    author = obj.get("createdBy") if isinstance(obj, dict) else None
    return author if isinstance(author, dict) else None


def _is_agent_authored(obj: dict) -> bool:
    """Whether an agent wrote this object, derived from the id as well as the declaration.

    `objects.is_agent_actor` reads `actorId` too, so an object whose `createdBy` says
    `{"actorType": "human", "actorId": "agent:x"}` is agent-authored here [T9 review M1].
    """
    return is_agent_actor(_author_of(obj))


def _describe(actor) -> str:
    """`'agent:recorded' (agent)` — a stable rendering for a finding message.

    Not `repr(dict)`: a dict's key order comes from whatever JSON the store happened to
    hold, and a finding message that changes with it is not a stable audit output.
    """
    if not isinstance(actor, dict):
        return repr(actor)
    return f"{actor.get('actorId')!r} ({actor.get('actorType')!r})"


def _revisions(g: Graph) -> list[tuple[str, int, dict | None]]:
    """Every `(id, rev, log-entry actor)` the store holds, log entries first.

    The log is the spine: `Graph.load` builds `_latest` and `_history` from it, so on any
    loaded store every revision appears here exactly once, with the actor its log entry
    names. A revision present in the object history but named by no log entry — reachable
    only on a graph assembled in memory without `put` — is appended with `None` for the
    actor, so the audit still reads its `createdBy` rather than skipping it silently.
    """
    seen: set[tuple[str, int]] = set()
    out: list[tuple[str, int, dict | None]] = []
    for e in g.log():
        oid, rev = e.get("id"), e.get("rev")
        if not isinstance(oid, str) or not isinstance(rev, int) or isinstance(rev, bool):
            continue  # a malformed entry is log-chain's finding, not this rule's
        actor = e.get("actor")
        out.append((oid, rev, actor if isinstance(actor, dict) else None))
        seen.add((oid, rev))
    for o in g.all():
        oid, head = o.get("id"), o.get("rev")
        if not isinstance(oid, str) or not isinstance(head, int) or isinstance(head, bool):
            continue
        out.extend((oid, rev, None) for rev in range(1, head + 1) if (oid, rev) not in seen)
    return out


def rule_authority(g: Graph) -> list[Finding]:
    """The agent boundary, re-checked from the store rather than from the write path.

    `put` refuses these writes in process, but a store can be hand-edited and the chain is
    unkeyed, so a forgery re-chains cleanly. Auditing authorship here is what makes the
    boundary checkable by a third party holding nothing but the saved store — and since
    that is what the proposal claims, this audits **all eight** rules
    `Graph._check_agent_authority` enforces, not only the forbidden-type rule
    [ruling R14, closing pre-flight defect 18]:

    1. no agent-authored object of an `AGENT_FORBIDDEN_TYPES` type;
    2. no agent-authored `Plan` carrying `approvedBy`;
    3. no agent-authored `Evidence` whose `reviewStatus` is anything but `draft`;
    4. no agent-authored revision of `Evidence` whose **predecessor** was not `draft` —
       including the downgrade, an agent quietly returning reviewed evidence to `draft`,
       which rule 3 alone cannot see because the revision it lands on looks compliant;
    5. no agent-authored `InsufficientEvidence` carrying `confirmedBy`;
    6. no agent-authored `Exclusion` whose `authority` is not this agent's own
       `agent-proposal` — and, on a revision, no agent-authored `Exclusion` whose
       **predecessor** was authorised by a human or proposed by a different agent;
    7. no agent-authored `DecisionEpisode` revision that changed `lifecycleState`;
    8. no agent-authored `DecisionEpisode` revision that changed `transitions`.

    Plus two consistency rules without which the eight above are defeated by a cheaper
    forgery than the one they were written for [T9 review I5, M1]:

    * every log entry's `actor` must equal the `createdBy` of the object revision it
      names. `Graph.load` verifies the object's hash against the entry, but the entry's
      actor is not part of the object, so the two can disagree and the store still
      loads — one word in one log line, and the audit used to pass.
    * an actor's declared `actorType` must agree with its `actorId` (`objects.
      actor_class_mismatch`): an id beginning `agent:` is an agent, whatever the dict
      says. The write path refuses the mismatch outright; this reports it from a store
      where the write path was bypassed.

    **Read from the log, not from `g.all()`.** Every rule walks every revision, because
    the head revision is not the record — an agent-authored `pl-cbo@1` carrying an
    approval, superseded by an honest human `pl-cbo@2`, is exactly the shape a
    head-only audit misses, and it is the shape a forger would choose. Where a rule
    needs the revision *before* the one an agent wrote (rules 4, 6-on-revision, 7, 8)
    it reads that too; where the predecessor is missing from a truncated history the
    comparison is skipped and `log-chain` reports the truncation.

    **Blast radius.** The rule name stays `authority` and the severity stays `blocking`
    for every one of them, which puts them in `WHOLE_STORE_RULES`. Every gate G1–G4 and
    `kernel.evaluate.evaluate` consult that set, so a single forged authorship line
    holds every gate in the store shut and refuses evaluation, not merely for the
    episode it touched. The one edge it does not hold shut is `VOID`: abandoning a
    record has to stay possible precisely when the record cannot be trusted. The
    finding names the offending object, so an honest scoping bug (an `Exclusion` whose
    `authority.who` is wrong) is diagnosable and curable by a correcting revision —
    that is the accepted cost of the wide radius [T9 review C1/M2].

    Every read here is defensive. This rule runs over stores this process did not write, so
    a hand-edited object of any shape at all must produce a finding, never a traceback.
    """
    out: list[Finding] = []

    def finding(oid: str, message: str) -> None:
        out.append(Finding("authority", "blocking", (oid,), message))

    # (1) forbidden types, from the objects and from the log — the log too, because a
    # forgery may delete the object file's revision history and leave the entry behind.
    offenders: dict[str, str] = {}
    for o in g.all():
        if o["type"] in AGENT_FORBIDDEN_TYPES and _is_agent_authored(o):
            offenders[o["id"]] = o["type"]
    for e in g.log():
        oid = e.get("id")
        if (e.get("type") in AGENT_FORBIDDEN_TYPES and is_agent_actor(e.get("actor"))
                and isinstance(oid, str)):
            offenders.setdefault(oid, e["type"])
    for oid, t in sorted(offenders.items()):
        finding(oid, f"{t} was written by an agent; agents may not author {t}")

    # (2)–(8) and the two consistency rules, over every revision the store holds.
    for oid, rev, entry_actor in _revisions(g):
        try:
            cur = g.get(oid, rev)
        except (KeyError, TypeError):
            continue  # an entry with no object is log-chain's finding, not this one's
        if not isinstance(cur, dict):
            continue
        author = _author_of(cur)

        for label, actor in (("createdBy", author), ("its log entry's actor", entry_actor)):
            mismatch = actor_class_mismatch(actor)
            if mismatch is not None:
                finding(oid, f"{oid}@{rev}: {label} is malformed — {mismatch}")
        if entry_actor is not None and author is not None and entry_actor != author:
            finding(oid, f"the log entry for {oid}@{rev} names actor "
                         f"{_describe(entry_actor)}, but the object says it was written by "
                         f"{_describe(author)}; a record that cannot agree with its own log "
                         f"about who wrote a revision names nobody")

        # Fail closed: if either the object or its log entry says agent, audit as agent.
        if not (is_agent_actor(author) or is_agent_actor(entry_actor)):
            continue
        actor_id = author.get("actorId") if author is not None else None
        # rev 1 has no predecessor; a rev > 1 whose predecessor is missing from the
        # history has an unreadable one, and a comparison against nothing is not a
        # finding — `log-chain` reports the truncation that caused it.
        try:
            prev = g.get(oid, rev - 1) if rev > 1 else None
        except (KeyError, TypeError):
            prev = None
        if not isinstance(prev, dict):
            prev = None
        t = cur.get("type")

        if t == "Plan" and is_content(cur.get("approvedBy")):
            finding(oid, "Plan approval was authored by an agent; only a human may "
                         "approve a plan (gate G2)")

        if t == "Evidence":
            if cur.get("reviewStatus") != "draft":
                finding(oid, f"Evidence reviewStatus {cur.get('reviewStatus')!r} was "
                             f"authored by an agent; an agent may only write draft evidence")
            if prev is not None and prev.get("reviewStatus") != "draft":
                finding(oid, f"an agent revised evidence a human had marked "
                             f"{prev.get('reviewStatus')!r} (now "
                             f"{cur.get('reviewStatus')!r}); reviewed evidence is frozen "
                             f"against agents, content and status alike")

        if t == "InsufficientEvidence" and is_content(cur.get("confirmedBy")):
            finding(oid, "the confirmation on this gap was authored by an agent; only a "
                         "human may confirm that something is missing")

        if t == "Exclusion":
            authority = cur.get("authority")
            who = authority.get("who") if isinstance(authority, dict) else None
            role = authority.get("role") if isinstance(authority, dict) else None
            if role != "agent-proposal" or who != actor_id:
                finding(oid, f"agent-authored Exclusion claims authority {who!r}/{role!r}; "
                             f"an agent may only propose an omission under its own actorId "
                             f"as 'agent-proposal'")
            prior = prev.get("authority") if prev is not None else None
            prior_who = prior.get("who") if isinstance(prior, dict) else None
            prior_role = prior.get("role") if isinstance(prior, dict) else None
            if prev is not None and prior_role != "agent-proposal":
                finding(oid, f"an agent revised an exclusion authorised by "
                             f"{prior_who!r}/{prior_role!r}; a human-authorised omission is "
                             f"not the agent's to restate, even under its own name")
            elif prev is not None and prior_who != actor_id:
                finding(oid, f"an agent revised an exclusion proposed by {prior_who!r}; a "
                             f"proposal's authorship is as protected as its content")

        if t == "DecisionEpisode":
            if rev == 1:
                if cur.get("lifecycleState") != "DRAFT":
                    finding(oid, f"an agent created this episode at lifecycleState "
                                 f"{cur.get('lifecycleState')!r}; agents create DRAFT "
                                 f"episodes only")
                if cur.get("transitions") != []:
                    finding(oid, "an agent wrote a transition record when creating this "
                                 "episode")
            elif prev is not None:
                if cur.get("lifecycleState") != prev.get("lifecycleState"):
                    finding(oid, f"an agent moved this episode from "
                                 f"{prev.get('lifecycleState')!r} to "
                                 f"{cur.get('lifecycleState')!r}; only a human or the "
                                 f"kernel may drive a lifecycle edge")
                if cur.get("transitions") != prev.get("transitions"):
                    finding(oid, "an agent rewrote this episode's transition history")

    return sorted(set(out))


def _safe_content_hash(obj) -> str | None:
    """content_hash, or None if the object cannot be canonicalised at all.

    A hand-edited store can hold a NaN or a value canonical JSON refuses; the seal
    check must report that as an unverifiable seal, never raise out of `validate()`.
    """
    try:
        return content_hash(obj)
    except (TypeError, ValueError):
        return None


def _recompute_inputs_hash(g: Graph, run: dict) -> str | None:
    """The run's `inputsHash` recomputed from the graph as it stands now, or None when
    the run does not carry enough (plan, step, bindings) to recompute it at all."""
    plan_id, step_id = run.get("plan"), run.get("step")
    if not (isinstance(plan_id, str) and g.has(plan_id)):
        return None
    steps = g.get(plan_id).get("steps")
    if not isinstance(steps, list):
        return None
    step = next((s for s in steps if isinstance(s, dict) and s.get("id") == step_id), None)
    bindings = run.get("parameterBindings")
    if step is None or not isinstance(bindings, dict):
        return None
    weights, obs_ids = bindings.get("weights"), bindings.get("observationIds")
    if not isinstance(weights, dict) or not isinstance(obs_ids, list):
        return None
    return inputs_hash_for(g, step, weights, obs_ids)


def rule_run_seal(g: Graph) -> list[Finding]:
    """Every sealed EvaluationRun still hashes to what it says it does.

    `evaluate()` computes `runRecordHash` and `outputHashes` at seal time, but nothing
    re-derives them from a *loaded* store — so a hand-edited run keeps a stale hash that
    matches nothing, and a renderer printing `runRecordHash[:12]` as evidence of
    integrity would be printing decoration. This rule turns those fields into an
    auditable claim: recompute both, and treat any revision of a sealed object as a
    breach of immutability in its own right.
    """
    out: list[Finding] = []
    for run in g.all("EvaluationRun"):
        rid = run.get("id")
        objects = (rid,) if isinstance(rid, str) else ()
        if run.get("rev") != 1:
            out.append(Finding(
                "run-seal", "blocking", objects,
                f"sealed objects are immutable: EvaluationRun is at rev {run.get('rev')!r}",
            ))
        stored = run.get("runRecordHash")
        recomputed = _safe_content_hash({k: v for k, v in run.items() if k != "runRecordHash"})
        if recomputed is None:
            out.append(Finding("run-seal", "blocking", objects,
                                "run record cannot be canonicalised; its seal is unverifiable"))
        elif not isinstance(stored, str) or stored != recomputed:
            out.append(Finding(
                "run-seal", "blocking", objects,
                f"runRecordHash {stored!r} does not match the run record ({recomputed})",
            ))
        sealed_inputs = run.get("inputsHash")
        if isinstance(sealed_inputs, str):
            # A stale run is not a dishonest one: it still records truthfully what it
            # computed, and its own seal still verifies. What has changed is the graph
            # around it, so this is a warning — "re-run before you rely on this" — not a
            # blocking integrity breach.
            try:
                recomputed_inputs = _recompute_inputs_hash(g, run)
            except Exception as exc:  # a hand-edited store may be arbitrarily malformed
                out.append(Finding(
                    "run-seal", "blocking", objects,
                    f"sealed run inputs cannot be recomputed: {type(exc).__name__}: {exc}",
                ))
            else:
                if recomputed_inputs is not None and recomputed_inputs != sealed_inputs:
                    out.append(Finding(
                        "run-inputs-changed", "warning", objects,
                        "the graph no longer reproduces this run's inputsHash: an input "
                        "has been revised since the run was sealed",
                    ))

        outputs = run.get("outputs")
        hashes = run.get("outputHashes")
        if not isinstance(outputs, list) or not isinstance(hashes, list):
            out.append(Finding("run-seal", "blocking", objects,
                                "outputs and outputHashes must both be lists"))
            continue
        if len(outputs) != len(hashes):
            out.append(Finding(
                "run-seal", "blocking", objects,
                f"outputs ({len(outputs)}) and outputHashes ({len(hashes)}) differ in length",
            ))
            continue
        for oid, want in zip(outputs, hashes, strict=True):
            pair = objects + ((oid,) if isinstance(oid, str) else ())
            if not isinstance(oid, str) or not g.has(oid):
                out.append(Finding("run-seal", "blocking", pair,
                                    f"sealed output {oid!r} is not in the graph"))
                continue
            got = _safe_content_hash(g.get(oid))
            if got != want:
                out.append(Finding(
                    "run-seal", "blocking", pair,
                    f"outputHash {want!r} does not match Result {oid} ({got})",
                ))
    for res in g.all("Result"):
        if res.get("rev") == 1:
            continue
        rid, run_ref = res.get("id"), res.get("run")
        pair = tuple(x for x in (run_ref, rid) if isinstance(x, str))
        out.append(Finding(
            "run-seal", "blocking", pair,
            f"sealed objects are immutable: Result is at rev {res.get('rev')!r}",
        ))
    return out


STRUCTURAL_RULES: list[Rule] = [
    rule_schema, rule_ref_integrity, rule_marker_type, rule_silence, rule_log_chain,
    rule_authority, rule_run_seal,
]

# Store-integrity rules are about the store as a whole, not about one episode's objects.
# `rule_log_chain` names the object whose log entry broke the chain and `rule_authority`
# names the forged object — either may sit outside a given episode's reach, so any
# consumer that filters findings by reachability would swallow them. A tampered log or a
# forged authorship line invalidates every reading of the store, every episode's
# included, so these count regardless of reach.
#
# Defined here, next to the rules that emit them, and imported by every consumer
# (`kernel/standards.py`, `kernel/lifecycle.py`) rather than restated: a second copy is a
# second thing to forget when a rule is added.
WHOLE_STORE_RULES = frozenset({"log-chain", "authority"})


def orphan_gaps(g: Graph) -> set[str]:
    """Every `InsufficientEvidence` in the store that nothing references.

    A gap is normally reached through the slot it fills, and forward reachability finds
    it. But a gap can be recorded with nowhere to hang: the elicitation mapper emits one
    when the model reports having looked for something and names a field that does not
    exist, and no object in the catalogue — `DecisionEpisode` included — has a field that
    can hold a free-standing gap. Scoping such an object by reachability drops it out of
    the sheet, out of this gate, and out of the validator at the same time, and the
    episode is then signed asserting that every gap was confirmed by a human when one was
    never even shown to one. Silence is the failure mode this system exists to refuse.

    So an unattributable gap is in scope for every episode, which is the same fail-safe
    `policy_rules._exclusion_in_scope` already applies to an exclusion whose target names
    no object. Over-reporting a gap costs a reviewer one line; under-reporting one puts a
    false statement in a signed record.

    A store stand-in that cannot be enumerated at all — no `all`, no `refs_to` — holds no
    *readable* gap, and this returns the empty set rather than raising. That is a narrower
    tolerance than it looks: every real `Graph`, including one loaded from a hand-edited
    store, has both methods, and if either of them raises on the contents it is allowed to
    propagate so `_tolerant` can fail the check closed. Only the absence of the method
    itself is read as "nothing to see".
    """
    lister = getattr(g, "all", None)
    refs_to = getattr(g, "refs_to", None)
    if lister is None or refs_to is None:
        return set()
    return {x["id"] for x in lister("InsufficientEvidence")
            if isinstance(x.get("id"), str) and not refs_to(x["id"])}


# Every rule name the kernel can emit, in one place.
#
# `Policy.blockingRules` is a list of rule names written by hand into a policy document,
# and nothing else in the codebase reads it: a one-character typo would silently switch
# off a blocker the policy author asked for, and the readiness report would print a clean
# section. `readiness_report` checks each listed name against this set and reports the
# ones nothing emits, so the set has to be complete — `tests/kernel/test_readiness.py`
# derives the emitted names from the `Finding("…")` literals and asserts both directions.
KNOWN_RULES: frozenset[str] = frozenset({
    # structural (this file)
    "schema", "ref-integrity", "marker-type", "silence", "log-chain", "authority",
    "run-seal", "run-inputs-changed",
    # policy (kernel/policy_rules.py)
    "baseline-present", "alternative-status-unreasoned", "objective-measured",
    "linchpin-unevidenced", "linchpin-not-varied", "model-vva", "vva-verbal",
    "bias-check-missing",
    "bias-check-evidence-gap", "exclusion-prohibited-reason", "lexicon-mixed",
    "claim-on-gap", "claim-on-exclusion", "claim-unsupported", "silent-omission",
    "inclusion-reason-missing", "value-conflict", "value-conflict-internal",
    "gap-unconfirmed", "definition-missing", "assumption-conflict",
    "observation-duplicate",
    # scope of validity (kernel/scope.py)
    "scope-unknown", "scope-lapsed", "condition-mismatch", "reuse-justified",
    "ReusePastPurpose", "ModelUsePastPurpose", "ReaccreditationRequired",
    "NotAssessableAtLevel", "assessable-with-classified-value",
    "claim-on-rejected-evidence",
    # semantic readiness (kernel/readiness.py)
    "objective-run-coverage", "accreditation-scope", "bias-check-evidence-unreviewed",
    "run-stale", "flip-summary-unavailable", "policy-unresolved",
    "blocking-rule-unknown",
})
# populated by docket.kernel.policy_rules (plan 03)
POLICY_RULES: list[Callable[[Graph, dict], list[Finding]]] = []

_POLICY_LOADED = False


def _ensure_policy_rules() -> None:
    """Import docket.kernel.policy_rules exactly once, to register POLICY_RULES."""
    global _POLICY_LOADED
    if not _POLICY_LOADED:
        from docket.kernel import policy_rules  # noqa: F401
        _POLICY_LOADED = True


def validate(g: Graph, policy: dict | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for rule in STRUCTURAL_RULES:
        findings.extend(rule(g))
    if policy is not None:
        _ensure_policy_rules()
        for prule in POLICY_RULES:
            findings.extend(prule(g, policy))
    return sorted(set(findings))


__all__ = ["validate", "Finding", "STRUCTURAL_RULES", "POLICY_RULES", "WHOLE_STORE_RULES",
           "KNOWN_RULES", "is_exclusion_ref", "orphan_gaps"]
