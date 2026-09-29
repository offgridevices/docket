"""Run every demo present in this tree into one output root, and print a manifest.

    uv run python -m demos.run_all [--out ROOT]

Default `--out` is the repository root, so a bare invocation reproduces the committed
layout: `demos/<name>/out/` for every demo, exactly as `git status` shows it today. Every
demo's own `run(out_dir)` is called with `<root>/demos/<name>/out`, honouring the `--out`
contract `scripts/determinism-check.sh` and `docket.kernel.verify.verify_determinism`
build on (design §9.6; §11 M2 row — "determinism tests in CI").

A demo whose `run` module does not exist yet — `demos.b_omfv_2019_2023` at the time this
was written (plan 05 Task 5 has landed `build.py` but not `run.py`) — is skipped, with a
printed reason, rather than failing the whole run: the point of this script is to prove
`reports/phase1-validation.md` is a separate artefact (plan 05 Task 8), written
under the same `--out` root by whatever produces it; this script does not write it and
does not assume it exists.

A demo whose module *does* import but whose `run(out_dir)` raises is a different case
entirely — a real bug, not an absent demo — so it is not caught and swallowed the way
`ModuleNotFoundError` is: `run_all` prints one line to stderr naming the demo and the
exception (`run_all: demo <name> FAILED: <ExceptionType>: <message>`) and re-raises, so
CI's exit code stays non-zero and the cause is legible in the log instead of an
unlabelled traceback that looks like any other crash in the process.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Demo package names, in a fixed order — not a directory listing, so a stray directory
# under demos/ (__pycache__, a future scratch directory) can never silently become "a
# demo", and the order a manifest prints in never depends on filesystem ordering.
DEMOS = [
    "a_cbo_gcv_2013",
    "ablation",
    "b_omfv_2019_2023",
    "budget_books",
    "control_gao_15_548",
    "validation_gao_21_460",
]

# Only `control_gao_15_548.run` declares a `RESULTS_FILE` constant today (its own module
# docstring: "plan 05 Task 8's run_all reads each demo's declared file, so each demo has
# to name one"); the other three demos write a results file under a literal name that is
# not (yet) exported as a constant. Read the constant when a demo's `run` module has one
# — so a future demo that adds it is picked up automatically — and fall back to this
# table, which mirrors each of the other demos' own `run.py`, otherwise. This table is
# not touched when a demo's own file changes its filename; the demo's `run.py` is the
# source of truth and this is a bridge until every demo names its own constant.
DEFAULT_RESULTS_FILE = {
    "a_cbo_gcv_2013": "results.json",
    "budget_books": "conflicts.json",
    "validation_gao_21_460": "agreement.json",
}


def _out_dir(root: Path, name: str) -> Path:
    return root / "demos" / name / "out"


def run_all(root: Path) -> list[dict]:
    """Run every present demo into `<root>/demos/<name>/out`.

    Returns one manifest entry per name in `DEMOS`, in order:
    `{"demo": name, "present": False, "reason": "..."}` for a demo whose `run` module
    does not exist, or `{"demo": name, "present": True, "outDir": "...",
    "resultsFile": "..." | None}` for one that ran.
    """
    root = Path(root)
    manifest: list[dict] = []
    for name in DEMOS:
        try:
            module = importlib.import_module(f"demos.{name}.run")
        except ModuleNotFoundError as e:
            manifest.append({
                "demo": name, "present": False,
                "reason": f"demos.{name}.run is absent ({e})",
            })
            continue
        out_dir = _out_dir(root, name)
        try:
            module.run(out_dir)
        except Exception as e:
            # A demo module that exists but crashes at `run()` time is categorically
            # different from one that is merely absent (the `ModuleNotFoundError`
            # branch above): it is a real bug, and CI must show it loudly rather than
            # produce a bare, unlabelled traceback that looks identical to any other
            # crash in the process. Print the offending demo's name before re-raising —
            # `run_all`'s own exit code stays non-zero (main's `raise SystemExit`,
            # or a bare pytest failure), this only adds the one line naming the cause.
            print(
                f"run_all: demo {name} FAILED: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            raise
        results_file = getattr(module, "RESULTS_FILE", None) or DEFAULT_RESULTS_FILE.get(name)
        manifest.append({
            "demo": name,
            "present": True,
            "outDir": str(out_dir),
            "resultsFile": str(out_dir / results_file) if results_file else None,
        })
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run every present demo into one output root."
    )
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT,
        help="Output root; demos land at <root>/demos/<name>/out (default: repo root, "
             "i.e. the committed layout)",
    )
    return parser


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv[1:])
    manifest = run_all(Path(args.out).resolve())
    for entry in manifest:
        if entry["present"]:
            print(f"{entry['demo']}: ok — {entry['resultsFile']}")
        else:
            print(f"{entry['demo']}: skipped — {entry['reason']}")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
