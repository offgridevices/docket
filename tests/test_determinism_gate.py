"""Tests for the byte-identical determinism gate (design §9.6; §11 M2 row —
"determinism tests in CI") and for `demos/run_all.py`'s `--out` contract.

Two things are tested here. First, `docket.kernel.verify.verify_determinism` re-
rendering a saved graph twice inside one process — the cheap check every `pytest` run
exercises, and the exact function `scripts/determinism-check.sh`, `docket verify` and
`docket.api.verify` (via the shared `render_hashes` helper) all build on (ruling R4: one
determinism function). Second, a lighter, in-process version of
`scripts/determinism-check.sh`'s "is the committed output stale" half: rebuild a demo and
compare its whole `out/` tree, file by file, against what is committed — the aggregate
form of each demo's own `test_committed_output_is_current` (`tests/demos/test_*.py`),
which checks a hand-picked file list rather than the whole tree.

Scope: the four demos this task was told are committed and stable —
`a_cbo_gcv_2013`, `budget_books`, `control_gao_15_548`, `validation_gao_21_460`.
`demos/b_omfv_2019_2023` is plan 05 Task 5's, landing concurrently with this task; this
file does not depend on its shape or its determinism (that demo has its own
`tests/demos/test_demo_b.py`). `demos/run_all.py` itself stays fully generic — it must
run whichever demos are present and skip whichever are not, which is exercised below
against a monkeypatched demo list rather than against whatever happens to be on disk at
any given moment.

Fix round 1 (review `review-t2-part1-report.md`) added three more things: I1, a test
that drives `verify_determinism`'s `identical is False` / non-empty `differing` branch —
the one comparison this whole gate exists to get right, previously untested on its false
side, via a monkeypatched `render_hashes` returning two disagreeing hash maps; N1, a test
that a demo module which *imports* but whose `run()` raises is reported and re-raised,
not silently swallowed the way an absent module is; and C1, tests for
`scripts/ci-audit-range.sh` — the event-derived audit-range resolver that replaced
`ci.yml`'s hardcoded `origin/main...HEAD` (a guaranteed empty diff on a direct push to
main) — run against a real temporary git repository built at runtime, covering an
ordinary push, a new branch's all-zeros `before` falling back to a merge-base, a
pull_request, and the script's fail-loud paths (an unresolvable sha; an empty range with
distinct endpoints) so an empty or bogus range can never pass silently.
"""
from __future__ import annotations

import hashlib
import importlib
import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

from docket.kernel.verify import verify_determinism

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMOS_DIR = REPO_ROOT / "demos"
CI_AUDIT_RANGE_SCRIPT = REPO_ROOT / "scripts" / "ci-audit-range.sh"
ZERO_SHA = "0" * 40

# The demos this task was briefed as committed and stable (see this file's docstring).
STABLE_DEMOS = [
    "a_cbo_gcv_2013",
    "budget_books",
    "control_gao_15_548",
    "validation_gao_21_460",
]


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _committed_renderings(out_dir: Path) -> list[str]:
    """Renderings this demo's committed `out/` actually built a package for, read from
    the filenames themselves (`package-<rendering>.md`) rather than assumed — so a demo
    that adds or drops a rendering is picked up without editing this file."""
    return sorted(p.stem.removeprefix("package-") for p in out_dir.glob("package-*.md"))


# ---- verify_determinism: two in-process renders of the same saved graph -------------


@pytest.mark.parametrize("name", STABLE_DEMOS)
def test_verify_determinism_is_identical_for_every_committed_package(name):
    run_mod = importlib.import_module(f"demos.{name}.run")
    out_dir = run_mod.OUT
    graph_dir = out_dir / "graph"
    renderings = _committed_renderings(out_dir)
    if not graph_dir.is_dir() or not renderings:
        pytest.skip(f"{name}: no committed package under {out_dir} to verify")

    for rendering in renderings:
        result = verify_determinism(
            graph_dir, run_mod.EPISODE,
            seed=run_mod.SEED, now=run_mod.NOW, rendering=rendering,
        )
        assert result["differing"] == [], (name, rendering, result["differing"])
        assert result["identical"] is True, (name, rendering, result)
        assert result["hashes"] == result["second"], (name, rendering)
        assert "package" in result["hashes"], (name, rendering)


def test_verify_determinism_raises_a_validation_error_on_an_unknown_episode(tmp_path):
    from docket.errors import ValidationError
    from docket.store import Graph

    Graph().save(tmp_path)
    with pytest.raises(ValidationError):
        verify_determinism(tmp_path, "nope", seed=0, now="2026-01-01T00:00:00Z")


def test_verify_determinism_reports_a_hash_mismatch(tmp_path, monkeypatch):
    """I1 (review C1/I1 fix round): nothing in the shipped suite ever drove
    `verify_determinism`'s `identical is False` / non-empty `differing` branch — the one
    comparison this whole gate exists to get right. Monkeypatch the module-level
    `render_hashes` (the primitive `verify_determinism` calls twice) to return two
    disagreeing hash maps and check the comparison itself: the false branch, the exact
    `differing` list, and that both raw hash dicts are threaded through unchanged."""
    import docket.kernel.verify as verify_module
    from docket.store import Graph

    Graph().save(tmp_path)
    first = {"package": "aaaa", "export-x": "same"}
    second = {"package": "bbbb", "export-x": "same"}
    monkeypatch.setattr(
        verify_module, "render_hashes", Mock(side_effect=[first, second])
    )

    result = verify_module.verify_determinism(
        tmp_path, "does-not-matter", seed=0, now="2026-01-01T00:00:00Z"
    )

    assert result["identical"] is False
    assert result["differing"] == ["package"]
    assert result["hashes"] == first
    assert result["second"] == second


# ---- committed out/ is not stale: the whole tree, not a hand-picked file list -------


@pytest.mark.parametrize("name", STABLE_DEMOS)
def test_committed_output_matches_a_fresh_rebuild(name, tmp_path):
    run_mod = importlib.import_module(f"demos.{name}.run")
    if not run_mod.OUT.exists():
        pytest.skip(f"{name}: no committed {run_mod.OUT}")

    fresh_dir = tmp_path / "fresh"
    run_mod.run(fresh_dir)

    committed = _hash_tree(run_mod.OUT)
    fresh = _hash_tree(fresh_dir)
    assert fresh == committed, (
        f"{name}: committed {run_mod.OUT} does not match a fresh run — re-run "
        f"uv run python -m demos.{name}.run"
    )


# ---- demos/run_all.py: the --out contract and the skip-if-absent behaviour ----------


def test_demos_list_names_every_expected_demo():
    from demos import run_all

    assert set(run_all.DEMOS) == {
        "a_cbo_gcv_2013", "ablation", "b_omfv_2019_2023", "budget_books",
        "control_gao_15_548", "validation_gao_21_460",
    }


def test_run_all_runs_every_stable_demo_into_the_out_contract(tmp_path):
    # One `run_all` call covering every stable demo, rather than one parametrized test
    # per name — the underlying `run_all` re-runs *every* demo each time it is called,
    # so parametrizing this would multiply a several-second call by len(STABLE_DEMOS)
    # for no extra coverage.
    from demos import run_all

    manifest = run_all.run_all(tmp_path)
    by_name = {entry["demo"]: entry for entry in manifest}

    for name in STABLE_DEMOS:
        entry = by_name[name]
        assert entry["present"] is True, entry
        out_dir = tmp_path / "demos" / name / "out"
        assert out_dir.is_dir()
        assert entry["outDir"] == str(out_dir)
        if entry["resultsFile"] is not None:
            assert Path(entry["resultsFile"]).is_file(), entry


def test_run_all_skips_a_demo_whose_module_is_absent(tmp_path, monkeypatch):
    """`run_all` must not fail the whole run because one demo's module has not landed
    yet — it must name the missing one and continue. Exercised against a monkeypatched
    demo list rather than a real gap in `demos/`, so this test is not hostage to which
    demo happens to be mid-flight at any given moment (plan 05 Task 5's Demo B lands
    concurrently with this task)."""
    from demos import run_all

    monkeypatch.setattr(run_all, "DEMOS", ["a_cbo_gcv_2013", "no_such_demo_xyz"])

    manifest = run_all.run_all(tmp_path)
    by_name = {entry["demo"]: entry for entry in manifest}

    assert by_name["a_cbo_gcv_2013"]["present"] is True
    assert (tmp_path / "demos" / "a_cbo_gcv_2013" / "out").is_dir()

    absent = by_name["no_such_demo_xyz"]
    assert absent["present"] is False
    assert "no_such_demo_xyz" in absent["reason"]


def test_run_all_reports_and_reraises_when_a_demos_run_crashes(tmp_path, monkeypatch):
    """N1 (review fix round): a demo module that *imports* fine but whose `run()`
    raises is a real bug, categorically different from a demo whose module is simply
    absent — it must not be swallowed the way `ModuleNotFoundError` is. `run_all` must
    print one line to stderr naming the demo and the exception, then re-raise, so the
    process exit stays non-zero and CI shows the cause instead of a bare, unlabelled
    traceback.

    The crashing module is injected via `sys.modules` (Python's import machinery
    returns an already-cached module by its full dotted name without needing the parent
    package to exist on disk — see `importlib._bootstrap._find_and_load`), so this test
    needs no real demo package under a temp `demos/` root."""
    from demos import run_all

    def _boom(out_dir):
        raise ValueError("bad graph state")

    fake_module = types.ModuleType("demos.crash_demo.run")
    fake_module.run = _boom

    monkeypatch.setitem(sys.modules, "demos.crash_demo.run", fake_module)
    monkeypatch.setattr(run_all, "DEMOS", ["crash_demo"])

    with pytest.raises(ValueError, match="bad graph state"):
        run_all.run_all(tmp_path)


def test_run_all_crash_message_names_the_demo_and_the_exception(tmp_path, monkeypatch, capsys):
    from demos import run_all

    def _boom(out_dir):
        raise ValueError("bad graph state")

    fake_module = types.ModuleType("demos.crash_demo.run")
    fake_module.run = _boom

    monkeypatch.setitem(sys.modules, "demos.crash_demo.run", fake_module)
    monkeypatch.setattr(run_all, "DEMOS", ["crash_demo"])

    with pytest.raises(ValueError):
        run_all.run_all(tmp_path)

    err = capsys.readouterr().err
    assert "run_all: demo crash_demo FAILED: ValueError: bad graph state" in err


def test_default_out_root_is_the_repository_root():
    """The `--out` default must be the repo root (D1's correction), so a bare `run_all`
    reproduces the committed layout. Checked against the parser's default, never by
    actually invoking a bare `run_all()` — that would overwrite the committed `out/`
    trees this same test file reads."""
    from demos import run_all

    args = run_all._build_parser().parse_args([])
    assert args.out == run_all.REPO_ROOT
    assert (run_all.REPO_ROOT / "demos").is_dir()


def test_main_prints_a_manifest_and_a_reason_for_each_skipped_demo(tmp_path, capsys, monkeypatch):
    from demos import run_all

    monkeypatch.setattr(run_all, "DEMOS", ["a_cbo_gcv_2013", "no_such_demo_xyz"])
    rc = run_all.main(["run_all.py", "--out", str(tmp_path)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "a_cbo_gcv_2013: ok" in out
    assert "no_such_demo_xyz: skipped" in out


# ---- C1: scripts/ci-audit-range.sh — the audit range comes from the event ----------
#
# `.github/workflows/ci.yml`'s hardcoded `--range origin/main...HEAD` was a guaranteed
# empty diff on a direct push to `main` (review C1): with `fetch-depth: 0`,
# `origin/main`'s remote-tracking ref already points at the commit that was just pushed
# by the time the job runs. `scripts/ci-audit-range.sh` replaces it, deriving the range
# from the triggering event instead of a fixed ref name. These tests build a real,
# throwaway git repository at runtime and run the script as a subprocess against it —
# exactly how the workflow invokes it — rather than mocking git.


def _init_range_test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    return repo


def _commit_range_test_file(repo: Path, name: str, contents: str) -> str:
    (repo / name).write_text(contents)
    subprocess.run(["git", "add", name], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", contents], cwd=repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_ci_audit_range(repo: Path, **env_vars) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_vars}
    return subprocess.run(
        [str(CI_AUDIT_RANGE_SCRIPT)], cwd=repo, env=env, capture_output=True, text=True,
    )


def test_ci_audit_range_push_uses_before_and_sha(tmp_path):
    """The ordinary case: a direct push to main. Range is `before..sha`, taken
    verbatim from the event — never a hardcoded branch name."""
    repo = _init_range_test_repo(tmp_path)
    a = _commit_range_test_file(repo, "f1.txt", "one")
    b = _commit_range_test_file(repo, "f2.txt", "two")

    result = _run_ci_audit_range(repo, CI_EVENT_NAME="push", CI_BASE_SHA=a, CI_HEAD_SHA=b)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{a}..{b}"


def test_ci_audit_range_new_branch_falls_back_to_merge_base(tmp_path):
    """A brand-new branch's first push carries the all-zeros `before` sha — there is no
    prior commit on this ref to diff from, so the range must start at the merge-base
    with the default branch instead of failing or silently passing an empty range."""
    repo = _init_range_test_repo(tmp_path)
    a = _commit_range_test_file(repo, "f1.txt", "one")
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", a], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=repo, check=True)
    c = _commit_range_test_file(repo, "f2.txt", "feature-work")

    result = _run_ci_audit_range(
        repo, CI_EVENT_NAME="push", CI_BASE_SHA=ZERO_SHA, CI_HEAD_SHA=c,
        CI_DEFAULT_BRANCH_REF="origin/main",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{a}..{c}"


def test_ci_audit_range_pull_request_uses_base_and_head_sha(tmp_path):
    """A pull_request event's range is `base.sha..head.sha`, taken directly from the
    event — never the merge-base fallback, which is push-only."""
    repo = _init_range_test_repo(tmp_path)
    a = _commit_range_test_file(repo, "f1.txt", "one")
    subprocess.run(["git", "checkout", "-q", "-b", "pr-branch"], cwd=repo, check=True)
    c = _commit_range_test_file(repo, "f2.txt", "pr-work")

    result = _run_ci_audit_range(repo, CI_EVENT_NAME="pull_request", CI_BASE_SHA=a, CI_HEAD_SHA=c)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{a}..{c}"


def test_ci_audit_range_fails_loudly_on_an_unresolvable_sha(tmp_path):
    repo = _init_range_test_repo(tmp_path)
    a = _commit_range_test_file(repo, "f1.txt", "one")

    result = _run_ci_audit_range(
        repo, CI_EVENT_NAME="push", CI_BASE_SHA=a,
        CI_HEAD_SHA="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    )

    assert result.returncode == 1
    assert result.stdout.strip() == ""
    assert "does not resolve to a commit" in result.stderr


def test_ci_audit_range_fails_loudly_on_an_empty_range_with_distinct_shas(tmp_path):
    """An empty `git rev-list --count` with two *different* endpoints (e.g. a
    backward/force push) is suspicious, not routine — it must fail, not be waved
    through as an ordinary no-op the way a genuinely empty range is."""
    repo = _init_range_test_repo(tmp_path)
    a = _commit_range_test_file(repo, "f1.txt", "one")
    b = _commit_range_test_file(repo, "f2.txt", "two")

    result = _run_ci_audit_range(repo, CI_EVENT_NAME="push", CI_BASE_SHA=b, CI_HEAD_SHA=a)

    assert result.returncode == 1
    assert result.stdout.strip() == ""
    assert "refusing to pass silently" in result.stderr


def test_ci_audit_range_allows_a_genuine_no_op_rerun(tmp_path):
    """`before == sha` (the literal same commit) is the one case an empty range is
    allowed through without failing — e.g. a workflow manually re-run against an event
    that added nothing new."""
    repo = _init_range_test_repo(tmp_path)
    a = _commit_range_test_file(repo, "f1.txt", "one")

    result = _run_ci_audit_range(repo, CI_EVENT_NAME="push", CI_BASE_SHA=a, CI_HEAD_SHA=a)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{a}..{a}"
