"""The blinded GAO-21-460 walk: does a record built without the key agree with the key?

Every number asserted here was **measured first and pinned afterwards**. None of it is a
target: no fixture value was changed after the key was read, and no rule was touched. If a
rule change moves one of these numbers the test fails on purpose — the README quotes them
and must be regenerated with `uv run python -m demos.validation_gao_21_460.run`.

The brief that commissioned this walk expected 20/21 with the execution band at or above
0.75. The measured result is 18/21 with the execution band at 0.625, and the three
disagreements are named below with the rule that produced each. That gap is the finding,
not a defect to be tuned away.
"""

import json
from pathlib import Path

import pytest

from demos.validation_gao_21_460.run import OUT, run
from docket.kernel.validate import validate
from docket.store import Graph
from tests.kernel.conftest import assert_history_honest

HERE = Path(__file__).resolve().parents[2] / "demos" / "validation_gao_21_460"

# Measured on kernel 0.1.0 under the `gao-21-460` tailoring. 18 of GAO's 21 published
# labels reproduced by a record built from GAO's prose by an agent that never saw them.
MEASURED_AGREEMENT = 18 / 21
MEASURED_KAPPA = 0.7096774193548386
MEASURED_BY_BAND = {"design": 1.0, "execution": 0.625, "presentation": 1.0}
# All three are the kernel calling "unable to assess" where GAO called "assessed", and all
# three fall off the end of their ladder for the same structural reason: the Army's study
# had not reported, so the record carries no claims and no observations.
#   EXE-3  the capabilities based assessment has no accreditation decision in GAO's
#          description, so `model-vva` blocks and `models_scope_ok` is false.
#   EXE-4  `data_scope_all_known`/`_some_known` read evidence *cited by a claim or an
#          observation*; there are none, so neither clause can fire.
#   EXE-5  same, for `reliability_all`/`reliability_some` — even though the record holds
#          four real DataReliabilityStep objects off printed p. 13.
EXPECTED_DISAGREEMENTS = {"EXE-3", "EXE-4", "EXE-5"}

# The blind is mechanical, not a promise. Anything on this list appearing in the fixture
# module or in the extracted description is a leak of the key into the blinded side.
# "unable to access" and "all were unable to be accessed" are GAO's own wording in the
# linearised Figure 6 text (PDF 45-46) — a typo for "assess", and the exact string a leak
# copied straight off the figure would carry. `not_in_figure_6` is the third value in
# research-standards-36.yaml's `usage` map, so it too can only come from the key channel.
DENYLIST = ("unable_to_assess", "unable to assess", "unable to access",
            "unable to be accessed", "not_in_figure_6", "ground_truth", "Figure 6",
            "figure 6", "answer key", "14/7", "assessed:")


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return run(tmp_path_factory.mktemp("gao-21-460"))


def test_agreement_with_figure_6_as_measured(result):
    assert result["blinded"] is True
    assert result["agreement"] == pytest.approx(MEASURED_AGREEMENT)
    assert result["agreement"] > result["majority_baseline"]
    assert result["majority_baseline"] == pytest.approx(2 / 3, abs=0.001)
    assert result["kappa"] == pytest.approx(MEASURED_KAPPA)
    assert result["by_band"] == pytest.approx(MEASURED_BY_BAND)
    assert result["tailoring"] == "gao-21-460"
    # Every truth "unable" is caught; the three misses are all in the other direction.
    assert result["confusion"] == {"tp": 7, "fp": 3, "fn": 0, "tn": 11, "n": 21}
    assert (result["precision_unable"], result["recall_unable"]) == pytest.approx((0.7, 1.0))


def test_the_three_disagreements_are_named_with_their_reason(result):
    misses = {q for q, v in result["per_question"].items() if not v["match"]}
    assert misses == EXPECTED_DISAGREEMENTS
    for q in sorted(misses):
        v = result["per_question"][q]
        assert (v["pred"], v["truth"]) == ("unable_to_assess", "assessed"), q
        assert v["rule"] == "always→4", q
    assert len(result["per_question"]) == 21


def test_the_presentation_band_is_leaked_by_the_source_and_says_so(result):
    """All four presentation questions reach `always→4` because the record has no claims
    — which two sentences on printed pp. 14 and 35 told the blinded builder outright. The
    band is therefore not an independent prediction, and the report must disclose that."""
    for q in ("PRE-1", "PRE-2", "PRE-3", "PRE-4"):
        assert result["per_question"][q]["rule"] == "always→4"
        assert result["per_question"][q]["truth"] == "unable_to_assess"
    report = (OUT / "report.md").read_text(encoding="utf-8")
    assert "Presentation-band caveat" in report
    assert "final report was not available during the time of our audit" in report
    assert "only per-question published key" in report


def test_the_key_is_never_read_by_the_fixture():
    """The blind, enforced rather than asserted: the fixture module must not name the key,
    and the extracted description must not carry Appendix II's contents."""
    build_src = (HERE / "build.py").read_text(encoding="utf-8")
    for term in DENYLIST:
        assert term not in build_src, f"{term!r} leaked into build.py"
    assert "ground_truth.yaml" not in build_src
    # run.py is the only module allowed to open the key.
    run_src = (HERE / "run.py").read_text(encoding="utf-8")
    assert 'HERE / "ground_truth.yaml"' in run_src


def test_the_extracted_description_is_the_eight_study_pages_and_nothing_else():
    """Printed pp. 6, 9, 11-14, 35-36. Figure 6 lives on printed pp. 39-41, which the
    extraction does not touch — verified by page marker, not by trust."""
    desc = (HERE / "study_description.txt").read_text(encoding="utf-8")
    markers = [ln for ln in desc.splitlines() if ln.startswith("=== printed p.")]
    assert markers == [f"=== printed p. {p} ===" for p in (6, 9, 11, 12, 13, 14, 35, 36)]
    for term in ("unable to assess", "Unable to assess", "Text of Figure 6",
                 "Figure 6:", "Generally Accepted Research Standards Used to Assess"):
        assert term not in desc, f"{term!r} leaked into study_description.txt"
    # Disclosed residual: printed pp. 6 and 35 point *at* appendix II ("A full list ... are
    # included in appendix II"). Neither reproduces a label, and the builder could not
    # follow the pointer without opening the PDF, which the protocol forbids. The brief
    # predicted zero occurrences of the phrase; there are two, and they are cross-
    # references, not content.
    assert desc.count("appendix II") + desc.count("Appendix II") == 2


def test_the_record_is_honest_about_not_being_ready(result):
    """A study that had not reported is not a signable record. `ready` is false for three
    reasons and the artefact names all three rather than hiding them."""
    assert result["ready"] is False
    assert set(result["blockers"]) == {"model-vva", "objective-run-coverage",
                                       "silent-omission"}
    assert result["dimensionVerdicts"] == {
        d: "insufficient_to_conclude" for d in result["dimensionVerdicts"]}


def test_history_is_honest_and_stops_where_the_study_stopped(result, tmp_path):
    fresh = run(tmp_path / "history")
    loaded = Graph.load(tmp_path / "history" / "graph")
    assert_history_honest(loaded, "ep-twv-2021")
    ep = loaded.get("ep-twv-2021")
    assert [t["to"] for t in ep["transitions"]] == ["MODEL_APPROVED", "PLAN_APPROVED"]
    assert ep["lifecycleState"] == "PLAN_APPROVED"
    assert ep["claims"] == [] and ep["runs"] == [] and ep["observations"] == []
    assert fresh["agreement"] == result["agreement"]


def test_no_schema_or_reference_finding_survives(tmp_path):
    """The fixture disagrees with GAO on three questions; it does not disagree with the
    schema on anything. Every blocking finding is a policy result, not a broken object."""
    run(tmp_path / "validate")
    g = Graph.load(tmp_path / "validate" / "graph")
    findings = validate(g, g.get("pol-twv"))
    assert [f for f in findings
            if f.rule in ("schema", "ref-integrity", "marker-type", "silence")] == []


def test_two_runs_are_byte_identical(tmp_path):
    a, b = run(tmp_path / "a"), run(tmp_path / "b")
    for name in ("agreement.json", "report.md"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), (
            name)
    assert a == b


def test_no_absolute_paths_in_any_output(tmp_path):
    out = tmp_path / "paths"
    run(out)
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
    assert checked > 40, f"expected the whole store under {out}, saw {checked} files"


def test_the_readme_quotes_the_measured_numbers():
    """The README must not drift from the artefact: every headline figure in it is read
    back out of `out/agreement.json`."""
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    measured = json.loads((OUT / "agreement.json").read_text(encoding="utf-8"))
    assert f"{measured['agreement']:.3f}" in readme
    assert f"{measured['kappa']:.3f}" in readme
    assert f"{measured['majority_baseline']:.3f}" in readme
    for band, value in measured["by_band"].items():
        assert f"{band} {value:.3f}" in readme
    for q in EXPECTED_DISAGREEMENTS:
        assert q in readme
    assert measured["agreement"] == pytest.approx(MEASURED_AGREEMENT)
