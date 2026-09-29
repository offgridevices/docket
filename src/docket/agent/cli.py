# src/docket/agent/cli.py
"""`docket agent ...` — thin CLI shells over the agent-assisted stages of a Department of
War decision record: elicitation, the G1 review sheet, plan proposal, dispatch, narration,
and the refresh watch.

Every command here is parse -> call -> print. None of them contain logic: the function each
one wraps is the same one plan 07's API calls directly (design §6, frontend spec §6), so the
two paths cannot drift. This module's own top-level imports stay light (`click` only) — every
heavier import (a backend, a graph, an agent-stage function) happens inside the command body
that needs it, the same convention `docket.cli` uses, so `docket --help` stays cheap.

Every command resolves its backend settings — and, with them, the denylist check on
`--model` [ruling R3] — before it does anything else, including before loading the graph:
a denylisted `--model` is refused the same way whether or not the command ever calls the
backend, and whether or not `GRAPH_DIR` even holds a valid store. No command ever prints a
`settings` value wholesale, and none prints an API key: the key never enters this module at
all, since `backend_from_settings` reads it from the environment on its own.

Nothing here names a provider, a model, or a hosting commitment: help text and defaults are
provider/model-agnostic, matching CLAUDE.md and design P8. The agent actor id defaults to
`agent:<model>`, never a bare `"agent"`, so `ingestionProvenance`/`createdBy` on anything
this CLI writes says which backend proposed it.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import click

__all__ = ["agent"]


@click.group("agent")
def agent() -> None:
    """Agent-assisted stages of a Department of War decision record: elicitation, the G1
    review sheet, plan proposal, dispatch, narration, and the refresh watch.

    The agent proposes; a human approves the model (G1) and the plan (G2) before any
    number is computed, and only a human opens a refresh. Every command below takes
    --provider/--model/--base-url and refuses a model excluded by policy (design P8).
    """


def backend_options(f):
    f = click.option(
        "--provider", default=None,
        help="LLM backend provider; defaults via DOCKET_LLM_PROVIDER or the config "
             "file, else \"recorded\"",
    )(f)
    f = click.option(
        "--model", default=None,
        help="Model id to resolve; refused by name if it matches the PRC-origin "
             "denylist (design P8)",
    )(f)
    f = click.option(
        "--base-url", "base_url", default=None,
        help="Base URL for an openai-compatible or anthropic backend",
    )(f)
    f = click.option(
        "--actor", "actor_id", default=None,
        help="agent actor id; defaults to agent:<model>",
    )(f)
    return f


def _resolve_backend(provider: str | None, model: str | None, base_url: str | None):
    """`resolve_settings` then `backend_from_settings` — the one place every command
    resolves its backend, so the denylist check on `--model` [ruling R3] and the
    CLI-flags-beat-env-beats-config precedence [ruling R6] apply identically everywhere.
    A `PolicyRefusal` (a denylisted model, or a provider that needs a base URL it wasn't
    given) becomes a one-line `click.ClickException`, never a traceback."""
    from docket.agent.backend import backend_from_settings, resolve_settings
    from docket.errors import PolicyRefusal

    try:
        settings = resolve_settings(provider=provider, model=model, base_url=base_url)
        return backend_from_settings(settings)
    except PolicyRefusal as e:
        raise click.ClickException(str(e)) from e


def _actor_for(backend, actor_id: str | None) -> dict:
    return {"actorType": "agent", "actorId": actor_id or f"agent:{backend.model_id}"}


def _load_graph(graph_dir: Path):
    """Mirrors `docket.cli._load_graph`: a corrupt or missing store becomes a clean CLI
    failure, never a traceback. Kept as this module's own copy rather than imported from
    `docket.cli`, the same tolerant-duplication convention `plan.py`/`narrate.py`/
    `review.py` each use for their own small `_obj` helper."""
    from docket.errors import ValidationError
    from docket.store import Graph

    try:
        return Graph.load(graph_dir)
    except ValidationError as e:
        raise click.ClickException(str(e)) from e


@contextmanager
def _agent_errors():
    """Turn every refusal an agent-stage function can raise into a clean CLI failure
    (exit 1) instead of a traceback: an unresolvable episode/plan/program id, an
    authority-boundary violation, an uncited narrative sentence, or a backend that never
    returned a valid response are all facts about this run, not bugs in this command."""
    from docket.errors import (
        AuthorityViolation,
        BackendError,
        PolicyRefusal,
        UncitedSentenceError,
        ValidationError,
    )

    try:
        yield
    except (ValidationError, AuthorityViolation, UncitedSentenceError, BackendError,
            PolicyRefusal) as e:
        raise click.ClickException(str(e)) from e
    except KeyError as e:
        raise click.ClickException(f"{e.args[0]!r} not found in the graph") from e


GRAPH_DIR_TYPE = click.Path(exists=True, file_okay=False, path_type=Path)


@agent.command("elicit")
@click.argument("graph_dir", type=GRAPH_DIR_TYPE)
@click.option(
    "--source", "source_file", required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Request text file to elicit from (Stage E)",
)
@click.option(
    "--source-artifact", "source_artifact", default=None,
    help="Citation label baked into the elicitation prompt and stored as "
         "ingestionProvenance.sourceArtifact on every DRAFT object this stage writes; "
         "defaults to --source's own path [fix round 1, issue I2]. Pass this when the "
         "file you elicit FROM is not the same string as the artifact you want cited — "
         "e.g. to replay the committed tests/fixtures/recorded/elicit.json fixture: "
         "docket agent elicit GRAPH_DIR --source "
         "tests/fixtures/requests/omfv-con-2020-02-25.md --source-artifact "
         "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md "
         "--episode ... --requested-by ... --policy pol-1 --now ... "
         "--provider recorded (with DOCKET_LLM_RECORDING pointed at that fixture).",
)
@click.option("--episode", "episode_id", required=True, help="Id for the new DRAFT episode")
@click.option("--requested-by", "requested_by", required=True,
             help="Charter.authority.signer — who asked for this decision")
@click.option("--policy", "policy_id", required=True,
             help="Policy object id; becomes Charter.decisionClassPolicy")
@click.option("--now", required=True, help="ISO-8601 timestamp recorded on new objects")
@click.option("--sequence", type=int, default=1, help="DecisionEpisode.sequence")
@click.option("--as-of", "as_of", default=None,
             help="DecisionEpisode.asOf for elapsed-time predicates; defaults to --now")
@backend_options
def elicit_cmd(graph_dir: Path, source_file: Path, source_artifact: str | None,
               episode_id: str, requested_by: str, policy_id: str, now: str,
               sequence: int, as_of: str | None, provider: str | None, model: str | None,
               base_url: str | None, actor_id: str | None) -> None:
    """Elicit a decision request (Stage E) into DRAFT graph objects and a DRAFT
    DecisionEpisode. Saves the graph in place."""
    backend = _resolve_backend(provider, model, base_url)
    actor = _actor_for(backend, actor_id)
    g = _load_graph(graph_dir)
    from docket.agent.elicit import elicit_into

    request_text = source_file.read_text(encoding="utf-8")
    with _agent_errors():
        ep = elicit_into(
            g, backend, request_text=request_text, policy_id=policy_id, actor=actor,
            now=now, source_artifact=source_artifact or str(source_file),
            requested_by=requested_by, episode_id=episode_id, sequence=sequence,
            as_of=as_of or now,
        )
    g.save(graph_dir)
    click.echo(f"{ep['id']}: elicited (charter={ep['charter']})")


@agent.command("g1-sheet")
@click.argument("graph_dir", type=GRAPH_DIR_TYPE)
@click.option("--episode", "episode_id", required=True)
@click.option(
    "--json", "as_json", is_flag=True,
    help="Print g1_review() as canonical JSON instead of the Markdown sheet",
)
@backend_options
def g1_sheet_cmd(graph_dir: Path, episode_id: str, as_json: bool, provider: str | None,
                 model: str | None, base_url: str | None, actor_id: str | None) -> None:
    """Print Gate G1's review sheet (design §5.2, §8.2): the model, before anything is
    computed. Read-only — never saves GRAPH_DIR, and calls no backend."""
    backend = _resolve_backend(provider, model, base_url)
    _actor_for(backend, actor_id)  # resolved for the same uniform precedence every
    # command applies [ruling R6]; g1-sheet is a pure read and never writes as this actor
    g = _load_graph(graph_dir)
    from docket.agent.review import g1_review, g1_sheet

    with _agent_errors():
        if as_json:
            import json

            click.echo(json.dumps(g1_review(g, episode_id), indent=2, sort_keys=True))
        else:
            click.echo(g1_sheet(g, episode_id))


@agent.command("propose-plan")
@click.argument("graph_dir", type=GRAPH_DIR_TYPE)
@click.option("--episode", "episode_id", required=True)
@click.option("--now", required=True, help="ISO-8601 timestamp recorded on the new Plan")
@backend_options
def propose_plan_cmd(graph_dir: Path, episode_id: str, now: str, provider: str | None,
                     model: str | None, base_url: str | None, actor_id: str | None) -> None:
    """Propose an evaluation Plan (Stage P) for an episode whose model has passed G1. No
    `approvedBy` is ever set here — a human approves it at G2. Saves the graph in place."""
    backend = _resolve_backend(provider, model, base_url)
    actor = _actor_for(backend, actor_id)
    g = _load_graph(graph_dir)
    from docket.agent.plan import propose_plan

    with _agent_errors():
        plan = propose_plan(backend, g, episode_id, actor=actor, now=now)
    g.save(graph_dir)
    click.echo(f"{plan['id']}: proposed ({len(plan['steps'])} step(s)); awaiting G2 approval")


@agent.command("dispatch")
@click.argument("graph_dir", type=GRAPH_DIR_TYPE)
@click.option("--plan", "plan_id", required=True, help="Plan object id; must be G2-approved")
@click.option("--seed", type=int, default=0, help="Seed recorded on every sealed run")
@click.option("--now", required=True, help="ISO-8601 timestamp recorded on kernel objects")
@backend_options
def dispatch_cmd(graph_dir: Path, plan_id: str, seed: int, now: str, provider: str | None,
                 model: str | None, base_url: str | None, actor_id: str | None) -> None:
    """Hand a G2-approved Plan to the kernel (Stage X) and print its sealed runs and flip
    analyses. No arithmetic happens in this module; the kernel computes. Saves the graph
    in place."""
    backend = _resolve_backend(provider, model, base_url)
    actor = _actor_for(backend, actor_id)
    g = _load_graph(graph_dir)
    from docket.agent.dispatch import dispatch

    with _agent_errors():
        result = dispatch(g, plan_id, actor=actor, seed=seed, now=now)
    g.save(graph_dir)
    for run in result["runs"]:
        click.echo(f"{run['id']}: ranking {' > '.join(run['ranking'])}")
    click.echo(f"{len(result['flips'])} flip analysis(es)")


@agent.command("narrate")
@click.argument("graph_dir", type=GRAPH_DIR_TYPE)
@click.option("--episode", "episode_id", required=True)
@click.option("--section", "section", required=True, help="Decision Package section name")
@click.option("--now", required=True, help="ISO-8601 timestamp recorded on the Narrative")
@backend_options
def narrate_cmd(graph_dir: Path, episode_id: str, section: str, now: str,
                provider: str | None, model: str | None, base_url: str | None,
                actor_id: str | None) -> None:
    """Draft, citation-check, and store one Decision Package section (Stage N). A draft
    that cites nothing it was shown is refused before anything is written. Saves the
    graph in place."""
    backend = _resolve_backend(provider, model, base_url)
    actor = _actor_for(backend, actor_id)
    g = _load_graph(graph_dir)
    from docket.agent.narrate import narrate

    with _agent_errors():
        n = narrate(g, episode_id, section=section, backend=backend, actor=actor, now=now)
    g.save(graph_dir)
    click.echo(f"{n['id']}: {len(n['sentences'])} sentence(s) for section {section!r}")


@agent.command("watch")
@click.argument("graph_dir", type=GRAPH_DIR_TYPE)
@click.option("--program", "program_id", default=None,
             help="DecisionProgram id to watch; required to use --file")
@click.option("--episode", "episode_id", default=None,
             help="Episode id, resolved to its program; narrows detection to it alone")
@click.option("--now", required=True,
             help="ISO-8601 timestamp recorded as detectedAt on any new proposal")
@click.option(
    "--file", "do_file", is_flag=True,
    help="File the printed proposals as RefreshTriggers under the agent actor "
         "(requires --program)",
)
@backend_options
def watch_cmd(graph_dir: Path, program_id: str | None, episode_id: str | None, now: str,
             do_file: bool, provider: str | None, model: str | None, base_url: str | None,
             actor_id: str | None) -> None:
    """Detect refresh-trigger proposals (Stage R, design §7.7): scope findings and
    assumption indicators that suggest the record may be stale. Prints every proposal; a
    human decides whether to open a refresh (`docket refresh`). Read-only unless --file
    is given, in which case the printed proposals are filed and the graph is saved.

    Exactly one of --program or --episode is required. --episode resolves to that
    episode's program and narrows detection to it alone; --file still requires an
    explicit --program, because a RefreshTrigger is filed on the program.
    """
    if (program_id is None) == (episode_id is None):
        raise click.UsageError("exactly one of --program or --episode is required")
    if do_file and program_id is None:
        raise click.UsageError("--file requires --program")

    backend = _resolve_backend(provider, model, base_url)
    actor = _actor_for(backend, actor_id)
    g = _load_graph(graph_dir)
    from docket.agent.refresh_watch import detect, file_all
    from docket.errors import ValidationError

    resolved_program = program_id
    with _agent_errors():
        if episode_id is not None:
            if not g.has(episode_id):
                raise ValidationError([f"episode {episode_id!r} is not in the graph"])
            prog_ref = g.get(episode_id).get("program")
            if not isinstance(prog_ref, str) or not g.has(prog_ref):
                raise ValidationError(
                    [f"episode {episode_id!r} has no resolvable program "
                     f"(DecisionEpisode.program)"]
                )
            resolved_program = prog_ref
        proposals = detect(g, resolved_program, now=now, episode_id=episode_id)

    if not proposals:
        click.echo("no refresh-trigger proposals")
    for p in proposals:
        click.echo(f"{p['kind']}: {p['source']} — {p['description']} "
                   f"(affected: {', '.join(p['affected'])})")

    if do_file:
        with _agent_errors():
            filed = file_all(g, resolved_program, proposals, actor=actor, now=now)
        g.save(graph_dir)
        for t in filed:
            click.echo(f"filed {t['id']}")
