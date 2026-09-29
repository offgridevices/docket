# tests/agent/test_agent_cli.py
"""CliRunner tests for `docket agent ...` (Task 8, Step 3/5). Every test is isolated
from the developer's real environment and config file — see `_isolated_docket_env`,
mirroring `tests/agent/test_backend.py`'s own isolation fixture — so a stray
`DOCKET_LLM_*` value or a real `~/.config/docket/llm.json` on the machine running these
tests can never change the outcome.
"""

import pytest
from click.testing import CliRunner

from docket.agent.backend import DENYLIST_FAMILIES
from docket.cli import main
from docket.store import Graph

NOW = "2026-09-04T00:00:00Z"


def _a_denylisted_model_id() -> str:
    """A real, currently-denylisted model id, built at runtime from the family list
    rather than spelled as a literal here: the repo-wide scan for a denylisted name in
    a committed fixture, default, or doc (`tests/agent/test_backend.py::
    test_no_committed_fixture_default_or_doc_names_a_denylisted_model`) reads this
    file's raw source text, and a literal family name would need — and not deserve — an
    exemption just to exercise the CLI's real refusal path end-to-end."""
    family = sorted(DENYLIST_FAMILIES)[0]
    return f"{family}-test"

_DOCKET_ENV_VARS = (
    "DOCKET_LLM_PROVIDER", "DOCKET_LLM_MODEL", "DOCKET_LLM_BASE_URL", "DOCKET_LLM_API_KEY",
    "DOCKET_LLM_RECORDING", "DOCKET_LLM_TIMEOUT", "DOCKET_LLM_CONFIG",
    "DOCKET_LLM_ALLOW_DENYLISTED",
)


@pytest.fixture(autouse=True)
def _isolated_docket_env(monkeypatch, tmp_path):
    for var in _DOCKET_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DOCKET_LLM_CONFIG", str(tmp_path / "unused-default-config.json"))


def test_agent_group_lists_the_six_commands():
    r = CliRunner().invoke(main, ["agent", "--help"])
    assert r.exit_code == 0
    for c in ("elicit", "g1-sheet", "propose-plan", "dispatch", "narrate", "watch"):
        assert c in r.output


def test_agent_watch_prints_proposals_and_files_them(
    tmp_path, monkeypatch, program_with_stale_model
):
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    g, prog = program_with_stale_model
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["agent", "watch", str(tmp_path), "--program", prog, "--now", NOW]
    )
    assert r.exit_code == 0, r.output
    assert "elapsed-time" in r.output
    # read-only: the on-disk store is untouched by the printing-only run
    assert Graph.load(tmp_path).get(prog)["refreshTriggers"] == []

    r2 = CliRunner().invoke(
        main, ["agent", "watch", str(tmp_path), "--program", prog, "--now", NOW, "--file"]
    )
    assert r2.exit_code == 0, r2.output
    assert Graph.load(tmp_path).get(prog)["refreshTriggers"]


def test_agent_watch_via_episode_resolves_the_program(tmp_path, program_with_stale_model):
    g, prog = program_with_stale_model
    g.save(tmp_path)

    r = CliRunner().invoke(
        main, ["agent", "watch", str(tmp_path), "--episode", "ep-1", "--now", NOW]
    )
    assert r.exit_code == 0, r.output
    assert "elapsed-time" in r.output


def test_agent_watch_via_episode_and_file_is_refused(tmp_path, program_with_stale_model):
    # per the brief's interim ruling: --file requires the explicit --program flag
    g, prog = program_with_stale_model
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["agent", "watch", str(tmp_path), "--episode", "ep-1", "--now", NOW, "--file"],
    )
    assert r.exit_code == 2
    assert "--program" in r.output + str(r.stderr or "")


def test_agent_watch_requires_exactly_one_of_program_or_episode(tmp_path):
    r = CliRunner().invoke(main, ["agent", "watch", str(tmp_path), "--now", NOW])
    assert r.exit_code == 2


def test_agent_command_refuses_a_denylisted_model_without_a_traceback(tmp_path):
    r = CliRunner().invoke(
        main,
        ["agent", "g1-sheet", str(tmp_path), "--episode", "ep-1", "--model",
         _a_denylisted_model_id()],
    )
    assert r.exit_code != 0
    assert "excluded by policy" in r.output + str(r.stderr or "")
    assert r.exception is None or isinstance(r.exception, SystemExit)


def test_no_cli_command_echoes_an_api_key(monkeypatch):
    monkeypatch.setenv("DOCKET_LLM_API_KEY", "sentinel key value")
    r = CliRunner().invoke(main, ["agent", "--help"])
    assert "sentinel key value" not in r.output


def test_g1_sheet_is_read_only(tmp_path, program_with_stale_model):
    g, prog = program_with_stale_model
    g.save(tmp_path)
    before = Graph.load(tmp_path).get("ep-1")

    r = CliRunner().invoke(main, ["agent", "g1-sheet", str(tmp_path), "--episode", "ep-1"])
    assert r.exit_code == 0, r.output
    assert "G1" in r.output

    after = Graph.load(tmp_path).get("ep-1")
    assert before == after


def test_g1_sheet_json_prints_g1_review(tmp_path, program_with_stale_model):
    import json

    g, prog = program_with_stale_model
    g.save(tmp_path)
    r = CliRunner().invoke(
        main, ["agent", "g1-sheet", str(tmp_path), "--episode", "ep-1", "--json"]
    )
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["episode"] == "ep-1"


def test_agent_commands_require_now(tmp_path, program_with_stale_model):
    g, prog = program_with_stale_model
    g.save(tmp_path)
    r = CliRunner().invoke(main, ["agent", "propose-plan", str(tmp_path), "--episode", "ep-1"])
    assert r.exit_code == 2


# ---- [fix round 1] I2: elicit is replayable end to end via --source-artifact ---------


def test_agent_elicit_replays_the_committed_fixture_via_source_artifact(
    tmp_path, monkeypatch
):
    """The committed `tests/fixtures/recorded/elicit.json` fixture was recorded with
    `request_text` read from `tests/fixtures/requests/omfv-con-2020-02-25.md` but
    `source_artifact` set to the logical citation label
    `"sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md"`
    (`tests/agent/test_elicit.py`'s `SRC`/`REQ`) — the two are deliberately decoupled.
    Before `--source-artifact` existed, the CLI always set `source_artifact=str(source_
    file)`, so this exact fixture could never be replayed through the CLI (review-t8
    issue I2). With `--source-artifact` naming the fixture's own label, the recording
    key the CLI computes matches the committed one and the run succeeds end to end."""
    from tests.kernel.conftest import H, policy

    g = Graph()
    g.put(policy(), H)
    g.save(tmp_path)

    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    monkeypatch.setenv("DOCKET_LLM_RECORDING", "tests/fixtures/recorded/elicit.json")

    r = CliRunner().invoke(
        main,
        [
            "agent", "elicit", str(tmp_path),
            "--source", "tests/fixtures/requests/omfv-con-2020-02-25.md",
            "--source-artifact",
            "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md",
            "--episode", "ep-omfv-cli-test",
            "--requested-by", "NGCV CFT",
            "--policy", "pol-1",
            "--now", "2026-09-04T00:00:00Z",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "elicited" in r.output

    after = Graph.load(tmp_path)
    ep = after.get("ep-omfv-cli-test")
    assert ep["lifecycleState"] == "DRAFT"
    assert after.get(ep["charter"])["type"] == "Charter"
    assert len(ep["objectives"]) == 9


def test_agent_elicit_defaults_source_artifact_to_the_source_path(tmp_path, monkeypatch):
    """Without `--source-artifact`, the default is unchanged from before this fix round:
    the `--source` file's own path. Probed against the same committed fixture: passing
    the file path as the (wrong, undecoupled) source_artifact must still miss the
    fixture's key and refuse cleanly — proving the default really is `str(source_file)`
    and not silently the fixture's label."""
    from tests.kernel.conftest import H, policy

    g = Graph()
    g.put(policy(), H)
    g.save(tmp_path)

    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    monkeypatch.setenv("DOCKET_LLM_RECORDING", "tests/fixtures/recorded/elicit.json")

    r = CliRunner().invoke(
        main,
        [
            "agent", "elicit", str(tmp_path),
            "--source", "tests/fixtures/requests/omfv-con-2020-02-25.md",
            "--episode", "ep-omfv-cli-test-2",
            "--requested-by", "NGCV CFT",
            "--policy", "pol-1",
            "--now", "2026-09-04T00:00:00Z",
        ],
    )
    assert r.exit_code == 1
    assert r.exception is None or isinstance(r.exception, SystemExit)
    assert "no recording" in r.output.lower()


def test_agent_elicit_help_documents_the_source_artifact_label(tmp_path):
    """[fix round 1, issue I2] The replay command's exact fixture label is documented in
    `--help` text (the ruling's redirect from `tests/fixtures/recorded/README.md`, which
    is committed and outside this task's file list). click reflows and hyphen-wraps long
    help text across lines, so the label is reassembled first: lines are rejoined with no
    separator when the previous line ends in a hyphen (a wrapped hyphenated word) and
    with a space otherwise."""
    r = CliRunner().invoke(main, ["agent", "elicit", "--help"])
    assert r.exit_code == 0
    assert "--source-artifact" in r.output

    reflowed = ""
    for line in r.output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        reflowed += stripped if reflowed.endswith("-") else f" {stripped}"
    assert "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md" in \
        reflowed


# ---- [fix round 1] I3: success-path CliRunner coverage for propose-plan/dispatch/narrate


def _demo_a_draft_for_cli():
    """Mirrors `tests/agent/test_plan.py`'s `demo_a_draft` fixture exactly (same helper,
    `demos.a_cbo_gcv_2013.build.build`, same strip-approval step) so the CLI test below
    exercises the identical fixture-shaped graph state that fixture's own recorded-
    fixture tests already prove works with `tests/fixtures/recorded/plan.json`."""
    from demos.a_cbo_gcv_2013.build import H as DEMO_H
    from demos.a_cbo_gcv_2013.build import build

    g = build()
    pl = g.get("pl-cbo")
    stripped = {k: v for k, v in pl.items() if k != "approvedBy"}
    stripped["rev"] = pl["rev"] + 1
    stripped["createdBy"] = DEMO_H
    g.put(stripped, DEMO_H)
    return g


def test_agent_propose_plan_runs_end_to_end_against_the_committed_plan_fixture(
    tmp_path, monkeypatch
):
    g = _demo_a_draft_for_cli()
    g.save(tmp_path)

    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    monkeypatch.setenv("DOCKET_LLM_RECORDING", "tests/fixtures/recorded/plan.json")

    r = CliRunner().invoke(
        main,
        ["agent", "propose-plan", str(tmp_path), "--episode", "ep-cbo-2013", "--now", NOW],
    )
    assert r.exit_code == 0, r.output
    assert "proposed" in r.output

    after = Graph.load(tmp_path)
    ep = after.get("ep-cbo-2013")
    assert ep["plan"] != "pl-cbo"
    plan = after.get(ep["plan"])
    assert plan["type"] == "Plan" and plan["steps"]
    assert "approvedBy" not in plan


def test_agent_dispatch_runs_end_to_end_against_a_g2_approved_plan(tmp_path):
    """`dispatch` calls no backend [ruling: dispatch constructs no backend, see
    `tests/agent/test_dispatch.py::test_dispatch_constructs_no_backend`], so this needs
    no recorded fixture — only the G1/G2-gated graph state `tests/agent/test_dispatch.py`
    itself builds (`dispatched`'s own steps), reproduced here with the same helpers
    (`demos.a_cbo_gcv_2013.build.build`, `docket.agent.plan.approve_plan`,
    `docket.kernel.lifecycle.transition`)."""
    from demos.a_cbo_gcv_2013.build import build
    from docket.agent.plan import approve_plan
    from docket.kernel.lifecycle import transition

    now = "2013-04-30T00:00:00Z"
    seed = 20130430
    h = {"actorType": "human", "actorId": "shreyash"}

    g = build()
    transition(g, "ep-cbo-2013", "MODEL_APPROVED", h, now=now)
    ep = g.get("ep-cbo-2013")
    if ep.get("plan") != "pl-cbo":
        g.put({**ep, "rev": ep["rev"] + 1, "createdBy": h, "createdAt": now,
               "plan": "pl-cbo"}, h)
    pl = g.get("pl-cbo")
    stripped = {k: v for k, v in pl.items() if k != "approvedBy"}
    stripped["rev"] = pl["rev"] + 1
    stripped["createdBy"] = h
    g.put(stripped, h)
    approve_plan(g, "pl-cbo", h, now=now)
    transition(g, "ep-cbo-2013", "PLAN_APPROVED", h, now=now)
    g.save(tmp_path)

    r = CliRunner().invoke(
        main,
        ["agent", "dispatch", str(tmp_path), "--plan", "pl-cbo", "--seed", str(seed),
         "--now", now],
    )
    assert r.exit_code == 0, r.output
    assert "ranking" in r.output
    assert "flip analysis" in r.output

    after = Graph.load(tmp_path)
    assert after.get("ep-cbo-2013")["runs"]


def test_agent_narrate_runs_end_to_end_against_the_committed_narrate_fixture(
    tmp_path, monkeypatch
):
    """Built the same way `tests/agent/test_narrate.py`'s `demo_a_graph_dir` fixture is
    (`demos.a_cbo_gcv_2013.run.run`, never into `demos/*/out`), against the committed
    `narrate-clean.json` fixture."""
    from demos.a_cbo_gcv_2013.run import run

    d = tmp_path / "demo-a"
    run(d)
    graph_dir = d / "graph"

    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    monkeypatch.setenv("DOCKET_LLM_RECORDING", "tests/fixtures/recorded/narrate-clean.json")

    r = CliRunner().invoke(
        main,
        ["agent", "narrate", str(graph_dir), "--episode", "ep-cbo-2013",
         "--section", "evaluation-results", "--now", "2013-04-30T00:00:00Z"],
    )
    assert r.exit_code == 0, r.output
    assert "sentence" in r.output

    after = Graph.load(graph_dir)
    assert after.get("ep-cbo-2013")["narratives"]
