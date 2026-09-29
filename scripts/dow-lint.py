#!/usr/bin/env python3
"""DoW naming lint [ruling R2, pre-flight defect D4, plan 06 Task 4, fix round 1].

The buyer is "Department of War (DoW)" in present-day prose; "DoD" survives only
inside document titles, clause/statute/standard citations, filenames, URLs, emails,
fenced code and verbatim block quotes (CLAUDE.md; design frontend spec §9). This is a
**whitelist lint, never a replace** — it reports; it never rewrites, and there is
deliberately no `--fix` flag. Rewriting a quotation would make the quoted document
unverifiable against its source, which is worse than the naming slip it would fix.

Whitelisted (never flagged):
  - "DoDI ...", "DoDD ...", "DoDM ..." — these are single tokens (no word boundary
    between "DoD" and the following letter), so the bare-word pattern never matches them
  - the named phrases "DoD RAI", "DoD CSO"
  - a "DoD"/"Department of Defense" occurrence inside a double-quoted span, an italic
    span (*...* or _..._), or inline code (`...`) on the same line — quoted document
    titles and verbatim text are never touched
  - an occurrence inside an email address or a URL
  - an entire line inside a fenced code block (``` ... ```) or a Markdown blockquote
    (a line starting with `>`)
  - [fix round 1] any line carrying the literal marker `<!-- dow-lint: allow -->`
    anywhere on it — a one-line, explicit, reviewable override for a line that states
    the naming rule itself (e.g. CLAUDE.md) rather than slipping on it. The marker
    exempts the whole line it appears on, nothing else on the page.

Scope: default paths are README.md, CONTRIBUTING.md and docs/ — the public prose —
with `sources/` always excluded even if passed explicitly. Verbatim government text is
expected to sit in blockquotes or quotes, which this lint leaves alone regardless of
directory. Pass explicit paths to check anything else.

Usage:
    uv run python scripts/dow-lint.py [paths...]
        default: README.md CONTRIBUTING.md docs/ (sources/ excluded);
        pass explicit paths to check anything else
        exit 0  clean
        exit 1  prints one line per hit: <path>:<line>: <reason>
    uv run python scripts/dow-lint.py --json [paths...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

DOD_RE = re.compile(r"\bDoD\b")
DEPT_RE = re.compile(r"\bDepartment of Defense\b")

WHITELIST_PHRASE_RE = re.compile(r"\bDoD (?:RAI|CSO)\b")
# Spans are matched per-PARAGRAPH, not per-line (see `paragraphs()`), so a quotation
# or italic run that wraps across a line break inside the same paragraph is still
# recognised as one span — a real false positive this fixed (a rubric quotation
# split by hard wrap in docs/design/phase1-design.md).
QUOTE_RE = re.compile(r'"[^"]*"')
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)[^*]+\*(?!\*)|(?<!_)_(?!_)[^_]+_(?!_)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://\S+")

ALLOW_MARKER = "<!-- dow-lint: allow -->"

DEFAULT_SCOPE = ("README.md", "CONTRIBUTING.md", "docs")
EXCLUDED_PREFIXES = ("sources",)


def _excluded(rel: str) -> bool:
    return any(rel == d or rel.startswith(d + "/") for d in EXCLUDED_PREFIXES)


def _default_paths() -> list[Path]:
    return [Path(name) for name in DEFAULT_SCOPE if Path(name).exists()]


def _iter_md_files(paths: list[Path]) -> Iterator[Path]:
    seen: set[Path] = set()
    for p in paths:
        candidates = [p] if p.is_file() else sorted(p.rglob("*.md")) if p.is_dir() else []
        for f in candidates:
            rel = f.as_posix()
            if _excluded(rel):
                continue
            resolved = f.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield f


def paragraphs(text: str) -> Iterator[tuple[int, str]]:
    """Yield (1-based start line, paragraph text) for each blank-line-delimited block.

    A blank line inside an open fenced code block does not split the paragraph, so a
    code sample with internal blank lines stays one paragraph (and one skip decision).
    """
    lines = text.split("\n")
    buf: list[str] = []
    start = 0
    in_fence = False
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        blank = stripped == "" and not in_fence
        if blank:
            if buf:
                yield start, "\n".join(buf)
                buf = []
        else:
            if not buf:
                start = i
            buf.append(line)
    if buf:
        yield start, "\n".join(buf)


def _spans(regex: re.Pattern, text: str) -> list[tuple[int, int]]:
    return [m.span() for m in regex.finditer(text)]


def _in_any_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _paragraph_hits(para: str) -> list[re.Match]:
    """Return the offending DoD/Department-of-Defense matches in one paragraph, after
    excluding every whitelisted span. Spans are computed over the whole paragraph
    (not line by line) so a quotation or italic run that wraps across a line break
    stays recognised as one span."""
    exempt_spans = (
        _spans(QUOTE_RE, para)
        + _spans(ITALIC_RE, para)
        + _spans(INLINE_CODE_RE, para)
        + _spans(EMAIL_RE, para)
        + _spans(URL_RE, para)
        + _spans(WHITELIST_PHRASE_RE, para)
    )
    hits: list[re.Match] = []
    for m in list(DOD_RE.finditer(para)) + list(DEPT_RE.finditer(para)):
        if _in_any_span(m.start(), exempt_spans):
            continue
        hits.append(m)
    return hits


def check_file(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    rel = path.as_posix()

    problems: list[str] = []
    for start_line, para in paragraphs(text):
        if para.lstrip().startswith("```"):
            continue                                   # fenced code block
        if para.split("\n", 1)[0].strip().startswith(">"):
            continue                                   # Markdown blockquote
        for m in _paragraph_hits(para):
            lineno = start_line + para.count("\n", 0, m.start())
            line_text = para.split("\n")[para.count("\n", 0, m.start())]
            if ALLOW_MARKER in line_text:               # [fix round 1] explicit override
                continue
            problems.append(
                f"{rel}:{lineno}: {m.group(0)!r} outside a whitelisted context "
                f"— {line_text.strip()}"
            )
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="dow-lint.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths", nargs="*", type=Path,
        help="files or directories to check (default: README.md CONTRIBUTING.md "
             "docs/; sources/ is always excluded). Pass explicit paths to check "
             "anything else.",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    paths = args.paths if args.paths else _default_paths()

    problems: list[str] = []
    for f in _iter_md_files(paths):
        problems.extend(check_file(f))

    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
        return 1 if problems else 0

    if problems:
        for line in problems:
            print(line)
        return 1

    print("dow-lint OK — no bare DoD / Department of Defense outside a whitelisted context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
