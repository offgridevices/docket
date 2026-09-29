"""G3 — the signature as a record object.

`sign` writes the `Commitment` a person makes — the option chosen, the stop rules, the
dissent — bound by hash to the full package they read, and then drives the SIGNED
transition through `lifecycle.transition`, whose checks (`commitment-present`,
`readiness-ready`, `commitment-package-hash`) are the only thing that lets the state
change. Nothing here bypasses a gate; a refusal is written to the episode's
transitions like any other.

A refusal leaves the record honest. `transition` writes the refused attempt to the
episode, but the revision this module wrote just before it — `episode.commitment`
pointing at the new `Commitment` — would then read, to `kernel.queue` (which drops the
`signature` item once a commitment resolves) and to `kernel.render` (which prints the
commitment into the next package), as if the decision had been taken. So on
`TransitionRefused` one more episode revision restores `commitment` to what it was
before the attempt, and the error is re-raised. The `Commitment` object and the refused
transition stay on the record: the attempt is recorded either way.

A standing send-back closes the gate up front: while `signed_return_triggers` — the
same predicate `kernel.queue.needs` uses for its `sent-back` item — lists a signer-return
newer than the latest full package and not yet opened as a refresh, signing is refused
with `ValidationError`, so the queue and this module can never disagree about it.

Conditions are written as an empty list in this version: the schema requires each
condition to name an `Action` object to verify it by, and no route creates `Action`s
yet. The view says so ("Conditions are not yet captured here").
"""
from __future__ import annotations

import re

from docket.errors import AuthorityViolation, TransitionRefused, ValidationError
from docket.kernel.clock import signed_return_triggers
from docket.kernel.lifecycle import transition
from docket.kernel.render import latest_package_hash
from docket.store import Graph


def _next_commitment_number(g: Graph, episode_id: str) -> int:
    """One more than the commitments already filed under this episode's id scheme.

    Counts exact matches of `cm-{episode}-` followed by digits only, the way
    `refresh.signer_return` counts its triggers — but closed against a prefix-sharing
    episode: `ep-x` must not count `cm-ep-x-r2-1` as its own, or the next id it mints
    would collide with a commitment that belongs to `ep-x-r2`.
    """
    own = re.compile(rf"^cm-{re.escape(episode_id)}-\d+$")
    return 1 + sum(1 for c in g.all("Commitment") if own.fullmatch(str(c.get("id", ""))))


def sign(g: Graph, episode_id: str, *, actor: dict, now: str, selected: str, role: str,
         stop_rules: list[str], dissent: list[dict] | None = None) -> dict:
    if not isinstance(actor, dict) or actor.get("actorType") != "human":
        raise AuthorityViolation("sign requires a human actor")
    # `signer.identity` is who took the decision — printed on the package, in the activity
    # log and beside the commitment. An actor with no `actorId` would record the string
    # "None" there and read as a person called None; refuse it here, before anything is
    # composed, exactly as `refresh.signer_return` refuses it for `source`.
    actor_id = actor.get("actorId")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValidationError(
            ["the actor has no actorId; a signature records by name who committed"]
        )
    if not isinstance(episode_id, str) or not g.has(episode_id):
        raise ValidationError([f"episode {episode_id!r} is not in the graph"])
    ep = g.get(episode_id)
    state = ep.get("lifecycleState")
    if state != "PENDING_SIGNATURE":
        raise ValidationError([f"episode {episode_id!r} is at {state!r}; only a decision "
                               "awaiting a signature can be signed"])
    if signed_return_triggers(g, episode_id):
        raise ValidationError(["This decision was sent back for rework; answer the return "
                               "before signing."])
    if selected not in (ep.get("alternatives") or []):
        raise ValidationError([f"{selected!r} is not one of this decision's options"])
    rules = [r.strip() for r in (stop_rules or []) if isinstance(r, str) and r.strip()]
    if not rules:
        raise ValidationError(["a signature needs at least one stop rule"])
    if not isinstance(role, str) or not role.strip():
        raise ValidationError(["a signature needs the signer's role"])
    package_hash = latest_package_hash(g, episode_id, rendering="full")
    if not package_hash:
        raise ValidationError(["sign needs a rendered full package to bind to"])
    n = _next_commitment_number(g, episode_id)
    commitment = {
        "id": f"cm-{episode_id}-{n}", "type": "Commitment", "rev": 1,
        "createdBy": actor, "createdAt": now,
        "episode": episode_id, "selected": selected,
        "signer": {"identity": actor_id.strip(), "role": role.strip()},
        "signedAt": now, "conditions": [], "stopRules": rules, "packageHash": package_hash,
    }
    if dissent:
        commitment["dissent"] = [
            {"who": str(d.get("who", "")).strip(), "text": str(d.get("text", "")).strip()}
            for d in dissent if isinstance(d, dict) and str(d.get("text", "")).strip()
        ]
    prior_commitment = ep.get("commitment")
    commitment = g.put(commitment, actor)
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": actor, "createdAt": now,
           "commitment": commitment["id"]}, actor)
    try:
        transition(g, episode_id, "SIGNED", actor, now=now)
    except TransitionRefused:
        # The gate has written the refused attempt; put `commitment` back as it was, on
        # top of that revision, so nothing downstream reads the refused attempt as a
        # decision taken.
        refused = g.get(episode_id)
        restored = {k: v for k, v in refused.items() if k != "commitment"}
        if prior_commitment is not None:
            restored["commitment"] = prior_commitment
        g.put({**restored, "rev": refused["rev"] + 1, "createdBy": actor, "createdAt": now},
              actor)
        raise
    return g.get(commitment["id"])


__all__ = ["sign"]
