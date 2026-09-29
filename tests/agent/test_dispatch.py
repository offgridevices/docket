# tests/agent/test_dispatch.py
"""Stage X: the agent asks the kernel to evaluate an approved plan and reads results
back by id — never copying or computing a number itself. `dispatch`/`read_back` need no
LLM: there is no backend fixture anywhere in this file, on purpose."""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from docket import KERNEL_ACTOR
from docket.agent.dispatch import dispatch, read_back
from docket.agent.plan import approve_plan
from docket.canon import canonical_json
from docket.errors import AuthorityViolation, ValidationError
from docket.kernel.flip import flip_analysis
from docket.kernel.lifecycle import transition

H = {"actorType": "human", "actorId": "shreyash"}
# The caller of `dispatch` is an agent throughout this file — asking the kernel to
# compute is not itself a numeric act, and the point of these tests is to show that
# nothing an agent-actor call produces ever carries agent authorship.
A = {"actorType": "agent", "actorId": "agent:recorded"}
NOW = "2013-04-30T00:00:00Z"
SEED = 20130430

RESULTS_JSON = Path(__file__).parents[2] / "demos" / "a_cbo_gcv_2013" / "out" / "results.json"


def _committed_results() -> dict:
    """Demo A's committed, kernel-produced rankings and figures — read, never retyped."""
    return json.loads(RESULTS_JSON.read_text(encoding="utf-8"))


def _link_plan(g):
    """03b links the episode to its plan before G2; do it here too if build() has not."""
    ep = g.get("ep-cbo-2013")
    if ep.get("plan") != "pl-cbo":
        g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
               "plan": "pl-cbo"}, H)


def _strip_approval(g, plan_id="pl-cbo"):
    """A new human revision with `approvedBy` absent — Demo A's build() ships it approved."""
    p = g.get(plan_id)
    return g.put({**{k: v for k, v in p.items() if k != "approvedBy"},
                  "rev": p["rev"] + 1, "createdBy": H, "createdAt": NOW}, H)


@pytest.fixture
def demo_a_at_g1():
    """Demo A built, model approved, plan linked, still before G2."""
    from demos.a_cbo_gcv_2013.build import build

    g = build()
    transition(g, "ep-cbo-2013", "MODEL_APPROVED", H, now=NOW)
    _link_plan(g)
    return g


# ---- refusals ----------------------------------------------------------------------


def test_dispatch_is_refused_on_an_unapproved_plan(demo_a_at_g1):
    g = demo_a_at_g1
    _strip_approval(g)
    assert "approvedBy" not in g.get("pl-cbo")
    with pytest.raises(AuthorityViolation) as exc:
        dispatch(g, "pl-cbo", actor=A, seed=SEED, now=NOW)
    assert "G2" in str(exc.value)
    assert g.get("ep-cbo-2013")["runs"] == [], "nothing computed before approval"
    assert g.get("ep-cbo-2013")["lifecycleState"] == "MODEL_APPROVED"


def test_dispatch_refuses_an_episode_that_has_not_passed_g2(demo_a_at_g1):
    g = demo_a_at_g1
    # The plan carries a human approval already (build() ships pl-cbo approved), but the
    # episode itself is still at MODEL_APPROVED: both halves of G2 are checked.
    assert "approvedBy" in g.get("pl-cbo")
    with pytest.raises(AuthorityViolation) as exc:
        dispatch(g, "pl-cbo", actor=A, seed=SEED, now=NOW)
    assert "G2" in str(exc.value)
    assert g.get("ep-cbo-2013")["runs"] == []


def test_dispatch_refuses_a_second_time_on_the_same_plan_with_no_partial_write(
    demo_a_at_g1,
):
    g = demo_a_at_g1
    _strip_approval(g)
    approve_plan(g, "pl-cbo", H, now=NOW)
    transition(g, "ep-cbo-2013", "PLAN_APPROVED", H, now=NOW)
    dispatch(g, "pl-cbo", actor=A, seed=SEED, now=NOW)
    log_length = len(g.log())
    # `evaluate()` computes `run_id = f"run-{plan_id}-{step}"` deterministically, so a
    # second dispatch of the same plan collides on the run/result ids it already wrote —
    # the kernel's own named refusal, not a bespoke one in this module.
    with pytest.raises(ValidationError) as exc:
        dispatch(g, "pl-cbo", actor=A, seed=SEED, now=NOW)
    assert "already present" in str(exc.value)
    assert len(g.log()) == log_length, "a refused dispatch must not write anything at all"


def test_flip_refusal_on_a_stale_run_surfaces_unmodified(demo_a_at_g1):
    """`dispatch` never constructs a stale run itself — evaluate() and flip_analysis() run
    back to back against the same live graph state, so nothing can go stale between them
    inside a single call. What this tests is that the refusal `flip_analysis` raises when
    a run's bound observations have moved since sealing — the exact function `dispatch`
    calls, with no try/except around it anywhere in this module — is not caught, wrapped
    or reworded on the way out. A caller that mistakenly re-requests flip analysis for a
    run after the record has moved on must see the kernel's own named refusal.
    """
    g = demo_a_at_g1
    _strip_approval(g)
    approve_plan(g, "pl-cbo", H, now=NOW)
    transition(g, "ep-cbo-2013", "PLAN_APPROVED", H, now=NOW)
    out = dispatch(g, "pl-cbo", actor=A, seed=SEED, now=NOW)
    run_id = next(r["id"] for r in out["runs"] if r["step"] == "primary")

    obs = g.get("ob-puma-prot")
    g.put({**obs, "rev": obs["rev"] + 1, "createdBy": H, "createdAt": NOW, "value": 999.0}, H)

    with pytest.raises(ValidationError) as exc:
        flip_analysis(g, run_id, seed=SEED, now=NOW)
    assert "changed since sealing" in str(exc.value)


# ---- the happy path, against Demo A's committed rankings ----------------------------


@pytest.fixture
def dispatched():
    """Demo A built, gated through G1 and G2, and dispatched — the graph, plus what
    `dispatch` returned."""
    from demos.a_cbo_gcv_2013.build import build

    g = build()
    transition(g, "ep-cbo-2013", "MODEL_APPROVED", H, now=NOW)
    _link_plan(g)
    _strip_approval(g)
    approve_plan(g, "pl-cbo", H, now=NOW)
    transition(g, "ep-cbo-2013", "PLAN_APPROVED", H, now=NOW)
    out = dispatch(g, "pl-cbo", actor=A, seed=SEED, now=NOW)
    return g, out


def test_dispatch_returns_a_dict_of_runs_and_flips(dispatched):
    # [defect 8] a dict — {"runs": [...], "flips": [...]} — not a list
    _, out = dispatched
    assert set(out) == {"runs", "flips"}
    assert {r["step"] for r in out["runs"]} == {"primary", "secondary"}
    assert all(r["sealedBy"] == "kernel" for r in out["runs"])
    assert all(r["createdBy"]["actorType"] == "kernel" for r in out["runs"])
    assert out["flips"], "Demo A's weight sets have more than one weight each"


def test_no_object_created_during_dispatch_is_agent_authored(dispatched):
    """The agent asked; only the kernel wrote. Every EvaluationRun, Result and
    FlipAnalysis dispatch produced is authored by KERNEL_ACTOR, never by the agent actor
    this call was made with."""
    g, out = dispatched
    for run in out["runs"]:
        assert run["createdBy"] == KERNEL_ACTOR
        for rid in run["outputs"]:
            assert g.get(rid)["createdBy"] == KERNEL_ACTOR
    for flip in out["flips"]:
        assert flip["createdBy"] == KERNEL_ACTOR
    assert g.get("ep-cbo-2013")["createdBy"] == KERNEL_ACTOR


def test_dispatch_refuses_a_malformed_actor_before_touching_the_kernel(demo_a_at_g1):
    """A bogus actor must be refused by name before the kernel is asked anything, so a
    malformed call can never seal a run."""
    g = demo_a_at_g1
    _strip_approval(g)
    approve_plan(g, "pl-cbo", H, now=NOW)
    transition(g, "ep-cbo-2013", "PLAN_APPROVED", H, now=NOW)
    before = len(g.log())
    for bad in ({"whatever": "junk"}, None, "agent:x", {"actorType": "kernel", "actorId": "k"}):
        with pytest.raises(ValidationError):
            dispatch(g, "pl-cbo", actor=bad, seed=SEED, now=NOW)
    assert len(g.log()) == before


def test_read_back_reproduces_demo_a_committed_rankings(dispatched):
    """Every number compared here is read out of `demos/a_cbo_gcv_2013/out/results.json`,
    never retyped — the fixture uses the same seed/now/graph as `demos/a_cbo_gcv_2013/
    run.py`, so the kernel must reproduce exactly what that run committed."""
    g, out = dispatched
    committed = _committed_results()
    by_step = {r["step"]: r["id"] for r in out["runs"]}

    for step in ("primary", "secondary"):
        rb = read_back(g, by_step[step])
        assert rb["ranking"] == committed["ranking"][step]

        aggregates = {row["alternative"]: row["value"] for row in rb["results"].values()
                     if row["aggregate"]}
        assert aggregates == committed[step]

        flips_by_target = {f["target"]: f for f in rb["flips"]}
        assert set(flips_by_target) == set(committed["flip"][step])
        for target, expected in committed["flip"][step].items():
            got = flips_by_target[target]
            assert got["flipThreshold"] == expected["flipThreshold"]
            assert got["flipDistance"] == expected["flipDistance"]
            assert got["direction"] == expected["direction"]


def test_read_back_result_shape(dispatched):
    g, out = dispatched
    run_id = next(r["id"] for r in out["runs"] if r["step"] == "primary")
    rb = read_back(g, run_id)
    assert rb["run"] == run_id
    assert all(g.has(i) for i in rb["ranking"])
    assert all(g.has(rid) for rid in rb["results"])
    assert all(g.has(f["id"]) for f in rb["flips"])
    # per-alternative aggregate value with units
    agg_rows = [row for row in rb["results"].values() if row["aggregate"]]
    assert agg_rows and all(row["units"] == "weighted value" for row in agg_rows)
    for f in rb["flips"]:
        stored = g.get(f["id"])
        # [defect 9] the label comes from parameter.label, not the top level
        assert f["label"] == stored["parameter"]["label"]
        assert f["kind"] == stored["parameter"]["kind"]
        assert f["target"] == stored["parameter"]["target"]


def test_read_back_values_are_byte_identical_to_stored_values(dispatched):
    """No rounding, scaling or reformatting: every number `read_back` hands out matches
    the stored kernel value byte-for-byte in canonical JSON, not merely `==`."""
    g, out = dispatched
    for run in out["runs"]:
        rb = read_back(g, run["id"])
        assert canonical_json(rb["ranking"]) == canonical_json(g.get(run["id"])["ranking"])
        assert canonical_json(rb["seed"]) == canonical_json(g.get(run["id"])["seed"])
        for rid, row in rb["results"].items():
            stored = g.get(rid)
            assert canonical_json(row["value"]) == canonical_json(stored["value"])
            assert canonical_json(row["units"]) == canonical_json(stored["units"])
        for f in rb["flips"]:
            stored = g.get(f["id"])
            assert canonical_json(f["flipThreshold"]) == canonical_json(stored["flipThreshold"])
            assert canonical_json(f["flipDistance"]) == canonical_json(stored["flipDistance"])
            assert canonical_json(f["label"]) == canonical_json(stored["parameter"]["label"])


# ---- the whole-module claim: no arithmetic anywhere in this path --------------------


def test_dispatch_module_contains_no_arithmetic():
    """A reviewer should be able to confirm the claim by reading the module.

    Restricted to genuine arithmetic operators (`ast.BinOp`/`ast.AugAssign` limited to
    `+ - * / // ** %`, and numeric `ast.UnaryOp` limited to unary `-`/`+`/`~`) rather than
    the brief's broader `ast.UnaryOp` check: a bare `ast.UnaryOp` also matches boolean
    `not`, which this module needs for its G2 pre-check (`not is_content(...)`) and which
    is not arithmetic on a value in any sense this test is meant to police.
    """
    import docket.agent.dispatch as mod

    arith_binops = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Pow, ast.Mod)
    arith_unaryops = (ast.USub, ast.UAdd, ast.Invert)

    tree = ast.parse(inspect.getsource(mod))
    offenders = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.AugAssign)
        or (isinstance(n, ast.BinOp) and isinstance(n.op, arith_binops))
        or (isinstance(n, ast.UnaryOp) and isinstance(n.op, arith_unaryops))
    ]
    dumped = [ast.dump(o) for o in offenders]
    assert not offenders, f"arithmetic in the agent dispatch path: {dumped}"


def test_dispatch_constructs_no_backend():
    """The numeric path has no LLM in it: `dispatch` never imports or constructs a
    backend of any kind."""
    import docket.agent.dispatch as mod

    source = inspect.getsource(mod)
    assert "backend" not in source.lower()
