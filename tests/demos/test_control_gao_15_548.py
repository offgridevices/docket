"""The positive control: a study GAO passed, scored by the same scorer.

Every number asserted here was **measured** from a run of
`demos/control_gao_15_548/run.py` and then written down, not chosen in advance. What is
*asserted in advance* is only the shape of the result the control exists to hold — no
applicable question worse than state 2, three `generally_*` verdicts, DES-4 at 2, and no
blocker other than the one a narrative study honestly earns. If any of those stop
holding, either the fixture or the scorer moved and somebody has to say which.

Nothing here asserts on the bytes of a rendered decision package, or on the wording of a
dimension qualifier. Both belong to modules under active revision, and a control that
broke every time a renderer changed a heading would be measuring the wrong thing.

GAO-15-548 published no per-question ratings for this study (printed p. 24) and does not
use the objectivity / validity / reliability frame at all. Every per-question state and
every dimension verdict below is OURS.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest
import yaml

from demos.control_gao_15_548.build import EPISODE, NOW, SRC, H, build
from demos.control_gao_15_548.run import OUT, RESULTS_FILE, SEED, run
from docket.eval.agreement import label_from_state
from docket.kernel.lifecycle import transition
from docket.kernel.readiness import readiness_report
from docket.kernel.validate import validate
from docket.store import Graph
from tests.kernel.conftest import assert_history_honest

HERE = Path(__file__).resolve().parents[2] / "demos" / "control_gao_15_548"
OUTPUT_FILES = (RESULTS_FILE, "report.md", "package-full.md")


@pytest.fixture(scope="module")
def expected() -> dict:
    return yaml.safe_load((HERE / "expected.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def control(tmp_path_factory):
    """One run of the control, shared by every test that only reads it."""
    return run(tmp_path_factory.mktemp("control-gao-15-548"))


def _rescore(g: Graph, *, k: int | None = None) -> tuple[dict, dict, list[str]]:
    """Drive both human gates and score, for the probes below."""
    transition(g, EPISODE, "MODEL_APPROVED", H, now=NOW)
    transition(g, EPISODE, "PLAN_APPROVED", H, now=NOW)
    rr = readiness_report(g, EPISODE, seed=SEED, now=NOW, k=k)
    sa = g.get(rr["standardsAssessment"])
    return ({r["questionId"]: r["state"] for r in sa["ratings"]},
            {d: v["verdict"] for d, v in sa["dimensionVerdicts"].items()},
            sorted({b["rule"] for b in rr["blockers"]}))


def _bump(g: Graph, oid: str, **over) -> None:
    """A human revision of one object, for the probes below."""
    o = g.get(oid)
    g.put({**o, "rev": o["rev"] + 1, "createdBy": H, "createdAt": NOW, **over}, H)


# ---- the control itself --------------------------------------------------------------


def test_a_passed_study_scores_generally_objective_valid_and_reliable(control, expected):
    off = {q: s for q, s in control["states"].items()
           if s is not None and s not in expected["all_applicable_states_in"]}
    assert off == {}, off
    assert control["dimensions"] == expected["dimension_verdicts"], control["dimensions"]
    assert control["states"]["DES-4"] == expected["des_4_state"]
    assert control["tailoring"] == "gao-15-548"
    # 21 applicable, 15 tailored out — the gao-15-548 tailoring of the 36-question standard.
    assert sum(1 for s in control["states"].values() if s is not None) == 21
    assert len(control["states"]) == 36


def test_blockers_are_only_the_ones_we_expect(control, expected):
    """`ready` may be false, but only for reasons we have written down.

    The study has no evaluation run, so no run covers the primary objective's measures.
    That is a true statement about a narrative study, not a fixture defect. Any *other*
    blocker is a fixture defect — fix the fixture, never the rules.
    """
    assert [b["rule"] for b in control["blockers"]] == expected["expected_blockers"]
    assert control["blockers"][0]["objects"] == ["obj-viability"]
    assert control["ready"] is False


def test_no_representation_finding_fires_at_all(control):
    """The point of the control, stated as an assertion.

    Every finding class the scorer can raise about how a record *represents* its work —
    silent omission, unsupported claim, undefined scope term, evidence reused past its
    purpose, a model with no VV&A, a gap nobody confirmed — stays quiet here. The
    readiness report's warning list is empty and its blocker list holds one entry, which
    is about a missing computation rather than about representation.
    """
    assert control["warnings"] == [], control["warnings"]
    assert control["computedBiasRisks"] == []


def test_expected_yaml_labels_the_states_as_ours(expected):
    assert expected["gao_published_no_per_question_key"] is True
    assert "OURS" in expected["gao_note"]
    assert "OURS" in expected["dimension_frame_note"]
    # The scope limit that must never drift: GAO assessed methods, not the analysis.
    assert "did not assess or verify" in expected["scope_note"]


def test_the_run_writes_the_ours_label_into_every_artefact(control):
    assert "OURS" in control["note"]
    report = (Path(control["outDir"]) / "report.md").read_text(encoding="utf-8")
    assert "OURS" in report
    assert "printed p. 24" in report


# ---- measured agreement, pinned as measured ------------------------------------------


def test_measured_agreement_against_our_target_is_pinned_as_measured(control):
    """Measured: 1.000 label agreement and 1.000 exact-state agreement over 21 questions.

    This is a regression check on the fixture, not a comparison against GAO: the target
    table in `expected.yaml` was recorded from a run of this same file, because GAO-15-548
    published no per-question key. The kappa is 0.0 and carries no information — the
    target has one label — and the majority baseline is 1.0 for the same reason. Both are
    asserted so that nobody reads the 1.000 as a skill score.
    """
    a = control["agreement"]
    assert a["available"] is True
    assert a["n"] == 21
    assert a["agreement"] == 1.0
    assert a["state_agreement"] == 1.0
    assert a["disagreements"] == {}
    assert a["majority_baseline"] == 1.0
    assert a["kappa"] == 0.0


def test_every_applicable_question_reads_assessed_under_the_gao_21_460_label_map(control):
    """The label map GAO-21-460 Figure 6 publishes has two values. Under it, every
    applicable question here reads `assessed` — which is what "GAO passed this study"
    looks like once the four states are collapsed onto GAO's two."""
    labels = {q: label_from_state(s) for q, s in control["states"].items() if s is not None}
    assert set(labels.values()) == {"assessed"}


# ---- the mechanisms, probed ----------------------------------------------------------


def test_des_4_is_driven_by_the_two_rationales_gao_named_and_nothing_else():
    """Measured: patching either gapped rationale alone leaves DES-4 at 2; patching both
    takes it to 1.

    GAO printed p. 10 says "some key assumptions could have been discussed or defined more
    explicitly" and gives two examples: the minimum sustainment rate's derivation (printed
    p. 13) and the Army-perspective risk assumption (printed p. 12). Those are exactly the
    two objects whose `rationale` is a recorded gap, and they are exactly what holds DES-4
    at 2. The charter-definition route (`definition-missing`) drives DES-2/DES-3, not
    DES-4, and does not fire here at all.
    """
    g = build()
    _bump(g, "as-min-sustainment-rate", rationale="a rationale the study did not state")
    assert _rescore(g)[0]["DES-4"] == 2

    g = build()
    _bump(g, "as-army-risk-perspective", rationale="a rationale the study did not state")
    assert _rescore(g)[0]["DES-4"] == 2

    g = build()
    _bump(g, "as-min-sustainment-rate", rationale="a rationale the study did not state")
    _bump(g, "as-army-risk-perspective", rationale="a rationale the study did not state")
    states, dims, _ = _rescore(g)
    assert states["DES-4"] == 1
    assert dims["objectivity"] == "generally_objective"


def test_des_6_rests_on_the_sensitivity_analysis_gao_credited():
    """Measured: withdraw the sensitivity credit and DES-6 falls 2 -> 3, taking
    reliability from `generally_reliable` to `not_reliable`.

    GAO printed p. 12 credits this study's sensitivity analysis explicitly. The probe is
    here so that nothing in this repository can quietly come to say the study lacked one.
    """
    g = build()
    _bump(g, "as-demand-scenarios", variedInSensitivity=False)
    states, dims, _ = _rescore(g)
    assert states["DES-6"] == 3
    assert dims["reliability"] == "not_reliable"


def test_the_kernel_default_k_would_fail_a_study_gao_passed(expected):
    """Measured: at k=1 all three dimensions read `not_*`; at the policy's k they read
    `generally_*`. This is the whole case for ruling R3, run rather than argued.

    GAO-23-106549 printed p. 17 states the rule the policy encodes: a report is "generally
    objective when available information presented in the report was consistent with our
    definition of objectivity but was missing information that would have addressed the
    generally accepted research standards" — a rule about missing information, not a count
    of it.
    """
    at_one = _rescore(build(), k=1)[1]
    assert at_one == {"objectivity": "not_objective", "validity": "not_valid",
                      "reliability": "not_reliable"}
    assert _rescore(build())[1] == expected["dimension_verdicts"]
    assert expected["aggregation_k"] == 21


def test_the_evidence_register_is_covered_and_the_rule_that_checks_it_is_live():
    """Measured: point the Kearney report's exclusion at something else and
    `silent-omission` fires on the report.

    Nine of the ten items in the register are cited by a Claim. The tenth — the Army's
    April 2014 report itself — cannot be: its pointer is a recorded gap, and a claim
    resting on evidence whose metadata nobody outside the Army can see is what the scope
    checker exists to refuse. It is covered by a typed Exclusion instead, and this probe
    shows that the cover is load-bearing rather than decorative.
    """
    g = build()
    ex = g.get("ex-kearney-report-not-public")
    _bump(g, "ex-kearney-report-not-public", target={**ex["target"], "id": "ev-gao-15-548"})
    assert "silent-omission" in _rescore(g)[2]


# ---- the record itself ---------------------------------------------------------------


def test_the_record_validates_under_its_own_policy(control):
    g = control["graph"]
    blocking = [f for f in validate(g, g.get("pol-kearney")) if f.severity == "blocking"]
    assert blocking == [], blocking


def test_transition_history_is_honest(control):
    """The record stops at PLAN_APPROVED, and the history says only what is true.

    `EVALUATED` is not driven: its gate asks that every planned step have a sealed run
    behind it, and this study has none. Claiming the state without the runs would be the
    fixture asserting a gate that would have refused it.
    """
    g = control["graph"]
    assert_history_honest(g, EPISODE)
    assert [t["to"] for t in g.get(EPISODE)["transitions"]] == [
        "MODEL_APPROVED", "PLAN_APPROVED"]
    assert g.get(EPISODE)["lifecycleState"] == "PLAN_APPROVED"
    assert g.get(EPISODE)["runs"] == []


def test_every_gap_is_human_confirmed_and_none_is_blocking(control):
    """Five recorded absences, each confirmed by a human, none of them blocking.

    `gap-msr-derivation` is `degrading` rather than `blocking` on GAO's own authority:
    printed p. 13, "we do not believe that the lack of explicitly stated information
    materially affected the results of the study". Marking it blocking would drop PRE-2
    from 1 to 2 and would put a severity on the record that GAO did not.
    """
    g = control["graph"]
    assert set(control["openGaps"]) == {
        "gap-criteria", "gap-kearney-report", "gap-msr-derivation",
        "gap-risk-perspective-rationale", "gap-weights"}
    for gid in control["openGaps"]:
        gap = g.get(gid)
        assert gap["confirmedBy"]["actorId"] == "shreyash"
        assert gap["impact"] in ("degrading", "informational"), (gid, gap["impact"])
    assert g.get("gap-msr-derivation")["impact"] == "degrading"


def test_the_reconstruction_is_labelled_as_one(control):
    """Confidence discipline: only GAO's account of GAO's own work is `explicit`.

    Everything that describes the A.T. Kearney study is `inferred`, because it was
    assembled out of GAO's prose rather than transcribed from the study — which is not
    public. Recorded absences are `absent`.
    """
    g = control["graph"]
    explicit = sorted(o["id"] for o in g.all() if o.get("confidence") == "explicit")
    assert explicit == ["drs-two-analysts", "ev-gao-15-548"]
    for gid in control["openGaps"]:
        assert g.get(gid)["confidence"] == "absent"
    for oid in ("ch-kearney-2014", "mdl-kearney-financial", "as-warm-shutdown",
                "pl-kearney", "cl-excess-capacity"):
        assert g.get(oid)["confidence"] == "inferred", oid


def test_every_locator_names_both_page_numberings(control):
    """Printed page + 3 = PDF page, on every object that cites the source."""
    g = control["graph"]
    cited = [o for o in g.all() if "ingestionProvenance" in o]
    assert len(cited) > 40
    for o in cited:
        prov = o["ingestionProvenance"]
        assert prov["sourceArtifact"].endswith(
            "gao-15-548-army-combat-vehicles-industrial-base-study.pdf"), o["id"]
        assert "printed p. " in prov["locator"] and "PDF p. " in prov["locator"], o["id"]


def test_the_general_reliability_steps_are_load_bearing_and_the_alternative_is_measured():
    """Measured: strict per-item attribution → EXE-5 2, PRE-1 4, validity insufficient.

    Seven of the eleven `reliabilitySteps` attachments read a general GAO finding at the
    scope GAO wrote it at. Printed pp. 16–17 carry a titled section — "The Army Took
    Sufficient Actions to Ensure the Data Were Valid and Reliable for the Study's
    Purposes" — under which each step is a universal about the study's data followed by an
    instance marked "For example". Attaching those findings to data items GAO does not
    name individually is the softest judgement in the fixture, so its counterfactual is
    pinned here rather than argued in a report.

    The strict alternative is built below: keep only the steps GAO names against the
    specific item (the non-respondent follow-up, the overhead normalisation, the Abrams
    program office, GAO's own two analysts, and the benchmark loop printed p. 16 describes
    against the benchmark estimates) and record a confirmed gap in the rest. Note that the
    naive form — an empty `reliabilitySteps` — is not available: the field is a P3 slot and
    an empty list raises a blocking `silence` finding.

    The result is why the attachment is kept, not a reason to be comfortable with it.
    PRE-1 = 4 reads "insufficient information to determine whether the results support the
    findings" — about a study for which GAO wrote a titled section concluding the data were
    valid and reliable and whose conclusions, printed p. 17, "flowed logically from the
    evidence collected based on the methodology".
    """
    g = build()
    g.put({"id": "gap-per-item-reliability", "type": "InsufficientEvidence", "rev": 1,
           "createdBy": H, "createdAt": NOW, "confidence": "absent",
           "sought": "a data reliability step GAO names against this specific item",
           "whereLookedFor": ["GAO-15-548 printed pp. 16-17"],
           "whyNotFound": ("GAO states the step of the study's data generally and "
                           "illustrates it with a different item"),
           "confirmedBy": {"actorId": "shreyash", "date": "2026-09-05"},
           "impact": "degrading", "indicatorsThatWouldResolve": []}, H)
    strict = {
        "ev-manufacturer-data": ["drs-normalise-overhead"],   # GAO names the normalisation
        "ev-amc-baseline": {"$gap": "gap-per-item-reliability"},
        "ev-oem-rates": {"$gap": "gap-per-item-reliability"},
        "ev-army-procurement-plans": {"$gap": "gap-per-item-reliability"},
        "ev-oem-review-2013": {"$gap": "gap-per-item-reliability"},
    }
    for ev_id, steps in strict.items():
        _bump(g, ev_id, reliabilitySteps=steps)

    states, dims, blockers = _rescore(g)
    assert states["EXE-5"] == 2
    assert states["PRE-1"] == 4
    assert dims["validity"] == "insufficient_to_conclude"
    # Only validity moves: PRE-1 is mapped to validity, and EXE-5's 2 is absorbed by the
    # policy's k on reliability.
    assert dims["objectivity"] == "generally_objective"
    assert dims["reliability"] == "generally_reliable"
    assert blockers == ["objective-run-coverage"]


# ---- the page attributions, checked against the source itself -------------------------


def _normalise(s: str) -> str:
    """Fold a fragment down to the letters and digits in it.

    Whitespace, curly quotes, en/em dashes and line breaks all differ between the fixture
    and `pdftotext`'s output, and `pdftotext` de-hyphenates across line breaks
    (`non-\nrespondents` → `nonrespondents`). Stripping every non-alphanumeric makes the
    comparison about the words and nothing else.
    """
    s = unicodedata.normalize("NFKC", s)
    for a, b in (("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'),
                 ("\u2014", "-"), ("\u2013", "-"), ("\u2018", "'")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s.lower())


FOOTER = re.compile(r"page\d+gao15548armycombatvehicles")


def _source_pages() -> list[dict[int, str]] | None:
    """The source's text layer, one printed page → normalised text map per extraction.

    Two extractions, because neither alone is enough: `-layout` preserves the two-column
    page but interleaves GAO's marginal section headings into the body text, and the
    plain extraction reads the columns in order but loses the layout. A fragment counts as
    present if *either* extraction has it, so they are kept apart rather than merged —
    merging would also destroy the page-to-page adjacency a straddling sentence needs.
    """
    if shutil.which("pdftotext") is None:
        return None
    pdf = Path(__file__).resolve().parents[2] / SRC
    if not pdf.exists():
        return None
    out = []
    for flags in ([], ["-layout"]):
        text = subprocess.run(["pdftotext", *flags, str(pdf), "-"],
                              capture_output=True, text=True, check=True).stdout
        # Printed page + 3 = PDF page; the offset is asserted below, not assumed.
        out.append({i - 3: _normalise(page)
                    for i, page in enumerate(text.split("\f"), start=1)})
    return out


def _span(pages: dict[int, str], wanted: list[int]) -> str:
    """The cited pages joined in order, with GAO's running footer removed.

    A sentence that starts on one printed page and finishes on the next — the
    spreadsheet-model sentence at printed pp. 13-14 is the one in this record — is only
    contiguous once "Page 13 GAO-15-548 Army Combat Vehicles" is taken out from between
    its two halves.
    """
    return "".join(FOOTER.sub("", pages.get(p, "")) for p in wanted)


def _strings(v) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [s for x in v.values() for s in _strings(x)]
    if isinstance(v, list):
        return [s for x in v for s in _strings(x)]
    return []


PRINTED = re.compile(r"printed pp?\. (\d+)")
QUOTED = re.compile(r'"([^"]{12,})"')


def _pages_named(text: str) -> set[int]:
    return {int(n) for n in PRINTED.findall(text)}


@pytest.fixture(scope="module")
def source_pages():
    pages = _source_pages()
    if pages is None:
        pytest.skip(
            "pdftotext is not on PATH (or the source PDF is missing), so the page "
            "attributions cannot be checked against the source. Install poppler-utils "
            "(`brew install poppler`) and re-run; this test is the only thing standing "
            "between a mistyped page number and a committed fixture.")
    return pages


def test_the_page_offset_is_what_every_locator_claims(source_pages):
    """Printed page + 3 = PDF page, verified from the page footers, not assumed."""
    for extraction in source_pages:
        for printed in (1, 7, 13, 17, 24):
            assert _normalise(f"Page {printed} GAO-15-548") in extraction[printed], printed


def test_every_quotation_is_on_a_page_the_object_names(source_pages):
    """The fixture's whole credibility is its page citations, so they are tested.

    Rule: every double-quoted fragment of twelve characters or more, anywhere in a
    provenanced object, must appear in the source's text layer on a page that object
    names — either in its `ingestionProvenance.locator` or in the very sentence carrying
    the quotation. A fragment that spans a page break is checked against the cited pages
    joined in order; an author's ellipsis splits the fragment and each half is checked.

    A mistyped page number, a quotation drifting from the sentence it was taken from, or a
    phrase this record attributes to GAO that GAO never wrote all fail here.
    """
    g = build()
    misses = []
    checked = 0
    for o in sorted(g.all(), key=lambda x: x["id"]):
        prov = o.get("ingestionProvenance")
        if not prov:
            continue
        locator_pages = _pages_named(prov["locator"])
        for text in _strings({k: v for k, v in o.items() if k != "ingestionProvenance"}):
            allowed = sorted(locator_pages | _pages_named(text))
            spans = [_span(extraction, allowed) for extraction in source_pages]
            for fragment in QUOTED.findall(text):
                for half in fragment.split("..."):
                    half = _normalise(half)
                    if len(half) < 12:
                        continue
                    checked += 1
                    if not any(half in span for span in spans):
                        misses.append((o["id"], allowed, fragment[:70]))
    assert checked > 50, f"only {checked} quotations checked — the extractor is broken"
    assert misses == [], misses


def test_each_object_quotes_at_least_one_page_its_locator_names(source_pages):
    """The locator itself has to be load-bearing, not decoration.

    The test above lets a quotation be justified by the sentence that carries it, which is
    right — an object may legitimately quote a page it does not index. But that alone
    would let a locator drift to a page the object has nothing to do with. So: any
    provenanced object carrying quotations must have at least one of them on a page its
    *locator* names.
    """
    g = build()
    offenders = []
    for o in sorted(g.all(), key=lambda x: x["id"]):
        prov = o.get("ingestionProvenance")
        if not prov:
            continue
        pages = sorted(_pages_named(prov["locator"]))
        spans = [_span(extraction, pages) for extraction in source_pages]
        fragments = [f for text in _strings({k: v for k, v in o.items()
                                             if k != "ingestionProvenance"})
                     for f in QUOTED.findall(text)]
        if not fragments:
            continue
        if not any(_normalise(h) in span for span in spans
                   for f in fragments for h in f.split("...") if len(_normalise(h)) >= 12):
            offenders.append((o["id"], pages))
    assert offenders == [], offenders


def test_the_saved_store_loads_and_still_validates(control):
    loaded = Graph.load(Path(control["outDir"]) / "graph")
    blocking = [f for f in validate(loaded, loaded.get("pol-kearney"))
                if f.severity == "blocking"]
    assert blocking == []
    assert loaded.snapshot_hash() == control["graph"].snapshot_hash()


# ---- determinism ----------------------------------------------------------------------


def test_two_runs_are_byte_identical(tmp_path):
    a, b = run(tmp_path / "a"), run(tmp_path / "b")
    for name in OUTPUT_FILES:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), \
            name
    for name in ("log.jsonl", "manifest.json"):
        assert ((tmp_path / "a" / "graph" / name).read_bytes()
                == (tmp_path / "b" / "graph" / name).read_bytes()), name
    assert a["states"] == b["states"]


@pytest.mark.parametrize("committed", [False, True])
def test_no_absolute_paths_in_any_output(control, committed):
    """A package that named the machine it was built on could not be byte-identical
    anywhere else, and would leak a home directory into a deliverable."""
    out = OUT if committed else Path(control["outDir"])
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
    assert checked > 50, f"expected the whole store under {out}, saw {checked} files"


def test_committed_scoring_output_is_current(tmp_path):
    """The committed `out/control.json` still says what a fresh run says.

    Compared field by field rather than byte for byte, and deliberately not over the
    package hash: the renderer is under revision in a sibling task, and a control that
    went red every time a heading moved would be measuring the renderer, not the record.
    """
    fresh = run(tmp_path / "fresh")
    committed = json.loads((OUT / RESULTS_FILE).read_text(encoding="utf-8"))
    for field in ("states", "rules", "dimensions", "des_4_state", "ready", "blockers",
                  "warnings", "openGaps", "openExclusions", "tailoring", "aggregationK",
                  "agreement"):
        assert committed[field] == fresh[field], (
            f"{field} is stale — re-run: uv run python -m demos.control_gao_15_548.run")


def test_run_writes_only_into_its_out_dir(tmp_path):
    """Containment, not an inventory.

    `run()` must put its four named artefacts in the directory it was handed and write
    nothing anywhere else. It may put *more* there — `build_package` also emits export
    artefacts, and that list belongs to the renderer's lane, not to this control — so the
    four names are asserted as a subset. An exact inventory here would go red on the next
    renderer change without saying anything true about this record.
    """
    root = tmp_path / "nested"
    target = root / "out"
    sibling = root / "sibling"
    sibling.mkdir(parents=True)
    (sibling / "canary.txt").write_text("untouched", encoding="utf-8")

    run(target)

    names = {p.name for p in target.iterdir()}
    assert {RESULTS_FILE, "graph", "package-full.md", "report.md"} <= names, names
    # Nothing outside the target: the sibling is unchanged and nothing new landed in the
    # parent, in the repository's demo directory, or in the current working directory.
    assert sorted(p.name for p in sibling.iterdir()) == ["canary.txt"]
    assert (sibling / "canary.txt").read_text(encoding="utf-8") == "untouched"
    assert sorted(p.name for p in root.iterdir()) == ["out", "sibling"]
