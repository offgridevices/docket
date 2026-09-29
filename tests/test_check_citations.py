"""Tests for scripts/check-citations.py [plan 06 Task 4].

The module is loaded from its hyphenated filename via importlib, since
`scripts/check-citations.py` is not a valid dotted import path.
"""

from __future__ import annotations

import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / "tests" / "fixtures" / "citations" / "good.md"
BAD = ROOT / "tests" / "fixtures" / "citations" / "bad.md"


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = _load("check_citations", "scripts/check-citations.py")

# [fix round 1] Rule 1 (the citation requirement) and the prefix half of rule 2 apply
# only inside a deliverable file. Prepend this to any ad hoc tmp_path fixture that
# means to exercise either of those two rules.
DELIVERABLE = cc.DELIVERABLE_MARKER + "\n\n"


# ---- fixture-driven rule tests ----------------------------------------------------------

def test_good_fixture_passes():
    assert cc.check_file(GOOD) == []


def test_each_bad_paragraph_is_reported():
    problems = cc.check_file(BAD)
    assert len(problems) == 9, problems
    assert any("GAO-validated" in p for p in problems)
    assert any("deterministic LLM" in p for p in problems)
    assert any("lacked sensitivity analysis" in p for p in problems)
    assert any("does not exist" in p for p in problems)
    assert any("ellipsis" in p for p in problems)
    assert any("not under an allowed [out:] prefix" in p for p in problems)
    assert any("pending-decision placeholder outside" in p for p in problems)
    assert sum("no [src:" in p for p in problems) == 2  # the digit and the GAO paragraph


def test_denylist_is_imported_not_retyped():
    """No PRC-origin family name is retyped in this script — checked with the same
    prose-tuned DOC_SCAN_DENYLIST pattern the repo-wide guard
    (tests/agent/test_backend.py) uses, rather than a naive substring search: several
    family names (`yi`, `ling`, `step`) are also ordinary English-word fragments
    ("verify", "handling", "step"), and a naive check would false-positive on this
    script's own comments."""
    pytest.importorskip("docket.agent.backend")
    from docket.agent.backend import DOC_SCAN_DENYLIST

    source = inspect.getsource(cc)
    assert "denylist_families" not in source.lower()
    hit = DOC_SCAN_DENYLIST.search(source)
    assert hit is None, f"names a denylisted model family: {hit.group(0)!r}" if hit else None


def test_clean_run_prints_the_limitation(capsys):
    rc = cc.main([str(GOOD)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "quotations are not verified" in out


def test_help_states_what_the_script_does_not_do(capsys):
    with pytest.raises(SystemExit):
        cc.main(["--help"])
    out = capsys.readouterr().out
    assert "quotation" in out.lower()


# ---- path-rule and prefix tests, isolated from the demos/ tree via tmp_path -------------

def test_out_tag_valid_when_generated_file_exists(tmp_path, monkeypatch):
    """[Step 1] '[out:] pointing at a real generated file' — built under tmp_path rather
    than depending on demos/*/out/ existing (or staying in its current shape), matching
    the brief's own instruction not to couple this fixture to the demos build."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "results.json").write_text("{}\n", encoding="utf-8")
    note = tmp_path / "note.md"
    note.write_text(
        "The run produced 12 findings [out: out/results.json].\n", encoding="utf-8",
    )
    assert cc.check_file(note) == []


def test_out_tag_missing_generated_file_is_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(
        "The run produced 12 findings [out: out/results.json].\n", encoding="utf-8",
    )
    problems = cc.check_file(note)
    assert len(problems) == 1
    assert "does not exist" in problems[0]


def test_src_under_demos_out_subtree_is_rejected(tmp_path, monkeypatch):
    """[D8 ruling] demos/ is [src:] material as build/run files; its own out/ subtree is
    generated and must be cited with [out:], never [src:]. The prefix-allowlist is
    deliverable-gated [fix round 1], so the fixture must be marked deliverable to
    exercise it."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demos" / "a" / "out").mkdir(parents=True)
    (tmp_path / "demos" / "a" / "out" / "results.json").write_text("{}\n", encoding="utf-8")
    note = tmp_path / "note.md"
    note.write_text(
        DELIVERABLE + "The run produced 12 findings [src: demos/a/out/results.json].\n",
        encoding="utf-8",
    )
    problems = cc.check_file(note)
    assert len(problems) == 1
    assert "not under an allowed [src:] prefix" in problems[0]


def test_src_under_demos_out_subtree_is_allowed_outside_a_deliverable(tmp_path, monkeypatch):
    """[fix round 1] The reduced check for non-deliverable files drops the prefix
    allowlist entirely — only bare-path syntax and existence apply."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demos" / "a" / "out").mkdir(parents=True)
    (tmp_path / "demos" / "a" / "out" / "results.json").write_text("{}\n", encoding="utf-8")
    note = tmp_path / "note.md"
    note.write_text(
        "The run produced 12 findings [src: demos/a/out/results.json].\n", encoding="utf-8",
    )
    assert cc.check_file(note) == []


def test_src_under_demos_build_file_is_allowed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demos" / "a").mkdir(parents=True)
    (tmp_path / "demos" / "a" / "run.py").write_text("# run\n", encoding="utf-8")
    note = tmp_path / "note.md"
    note.write_text(
        DELIVERABLE + "The kernel is exercised by 3 runs [src: demos/a/run.py].\n",
        encoding="utf-8",
    )
    assert cc.check_file(note) == []


def test_locator_inside_bracket_is_an_error(tmp_path, monkeypatch):
    """[CARRIES ruling after T3 review] a page/section locator belongs OUTSIDE the
    bracket; one written inside it is refused with a clear message, not silently
    split and accepted."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "doc.pdf").write_text("x", encoding="utf-8")
    note = tmp_path / "note.md"
    note.write_text(
        "The clause is quoted on page 12 [src: sources/doc.pdf p. 12].\n", encoding="utf-8",
    )
    problems = cc.check_file(note)
    assert len(problems) == 1
    assert "locator inside the bracket" in problems[0]


def test_locator_outside_bracket_is_fine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "doc.pdf").write_text("x", encoding="utf-8")
    note = tmp_path / "note.md"
    note.write_text(
        "The clause is quoted on page 12 [src: sources/doc.pdf] p. 12.\n", encoding="utf-8",
    )
    assert cc.check_file(note) == []


# ---- deliverable detection [fix round 1] -------------------------------------------

def test_non_deliverable_file_needs_no_citation_for_a_real_count(tmp_path, monkeypatch):
    """[fix round 1] Rule 1 applies only inside a deliverable file. The very same
    uncited numeral that fails in test_a_real_count_still_needs_a_citation below is
    legal here, because this file is not marked deliverable."""
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("The run detected 9 of the nine findings.\n", encoding="utf-8")
    assert cc.check_file(note) == []


def test_non_deliverable_non_strict_file_gets_path_check_but_not_denylist(
    tmp_path, monkeypatch,
):
    """[round 2] A file outside any strict directory and not deliverable (e.g. a decision record
    under docs/decisions/) still gets the bare-path+exists check, but the
    overstatement/provider/model-family denylist does NOT apply there — an internal
    decision record legitimately discusses, in the abstract, what a phrase like
    "deterministic LLM" would require and why it can't be promised."""
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(
        "The record is GAO-validated [src: does/not/exist.pdf].\n", encoding="utf-8",
    )
    problems = cc.check_file(note)
    assert len(problems) == 1
    assert "does not exist" in problems[0]
    # the paragraph's own prose still says "GAO-validated" in the printed block below
    # the reason line — check the RULE didn't fire, not that the word never appears
    assert not any("overstatement" in p for p in problems)


def test_strict_dir_non_deliverable_file_still_gets_the_denylist(tmp_path, monkeypatch):
    """[round 2] The denylist applies to every file under a strict directory, whether or
    not that specific file is itself marked deliverable — only files outside every
    strict directory (and not marked) are exempt from it."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "strict").mkdir()
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "x.pdf").write_text("x", encoding="utf-8")
    note = tmp_path / "strict" / "checklist.md"
    note.write_text(
        "The record is GAO-validated [src: sources/x.pdf].\n", encoding="utf-8",
    )
    problems = cc.check_file(note, strict_dirs=(tmp_path / "strict",))
    assert len(problems) == 1
    assert any("GAO-validated" in p for p in problems)
    # the same file, with no strict directory named, is not denylist-checked
    assert cc.check_file(note) == []


def test_a_file_without_the_marker_is_not_deliverable_whatever_its_name(tmp_path, monkeypatch):
    """Deliverable status comes from the marker only, never from a path pattern."""
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "volume-2-technical.md"
    note.write_text("The run detected 9 of the nine findings.\n", encoding="utf-8")
    assert cc.check_file(note) == []


def test_allow_prefix_widens_the_deliverable_prefix_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "extra").mkdir()
    (tmp_path / "extra" / "doc.md").write_text("x", encoding="utf-8")
    note = tmp_path / "note.md"
    note.write_text(
        DELIVERABLE + "The count is 3 [src: extra/doc.md].\n", encoding="utf-8",
    )
    problems = cc.check_file(note)
    assert len(problems) == 1 and "not under an allowed [src:] prefix" in problems[0]
    assert cc.check_file(note, extra_prefixes=("extra/",)) == []


def test_marker_outside_first_five_lines_does_not_count(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    padding = "\n".join(f"filler line {i}" for i in range(6))
    note.write_text(
        padding + "\n" + cc.DELIVERABLE_MARKER + "\nThe run detected 9 findings.\n",
        encoding="utf-8",
    )
    assert cc.check_file(note) == []


# ---- numeral exemption: dates, section refs, page refs, doc ids, trigger words ----------

@pytest.mark.parametrize("sentence", [
    "The window closes 2026-10-07 12:00 and reopens the next cycle.",
    "See §3.7(f) for the mandatory uploads list.",
    "The finding sits at pp. 11-13 of the instructions.",
    "FY22 NDAA §234(d) sets the statutory criteria.",
    "Solicitation 26.BX is the governing document.",
    "DoDI 5000.84 requires a status-quo alternative.",
    "The draft is on track (1,847 words) for the seven-page limit.",
    "The revision trimmed the draft (150+ words) before submission.",
])
def test_exempt_numerals_need_no_citation(sentence, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(DELIVERABLE + sentence + "\n", encoding="utf-8")
    assert cc.check_file(note) == [], sentence


def test_a_real_count_still_needs_a_citation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(
        DELIVERABLE + "The run detected 9 of the nine findings.\n", encoding="utf-8",
    )
    problems = cc.check_file(note)
    assert len(problems) == 1
    assert "no [src:" in problems[0]


def test_trigger_word_alone_needs_a_citation_even_with_no_digit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(
        DELIVERABLE + "The incumbent's approach differs from ours.\n", encoding="utf-8",
    )
    problems = cc.check_file(note)
    assert len(problems) == 1


# ---- code fences, tables, headings and blockquotes are skipped for rule 1, never for
# ---- rule 4 [heading/blockquote exemption added in fix round 1] ------------------------

def test_fenced_code_block_is_exempt_from_the_citation_rule(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(DELIVERABLE + "```\nGAO found 47 issues.\n```\n", encoding="utf-8")
    assert cc.check_file(note) == []


def test_table_row_is_exempt_from_the_citation_rule(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(
        DELIVERABLE + "| Vol | Pages |\n|---|---|\n| 2 | 7 |\n", encoding="utf-8",
    )
    assert cc.check_file(note) == []


def test_heading_is_exempt_from_the_citation_rule(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(
        DELIVERABLE + "## Finding 7 — GAO found 47 issues\n", encoding="utf-8",
    )
    assert cc.check_file(note) == []


def test_blockquote_is_exempt_from_the_citation_rule(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(
        DELIVERABLE + "> GAO found 47 issues in the 2026 record.\n", encoding="utf-8",
    )
    assert cc.check_file(note) == []


# [round 2] The denylist applies only under a strict directory or inside a deliverable
# file, so these tests name a tmp_path directory as strict.

def test_denylist_phrase_in_a_table_caption_is_still_caught(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "strict").mkdir()
    note = tmp_path / "strict" / "note.md"
    note.write_text(
        "| Result | Status |\n|---|---|\n| GAO-validated | done |\n", encoding="utf-8",
    )
    problems = cc.check_file(note, strict_dirs=(tmp_path / "strict",))
    assert any("GAO-validated" in p for p in problems)


def test_denylist_phrase_in_a_fenced_code_block_is_still_caught(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "strict").mkdir()
    note = tmp_path / "strict" / "note.md"
    note.write_text("```\n# deterministic LLM output\n```\n", encoding="utf-8")
    problems = cc.check_file(note, strict_dirs=(tmp_path / "strict",))
    assert any("deterministic LLM" in p for p in problems)


def test_denylist_does_not_apply_outside_strict_dirs_or_deliverable(tmp_path, monkeypatch):
    """[round 2] The same overstatement, in the same shape, in a file that is neither
    under a strict directory nor deliverable — e.g. docs/decisions/ — is not flagged."""
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("```\n# deterministic LLM output\n```\n", encoding="utf-8")
    assert cc.check_file(note) == []


# ---- provider-name denylist (kept out of any committed fixture / test name) -------------

def test_provider_name_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "strict").mkdir()
    note = tmp_path / "strict" / "note.md"
    provider = cc.PROVIDER_NAMES[0]
    note.write_text(f"The demo calls {provider} for completions.\n", encoding="utf-8")
    problems = cc.check_file(note, strict_dirs=(tmp_path / "strict",))
    assert any("provider/hosting commitment" in p for p in problems)


def test_model_family_denylist_is_enforced_via_the_imported_pattern(tmp_path, monkeypatch):
    """Builds the probe text from the imported family list at runtime so no denylisted
    name is ever retyped in this test file or committed to a fixture (that would trip
    tests/agent/test_backend.py's own repo-wide guard)."""
    pytest.importorskip("docket.agent.backend")
    from docket.agent.backend import DENYLIST_FAMILIES

    monkeypatch.chdir(tmp_path)
    (tmp_path / "strict").mkdir()
    family = DENYLIST_FAMILIES[0]
    note = tmp_path / "strict" / "note.md"
    note.write_text(f"The backend defaults to {family}-8b for this run.\n", encoding="utf-8")
    problems = cc.check_file(note, strict_dirs=(tmp_path / "strict",))
    assert any("denylisted model family" in p for p in problems)


# ---- pending-decision exception ----------------------------------------------------------

def test_pending_decision_allowed_in_a_named_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "people.md"
    note.write_text("Resume to follow [src: pending-decision §14.4].\n", encoding="utf-8")
    assert cc.check_file(note, pending_files=(note,)) == []


def test_pending_decision_allowed_beside_its_readable_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(
        "Open: [reviewer — pending decision §2.1] [src: pending-decision §2.1].\n",
        encoding="utf-8",
    )
    assert cc.check_file(note) == []
    # a marker for a different decision does not excuse this one
    note.write_text(
        "Open: [reviewer — pending decision §2.2] [src: pending-decision §2.1].\n",
        encoding="utf-8",
    )
    assert len(cc.check_file(note)) == 1


def test_pending_decision_rejected_elsewhere(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("Resume to follow [src: pending-decision §14.4].\n", encoding="utf-8")
    problems = cc.check_file(note)
    assert len(problems) == 1
    assert "pending-decision placeholder outside" in problems[0]


# ---- real-tree run: report, don't weaken the rule ---------------------------------------

def test_real_tree_check_citations():
    """Runs the checker over the actual repository (default scope: docs/). If this
    fails, the failure output IS the finding — the fix is to add citations to the
    offending prose, never to loosen a rule in this script."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-citations.py")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        "check-citations.py found real-tree citation problems (see plan 06 Task 4 "
        f"report):\n\n{result.stdout}{result.stderr}"
    )
