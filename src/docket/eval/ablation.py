"""Ablations (design §9.2 step 5): what a readiness reading loses when a mechanism is
turned off, an Exclusion object is dropped, or an InsufficientEvidence object is
collapsed.

This module never reads or builds Demo B itself — `demos/ablation/run.py` supplies the
graph (`build_fn`) and the reading (`score_fn`); this module only transforms graphs and
compares readings. That separation is what lets `run_ablations` be tested against any
episode set, not only Demo B's.

**Transforms never mutate their input.** `strip_exclusions` and `collapse_gaps` each
work on a `copy.deepcopy` of the graph they are given, and `run_ablations` deep-copies
its `build_fn()` result once per variant, including the "baseline" variant itself — no
variant is special-cased to run against the shared original. `run_ablations` asserts the
graph `build_fn()` returned is byte-for-bit unchanged (snapshot hash and log) after every
variant has run.

**Why the transforms write into `Graph._latest`/`_history` directly instead of calling
`Graph.put()`.** `put()` enforces `docket.schema.validate_object` as a precondition for
every write, and it enforces the agent-authority boundary. Both are the right rule for a
process writing a real record — and the wrong rule here, because the entire point of
`collapse_gaps` is to produce the "hand-edited store" every kernel rule's docstring
already promises to tolerate: a slot whose gap marker has been overwritten with an empty
value the schema does not accept, deliberately, to see whether `rule_schema` reports it
(ruling R9) rather than to have the write refused before it happens. `docket.kernel.
validate`'s own `rule_authority` docstring names this shape directly: "a graph assembled
in memory without put". This module is that assembly.

**Requiredness and the schema-valid empty come from the catalogue, not from re-deriving
JSON Schema.** `docket.objects._spec_for` is the same per-field spec `iter_slots`/
`iter_refs` walk, and every field's own `"required"` flag there is exactly the schema
generator's source of truth (`docket/schema/generate.py` compiles it into the JSON
Schema's `required` arrays). Reusing it means this module can never disagree with the
schema about which fields are required.
"""

from __future__ import annotations

import copy as _copylib
from collections.abc import Callable, Sequence
from contextlib import ExitStack, contextmanager

from docket.objects import _spec_for, iter_refs
from docket.schema import validate_object
from docket.store import Graph

__all__ = [
    "strip_exclusions",
    "collapse_gaps",
    "scope_off",
    "silence_off",
    "run_ablations",
]


# ---- graph surgery, bypassing put() on purpose (see module docstring) ----------------


def _copy_graph(g: Graph) -> Graph:
    """A fully independent copy: new dicts and lists throughout, safe to mutate."""
    return _copylib.deepcopy(g)


def _replace(g: Graph, obj: dict) -> None:
    """Overwrite `obj`'s current revision in place. Bypasses `put()`'s schema and
    authority gate — see the module docstring for why that is the point, not a bug."""
    oid = obj["id"]
    g._latest[oid] = obj
    g._history.setdefault(oid, {})[obj.get("rev", 1)] = obj
    g._reverse = None  # the reverse-reference index is now stale; force a recompute


def _drop(g: Graph, oid: str) -> None:
    """Remove an object from the graph's current state entirely. Its log entry (if any)
    is left alone: `rule_log_chain` only checks the log's own internal chain, never that
    a log entry's object still exists, so a dropped object leaves no spurious finding —
    exactly the "hand-edited store" tolerance the structural rules already promise."""
    g._latest.pop(oid, None)
    g._reverse = None


# ---- path-addressed field lookup, mirroring objects.iter_slots/iter_refs -------------


def _path_key(path: str) -> tuple:
    return tuple(int(p) if p.isdigit() else p for p in path.split("/"))


def _container_at(obj, parts: list[str]):
    cur = obj
    for part in parts[:-1]:
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur, parts[-1]


def _set_at(obj: dict, path: str, value: object) -> None:
    container, last = _container_at(obj, path.split("/"))
    if isinstance(container, list):
        container[int(last)] = value
    else:
        container[last] = value


def _del_at(obj: dict, path: str) -> None:
    container, last = _container_at(obj, path.split("/"))
    if isinstance(container, list):
        del container[int(last)]
    else:
        del container[last]


def _field_spec_at(obj: dict, path: str) -> dict:
    """The catalogue field spec that produced the value at `path`, walking exactly the
    route `objects.iter_slots`/`iter_refs` built it by: a property name at each object
    hop, a numeric index at each array hop.

    An unresolvable hop (a shape this walker does not follow, e.g. a polymorphic
    `oneOfTypes` field) returns `{}`. `_is_required` reads that as "required" and
    `_schema_empty_for` falls back to `""` — the safe direction: guessing wrong here
    only costs a `schema-forced` label instead of `empty` (`_drop_type` re-validates the
    real object with `validate_object` either way), never a silent deletion of a field
    the catalogue does describe.
    """
    fs: dict = {"properties": _spec_for(obj.get("type"), obj)}
    for part in path.split("/"):
        if part.isdigit():
            fs = fs.get("items") or {}
        else:
            props = fs.get("properties") or {}
            target = props.get(part)
            if target is None:
                return {}
            fs = target
        if isinstance(fs, str):
            fs = {"type": fs}
        if not isinstance(fs, dict):
            return {}
    return fs


def _is_required(fs: dict) -> bool:
    return True if not fs else bool(fs.get("required"))


def _schema_empty_for(fs: dict) -> object:
    """The schema-valid empty for this slot's declared shape: `""` for a ref (a ref *is*
    a string, constrained to the id pattern, which an empty string never matches — so a
    ref substitution is always later found `schema-forced`, per DECISION NEEDED 2), `[]`
    for an array, `{}` for an object, `0`/`False` for a number/boolean, `""` otherwise
    (including an unresolved spec — the `_field_spec_at` fallback)."""
    if "ref" in fs:
        return ""
    t = fs.get("type")
    if t == "array":
        return []
    if t == "object":
        return {}
    if t in ("integer", "number"):
        return 0
    if t == "boolean":
        return False
    return ""


def _err_at(errs: list[str], path: str) -> bool:
    """Whether any `validate_object` error is reported at `path` or beneath it."""
    for e in errs:
        loc = e.split(":", 1)[0]
        if loc == path or loc.startswith(path + "/") or (loc and path.startswith(loc + "/")):
            return True
    return False


# ---- the two transforms ---------------------------------------------------------------


def _drop_type(g: Graph, drop_type: str) -> tuple[Graph, list[dict]]:
    """Drop every object of `drop_type` (`"Exclusion"` or `"InsufficientEvidence"`) from
    a copy of `g`, fixing every reference that named one — marker slot or plain ref
    field alike, since `iter_refs` yields both the same way.

    Per field, per DECISION NEEDED 2: delete the key when the catalogue does not mark it
    required; otherwise substitute the schema-valid empty for its declared shape and
    record which kind the substitution turned out to be, from `validate_object` run once
    per touched object — the real schema validator, not a hand-rolled guess about which
    substitutions it will accept.
    """
    g2 = _copy_graph(g)
    dropped = {x["id"] for x in g.all(drop_type)}
    subs: list[dict] = []
    if dropped:
        for oid in g2.ids():
            if oid in dropped:
                continue
            obj = g2.get(oid)
            hits = [(path, target) for path, target in iter_refs(obj) if target in dropped]
            if not hits:
                continue
            kinds: dict[str, str] = {}
            for path, _target in hits:
                fs = _field_spec_at(obj, path)
                kinds[path] = "removed" if not _is_required(fs) else "pending"
                if kinds[path] == "pending":
                    _set_at(obj, path, _schema_empty_for(fs))
            removals = sorted((p for p, k in kinds.items() if k == "removed"),
                               key=_path_key, reverse=True)
            for path in removals:
                _del_at(obj, path)
            pending = [p for p, k in kinds.items() if k == "pending"]
            if pending:
                errs = validate_object(obj)
                for path in pending:
                    kinds[path] = "schema-forced" if _err_at(errs, path) else "empty"
            for path in sorted(kinds):
                subs.append({"object": oid, "path": path, "kind": kinds[path]})
            _replace(g2, obj)
        for oid in dropped:
            _drop(g2, oid)
    return g2, subs


def strip_exclusions(g: Graph) -> tuple[Graph, list[dict]]:
    """A new graph with every `Exclusion` object dropped, and every reference to one —
    a `{"$exclusion": id}` marker slot or a plain `ref` field such as `Alternative.
    statusReason` — fixed per `_drop_type`'s rule. `evidenceRegister` is untouched: it
    never names an Exclusion (it lists Evidence ids), so nothing there is ever a hit."""
    return _drop_type(g, "Exclusion")


def collapse_gaps(g: Graph) -> tuple[Graph, list[dict]]:
    """A new graph with every `InsufficientEvidence` object dropped, and every
    `{"$gap": id}` marker or plain ref that named one fixed per `_drop_type`'s rule."""
    return _drop_type(g, "InsufficientEvidence")


# ---- the two context managers ---------------------------------------------------------


@contextmanager
def scope_off():
    """[pre-flight defect 26 / ruling R9, widened] `check_scope` is imported **by
    name** into `docket.kernel.readiness` and `docket.kernel.standards` — ruling R9's
    two named sites — and, discovered while implementing this module and not named by
    the ruling, into `docket.kernel.bias` as well: `bias_indicators` (which `readiness_
    report` runs *before* its own `check_scope` call) folds `check_scope`'s findings
    into what `_selection`'s bias-selection Risk reads. Patching only the two named
    sites would leave that third call live and call the reading "scope off" anyway.
    All three are patched and all three restored.

    `demos.b_omfv_2019_2023.run` imports `check_scope` by name too, but it is a demo
    module, not production kernel code, and nothing on this module's own call path
    (`demos/ablation/run.py`'s `_score` calls `readiness_report` only) ever reaches it
    — patching it would be reaching into a sibling demo for no effect any consumer of
    this module could observe. `tests/eval/test_ablation.py` names it explicitly rather
    than silently widening the "known binders" set to cover it.
    """
    import docket.kernel.bias as bias_mod
    import docket.kernel.readiness as readiness_mod
    import docket.kernel.standards as standards_mod

    def _off(g, episode_id):
        return []

    old_b = bias_mod.check_scope
    old_r, old_s = readiness_mod.check_scope, standards_mod.check_scope
    bias_mod.check_scope = readiness_mod.check_scope = standards_mod.check_scope = _off
    try:
        yield
    finally:
        bias_mod.check_scope = old_b
        readiness_mod.check_scope, standards_mod.check_scope = old_r, old_s


@contextmanager
def silence_off():
    """Removes `rule_silence` from the module-level list `docket.kernel.validate.
    STRUCTURAL_RULES` and restores it at the same index in a `finally` — `validate()`
    iterates that list at call time, so the removal takes effect immediately, and a
    variant that left it removed would corrupt every later variant sharing the process.
    """
    from docket.kernel.validate import STRUCTURAL_RULES, rule_silence

    if rule_silence not in STRUCTURAL_RULES:
        yield
        return
    idx = STRUCTURAL_RULES.index(rule_silence)
    STRUCTURAL_RULES.pop(idx)
    try:
        yield
    finally:
        STRUCTURAL_RULES.insert(idx, rule_silence)


# ---- the harness -----------------------------------------------------------------------

ScoreFn = Callable[[Graph, str], dict]

DEFAULT_VARIANTS: tuple[str, ...] = (
    "baseline", "scope-off", "no-exclusions", "gaps-collapsed", "silence-off",
    "gaps-collapsed-silence-off",
)


def _bucket(rule: str) -> str:
    if rule == "schema":
        return "schema"
    if rule == "silence":
        return "silence"
    return "other"


def _instance_sets(findings: dict) -> dict[str, set[tuple]]:
    """`{rule: {tuple(objects), ...}}` — every distinct occurrence of each rule, so a
    rule already present at baseline can still be told apart from a *new* occurrence of
    it (`no-exclusions` does not introduce the rule `silent-omission` — that rule already
    fires on other evidence — it introduces one new occurrence, on `ev-234-report`, and a
    comparison that only asked "is this rule name new" would miss exactly that)."""
    return {rule: {tuple(objs) for objs in occurrences} for rule, occurrences in findings.items()}


def _compare(baseline: dict, variant: dict, subs: list[dict]) -> dict:
    base_by_rule = _instance_sets(baseline.get("findings", {}))
    var_by_rule = _instance_sets(variant.get("findings", {}))

    # A rule is "lost" only when every occurrence of it is gone — the F1/F4 case, where
    # `scope-off` leaves zero `ReusePastPurpose`/`NotAssessableAtLevel` findings behind.
    # A rule that keeps some occurrences while losing others is not reported here: this
    # module's own tests are the record of that finer distinction where it matters.
    lost = sorted(rule for rule in base_by_rule if rule not in var_by_rule)

    # "Gained" is per-occurrence, not per-rule: a rule already present at baseline still
    # counts here if the variant fires it on an object baseline never did.
    gained: dict[str, list[str]] = {"schema": [], "silence": [], "other": []}
    for rule in sorted(set(base_by_rule) | set(var_by_rule)):
        if var_by_rule.get(rule, set()) - base_by_rule.get(rule, set()):
            gained[_bucket(rule)].append(rule)

    base_ratings, var_ratings = baseline.get("ratings", {}), variant.get("ratings", {})
    ratings_changed = {
        q: [base_ratings.get(q), var_ratings.get(q)]
        for q in sorted(set(base_ratings) | set(var_ratings))
        if base_ratings.get(q) != var_ratings.get(q)
    }
    base_verdicts, var_verdicts = baseline.get("verdicts", {}), variant.get("verdicts", {})
    verdicts_changed = {
        d: [base_verdicts.get(d), var_verdicts.get(d)]
        for d in sorted(set(base_verdicts) | set(var_verdicts))
        if base_verdicts.get(d) != var_verdicts.get(d)
    }
    gaps_lost = sorted(set(baseline.get("gaps", [])) - set(variant.get("gaps", [])))
    exclusions_lost = sorted(
        set(baseline.get("exclusions", [])) - set(variant.get("exclusions", [])))

    return {
        "lost_findings": lost,
        "gained_findings": gained,
        "ratings_changed": ratings_changed,
        "verdicts_changed": verdicts_changed,
        "gaps_lost": gaps_lost,
        "exclusions_lost": exclusions_lost,
        "substitutions": subs,
    }


def run_ablations(
    build_fn: Callable[[], Graph],
    score_fn: ScoreFn,
    episode_ids: Sequence[str],
    *,
    variants: Sequence[str] = DEFAULT_VARIANTS,
) -> dict:
    """Score every episode in `episode_ids` under every variant, and compare each
    non-baseline variant's reading to that episode's own baseline reading.

    Dispatch is by **substring membership** on the variant name
    (`"gaps-collapsed" in variant`, `"silence-off" in variant`, `"scope-off" in
    variant`), not equality [pre-flight defect 27] — so `"gaps-collapsed-silence-off"`
    both collapses gaps and disables silence, without a special case naming that
    combination.

    Every variant, `"baseline"` included, runs against its own `copy.deepcopy` of
    `build_fn()`'s graph — no variant is special-cased to score the shared original, so
    the same code path that proves the ablations non-mutating also proves the baseline
    reading is not an accidental side effect of scoring the object every later variant
    is deep-copied from. After every variant has run, the graph `build_fn()` returned is
    asserted byte-for-bit unchanged (snapshot hash and log).

    Returns `{episode_id: {"baseline": {...}, variant_name: {...}, ...}}` — see
    `_compare`'s docstring above for the per-variant comparison shape and `score_fn`'s
    expected return shape (`{"findings": {rule: [objects]}, "ratings": {qid: state},
    "verdicts": {dim: verdict}, "gaps": [...], "exclusions": [...]}`).
    """
    if "baseline" not in variants:
        raise ValueError("run_ablations requires 'baseline' among variants")

    base = build_fn()
    base_hash, base_log = base.snapshot_hash(), base.log()

    def _score_variant(variant: str) -> tuple[dict[str, dict], list[dict]]:
        g = _copy_graph(base)
        subs: list[dict] = []
        if "no-exclusions" in variant:
            g, s = strip_exclusions(g)
            subs += s
        if "gaps-collapsed" in variant:
            g, s = collapse_gaps(g)
            subs += s
        with ExitStack() as stack:
            if "scope-off" in variant:
                stack.enter_context(scope_off())
            if "silence-off" in variant:
                stack.enter_context(silence_off())
            results = {ep: score_fn(g, ep) for ep in episode_ids}
        return results, subs

    baseline_results, _ = _score_variant("baseline")
    out: dict[str, dict] = {ep: {"baseline": baseline_results[ep]} for ep in episode_ids}
    for variant in variants:
        if variant == "baseline":
            continue
        results, subs = _score_variant(variant)
        for ep in episode_ids:
            out[ep][variant] = _compare(baseline_results[ep], results[ep], subs)

    assert base.snapshot_hash() == base_hash and base.log() == base_log, (
        "run_ablations must never mutate the graph build_fn() returned — every variant, "
        "baseline included, must score a copy"
    )
    return out
