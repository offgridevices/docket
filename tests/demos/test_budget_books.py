"""The budget-book sub-demonstration: conflicts the public record never reconciled.

Every locator asserted here was read out of the committed extract, not copied from a
plan or a research note. `volume p. 2a-99` is the page number printed in the footer of
the source volume; `extract PDF p. 60` is where that sheet sits in
`sources/army-rdte-r2-fy2024-omfv-xm30-extract.pdf`. Both are given because the extract
sidecars say "Page numbering is that of the source volumes", so one without the other is
not checkable.

Nothing here asserts that a figure is wrong. The assertions are about what the record
says and where it says it.
"""

import json
from pathlib import Path

import pytest

from demos.budget_books.build import build
from demos.budget_books.run import EPISODE, OUT, POLICY, run
from docket.kernel.validate import validate
from docket.store import Graph
from tests.kernel.conftest import assert_history_honest

# Every locator the record carries, as printed in `out/report.md`.
LOCATORS = [
    "PB2023 PE 0605625A R-2/R-2A, volume pp. 2e-257, 2e-259 (extract PDF pp. 73, 75)",
    "PB2024 PE 0603645A R-2/R-2A, volume pp. 2a-99, 2a-101 (extract PDF pp. 60, 61)",
    "PB2024 PE 0605625A R-2/R-2A, volume pp. 3d-268, 3d-270 (extract PDF pp. 74, 76)",
    "PB2025 PE 0605625A R-2/R-2A, volume pp. 3d-191, 3d-192 (extract PDF pp. 64, 65)",
    "PB2027 PE 0605625A R-2/R-2A, volume pp. 3d-306, 3d-308 (extract PDF pp. 50, 52)",
    "PB2021 PE 0604100A R-2A, volume p. 451 (extract PDF p. 75)",
    "PB2021 PE 0605625A R-4A, volume p. 506 (extract PDF p. 92); "
    "R-2A, volume p. 500 (extract PDF p. 86)",
    "PB2023 PE 0605625A R-2A, volume p. 2e-261 (extract PDF p. 77)",
    "PB2024 PE 0605625A R-2A, volume p. 3d-271 (extract PDF p. 77)",
    "PB2025 PE 0604100A R-2A, volume p. 2b-33 (extract PDF p. 52)",
    "PB2022 PE 0605625A R-3, volume p. 460 (extract PDF p. 89)",
    "PB2023 PE 0605625A R-3, volume p. 2e-264 (extract PDF p. 80)",
    "GAO-23-106549, Highlights page (PDF p. 2) and printed p. 5 (PDF p. 8)",
    "PB2022 PE 0605625A R-4A, volume p. 463 (extract PDF p. 92)",
    "PB2023 PE 0605625A R-4A, volume p. 2e-268 (extract PDF p. 84)",
    "PB2024 PE 0605625A R-4A, volume p. 3d-281 (extract PDF p. 87)",
    "PB2025 PE 0605625A R-4A, volume p. 3d-204 (extract PDF p. 77)",
    "PB2026 PE 0605625A R-4A, volume p. 3d-339 (extract PDF p. 74)",
    "PB2027 PE 0605625A R-4A, volume p. 3d-320 (extract PDF p. 64)",
    "PB2026 PE 0605625A R-2A, volume p. 3d-330 (extract PDF p. 65)",
    "Industry Day briefing, PDF p. 18 (slide footer 20)",
    "GAO-23-106059 printed p. 128 (PDF p. 138)",
]

OUTPUT_FILES = ("conflicts.json", "report.md")


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    """One run of the demo, shared by every test that only reads it."""
    return run(tmp_path_factory.mktemp("budget-books"))


def _locator(conflict, evidence_id, needle, rows):
    """The locator of the row of `conflict`'s subject that states `needle`."""
    subject_field = conflict["message"].split(" ", 1)[0]
    for row in rows[subject_field]:
        if row["evidence"] == evidence_id and str(row["value"]) == needle:
            return row["locator"]
    raise AssertionError(f"{evidence_id} states no {needle} for {subject_field}")


def test_the_same_march_2023_book_states_two_totals(demo, tmp_path):
    """Ruling R8: at least one internal conflict, including the PB2024 case, by locator.

    PB 2024 was submitted in March 2023. On PE 0603645A it puts the OMFV Middle Tier of
    Acquisition effort at $1,348M for FY21-FY24; on PE 0605625A, in the same book and the
    same month, at $1,384M.
    """
    internal = demo["internal"]
    assert len(internal) >= 1

    rows = json.loads((Path(demo["outDir"]) / "conflicts.json").read_text())["rows"]
    pb2024 = [c for c in internal if "ev-pb2024" in c["objects"]]
    assert len(pb2024) == 1, [c["message"] for c in internal]
    conflict = pb2024[0]

    assert conflict["rule"] == "value-conflict-internal"
    assert conflict["severity"] == "blocking"
    assert "1348" in conflict["message"] and "1384" in conflict["message"]
    assert _locator(conflict, "ev-pb2024", "1348", rows) == (
        "PB2024 PE 0603645A R-2/R-2A, volume pp. 2a-99, 2a-101 (extract PDF pp. 60, 61)")
    assert _locator(conflict, "ev-pb2024", "1384", rows) == (
        "PB2024 PE 0605625A R-2/R-2A, volume pp. 3d-268, 3d-270 (extract PDF pp. 74, 76)")


def test_the_pb2021_aoa_window_self_conflict_is_reported_not_suppressed(demo):
    """Defect 25 / ruling R8: PB2021 is a genuine second internal conflict.

    PE 0604100A says several Analyses of Alternatives, the OMFV's among them, started in
    FY2019; the PE 0605625A R-4A schedule in the same book runs the AoA from 2Q FY2020 to
    1Q FY2021. This is a statement about what the record says, not about whether the Army
    did an Analysis of Alternatives.
    """
    pb2021 = [c for c in demo["internal"] if "ev-pb2021" in c["objects"]]
    assert len(pb2021) == 1, [c["message"] for c in demo["internal"]]
    message = pb2021[0]["message"]
    assert message.startswith("omfv-aoa.window takes different values within one document")
    assert "started FY2019" in message
    assert "2Q2020-1Q2021, completion" in message
    assert "volume p. 451 (extract PDF p. 75)" in message
    assert "volume p. 506 (extract PDF p. 92)" in message


def test_the_conflicts_the_rule_found(demo):
    """Six subjects disagree; two of them disagree inside a single document."""
    assert demo["subjects"] == [
        "aries.definition",
        "cave.definition",
        "omfv-acdd.quarter",
        "omfv-aoa.window",
        "omfv-mta-total-cost-fy21-24.costM",
        "omfv-phase2-award.date",
    ]
    assert len(demo["subjects"]) >= 5
    assert sorted(o for c in demo["internal"] for o in c["objects"]) == [
        "ev-pb2021", "ev-pb2024"]


def test_the_concept_design_window_is_recorded_and_agrees(demo):
    """Review I2: the Army statement most directly comparable with the award date.

    `Concept Design (5 OEMs)  4 2021 – 1 2023` sits one line below the A-CDD row on the
    R-4A sheets the record already cites. 4Q FY2021 is July-September 2021, compatible
    with the July the R-3 exhibits print and with GAO's September alike, so recording it
    keeps the award-date finding from being read on its own. All six books agree, so it
    produces no finding — which is the point.

    Every book that prints the row is recorded, not a sample: all six of these R-4A
    sheets are already cited for their A-CDD row, and reading a page for one line while
    passing over the line below it is the omission this product exists to catch.
    """
    rows = json.loads((Path(demo["outDir"]) / "conflicts.json").read_text())["rows"]
    assert rows["omfv-concept-design.window"] == [
        {"evidence": "ev-pb2022", "value": "4Q FY2021 - 1Q FY2023",
         "locator": "PB2022 PE 0605625A R-4A, volume p. 463 (extract PDF p. 92)"},
        {"evidence": "ev-pb2023", "value": "4Q FY2021 - 1Q FY2023",
         "locator": "PB2023 PE 0605625A R-4A, volume p. 2e-268 (extract PDF p. 84)"},
        {"evidence": "ev-pb2024", "value": "4Q FY2021 - 1Q FY2023",
         "locator": "PB2024 PE 0605625A R-4A, volume p. 3d-281 (extract PDF p. 87)"},
        {"evidence": "ev-pb2025", "value": "4Q FY2021 - 1Q FY2023",
         "locator": "PB2025 PE 0605625A R-4A, volume p. 3d-204 (extract PDF p. 77)"},
        {"evidence": "ev-pb2026", "value": "4Q FY2021 - 1Q FY2023",
         "locator": "PB2026 PE 0605625A R-4A, volume p. 3d-339 (extract PDF p. 74)"},
        {"evidence": "ev-pb2027", "value": "4Q FY2021 - 1Q FY2023",
         "locator": "PB2027 PE 0605625A R-4A, volume p. 3d-320 (extract PDF p. 64)"}]
    assert "omfv-concept-design.window" not in demo["subjects"]
    # Every A-CDD sheet also carries the concept-design row, and vice versa.
    acdd_pages = {r["locator"] for r in rows["omfv-acdd.quarter"] if "R-4A" in r["locator"]}
    assert {r["locator"] for r in rows["omfv-concept-design.window"]} == acdd_pages


def test_internal_findings_carry_only_their_own_documents_rows(demo):
    """Review M3: the kernel's `message` lists every page that states the subject, which
    is misleading on a finding whose whole claim is "within one document". The payload
    carries a `rows` key filtered to the documents the finding names."""
    payload = json.loads((Path(demo["outDir"]) / "conflicts.json").read_text())
    for conflict in payload["internal"]:
        assert {r["evidence"] for r in conflict["rows"]} == set(conflict["objects"])
        assert len({str(r["value"]) for r in conflict["rows"]}) >= 2
    for conflict in payload["across"]:
        assert {r["evidence"] for r in conflict["rows"]} == set(conflict["objects"])


def test_the_scope_difference_is_not_reported_as_a_conflict(demo):
    """The five-year window is a different subject from the four-year one on purpose."""
    assert "omfv-mta-total-cost-fy21-25" not in [
        s.split(".")[0] for s in demo["subjects"]]
    rows = json.loads((Path(demo["outDir"]) / "conflicts.json").read_text())["rows"]
    assert rows["omfv-mta-total-cost-fy21-25.costM"] == [
        {"evidence": "ev-pb2027", "value": 1536,
         "locator": "PB2027 PE 0605625A R-2/R-2A, volume pp. 3d-306, 3d-308 "
                    "(extract PDF pp. 50, 52)"}]


def test_every_locator_reaches_the_report(demo):
    report = (Path(demo["outDir"]) / "report.md").read_text(encoding="utf-8")
    missing = [loc for loc in LOCATORS if loc not in report]
    assert missing == [], missing


def test_every_object_validates(demo):
    """No schema error, no dangling reference, no empty slot, no unconfirmed gap."""
    structural = {"schema", "ref-integrity", "marker-type", "silence", "log-chain",
                  "authority", "run-seal", "gap-unconfirmed"}
    offenders = [f.to_dict() for f in demo["findings"] if f.rule in structural]
    assert offenders == []


def test_the_record_is_an_ingestion_not_a_readiness_record(demo):
    """Expected and stated out loud: every register entry is uncited, so
    `silent-omission` fires once for each, and the record is not ready."""
    episode = demo["graph"].get(EPISODE)
    # No gate was driven and the record claims none: the episode is DRAFT with an empty
    # transition history, so there is no approval it does not satisfy.
    assert episode["lifecycleState"] == "DRAFT"
    assert episode["transitions"] == []
    assert_history_honest(demo["graph"], EPISODE)
    register = episode["evidenceRegister"]
    silent = [f for f in demo["findings"] if f.rule == "silent-omission"]
    assert len(silent) == len(register) == 10
    assert sorted(f.objects[1] for f in silent) == sorted(register)
    assert demo["other_findings"] == {"silent-omission": 10}


def test_the_saved_store_loads_and_the_rule_still_fires(demo):
    loaded = Graph.load(Path(demo["outDir"]) / "graph")
    assert loaded.snapshot_hash() == demo["graph"].snapshot_hash()
    reloaded = validate(loaded, loaded.get(POLICY))
    internal = [f for f in reloaded if f.rule == "value-conflict-internal"]
    assert sorted(o for f in internal for o in f.objects) == ["ev-pb2021", "ev-pb2024"]


def test_two_runs_are_byte_identical(tmp_path):
    run(tmp_path / "a")
    run(tmp_path / "b")
    for name in OUTPUT_FILES:
        assert (tmp_path / "a" / name).read_bytes() == (
            tmp_path / "b" / name).read_bytes(), name
    for name in ("log.jsonl", "manifest.json"):
        assert (tmp_path / "a" / "graph" / name).read_bytes() == (
            tmp_path / "b" / "graph" / name).read_bytes(), name


@pytest.mark.parametrize("committed", [False, True])
def test_no_absolute_paths_in_any_output(demo, committed):
    """A file that named the machine it was built on could not be byte-identical
    anywhere else, and would leak a home directory into a deliverable."""
    out = OUT if committed else Path(demo["outDir"])
    checked = 0
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert str(out) not in text, path
        assert "/Users/" not in text, path
        assert "/home/" not in text, path
        assert "/tmp/" not in text, path
        checked += 1
    assert checked > 10, f"expected the whole store under {out}, saw {checked} files"


def test_committed_output_is_current(tmp_path):
    fresh = run(tmp_path / "fresh")
    for name in OUTPUT_FILES:
        assert (OUT / name).read_bytes() == (tmp_path / "fresh" / name).read_bytes(), (
            f"{name} is stale — re-run: uv run python -m demos.budget_books.run")
    assert (OUT / "graph" / "manifest.json").read_bytes() == (
        tmp_path / "fresh" / "graph" / "manifest.json").read_bytes()
    assert fresh["subjects"] == json.loads(
        (OUT / "conflicts.json").read_text())["subjects"]


def test_run_writes_only_into_its_out_dir(tmp_path):
    target = tmp_path / "nested" / "out"
    run(target)
    assert sorted(p.name for p in target.iterdir()) == [
        "conflicts.json", "graph", "report.md"]


def test_every_budget_exhibit_is_unclassified_and_public(demo):
    """Every page of every extract carries the header UNCLASSIFIED; the sidecars record
    `no-CUI-marking`. Nothing in this record is controlled."""
    g = build()
    for ev in g.all("Evidence"):
        assert ev["classification"] == {"level": "U", "metadataLevel": "U"}, ev["id"]
        assert "sources/" in ev["pointer"]["uri"], ev["id"]
    exhibits = [ev for ev in g.all("Evidence") if ev["evidenceType"] == "BudgetExhibit"]
    assert len(exhibits) == 7
    assert sorted(ev["fiscalYear"] for ev in exhibits) == [
        f"FY{y}" for y in range(2021, 2028)]
