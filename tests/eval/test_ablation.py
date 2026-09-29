"""Ablations (plan 05 Task 7): what a readiness reading loses without the scope checker,
the Exclusion objects, or the gap objects — measured on Demo B's `-fs` and `-ce`
sub-episodes, not asserted.

Three of the plan's four Step 1 hypotheses were wrong against the real rules (the
task-7 brief, Section C) — only `scope-off`'s F1/F4 losses are structurally certain.
Every other assertion below is written from a measured run
(`uv run python -c "from demos.ablation.run import run; print(...)"`), per the brief's
own instruction not to adjust the transform or the fixture to make a hypothesis true.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import docket.kernel.bias as bias
import docket.kernel.readiness as readiness
import docket.kernel.scope as scope
import docket.kernel.standards as standards
from demos.ablation.run import OUT, RESULTS_FILE, run
from docket.eval.ablation import run_ablations, scope_off, silence_off
from docket.kernel.validate import STRUCTURAL_RULES, rule_silence

FS = "ep-omfv-2020-02-r4-fs"
CE = "ep-omfv-2020-02-r4-ce"


def test_scope_off_patches_every_binding():
    """[pre-flight defect 26; ruling R9 widened] `check_scope` is imported by name into
    three production modules, not the two R9 names: `docket.kernel.bias` calls it
    inside `bias_indicators`, which `readiness_report` runs before its own `check_scope`
    call — found while implementing this module, see `scope_off`'s docstring."""
    before = (bias.check_scope, readiness.check_scope, standards.check_scope)
    with scope_off():
        assert bias.check_scope(None, "x") == []
        assert readiness.check_scope(None, "x") == []
        assert standards.check_scope(None, "x") == []
    assert (bias.check_scope, readiness.check_scope, standards.check_scope) == before


def test_every_production_import_of_check_scope_is_accounted_for():
    """Static, not `sys.modules`-based: a `getattr(module, "check_scope", ...) is
    scope.check_scope` scan (the brief's own suggested test) depends on *what else the
    test session has already imported* — running only this file finds four binders;
    running the whole suite finds `docket.exports.{gsn,prov,rtvm}`,
    `docket.api.routes.kernel`, `docket.agent.refresh_watch` and even test modules that
    import `check_scope` for their own assertions, none of which this ablation's
    `score_fn` (which calls only `readiness_report`) ever reaches. A source grep is the
    actual invariant, and it is the verification command the brief itself lists:
    `command grep -rn 'from docket.kernel.scope import check_scope' src/docket`.

    Every production import site is named below, split into the three `scope_off`
    patches (on `readiness_report`'s own call graph: itself, `build_context`'s
    standards scoring, and `bias_indicators`) and the ones it deliberately does not —
    independent consumers of `check_scope` for their own features (export renderers, an
    agent watcher, an API route) that `readiness_report` never calls into. If a new
    import site appears anywhere in `src/docket` that isn't in one of these two sets,
    that is a real, uncategorised gap and this test must fail until it is placed.
    """
    src = Path(scope.__file__).resolve().parent.parent  # .../src/docket
    pattern = re.compile(r"^from docket\.kernel\.scope import check_scope", re.MULTILINE)
    importers = {
        str(p.relative_to(src.parent)).replace("\\", "/")
        for p in src.rglob("*.py")
        if pattern.search(p.read_text(encoding="utf-8"))
    }

    patched = {  # on readiness_report's own call graph — scope_off() covers these
        "docket/kernel/readiness.py", "docket/kernel/standards.py", "docket/kernel/bias.py",
    }
    not_on_this_path = {  # independent features readiness_report never calls into
        "docket/agent/refresh_watch.py", "docket/exports/gsn.py", "docket/exports/prov.py",
        "docket/exports/rtvm.py", "docket/api/routes/kernel.py",
    }
    accounted_for = patched | not_on_this_path
    assert importers <= accounted_for, (
        f"new check_scope import site(s) not categorised: {importers - accounted_for}")
    # Every accounted-for site must still be a real import, not stale bookkeeping.
    assert importers >= patched, (
        f"scope_off() patches a site that no longer imports check_scope: "
        f"{patched - importers}")


def test_silence_off_restores_the_rule_list():
    before = list(STRUCTURAL_RULES)
    with silence_off():
        assert len(STRUCTURAL_RULES) == len(before) - 1
        assert rule_silence not in STRUCTURAL_RULES
    assert list(STRUCTURAL_RULES) == before


def test_silence_off_restores_at_the_original_index():
    """`rule_silence` is not last in `STRUCTURAL_RULES` — a restore that appended it
    instead of reinserting at its original index would pass a set-equality check but
    fail this one."""
    idx = STRUCTURAL_RULES.index(rule_silence)
    with silence_off():
        pass
    assert STRUCTURAL_RULES.index(rule_silence) == idx


def test_silence_off_is_a_noop_if_the_rule_is_already_absent():
    idx = STRUCTURAL_RULES.index(rule_silence)
    removed = STRUCTURAL_RULES.pop(idx)
    try:
        with silence_off():
            assert rule_silence not in STRUCTURAL_RULES
        assert rule_silence not in STRUCTURAL_RULES
    finally:
        STRUCTURAL_RULES.insert(idx, removed)


def test_run_ablations_requires_baseline_in_variants():
    with pytest.raises(ValueError):
        run_ablations(lambda: None, lambda g, e: {}, ["x"], variants=("scope-off",))


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    return run(tmp_path_factory.mktemp("ablation"))


def test_scope_off_loses_exactly_f1_and_f4(demo):
    """Structurally certain (brief Section C): only `check_scope` emits either rule, so
    turning it off must make it vanish from the section GAO attributed it to."""
    fs, ce = demo[FS], demo[CE]
    assert fs["scope-off"]["lost_findings"] == ["ReusePastPurpose"]
    assert ce["scope-off"]["lost_findings"] == ["NotAssessableAtLevel"]
    # F1's other half: EXE-3 is rated by `model_evidence_reuse_past_purpose`, which
    # reads `ctx.scope` — turning the checker off must move it.
    assert fs["scope-off"]["ratings_changed"]["EXE-3"][0] == 3


def test_no_exclusions_gains_a_silent_omission_not_a_silence(demo):
    """[brief Section C, correcting the plan] Dropping the three Exclusion objects does
    not turn them into `silence` findings — none of them sits behind a slot a marker
    could occupy (they are free-standing, per the ledger). What changes is
    `silent_omission`'s coverage set: `ex-234-report-not-public` was the only thing
    keeping `ev-234-report` from firing it, so a *new occurrence* of the
    already-present rule `silent-omission` appears, and it must be bucketed `other`,
    never `silence`."""
    for ep_id in (FS, CE):
        d = demo[ep_id]["no-exclusions"]
        assert d["lost_findings"] == []
        assert "silent-omission" in d["gained_findings"]["other"]
        assert "silent-omission" not in d["gained_findings"]["silence"]
        assert "silent-omission" not in d["gained_findings"]["schema"]


def test_gaps_collapsed_linchpin_unevidenced_survives(demo):
    """[brief Section C, correcting the plan] `linchpin_unevidenced` fires on
    `not is_content(evidence)`, and an empty string satisfies that exactly as a `$gap`
    marker does — the rule is never lost. What is lost is the gap objects' own content
    (`sought`, `whereLookedFor`, `whyNotFound`, `indicatorsThatWouldResolve`,
    `confirmedBy`) and the whole `openGaps` list."""
    for ep_id in (FS, CE):
        d = demo[ep_id]["gaps-collapsed"]
        assert "linchpin-unevidenced" not in d["lost_findings"]
        assert d["gaps_lost"], f"{ep_id}: no gap objects were lost"
    # The finding survives; some slots empty to schema-valid content (`silence`) and
    # some do not (`schema`) — never counted as the same thing (ruling R9).
    assert demo[CE]["gaps-collapsed"]["gained_findings"]["silence"]
    assert demo[CE]["gaps-collapsed"]["gained_findings"]["schema"]


def test_gaps_collapsed_silence_off_ratings_survive_with_no_object(demo):
    """[brief Section C, correcting the plan] EXE-5 and EXE-8 are rated from the cited
    evidence's own `reliabilitySteps`/VV&A sections, not from a Finding — collapsing
    gaps and disabling `silence` together removes every trace of what was sought, but
    the ratings do not move. That is what a checklist without objects produces, and it
    is the point of the ablation."""
    for ep_id in (FS, CE):
        d = demo[ep_id]["gaps-collapsed-silence-off"]
        assert "EXE-5" not in d["ratings_changed"]
        assert "EXE-8" not in d["ratings_changed"]
        assert "linchpin-unevidenced" not in d["lost_findings"]
        # `silence` is off: nothing can be freshly reported by that rule.
        assert d["gained_findings"]["silence"] == []
        assert d["gaps_lost"], f"{ep_id}: no gap objects were lost"


def test_gained_findings_are_always_bucketed_three_ways(demo):
    for ep_id in (FS, CE):
        for variant, d in demo[ep_id].items():
            if variant == "baseline":
                continue
            assert set(d["gained_findings"]) == {"silence", "schema", "other"}


def test_ablation_on_demo_b(tmp_path):
    """The task-7 brief's own Step 2 test, verbatim (self-contained — it runs its own
    `run(tmp_path)` rather than sharing the module-scoped `demo` fixture, exactly as
    the brief wrote it)."""
    r = run(tmp_path)
    fs = r["ep-omfv-2020-02-r4-fs"]
    ce = r["ep-omfv-2020-02-r4-ce"]
    assert "ReusePastPurpose" in fs["scope-off"]["lost_findings"]
    assert "NotAssessableAtLevel" in ce["scope-off"]["lost_findings"]
    for ep in (fs, ce):
        for variant, d in ep.items():
            if variant == "baseline":
                continue
            assert set(d["gained_findings"]) == {"silence", "schema", "other"}
    assert ce["gaps-collapsed"]["gaps_lost"], "no gap objects were lost"
    assert (tmp_path / "ablation.md").exists()


def test_run_restores_global_state_after_finishing(demo):
    """Every variant patches and restores `check_scope`/`STRUCTURAL_RULES` in turn —
    after a full `run()`, both must be back to their originals."""
    assert readiness.check_scope is scope.check_scope
    assert standards.check_scope is scope.check_scope
    assert rule_silence in STRUCTURAL_RULES


def test_run_ablations_never_mutates_the_baseline_graph():
    """An external check on top of `run_ablations`'s own internal assertion: the exact
    graph object `build_fn()` returns must be byte-for-bit unchanged after every
    variant — snapshot hash and log both — even though several variants score copies
    derived from it that carry deliberately schema-invalid content."""
    from demos.ablation.run import EPISODE_IDS, _build_graph, _score

    captured: dict[str, object] = {}

    def build_fn():
        g = _build_graph()
        captured["graph"], captured["hash"], captured["log"] = g, g.snapshot_hash(), g.log()
        return g

    run_ablations(build_fn, _score, EPISODE_IDS)
    assert captured["graph"].snapshot_hash() == captured["hash"]
    assert captured["graph"].log() == captured["log"]


def test_run_is_deterministic(tmp_path):
    a, b = run(tmp_path / "a"), run(tmp_path / "b")
    assert a == b
    left, right = tmp_path / "a", tmp_path / "b"
    names = sorted(p.relative_to(left) for p in left.rglob("*") if p.is_file())
    assert names == sorted(p.relative_to(right) for p in right.rglob("*") if p.is_file())
    differing = [str(rel) for rel in names
                 if (left / rel).read_bytes() != (right / rel).read_bytes()]
    assert differing == [], differing


def test_run_writes_only_into_its_out_dir(tmp_path):
    target = tmp_path / "nested" / "out"
    run(target)
    assert sorted(p.name for p in target.iterdir()) == sorted([RESULTS_FILE, "ablation.md"])


def test_committed_output_is_current(tmp_path):
    if not (OUT / RESULTS_FILE).exists():
        pytest.skip("demos/ablation/out has not been generated yet")
    fresh = tmp_path / "fresh"
    run(fresh)
    committed = sorted(p.relative_to(OUT) for p in OUT.rglob("*") if p.is_file())
    produced = sorted(p.relative_to(fresh) for p in fresh.rglob("*") if p.is_file())
    hint = " — re-run: uv run python -m demos.ablation.run"
    assert committed == produced, f"the committed file list differs from a fresh run's{hint}"
    stale = [str(rel) for rel in committed
             if (OUT / rel).read_bytes() != (fresh / rel).read_bytes()]
    assert stale == [], f"{len(stale)} stale file(s): {stale[:10]}{hint}"
