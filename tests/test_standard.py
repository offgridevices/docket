from pathlib import Path

import pytest

from docket.standard import (
    load_crosswalk,
    load_standard,
    load_tailoring,
    published_21,
    question,
    question_ids,
)

DES = [f"DES-{i}" for i in range(1, 15)]
EXE = [f"EXE-{i}" for i in range(1, 16)]
PRE = [f"PRE-{i}" for i in range(1, 8)]


def test_36_questions_14_15_7():
    s = load_standard()
    ids = [q["id"] for q in s["questions"]]
    assert ids == DES + EXE + PRE
    bands = {q["id"]: q["band"] for q in s["questions"]}
    assert all(bands[i] == "design" for i in DES) and all(bands[i] == "execution" for i in EXE)
    assert all(bands[i] == "presentation" for i in PRE)


def test_published_21():
    assert published_21() == DES[:9] + EXE[:8] + PRE[:4]
    assert question_ids() == DES + EXE + PRE


def test_canonical_text_samples():
    q = {x["id"]: x["canonical"] for x in load_standard()["questions"]}
    assert q["DES-6"] == "Are the assumptions varied to allow for sensitivity analyses?"
    assert q["EXE-14"].startswith("Was a verification, validation, and accreditation (VV&A) report")
    assert q["PRE-3"] == "Are the conclusions sound?"


def test_dimension_mapping_matches_gao_23_106549():
    dm = load_standard()["dimension_mapping"]
    assert dm["objectivity"]["question_ids"] == [
        "DES-2", "DES-4", "DES-7", "EXE-1", "EXE-2", "PRE-3", "PRE-4",
    ]
    assert dm["validity"]["question_ids"] == ["DES-5", "EXE-3", "PRE-1", "PRE-3"]
    assert dm["reliability"]["question_ids"] == ["DES-6", "EXE-5", "PRE-2", "PRE-3"]
    assert dm["unmapped_questions"] == [
        "DES-1", "DES-3", "DES-8", "DES-9", "EXE-4", "EXE-6", "EXE-7", "EXE-8",
    ]


def test_rating_scale_four_states():
    rs = load_standard()["rating_scale"]
    assert [lv["level"] for lv in rs["levels"]] == [1, 2, 3, 4]
    assert "not sufficient information" in rs["levels"][3]["verbatim"]


def test_tailorings():
    full = load_tailoring("full-36")
    assert all(v["applicable"] for v in full["questions"].values()) and len(full["questions"]) == 36
    p21 = load_tailoring("published-21")
    assert sum(v["applicable"] for v in p21["questions"].values()) == 21
    assert p21["questions"]["EXE-14"]["applicable"] is False and p21["questions"]["EXE-14"][
        "tailoringReason"
    ]
    for name in ("gao-21-460", "gao-23-106549", "gao-15-548"):
        t = load_tailoring(name)
        assert {k for k, v in t["questions"].items() if v["applicable"]} == set(published_21())
    plus = load_tailoring("published-21-plus-vva")
    assert plus["questions"]["EXE-14"]["applicable"] is True
    assert sum(v["applicable"] for v in plus["questions"].values()) == 22


def test_crosswalk_covers_key_objects():
    rows = load_crosswalk()
    objs = {r["object"] for r in rows}
    assert {
        "Charter", "Evidence", "Exclusion", "InsufficientEvidence", "VVARecord",
        "Assumption", "FlipAnalysis",
    } <= objs
    for r in rows:
        assert r["doctrine"] and r["locus"]


# A `true` flag means only that `canonical` matches none of the wordings we carry — never on
# its own that we reworded anything. DES-12 and DES-13 are both verbatim from GAO-16-820
# p. 29, a source `wordings` does not carry: DES-13 has no wording at all to compare against,
# and DES-12 differs from its 2006 and 2010 predecessors because GAO reworded it in 2016.
# Recorded in meta.canonical_is_reworded_note.
REWORDED = ["DES-12", "DES-13", "DES-14", "EXE-9", "EXE-11", "EXE-14", "EXE-15", "PRE-7"]


def test_questions_carry_source_wordings():
    qs = load_standard()["questions"]
    assert all("wordings" in q and "canonical_is_reworded" in q for q in qs)
    spine = question("EXE-14")["wordings"]["spine_2015"]
    assert spine["ref"] == "VI.a" and spine["na_flag"] is True
    assert spine["verbatim"].startswith("Was a VV&A report")
    # The caution that stops a reader misreading na_flag travels with the flag.
    assert "DO NOT READ THIS" in question("EXE-4")["wordings"]["spine_2015"]["na_flag_warning"]
    assert question("EXE-14")["canonical_is_reworded"] is True
    assert question("DES-1")["wordings"] == {}
    assert [q["id"] for q in qs if q["canonical_is_reworded"]] == REWORDED
    assert not any(q["canonical_is_reworded"] for q in qs if q["in_published_21"])
    note = load_standard()["meta"]["canonical_is_reworded_note"]
    assert "DES-12" in note and "DES-13" in note and "GAO-16-820 p. 29" in note


def test_editorial_acts_are_carried_with_their_cautions():
    acts = load_standard()["editorial_acts"]
    assert set(acts) == {"merges", "splits", "band_moves", "exclusions_to_hold_at_36"}
    merged = {m["id"] for m in acts["merges"]}
    assert {"DES-14", "EXE-15"} <= merged
    ours = {m["id"] for m in acts["merges"] if "caution" in m}
    assert {"DES-14", "EXE-15"} <= ours


def by_id_note(sources, sid):
    return next(s["note"] for s in sources if s["id"] == sid)


def test_meta_derived_from_lists_every_source():
    src = load_standard()["meta"]["derived_from"]
    ids = [s["id"] for s in src]
    assert ids[:8] == ["GAO-06-938", "GAO-11-82R", "GAO-15-457R", "GAO-15-548",
                       "GAO-16-820", "GAO-18-230", "GAO-21-460", "GAO-23-106549"]
    assert {"GAO-16-86", "GAO-24-106982"} <= set(ids)
    assert all(set(s) == {"id", "date", "locus", "count", "note", "source"} for s in src)
    assert "parentheses reproduced" in by_id_note(src, "GAO-06-938")
    by_id = {s["id"]: s for s in src}
    assert by_id["GAO-23-106549"]["locus"] == "Figure 3, p. 7"
    assert by_id["GAO-06-938"]["date"] == "2006-09-20"
    assert "not in the master sources block" in by_id["GAO-16-86"]["locus"]


def test_every_derived_from_source_is_a_committed_file():
    """Rule 2 — every claim cites a file in `sources/`. The standard is the kernel's
    load-bearing artefact, so each document it derives from must have a committed
    `.source.md` provenance note in `sources/`, not merely a reference into the
    gitignored research library. The downloaded document itself is not committed; the
    note records where to fetch it. Raised in review of the Phase I pull request, where
    seven of the ten were only in `library/gao/`."""
    root = Path(__file__).resolve().parents[1]
    for entry in load_standard()["meta"]["derived_from"]:
        path = entry["source"]
        assert path.startswith("sources/"), f"{entry['id']} cites {path}, outside sources/"
        sidecar = root / (path.rsplit(".", 1)[0] + ".source.md")
        assert sidecar.is_file(), f"{entry['id']}'s source has no .source.md sidecar"


def test_loaders_return_copies():
    load_standard()["questions"].clear()
    assert len(load_standard()["questions"]) == 36
    question("DES-1")["canonical"] = "mutated"
    assert question("DES-1")["canonical"] == "Is the study's design clear?"
    load_tailoring("full-36")["questions"].clear()
    assert len(load_tailoring("full-36")["questions"]) == 36
    load_crosswalk().clear()
    assert load_crosswalk()


def test_load_tailoring_rejects_a_name_that_is_not_a_slug():
    for bad in ("../crosswalk", "full-36/../../x", "Full-36", "full 36", "full-36\n", ""):
        with pytest.raises(ValueError, match="bare slug"):
            load_tailoring(bad)


def test_residual_questions_are_carried():
    rq = load_standard()["residual_questions"]
    assert [r["id"] for r in rq] == [f"R{i}" for i in range(1, 8)]
    assert all(r["verbatim"] and r["disposition"] and r["sources"] for r in rq)
    # exclusions_to_hold_at_36 promises seven; the section it points at must hold seven.
    note = load_standard()["editorial_acts"]["exclusions_to_hold_at_36"]["note"]
    assert "Seven questions" in note and len(rq) == 7
