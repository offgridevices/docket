"""Lifecycle transitions with recorded policy checks (design §5.2 gates G1–G4).

A gate is not a button. Every human or kernel attempt to move an episode — passed or
refused — appends a record to the episode naming the actor, the time, the policy version
in force and the result of every check the gate ran. A refusal is written by the actor
who was refused and then raised as `TransitionRefused`; the state does not move, but the
attempt is in the record. Nothing about a *human or kernel* gate attempt is silent, with
one narrow exception: if the stored episode is itself schema-invalid — reachable only on
a hand-edited store, since `Graph.load` verifies hashes and the chain but not the schema
— `put` raises `ValidationError` and no record lands. The same reasoning that keeps an
unreadable `transitions` field from swallowing the record cannot save an object the
schema will not accept at all.

Who may drive which edge is part of the boundary the whole architecture rests on:
- `MODEL_APPROVED`, `PLAN_APPROVED`, `SIGNED`, `VOID` are **human-only**. These are the
  three human gates (G1, G2, G3) plus the abandon edge.
- `SUSPECT` and `SUPERSEDED` are **kernel-only**. They are what the refresh engine (G4)
  concludes when a record's inputs move; they are findings, not opinions.
- An **agent** may drive nothing, and "agent" is derived rather than declared: an
  `actorId` beginning `agent:` is an agent whatever `actorType` claims, and an actor
  whose two halves disagree is refused as malformed (`objects.actor_class_mismatch`,
  applied in `Graph.put`, the one write every transition passes through).
  `Graph.put` refuses an agent revision that changes `lifecycleState` or `transitions`,
  so the store raises `AuthorityViolation` before any record is written. This is the
  other exception to the paragraph above — an agent's forbidden attempt at a transition
  is refused at the store boundary and never enters the record at all, not even as a
  refusal; the log is append-only and hash-chained (tamper-evident, not tamper-proof —
  the chain is unkeyed in Phase I, so it proves the store is internally consistent, and
  proves it has not changed only against a log head retained elsewhere; signing entries
  would make it evidence of authorship, and that is not Phase I), but that guarantee
  only ever covers what was written, and this is a case of nothing being written.
- Every target state but `VOID` also consults the whole-store rules before any of its
  own checks are read (`whole_store_blockers`): a broken log chain or a forged
  authorship line refuses the transition as `store-integrity`. `VOID` is exempt because
  abandoning a record must stay possible precisely when the record cannot be trusted.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from docket.errors import TransitionRefused, ValidationError
from docket.kernel.validate import WHOLE_STORE_RULES, orphan_gaps, validate
from docket.objects import is_content
from docket.store import Graph

Check = Callable[[Graph, dict], bool]

EDGES: dict[str, set[str]] = {
    "DRAFT": {"MODEL_APPROVED", "VOID"},
    "MODEL_APPROVED": {"PLAN_APPROVED", "SUSPECT", "VOID"},
    "PLAN_APPROVED": {"EVALUATED", "SUSPECT", "VOID"},
    "EVALUATED": {"PENDING_SIGNATURE", "SUSPECT", "VOID"},
    "PENDING_SIGNATURE": {"SIGNED", "SUSPECT", "VOID"},
    "SIGNED": {"SUSPECT", "SUPERSEDED", "VOID"},
    "SUSPECT": {"SUPERSEDED", "VOID"},
    "SUPERSEDED": {"VOID"},
    "VOID": set(),
}
HUMAN_ONLY = {"MODEL_APPROVED", "PLAN_APPROVED", "SIGNED", "VOID"}
KERNEL_ONLY = {"SUSPECT", "SUPERSEDED"}

# The one edge a whole-store finding does not hold shut. Abandoning a record has to stay
# possible precisely when the record cannot be trusted; refusing `VOID` on a forged or
# tampered store would trap the episode in a state it could never leave, and voiding
# asserts nothing about the record's contents. Every other target — G1, G2, the
# evaluation and readiness steps, G3 and G4's two kernel edges — consults
# `WHOLE_STORE_RULES` [T9 review C1].
STORE_INTEGRITY_EXEMPT = {"VOID"}

# AR 5-11 ¶4-5b(1)–(3): the three fields G1 exists to put a human's name against.
AR_5_11_FIELDS = ("question", "decisionToBeMade", "consequencesOfErroneousOutput")


def _tolerant(fn: Check) -> Check:
    """A check that cannot be evaluated has not been satisfied.

    Gates run over stores this process did not write. A hand-edited or
    different-version store can hold any shape at all, and a gate that raises on one is a
    gate that cannot be run on the store it exists to audit. Every check is written to
    read defensively; this is the last resort behind that, and it fails *closed* — the
    check lands in `checksUnsatisfied`, which is recorded and refuses the transition,
    rather than escaping as a traceback.
    """

    @functools.wraps(fn)
    def wrapper(g: Graph, ep: dict) -> bool:
        try:
            return bool(fn(g, ep))
        except Exception:
            return False

    return wrapper


def _obj(g: Graph, ref) -> dict | None:
    """The object `ref` names, or None — for any shape of `ref` at all."""
    if not isinstance(ref, str) or not g.has(ref):
        return None
    obj = g.get(ref)
    return obj if isinstance(obj, dict) else None


def _own(g: Graph, ep: dict, field: str) -> dict | None:
    """The object `ep[field]` names, but only if it was computed *for this episode*.

    `ReadinessReport` and `Commitment` both carry a required `episode` ref. Resolving the
    forward reference alone would let an episode be signed on another episode's readiness
    report — a sign-swap that needs no hand-editing, only crossed wiring, and that leaves
    a store auditing perfectly clean. The gate compares the reference back.
    """
    obj = _obj(g, ep.get(field))
    if obj is None or obj.get("episode") != ep.get("id"):
        return None
    return obj


def _actor_type(obj) -> str | None:
    author = obj.get("createdBy") if isinstance(obj, dict) else None
    return author.get("actorType") if isinstance(author, dict) else None


def _reach(g: Graph, ep: dict) -> set[str]:
    """The episode and everything it transitively references — its model.

    Forward reachability, not reverse: G1 asks whether *this* record is sound, and a
    second episode's broken charter is not this episode's concern.
    """
    oid = ep.get("id")
    if not isinstance(oid, str):
        raise ValidationError(["episode has no id"])
    return {oid} | g.reachable_from(oid, reverse=False)


def _plan(g: Graph, ep: dict) -> dict | None:
    return _obj(g, ep.get("plan"))


def _plan_steps(g: Graph, ep: dict) -> list | None:
    plan = _plan(g, ep)
    steps = plan.get("steps") if plan is not None else None
    return steps if isinstance(steps, list) and steps else None


def _policy(g: Graph, ep: dict) -> dict | None:
    charter = _obj(g, ep.get("charter"))
    return _obj(g, charter.get("decisionClassPolicy")) if charter is not None else None


def policy_version(g: Graph, ep: dict) -> str:
    """The policy version the checks ran under, or `"unknown"`.

    An episode whose charter or policy cannot be resolved is already refused by G1's
    `no-blocking-structural` (a dangling `decisionClassPolicy` is a ref-integrity
    breach), so this fallback only ever labels a record on the abandon path. Recording
    `"unknown"` says which; inventing a version would not.
    """
    policy = _policy(g, ep)
    version = policy.get("version") if policy is not None else None
    return version if isinstance(version, str) and version else "unknown"


# ---- G1: the model ------------------------------------------------------------------


@_tolerant
def c_charter(g: Graph, ep: dict) -> bool:
    """The three AR 5-11 ¶4-5b fields hold content — not silence, not a gap marker."""
    charter = _obj(g, ep.get("charter"))
    return charter is not None and all(is_content(charter.get(k)) for k in AR_5_11_FIELDS)


@_tolerant
def c_charter_human(g: Graph, ep: dict) -> bool:
    """The latest revision of that Charter was written by a human.

    Design §8.2 requires the three fields "human-authored or human-accepted". An
    elicited charter nobody edited satisfies neither: accepting it means writing the
    revision, which puts a human name on it.

    Authorship only. `charter-three-fields` already carries the fields, and a refusal
    that named both would tell a reviewer no human accepted a charter a human wrote.
    """
    return _actor_type(_obj(g, ep.get("charter"))) == "human"


@_tolerant
def c_no_blocking_structural(g: Graph, ep: dict) -> bool:
    """No blocking structural finding touches anything this episode can reach.

    Severity, not a hardcoded list of rule names: `validate(g)` with no policy runs the
    structural rules and nothing else, so every finding it returns is structural by
    construction, and a rule added later is covered without editing this gate. Warnings
    (`run-inputs-changed`: re-run before you rely on this) do not hold a gate shut.

    Reach scopes the *object-level* rules only. A `WHOLE_STORE_RULES` finding — a broken
    log chain, a forged authorship line — is not another episode's problem: it
    invalidates every reading of the store, this episode's included. Same predicate the
    standards scorer uses, from the same definition.
    """
    ids = _reach(g, ep)
    return not any(
        f.severity == "blocking"
        and (f.rule in WHOLE_STORE_RULES or not f.objects or set(f.objects) & ids)
        for f in validate(g)
    )


def whole_store_blockers(g: Graph) -> list[str]:
    """Every blocking `WHOLE_STORE_RULES` finding — a broken log chain, a forged
    authorship line — rendered as `object[, object]: message`, regardless of which
    episode's objects it names.

    Each string names the offending object, because the blast radius is wide by design
    and a refusal that only said "this store is not trustworthy" would be undiagnosable
    on a multi-episode programme: an honest scoping bug in one study must be findable
    from the refusal it caused in another [T9 review M2].

    These are not one episode's problem. A tampered log or an authorship line the store
    cannot vouch for invalidates every reading of the store, so this is consulted on every
    gate rather than only inside G1's `no-blocking-structural`, and by
    `kernel.evaluate.evaluate` before it computes anything [T9 review C1]. Same set, one
    definition, three consumers.

    Defensive like the checks are: a store this process did not write can be malformed in
    ways `validate()` itself refuses to survive, and a gate that raises is a gate that
    cannot be run on the store it exists to audit. An unreadable store is treated as a
    blocked one — the safe direction.
    """
    try:
        return sorted(
            (", ".join(f.objects) + ": " if f.objects else "") + f.message
            for f in validate(g)
            if f.severity == "blocking" and f.rule in WHOLE_STORE_RULES
        )
    except Exception as exc:
        return [f"the store could not be validated: {type(exc).__name__}: {exc}"]


@_tolerant
def c_gaps_confirmed(g: Graph, ep: dict) -> bool:
    """Every InsufficientEvidence the episode reaches has been confirmed by a human.

    The store already refuses an agent that sets `confirmedBy`, so the field's presence
    is the human's signature on "yes, this really is missing".

    "Reaches" includes the gaps that hang off nothing at all (`orphan_gaps`): a gap the
    model recorded but could not route to a field is still a gap, and a gate that opened
    over one would record that a human confirmed something they were never shown.
    """
    for oid in sorted(_reach(g, ep) | orphan_gaps(g)):
        obj = _obj(g, oid)
        if obj is None or obj.get("type") != "InsufficientEvidence":
            continue
        if not is_content(obj.get("confirmedBy")):
            return False
    return True


@_tolerant
def c_linchpins_human(g: Graph, ep: dict) -> bool:
    """No unreviewed linchpin: the latest revision of every linchpin Assumption is human.

    An assumption the gate cannot read at all counts as unreviewed.
    """
    ids = ep.get("assumptions")
    if not isinstance(ids, list):
        return False
    for ref in ids:
        obj = _obj(g, ref)
        if obj is None:
            return False
        if obj.get("linchpin") is True and _actor_type(obj) != "human":
            return False
    return True


# ---- G2: the plan -------------------------------------------------------------------


@_tolerant
def c_plan_present(g: Graph, ep: dict) -> bool:
    """The episode names a plan, and the store holds it.

    The docstring's first line is what `queue.what_would_satisfy` prints on the queue and
    on the gate ladder; without one this check named its own source file at a reader.
    """
    return _plan(g, ep) is not None


def _fields(value, *names: str) -> bool:
    """`value` is an object carrying content in every one of `names`.

    A schema-valid store cannot hold anything else; a hand-edited one can hold
    `authority: "see the memo"`, and a check that accepted it would be asserting less
    than its own name claims.
    """
    return isinstance(value, dict) and all(is_content(value.get(n)) for n in names)


@_tolerant
def c_plan_approved(g: Graph, ep: dict) -> bool:
    """The plan carries a named approval and a date, on a revision a human wrote.

    `Graph.put` refuses an agent that sets `approvedBy`, but a saved store can be edited
    by hand, so the gate re-derives the authorship instead of trusting the field.
    """
    plan = _plan(g, ep)
    return (plan is not None and _fields(plan.get("approvedBy"), "actorId", "date")
            and _actor_type(plan) == "human")


@_tolerant
def c_plan_authority(g: Graph, ep: dict) -> bool:
    """Every step cites the doctrine paragraph that requires it (DMN AuthorityRequirement).

    A citation is a document *and* a paragraph. "See the memo" is not an authority.
    """
    steps = _plan_steps(g, ep)
    if steps is None:
        return False
    return all(isinstance(s, dict) and _fields(s.get("authority"), "document", "paragraph")
               for s in steps)


@_tolerant
def c_policy_method(g: Graph, ep: dict) -> bool:
    """No step may quietly use a method the decision-class policy did not choose."""
    steps = _plan_steps(g, ep)
    policy = _policy(g, ep)
    if steps is None or policy is None:
        return False
    want = policy.get("method")
    return bool(want) and all(isinstance(s, dict) and s.get("method") == want for s in steps)


# ---- EVALUATED, PENDING_SIGNATURE, G3 SIGNED ----------------------------------------


@_tolerant
def c_every_step_has_run(g: Graph, ep: dict) -> bool:
    """Every planned step has a sealed run *of this plan* behind it."""
    steps = _plan_steps(g, ep)
    run_ids = ep.get("runs")
    if steps is None or not isinstance(run_ids, list):
        return False
    plan_id = ep.get("plan")
    evaluated = set()
    for ref in run_ids:
        run = _obj(g, ref)
        if run is not None and run.get("plan") == plan_id:
            evaluated.add(run.get("step"))
    return all(isinstance(s, dict) and s.get("id") in evaluated for s in steps)


@_tolerant
def c_readiness_present(g: Graph, ep: dict) -> bool:
    """This episode has been scored against the standard, and the report is on record.

    The docstring's first line is what `queue.what_would_satisfy` prints on the queue and
    on the gate ladder; without one this check named its own source file at a reader.
    """
    return _own(g, ep, "readiness") is not None


@_tolerant
def c_readiness_ready(g: Graph, ep: dict) -> bool:
    """This episode's own readiness report says the record is ready to be signed."""
    readiness = _own(g, ep, "readiness")
    return readiness is not None and readiness.get("ready") is True


@_tolerant
def c_commitment_present(g: Graph, ep: dict) -> bool:
    """A Commitment for this episode is recorded: someone has taken the decision."""
    return _own(g, ep, "commitment") is not None


@_tolerant
def c_commitment_hash(g: Graph, ep: dict) -> bool:
    """The signature binds to a package hash — and to *this* package.

    A non-empty `packageHash` is not enough: G4's whole argument is that the record a
    signer read is the record they signed, so `Commitment.packageHash` must equal
    `latest_package_hash(g, ep['id'], rendering="full")` — the hash of the most
    recently built full-rendering `DecisionPackage` for this episode (the signer
    reads the full record, never the unclassified one, so `full` is the rendering
    this binds to). No package built at all, or a hash that no longer matches the
    latest build (the record changed and was re-rendered after the commitment was
    written, or before it), fails the check by the same return value — the
    transition record names the check, not the reason, so there is nothing to
    distinguish here.

    `docket.kernel.render` is imported lazily, inside the function, rather than at
    module level: `lifecycle.py` is a foundational gate module with no other
    same-layer kernel dependency, `render.py` is a presentation-layer consumer of
    the kernel (it already imports `kernel.validate`), and importing it at call time
    keeps that layering visible and keeps a future accidental cycle (were `render.py`
    ever to need something that itself imports `lifecycle.py`) from being a hard
    module-load-time failure. Verified empirically today that a top-level import
    would not in fact cycle; the lazy import is a deliberate layering choice, not a
    workaround for an existing one.
    """
    from docket.kernel.render import latest_package_hash

    commitment = _own(g, ep, "commitment")
    package_hash = commitment.get("packageHash") if commitment is not None else None
    if not isinstance(package_hash, str) or not package_hash:
        return False
    episode_id = ep.get("id")
    if not isinstance(episode_id, str):
        return False
    return package_hash == latest_package_hash(g, episode_id, rendering="full")


CHECKS: dict[str, list[tuple[str, Check]]] = {
    # G1 — the model. Nothing is computed until this passes.
    "MODEL_APPROVED": [("charter-three-fields", c_charter),
                       ("charter-human-accepted", c_charter_human),
                       ("no-blocking-structural", c_no_blocking_structural),
                       ("gaps-confirmed", c_gaps_confirmed),
                       ("linchpins-human", c_linchpins_human)],
    # G2 — the plan. `evaluate()` enforces this one again, in the kernel.
    "PLAN_APPROVED": [("plan-present", c_plan_present),
                      ("plan-approved-by-human", c_plan_approved),
                      ("plan-steps-have-authority", c_plan_authority),
                      ("policy-method-matches", c_policy_method)],
    "EVALUATED": [("every-step-has-run", c_every_step_has_run)],
    "PENDING_SIGNATURE": [("readiness-present", c_readiness_present)],
    # G3 — the signature.
    "SIGNED": [("commitment-present", c_commitment_present),
               ("readiness-ready", c_readiness_ready),
               ("commitment-package-hash", c_commitment_hash)],
    # G4's edges. The kernel-only restriction is the whole check: SUSPECT and SUPERSEDED
    # are conclusions the refresh engine draws, and refresh.py decides when to draw them.
    "SUSPECT": [],
    "SUPERSEDED": [],
    "VOID": [],
}


def transition(g: Graph, episode_id: str, to_state: str, actor: dict, *, now: str) -> dict:
    """Attempt one lifecycle transition; record it either way.

    Returns the new episode revision on success. On refusal, appends a record with
    `refused: true` naming every unsatisfied check — written by the actor who was
    refused, so the history says who tried — and raises `TransitionRefused`.
    """
    if not isinstance(episode_id, str) or not g.has(episode_id):
        raise ValidationError([f"episode {episode_id!r} is not in the graph"])
    ep = g.get(episode_id)
    frm = ep.get("lifecycleState")

    satisfied: list[str] = []
    unsatisfied: list[str] = []
    if to_state not in EDGES.get(frm, set()):
        unsatisfied.append(f"edge-{frm}-to-{to_state}")
    actor_type = _actor_type({"createdBy": actor})
    if to_state in HUMAN_ONLY and actor_type != "human":
        unsatisfied.append("human-actor")
    if to_state in KERNEL_ONLY and actor_type != "kernel":
        unsatisfied.append("kernel-actor")
    # A precondition, recorded the same way the edge rule and the actor rules are: named
    # in `checksUnsatisfied` when it fails and absent when it passes, because a store
    # whose integrity is intact is the ordinary case and not a check the gate ran.
    if to_state not in STORE_INTEGRITY_EXEMPT and whole_store_blockers(g):
        unsatisfied.append("store-integrity")
    for name, check in CHECKS.get(to_state, []):
        (satisfied if check(g, ep) else unsatisfied).append(name)

    who = actor if isinstance(actor, dict) else {}
    record = {
        "from": f"{frm}", "to": f"{to_state}",
        "actor": {"actorType": who.get("actorType"), "actorId": who.get("actorId")},
        "at": now, "policyVersion": policy_version(g, ep),
        "checksSatisfied": satisfied, "checksUnsatisfied": unsatisfied,
        "refused": bool(unsatisfied),
    }
    # `Graph.load` verifies hashes and the chain, not the schema, so a re-chained store
    # can hand this function a `transitions` field of any shape at all. Fail closed like
    # the checks do: an unreadable history is no history, and the record still lands.
    prior = ep.get("transitions")
    new = {**ep, "rev": ep["rev"] + 1, "createdBy": actor, "createdAt": now,
           "transitions": (prior if isinstance(prior, list) else []) + [record]}
    if not unsatisfied:
        new["lifecycleState"] = to_state
    stored = g.put(new, actor)
    if unsatisfied:
        raise TransitionRefused(unsatisfied)
    return stored


__all__ = ["CHECKS", "EDGES", "HUMAN_ONLY", "KERNEL_ONLY", "STORE_INTEGRITY_EXEMPT",
           "orphan_gaps", "transition", "whole_store_blockers"]
