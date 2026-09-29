"""One-off: derive src/docket/standard/research-standards-36.yaml from the local research
library master (gitignored). Usage: uv run python scripts/derive_standard.py"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

SRC = Path("library/gao/derived/gao-research-standards-master-36.yaml")
GT = Path("library/gao/derived/gao-23-106549-ground-truth.yaml")
OUT = Path("src/docket/standard/research-standards-36.yaml")

BAND_ORDER = {"design": 0, "execution": 1, "presentation": 2}

CLUSTER_OF: dict[str, str] = {}

# Wording blocks copied onto each question, and the keys carried out of each.
# spine_2015 also carries `na_flag_warning` and `note` where the master has them: both
# exist only to stop a reader misreading the `na_flag` we are carrying, so dropping them
# would make the flag say something GAO did not say (see EXE-4).
WORDING_KEYS = {
    "predecessor_2006": ("ref", "verbatim"),
    "predecessor_2010": ("ref", "verbatim"),
    "spine_2015": ("ref", "verbatim", "na_flag", "na_flag_warning", "note"),
}

# Applied the 36 questions but not listed in the master's `sources:` block; they appear
# only in per-row usage notes, so we record that rather than inventing a page.
EXTRA_SOURCES = ["GAO-16-86", "GAO-24-106982"]
EXTRA_LOCUS = "cited in per-row usage notes; not in the master sources block"


def sort_key(q: dict) -> tuple[int, int]:
    """Band order design→execution→presentation, then the numeric suffix of the id.

    The committed file must always read DES-1..14, EXE-1..15, PRE-1..7 regardless of the
    order the library master happens to list them in.
    """
    band = BAND_ORDER.get(q["band"])
    if band is None:
        raise SystemExit(f"unknown band {q['band']!r} on {q['id']}")
    _, _, suffix = q["id"].partition("-")
    if not suffix.isdigit():
        raise SystemExit(f"id {q['id']!r} has no numeric suffix")
    return (band, int(suffix))


def wordings_of(q: dict) -> dict:
    """The source wordings recorded for this question, blocks absent where the master has none."""
    out = {}
    for block, keys in WORDING_KEYS.items():
        raw = q.get(block)
        if isinstance(raw, dict):
            out[block] = {k: raw[k] for k in keys if k in raw}
    return out


def is_reworded(q: dict, wordings: dict) -> bool:
    """True when `canonical` matches none of the verbatim wordings recorded for the row.

    A published-21 row is never reworded: `canonical` IS the wording GAO printed in
    GAO-15-548 App. I / GAO-21-460 Fig. 6 / GAO-23-106549 Fig. 3.
    """
    if q.get("in_published_21"):
        return False
    return q["canonical"] not in {w["verbatim"] for w in wordings.values() if "verbatim" in w}


def main() -> int:
    if not SRC.exists():
        print(f"missing {SRC} — the research library is local-only", file=sys.stderr)
        return 1
    m = yaml.safe_load(SRC.read_text())
    gt = yaml.safe_load(GT.read_text())
    for cname, c in m["normative_definitions"].items():
        if isinstance(c, dict) and "governs" in c:
            for qid in c["governs"]:
                CLUSTER_OF[qid] = cname
    questions = []
    for q in sorted(m["questions"], key=sort_key):
        wordings = wordings_of(q)
        questions.append({
            "id": q["id"], "band": q["band"], "canonical": q["canonical"],
            "in_published_21": bool(q.get("in_published_21")),
            "supports_dimension": list(q.get("supports_dimension") or []),
            "verbatim_source": q.get("verbatim_source", ""),
            "cluster": CLUSTER_OF.get(q["id"]),
            "wordings": wordings,
            "canonical_is_reworded": is_reworded(q, wordings),
            "usage": q.get("usage") or {},
        })
    sources = [
        {"id": s["id"], "date": str(s["date"]), "locus": s["locus"],
         "count": s.get("count", ""), "note": s.get("note", "")}
        for s in m["sources"]
    ]
    listed = {s["id"] for s in sources}
    for extra in EXTRA_SOURCES:
        if extra not in listed:
            sources.append({"id": extra, "date": "", "locus": EXTRA_LOCUS,
                            "count": "", "note": ""})
    dm = gt["dimension_mapping"]
    out = {
        "meta": {
            "derived_from": sources,
            "note": "DERIVED ARTIFACT, not a GAO document. 36 = 14 design / 15 execution / "
                    "7 presentation (GAO-16-820 App. I). The published 21 are a tailored "
                    "subset. Verify any quoted text against the cited page.",
            "id_scheme": "DES-1..9, EXE-1..8, PRE-1..4 are the published 21; DES-10..14, "
                         "EXE-9..15, PRE-5..7 are the remaining 15.",
            "canonical_is_reworded_note":
                "True means `canonical` matches none of the verbatim wordings under "
                "`wordings`. It does not by itself mean we reworded the question. DES-12 "
                "and DES-13 are both flagged although their canonical text is verbatim "
                "from GAO-16-820 p. 29, a source `wordings` does not carry: DES-13 has no "
                "2006, 2010 or 2015-spine wording to compare against at all, and DES-12's "
                "canonical differs from its 2006 and 2010 predecessors because GAO "
                "reworded it in 2016, not because we did. Published-21 rows are never "
                "flagged: `canonical` is the wording GAO printed.",
        },
        "rating_scale": {
            "source": m["rating_scale"]["source"],
            "levels": m["rating_scale"]["levels"],
            "decision_rule_verbatim": m["rating_scale"]["decision_rule_verbatim"],
        },
        "band_prompts": {k: v for k, v in m["band_prompts"].items()
                         if k in ("design", "execution", "presentation")},
        "normative_definitions": {
            k: {"band": v["band"], "page": v["page"], "verbatim": v["verbatim"],
                "governs": v["governs"]}
            for k, v in m["normative_definitions"].items()
            if isinstance(v, dict) and "governs" in v
        },
        # Verbatim from the master, cautions included, so the "see editorial_acts.merges"
        # references on DES-14 and EXE-15 resolve inside this file.
        "editorial_acts": {k: m["editorial_acts"][k]
                           for k in ("merges", "splits", "band_moves",
                                     "exclusions_to_hold_at_36")},
        # The seven questions named in at least one GAO source but held out of the 36, so
        # exclusions_to_hold_at_36.note resolves here too. Public GAO text.
        "residual_questions": m["residual_questions"],
        "dimension_mapping": {
            "source": "GAO-23-106549 pp. 7-8",
            "objectivity": {"verbatim": dm["objectivity"]["verbatim"],
                            "question_ids": dm["objectivity"]["question_ids"]},
            "validity": {"verbatim": dm["validity"]["verbatim"],
                         "question_ids": dm["validity"]["question_ids"]},
            "reliability": {"verbatim": dm["reliability"]["verbatim"],
                            "question_ids": dm["reliability"]["question_ids"]},
            "unmapped_questions": dm["unmapped_questions"],
        },
        "questions": questions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "# DERIVED ARTIFACT — generated by scripts/derive_standard.py from public GAO documents.\n"
        "# Do not edit by hand; edit the derivation and re-run.\n"
        + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=100))
    print(OUT, len(questions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
