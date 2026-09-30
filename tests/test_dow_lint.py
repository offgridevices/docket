"""Tests for scripts/dow-lint.py [ruling R2, plan 06 Task 4].

The module is loaded from its hyphenated filename via importlib, since
`scripts/dow-lint.py` is not a valid dotted import path. All fixtures live under
tmp_path — the whitelist lint scans docs/, and a committed fixture naming "DoD" in
prose would itself become a real hit once the scope includes tests/fixtures/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relpath: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dl = _load("dow_lint", "scripts/dow-lint.py")


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "note.md"
    p.write_text(text, encoding="utf-8")
    return p


# ---- the rule: bare DoD / Department of Defense in prose --------------------------------

def test_bare_dod_is_flagged(tmp_path):
    p = _write(tmp_path, "The DoD requires a status-quo alternative.\n")
    problems = dl.check_file(p)
    assert len(problems) == 1
    assert "DoD" in problems[0]


def test_department_of_defense_spelled_out_is_flagged(tmp_path):
    p = _write(tmp_path, "The Department of Defense fields the vehicle.\n")
    problems = dl.check_file(p)
    assert len(problems) == 1


def test_dow_is_never_flagged(tmp_path):
    p = _write(tmp_path, "The Department of War (DoW) is the present-day buyer.\n")
    assert dl.check_file(p) == []


# ---- exemptions -----------------------------------------------------------------------

def test_dodi_directive_is_exempt(tmp_path):
    p = _write(tmp_path, "DoDI 5000.84 requires a status-quo alternative.\n")
    assert dl.check_file(p) == []


def test_dodd_and_dodm_are_exempt(tmp_path):
    p = _write(tmp_path, "See DoDD 5000.01 and DoDM 5200.01 for the chain.\n")
    assert dl.check_file(p) == []


def test_named_dod_phrases_are_exempt(tmp_path):
    for phrase in ("DoD RAI", "DoD CSO"):
        p = _write(tmp_path, f"The {phrase} program governs this submission.\n")
        assert dl.check_file(p) == [], phrase


def test_quoted_document_title_is_exempt(tmp_path):
    p = _write(tmp_path, 'The report is titled "DoD Responsible AI Strategy" here.\n')
    assert dl.check_file(p) == []


def test_italic_document_title_is_exempt(tmp_path):
    p = _write(tmp_path, "The report *DoD Responsible AI Strategy* is cited here.\n")
    assert dl.check_file(p) == []


def test_underscore_italic_is_exempt(tmp_path):
    p = _write(tmp_path, "The report _DoD Responsible AI Strategy_ is cited here.\n")
    assert dl.check_file(p) == []


def test_inline_code_is_exempt(tmp_path):
    p = _write(tmp_path, "The literal string `DoD 2026` appears in the config.\n")
    assert dl.check_file(p) == []


def test_fenced_code_block_is_exempt(tmp_path):
    p = _write(tmp_path, "```\nDoD is mentioned only in this sample output.\n```\n")
    assert dl.check_file(p) == []


def test_blockquote_is_exempt(tmp_path):
    """A verbatim quotation is never rewritten or flagged — this is the single most
    important exemption: a lint that touches a blockquote makes every quoted source
    document unverifiable against its original wording."""
    p = _write(tmp_path, "> The DoD shall provide guidance under this section.\n")
    assert dl.check_file(p) == []


def test_email_is_exempt(tmp_path):
    p = _write(tmp_path, "Contact dod.reviewer@example.mil for DoD@example.mil details.\n")
    # the word "DoD" only appears embedded in the email address, never bare
    assert dl.check_file(p) == []


def test_url_is_exempt(tmp_path):
    p = _write(tmp_path, "See https://example.mil/DoD-page for the source document.\n")
    assert dl.check_file(p) == []


def test_bare_lowercase_domain_is_not_a_hit(tmp_path):
    p = _write(tmp_path, "Submit through www.dod.mil as instructed.\n")
    assert dl.check_file(p) == []


# ---- mixed line: one whitelisted mention, one bare mention ------------------------------

def test_mixed_line_flags_only_the_bare_mention(tmp_path):
    p = _write(
        tmp_path,
        'The "DoD Acquisition Overview" explains this, but DoD policy varies by service.\n',
    )
    problems = dl.check_file(p)
    assert len(problems) == 1


# ---- scope: default is README.md, CONTRIBUTING.md, docs/; sources/ always excluded ---

def test_default_scope_is_the_public_prose(tmp_path, monkeypatch):
    """The default scope is the public prose — README.md, CONTRIBUTING.md and docs/ —
    and nothing else; any other directory must be passed explicitly."""
    monkeypatch.chdir(tmp_path)
    for name in ("docs/design", "docs/research", "other"):
        (tmp_path / name).mkdir(parents=True)
    (tmp_path / "README.md").write_text("root readme\n", encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text("contributing\n", encoding="utf-8")
    (tmp_path / "docs" / "design" / "b.md").write_text("design\n", encoding="utf-8")
    (tmp_path / "docs" / "research" / "c.md").write_text("research\n", encoding="utf-8")
    (tmp_path / "other" / "a.md").write_text("other\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude\n", encoding="utf-8")

    scanned = {p.as_posix() for p in dl._iter_md_files(dl._default_paths())}
    assert scanned == {"README.md", "CONTRIBUTING.md", "docs/design/b.md",
                        "docs/research/c.md"}


def test_sources_is_excluded_even_when_passed_explicitly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "doc.md").write_text("The DoD text lives here.\n", encoding="utf-8")
    assert list(dl._iter_md_files([Path("sources")])) == []


def test_our_own_heading_with_a_bare_mention_is_caught(tmp_path):
    """A non-verbatim, non-whitelisted "DoD" in our own prose (e.g. a heading, not a
    quotation) is a real hit."""
    note = tmp_path / "our-notes.md"
    note.write_text("## Finding — this is DoD-wide, not component-specific\n",
                     encoding="utf-8")
    assert dl.check_file(note) != []


# ---- <!-- dow-lint: allow --> line marker [fix round 1] --------------------------------

def test_allow_marker_exempts_the_line(tmp_path):
    p = _write(
        tmp_path,
        "The DoD requires a status-quo alternative. <!-- dow-lint: allow -->\n",
    )
    assert dl.check_file(p) == []


def test_allow_marker_does_not_exempt_other_lines(tmp_path):
    p = _write(
        tmp_path,
        "The DoD requires a status-quo alternative. <!-- dow-lint: allow -->\n"
        "\n"
        "A second, unmarked paragraph also names the DoD here.\n",
    )
    problems = dl.check_file(p)
    assert len(problems) == 1
    assert "second, unmarked paragraph" in problems[0]


def test_claude_md_passes_the_lint():
    """`CLAUDE.md` is committed agent guidance and is held to the same naming rule as the
    rest of our prose: any "DoD" in it must be in a whitelisted context or carry the
    allow marker."""
    claude_md = ROOT / "CLAUDE.md"
    assert claude_md.exists()
    assert dl.check_file(claude_md) == []


# ---- no --fix flag: whitelist lint, never a replace -------------------------------------

def test_there_is_no_fix_flag(tmp_path):
    p = _write(tmp_path, "The DoD requires a status-quo alternative.\n")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dow-lint.py"), "--fix", str(p)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2  # argparse: unrecognized argument
    assert p.read_text(encoding="utf-8") == "The DoD requires a status-quo alternative.\n"


def test_main_exits_1_on_a_hit_and_0_when_clean(tmp_path):
    hit = _write(tmp_path, "The DoD requires a status-quo alternative.\n")
    assert dl.main([str(hit)]) == 1
    clean = tmp_path / "clean.md"
    clean.write_text("The DoW requires a status-quo alternative.\n", encoding="utf-8")
    assert dl.main([str(clean)]) == 0


def test_json_output(tmp_path, capsys):
    hit = _write(tmp_path, "The DoD requires a status-quo alternative.\n")
    rc = dl.main(["--json", str(hit)])
    assert rc == 1
    out = capsys.readouterr().out
    assert '"ok": false' in out


# ---- real-tree run: report, don't weaken the rule ---------------------------------------

def test_real_tree_dow_lint():
    """Runs the lint over the actual repository's default scope. If this fails, the
    failure output IS the finding (plan 06 Task 4 report) — the fix is to reword the
    offending prose to DoW or a whitelisted context, never to widen the whitelist."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dow-lint.py")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"dow-lint.py found real-tree hits (see plan 06 Task 4 report):\n\n"
        f"{result.stdout}{result.stderr}"
    )
