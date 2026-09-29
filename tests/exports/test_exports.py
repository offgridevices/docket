"""Tests for `src/docket/exports/*` — six deterministic mappers over one graph
(design §6.3, plan 06 task 1 mapping tables 1-6).
"""

from __future__ import annotations

import csv
import io
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from docket.canon import canonical_json, sha256_hex
from docket.exports import (
    EXPORTS,
    compute_all,
    export_text,
    resolve_plan_id,
    resolve_vva_id,
    write_exports,
)
from docket.exports.dmn import to_dmn
from docket.exports.gsn import to_gsn
from docket.exports.madr import to_madr
from docket.exports.milstd3022 import NOT_APPLICABLE, to_milstd3022, to_milstd3022_for_episode
from docket.exports.prov import to_prov
from docket.exports.rtvm import RTVM_COLUMNS, rtvm_csv, to_rtvm
from docket.kernel.render import build_package
from docket.store import Graph
from tests.kernel.conftest import COMPLETE_NOW, COMPLETE_RUN_ID, complete_graph

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_A_OUT = REPO_ROOT / "demos" / "a_cbo_gcv_2013" / "out"


def _demo_a_graph() -> Graph:
    graph_dir = DEMO_A_OUT / "graph"
    if not graph_dir.exists():
        pytest.skip(f"{graph_dir} not present — run `uv run python -m "
                     "demos.a_cbo_gcv_2013.run` first")
    return Graph.load(graph_dir)


def _demo_a_ids() -> tuple[str, str]:
    """`(episode_id, plan_id)`, imported from the demo module rather than hard-coded —
    the same rule the brief applies to Demo B, extended here for consistency."""
    from demos.a_cbo_gcv_2013.run import EPISODE, PLAN

    return EPISODE, PLAN


def _demo_b_module():
    return pytest.importorskip(
        "demos.b_omfv_2019_2023.build",
        reason="demos/b_omfv_2019_2023 does not exist yet (plan 05 has not landed)",
    )


# ---- 1. to_prov ---------------------------------------------------------------------


def test_to_prov_demo_a_one_activity_per_run_no_invalidations_used_resolves():
    g = _demo_a_graph()
    episode_id, _ = _demo_a_ids()
    prov = to_prov(g, episode_id, rendering="full")
    bundle = prov["bundle"][f"pkg:{episode_id}-full"]

    run_ids = {r["id"] for r in g.all("EvaluationRun")}
    run_activities = {aid for aid, a in bundle["activity"].items() if aid in run_ids}
    assert run_activities == run_ids
    for aid in run_activities:
        assert bundle["activity"][aid]["prov:startTime"] == bundle["activity"][aid]["prov:endTime"]

    assert "wasInvalidatedBy" not in bundle  # Demo A has no lapsed scope

    for rel in bundle.get("used", {}).values():
        assert rel["prov:entity"] in bundle["entity"]

    # I1: every Result the run's own `outputs` names has a generation edge.
    assert bundle.get("wasGeneratedBy"), "expected wasGeneratedBy edges (I1)"
    for rel in bundle["wasGeneratedBy"].values():
        assert rel["prov:entity"] in bundle["entity"]
        assert rel["prov:activity"] in run_ids


def test_to_prov_is_pure_json_serialisable_and_sorted():
    g = complete_graph()
    prov = to_prov(g, "ep-1", rendering="full")
    text = canonical_json(prov)
    assert canonical_json(to_prov(g, "ep-1", rendering="full")) == text  # deterministic


def test_to_prov_withholds_evidence_title_under_unclassified():
    g = complete_graph()
    ev = g.get("ev-doc")
    g.put({**ev, "rev": ev["rev"] + 1, "createdBy": ev["createdBy"],
           "classification": {"level": "CUI", "metadataLevel": "CUI"}}, ev["createdBy"])
    prov = to_prov(g, "ep-1", rendering="unclassified")
    entity = prov["bundle"]["pkg:ep-1-unclassified"]["entity"]["ev-doc"]
    assert entity["docket:title"] == "[withheld: CUI]"
    full = to_prov(g, "ep-1", rendering="full")
    assert full["bundle"]["pkg:ep-1-full"]["entity"]["ev-doc"]["docket:title"] != "[withheld: CUI]"


def test_to_prov_is_resolvable_prov_json():
    """I2: `default` and `pkg` namespaces declared; every agent id is a single-colon
    qualified name. I3: the two renderings do not share a bundle id."""
    g = complete_graph()
    unclassified = to_prov(g, "ep-1", rendering="unclassified")
    full = to_prov(g, "ep-1", rendering="full")

    for prov in (unclassified, full):
        assert prov["prefix"]["default"] == prov["prefix"]["docket"]
        assert prov["prefix"]["pkg"].startswith(prov["prefix"]["docket"])
        bundle = next(iter(prov["bundle"].values()))
        for agent_id in bundle["agent"]:
            assert agent_id.count(":") == 1, agent_id

    assert set(unclassified["bundle"]) != set(full["bundle"])
    assert set(unclassified["bundle"]) == {"pkg:ep-1-unclassified"}
    assert set(full["bundle"]) == {"pkg:ep-1-full"}


def test_to_prov_plan_entity_is_also_prov_plan():
    g = complete_graph()
    bundle = to_prov(g, "ep-1", rendering="full")["bundle"]["pkg:ep-1-full"]
    assert "prov:Plan" in bundle["entity"]["pl-1"]["prov:type"]


def test_to_prov_invalidation_atime_is_a_full_datetime():
    g = complete_graph()
    ev = g.get("ev-doc")
    g.put(
        {**ev, "rev": ev["rev"] + 1, "createdBy": ev["createdBy"],
         "scopeOfValidity": {**ev["scopeOfValidity"], "validUntil": "2001-01-01"}},
        ev["createdBy"],
    )
    bundle = to_prov(g, "ep-1", rendering="full")["bundle"]["pkg:ep-1-full"]
    assert bundle.get("wasInvalidatedBy"), "expected a scope-lapsed invalidation"
    for rel in bundle["wasInvalidatedBy"].values():
        assert rel["prov:atTime"] == "2026-09-04T00:00:00Z"  # COMPLETE_NOW's own asOf date


def test_to_prov_wasGeneratedBy_keys_on_result_and_run_not_result_alone():
    """M2 (review round 2): `wasGeneratedBy` used to key `_:gen-{res_id}` — the
    Result id alone — so two runs both naming the same output in their `outputs`
    field silently collapsed to one generation edge, with the survivor being
    whichever run id happened to sort highest rather than a modelled choice. Keying
    on `(result, run)` keeps both edges.

    The duplicate run must itself be forward-reachable from the episode (`to_prov`
    only walks the episode's own reference graph) — a second Claim naming it via
    `derivedFrom` gives it exactly the same path the original run has through `cl-1`.
    """
    from tests.kernel.conftest import H, claim

    g = complete_graph()
    run = g.get(COMPLETE_RUN_ID)
    duplicate_run_id = "run-duplicate"
    g.put({**run, "id": duplicate_run_id, "rev": 1}, run["createdBy"])
    g.put(claim("cl-dup", ["ev-doc"], section="evaluation-results",
                derivedFrom=duplicate_run_id), H)
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "claims": [*ep["claims"], "cl-dup"]}, H)

    bundle = to_prov(g, "ep-1", rendering="full")["bundle"]["pkg:ep-1-full"]
    result_id = run["outputs"][0]
    activities = {
        rel["prov:activity"] for rel in bundle["wasGeneratedBy"].values()
        if rel["prov:entity"] == result_id
    }
    assert activities == {COMPLETE_RUN_ID, duplicate_run_id}


# ---- 2. to_gsn ------------------------------------------------------------------------


def test_to_gsn_demo_b_fs_challenge_and_defeated():
    demo_b = _demo_b_module()
    if not hasattr(demo_b, "SUB_EPISODES") or not callable(getattr(demo_b, "build", None)):
        pytest.skip(
            "demos.b_omfv_2019_2023.build does not yet export both SUB_EPISODES and a "
            "callable build() (plan 05 landing in progress)"
        )
    fs_episode = demo_b.SUB_EPISODES["fs"]
    g = demo_b.build()
    if not g.has(fs_episode):
        pytest.skip(
            f"demos.b_omfv_2019_2023.build.build() does not yet populate "
            f"{fs_episode!r} (plan 05 landing in progress)"
        )
    gsn = to_gsn(g, fs_episode, rendering="full")
    assert gsn["dialectic"]["challenge"], "expected a ReusePastPurpose challenge node"
    assert gsn["dialectic"]["defeated"], "expected downselect exclusions as 'defeated'"
    # I6: challenge is a {from, to} edge whose source is a Solution (Evidence) node;
    # defeated is a status entry, not a node with an embedded challenge.
    for edge in gsn["dialectic"]["challenge"]:
        assert edge["from"] in gsn["solutions"]
        assert edge["to"] in gsn["goals"]
    for status in gsn["dialectic"]["defeated"]:
        assert status["defeated"] is True
        assert "by" in status and "element" in status


def test_to_gsn_is_shaped_and_deterministic():
    g = complete_graph()
    gsn = to_gsn(g, "ep-1", rendering="full")
    for key in ("goals", "solutions", "contexts", "assumptions", "justifications",
                "strategies", "supportedBy", "dialectic", "modular"):
        assert key in gsn
    assert "inContextOf" not in gsn  # I7: dropped, not a Cartesian-product overclaim
    assert "cl-1" in gsn["goals"]
    assert "ev-doc" in gsn["solutions"]
    assert "awaySolution" in gsn["modular"]  # I6
    assert "awayGoal" not in gsn["modular"]
    assert canonical_json(to_gsn(g, "ep-1", rendering="full")) == canonical_json(gsn)


def test_to_gsn_strategy_ids_are_plan_qualified():
    """M6: keyed `plan_id:step_id`, and `supportedBy` names the same qualified id."""
    g = complete_graph()
    gsn = to_gsn(g, "ep-1", rendering="full")
    assert "pl-1:s1" in gsn["strategies"]
    assert any(
        e["from"] == "pl-1:s1" and e["to"] == "cl-1" for e in gsn["supportedBy"]
    )


def test_to_gsn_challenge_is_structured_and_never_carries_a_message():
    """I1 (review round 2): `dialectic.challenge[]` is `{"from", "to", "rule"}` —
    never the `ReusePastPurpose` finding's own free-text `message`, which
    interpolates the metadata-gated `scopeOfValidity.builtToAnswer` (the same field
    the evidence register and the RTVM gate under `metadata_withheld`)."""
    g = complete_graph()
    ev = g.get("ev-test")
    g.put(
        {**ev, "rev": ev["rev"] + 1, "createdBy": ev["createdBy"],
         "scopeOfValidity": {**ev["scopeOfValidity"], "questionClass": "cost"}},
        ev["createdBy"],
    )
    gsn = to_gsn(g, "ep-1", rendering="full")
    assert gsn["dialectic"]["challenge"], "expected a ReusePastPurpose challenge"
    for edge in gsn["dialectic"]["challenge"]:
        assert set(edge) == {"from", "to", "rule"}
        assert edge["rule"] == "ReusePastPurpose"


def test_to_gsn_unresolved_exclusion_targets_go_to_a_named_list_not_defeated():
    """I3 (review round 2): a `defeated[].element` may only name an id this document
    itself declares. An Exclusion whose target resolves to a declared node (here,
    the Evidence `ev-doc`, a `solutions` entry) is a real Defeated status; one whose
    target is label-only (no `id`, or an `id` this export never declares) goes into
    `unresolvedTargets` instead of a synthetic id that resolves nowhere."""
    from tests.kernel.conftest import H, alternative, obj

    g = complete_graph()
    g.put(obj(
        "ex-resolves", "Exclusion", target={"kind": "Evidence", "id": "ev-doc", "label": "doc"},
        reasonType="not-applicable", reason="superseded by a later study",
        authority={"who": "analyst", "role": "analyst", "date": "2026-01-01"},
        retainedInStructure=True,
    ), H)
    g.put(obj(
        "ex-unresolved", "Exclusion",
        target={"kind": "Scenario", "label": "a scenario this export never declares"},
        reasonType="out-of-scope", reason="never modelled",
        authority={"who": "analyst", "role": "analyst", "date": "2026-01-01"},
        retainedInStructure=True,
    ), H)
    g.put(alternative("alt-excl-1", status="screened-out", statusReason="ex-resolves"), H)
    g.put(alternative("alt-excl-2", status="screened-out", statusReason="ex-unresolved"), H)
    ep = g.get("ep-1")
    g.put(
        {**ep, "rev": ep["rev"] + 1, "createdBy": H,
         "alternatives": [*ep["alternatives"], "alt-excl-1", "alt-excl-2"]},
        H,
    )

    gsn = to_gsn(g, "ep-1", rendering="full")
    assert {"element": "ev-doc", "defeated": True, "by": "ex-resolves"} in (
        gsn["dialectic"]["defeated"]
    )
    assert any(u["by"] == "ex-unresolved" for u in gsn["unresolvedTargets"])
    assert not any(d["by"] == "ex-unresolved" for d in gsn["dialectic"]["defeated"])


def _gsn_declared_ids(gsn: dict) -> set[str]:
    return (
        set(gsn["goals"]) | set(gsn["solutions"]) | set(gsn["contexts"])
        | set(gsn["assumptions"]) | set(gsn["justifications"]) | set(gsn["strategies"])
    )


def _assert_gsn_edges_resolve(gsn: dict) -> None:
    """I3's own probe, generalised: every edge/element id `to_gsn` emits must name a
    node the same document declares — never a dangling id."""
    declared = _gsn_declared_ids(gsn)
    for edge in gsn["supportedBy"]:
        assert edge["from"] in declared, edge
        assert edge["to"] in declared, edge
    for edge in gsn["dialectic"]["challenge"]:
        assert edge["from"] in declared, edge
        assert edge["to"] in declared, edge
    for status in gsn["dialectic"]["defeated"]:
        assert status["element"] in declared, status


def test_to_gsn_every_edge_and_element_id_resolves_on_a_synthetic_graph():
    g = complete_graph()
    _assert_gsn_edges_resolve(to_gsn(g, "ep-1", rendering="full"))
    _assert_gsn_edges_resolve(to_gsn(g, "ep-1", rendering="unclassified"))


@pytest.mark.parametrize(
    "name,module_path",
    [
        ("a_cbo_gcv_2013", "demos.a_cbo_gcv_2013.run"),
        ("validation_gao_21_460", "demos.validation_gao_21_460.run"),
        ("control_gao_15_548", "demos.control_gao_15_548.build"),
    ],
)
def test_to_gsn_every_edge_and_element_id_resolves_on_every_demo(name, module_path):
    import importlib

    out_dir = REPO_ROOT / "demos" / name / "out"
    graph_dir = out_dir / "graph"
    if not graph_dir.exists():
        pytest.skip(f"{graph_dir} not present — run the demo's own build/run first")
    mod = importlib.import_module(module_path)
    g = Graph.load(graph_dir)
    _assert_gsn_edges_resolve(to_gsn(g, mod.EPISODE, rendering="full"))


def test_to_gsn_marks_a_gap_backed_claim_as_undeveloped():
    """M3 (review round 2): SCSC-141C Table 1:2-1's Undeveloped element decorator —
    "a claim which is intentionally left undeveloped" — for a Claim whose only
    support is a `{"$gap": ...}` marker. No demo graph exercises this today (Demo A,
    validation and control all have zero gap-backed claims), so this is a
    synthetic-graph test."""
    from tests.kernel.conftest import H, charter, claim, episode, obj

    g = Graph()
    g.put(obj("gap-1", "InsufficientEvidence", sought="a cost estimate",
               whereLookedFor=["programme office"], whyNotFound="not yet produced",
               impact="degrading", indicatorsThatWouldResolve=["a future cost report"]), H)
    g.put(charter(), H)
    g.put(claim("cl-gap", [], supportedBy={"$gap": "gap-1"}), H)
    g.put({**episode(), "claims": ["cl-gap"]}, H)

    gsn = to_gsn(g, "ep-1", rendering="full")
    assert gsn["goals"]["cl-gap"]["undeveloped"] is True
    assert gsn["goals"]["cl-gap"]["gap"] == "gap-1"


# ---- 3. to_dmn --------------------------------------------------------------------


def test_to_dmn_parses_and_requirements_resolve():
    g = complete_graph()
    xml_text = to_dmn(g, "pl-1", rendering="full")
    root = ET.fromstring(xml_text)
    ns = {"dmn": "https://www.omg.org/spec/DMN/20230324/MODEL/"}
    decisions = root.findall("dmn:decision", ns)
    assert len(decisions) == 1
    authority_reqs = root.findall(".//dmn:authorityRequirement", ns)
    assert len(authority_reqs) >= 1
    ks_ids = {ks.get("id") for ks in root.findall("dmn:knowledgeSource", ns)}
    for req in authority_reqs:
        href = req.find("dmn:requiredAuthority", ns).get("href").lstrip("#")
        assert href in ks_ids


def test_to_dmn_information_requirement_precedes_authority_requirement():
    """I5: Table 11's order, the reverse of the first draft's."""
    g = complete_graph()
    root = ET.fromstring(to_dmn(g, "pl-1", rendering="full"))
    ns = {"dmn": "https://www.omg.org/spec/DMN/20230324/MODEL/"}
    decision = root.find("dmn:decision", ns)
    tags = [child.tag.split("}")[-1] for child in decision]
    info_positions = [i for i, t in enumerate(tags) if t == "informationRequirement"]
    auth_positions = [i for i, t in enumerate(tags) if t == "authorityRequirement"]
    assert info_positions and auth_positions
    assert max(info_positions) < min(auth_positions)


def test_to_dmn_bytes_do_not_depend_on_a_foreign_namespace_registration():
    """I4: `ET.register_namespace` is process-global; a foreign registration anywhere
    else in the process must not change these bytes."""
    import xml.etree.ElementTree as ET_module

    g = complete_graph()
    before = to_dmn(g, "pl-1", rendering="full")
    ET_module.register_namespace("", "http://example.com/other")
    try:
        after = to_dmn(g, "pl-1", rendering="full")
    finally:
        ET_module.register_namespace("", "https://www.omg.org/spec/DMN/20230324/MODEL/")
    assert before == after
    assert "ns0:" not in after


def test_to_dmn_tolerates_missing_plan():
    g = complete_graph()
    xml_text = to_dmn(g, "no-such-plan", rendering="full")
    root = ET.fromstring(xml_text)  # still well-formed
    ns = {"dmn": "https://www.omg.org/spec/DMN/20230324/MODEL/"}
    assert root.findall("dmn:decision", ns) == []

    # A bare `plan_id=None` is not itself a fact about any plan — it must render as
    # well-formed, decision-free XML too, and never as the literal text "None" (the
    # same "no raw Python `None` in a deliverable" rule I2 states for MIL-STD-3022).
    none_text = to_dmn(g, None, rendering="full")
    none_root = ET.fromstring(none_text)
    assert none_root.findall("dmn:decision", ns) == []
    assert "None" not in none_text


def test_to_dmn_no_xml_declaration():
    g = complete_graph()
    assert not to_dmn(g, "pl-1", rendering="full").startswith("<?xml")


# ---- 4. to_milstd3022 --------------------------------------------------------------


def test_to_milstd3022_demo_a_not_applicable_count():
    g = _demo_a_graph()
    text = to_milstd3022(g, "vva-cbo-metric", rendering="unclassified")
    assert text.count(NOT_APPLICABLE) == 2


def test_to_milstd3022_missing_section_renders_as_missing_not_raise():
    g = complete_graph()
    # complete_graph's VV&A record has no "Resources" section at all.
    text = to_milstd3022(g, "vva-1", rendering="full")
    assert "*(section not present in the record)*" in text


def test_to_milstd3022_tolerates_missing_vva():
    g = complete_graph()
    text = to_milstd3022(g, "no-such-vva", rendering="full")
    assert "no VV&A record resolves" in text
    assert NOT_APPLICABLE not in text


def test_to_milstd3022_accreditation_decision_is_rendered():
    """C2: `accreditationDecision`'s five sub-fields, previously dropped entirely."""
    g = complete_graph()
    text = to_milstd3022(g, "vva-1", rendering="full")
    assert "chief engineer" in text  # complete_graph's accreditationDecision.authority
    assert "Authority:" in text and "Date:" in text and "Scope:" in text


def test_to_milstd3022_appendix_escapes_pipes_and_newlines():
    """M5."""
    g = complete_graph()
    ev = g.get("ev-doc")
    g.put(
        {**ev, "rev": ev["rev"] + 1, "createdBy": ev["createdBy"],
         "title": "a | pipe\nand a newline"},
        ev["createdBy"],
    )
    text = to_milstd3022(g, "vva-1", rendering="full")
    appendix = text.split("## Appendix: Requirements Traceability Matrix")[-1]
    # The raw title (with its literal newline and un-escaped pipe) must not appear —
    # only the escaped, single-line form — or the newline would split one logical row
    # across two lines and the bare `|` would add a phantom column.
    assert "a | pipe\nand a newline" not in appendix
    assert "a \\| pipe and a newline" in appendix


def test_to_milstd3022_tolerates_a_bare_none_vva_id_without_interpolating_it():
    """I2 (review round 2): `vva_id=None` is not a fact about any record — it must
    never render as the literal text `None` (the round-2 probe's own finding on
    `demos/validation_gao_21_460/out/export-milstd3022-full.md`)."""
    g = complete_graph()
    text = to_milstd3022(g, None, rendering="full")
    assert "None" not in text
    assert NOT_APPLICABLE not in text


def test_to_milstd3022_for_episode_renders_every_reachable_record_in_id_order():
    """I2: two of the three demos hold two VVARecords each reachable from their one
    episode; the tolerant, whole-episode export must render both, in id order, never
    pick one nor say "no record resolves" over records that plainly exist."""
    from demos.validation_gao_21_460.run import EPISODE

    graph_dir = REPO_ROOT / "demos" / "validation_gao_21_460" / "out" / "graph"
    if not graph_dir.exists():
        pytest.skip(f"{graph_dir} not present — run the demo's own run.py first")
    g = Graph.load(graph_dir)

    text = to_milstd3022_for_episode(g, EPISODE, rendering="full")
    first, second = text.index("vva-cba"), text.index("vva-lbc")
    assert first < second, "expected id order (vva-cba before vva-lbc)"
    assert text.count("## Appendix: Requirements Traceability Matrix") == 2
    assert "None" not in text
    assert "no VV&A record resolves" not in text


def test_to_milstd3022_for_episode_says_so_in_words_when_none_reachable():
    from tests.kernel.conftest import H, episode

    g = Graph()
    g.put(episode(oid="ep-bare", charter="ch-missing"), H)
    text = to_milstd3022_for_episode(g, "ep-bare", rendering="full")
    assert "no VVARecord is reachable from episode ep-bare" in text
    assert "None" not in text


# ---- 5. to_madr ---------------------------------------------------------------------


def test_to_madr_demo_a_five_options_no_decision_and_content_hash_line():
    g = _demo_a_graph()
    episode_id, _ = _demo_a_ids()
    text = to_madr(g, episode_id, rendering="full")
    for alt in ("alt-gcv", "alt-namer", "alt-upgraded-bradley", "alt-puma", "alt-retain-bradley"):
        assert f"({alt})" in text
    # Review round 2, R1: this used to be `"no decision" in text.lower() or "no
    # commitment" in text.lower()` — a disjunction that stayed true even after the
    # round-1 C3 fix silently dropped Demo A's own unreferenced `ex-no-commitment`
    # exclusion and its authority, degrading "No commitment on record — ... CBO's
    # mandate ..." down to the bare fallback "*no decision recorded*". Asserting the
    # authority string closes that hole: only the real exclusion path prints it.
    assert "No commitment on record" in text
    assert "Congressional Budget Office" in text
    assert "full" in text
    assert "graph snapshot hash" in text  # M4: labelled to match the annex's own wording


def test_to_madr_names_rendering_and_stable_content_hash():
    """D18, revisited: `to_madr` must name the rendering and a value that does not
    depend on how many `DecisionPackage` objects have been built (kernel C2) — see
    `madr.py`'s module docstring for why the literal "quote the package's stored
    hash" mapping-table instruction would break C2 and was replaced with this."""
    from docket.kernel.render import content_snapshot_hash

    g = complete_graph()
    before = content_snapshot_hash(g)
    build_package(g, "ep-1", rendering="unclassified", now=COMPLETE_NOW, out_dir=None)
    build_package(g, "ep-1", rendering="unclassified", now=COMPLETE_NOW, out_dir=None)
    text = to_madr(g, "ep-1", rendering="unclassified")
    assert before in text
    assert "unclassified" in text


# ---- 6. to_rtvm -----------------------------------------------------------------------


def test_to_rtvm_withholding_marker_before_and_after_repair():
    demo_b = _demo_b_module()
    if not hasattr(demo_b, "SUB_EPISODES") or not callable(getattr(demo_b, "build", None)):
        pytest.skip(
            "demos.b_omfv_2019_2023.build does not yet export both SUB_EPISODES and a "
            "callable build() (plan 05 landing in progress)"
        )
    ce_episode = demo_b.SUB_EPISODES["ce"]
    g = demo_b.build()
    if not g.has(ce_episode):
        pytest.skip(
            f"demos.b_omfv_2019_2023.build.build() does not yet populate "
            f"{ce_episode!r} (plan 05 landing in progress)"
        )
    rows = to_rtvm(g, ce_episode, rendering="unclassified")
    before = [r for r in rows if r["evidence_id"] == "ev-ce-metrics"]
    assert before and before[0]["pointer"].startswith("[withheld:")
    assert before[0]["assessable_at_U"] is False


def test_to_rtvm_columns_and_row_order():
    g = complete_graph()
    rows = to_rtvm(g, "ep-1", rendering="full")
    assert rows, "complete_graph should have at least one claim/evidence row"
    keys = set(rows[0])
    assert keys == set(RTVM_COLUMNS)
    ordered = sorted(rows, key=lambda r: (str(r["claim_id"]), str(r["evidence_id"])))
    assert rows == ordered


def test_to_rtvm_vva_status_is_n_a_for_non_msstudy_evidence():
    g = complete_graph()
    rows = to_rtvm(g, "ep-1", rendering="full")
    for row in rows:
        if row["evidence_id"] and row["evidence_id"] != "unresolved":
            assert row["vva_status"] == "n/a"  # ev-doc/ev-test/ev-bias are all Document/Dataset


def test_rtvm_csv_no_carriage_return_and_stable_header():
    g = complete_graph()
    rows = to_rtvm(g, "ep-1", rendering="full")
    csv_text = rtvm_csv(rows)
    assert "\r" not in csv_text
    header = csv_text.splitlines()[0]
    assert header.split(",") == RTVM_COLUMNS
    # round-trips through the stdlib reader
    reader = csv.DictReader(io.StringIO(csv_text))
    assert list(reader.fieldnames) == RTVM_COLUMNS


# ---- 7. byte-identity across two calls and a save/load round trip ------------------


@pytest.mark.parametrize("rendering", ["unclassified", "full"])
def test_every_export_is_byte_identical_across_two_calls(rendering, tmp_path):
    g = complete_graph()
    for name in EXPORTS:
        t1 = export_text(g, name=name, episode_id="ep-1", rendering=rendering)
        t2 = export_text(g, name=name, episode_id="ep-1", rendering=rendering)
        assert t1 == t2, name


@pytest.mark.parametrize("rendering", ["unclassified", "full"])
def test_every_export_hash_is_stable_across_save_load(rendering, tmp_path):
    g = complete_graph()
    before = {
        name: sha256_hex(export_text(g, name=name, episode_id="ep-1", rendering=rendering))
        for name in EXPORTS
    }
    save_dir = tmp_path / "graph"
    g.save(save_dir)
    g2 = Graph.load(save_dir)
    after = {
        name: sha256_hex(export_text(g2, name=name, episode_id="ep-1", rendering=rendering))
        for name in EXPORTS
    }
    assert before == after


def test_write_exports_writes_basenames_only_and_matches_compute_all(tmp_path):
    g = complete_graph()
    computed = dict(compute_all(g, "ep-1", rendering="full"))
    written = write_exports(g, "ep-1", rendering="full", out_dir=tmp_path)
    assert dict(written) == {fn: sha256_hex(text) for fn, text in computed.items()}
    for filename in computed:
        assert "/" not in filename
        assert (tmp_path / filename).read_text(encoding="utf-8") == computed[filename]


# ---- 8. purity: no wall clock under src/docket/exports/ ----------------------------


def test_no_wall_clock_in_exports_package():
    exports_dir = REPO_ROOT / "src" / "docket" / "exports"
    result = subprocess.run(
        ["grep", "-rn", "datetime", str(exports_dir)],
        capture_output=True, text=True, check=False,
    )
    assert result.stdout == "", f"wall clock reference(s) found:\n{result.stdout}"


# ---- 9. rtvm_csv has no \r (folded into test_rtvm_csv_no_carriage_return_and_stable_header) --


# ---- I2: a raw Python `None` must never appear in a deliverable --------------------


def test_no_raw_none_in_any_demo_export():
    """I2 (review round 2): `demos/validation_gao_21_460/out/export-milstd3022-full.md`
    used to read `_[no VV&A record resolves for None]_` while the graph held two
    VVARecords — `None` is Python's, not the record's, and must never reach a
    deliverable. Scans every committed `export-*` file of every demo for the two
    shapes the round-2 probe named: `None]` (a marker whose payload is `None`) and
    `: None` (a bare interpolated field).

    One string is scrubbed before the check: Demo A's `export-madr-*.md` quotes
    CBO's own Table 2-2 qualitative programmatic-risk rating verbatim, and for the
    retained-Bradley alternative that rating's own text *is* the word "None" —
    `demos/a_cbo_gcv_2013/build.py`'s `RISK` table, not a Python `None` reaching the
    page. Every other occurrence of either shape, anywhere in any demo's exports, is
    a real finding.
    """
    legitimate = "Programmatic risk: None."  # CBO's own rating, not a Python `None` leak
    checked = 0
    for name in ("a_cbo_gcv_2013", "validation_gao_21_460", "control_gao_15_548",
                 "budget_books"):
        out_dir = REPO_ROOT / "demos" / name / "out"
        if not out_dir.exists():
            continue
        for path in sorted(out_dir.glob("export-*.*")):
            text = path.read_text(encoding="utf-8").replace(legitimate, "")
            assert "None]" not in text, f"{path}: raw None"
            assert ": None" not in text, f"{path}: raw None"
            checked += 1
    assert checked, "no demo export files found to check — run the demos first"


# ---- M10: a small non-U fixture exercising every export's withholding path --------


def test_every_export_withholds_a_classified_evidence_item_under_unclassified():
    """Review round 1, M10 — Demo A alone never exercises this (every one of its
    Evidence items is `level: U, metadataLevel: U`, so five of the six exports are
    byte-identical between the two renderings). This is C1's own probe, generalised
    into a permanent regression test across every export rather than just RTVM.

    Review round 2 second axis: `ev-test`'s `scopeOfValidity.questionClass` is also
    changed (to `"cost"`, mismatching `cl-2`'s own `"other"`, with no
    `reuseJustification` on the supporting entry), which forces `check_scope` to
    raise a `ReusePastPurpose` finding whose message embeds the same needle via
    `builtToAnswer`. The original fixture never triggered this rule, which is why
    I1's leak — `docket.exports.gsn` copying that finding's free-text message
    straight into `dialectic.challenge[].message` — passed unnoticed under the
    original M10 test.
    """
    g = complete_graph()
    ev = g.get("ev-test")
    needle = "SECRETSCOPE-XYZ"
    g.put(
        {**ev, "rev": ev["rev"] + 1, "createdBy": ev["createdBy"],
         "classification": {"level": "S", "metadataLevel": "S"},
         "scopeOfValidity": {**ev["scopeOfValidity"], "builtToAnswer": needle,
                             "questionClass": "cost"}},
        ev["createdBy"],
    )

    from docket.kernel.scope import check_scope

    findings = check_scope(g, "ep-1")
    assert any(
        f.rule == "ReusePastPurpose" and needle in f.message for f in findings
    ), "fixture must actually trigger ReusePastPurpose for this to be a real probe"

    for name in EXPORTS:
        text = export_text(g, name=name, episode_id="ep-1", rendering="unclassified")
        assert needle not in text, f"{name} leaked the needle under unclassified"

    # The full rendering must show the needle *somewhere* — proving the absence above
    # is real withholding, not just that no export ever touches this evidence at all.
    full_hits = [
        name for name in EXPORTS
        if needle in export_text(g, name=name, episode_id="ep-1", rendering="full")
    ]
    assert full_hits, "expected the needle to appear in at least one full-rendering export"


# ---- build_package / Machine annex wiring (ruling R3) ------------------------------


def test_build_package_annex_lists_export_filenames_and_hashes(tmp_path):
    g = complete_graph()
    exports = compute_all(g, "ep-1", rendering="unclassified")
    pkg, text = build_package(
        g, "ep-1", rendering="unclassified", now=COMPLETE_NOW, out_dir=tmp_path
    )
    for filename, export_body in exports:
        assert f"- {filename}  sha256:{sha256_hex(export_body)}" in text
        assert (tmp_path / filename).read_text(encoding="utf-8") == export_body
    assert pkg["hash"] == sha256_hex(text)


def test_build_package_without_out_dir_still_lists_hashes_and_matches_with_out_dir(tmp_path):
    g1 = complete_graph()
    _, text_no_dir = build_package(
        g1, "ep-1", rendering="unclassified", now=COMPLETE_NOW, out_dir=None
    )
    g2 = complete_graph()
    _, text_with_dir = build_package(
        g2, "ep-1", rendering="unclassified", now=COMPLETE_NOW, out_dir=tmp_path
    )
    assert text_no_dir == text_with_dir


def test_build_package_two_out_roots_produce_identical_package_hash(tmp_path):
    g1 = complete_graph()
    pkg1, _ = build_package(
        g1, "ep-1", rendering="unclassified", now=COMPLETE_NOW, out_dir=tmp_path / "a"
    )
    g2 = complete_graph()
    pkg2, _ = build_package(
        g2, "ep-1", rendering="unclassified", now=COMPLETE_NOW, out_dir=tmp_path / "b"
    )
    assert pkg1["hash"] == pkg2["hash"]


# ---- resolve_plan_id / resolve_vva_id ----------------------------------------------


def test_resolve_plan_id_absent_and_present():
    g = complete_graph()
    plan_id, err = resolve_plan_id(g, "ep-1")
    assert plan_id == "pl-1" and err is None

    from tests.kernel.conftest import H, episode

    g2 = Graph()
    g2.put(episode(oid="ep-bare", charter="ch-missing"), H)
    plan_id, err = resolve_plan_id(g2, "ep-bare")
    assert plan_id is None and err is not None


def test_resolve_vva_id_zero_and_one():
    g = complete_graph()
    vva_id, err = resolve_vva_id(g, "ep-1")
    assert vva_id == "vva-1" and err is None

    from tests.kernel.conftest import H, episode

    g2 = Graph()
    g2.put(episode(oid="ep-bare", charter="ch-missing"), H)
    vva_id, err = resolve_vva_id(g2, "ep-bare")
    assert vva_id is None and err is not None
