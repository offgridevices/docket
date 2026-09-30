"""Tests for scripts/precommit-audit.sh: the pre-existing staged-index mode (must stay
byte-for-byte unchanged in behaviour) and the additive `--range <base>..<head>` mode
(ruling R6, plan 06 Task 2).

Every fixture below builds its planted secret at runtime rather than writing it as one
literal token in this file's source — this is a test *of* a secret scanner, committed
into the very repository that scanner audits, so a literal `AKIA` + 16 characters here
would trip the real audit on this file the moment it is staged. See `FAKE_AWS_KEY`.

Each test builds a throwaway git repository under `tmp_path` and runs the real script
(by absolute path) with that repository as the working directory — the script's own
first line, `cd "$(git rev-parse --show-toplevel)"`, then resolves to the throwaway
repo, not this one.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "precommit-audit.sh"

GOOD_GITIGNORE = (
    ".env\n*.pem\n*.key\ncredentials.json\nservice-account*.json\nlibrary/\nproposal/\n"
)

# Built at runtime — see module docstring. Matches the audit's own `AKIA[0-9A-Z]{16}`
# pattern without the 20-character match ever appearing as one literal token here.
FAKE_AWS_KEY = "AKIA" + "Q" * 16


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=check, capture_output=True, text=True,
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], cwd=path)
    _git(["config", "user.name", "Test"], cwd=path)
    _git(["config", "user.email", "test@example.com"], cwd=path)
    _git(["config", "commit.gpgsign", "false"], cwd=path)


def _commit_all(path: Path, message: str) -> str:
    _git(["add", "-A"], cwd=path)
    _git(["commit", "-q", "-m", message], cwd=path)
    return _git(["rev-parse", "HEAD"], cwd=path).stdout.strip()


def _run_audit(cwd: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *extra_args], cwd=cwd, capture_output=True, text=True,
    )


def _base_repo(tmp_path: Path, name: str) -> Path:
    """A repo with one clean commit: a compliant `.gitignore` and one tracked file."""
    repo = tmp_path / name
    _init_repo(repo)
    (repo / ".gitignore").write_text(GOOD_GITIGNORE, encoding="utf-8")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _commit_all(repo, "base")
    return repo


def _plant_four_violations(repo: Path) -> None:
    """The cases both modes must catch: a forbidden filename, a research-library path, a
    private-proposal path, a secret-shaped string in a tracked file, and a `.gitignore`
    that dropped `library/` and `proposal/`.

    `.env` is itself covered by `GOOD_GITIGNORE`, so a plain `git add -A` would silently
    skip it and never plant the violation at all — force-add it here to simulate the
    real failure mode check 1 exists for (someone bypasses the ignore, with `git add -f`
    or an editor that stages it directly), rather than relying on the caller's `add -A`.
    """
    (repo / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (repo / "library").mkdir()
    (repo / "library" / "x.md").write_text("notes\n", encoding="utf-8")
    (repo / "proposal").mkdir()
    (repo / "proposal" / "draft.md").write_text("private\n", encoding="utf-8")
    (repo / "leaked.py").write_text(f'KEY = "{FAKE_AWS_KEY}"\n', encoding="utf-8")
    (repo / ".gitignore").write_text(
        GOOD_GITIGNORE.replace("library/\n", "").replace("proposal/\n", ""),
        encoding="utf-8",
    )
    _git(["add", "-f", ".env"], cwd=repo)


def _assert_four_violations_reported(output: str) -> None:
    assert "FORBIDDEN FILE STAGED: .env" in output
    assert "RESEARCH LIBRARY FILE STAGED" in output and "library/x.md" in output
    assert "POSSIBLE SECRET IN STAGED DIFF" in output
    assert FAKE_AWS_KEY in output
    assert ".gitignore MISSING: library/" in output
    assert "PRIVATE PROPOSAL FILE STAGED" in output and "proposal/draft.md" in output
    assert ".gitignore MISSING: proposal/" in output


def test_a_nested_proposal_path_is_refused_too(tmp_path):
    """`proposal/` is treated exactly like `library/`: at the root or at any depth."""
    repo = _base_repo(tmp_path, "nested-proposal")
    (repo / "sub" / "proposal").mkdir(parents=True)
    (repo / "sub" / "proposal" / "x.md").write_text("private\n", encoding="utf-8")
    _git(["add", "-f", "sub/proposal/x.md"], cwd=repo)
    result = _run_audit(repo)
    assert result.returncode == 1, result.stdout
    assert "PRIVATE PROPOSAL FILE STAGED (must stay local): sub/proposal/x.md" in result.stdout


def test_a_downloaded_source_document_is_refused(tmp_path):
    """`sources/` commits only the `.source.md` provenance notes; the documents are
    third-party downloads that stay local, even when force-added past `.gitignore`."""
    repo = _base_repo(tmp_path, "source-pdf")
    (repo / "sources").mkdir()
    (repo / "sources" / "gao-00-000.pdf").write_bytes(b"%PDF-1.7\n")
    _git(["add", "-f", "sources/gao-00-000.pdf"], cwd=repo)
    result = _run_audit(repo)
    assert result.returncode == 1, result.stdout
    assert ("DOWNLOADED SOURCE DOCUMENT STAGED (sources/ commits only *.source.md "
            "notes): sources/gao-00-000.pdf") in result.stdout


def test_a_source_note_and_the_sources_readme_are_allowed(tmp_path):
    repo = _base_repo(tmp_path, "source-note")
    (repo / "sources").mkdir()
    (repo / "sources" / "gao-00-000.source.md").write_text("# note\n", encoding="utf-8")
    (repo / "sources" / "README.md").write_text("# sources\n", encoding="utf-8")
    _git(["add", "sources"], cwd=repo)
    result = _run_audit(repo)
    assert result.returncode == 0, result.stdout
    assert "DOWNLOADED SOURCE DOCUMENT STAGED" not in result.stdout


# ---- staged mode (must stay byte-for-byte unchanged in behaviour) ------------------


def test_staged_mode_fails_on_the_four_planted_violations(tmp_path):
    repo = _base_repo(tmp_path, "staged-fail")
    _plant_four_violations(repo)
    _git(["add", "-A"], cwd=repo)

    result = _run_audit(repo)

    assert result.returncode == 1, result.stdout
    _assert_four_violations_reported(result.stdout)
    assert "AUDIT FAILED" in result.stdout


def test_staged_mode_exits_1_on_an_empty_index(tmp_path):
    repo = _base_repo(tmp_path, "staged-empty")
    result = _run_audit(repo)
    assert result.returncode == 1
    assert "NOTHING STAGED" in result.stdout


def test_staged_mode_passes_on_a_clean_stage(tmp_path):
    repo = _base_repo(tmp_path, "staged-clean")
    (repo / "notes.md").write_text("nothing sensitive here\n", encoding="utf-8")
    _git(["add", "-A"], cwd=repo)
    result = _run_audit(repo)
    assert result.returncode == 0, result.stdout
    assert "AUDIT CLEAN." in result.stdout


# ---- range mode (additive; ruling R6) ----------------------------------------------


def test_range_mode_fails_on_the_same_four_violations(tmp_path):
    repo = _base_repo(tmp_path, "range-fail")
    base = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    _plant_four_violations(repo)
    head = _commit_all(repo, "head")

    result = _run_audit(repo, "--range", f"{base}..{head}")

    assert result.returncode == 1, result.stdout
    _assert_four_violations_reported(result.stdout)
    assert "AUDIT FAILED" in result.stdout


def test_range_mode_passes_on_an_empty_range(tmp_path):
    repo = _base_repo(tmp_path, "range-empty")
    head = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    result = _run_audit(repo, "--range", f"{head}..{head}")
    assert result.returncode == 0, result.stdout
    assert f"range {head}..{head}: 0 file(s)" in result.stdout
    assert "AUDIT CLEAN." in result.stdout


def test_range_mode_does_not_refuse_on_an_empty_index(tmp_path):
    """Check 0's empty-index refusal is staged-mode only (ruling R6): a range has no
    index to be empty, so an empty range must not print "NOTHING STAGED"."""
    repo = _base_repo(tmp_path, "range-no-index-refusal")
    head = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    result = _run_audit(repo, "--range", f"{head}..{head}")
    assert "NOTHING STAGED" not in result.stdout
    assert result.returncode == 0


def test_range_mode_fails_when_head_gitignore_dropped_a_pattern(tmp_path):
    repo = _base_repo(tmp_path, "range-gitignore")
    base = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    (repo / ".gitignore").write_text(
        GOOD_GITIGNORE.replace("*.pem\n", ""), encoding="utf-8",
    )
    head = _commit_all(repo, "drop *.pem")

    result = _run_audit(repo, "--range", f"{base}..{head}")

    assert result.returncode == 1, result.stdout
    assert ".gitignore MISSING: *.pem" in result.stdout


def test_range_mode_reads_gitignore_at_head_not_the_working_tree(tmp_path):
    """Check 4 in range mode must read `.gitignore` as committed at <head> via
    `git show`, never the working tree — a range describes commits, and an uncommitted
    change after <head> is not part of what is being pushed."""
    repo = _base_repo(tmp_path, "range-head-not-worktree")
    base = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    (repo / "notes.md").write_text("trivial change\n", encoding="utf-8")
    head = _commit_all(repo, "trivial")
    # Dirty the working tree after `head` without committing it.
    (repo / ".gitignore").write_text(
        GOOD_GITIGNORE.replace("*.pem\n", ""), encoding="utf-8",
    )

    result = _run_audit(repo, "--range", f"{base}..{head}")

    assert result.returncode == 0, result.stdout
    assert ".gitignore MISSING" not in result.stdout


def test_range_mode_accepts_a_triple_dot_range(tmp_path):
    """`.github/workflows/ci.yml` calls this with `origin/main...HEAD` (three dots);
    `${RANGE##*..}` must still resolve to the second endpoint."""
    repo = _base_repo(tmp_path, "range-triple-dot")
    base = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    _plant_four_violations(repo)
    head = _commit_all(repo, "head")

    result = _run_audit(repo, "--range", f"{base}...{head}")

    assert result.returncode == 1, result.stdout
    _assert_four_violations_reported(result.stdout)
