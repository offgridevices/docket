"""PROV-JSON export (design §6.3). Pure; no wall clock; deterministic key order.

The shape is PROV-JSON: one bundle, keyed `pkg:{episode_id}-{rendering}` (review round
1, I3 — the bundle id must not collide between the two renderings, which are two
different documents), holding `entity`/`activity`/`agent` dictionaries and the five
relations this record actually has evidence for (`used`, `wasGeneratedBy`,
`wasAttributedTo`, `wasAssociatedWith`, `wasInvalidatedBy`). Relation ids are built from
the objects they relate rather than a counter, so the same graph always produces the
same relation id — required for byte-identity across two calls and across a save/load
round trip.

**Resolvable as PROV, not merely PROV-shaped (review round 1, I2).** Per W3C PROV-DM
§5.7.5 ("Namespaces and Identifiers"), a `default` namespace declaration is what every
un-prefixed qualified name resolves against, and a bound prefix must be declared before
it is used. `prefix` here declares `docket` (the type/attribute vocabulary), `default`
(so an un-prefixed local part still resolves) and `pkg` (the bundle's own local
namespace) — and every agent id is a single-prefix qualified name
(`docket:agent-<type>-<slugged-id>`), not the two-colon, slash-bearing string an actor
id like `docket-kernel/0.1.0` would otherwise produce.

Every relation id and every dict key is sorted by construction (`sorted(reach)`,
`sorted(...)` loops below) so `canonical_json`'s own `sort_keys=True` is redundant but
never load-bearing on its own: this module never relies on Python's dict insertion
order to produce a stable result.

**Deviation from the task brief's mapping table:** `DecisionPackage` is not an entity
type here, though the mapping table names it alongside Evidence/Result/Claim. Kernel
C2 (`tests/kernel/test_render.py`) requires two consecutive `build_package` calls on an
unchanged record to produce byte-identical text, and `render.py`'s own
`_content_snapshot` already excludes `DecisionPackage` from the graph snapshot hash for
exactly this reason — a rendering artefact is not part of the record it renders.
Including it here would make this bundle (one of the six exports the Machine annex
hashes into a *new* package's text) depend on how many packages already sit in the
graph, breaking C2 the moment one build's package lands before the next build runs
(review round 1 confirmed this by monkeypatching the pre-fix behaviour back in and
reproducing the break). What is genuinely lost by the exclusion is smaller than that
might suggest: not the package, but the `wasGeneratedBy` edges from runs to Results,
which have nothing to do with the package and are added below (I1).
"""

from __future__ import annotations

import re

from docket import KERNEL_VERSION
from docket.exports._util import obj, reachable_objects, ref_ids, slug
from docket.kernel.render import _cite_withheld_level, evidence_title
from docket.kernel.scope import check_scope
from docket.objects import is_content
from docket.store import Graph

PROV_NS = "https://docket.dev/ns#"
_BARE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _agent_key(actor: object) -> str | None:
    """A single-prefix PROV qualified name for `actor` — `docket:agent-<type>-<slugged
    id>` — never the old `agent:<type>:<id>` shape, which was two colons and (for the
    kernel actor, `docket-kernel/0.1.0`) a slash: not an NCName local part (I2)."""
    if not isinstance(actor, dict):
        return None
    actor_type, actor_id = actor.get("actorType"), actor.get("actorId")
    if not isinstance(actor_type, str) or not isinstance(actor_id, str):
        return None
    return f"docket:agent-{actor_type}-{slug(actor_id)}"


def _add_agent(agents: dict[str, dict], actor: object) -> str | None:
    key = _agent_key(actor)
    if key is None:
        return None
    agents[key] = {"prov:type": f"docket:{actor['actorType']}", "docket:actorId": actor["actorId"]}
    return key


def _at_time(value: object) -> object:
    """Normalise a bare `YYYY-MM-DD` date to `...T00:00:00Z` (M2): `prov:atTime` wants
    an `xsd:dateTime`, and `episode["asOf"]` (the only source `wasInvalidatedBy` has for
    it) may be stored as a bare date. Anything else — already a full timestamp, or not
    a string at all — passes through unchanged."""
    if isinstance(value, str) and _BARE_DATE.match(value):
        return f"{value}T00:00:00Z"
    return value


def _obs_by_alt(g: Graph, ep: dict) -> dict[str, list[dict]]:
    """The same `alternative -> [Observation, ...]` grouping `render.py` builds, so the
    private `_cite_withheld_level` this module borrows behaves identically here."""
    out: dict[str, list[dict]] = {}
    for oid in ep.get("observations") or []:
        o = obj(g, oid)
        if o is not None:
            out.setdefault(o.get("alternative"), []).append(o)
    return out


def _evidence_used_by(g: Graph, run: dict, episode: dict) -> list[str]:
    """Evidence ids a run consumed, via the run's *sealed* observation list.

    `EvaluationRun.parameterBindings.observationIds` is the stored run->observation edge
    (`evaluate.py` writes it; `flip._run_inputs` reads it the same way). Re-deriving the
    set from `episode["observations"]` would ignore the seal and could name observations
    the run never used — pre-flight defect D17. `episode["observations"]` is used only
    as the fallback for a pre-kernel-0.1.0 run that has no sealed list at all, exactly as
    `flip._run_inputs` falls back.
    """
    pb = run.get("parameterBindings") or {}
    obs_ids = pb.get("observationIds")
    if not isinstance(obs_ids, list):
        obs_ids = list(episode.get("observations") or [])
    out: set[str] = set()
    for oid in obs_ids:
        if not isinstance(oid, str) or not g.has(oid):
            continue
        ev = g.get(oid).get("evidence")
        if is_content(ev) and isinstance(ev, str) and g.has(ev):
            out.add(ev)
    return sorted(out)


def _invalidations(g: Graph, episode_id: str) -> list[str]:
    """Evidence whose scope lapsed, taken from the kernel's own finding.

    `check_scope` already does the validUntil-vs-asOf arithmetic (`kernel/scope.py`,
    rule `scope-lapsed`), and `Evidence.scopeOfValidity` is a P3 slot that may be a gap
    marker. Re-walking the path here would duplicate the arithmetic and drift from it
    (pre-flight defect D16).
    """
    return sorted({f.objects[0] for f in check_scope(g, episode_id)
                   if f.rule == "scope-lapsed" and f.objects})


def to_prov(g: Graph, episode_id: str, *, rendering: str) -> dict:
    """PROV-JSON for `episode_id`'s reachable record (design §6.3, mapping table 1).

    `rendering="unclassified"` withholds the same things `render.py` withholds and
    nothing else: an Evidence entity's title becomes `[withheld: <level>]` when its
    metadata classification is not visible (`render.evidence_title`; review round 2,
    I4 — the same helper the package's own evidence register, GSN's `solutions` and
    the RTVM's `evidence_title` column now share), and a Result entity's
    `docket:value` is dropped the same way `render.py`'s evaluation-results table
    taints an aggregate (`_cite_withheld_level`, reused rather than re-derived — same
    rule, one definition).
    """
    ep = obj(g, episode_id) or {}
    obs_by_alt = _obs_by_alt(g, ep)

    entities: dict[str, dict] = {}
    agents: dict[str, dict] = {}
    activities: dict[str, dict] = {}
    used: dict[str, dict] = {}
    was_generated_by: dict[str, dict] = {}
    was_attributed_to: dict[str, dict] = {}
    was_associated_with: dict[str, dict] = {}
    was_invalidated_by: dict[str, dict] = {}

    def add_entity(oid: str, o: dict, extra: dict) -> None:
        entities[oid] = {"prov:type": f"docket:{o.get('type')}", **extra}
        akey = _add_agent(agents, o.get("createdBy"))
        if akey is not None:
            was_attributed_to[f"_:attr-{oid}"] = {"prov:entity": oid, "prov:agent": akey}

    for oid, o in reachable_objects(g, episode_id, "Evidence"):
        # I4: `evidence_title` — the single, metadataLevel-gated definition of "is
        # this evidence's title visible" the package, GSN and RTVM now share too,
        # replacing this module's own `_withheld` (value-classification) check.
        add_entity(oid, o, {"docket:title": evidence_title(g, o, rendering)})

    for oid, o in reachable_objects(g, episode_id, "Claim"):
        add_entity(oid, o, {"docket:text": o.get("text")})

    for oid, o in reachable_objects(g, episode_id, "Result"):
        level = _cite_withheld_level(g, oid, rendering, obs_by_alt)
        value = f"[withheld: {level}]" if level else o.get("value")
        add_entity(oid, o, {"docket:value": value})

    plan_ids: set[str] = set()
    for oid, o in reachable_objects(g, episode_id, "Plan"):
        # M1: also `prov:Plan`, so a consumer following `wasAssociatedWith/prov:plan`
        # can tell the target is a plan without knowing docket's own type vocabulary.
        add_entity(oid, o, {"prov:type": ["docket:Plan", "prov:Plan"]})
        plan_ids.add(oid)

    # Deliberately **not** an entity here: `DecisionPackage`, unlike the mapping table's
    # literal list. A `DecisionPackage` is a rendering artefact, not part of the record
    # (the same reasoning `render._content_snapshot` excludes it from the graph snapshot
    # hash on) — including it would make `to_prov`'s own output depend on how many
    # packages happen to sit in the graph already, and this bundle is itself one of the
    # exports the Machine annex hashes into a *new* package's text. Two consecutive
    # `build_package` calls on an unchanged record must produce byte-identical text
    # (kernel's own C2 guarantee); citing `g.all("DecisionPackage")` here would break it
    # the moment the first call's package lands in the graph before the second call runs.

    for oid, o in reachable_objects(g, episode_id, "EvaluationRun"):
        sealed_at = o.get("sealedAt")
        # objects.yaml's EvaluationRun has exactly one `sealedAt`, no start/end pair —
        # emitting a zero-duration activity (start == end) is honest; inventing a start
        # time the schema does not record would not be (design mapping table 1).
        activities[oid] = {
            "prov:type": "docket:EvaluationRun",
            "prov:startTime": sealed_at, "prov:endTime": sealed_at,
        }
        if o.get("sealedBy") == "kernel":
            kernel_actor = {
                "actorType": "kernel", "actorId": f"docket-kernel/{KERNEL_VERSION}",
            }
            akey = _add_agent(agents, kernel_actor)
            assoc: dict = {"prov:activity": oid, "prov:agent": akey}
            plan_id = o.get("plan")
            if isinstance(plan_id, str) and plan_id in plan_ids:
                assoc["prov:plan"] = plan_id
            was_associated_with[f"_:assoc-{oid}"] = assoc
        for ev_id in _evidence_used_by(g, o, ep):
            used[f"_:used-{oid}-{ev_id}"] = {"prov:activity": oid, "prov:entity": ev_id}
        # I1: the generation edge — free from the run's own stored `outputs` field.
        # `res_id in entities` both resolves the reference and skips a Result the
        # earlier Result loop did not add (an `outputs` entry naming something else,
        # or a dangling id in a hand-edited store).
        #
        # M2 (review round 2): keyed on `(result, run)`, not the Result id alone — a
        # bare `_:gen-{res_id}` let two runs both naming the same output in `outputs`
        # silently collapse to one generation edge, with whichever run id sorted
        # highest winning by accident of dict-key collision rather than by any
        # modelled choice.
        for res_id in ref_ids(o.get("outputs")):
            if res_id in entities:
                was_generated_by[f"_:gen-{res_id}-{oid}"] = {
                    "prov:entity": res_id, "prov:activity": oid,
                }

    as_of = ep.get("asOf")
    for ev_id in _invalidations(g, episode_id):
        act_id = f"scope-lapse-{ev_id}"
        activities[act_id] = {"prov:type": "docket:ScopeLapse"}
        was_invalidated_by[f"_:inv-{ev_id}"] = {
            "prov:entity": ev_id, "prov:activity": act_id,
            # The only defensible instant for a lapse the kernel detects by comparison,
            # not by a recorded event time — `scope-lapsed` reports validUntil < asOf,
            # and asOf is the episode's own declared "now" (mapping table 1).
            # `_at_time` (M2) normalises a bare date to an `xsd:dateTime`.
            "prov:atTime": _at_time(as_of),
        }

    bundle: dict[str, dict] = {"entity": entities, "agent": agents, "activity": activities}
    if used:
        bundle["used"] = used
    if was_generated_by:
        bundle["wasGeneratedBy"] = was_generated_by
    if was_attributed_to:
        bundle["wasAttributedTo"] = was_attributed_to
    if was_associated_with:
        bundle["wasAssociatedWith"] = was_associated_with
    if was_invalidated_by:
        bundle["wasInvalidatedBy"] = was_invalidated_by

    prefix = {"docket": PROV_NS, "default": PROV_NS, "pkg": f"{PROV_NS}pkg/"}
    return {"prefix": prefix, "bundle": {f"pkg:{episode_id}-{rendering}": bundle}}


__all__ = ["to_prov"]
