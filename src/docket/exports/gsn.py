"""GSN-v3-*shaped* JSON export (design §6.3, mapping table 2).

**Naming, load-bearing:** GSN v3 (the Assurance Case Working Group's Goal Structuring
Notation) defines a *notation*, not a JSON interchange format, so this module produces
docket's own JSON shape inspired by its Core, Dialectic and Modular extensions. Always
say "GSN-v3-shaped JSON" or "a GSN v3 rendering" in code, docs and the proposal — never
a phrase that implies this output *is* the standard's own interchange format.

**Sourced against the standard (review round 1, I6) — GSN Community Standard v3, SCSC
Assurance Case Working Group, May 2021, `library/standards/scsc-141c-gsn-community-
standard-v3.pdf`, read directly, not carried from the first draft's "unverified"
placeholder:**

- **§1:4.2.1 (p. 32), Modular Extension — Argument View.** The argument-view elements
  are "Away Goal, Away Solution, Away Context, Away Assumption, Away Justification,
  Module Reference, Contract Reference." Evidence maps to `solutions` in this export
  (Core GSN's Solution), so its away form is **Away Solution**, not "Away Goal" — the
  first draft applied the wrong away-element name. `contract: {visibleAt, valueAt}` is
  docket's own annotation of *when* a module's contents are visible, not an
  implementation of GSN's own "Contract Reference" element, which this export does not
  attempt.
- **§1:6.2.2–1:6.2.4 (p. 50), Dialectic Extension — Notation.** "GSN defines dialectic
  uses of the following core elements: Goal, Solution. An additional dialectic specific
  relationship is provided: Challenges. GSN defines a status that may be assigned to
  elements and relationships: Defeated." Table 1:6-2 (p. 51) further defines Challenges
  as "a relationship between a source element (the entity responsible for making the
  challenge) and a target element," with permitted connections "goal-to-any element,
  solution-to-any element, goal-to-any relationship, solution-to-any relationship" — the
  *source* must be a Goal or a Solution. So `defeated` is a **status list** here
  (`{"element": id, "defeated": true, "by": exclusion_id}`), not a list of defeated
  nodes with an embedded challenge, and `challenge` is a real `{from, to}` edge whose
  `from` is always a `solutions`-keyed (Evidence) or `goals`-keyed (Claim) id — never an
  `Exclusion`'s bare `{who, role, date}` authority object, which is not itself a Goal or
  a Solution and so cannot be the source of a Challenges relationship. (Docket's own
  `Exclusion` records — who defeated an element and why — are named on the `defeated`
  status entry's `by` field instead, where they belong: they are the *reason*, not a
  challenging Goal or Solution.)

Every other element name (`goals`, `solutions`, `contexts`, `strategies`,
`justifications`) matches Core GSN's own vocabulary (Goal, Solution, Context, Strategy,
Justification).

**Review round 2 — three further fixes, none of them naming.**

- **I1.** `dialectic.challenge[]` is now `{"from", "to", "rule"}` — never the
  `ReusePastPurpose` finding's own free-text `message`, which interpolates
  `scopeOfValidity.builtToAnswer`, a field `render.metadata_withheld` gates
  everywhere else this document prints it. `from`/`to` are ids into `solutions`/
  `goals`, already gated the same way the package gates them.
- **I3.** `dialectic.defeated[].element` names only an id this document itself
  declares (a key of `goals`/`solutions`/`contexts`/`assumptions`/`justifications`/
  `strategies`); an Exclusion whose target does not resolve to one goes into the
  sibling `unresolvedTargets` list instead — a synthetic `target-<slug>` id that
  names no element in the document is not GSN's Defeated status, whatever it is
  called.
- **M3.** A Claim whose `supportedBy` is a `{"$gap": ...}` marker is exported with
  `undeveloped: true` (and the gap's id) on its `goals` entry — SCSC-141C Table
  1:2-1's Undeveloped element decorator, "a claim which is intentionally left
  undeveloped."
"""

from __future__ import annotations

from docket.exports._util import obj, reachable_objects
from docket.kernel.render import evidence_title
from docket.kernel.scope import check_scope
from docket.objects import is_gap_ref
from docket.store import Graph


def _scope_contexts(ch: dict) -> dict[str, dict]:
    scope = ch.get("scope") if isinstance(ch.get("scope"), dict) else {}
    out: dict[str, dict] = {}
    for kind in ("included", "excluded"):
        for i, text in enumerate(scope.get(kind) or []):
            if isinstance(text, str):
                out[f"ctx-{kind}-{i}"] = {"statement": text, "source": f"charter.scope.{kind}"}
    return out


def to_gsn(g: Graph, episode_id: str, *, rendering: str) -> dict:
    ep = obj(g, episode_id) or {}
    ch = obj(g, ep.get("charter")) or {}

    goals: dict[str, dict] = {}
    for cid, c in reachable_objects(g, episode_id, "Claim"):
        level = (c.get("assessableAt") or {}).get("level") if isinstance(
            c.get("assessableAt"), dict
        ) else None
        goal: dict = {"text": c.get("text"), "section": c.get("section"), "level": level}
        sb = c.get("supportedBy")
        if is_gap_ref(sb):
            # M3: SCSC-141C Table 1:2-1's Undeveloped element decorator — "a claim
            # which is intentionally left undeveloped" — for a Claim whose only
            # support is a recorded gap. Before this, a `{"$gap": ...}`-backed
            # `supportedBy` simply produced zero `supportedBy` edges below, making a
            # gap-backed Goal indistinguishable from a fully-supported one with no
            # edge of its own reason to be there. No demo graph exercises this today
            # (a synthetic-graph test covers it).
            goal["undeveloped"] = True
            goal["gap"] = sb["$gap"]
        goals[cid] = goal

    solutions: dict[str, dict] = {}
    for eid, e in reachable_objects(g, episode_id, "Evidence"):
        # I4: `evidence_title` — the single, metadataLevel-gated definition of "is
        # this evidence's title visible" every one of the package, PROV, GSN and RTVM
        # now shares, replacing this module's own `_withheld` (value-classification)
        # check, which could disagree with the package about the very same item.
        solutions[eid] = {
            "title": evidence_title(g, e, rendering), "evidenceType": e.get("evidenceType"),
        }

    contexts = _scope_contexts(ch)
    for sid, s in reachable_objects(g, episode_id, "Scenario"):
        contexts[sid] = {"name": s.get("name"), "description": s.get("description")}

    assumptions: dict[str, dict] = {}
    for aid, a in reachable_objects(g, episode_id, "Assumption"):
        assumptions[aid] = {"statement": a.get("statement"), "linchpin": bool(a.get("linchpin"))}

    justifications: dict[str, dict] = {}
    for rid, r in reachable_objects(g, episode_id, "Rationale"):
        justifications[rid] = {"text": r.get("text"), "author": r.get("author")}

    # M6: keyed `plan_id:step_id`, not the bare step id — two Plans in one graph (or
    # one episode across a refresh) can reuse a step id like "primary", and a bare key
    # would silently let the second overwrite the first.
    strategies: dict[str, dict] = {}
    for pid, p in reachable_objects(g, episode_id, "Plan"):
        for step in p.get("steps") or []:
            if not isinstance(step, dict) or not isinstance(step.get("id"), str):
                continue
            measures = step.get("measures") if isinstance(step.get("measures"), list) else []
            strategies[f"{pid}:{step['id']}"] = {
                "label": f"{step.get('method')} over {len(measures)} measures",
                "plan": pid,
            }

    supported_by: list[dict] = []
    for cid, c in reachable_objects(g, episode_id, "Claim"):
        for entry in c.get("supportedBy") or []:
            if isinstance(entry, dict) and isinstance(entry.get("evidence"), str):
                supported_by.append({"from": cid, "to": entry["evidence"]})
        run = obj(g, c.get("derivedFrom"))
        strategy_id = (
            f"{run.get('plan')}:{run.get('step')}"
            if run is not None and isinstance(run.get("plan"), str)
            and isinstance(run.get("step"), str) else None
        )
        if strategy_id is not None and strategy_id in strategies:
            supported_by.append({"from": strategy_id, "to": cid})
    supported_by = sorted({(e["from"], e["to"]) for e in supported_by})
    supported_by = [{"from": f, "to": t} for f, t in supported_by]

    # I7: dropped, not derived. The first draft's `inContextOf` was the full Cartesian
    # product of goals × (contexts + assumptions) — Demo A alone asserted 95 edges this
    # way, none of them backed by anything a Claim actually references. The honest
    # alternative the review offered — deriving per-claim context from what the claim
    # itself reaches (`g.reachable_from(claim_id, reverse=False)`) — was checked and
    # rejected too: `Claim` has no schema field that reaches an `Assumption` or a
    # Charter scope item at all (`objects.yaml`'s `Claim` fields are `text`,
    # `questionClass`, `section`, `assessableAt`, `supportedBy`, `derivedFrom`,
    # `resultRef`, `addresses`, `mandateElements` — none of them a path to `contexts`/
    # `assumptions`), so a reachability-based version would be correct but permanently
    # empty, which reads as "checked, found none" rather than "this record does not
    # carry that edge at all." This export therefore does not state an `inContextOf`
    # relationship anywhere; `contexts`/`assumptions` are still exported as GSN nodes,
    # just not linked to any particular goal.

    # I3: a `defeated[].element` may name only an id this document itself declares —
    # a key of `goals`, `solutions`, `contexts`, `assumptions`, `justifications` or
    # `strategies`. The first draft minted a synthetic `target-<slug>` id for a
    # label-only Exclusion target and asserted a Defeated *status* against it — an id
    # this document never declares as an element, so every reader following it found
    # nothing. An Exclusion whose target does not resolve to a declared node is not a
    # GSN Defeated status at all (SCSC-141C's Defeated decorates an *element*); it is
    # docket's own scope decision, named honestly in `unresolvedTargets` instead of
    # dressed up as one.
    declared_ids = (
        set(goals) | set(solutions) | set(contexts) | set(assumptions)
        | set(justifications) | set(strategies)
    )
    defeated: list[dict] = []
    unresolved_targets: list[dict] = []
    for xid, x in reachable_objects(g, episode_id, "Exclusion"):
        target = x.get("target") if isinstance(x.get("target"), dict) else {}
        target_id = target.get("id") if isinstance(target.get("id"), str) else None
        if target_id is not None and target_id in declared_ids:
            defeated.append({"element": target_id, "defeated": True, "by": xid})
        else:
            unresolved_targets.append(
                {"label": target_id if target_id is not None else target.get("label"),
                 "by": xid}
            )
    defeated.sort(key=lambda d: (d["element"], d["by"]))
    unresolved_targets.sort(key=lambda d: (str(d["label"]), d["by"]))

    # I1: a structured `{from, to, rule}` fact, never `f.message` verbatim. The
    # `ReusePastPurpose` finding's own message (`kernel/scope.py`) interpolates
    # `scopeOfValidity.builtToAnswer` — a field `metadata_withheld` gates everywhere
    # else this document prints it (the evidence register, RTVM) — so carrying it
    # through unchanged leaked it at the unclassified rendering regardless of whether
    # `solutions[eid]["title"]` was itself withheld (review round 2, I1: the same
    # class of leak C1's fix closed in `docket.exports.rtvm`, surviving here because
    # this export never went through that fix). `from`/`to` are ids into `solutions`/
    # `goals`, which are already gated the same way the package gates them — a reader
    # resolving either one sees exactly what the package would show, never more.
    challenge: list[dict] = []
    for f in check_scope(g, episode_id):
        if f.rule == "ReusePastPurpose" and len(f.objects) >= 2:
            claim_id, evidence_id = f.objects[0], f.objects[1]
            # Table 1:6-2: the Challenges source must be a Goal or a Solution. The
            # reused Evidence (a Solution) is what challenges whether the Claim (a
            # Goal) can rest on it outside the scope it was built to answer.
            challenge.append({"from": evidence_id, "to": claim_id, "rule": f.rule})
    challenge.sort(key=lambda c: (c["from"], c["to"]))

    away_solution: dict[str, dict] = {}
    for eid, e in reachable_objects(g, episode_id, "Evidence"):
        cls = e.get("classification") if isinstance(e.get("classification"), dict) else {}
        level = cls.get("level")
        if isinstance(level, str) and level != "U":
            away_solution[eid] = {
                "contract": {"visibleAt": cls.get("metadataLevel"), "valueAt": level},
            }

    return {
        "goals": goals,
        "solutions": solutions,
        "contexts": contexts,
        "assumptions": assumptions,
        "justifications": justifications,
        "strategies": strategies,
        "supportedBy": supported_by,
        "dialectic": {"defeated": defeated, "challenge": challenge},
        # I3: sibling to `dialectic`, not nested inside it — an Exclusion whose target
        # does not resolve to a declared node is not itself a GSN Dialectic status;
        # nesting it under `dialectic` would claim otherwise.
        "unresolvedTargets": unresolved_targets,
        "modular": {"awaySolution": away_solution},
    }


__all__ = ["to_gsn"]
