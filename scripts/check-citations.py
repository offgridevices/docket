#!/usr/bin/env python3
"""Citation checker for deliverable documents and decision records [plan 06 Task 4, fix
round 1, round 2].

Three tiers of check, by file:

DELIVERABLE files — any file carrying the literal `<!-- check-citations: deliverable -->`
marker somewhere in its first 5 lines — get the FULL rule set:
  1. every paragraph with a numeral or a TRIGGER_WORDS mention (GAO, CBO, Army, ...)
     must carry a `[src:]`/`[out:]` tag (numeral exemption below);
  2. every tag's bracket holds a bare path (no ellipsis, no locator) that starts with
     an allowed prefix for its kind and exists on disk;
  3. `[src: pending-decision §N.M]` only where it is allowed (see below);
  4. the overstatement/provider/model-family denylist below.

Files under a STRICT directory (`--strict DIR`, repeatable; none by default) that are NOT
deliverable get: (a) every tag's bracket holds a bare path that exists on disk — same
syntax rule as #2 above, but with NO prefix-allowlist requirement — plus (b) the
denylist (#4).

EVERY OTHER scanned file (`docs/decisions/`, or anything else passed explicitly that
is neither under a strict directory nor marked deliverable) gets (a) ONLY — the
bare-path + exists check, with no prefix-allowlist and no denylist. [round 2] Internal
decision records legitimately discuss, in the abstract, what a phrase like
"deterministic LLM" would require and why it can't be promised; the denylist exists to
keep such phrases out of deliverable-track files, not to police that discussion where it
belongs.

The `[src: pending-decision §N.M]` pseudo-tag marks a decision not yet made. It is
allowed only in a file named with `--allow-pending FILE` (repeatable), or in a paragraph
that also carries a human-readable marker for the same decision, shaped
`[<what> — pending decision §N.M]`, so a reader of the rendered text still sees it.

The denylist (#4) is scanned on every line, including tables and fenced code, in every
file where it applies.

Numeral exemption for rule 1 (stated exactly, since it changes what "needs a citation"
means): a numeral does NOT trigger the citation requirement by itself when it appears
only inside an existing `[src:]`/`[out:]` tag, an ISO date (`2026-09-23`), a clock time
(`12:00`), a section/paragraph reference (`§3.7(f)`, `¶4-2i`), a page locator
(`p. 12`, `pp. 11-13`), a fiscal year (`FY22`), a solicitation code (`26.BX`), a
document identifier shaped like `GAO-23-106549` / `DoDI 5000.84` / `DFARS 252.227-7017`,
or a word-count annotation (`(1,847 words)`). A whole heading paragraph (`#...`) or a
whole blockquote paragraph (every line starts with `>`) is exempt from rule 1
entirely, same as a fenced-code or table paragraph already was. A mention of a
TRIGGER_WORDS entry always requires a citation regardless of any exempt numeral
nearby, because naming the source is itself the claim.

What this script does NOT do: it cannot verify that a quotation is actually present in
the file it cites — only that the path exists. See the "quotations are not verified"
line printed on a clean run; that is why promoted quotations are checked by hand
(plan 06 Task 5 Step 1), not by this tool.

Usage:
    uv run python scripts/check-citations.py [paths...] [--strict DIR]
            [--allow-pending FILE] [--allow-prefix PREFIX]
        default paths: docs/  (pass explicit paths to widen or narrow scope, e.g. so
        CI can also check NOTICE.md or reports/*.md)
        exit 0  clean
        exit 1  prints one block per offending paragraph or line:
                <path>:<line>: <reason>
                  <the paragraph or line, indented>
    uv run python scripts/check-citations.py --json [paths...]
        emits {"ok": bool, "problems": [...], "paragraphs": N, "tags": M} instead

Paths inside `[src:]`/`[out:]` tags are resolved relative to the current working
directory — run this from the repository root, exactly as CI and the pre-commit hook
do (`uv run python scripts/check-citations.py`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

# ---- tag and rule constants [interface, task-4-brief.md] ------------------------------

TAG = re.compile(r"\[(src|out): ([^\]]+)\]")

TRIGGER_WORDS: tuple[str, ...] = (
    "GAO", "CBO", "CRS", "Army", "DoW", "incumbent", "DAOSoft", "NDIA", "OSD",
    "IDA", "DEVCOM", "PAE",
)
TRIGGER_RE = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in TRIGGER_WORDS) + r")\b")

# [ruling: pending-decision exception] Only a file passed with --allow-pending, or a
# paragraph carrying the matching human-readable marker, may satisfy rule 1 with a
# pending placeholder instead of a real path.
PENDING = re.compile(r"\[src: pending-decision (§\d+\.\d+)\]")
PENDING_MARKER = re.compile(r"\[[^\[\]]+ — pending decision (§\d+\.\d+)\]")

# [fix round 1] Rule 1 (the citation requirement) and the prefix-allowlist half of
# rule 2 apply only to DELIVERABLE files. Everything else still gets a bare-path +
# exists check and the denylist (see module docstring).
DELIVERABLE_MARKER = "<!-- check-citations: deliverable -->"

# [pre-flight defect D12] An ellipsis, angle bracket or bare directory is not a path.
_BAD_PATH_CHARS = ("…", "...", "<", ">")

# [D8, adopted] `[src:]` = a committed file the sentence rests on. `[out:]` = a
# generated artefact a number was read out of. `demos/` build/run files are `[src:]`
# material; anything under a demo's own `out/` subtree is generated and must be cited
# as `[out:]`, never `[src:]` — that split is what keeps the two tags meaningful. A
# `sources/*.source.md` sidecar is a valid `[src:]` target in its own right (two
# entries in `sources/` are sidecar-only by design); no special-casing is needed
# because the existence check below already treats it like any other committed file.
ALLOWED_SRC_PREFIXES: tuple[str, ...] = (
    "sources/", "docs/", "src/", "tests/", "scripts/",
)
ALLOWED_SRC_EXACT: tuple[str, ...] = ("NOTICE.md", "README.md")
ALLOWED_OUT_PREFIXES: tuple[str, ...] = ("reports/", "out/")
_DEMOS_OUT_RE = re.compile(r"^demos/[^/]+/out/")

# ---- overstatement denylist [ruling R9] ------------------------------------------------

DENYLIST: tuple[tuple[str, str], ...] = (
    ("GAO-validated", "GAO validated nothing of ours; GAO did not assess or verify the "
        "Army's underlying analytical work (GAO-23-106549 fn. 7, App. I)"),
    ("GAO validated", "GAO validated nothing of ours; GAO did not assess or verify the "
        "Army's underlying analytical work (GAO-23-106549 fn. 7, App. I)"),
    ("validated by GAO", "GAO validated nothing of ours; GAO did not assess or verify "
        "the Army's underlying analytical work (GAO-23-106549 fn. 7, App. I)"),
    ("GAO-approved", "GAO validated nothing of ours; GAO did not assess or verify the "
        "Army's underlying analytical work (GAO-23-106549 fn. 7, App. I)"),
    ("GAO approved", "GAO validated nothing of ours; GAO did not assess or verify the "
        "Army's underlying analytical work (GAO-23-106549 fn. 7, App. I)"),
    ("reproduces GAO's per-question", "GAO-21-460 Fig. 6 is the only published "
        "per-question key; GAO-23-106549 publishes a 3x3 grid and nine findings — any "
        "per-question reading of it is ours"),
    ("GAO's per-question", "GAO-21-460 Fig. 6 is the only published per-question key; "
        "GAO-23-106549 publishes a 3x3 grid and nine findings — any per-question "
        "reading of it is ours"),
    ("deterministic LLM", "the reproducibility promise is architectural, not a claim "
        "about inference"),
    ("reproducible LLM", "the reproducibility promise is architectural, not a claim "
        "about inference"),
    ("deterministic inference", "the reproducibility promise is architectural, not a "
        "claim about inference"),
    ("lacked sensitivity analysis", "GAO credited the combat-effectiveness section for "
        "varying engine power and infantry carried across four vehicles"),
    ("no sensitivity analysis", "GAO credited the combat-effectiveness section for "
        "varying engine power and infantry carried across four vehicles"),
    ("without sensitivity analysis", "GAO credited the combat-effectiveness section for "
        "varying engine power and infantry carried across four vehicles"),
    ("reproduces the Army's", "the analysis cannot be reconstructed; the metrics are "
        "classified"),
)

# [rule 4, "small explicit constant ... keep it short"] Generic AI-provider/product
# names — a functional detection list, not illustrative prose. This is deliberately
# short (ruling R14: no provider, model or hosting commitment) and deliberately does
# NOT include any PRC-origin model family; those come only from the imported
# DOC_SCAN_DENYLIST below, never retyped here.
PROVIDER_NAMES: tuple[str, ...] = (
    "OpenAI", "Anthropic", "Google Gemini", "Azure OpenAI", "Amazon Bedrock",
    "Mistral AI", "Cohere",
)

# ---- model-family denylist: imported, never retyped [rule 4] --------------------------

_family_pattern: re.Pattern | None = None
_family_import_warned = False


def _model_family_pattern() -> re.Pattern | None:
    """Lazily import the PRC-origin model-family scanner from the agent backend.

    Uses DOC_SCAN_DENYLIST rather than the brief's literal `DENYLIST` name: `DENYLIST`
    is tuned to match a single resolved model id and is documented in backend.py as
    producing false positives on ordinary prose (e.g. "a paper by Yi et al."); the
    module deliberately exports a second, prose-tuned pattern, DOC_SCAN_DENYLIST, for
    exactly this "does a document name a denylisted family" check — the same one
    tests/agent/test_backend.py's repo-wide guard already uses. Deviation noted for
    review.
    """
    global _family_pattern, _family_import_warned
    if _family_pattern is not None:
        return _family_pattern
    try:
        from docket.agent.backend import DOC_SCAN_DENYLIST
    except ImportError:
        if not _family_import_warned:
            print(
                "warning: docket.agent.backend is not importable — the PRC-origin "
                "model-family check is skipped this run (rule 4)",
                file=sys.stderr,
            )
            _family_import_warned = True
        return None
    _family_pattern = DOC_SCAN_DENYLIST
    return _family_pattern


# ---- paragraph splitting ---------------------------------------------------------------

def paragraphs(text: str) -> Iterator[tuple[int, str]]:
    """Yield (1-based start line, paragraph text) for each blank-line-delimited block.

    A blank line inside an open fenced code block (```` ``` ````) does not split the
    paragraph — the fence is tracked so a code sample with internal blank lines stays
    one paragraph (and therefore one skip decision for rule 1).
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


def _is_code_paragraph(para: str) -> bool:
    return para.lstrip().startswith("```")


def _is_table_paragraph(para: str) -> bool:
    lines = [line for line in para.split("\n") if line.strip()]
    return len(lines) >= 1 and all(line.strip().startswith("|") for line in lines)


def _is_heading_paragraph(para: str) -> bool:
    return para.lstrip().startswith("#")


def _is_blockquote_paragraph(para: str) -> bool:
    lines = [line for line in para.split("\n") if line.strip()]
    return len(lines) >= 1 and all(line.strip().startswith(">") for line in lines)


def _is_deliverable(rel: str, text: str) -> bool:
    """[fix round 1] A deliverable file gets the full rule set (see module docstring):
    DELIVERABLE_MARKER appears somewhere in its first 5 lines."""
    first_lines = text.split("\n")[:5]
    return any(DELIVERABLE_MARKER in line for line in first_lines)


def _in_denylist_scope(path: Path, deliverable: bool, strict_dirs: tuple[Path, ...]) -> bool:
    """[round 2] The overstatement/provider/model-family denylist (rule 4) applies to
    every deliverable file and to every file under a strict directory. Everything else —
    docs/decisions/ chief among them — gets no denylist check: an internal decision
    record legitimately discusses, in the abstract, what a phrase like "deterministic
    LLM" would require and why it can't be promised; the denylist exists to keep that
    phrase out of deliverables, not to police the discussion where it actually belongs."""
    if deliverable:
        return True
    resolved = path.resolve()
    return any(resolved.is_relative_to(d.resolve()) for d in strict_dirs)


# ---- numeral exemption (stated exactly — see module docstring) ------------------------

_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_CLOCK_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_SECTION_REF_RE = re.compile(r"[§¶]\s?\d+(?:\.\d+)*[a-z]?(?:\([a-z0-9]+\))?", re.IGNORECASE)
_PAGE_REF_RE = re.compile(r"\bpp?\.\s?\d+[\d,\-–\s]*", re.IGNORECASE)
_FY_RE = re.compile(r"\bFY\s?\d{2,4}\b", re.IGNORECASE)
_SOLICITATION_RE = re.compile(r"\b\d{2}\.[A-Z]{2}\b")
_DOC_ID_RE = re.compile(
    r"\b(?:GAO|CBO|CRS|DoDI|DoDD|DoDM|DFARS|R-DFARS|NDAA|ARM\d+[A-Z0-9]*)"
    r"[-\s]?\d[\dA-Za-z.\-]*\b"
)
# [fix round 1] "(1,847 words)" / "(150+ words)" style annotations are exempt everywhere.
_WORD_COUNT_RE = re.compile(r"\(\s*[\d,]+\+?\s*words?\s*\)", re.IGNORECASE)


def _strip_exempt_numerals(para: str) -> str:
    text = TAG.sub(" ", para)
    for pattern in (_ISO_DATE_RE, _CLOCK_RE, _SECTION_REF_RE, _PAGE_REF_RE, _FY_RE,
                    _SOLICITATION_RE, _DOC_ID_RE, _WORD_COUNT_RE):
        text = pattern.sub(" ", text)
    return text


def needs_citation(para: str) -> bool:
    """A digit outside every exemption, or a trigger word anywhere, needs a citation."""
    if TRIGGER_RE.search(para):
        return True
    return bool(re.search(r"\d", _strip_exempt_numerals(para)))


# ---- per-tag validation ------------------------------------------------------------

def _prefix_ok(kind: str, path: str, extra_prefixes: tuple[str, ...] = ()) -> bool:
    if kind == "out":
        return path.startswith(ALLOWED_OUT_PREFIXES) or bool(_DEMOS_OUT_RE.match(path))
    if path in ALLOWED_SRC_EXACT:
        return True
    if path.startswith("demos/"):
        # demos/ is [src:] material as build/run files, never inside its own out/ tree
        return "/out/" not in path
    return path.startswith(ALLOWED_SRC_PREFIXES + tuple(extra_prefixes))


def _pending_allowed(path: Path, para: str, section: str,
                     pending_files: tuple[Path, ...]) -> bool:
    if any(path.resolve() == f.resolve() for f in pending_files):
        return True
    return any(m.group(1) == section for m in PENDING_MARKER.finditer(para))


def _block(path: str, lineno: int, reason: str, body: str) -> str:
    indented = "\n".join("  " + line for line in body.split("\n"))
    return f"{path}:{lineno}: {reason}\n{indented}"


def _check_tag(
    path_obj: Path, rel: str, start_line: int, para: str, m: re.Match, *,
    deliverable: bool, pending_files: tuple[Path, ...] = (),
    extra_prefixes: tuple[str, ...] = (),
) -> str | None:
    """[fix round 1] The bare-path and exists checks apply to every tag, everywhere.
    The prefix-allowlist (`_prefix_ok`) applies only inside a deliverable file — see
    module docstring."""
    kind = m.group(1)
    raw = m.group(2)
    full = m.group(0)

    pending = PENDING.fullmatch(full) if kind == "src" else None
    if pending:
        if _pending_allowed(path_obj, para, pending.group(1), pending_files):
            return None
        return _block(
            rel, start_line,
            f"{full!r} is a pending-decision placeholder outside its allowed locations "
            "(a file passed with --allow-pending, or a paragraph carrying a matching "
            f"'[... — pending decision {pending.group(1)}]' marker)",
            para,
        )

    if any(ch in raw for ch in _BAD_PATH_CHARS) or raw.endswith("/"):
        return _block(
            rel, start_line,
            f"{full!r} is not a resolved path — an ellipsis, placeholder or bare "
            "directory is not a citation",
            para,
        )

    if " " in raw.strip():
        path_part = raw.strip().split(" ", 1)[0]
        locator = raw.strip().split(" ", 1)[1]
        return _block(
            rel, start_line,
            f"{full!r} carries a locator inside the bracket — move it outside: "
            f"[{kind}: {path_part}] {locator}",
            para,
        )

    path = raw.strip()
    if deliverable and not _prefix_ok(kind, path, extra_prefixes):
        return _block(
            rel, start_line,
            f"{full!r} is not under an allowed [{kind}:] prefix",
            para,
        )

    if not Path(path).exists() and not _source_note_exists(path):
        return _block(rel, start_line, f"{full!r} does not exist on disk", para)

    return None


def _source_note_exists(path: str) -> bool:
    """A downloaded document under `sources/` is not committed; its `.source.md`
    provenance note is. The note stands in for the document on a fresh clone."""
    if not path.startswith("sources/") or path.endswith(".source.md"):
        return False
    return Path(path.rsplit(".", 1)[0] + ".source.md").is_file()


# ---- overstatement / provider / model-family scan (every line, incl. tables/code) -------

def _check_denylist_line(rel: str, lineno: int, line: str) -> list[str]:
    problems: list[str] = []
    lower = line.lower()

    for phrase, why in DENYLIST:
        if phrase.lower() in lower:
            problems.append(_block(rel, lineno, f"overstatement {phrase!r} — {why}", line))

    for name in PROVIDER_NAMES:
        if name.lower() in lower:
            problems.append(_block(
                rel, lineno,
                f"names a provider/hosting commitment {name!r} — no provider, model or "
                "hosting commitment in a deliverable [ruling R14]",
                line,
            ))

    family_re = _model_family_pattern()
    if family_re is not None:
        hit = family_re.search(line)
        if hit:
            problems.append(_block(
                rel, lineno, f"names a denylisted model family {hit.group(0)!r}", line,
            ))

    return problems


# ---- file-level check -------------------------------------------------------------------

def _relpath(path: Path) -> str:
    """Path as it should read in a report: relative to the current working directory
    when possible (matching how [src:]/[out:] tags are themselves resolved), else as
    given."""
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def check_file(
    path: Path, *,
    strict_dirs: tuple[Path, ...] = (),
    pending_files: tuple[Path, ...] = (),
    extra_prefixes: tuple[str, ...] = (),
) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    rel = _relpath(path)
    deliverable = _is_deliverable(rel, text)

    problems: list[str] = []

    # [round 2] Rule 4 (overstatement/provider/model-family) applies to deliverable files
    # and strict directories only, on every line including tables and fenced code.
    # docs/decisions/ and everything else get no denylist check.
    if _in_denylist_scope(path, deliverable, strict_dirs):
        for lineno, line in enumerate(text.split("\n"), start=1):
            problems.extend(_check_denylist_line(rel, lineno, line))

    for start_line, para in paragraphs(text):
        for m in TAG.finditer(para):
            problem = _check_tag(
                path, rel, start_line, para, m, deliverable=deliverable,
                pending_files=pending_files, extra_prefixes=extra_prefixes,
            )
            if problem is not None:
                problems.append(problem)

        if not deliverable:
            continue  # rule 1 (the citation requirement) is deliverable-only

        if (_is_code_paragraph(para) or _is_table_paragraph(para)
                or _is_heading_paragraph(para) or _is_blockquote_paragraph(para)):
            continue

        if needs_citation(para) and not TAG.search(para):
            problems.append(_block(
                rel, start_line,
                "no [src: ...] or [out: ...] tag on a paragraph with a numeral or a "
                "trigger word (" + ", ".join(TRIGGER_WORDS) + ")",
                para,
            ))

    return problems


def _stats(text: str) -> tuple[int, int]:
    paras = list(paragraphs(text))
    n_tags = sum(len(TAG.findall(p)) for _, p in paras)
    return len(paras), n_tags


# ---- CLI ----------------------------------------------------------------------------

def _default_paths() -> list[Path]:
    return [Path("docs")]


def _iter_md_files(paths: list[Path]) -> Iterator[Path]:
    seen: set[Path] = set()
    for p in paths:
        candidates = [p] if p.is_file() else sorted(p.rglob("*.md")) if p.is_dir() else []
        for f in candidates:
            resolved = f.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield f


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="check-citations.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths", nargs="*", type=Path,
        help="files or directories to check (default: docs/)",
    )
    parser.add_argument(
        "--strict", action="append", type=Path, default=[], metavar="PATH",
        help="apply the denylist to PATH (a file, or every file under a directory)",
    )
    parser.add_argument(
        "--allow-pending", action="append", type=Path, default=[], metavar="FILE",
        help="allow [src: pending-decision §N.M] anywhere in FILE",
    )
    parser.add_argument(
        "--allow-prefix", action="append", default=[], metavar="PREFIX",
        help="an extra [src:] path prefix allowed inside deliverable files",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    paths = args.paths if args.paths else _default_paths()

    problems: list[str] = []
    total_paragraphs = 0
    total_tags = 0
    for f in _iter_md_files(paths):
        problems.extend(check_file(
            f, strict_dirs=tuple(args.strict), pending_files=tuple(args.allow_pending),
            extra_prefixes=tuple(args.allow_prefix),
        ))
        n_p, n_t = _stats(f.read_text(encoding="utf-8").replace("\r\n", "\n"))
        total_paragraphs += n_p
        total_tags += n_t

    if args.json:
        print(json.dumps({
            "ok": not problems,
            "problems": problems,
            "paragraphs": total_paragraphs,
            "tags": total_tags,
        }, indent=2))
        return 1 if problems else 0

    if problems:
        for block in problems:
            print(block)
            print()
        return 1

    print(
        f"citations OK ({total_paragraphs} paragraphs, {total_tags} tags) — paths "
        "exist; quotations are not verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
