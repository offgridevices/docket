# src/docket/agent/plan.py
"""Stage P: the agent proposes an evaluation Plan; a human approves it (G2).

`propose_plan()` builds a deterministic skeleton — one step per WeightSet in the episode,
naming its measures, alternatives, evaluator, method and sensitivity sweeps, all computed
from the graph — and asks the backend for exactly two strings per step: a doctrine
citation key drawn from the closed `AUTHORITY_CATALOGUE` and one sentence of rationale.
Nothing numeric, no ranking, no weight and no choice of measure, alternative or evaluator
ever comes from the backend; see `prompts/authority.md`. The Plan it writes carries no
`approvedBy` — `Graph.put` raises `AuthorityViolation` if an agent revision tries to set
one — so the record it produces cannot itself pass G2.

`Plan.steps[]` is `additionalProperties: false` and has no `rationale` property
[pre-flight defect 6], so the backend's sentence has nowhere to live inside a step. It is
persisted instead as its own `Rationale` object, put by the agent actor before the Plan,
at id `rat-{plan_id}-{step_id}` — that id convention is the only link between a step and
its rationale; read it back with `step_rationale(g, plan_id, step_id)`.

`steps[].evaluator` is a required `Model` ref that the brief never sourced
[pre-flight defect 7]: it comes from `episode["models"]`. Exactly one model resolves it
without a rule; zero, or more than one whose declared `inputs` do not narrow to exactly
one candidate, is refused by name — a human names the evaluator in that case, the agent
does not choose between models.

`approve_plan()` is the one human-only function that ever sets `Plan.approvedBy`, matching
G2 (`kernel.lifecycle.CHECKS["PLAN_APPROVED"]`) and the kernel's own independent re-check
(`kernel.evaluate._require_plan_approval`) — belt and suspenders, on purpose. `propose_plan`
refuses, before writing anything, to replace a plan the episode already names if that
plan's `approvedBy` holds content: overwriting an approved plan is exactly the move G2
exists to stop, and the check is re-derived from the graph rather than trusted from a flag,
the same defensive posture `kernel.lifecycle.c_plan_approved` takes.

`author_weight_set()` is a third, earlier human action this module owns: `propose_plan`
needs at least one `WeightSet` in `episode["weightSets"]` and refuses outright otherwise
(`_skeleton_steps`'s own `ValidationError`), and nothing wrote one until this function
existed [plan 07 Task weights; see `task-9b-report.md`'s "WeightSet gap"]. Weights are a
human value judgement, never the agent's to propose — see the function's own docstring
for the id convention, the validation (reusing `kernel.evaluate.check_weights`, never a
second copy), and the `$gap` `provenance` a stated weight carries instead of a fabricated
`Evidence`.
"""

from __future__ import annotations

import logging
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from docket.agent.prompts import load_prompt
from docket.agent.review import _human_only
from docket.errors import AuthorityViolation, ValidationError
from docket.kernel.evaluate import check_weights
from docket.objects import is_content

__all__ = ["AUTHORITY_CATALOGUE", "PLAN_SCHEMA", "propose_plan", "approve_plan",
           "step_rationale", "author_weight_set"]

log = logging.getLogger("docket.agent.plan")

HERE = Path(__file__).parent
_CATALOGUE_PATH = HERE / "authority_catalogue.yaml"

@cache
def _load_catalogue() -> dict[str, dict[str, str]]:
    data = yaml.safe_load(_CATALOGUE_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


#: The doctrine paragraph that requires a plan step. Closed list; the agent picks a key,
#: never writes a citation. Loaded once and cached — see the module docstring and the YAML
#: file itself for the verification note on each entry.
AUTHORITY_CATALOGUE: dict[str, dict[str, str]] = _load_catalogue()

#: Fallback authority key when there is no backend, or the backend omits a step. Chosen
#: because "document the method before executing it" / "vary the key assumptions" apply to
#: every step regardless of which weight set it evaluates.
DEFAULT_AUTHORITY_KEY = "sensitivity"

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False, "required": ["steps"],
    "properties": {"steps": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "authorityKey", "rationale"],
        "properties": {"id": {"type": "string"},
                       "authorityKey": {"enum": sorted(AUTHORITY_CATALOGUE)},
                       "rationale": {"type": "string"}}}}},
}


# ---- graph helpers ---------------------------------------------------------------------


def _obj(g, ref: Any) -> dict | None:
    """The object `ref` names, or None — for any shape of `ref` at all."""
    if not isinstance(ref, str) or not g.has(ref):
        return None
    return g.get(ref)


def _policy_for(g, episode: dict) -> dict:
    charter = _obj(g, episode.get("charter"))
    policy = _obj(g, charter.get("decisionClassPolicy")) if charter is not None else None
    if policy is None:
        raise ValidationError(
            [f"episode {episode.get('id')!r} has no resolvable decision-class policy "
             f"(charter -> decisionClassPolicy); propose_plan cannot choose a method or "
             f"bias checks without one"]
        )
    return policy


def _strip_ws_prefix(weight_set_id: str) -> str:
    """`ws-primary` -> `primary`, so an agent-proposed step carries the same name Demo A's
    hand-built plan uses for the same weight set."""
    return weight_set_id[len("ws-"):] if weight_set_id.startswith("ws-") else weight_set_id


def _select_evaluator(g, episode_id: str, step_id: str, models: list[str],
                       measures: list[str]) -> str:
    """[pre-flight defect 7] `steps[].evaluator` is a required Model ref the brief never
    sourced. Exactly one declared model resolves it with no rule at all; otherwise, exactly
    one whose declared `inputs` cover this step's measures must be the unique candidate — a
    human names the evaluator in every other case, the agent will not choose between
    models."""
    if len(models) == 1:
        return models[0]
    covering = [m for m in models
                if set(measures) <= set(g.get(m).get("inputs") or [])]
    if len(covering) != 1:
        raise ValidationError([
            f"cannot choose an evaluator for step {step_id!r} of episode {episode_id!r}: "
            f"episode models {models}, models whose inputs cover {measures}: {covering}. "
            f"A human must name the evaluator; the agent will not pick between models."])
    return covering[0]


def _linchpin_bindings(g, ep: dict) -> list[dict]:
    """Every linchpin Assumption's `parameterBinding`, guarded: `parameterBinding` is
    optional and may be a `$gap` marker or any other shape at all in a hand-edited store."""
    out: list[dict] = []
    for ref in ep.get("assumptions") or []:
        a = _obj(g, ref)
        if a is None or a.get("linchpin") is not True:
            continue
        binding = a.get("parameterBinding")
        if (isinstance(binding, dict) and isinstance(binding.get("kind"), str)
                and isinstance(binding.get("target"), str)):
            out.append(binding)
    return out


def _varied_observations(g, ep: dict) -> list[dict]:
    out: list[dict] = []
    for ref in ep.get("observations") or []:
        o = _obj(g, ref)
        if o is not None and o.get("variedInSensitivity") is True:
            out.append(o)
    return out


def _sweeps_by_step(g, steps_meta: list[dict], bindings: list[dict],
                     varied_obs: list[dict]) -> dict[str, list[dict]]:
    """step id -> sorted sensitivity-sweep list, computed across ALL steps at once so a
    binding that no step claims can be logged rather than silently dropped [M3], and so a
    weight binding is only ever claimed by the step whose weight set it names AND whose
    measures actually contain the bound measure [M2] — `ws-primary:m-squad` is not a sweep
    on `primary` when `m-squad` is not one of `primary`'s measures, even though the weight
    set id matches.

    One entry per linchpin Assumption `parameterBinding` and per Observation with
    `variedInSensitivity is True`. Each entry is exactly `{"kind": ..., "target": ...}` —
    no `range` key (the policy or the assumption supplies one later, at flip analysis, if
    at all — see `kernel.flip._weight_range`/`_obs_range`). De-duplicated and sorted by
    `(kind, target)`.
    """
    sweeps: dict[str, set[tuple[str, str]]] = {m["id"]: set() for m in steps_meta}

    for b in bindings:
        kind, target = b["kind"], b["target"]
        claimed = False
        if kind == "weight":
            ws_target, _, measure_target = target.partition(":")
            for m in steps_meta:
                if m["weightSet"] == ws_target and measure_target in m["measures"]:
                    sweeps[m["id"]].add((kind, target))
                    claimed = True
        elif kind == "observation":
            o = _obj(g, target)
            if o is not None:
                for m in steps_meta:
                    if (o.get("measure") in m["measures"]
                            and o.get("alternative") in m["alternatives"]):
                        sweeps[m["id"]].add((kind, target))
                        claimed = True
        if not claimed:
            log.warning("linchpin parameterBinding %r is claimed by no plan step; dropped",
                       b)

    for o in varied_obs:
        for m in steps_meta:
            if o.get("measure") in m["measures"] and o.get("alternative") in m["alternatives"]:
                sweeps[m["id"]].add(("observation", o["id"]))

    return {sid: [{"kind": k, "target": t} for k, t in sorted(s)] for sid, s in sweeps.items()}


def _skeleton_steps(g, episode_id: str, ep: dict, policy: dict) -> list[dict]:
    """Everything numeric or structural, computed here. The backend contributes two
    strings per step later (`_authority_for_steps`) and nothing else."""
    method = policy.get("method")
    required_bias = set(policy.get("requiredBiasChecks") or [])
    models = [m for m in ep.get("models") or [] if isinstance(m, str) and g.has(m)]
    bindings = _linchpin_bindings(g, ep)
    varied_obs = _varied_observations(g, ep)

    bias_checks = sorted(
        b for b in (ep.get("biasChecks") or [])
        if isinstance(b, str) and g.has(b) and g.get(b).get("checkType") in required_bias
    )

    steps_meta: list[dict] = []
    for ws_id in ep.get("weightSets") or []:
        if not isinstance(ws_id, str) or not g.has(ws_id):
            log.warning("episode %r names weight set %r, which is not in the graph; "
                       "skipped [M3]", episode_id, ws_id)
            continue
        weights = g.get(ws_id).get("weights") or {}
        measures = sorted(weights)
        alternatives = [a for a in (ep.get("alternatives") or [])
                        if isinstance(a, str) and g.has(a)
                        and g.get(a).get("status") == "evaluated"]
        step_id = _strip_ws_prefix(ws_id)
        evaluator = _select_evaluator(g, episode_id, step_id, models, measures)
        steps_meta.append({"id": step_id, "weightSet": ws_id, "measures": measures,
                           "alternatives": alternatives, "evaluator": evaluator})

    if not steps_meta:
        raise ValidationError(
            [f"episode {episode_id!r} has no weight sets; propose_plan needs at least one "
             f"WeightSet to build a plan step from"]
        )

    sweeps_by_step = _sweeps_by_step(g, steps_meta, bindings, varied_obs)
    return [
        {"id": m["id"], "evaluator": m["evaluator"], "method": method,
         "alternatives": m["alternatives"], "measures": m["measures"],
         "weightSet": m["weightSet"], "sensitivitySweeps": sweeps_by_step[m["id"]],
         "biasChecks": bias_checks}
        for m in steps_meta
    ]


# ---- what the backend is asked ----------------------------------------------------------


def _catalogue_lines() -> str:
    return "\n".join(
        f"- {key}: {entry['requires']}" for key, entry in sorted(AUTHORITY_CATALOGUE.items())
    )


def _step_lines(steps: list[dict]) -> str:
    lines = []
    for s in steps:
        sweep_targets = [sw["target"] for sw in s["sensitivitySweeps"]]
        lines.append(f"- {s['id']}: weightSet={s['weightSet']} measures={s['measures']} "
                     f"sweepTargets={sweep_targets}")
    return "\n".join(lines)


def _user_prompt(steps: list[dict]) -> str:
    # No clock value anywhere in this text: recording keys are computed over the prompt,
    # and a date here would rot the fixture daily.
    return (
        "The evaluation plan's steps are already fixed; you choose no measure, "
        "alternative, weight or evaluator. Steps:\n" + _step_lines(steps) + "\n\n"
        "Authority catalogue (choose exactly one key per step):\n" + _catalogue_lines() +
        "\n\nFor each step return its id, one authorityKey from the catalogue above that "
        "requires this step to exist, and one sentence of rationale for why that citation "
        "fits this step."
    )


def _system_prompt() -> str:
    # [M8] the catalogue and the step list are in the NEXT (user) message, not "above" —
    # this system prompt is sent first.
    return (load_prompt("authority") + "\n\nThe next message lists the plan's steps and "
            "the authority catalogue; you choose one authority key per step from that "
            "catalogue and write one sentence of rationale; you compute nothing.")


def _authority_for_steps(backend, steps: list[dict]) -> dict[str, dict[str, str]]:
    """step id -> {"authorityKey": ..., "rationale": ...}.

    `backend is None`: every step defaults to `DEFAULT_AUTHORITY_KEY` with no rationale. A
    backend response naming an unknown step id is ignored; a step the backend omitted
    defaults the same way. Both are logged, not silently swallowed.
    """
    if backend is None:
        return {s["id"]: {"authorityKey": DEFAULT_AUTHORITY_KEY, "rationale": ""}
                for s in steps}

    resp = backend.complete_json(system=_system_prompt(), user=_user_prompt(steps),
                                 schema=PLAN_SCHEMA)
    known_ids = {s["id"] for s in steps}
    by_id: dict[str, dict[str, str]] = {}
    for entry in resp.get("steps") or []:
        sid = entry.get("id")
        if sid not in known_ids:
            log.warning("backend named authority for unknown step %r; ignored", sid)
            continue
        by_id[sid] = {"authorityKey": entry.get("authorityKey") or DEFAULT_AUTHORITY_KEY,
                      "rationale": entry.get("rationale") or ""}

    out: dict[str, dict[str, str]] = {}
    for s in steps:
        if s["id"] in by_id:
            out[s["id"]] = by_id[s["id"]]
        else:
            log.warning("backend omitted step %r; defaulting authorityKey to %r",
                        s["id"], DEFAULT_AUTHORITY_KEY)
            out[s["id"]] = {"authorityKey": DEFAULT_AUTHORITY_KEY, "rationale": ""}
    return out


# ---- rationale persistence [pre-flight defect 6] -----------------------------------------


def _rationale_id(plan_id: str, step_id: str) -> str:
    return f"rat-{plan_id}-{step_id}"


def _rationale_object(plan_id: str, step_id: str, rationale: str, *, episode_id: str,
                       backend, actor: dict, now: str) -> dict:
    return {
        "id": _rationale_id(plan_id, step_id), "type": "Rationale", "rev": 1,
        "createdBy": actor, "createdAt": now,
        "ingestionProvenance": {"sourceArtifact": episode_id, "locator": f"plan step {step_id}",
                                "extractor": backend.extractor, "extractedAt": now},
        "text": rationale, "author": backend.extractor,
    }


def step_rationale(g, plan_id: str, step_id: str) -> dict | None:
    """The `Rationale` object behind `step_id` of `plan_id`, or None. The link between a
    step and its rationale is this id convention (`rat-{plan_id}-{step_id}`) — `Plan.steps[]`
    has no field to hold a rationale [pre-flight defect 6]."""
    rid = _rationale_id(plan_id, step_id)
    return g.get(rid) if g.has(rid) else None


# ---- plan id, and the "no replacing an approved plan" guard -----------------------------


def _next_plan_id(g, episode_id: str) -> str:
    """Deterministic and never collides with a hand-built plan id such as `pl-cbo`: an
    agent-proposed plan always carries the `pl-{episode}-agent-{n}` shape."""
    prefix = f"pl-{episode_id}-agent-"
    n = 1 + sum(1 for oid in g.ids() if oid.startswith(prefix))
    return f"{prefix}{n}"


def _named_approved_plan(g, ep: dict) -> dict | None:
    """The episode's named Plan, if it exists and its `approvedBy` holds content —
    else `None`. Shared by `_refuse_if_named_plan_is_approved` (below) and
    `author_weight_set`'s own precondition, so the underlying graph fact — "has G2
    already happened for this episode" — is computed exactly once and worded
    differently by each caller, rather than copied."""
    named = ep.get("plan")
    if not isinstance(named, str) or not g.has(named):
        return None
    current = g.get(named)
    return current if is_content(current.get("approvedBy")) else None


def _refuse_if_named_plan_is_approved(g, ep: dict) -> None:
    plan = _named_approved_plan(g, ep)
    if plan is not None:
        raise AuthorityViolation(
            f"episode {ep.get('id')!r} already names plan {plan['id']!r}, and its "
            f"approvedBy holds content: propose_plan refuses to replace an approved "
            f"plan behind G2. Approve a plan the agent proposes fresh, or have a human "
            f"revise {plan['id']!r} first."
        )


# ---- the two public actions --------------------------------------------------------------


def propose_plan(backend, g, episode_id: str, *, actor: dict, now: str,
                 plan_id: str | None = None) -> dict:
    """Write an agent-authored Plan for `episode_id` — no `approvedBy`; every step's
    `authority` cites a doctrine paragraph from `AUTHORITY_CATALOGUE`. `backend` supplies
    only the authority key and rationale sentence per step; every measure, alternative,
    weight set, evaluator and sweep is read from the graph. Returns the stored Plan — the
    same shape `POST /api/session/{s}/episode/{e}/plan` returns.

    Refuses (`AuthorityViolation`, before any write) if the episode already names a plan
    whose `approvedBy` holds content. Refuses (`ValidationError`, before any write) if a
    caller-supplied `plan_id` already exists in the graph — `plan_id` is a public
    parameter the frontend route maps onto, so a caller reusing an existing id is plain API
    misuse, not a contrived state, and it must not silently adopt (or half-write into)
    whatever that id already names [I1].

    Everything is built in memory first and every id it would write is checked against the
    graph before the first `put`: compute, then check, then write — Plan, then its
    Rationale objects, then the episode revision. `Rationale` objects used to be written
    *before* the Plan (the brief's own ordering), on the theory that a Plan's steps could
    someday reference them; nothing ever did, so a Plan `put` failure (a malformed decision-
    class policy, most plausibly) orphaned agent-authored Rationale objects onto whatever
    plan id the episode already named, and `_next_plan_id` — which counts *plans*, not
    rationales, with a given prefix — then re-adopted the same id on retry [I1]. Writing the
    Plan first means a Plan failure leaves nothing behind to orphan.
    """
    if not isinstance(episode_id, str) or not g.has(episode_id):
        raise ValidationError([f"episode {episode_id!r} is not in the graph"])
    ep = g.get(episode_id)
    _refuse_if_named_plan_is_approved(g, ep)
    # [I1] checked before the backend is ever asked anything: a caller-supplied plan_id
    # collision is a pure graph fact, independent of the skeleton or the citations.
    if plan_id is not None and g.has(plan_id):
        raise ValidationError(
            [f"plan id {plan_id!r} already exists in the graph; propose_plan refuses to "
             f"write into an existing object's id — name a different plan_id, or omit it "
             f"to let propose_plan mint a fresh, non-colliding one"]
        )

    policy = _policy_for(g, ep)
    skeleton = _skeleton_steps(g, episode_id, ep, policy)
    citations = _authority_for_steps(backend, skeleton)

    pid = plan_id or _next_plan_id(g, episode_id)

    steps: list[dict] = []
    rationale_objs: list[dict] = []
    for s in skeleton:
        cite = citations[s["id"]]
        entry = AUTHORITY_CATALOGUE.get(cite["authorityKey"],
                                        AUTHORITY_CATALOGUE[DEFAULT_AUTHORITY_KEY])
        steps.append({**s, "authority": {"document": entry["document"],
                                         "paragraph": entry["paragraph"]}})
        rationale_text = (cite.get("rationale") or "").strip()
        # An empty Rationale is worse than none: skip it entirely when there is nothing to
        # say, or when there is no backend to attribute it to.
        if backend is not None and rationale_text:
            rationale_objs.append(_rationale_object(
                pid, s["id"], rationale_text, episode_id=episode_id, backend=backend,
                actor=actor, now=now))

    plan_obj = {
        "id": pid, "type": "Plan", "rev": 1, "createdBy": actor, "createdAt": now,
        "episode": episode_id, "policyBasis": policy["id"], "steps": steps,
        # Explicit empty list, not an absent field: nothing has deviated from this plan yet.
        "deviations": [],
    }

    # Every id this call is about to write, checked before any of them are — a rationale id
    # can only collide if a caller reuses a `plan_id` that some earlier, different
    # elicitation already minted Rationale objects under, but the check costs nothing and
    # makes the all-or-nothing guarantee explicit rather than incidental [I1].
    colliding = [oid for oid in [pid, *(r["id"] for r in rationale_objs)] if g.has(oid)]
    if colliding:
        raise ValidationError(
            [f"propose_plan refuses to write: id(s) already exist in the graph: "
             f"{colliding}"]
        )

    stored_plan = g.put(plan_obj, actor)
    for r in rationale_objs:
        g.put(r, actor)

    current_ep = g.get(episode_id)
    g.put({**current_ep, "rev": current_ep["rev"] + 1, "createdBy": actor, "createdAt": now,
          "plan": pid}, actor)

    return stored_plan


def approve_plan(g, plan_id: str, actor: dict, *, now: str) -> dict:
    """HUMAN action: the only place `Plan.approvedBy` is ever set (G2).

    The explicit check here is for the message, not the enforcement: `Graph.put` and
    `kernel.lifecycle.c_plan_approved` both refuse independently, and `evaluate()` refuses
    again in the kernel [ruling R12].
    """
    if actor.get("actorType") != "human":
        raise AuthorityViolation("only a human may approve a Plan (G2)")
    p = g.get(plan_id)
    return g.put({**p, "rev": p["rev"] + 1, "createdBy": actor, "createdAt": now,
                 "approvedBy": {"actorId": actor["actorId"], "date": now}}, actor)


# ---- weights: the human value judgement propose_plan needs ------------------------------


def _weight_set_id(episode_id: str) -> str:
    """The one `WeightSet` id `author_weight_set` ever writes for `episode_id`.

    Deterministic and per-episode, on purpose: `propose_plan` builds one plan step per
    id in `episode["weightSets"]` (`_skeleton_steps`, above), so a route that minted a
    fresh id on every call would silently grow the plan by one step every time a human
    revised their own weighting, rather than revising the one judgement they keep
    editing. A second `author_weight_set` call for the same episode supersedes this same
    id as a new revision — never a second, competing `WeightSet` — the same convention
    `_rationale_id`'s own comment already establishes for this module (`rat-{plan_id}-
    {step_id}`, "the only link between a step and its rationale"). The frontend's
    Weights panel (`ui/src/components/WeightsPanel.tsx`) computes this exact string to
    read the set back before a human has revised it in the current page load — if this
    convention ever changes, that component's own comment says so and must change with
    it.
    """
    return f"ws-{episode_id}-human"


def _weight_gap_id(weight_set_id: str) -> str:
    """The `InsufficientEvidence` id behind `weight_set_id`'s required `provenance`
    slot — see `author_weight_set`'s docstring for why a gap, not a fabricated
    `Evidence`, is what belongs there."""
    return f"gap-{weight_set_id}"


def author_weight_set(g, episode_id: str, actor: dict, *, now: str, name: str,
                      weights: dict, rationale: str | None = None) -> dict:
    """HUMAN: give `episode_id` the `WeightSet` `propose_plan` needs before it can build
    a step (`_skeleton_steps` above raises `episode {episode_id!r} has no weight sets`
    otherwise) — closing the gap `task-9b-report.md` found: no route anywhere in
    `src/docket/api/` ever created one, so a live elicitation could reach `MODEL_APPROVED`
    and go no further. The ledger's ruling (`.superpowers/sdd/2026-09-05-docket-07-
    frontend/progress.md`, last entry): weights are a human value judgement, not
    something the agent proposes and a human merely accepts.

    `weights` is keyed by the episode's *objective* ids (`episode["objectives"]`), not
    by measure ids — a freshly elicited episode (`agent.elicit`) carries Objectives and
    no Measures at all yet [pre-flight: `elicit()`'s own docstring, "produces no
    Observation, WeightSet..."], so objectives are the only thing there is to weigh this
    early. Validated by `kernel.evaluate.check_weights` — the exact rule
    `evaluate_step` applies to a plan step's weights against its measures — called here
    against the episode's objectives instead: every objective present exactly once, no
    extras, non-negative finite reals, summing to 1 within the kernel's own tolerance.
    One rule, reused; this function keeps no second copy of it, and a caller reading the
    422 sees `check_weights`'s own wording (it still says "measures" even though the ids
    are objectives — see that function's docstring for why the wording is not forked
    per caller).

    `method` is always `"stated"` (`WeightSet.method`'s enum: swing/stated/equal/
    derived) — a human typing numbers directly, with no elicitation or derivation, is
    exactly what "stated" names. `provenance` (required, `slot: true`) is a `$gap`
    naming a fresh `InsufficientEvidence`, not a fabricated `Evidence` object: there is
    no source document behind a number a human just typed, and inventing a pointer/
    classification/scopeOfValidity to satisfy `Evidence`'s schema would be exactly the
    "PhantomFill" `InsufficientEvidence`'s own doc comment exists to refuse. The gap
    carries `confirmedBy` immediately, self-confirmed by the same human at the same
    `now` — using this route at all is the acknowledgment that no evidence backs the
    values, so there is nothing left for a later G1 pass to confirm about it.

    Refuses (`ValidationError`) before G2: `episode["lifecycleState"]` must be `DRAFT`
    or `MODEL_APPROVED` — the two states `propose_plan` itself can still be called from
    (it has no lifecycle precondition of its own beyond "not already an approved plan").
    Refuses (`AuthorityViolation`) if the episode already names an approved Plan — the
    same graph fact `propose_plan`'s own `_refuse_if_named_plan_is_approved` derives,
    via the shared `_named_approved_plan` — changing the weight basis underneath an
    approved plan is exactly what G2 exists to prevent, so this reuses that check rather
    than inventing a new one.

    One `WeightSet` per episode, at `_weight_set_id(episode_id)`: the first call writes
    `rev: 1` and appends the id to `episode["weightSets"]`; every later call on the same
    episode supersedes it as a new revision of the *same* id (append-only, `rev + 1`) —
    never a second entry in `weightSets`, which would otherwise make `propose_plan`
    build one plan step per revision instead of one step for the one judgement being
    revised.

    Returns the stored `WeightSet`.
    """
    _human_only(actor, "author_weight_set")
    if not isinstance(episode_id, str) or not g.has(episode_id):
        raise ValidationError([f"episode {episode_id!r} is not in the graph"])
    ep = g.get(episode_id)
    state = ep.get("lifecycleState")
    if state not in ("DRAFT", "MODEL_APPROVED"):
        raise ValidationError(
            [f"episode {episode_id!r} is at lifecycleState {state!r}; weights may only "
             f"be authored at DRAFT or MODEL_APPROVED, before a plan is proposed and "
             f"approved (G2)"]
        )
    approved = _named_approved_plan(g, ep)
    if approved is not None:
        raise AuthorityViolation(
            f"episode {episode_id!r} already names plan {approved['id']!r}, and its "
            f"approvedBy holds content: author_weight_set refuses to change the weight "
            f"basis behind G2 once a plan is approved."
        )
    if not isinstance(name, str) or not name.strip():
        raise ValidationError(["author_weight_set needs a name"])

    objectives = [o for o in (ep.get("objectives") or []) if isinstance(o, str)]
    check_weights(weights, objectives)

    ws_id = _weight_set_id(episode_id)
    gap_id = _weight_gap_id(ws_id)
    existing = g.get(ws_id) if g.has(ws_id) else None
    rev = existing["rev"] + 1 if existing is not None else 1

    why_not_found = (
        rationale.strip() if isinstance(rationale, str) and rationale.strip()
        else "the operator authored these weights directly (method: stated) and cited "
             "no external document or dataset"
    )
    existing_gap = g.get(gap_id) if g.has(gap_id) else None
    gap_obj = {
        "id": gap_id, "type": "InsufficientEvidence",
        "rev": (existing_gap["rev"] + 1) if existing_gap is not None else 1,
        "createdBy": actor, "createdAt": now,
        "sought": f"a cited document or dataset behind WeightSet {ws_id!r}'s weights",
        "whereLookedFor": ["the rationale the operator supplied when authoring these weights"],
        "whyNotFound": why_not_found,
        "confirmedBy": {"actorId": actor["actorId"], "date": now},
        "impact": "informational",
        "indicatorsThatWouldResolve": [
            "a cited document or expert-elicitation record backing these specific "
            "weight values"
        ],
    }
    g.put(gap_obj, actor)

    ws_obj = {
        "id": ws_id, "type": "WeightSet", "rev": rev, "createdBy": actor, "createdAt": now,
        "name": name, "method": "stated", "weights": weights,
        "provenance": {"$gap": gap_id},
    }
    stored = g.put(ws_obj, actor)

    if ws_id not in (ep.get("weightSets") or []):
        current_ep = g.get(episode_id)
        g.put({**current_ep, "rev": current_ep["rev"] + 1, "createdBy": actor,
              "createdAt": now,
              "weightSets": [*(current_ep.get("weightSets") or []), ws_id]}, actor)

    return stored
