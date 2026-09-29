"""Validate the budget-book record and write down every value conflict the kernel finds.

    uv run python -m demos.budget_books.run [out_dir]

Nothing here reads a clock, a network or an environment variable, and no path written
into `out/` is absolute — so two runs produce byte-identical output.

This demonstration stops at `validate`. It never calls `readiness_report`, never drives a
lifecycle gate and never evaluates anything, because there is nothing here to evaluate:
the record is an ingestion of seven budget books and three published documents, and its
only purpose is the `value-conflict` rule. The register is deliberately uncited by any
claim, so `silent-omission` fires once per evidence object and the record is *not* ready.
That is honest and is stated in the README rather than hidden.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from demos.budget_books.build import NOW, build
from docket.kernel.validate import validate

SEED = 20260905
OUT = Path(__file__).parent / "out"
POLICY = "pol-budget"
EPISODE = "ep-budget"


def _rows_by_key(g) -> dict[tuple[str, str], list[dict]]:
    """Every assertion in the episode's register, grouped by (subject, field).

    Read back out of the graph rather than out of `build.ASSERTIONS`, so the table in
    `report.md` is what the store holds and what the rule saw.
    """
    rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for ev_id in g.get(EPISODE)["evidenceRegister"]:
        ev = g.get(ev_id)
        for a in ev.get("assertions") or []:
            rows[(a["subject"], a["field"])].append(
                {"evidence": ev_id, "value": a["value"], "locator": a["locator"]})
    return rows


def _key_of(finding: dict) -> tuple[str, str]:
    """The (subject, field) a value-conflict finding is about.

    Both `value-conflict` messages open with `<subject>.<field> `, written by
    `docket.kernel.policy_rules.value_conflicts`. Splitting the kernel's own text keeps
    this file from re-deriving which pairs conflict.
    """
    subject_field = finding["message"].split(" ", 1)[0]
    subject, _, field = subject_field.rpartition(".")
    return subject, field


def _report(conflicts: list[dict], rows: dict[tuple[str, str], list[dict]],
            other: dict[str, int]) -> str:
    internal = [c for c in conflicts if c["rule"] == "value-conflict-internal"]
    across = [c for c in conflicts if c["rule"] == "value-conflict"]

    out: list[str] = [
        "# Value conflicts in the public OMFV/XM30 budget record",
        "",
        "A *value conflict* here is one thing — one line item, one date, one definition —",
        "stated at two different values, either on two pages of the same document or",
        "across two documents. The kernel reports the disagreement and names every page it",
        "read. It does not decide which figure is right, and neither does this file.",
        "",
        f"Kernel input: the record built by `demos/budget_books/build.py`, `now` = {NOW}.",
        "",
        "Locators are dual. `volume p. 3d-268` is the page number printed in the footer of",
        "the source volume; `extract PDF p. 74` is where that sheet sits in the committed",
        "extract. Open the extract at the extract page and read the volume page off the",
        "bottom of the sheet.",
        "",
        f"## Conflicts within one document — {len(internal)} (blocking)",
        "",
    ]
    if not internal:
        out += ["None.", ""]
    for i, c in enumerate(internal, 1):
        subject, field = _key_of(c)
        documents = ", ".join(f"`{o}`" for o in c["objects"])
        out += [f"### {i}. `{subject}.{field}` — within {documents}", "",
                "| Document | Value | Locator |", "|---|---|---|"]
        # Only the pages of the document that contradicts itself. Every other page that
        # states this subject is listed under the cross-document conflict below, which
        # fires on the same key.
        out += [f"| `{r['evidence']}` | {r['value']} | {r['locator']} |"
                for r in rows[(subject, field)] if r["evidence"] in c["objects"]]
        out += [""]

    out += [f"## Conflicts across documents — {len(across)} (warning)", ""]
    if not across:
        out += ["None.", ""]
    for i, c in enumerate(across, 1):
        subject, field = _key_of(c)
        out += [f"### {i}. `{subject}.{field}`", "",
                "| Document | Value | Locator |", "|---|---|---|"]
        out += [f"| `{r['evidence']}` | {r['value']} | {r['locator']} |"
                for r in rows[(subject, field)]]
        out += [""]

    singles = sorted(k for k, v in rows.items()
                     if len({str(r["value"]) for r in v}) == 1)
    out += ["## Subjects the rule read and did not report", "",
            "A subject with one value across every page that states it is not a conflict.",
            "`omfv-mta-total-cost-fy21-25` is here on purpose: it is a five-year window,",
            "not the four-year one, and keeping it under its own subject key is what stops",
            "the rule reporting a scope difference as a disagreement.",
            "`omfv-concept-design` is here for the opposite reason: it is the Army",
            "statement most directly comparable with the award date, it is uncontested,",
            "and the award-date conflict above should be read beside it.", ""]
    for s, f in singles:
        out += [f"### `{s}.{f}`", "", "| Document | Value | Locator |", "|---|---|---|"]
        out += [f"| `{r['evidence']}` | {r['value']} | {r['locator']} |"
                for r in rows[(s, f)]]
        out += [""]
    out += ["",
            "## Everything else the validator said", "",
            "This record is an ingestion, not a readiness record. No claim cites any",
            "register entry, so `silent-omission` fires once per evidence object and the",
            "record is deliberately not ready.", "",
            "| Rule | Findings |", "|---|---|"]
    out += [f"| `{rule}` | {count} |" for rule, count in sorted(other.items())]
    out += [""]
    return "\n".join(out)


def run(out_dir: Path = OUT) -> dict:
    """Build, validate, write the conflicts. Returns the summary the tests read."""
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    g = build()
    findings = validate(g, g.get(POLICY))
    conflicts = [f.to_dict() for f in findings if f.rule.startswith("value-conflict")]
    rows = _rows_by_key(g)
    for c in conflicts:
        # The kernel's `message` lists every row for the key, including rows from
        # documents other than the ones in `objects` — right for a cross-document
        # finding, misleading for an internal one, where "within one document" is the
        # whole claim. `rows` is the same list filtered to the documents the finding
        # actually names, so a consumer of the JSON gets the set the rule reported on.
        c["rows"] = [r for r in rows[_key_of(c)] if r["evidence"] in c["objects"]]
    internal = [c for c in conflicts if c["rule"] == "value-conflict-internal"]
    across = [c for c in conflicts if c["rule"] == "value-conflict"]
    other = dict(Counter(f.rule for f in findings if not f.rule.startswith("value-conflict")))
    subjects = sorted({f"{s}.{f}" for s, f in (_key_of(c) for c in conflicts)})

    payload = {
        "now": NOW,
        "seed": SEED,
        "policy": POLICY,
        "episode": EPISODE,
        "conflicts": conflicts,
        "internal": internal,
        "across": across,
        "subjects": subjects,
        "rows": {f"{s}.{f}": v for (s, f), v in sorted(rows.items())},
        "otherFindings": dict(sorted(other.items())),
        "blockers": sorted({f.rule for f in findings if f.severity == "blocking"}),
    }
    (out_dir / "conflicts.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")
    (out_dir / "report.md").write_text(
        _report(conflicts, rows, other), encoding="utf-8", newline="\n")
    g.save(out_dir / "graph")

    return {"graph": g, "findings": findings, "conflicts": conflicts, "internal": internal,
            "across": across, "subjects": subjects, "other_findings": other,
            "outDir": str(out_dir)}


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else OUT
    outcome = run(out_dir)
    print(json.dumps({
        "internal": [c["message"] for c in outcome["internal"]],
        "across": [c["message"].split(":")[0] for c in outcome["across"]],
        "subjects": outcome["subjects"],
        "other_findings": dict(sorted(outcome["other_findings"].items())),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
