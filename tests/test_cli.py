import json
from pathlib import Path

from click.testing import CliRunner

from docket.cli import main
from docket.store import Graph
from tests.kernel import conftest as kc
from tests.kernel.conftest import COMPLETE_NOW, COMPLETE_SEED, complete_graph, revise

H = {"actorType": "human", "actorId": "t"}
NOW = "2026-09-05T12:00:00Z"


def test_validate_reports_findings(tmp_path):
    g = Graph()
    g.put(
        {
            "id": "gr-1", "type": "GroundRule", "rev": 1, "createdBy": H,
            "createdAt": "2026-09-04", "statement": "s", "source": "ev-x",
        },
        H,
    )
    g.save(tmp_path)
    r = CliRunner().invoke(main, ["validate", str(tmp_path)])
    assert r.exit_code == 1 and "ref-integrity" in r.output


def test_schema_list():
    r = CliRunner().invoke(main, ["schema", "list"])
    assert r.exit_code == 0 and "Charter" in r.output and "Narrative" in r.output


def test_validate_reports_an_unknown_policy_id_without_a_traceback(tmp_path):
    g = Graph()
    g.put(
        {
            "id": "r-1", "type": "Rationale", "rev": 1, "createdBy": H,
            "createdAt": "2026-09-04", "text": "t", "author": "a",
        },
        H,
    )
    g.save(tmp_path)
    r = CliRunner().invoke(main, ["validate", str(tmp_path), "--policy", "pol-nope"])
    assert r.exit_code == 1
    assert "policy 'pol-nope' not found" in r.output + r.stderr
    assert isinstance(r.exception, SystemExit)


# ---------------------------------------------------------------------------------
# A minimal, pre-evaluation two-alternative graph for `docket evaluate`.
#
# `tests.kernel.conftest.two_alt_graph` is the natural thing to reuse here, but
# it is a `@pytest.fixture` in a different test package's module, and pytest
# fixtures are not callable directly outside dependency injection — so this rebuilds
# the same shape from the same `tests.kernel.conftest` builders instead.
# ---------------------------------------------------------------------------------


def _pre_run_graph(*, approved: bool = True) -> Graph:
    g = Graph()
    plan_fields = dict(
        episode="ep-1", policyBasis="pol-1", deviations=[],
        steps=[{"id": "s1", "evaluator": "mdl-1", "method": "mavt",
                "alternatives": ["alt-x", "alt-y"], "measures": ["m-a", "m-b"],
                "weightSet": "ws-1",
                "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}],
    )
    if approved:
        plan_fields["approvedBy"] = {"actorId": "fixture", "date": "2026-08-27"}
    ep_fields = {
        **kc.episode(), "alternatives": ["alt-x", "alt-y"],
        "observations": ["ob-xa", "ob-xb", "ob-ya", "ob-yb"],
        "weightSets": ["ws-1"], "models": ["mdl-1"], "plan": "pl-1",
        "objectives": ["obj-1"],
    }
    if approved:
        ep_fields.update(kc.plan_approved())
    kc.put_all(
        g,
        kc.policy(), kc.evidence("ev-doc"), kc.drs(), kc.charter(),
        kc.gap("gap-v", impact="informational", confirmed=True),
        kc.objective("obj-1", measures=["m-a", "m-b"]),
        kc.measure("m-a", "obj-1"), kc.measure("m-b", "obj-1"),
        kc.model("mdl-1", vva={"$gap": "gap-v"}),
        kc.alternative("alt-x", order=1), kc.alternative("alt-y", baseline=True, order=2),
        kc.observation("ob-xa", "alt-x", "m-a", 10),
        kc.observation("ob-xb", "alt-x", "m-b", 0),
        kc.observation("ob-ya", "alt-y", "m-a", 0),
        kc.observation("ob-yb", "alt-y", "m-b", {"lo": 20, "hi": 40}),
        kc.obj("ws-1", "WeightSet", name="w", method="stated",
               weights={"m-a": 0.5, "m-b": 0.5}, provenance="ev-doc"),
        kc.obj("pl-1", "Plan", **plan_fields),
        ep_fields,
    )
    return g


def test_evaluate_seals_a_run_and_writes_flip_analyses(tmp_path):
    g = _pre_run_graph()
    kc.assert_history_honest(g)
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["evaluate", str(tmp_path), "--plan", "pl-1", "--seed", "7", "--now", NOW]
    )

    assert r.exit_code == 0, r.output
    assert "run-pl-1-s1: ranking alt-y > alt-x; 2 flip analyses" in r.output
    g2 = Graph.load(tmp_path)
    assert g2.has("run-pl-1-s1")
    assert len(g2.get("ep-1")["flipAnalyses"]) == 2


def test_evaluate_reports_a_g2_refusal_without_a_traceback(tmp_path):
    g = _pre_run_graph(approved=False)
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["evaluate", str(tmp_path), "--plan", "pl-1", "--seed", "7", "--now", NOW]
    )

    assert r.exit_code == 1
    assert r.exc_info[0] is SystemExit
    assert "has not been approved" in r.output + r.stderr
    # nothing was computed, so nothing was written back to the saved store
    assert not Graph.load(tmp_path).has("run-pl-1-s1")


def test_evaluate_reports_an_unknown_plan_id_without_a_traceback(tmp_path):
    g = _pre_run_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["evaluate", str(tmp_path), "--plan", "pl-missing", "--now", NOW]
    )

    assert r.exit_code == 1
    assert r.exc_info[0] is SystemExit
    assert "pl-missing" in r.output + r.stderr


def test_readiness_reports_ready_and_records_the_report(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["readiness", str(tmp_path), "--episode", "ep-1", "--seed", str(COMPLETE_SEED),
         "--now", COMPLETE_NOW],
    )

    assert r.exit_code == 0, r.output
    assert "rr-ep-1-1: ready=True blockers=0" in r.output
    assert Graph.load(tmp_path).get("ep-1")["readiness"] == "rr-ep-1-1"


def test_readiness_json_prints_the_canonical_report(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["readiness", str(tmp_path), "--episode", "ep-1", "--seed", str(COMPLETE_SEED),
         "--now", COMPLETE_NOW, "--json"],
    )

    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["ready"] is True and payload["id"] == "rr-ep-1-1"


def test_readiness_exits_1_and_prints_blockers_when_not_ready(tmp_path):
    g = complete_graph()
    revise(g, "ep-1", alternatives=["alt-a", "alt-b"])  # drops the baseline
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["readiness", str(tmp_path), "--episode", "ep-1", "--seed", str(COMPLETE_SEED),
         "--now", COMPLETE_NOW],
    )

    assert r.exit_code == 1
    assert "ready=False" in r.output
    assert "baseline-present" in r.output


def test_readiness_reports_a_missing_store_without_a_traceback(tmp_path):
    r = CliRunner().invoke(
        main, ["readiness", str(tmp_path), "--episode", "ep-1", "--now", COMPLETE_NOW]
    )
    assert r.exit_code == 1
    assert "store not found" in r.output + r.stderr


def test_render_writes_the_package_file_and_prints_its_hash(tmp_path):
    # `--out` must not be a subdirectory of `graph_dir`: `Graph.save` atomically
    # replaces the *entire* graph directory, which would delete anything this
    # command just wrote underneath it.
    graph_dir = tmp_path / "graph"
    out_dir = tmp_path / "out"
    g = complete_graph()
    g.save(graph_dir)

    r = CliRunner().invoke(
        main,
        ["render", str(graph_dir), "--episode", "ep-1", "--rendering", "full",
         "--now", COMPLETE_NOW, "--out", str(out_dir)],
    )

    assert r.exit_code == 0, r.output
    assert (out_dir / "package-full.md").exists()
    assert "hash" in r.output


def test_render_prints_markdown_to_stdout_by_default(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["render", str(tmp_path), "--episode", "ep-1", "--now", COMPLETE_NOW]
    )

    assert r.exit_code == 0, r.output
    assert "# Decision Package — ep-1" in r.output


def test_render_json_prints_the_sealed_package(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["render", str(tmp_path), "--episode", "ep-1", "--now", COMPLETE_NOW, "--json"],
    )

    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["type"] == "DecisionPackage" and payload["rendering"] == "full"


def test_verify_reports_identical_for_a_freshly_rendered_graph(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["verify", str(tmp_path), "--episode", "ep-1", "--now", COMPLETE_NOW,
         "--seed", str(COMPLETE_SEED), "--rendering", "unclassified"],
    )

    assert r.exit_code == 0, r.output
    assert "identical=True" in r.output


def test_verify_json_prints_the_full_payload(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["verify", str(tmp_path), "--episode", "ep-1", "--now", COMPLETE_NOW,
         "--seed", str(COMPLETE_SEED), "--json"],
    )

    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["identical"] is True
    assert payload["differing"] == []
    assert payload["hashes"] == payload["second"]
    assert "package" in payload["hashes"]


def test_verify_reports_an_unknown_episode_without_a_traceback(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["verify", str(tmp_path), "--episode", "nope", "--now", COMPLETE_NOW],
    )

    assert r.exit_code != 0
    assert "nope" in r.output
    assert isinstance(r.exception, SystemExit)


def test_verify_does_not_save_the_graph(tmp_path):
    g = complete_graph()
    g.save(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    r = CliRunner().invoke(
        main, ["verify", str(tmp_path), "--episode", "ep-1", "--now", COMPLETE_NOW],
    )

    assert r.exit_code == 0, r.output
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_verify_cli_exits_nonzero_on_a_hash_mismatch(tmp_path, monkeypatch):
    """I1 (review fix round): drive `docket verify`'s non-happy path — the one where
    the two renders actually disagree — by monkeypatching the shared `render_hashes`
    primitive `verify_determinism` calls twice. Closes the previously-untested
    `SystemExit(1)` / `differs: <name>` branch in `src/docket/cli.py`."""
    from unittest.mock import Mock

    import docket.kernel.verify as verify_module

    g = complete_graph()
    g.save(tmp_path)

    first = {"package": "aaaa"}
    second = {"package": "bbbb"}
    monkeypatch.setattr(
        verify_module, "render_hashes", Mock(side_effect=[first, second])
    )

    r = CliRunner().invoke(
        main, ["verify", str(tmp_path), "--episode", "ep-1", "--now", COMPLETE_NOW],
    )

    assert r.exit_code == 1, r.output
    assert "identical=False" in r.output
    assert "differs: package" in r.output


def test_transition_succeeds_then_records_a_refusal_on_disk(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r1 = CliRunner().invoke(
        main,
        ["transition", str(tmp_path), "--episode", "ep-1", "--to", "EVALUATED",
         "--actor", "pm", "--now", COMPLETE_NOW],
    )
    assert r1.exit_code == 0, r1.output
    assert "ep-1: pm" in r1.output and "EVALUATED" in r1.output

    # PENDING_SIGNATURE requires a readiness report on this episode; none was
    # computed, so the gate refuses — and the refusal must still be saved.
    r2 = CliRunner().invoke(
        main,
        ["transition", str(tmp_path), "--episode", "ep-1", "--to", "PENDING_SIGNATURE",
         "--actor", "pm", "--now", COMPLETE_NOW],
    )
    assert r2.exit_code == 1
    assert "refused" in r2.output and "readiness-present" in r2.output

    ep = Graph.load(tmp_path).get("ep-1")
    assert ep["lifecycleState"] == "EVALUATED"  # the refusal did not move the state
    last = ep["transitions"][-1]
    assert last["to"] == "PENDING_SIGNATURE" and last["refused"] is True
    assert last["checksUnsatisfied"] == ["readiness-present"]
    assert last["actor"] == {"actorType": "human", "actorId": "pm"}


def test_transition_requires_an_explicit_actor(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["transition", str(tmp_path), "--episode", "ep-1", "--to", "EVALUATED",
         "--now", COMPLETE_NOW],
    )

    assert r.exit_code == 2
    assert "actor" in (r.output + r.stderr).lower()


def test_every_command_requires_now(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(main, ["readiness", str(tmp_path), "--episode", "ep-1"])

    assert r.exit_code == 2
    assert "now" in (r.output + r.stderr).lower()


# ---------------------------------------------------------------------------------
# Round 1: validate grouping, flip, refresh, diff, gates, and the hard --out refusal.
# ---------------------------------------------------------------------------------


def test_validate_groups_findings_by_severity(tmp_path):
    g = Graph()
    g.put(
        {
            "id": "gr-1", "type": "GroundRule", "rev": 1, "createdBy": H,
            "createdAt": "2026-09-04", "statement": "s", "source": "ev-x",
        },
        H,
    )
    g.save(tmp_path)

    r = CliRunner().invoke(main, ["validate", str(tmp_path)])

    assert r.exit_code == 1
    assert "blocking (" in r.output
    # a blocking group, if present, is printed before any warning/info group
    assert r.output.index("blocking (") < r.output.index("finding(s)")


def _base_graph() -> Graph:
    """The shape of `tests.kernel.conftest.base_graph`, rebuilt as a plain function —
    see `_pre_run_graph`'s docstring for why the fixture itself can't be imported."""
    g = Graph()
    kc.put_all(g, kc.policy(), kc.evidence("ev-doc"), kc.drs(), kc.charter(), kc.episode())
    return g


def _assumption(oid: str, statement: str) -> dict:
    return kc.obj(
        oid, "Assumption", statement=statement, linchpin=False, rationale="r",
        evidence="ev-doc", implicationsIfWrong="i", indicatorsThatWouldAlter=["x"],
        variedInSensitivity=False,
    )


def _refreshed_graph(tmp_path):
    """A base graph, refreshed once via the CLI, saved at `tmp_path`."""
    g = _base_graph()
    kc.put_all(
        g,
        _assumption("as-old", "minimal crew"),
        _assumption("as-new", "30 dismounts per platoon"),
        {**kc.episode(), "rev": 2, "lifecycleState": "SIGNED", "assumptions": ["as-old"]},
        kc.obj("prg-1", "DecisionProgram", name="p", charter="ch-1", episodes=["ep-1"],
               refreshTriggers=[], diffs=[]),
        kc.obj("rt-1", "RefreshTrigger", kind="assumption-changed", source="s",
               description="d", detectedAt="2026-09-01", affected=["as-old"]),
    )
    g.save(tmp_path)
    r = CliRunner().invoke(
        main,
        ["refresh", str(tmp_path), "--program", "prg-1", "--trigger", "rt-1",
         "--actor", "pm", "--now", NOW, "--replacements", "as-old=as-new"],
    )
    assert r.exit_code == 0, r.output
    return r


def test_refresh_opens_a_new_episode(tmp_path):
    r = _refreshed_graph(tmp_path)
    assert "ep-1-r2 opened by pm" in r.output
    assert "supersedes ep-1" in r.output and "prior now SUSPECT" in r.output


def test_diff_reports_the_refresh_as_text(tmp_path):
    _refreshed_graph(tmp_path)

    r = CliRunner().invoke(
        main, ["diff", str(tmp_path), "--prior", "ep-1", "--new", "ep-1-r2", "--now", NOW]
    )
    assert r.exit_code == 0, r.output
    assert "pairing=replacements" in r.output
    assert "added=1" in r.output and "removed=1" in r.output


def test_diff_json_matches_diff_episodes(tmp_path):
    _refreshed_graph(tmp_path)

    r = CliRunner().invoke(
        main,
        ["diff", str(tmp_path), "--prior", "ep-1", "--new", "ep-1-r2", "--now", NOW, "--json"],
    )
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["pairing"] == "replacements"
    assert payload["added"] == ["as-new"] and payload["removed"] == ["as-old"]


def test_refresh_rejects_a_malformed_replacements_pair(tmp_path):
    g = _base_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["refresh", str(tmp_path), "--program", "prg-x", "--trigger", "rt-x",
         "--actor", "pm", "--now", NOW, "--replacements", "no-equals-sign"],
    )

    assert r.exit_code == 2


def test_refresh_requires_an_explicit_actor(tmp_path):
    g = _base_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["refresh", str(tmp_path), "--program", "prg-x", "--trigger", "rt-x", "--now", NOW],
    )

    assert r.exit_code == 2
    assert "actor" in (r.output + r.stderr).lower()


def test_flip_writes_analyses_and_prints_ranked_flips_and_robustness(tmp_path):
    from docket.kernel.evaluate import evaluate as _evaluate

    g = _pre_run_graph()
    kc.assert_history_honest(g)
    run = _evaluate(g, "pl-1", seed=7, now=NOW)[0]  # deliberately no flip_analysis yet
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["flip", str(tmp_path), "--run", run["id"], "--seed", "7", "--now", NOW]
    )

    assert r.exit_code == 0, r.output
    assert f"flip-{run['id']}-1" in r.output
    assert "robustness" in r.output
    g2 = Graph.load(tmp_path)
    assert len(g2.get("ep-1")["flipAnalyses"]) == 2

    r_json = CliRunner().invoke(
        main,
        ["flip", str(tmp_path), "--run", run["id"], "--seed", "7", "--now", NOW, "--json"],
    )
    assert r_json.exit_code == 1  # flip-analysis ids already exist; append-only refuses
    assert "append-only" in r_json.output + r_json.stderr


def test_gates_reports_state_history_and_next_target_checks(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(main, ["gates", str(tmp_path), "--episode", "ep-1"])

    assert r.exit_code == 0, r.output
    assert "ep-1: PLAN_APPROVED" in r.output
    assert "MODEL_APPROVED" in r.output  # from the recorded history
    assert "→ EVALUATED" in r.output
    assert "every-step-has-run=satisfied" in r.output


def test_gates_json_lists_next_targets_from_lifecycle_edges(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(main, ["gates", str(tmp_path), "--episode", "ep-1", "--json"])

    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["lifecycleState"] == "PLAN_APPROVED"
    targets = {t["to"]: t for t in payload["nextTargets"]}
    assert set(targets) == {"EVALUATED", "SUSPECT", "VOID"}
    assert {c["name"] for c in targets["EVALUATED"]["checks"]} == {"every-step-has-run"}
    assert targets["EVALUATED"]["actor"] == "any"
    assert targets["VOID"]["actor"] == "human"
    assert targets["SUSPECT"]["actor"] == "kernel"


def test_gates_does_not_save_or_transition(tmp_path):
    g = complete_graph()
    g.save(tmp_path)
    before = Graph.load(tmp_path).log()

    r = CliRunner().invoke(main, ["gates", str(tmp_path), "--episode", "ep-1"])

    assert r.exit_code == 0, r.output
    assert Graph.load(tmp_path).log() == before


def test_render_refuses_when_out_is_the_graph_dir_or_nested_in_it(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    for out in (tmp_path, tmp_path / "out"):
        r = CliRunner().invoke(
            main,
            ["render", str(tmp_path), "--episode", "ep-1", "--now", COMPLETE_NOW,
             "--out", str(out)],
        )
        assert r.exit_code == 2, r.output
        assert "subdirectory" in (r.output + r.stderr).lower()


def test_refresh_rejects_a_replacements_key_named_twice(tmp_path):
    g = _base_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["refresh", str(tmp_path), "--program", "prg-x", "--trigger", "rt-x",
         "--actor", "pm", "--now", NOW,
         "--replacements", "as-1=as-2", "--replacements", "as-1=as-3"],
    )

    assert r.exit_code == 2
    assert "twice" in r.output


# ---- export (plan 06 task 1) ------------------------------------------------------


def test_export_prints_a_single_format_to_stdout_by_default(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["export", str(tmp_path), "--episode", "ep-1", "--format", "rtvm"],
    )

    assert r.exit_code == 0, r.output
    assert r.output.startswith("claim_id,claim_text,")


def test_export_single_format_writes_one_file_and_prints_its_hash(tmp_path):
    graph_dir = tmp_path / "graph"
    out_dir = tmp_path / "out"
    g = complete_graph()
    g.save(graph_dir)

    r = CliRunner().invoke(
        main,
        ["export", str(graph_dir), "--episode", "ep-1", "--format", "madr",
         "--rendering", "full", "--out", str(out_dir)],
    )

    assert r.exit_code == 0, r.output
    assert (out_dir / "export-madr-full.md").exists()
    assert "export-madr-full.md" in r.output


def test_export_format_all_requires_out(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(main, ["export", str(tmp_path), "--episode", "ep-1", "--format", "all"])

    assert r.exit_code == 2
    assert "--out" in (r.output + r.stderr)


def test_export_format_all_writes_every_file_and_lists_hashes(tmp_path):
    graph_dir = tmp_path / "graph"
    out_dir = tmp_path / "out"
    g = complete_graph()
    g.save(graph_dir)

    r = CliRunner().invoke(
        main,
        ["export", str(graph_dir), "--episode", "ep-1", "--format", "all",
         "--out", str(out_dir)],
    )

    assert r.exit_code == 0, r.output
    extensions = {
        "prov": "json", "gsn": "json", "dmn": "xml", "milstd3022": "md",
        "madr": "md", "rtvm": "csv",
    }
    for name, ext in extensions.items():
        assert (out_dir / f"export-{name}-unclassified.{ext}").exists()
    lines = [ln for ln in r.output.splitlines() if ln.strip()]
    assert len(lines) == 6


def test_export_dmn_refuses_when_the_episode_has_no_plan(tmp_path):
    g = _base_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["export", str(tmp_path), "--episode", "ep-1", "--format", "dmn"],
    )

    assert r.exit_code != 0
    assert "plan" in r.output.lower()


def test_export_dmn_plan_override_is_used(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["export", str(tmp_path), "--episode", "ep-1", "--format", "dmn",
               "--plan", "pl-1"],
    )

    assert r.exit_code == 0, r.output
    assert "<" in r.output  # XML


def test_export_milstd3022_refuses_when_no_vva_is_reachable(tmp_path):
    g = _base_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["export", str(tmp_path), "--episode", "ep-1", "--format", "milstd3022"],
    )

    assert r.exit_code != 0
    assert "vvarecord" in r.output.lower()


def test_export_reports_an_unknown_episode_without_a_traceback(tmp_path):
    g = complete_graph()
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["export", str(tmp_path), "--episode", "nope", "--format", "madr"],
    )

    assert r.exit_code != 0
    assert "nope" in r.output


def test_export_refuses_when_out_is_the_graph_dir_or_nested_in_it(tmp_path):
    """M3."""
    g = complete_graph()
    g.save(tmp_path)

    for out in (tmp_path, tmp_path / "graph" / "objects"):
        r = CliRunner().invoke(
            main,
            ["export", str(tmp_path), "--episode", "ep-1", "--format", "madr",
             "--out", str(out)],
        )
        assert r.exit_code == 2, r.output
        assert "subdirectory" in (r.output + r.stderr).lower()


def test_export_single_format_stdout_is_byte_identical_to_the_written_file(tmp_path):
    """M9: the I9 regression the review's own probe caught — echoing to stdout must
    not add a trailing newline the written file (and the Machine annex's sha256) does
    not have."""
    graph_dir = tmp_path / "graph"
    out_dir = tmp_path / "out"
    g = complete_graph()
    g.save(graph_dir)

    to_file = CliRunner().invoke(
        main,
        ["export", str(graph_dir), "--episode", "ep-1", "--format", "prov",
         "--rendering", "full", "--out", str(out_dir)],
    )
    assert to_file.exit_code == 0, to_file.output
    to_stdout = CliRunner().invoke(
        main, ["export", str(graph_dir), "--episode", "ep-1", "--format", "prov",
               "--rendering", "full"],
    )
    assert to_stdout.exit_code == 0, to_stdout.output

    written = (out_dir / "export-prov-full.json").read_bytes()
    assert to_stdout.output.encode("utf-8") == written


def test_export_cli_matches_build_package_bytes_and_hash(tmp_path):
    """M9: `docket export --format all` must write the exact bytes `build_package`
    writes for the same graph/rendering, and the CLI's printed sha256 must match the
    Machine annex's own line for the same file."""
    from docket.canon import sha256_hex
    from docket.kernel.render import build_package

    graph_dir = tmp_path / "graph"
    via_build = tmp_path / "via_build"
    via_cli = tmp_path / "via_cli"
    g = complete_graph()
    g.save(graph_dir)

    g2 = Graph.load(graph_dir)
    _pkg, text = build_package(
        g2, "ep-1", rendering="full", now=COMPLETE_NOW, out_dir=via_build,
    )

    r = CliRunner().invoke(
        main,
        ["export", str(graph_dir), "--episode", "ep-1", "--format", "all",
         "--rendering", "full", "--out", str(via_cli)],
    )
    assert r.exit_code == 0, r.output
    printed = dict(line.split("  sha256:") for line in r.output.splitlines() if line.strip())

    for path in via_build.iterdir():
        if path.name.startswith("export-"):
            cli_path = via_cli / path.name
            assert cli_path.read_bytes() == path.read_bytes(), path.name
            assert printed[path.name] == sha256_hex(path.read_text(encoding="utf-8"))
            assert f"- {path.name}  sha256:{printed[path.name]}" in text


# ---------------------------------------------------------------------------------
# `docket ui` (plan 07 Task 9, Step 1) — never actually binds a socket or opens a real
# browser in a test: `uvicorn.run` and `webbrowser.open` are monkeypatched at their
# real, shared module attributes (not a `docket.cli`-local import), because `ui()`
# imports both lazily inside the function body, matching every other command in this
# file (`export_cmd`'s own comment explains why: nothing this heavy is paid at
# `docket --help` time).
# ---------------------------------------------------------------------------------


def test_ui_help_shows_every_option():
    r = CliRunner().invoke(main, ["ui", "--help"])
    assert r.exit_code == 0
    for opt in ("--port", "--host", "--open", "--no-open", "--demo", "--seed-demos",
                "--no-seed-demos"):
        assert opt in r.output, r.output


def test_ui_no_open_records_host_and_port_and_never_touches_a_browser(monkeypatch):
    calls: dict = {}

    def fake_run(app, host, port):
        calls["app"] = app
        calls["host"] = host
        calls["port"] = port

    def fail_open(*_args, **_kwargs):
        raise AssertionError("docket ui --no-open must never open a browser")

    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setattr("webbrowser.open", fail_open)

    r = CliRunner().invoke(
        main, ["ui", "--no-open", "--no-seed-demos", "--host", "127.0.0.1", "--port", "9123"],
    )
    assert r.exit_code == 0, r.output
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 9123
    assert calls["app"] is not None


def test_ui_prints_the_build_line_and_still_serves_when_the_spa_is_missing(
    monkeypatch, tmp_path,
):
    served = {}

    def fake_run(app, host, port):
        served["ran"] = True

    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setenv("DOCKET_STATIC_DIR", str(tmp_path / "no-such-static"))

    r = CliRunner().invoke(main, ["ui", "--no-open", "--no-seed-demos"])
    assert r.exit_code == 0, r.output
    assert "make ui-build" in r.output
    assert served.get("ran") is True


def test_ui_seeds_a_missing_demo_store_and_leaves_a_built_one_alone(monkeypatch, tmp_path):
    demos_root = tmp_path / "demos"
    # Demo B already "built": its `run()` must never be called.
    b_graph = demos_root / "b_omfv_2019_2023" / "out" / "graph"
    b_graph.mkdir(parents=True)
    (b_graph / "log.jsonl").write_text("")

    def fail_if_called(out_dir):
        raise AssertionError(f"demo-b is already built; run() must not be called ({out_dir})")

    seeded: dict = {}

    def fake_run(out_dir):
        seeded["out_dir"] = Path(out_dir)
        graph = Path(out_dir) / "graph"
        graph.mkdir(parents=True, exist_ok=True)
        (graph / "log.jsonl").write_text("")

    monkeypatch.setattr("demos.a_cbo_gcv_2013.run.run", fake_run)
    monkeypatch.setattr("demos.b_omfv_2019_2023.run.run", fail_if_called)
    monkeypatch.setenv("DOCKET_DEMOS_DIR", str(demos_root))
    monkeypatch.setenv("DOCKET_STATIC_DIR", str(tmp_path / "no-such-static"))
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: None)

    r = CliRunner().invoke(main, ["ui", "--no-open", "--seed-demos"])
    assert r.exit_code == 0, r.output
    assert seeded["out_dir"] == demos_root / "a_cbo_gcv_2013" / "out"
    assert "demo-a" in r.output


def test_demo_help_shows_the_out_option():
    r = CliRunner().invoke(main, ["demo", "--help"])
    assert r.exit_code == 0
    assert "--out" in r.output


def test_demo_all_wraps_run_all_with_the_resolved_out_root(monkeypatch, tmp_path):
    calls: dict = {}

    def fake_run_all(root):
        calls["root"] = Path(root)
        return [
            {"demo": "a_cbo_gcv_2013", "present": True, "outDir": "x",
             "resultsFile": "x/results.json"},
            {"demo": "b_omfv_2019_2023", "present": False,
             "reason": "demos.b_omfv_2019_2023.run is absent"},
        ]

    monkeypatch.setattr("demos.run_all.run_all", fake_run_all)

    r = CliRunner().invoke(main, ["demo", "all", "--out", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert calls["root"] == tmp_path.resolve()
    assert "a_cbo_gcv_2013: ok — x/results.json" in r.output
    assert "b_omfv_2019_2023: skipped — demos.b_omfv_2019_2023.run is absent" in r.output


def test_demo_single_name_calls_only_that_demos_run(monkeypatch, tmp_path):
    calls: dict = {}

    def fake_run(out_dir):
        calls["out_dir"] = Path(out_dir)

    def fail_if_called(out_dir):
        raise AssertionError(f"only the named demo's run() may be called ({out_dir})")

    monkeypatch.setattr("demos.ablation.run.run", fake_run)
    monkeypatch.setattr("demos.budget_books.run.run", fail_if_called)

    r = CliRunner().invoke(main, ["demo", "ablation", "--out", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert calls["out_dir"] == tmp_path / "demos" / "ablation" / "out"
    assert "ablation: ok" in r.output


def test_demo_unknown_name_is_a_clean_usage_error(tmp_path):
    r = CliRunner().invoke(main, ["demo", "not-a-real-demo", "--out", str(tmp_path)])
    assert r.exit_code == 2
    assert "unknown demo" in r.output
    assert "'all'" in r.output


def test_demo_out_defaults_to_the_repo_root(monkeypatch):
    from demos.run_all import REPO_ROOT

    calls: dict = {}

    def fake_run_all(root):
        calls["root"] = root
        return []

    monkeypatch.setattr("demos.run_all.run_all", fake_run_all)

    r = CliRunner().invoke(main, ["demo", "all"])
    assert r.exit_code == 0, r.output
    assert calls["root"] == REPO_ROOT


def test_installed_docket_binary_can_run_a_demo_from_any_cwd(tmp_path):
    """The console script (not the in-process runner) must import `demos/`, which sits
    outside the package: it failed with ModuleNotFoundError before the path fix."""
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    binary = Path(sys.executable).parent / "docket"
    if not binary.exists():
        binary = shutil.which("docket")
    assert binary, "no docket console script found"
    out = tmp_path / "out"
    r = subprocess.run(
        [str(binary), "demo", "budget_books", "--out", str(out)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr[-800:]
    assert any(out.rglob("*.json")), "the demo wrote nothing"
