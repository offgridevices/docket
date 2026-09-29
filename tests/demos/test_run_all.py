"""`demos/run_all.py` regenerates every demo; `reports/generate.py` writes the Phase I
validation report from what it regenerated. This module proves the two link up: a fresh
build into a scratch directory produces the same eight-section report that is committed
at `reports/phase1-validation.md`, byte for byte, and every numeral the report
carries traces back to a value some demo's own `out/*.json` actually holds.

Building all six demos is the slow part of this file (`demos.run_all.run_all` runs every
demo's `run()` from scratch) — done exactly once, in a module-scoped fixture, and reused
by every test below rather than repeated per test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from demos.run_all import run_all
from reports.generate import DENYLIST, PROVIDER_NAMES, REQUIRED, SECTION_HEADINGS, write_report

REPO = Path(__file__).resolve().parents[2]
COMMITTED = REPO / "reports" / "phase1-validation.md"

# Numerals that legitimately appear in the rendered report's prose without being a
# substring of any `out/*.json` file — each is a section-reference into a design or
# ledger document, not a result statistic, so there is no artefact for it to trace to.
# Every other numeral in the report (every count, ratio, hash and rating) is checked
# against the concatenated text of every demo's own `out/**/*.json`.
STRUCTURAL_NUMERALS: frozenset[str] = frozenset({
    "9.2",  # "design §9.2" — the procedure section, cited by number, not a result
    "9.6",  # "design §9.6" — the "what Phase I proves" section, quoted verbatim in §8
})

_NUMERAL_RE = re.compile(r"-?\d+\.\d+|-?\d+/\d+|\b\d+\b")


@pytest.fixture(scope="module")
def built_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Every demo's `out/`, freshly built into a scratch root, plus the report
    generated from that same root — exactly what `git status` should show as unchanged
    against the committed tree."""
    root = tmp_path_factory.mktemp("docket-run-all")
    run_all(root)
    write_report(root)
    return root


def _committed_text() -> str:
    return COMMITTED.read_text(encoding="utf-8")


def _fresh_text(built_root: Path) -> str:
    return (built_root / "reports" / "phase1-validation.md").read_text(
        encoding="utf-8"
    )


def test_report_carries_all_eight_section_headings(built_root: Path) -> None:
    text = _fresh_text(built_root)
    assert len(SECTION_HEADINGS) == 8
    for heading in SECTION_HEADINGS:
        assert heading in text, heading


def test_committed_report_equals_a_fresh_regeneration(built_root: Path) -> None:
    """The committed `reports/phase1-validation.md` is not hand-edited: it is
    exactly what `demos.run_all.run_all` + `reports.generate.write_report` produce from a
    clean build, byte for byte. A mismatch here means the report is stale — regenerate
    it with `uv run python -m demos.run_all && uv run python -m reports.generate`."""
    assert _committed_text() == _fresh_text(built_root)


def test_the_second_reader_row_is_still_a_placeholder() -> None:
    """The one placeholder the plan allows (design §9.2 step 4): reading is a human
    act, and no agent may fill this row in on Shreyash's behalf."""
    assert "pending: Shreyash" in _committed_text()


def test_no_overstatement_and_every_required_disclosure_is_present(
    built_root: Path,
) -> None:
    text = _fresh_text(built_root).lower()
    hits = [phrase for phrase, _why in DENYLIST if phrase.lower() in text]
    assert hits == [], hits
    provider_hits = [name for name in PROVIDER_NAMES if name.lower() in text]
    assert provider_hits == [], provider_hits
    missing = [phrase for phrase in REQUIRED if phrase.lower() not in text]
    assert missing == [], missing


def _json_haystack(root: Path) -> str:
    """Every byte of every JSON file any demo wrote under `root` — the only material a
    numeral in the report is allowed to have come from."""
    parts = []
    for path in sorted((root / "demos").rglob("*.json")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_every_numeral_traces_to_a_results_file(built_root: Path) -> None:
    """[design §9.6 rule; plan 05 Task 8] Every numeral in the report's body is read
    out of a JSON field, never typed by hand. Proof, mechanically: strip Markdown
    headings (a heading may carry a structural section number, e.g. "## 4."), collect
    every remaining numeral token, and require each to appear verbatim somewhere in the
    JSON every demo wrote for this same build — the same substring relationship the
    generator itself relies on, since it only ever formats a loaded `json.load` value or
    a `len()`/pairing over one, never a rounded or re-derived figure.

    `STRUCTURAL_NUMERALS` is the complete, documented list of exceptions: numerals that
    are a citation into a design or ledger document by section number, not a result.
    """
    text = _fresh_text(built_root)
    body = "\n".join(
        line for line in text.split("\n") if not line.lstrip().startswith("#")
    )
    haystack = _json_haystack(built_root)
    tokens = set(_NUMERAL_RE.findall(body))
    unexplained = sorted(
        t for t in tokens if t not in STRUCTURAL_NUMERALS and t not in haystack
    )
    assert unexplained == [], (
        f"numerals with no source in any out/*.json and not in STRUCTURAL_NUMERALS: "
        f"{unexplained}"
    )


def test_every_demo_actually_built(built_root: Path) -> None:
    """Sanity check on the fixture itself: a demo silently failing to build (skipped,
    not run) would otherwise make every test above pass vacuously against a report
    missing that demo's numbers."""
    for name in ("a_cbo_gcv_2013", "ablation", "b_omfv_2019_2023", "budget_books",
                 "control_gao_15_548", "validation_gao_21_460"):
        out_dir = built_root / "demos" / name / "out"
        assert out_dir.is_dir(), name
        assert any(out_dir.glob("*.json")), name
