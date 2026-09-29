import json
from contextlib import contextmanager
from pathlib import Path

import click

from docket import KERNEL_VERSION
from docket.agent.cli import agent as _agent_group


@click.group()
@click.version_option(KERNEL_VERSION, prog_name="docket")
def main() -> None:
    """docket — auditable decision records with a deterministic kernel."""


main.add_command(_agent_group)


def _load_graph(graph_dir: Path):
    """Load a saved graph, turning a corrupt or missing store into a clean CLI
    failure instead of a traceback.

    Every command that reads a store goes through here: a hand-edited or
    partially-written store (or a directory that was never `Graph.save`d at all)
    raises `ValidationError`, and a raw traceback for that is not an acceptable
    failure mode for a CLI a reviewer runs directly against evidence.
    """
    from docket.errors import ValidationError
    from docket.store import Graph

    try:
        return Graph.load(graph_dir)
    except ValidationError as e:
        raise click.ClickException(str(e)) from e


def _human(actor_id: str) -> dict:
    return {"actorType": "human", "actorId": actor_id}


@contextmanager
def _kernel_errors():
    """Turn the kernel's own refusals into a clean CLI failure (exit 1) rather than
    a traceback: an unresolvable plan/episode id, a G2 refusal, an authority-boundary
    violation, or an uncited narrative sentence are all facts about the record, not
    bugs in this command.

    `TransitionRefused` is deliberately not caught here — `transition` handles it
    itself, because a refusal there is a recorded write (the attempt is appended to
    the episode's history either way) that must still be saved, not discarded.
    """
    from docket.errors import AuthorityViolation, UncitedSentenceError, ValidationError

    try:
        yield
    except (ValidationError, AuthorityViolation, UncitedSentenceError) as e:
        raise click.ClickException(str(e)) from e
    except KeyError as e:
        raise click.ClickException(f"{e.args[0]!r} not found in the graph") from e


@main.command()
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option(
    "--policy", "policy_id", default=None,
    help="Policy object id to apply policy rules",
)
@click.option("--json", "as_json", is_flag=True)
def validate(graph_dir: Path, policy_id: str | None, as_json: bool) -> None:
    """Run the validator over a saved graph, findings grouped by severity. Exit 1
    if any blocking finding, 0 otherwise."""
    from docket.kernel.validate import validate as _validate

    g = _load_graph(graph_dir)
    if policy_id and not g.has(policy_id):
        raise click.ClickException(f"policy {policy_id!r} not found")
    policy = g.get(policy_id) if policy_id else None
    findings = _validate(g, policy)
    if as_json:
        click.echo(json.dumps([f.to_dict() for f in findings], indent=2, sort_keys=True))
    else:
        # blocking, warning, info — in that order, so the finding a reader most
        # needs to act on is always the first thing printed, regardless of the
        # order `validate()` happened to return them in.
        for sev in ("blocking", "warning", "info"):
            group = [f for f in findings if f.severity == sev]
            if not group:
                continue
            click.echo(f"{sev} ({len(group)}):")
            for f in group:
                click.echo(f"  {f.rule} {','.join(f.objects)}: {f.message}")
        click.echo(f"{len(findings)} finding(s)")
    if any(f.severity == "blocking" for f in findings):
        raise SystemExit(1)


@main.group()
def schema() -> None:
    """Object schema commands."""


@schema.command("list")
def schema_list() -> None:
    from docket.objects import TYPES

    for t in sorted(TYPES):
        click.echo(t)


@schema.command("regenerate")
def schema_regenerate() -> None:
    from docket.schema.generate import generate

    for p in generate():
        click.echo(p)


@main.command()
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--plan", "plan_id", required=True, help="Plan object id to run")
@click.option("--seed", type=int, default=0, help="Seed recorded on every sealed run")
@click.option(
    "--now", required=True, help="ISO-8601 timestamp recorded on kernel objects"
)
def evaluate(graph_dir: Path, plan_id: str, seed: int, now: str) -> None:
    """Run an approved Plan's steps, seal the runs, and flip-analyse each one
    (design §7.2-7.3). Saves the graph in place.

    Refuses under G2 if the plan has not been approved by a human, or the episode
    has not reached a post-approval lifecycleState — the kernel enforces this
    itself (`docket.kernel.evaluate._require_plan_approval`), so this command
    cannot be a way around the gate.
    """
    from docket.kernel.evaluate import evaluate as _evaluate
    from docket.kernel.flip import flip_analysis

    g = _load_graph(graph_dir)
    lines: list[str] = []
    with _kernel_errors():
        for run in _evaluate(g, plan_id, seed=seed, now=now):
            n = len(flip_analysis(g, run["id"], seed=seed, now=now))
            lines.append(
                f"{run['id']}: ranking {' > '.join(run['ranking'])}; {n} flip analyses"
            )
    g.save(graph_dir)
    for line in lines:
        click.echo(line)


@main.command()
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--episode", "episode_id", required=True)
@click.option(
    "--tailoring", default=None,
    help="Standard tailoring name; defaults to the episode's Policy",
)
@click.option(
    "--k", type=int, default=None, help="Aggregation k; defaults to the Policy's"
)
@click.option("--seed", type=int, default=0, help="Seed recorded on every sealed run")
@click.option(
    "--now", required=True, help="ISO-8601 timestamp recorded on kernel objects"
)
@click.option(
    "--json", "as_json", is_flag=True,
    help="Print the ReadinessReport as canonical JSON",
)
def readiness(
    graph_dir: Path, episode_id: str, tailoring: str | None, k: int | None,
    seed: int, now: str, as_json: bool,
) -> None:
    """Compute and record the episode's ReadinessReport (design §6.1, §7.1).

    Prints `ready` and every blocker by rule and object id. Exits 1 when the
    record is not ready, in addition to any usage failure — the same convention
    `docket validate` uses for a blocking finding.
    """
    from docket.kernel.readiness import readiness_report

    g = _load_graph(graph_dir)
    with _kernel_errors():
        rr = readiness_report(
            g, episode_id, tailoring=tailoring, k=k, seed=seed, now=now
        )
    g.save(graph_dir)
    if as_json:
        click.echo(json.dumps(rr, indent=2, sort_keys=True))
    else:
        sa = g.get(rr["standardsAssessment"])
        verdicts = " ".join(
            f"{d}={v['verdict']}" for d, v in sorted(sa["dimensionVerdicts"].items())
        )
        click.echo(
            f"{rr['id']}: ready={rr['ready']} blockers={len(rr['blockers'])} {verdicts}"
        )
        for b in rr["blockers"]:
            click.echo(
                f"  blocker [{b['rule']}] {','.join(b['objects'])}: {b['message']}"
            )
    if not rr["ready"]:
        raise SystemExit(1)


@main.command()
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--episode", "episode_id", required=True)
@click.option(
    "--rendering", type=click.Choice(["unclassified", "full"]), default="full"
)
@click.option(
    "--now", required=True, help="ISO-8601 timestamp recorded on kernel objects"
)
@click.option(
    "--out", "out_dir", type=click.Path(path_type=Path), default=None,
    help="Directory to write package-<rendering>.md into; prints the text to "
         "stdout if omitted. Must not be graph_dir or a subdirectory of it — "
         "this command saves graph_dir afterwards, and Graph.save atomically "
         "replaces the whole directory, taking anything else written under it "
         "with it.",
)
@click.option(
    "--json", "as_json", is_flag=True,
    help="Print the sealed DecisionPackage object as canonical JSON instead of "
         "the rendered text",
)
def render(
    graph_dir: Path, episode_id: str, rendering: str, now: str,
    out_dir: Path | None, as_json: bool,
) -> None:
    """Render the Decision Package (design §7.8, §10) and seal it as a
    DecisionPackage. Saves the graph in place."""
    from docket.kernel.render import build_package

    if out_dir is not None:
        resolved_out = Path(out_dir).resolve()
        resolved_graph = Path(graph_dir).resolve()
        if resolved_out == resolved_graph or resolved_graph in resolved_out.parents:
            raise click.UsageError(
                f"--out {out_dir} must not be graph_dir or a subdirectory of it "
                f"({graph_dir}) — this command saves graph_dir afterwards, and "
                "Graph.save atomically replaces the whole directory"
            )
    g = _load_graph(graph_dir)
    with _kernel_errors():
        pkg, text = build_package(
            g, episode_id, rendering=rendering, now=now, out_dir=out_dir
        )
    g.save(graph_dir)
    if as_json:
        click.echo(json.dumps(pkg, indent=2, sort_keys=True))
    elif out_dir is not None:
        click.echo(f"{pkg['id']} → {pkg['path']} (hash {pkg['hash'][:12]})")
    else:
        click.echo(text)


@main.command()
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--episode", "episode_id", required=True)
@click.option("--seed", type=int, default=0, help="Seed recorded on every sealed run")
@click.option(
    "--now", required=True, help="ISO-8601 timestamp recorded on kernel objects"
)
@click.option(
    "--rendering", type=click.Choice(["unclassified", "full"]), default="unclassified"
)
@click.option(
    "--json", "as_json", is_flag=True,
    help="Print the identical/hashes/second/differing payload as canonical JSON",
)
def verify(
    graph_dir: Path, episode_id: str, seed: int, now: str, rendering: str, as_json: bool,
) -> None:
    """Re-render the package and every export twice from a saved graph and report
    whether the two renders are byte-identical (design §9.6; §11 M2 row —
    "determinism tests in CI").

    Read-only — never saves `graph_dir`. Calls the same
    `docket.kernel.verify.verify_determinism` that `scripts/determinism-check.sh` and
    `tests/test_determinism_gate.py` call (ruling R4: one determinism function), so this
    command and the CI gate can never disagree about what "identical" means. `--seed` is
    accepted for symmetry with `docket evaluate`/`readiness`/`flip` (design §7.5) but is
    not consumed — a re-render draws nothing. Exits 1 when the two renders differ, in
    addition to any usage failure.
    """
    from docket.kernel.verify import verify_determinism

    with _kernel_errors():
        result = verify_determinism(
            graph_dir, episode_id, seed=seed, now=now, rendering=rendering
        )
    if as_json:
        click.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        click.echo(f"identical={result['identical']} rendering={rendering}")
        for name in result["differing"]:
            click.echo(f"  differs: {name}")
    if not result["identical"]:
        raise SystemExit(1)


@main.command()
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--episode", "episode_id", required=True)
@click.option(
    "--to", "to_state", required=True, help="Target lifecycleState (design §5.2)"
)
@click.option(
    "--actor", required=True,
    help="Human actor id — required; the CLI never assumes a default human identity",
)
@click.option(
    "--now", required=True, help="ISO-8601 timestamp recorded on kernel objects"
)
def transition(
    graph_dir: Path, episode_id: str, to_state: str, actor: str, now: str
) -> None:
    """Attempt one lifecycle transition as a human actor (design §5.2 gates).

    A refusal is recorded and saved exactly like a success — nothing about a
    gate is silent — so the graph is written either way and only the exit code
    and printed message tell you which happened.
    """
    from docket.errors import AuthorityViolation, TransitionRefused, ValidationError
    from docket.kernel.lifecycle import transition as _transition

    g = _load_graph(graph_dir)
    try:
        ep = _transition(g, episode_id, to_state, _human(actor), now=now)
    except TransitionRefused as e:
        g.save(graph_dir)
        click.echo(
            f"{episode_id}: {actor} → {to_state} refused: {', '.join(e.unsatisfied)}"
        )
        raise SystemExit(1) from e
    except (ValidationError, AuthorityViolation) as e:
        raise click.ClickException(str(e)) from e
    except KeyError as e:
        raise click.ClickException(f"{e.args[0]!r} not found in the graph") from e
    g.save(graph_dir)
    click.echo(f"{episode_id}: {actor} → {ep['lifecycleState']}")


@main.command()
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--run", "run_id", required=True, help="Sealed EvaluationRun id")
@click.option("--seed", type=int, default=0, help="Seed recorded on every sealed run")
@click.option(
    "--now", required=True, help="ISO-8601 timestamp recorded on kernel objects"
)
@click.option(
    "--n-simplex", "n_simplex", type=int, default=None,
    help="Weight-simplex draws; defaults to the episode's Policy (design §7.5)",
)
@click.option(
    "--json", "as_json", is_flag=True,
    help="Print the flip analyses and the simplex summary as canonical JSON",
)
def flip(
    graph_dir: Path, run_id: str, seed: int, now: str, n_simplex: int | None,
    as_json: bool,
) -> None:
    """Flip-analyse a sealed run and print the weight-simplex robustness summary
    (design §7.3). Saves the graph in place.

    Writes new `FlipAnalysis` objects for `run_id`, so this refuses (append-only)
    if the run already has them — `docket evaluate` already runs this step for
    every run it seals; use this for a run that was sealed without it.
    """
    from docket.kernel.flip import flip_analysis, flip_summary

    g = _load_graph(graph_dir)
    with _kernel_errors():
        flips = flip_analysis(g, run_id, seed=seed, now=now)
        summary = flip_summary(g, run_id, seed=seed, now=now, n_simplex=n_simplex)
    g.save(graph_dir)
    ranked = sorted(
        flips,
        key=lambda f: (f["flipDistance"] is None, f["flipDistance"] or 0, f["id"]),
    )
    if as_json:
        click.echo(
            json.dumps({"flips": ranked, "summary": summary}, indent=2, sort_keys=True)
        )
        return
    for f in ranked:
        click.echo(
            f"{f['id']}: {f['parameter']['label']} threshold={f['flipThreshold']} "
            f"distance={f['flipDistance']}"
        )
    robustness = " ".join(
        f"{a}={v}" for a, v in sorted(summary["simplexRobustness"].items())
    )
    click.echo(
        f"robustness (n={summary['nSimplex']}, seed={summary['seed']}): {robustness}"
    )


@main.command()
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--program", "program_id", required=True)
@click.option("--trigger", "trigger_id", required=True)
@click.option(
    "--actor", required=True,
    help="Human actor id — required; a refresh reopens the model for G1 to "
         "approve again",
)
@click.option(
    "--now", required=True, help="ISO-8601 timestamp recorded on kernel objects"
)
@click.option(
    "--replacements", multiple=True,
    help="old=new object id pair; repeatable for more than one replacement",
)
def refresh(
    graph_dir: Path, program_id: str, trigger_id: str, actor: str, now: str,
    replacements: tuple[str, ...],
) -> None:
    """Open a refresh episode for a program in response to a trigger (design §7.7):
    marks the prior episode SUSPECT and opens a new DRAFT successor. Saves the
    graph in place. A refusal prints its message and exits 1 without saving —
    nothing legitimate was produced, so there is nothing to persist."""
    from docket.errors import AuthorityViolation, TransitionRefused, ValidationError
    from docket.kernel.refresh import open_refresh

    repl: dict[str, str] = {}
    for pair in replacements:
        if "=" not in pair:
            raise click.BadParameter(
                f"--replacements must be old=new, got {pair!r}", param_hint="--replacements"
            )
        old, new = pair.split("=", 1)
        if old in repl:
            raise click.BadParameter(
                f"--replacements names {old!r} twice", param_hint="--replacements"
            )
        repl[old] = new

    g = _load_graph(graph_dir)
    try:
        new_ep = open_refresh(
            g, program_id, trigger_id, actor=_human(actor), now=now,
            replacements=repl or None,
        )
    except TransitionRefused as e:
        click.echo(f"refused: {', '.join(e.unsatisfied)}")
        raise SystemExit(1) from e
    except (ValidationError, AuthorityViolation) as e:
        raise click.ClickException(str(e)) from e
    except KeyError as e:
        raise click.ClickException(f"{e.args[0]!r} not found in the graph") from e
    g.save(graph_dir)
    prior = g.get(new_ep["supersedes"])
    click.echo(
        f"{new_ep['id']} opened by {actor} (supersedes {new_ep['supersedes']}, "
        f"prior now {prior['lifecycleState']})"
    )


@main.command("diff")
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--prior", "from_id", required=True, help="Episode id before the refresh")
@click.option("--new", "to_id", required=True, help="Episode id after the refresh")
@click.option(
    "--now", required=True, help="ISO-8601 timestamp recorded on kernel objects"
)
@click.option(
    "--json", "as_json", is_flag=True, help="Print the EpisodeDiff as canonical JSON"
)
def diff_cmd(
    graph_dir: Path, from_id: str, to_id: str, now: str, as_json: bool
) -> None:
    """Diff two episode revisions across a refresh (design §7.7; ICD 203
    §D.6.e(7)). Saves the graph in place."""
    from docket.kernel.refresh import diff_episodes

    g = _load_graph(graph_dir)
    with _kernel_errors():
        d = diff_episodes(g, from_id, to_id, now=now)
    g.save(graph_dir)
    if as_json:
        click.echo(json.dumps(d, indent=2, sort_keys=True))
        return
    click.echo(
        f"{d['id']}: pairing={d['pairing']} added={len(d['added'])} "
        f"removed={len(d['removed'])} changed={len(d['changed'])}"
    )
    for c in d["changed"]:
        click.echo(f"  changed {c['object']}.{c['field']}: {c['before']} → {c['after']}")
    for a in d["added"]:
        click.echo(f"  added {a}")
    for rmv in d["removed"]:
        click.echo(f"  removed {rmv}")


@main.command()
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--episode", "episode_id", required=True)
@click.option(
    "--json", "as_json", is_flag=True,
    help="Print the state, history and next-target checks as canonical JSON",
)
def gates(graph_dir: Path, episode_id: str, as_json: bool) -> None:
    """Print an episode's lifecycle state, its recorded transition history, and
    the named checks for every next allowed target (design §5.2). Read-only — no
    transition is attempted and the graph is not saved."""
    from docket.kernel.lifecycle import CHECKS, EDGES, HUMAN_ONLY, KERNEL_ONLY

    g = _load_graph(graph_dir)
    if not g.has(episode_id):
        raise click.ClickException(f"{episode_id!r} not found in the graph")
    ep = g.get(episode_id)
    state = ep.get("lifecycleState")
    history = ep.get("transitions") or []
    targets = []
    for to_state in sorted(EDGES.get(state, set())):
        actor = "human" if to_state in HUMAN_ONLY else (
            "kernel" if to_state in KERNEL_ONLY else "any"
        )
        checks = [
            {"name": name, "satisfied": bool(check(g, ep))}
            for name, check in CHECKS.get(to_state, [])
        ]
        targets.append({"to": to_state, "actor": actor, "checks": checks})
    if as_json:
        click.echo(json.dumps(
            {"episode": episode_id, "lifecycleState": state, "history": history,
             "nextTargets": targets},
            indent=2, sort_keys=True,
        ))
        return
    click.echo(f"{episode_id}: {state}")
    for record in history:
        actor = record.get("actor") or {}
        status = "refused" if record.get("refused") else "ok"
        click.echo(
            f"  {record.get('at')} {actor.get('actorId')} {record.get('from')} → "
            f"{record.get('to')} [{status}]"
        )
    for target in targets:
        rendered = " ".join(
            f"{c['name']}={'satisfied' if c['satisfied'] else 'unsatisfied'}"
            for c in target["checks"]
        ) or "(no checks)"
        click.echo(f"  → {target['to']} ({target['actor']}-only): {rendered}")


@main.command("export")
@click.argument(
    "graph_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--episode", "episode_id", required=True)
@click.option(
    # Kept as a literal list, not `sorted(docket.exports.EXPORTS)`, so importing
    # docket.exports (and everything it pulls in from docket.kernel.render) is not
    # paid at `docket --help` time — every other command in this file follows the
    # same "import inside the function" convention.
    "--format", "fmt",
    type=click.Choice(["all", "dmn", "gsn", "madr", "milstd3022", "prov", "rtvm"]),
    required=True,
)
@click.option(
    "--rendering", type=click.Choice(["unclassified", "full"]), default="unclassified"
)
@click.option(
    "--plan", "plan_id", default=None,
    help="Plan object id for --format dmn; overrides the episode's own plan reference",
)
@click.option(
    "--vva", "vva_id", default=None,
    help="VVARecord object id for --format milstd3022; overrides the "
         "reachable-from-episode auto-resolution",
)
@click.option(
    "--out", "out_dir", type=click.Path(path_type=Path), default=None,
    help="Directory to write the export(s) into; required for --format all. "
         "Without it, a single format prints to stdout.",
)
def export_cmd(
    graph_dir: Path, episode_id: str, fmt: str, rendering: str,
    plan_id: str | None, vva_id: str | None, out_dir: Path | None,
) -> None:
    """Export PROV, GSN, DMN, MIL-STD-3022, MADR or RTVM from a saved graph (design
    §6.3, §10 item 16). Read-only — never saves `graph_dir`.

    `--format all` writes every export into `--out` (required) and prints one
    `filename  sha256` line per file — the same computation `docket render`'s
    Machine annex lists, so this can be used to fetch the files that annex names.

    A single named format resolves `--plan`/`--vva` **strictly**: if it is not given
    and the episode has no approved plan (`dmn`) or reaches zero or more than one
    `VVARecord` (`milstd3022`), this refuses rather than guessing — `--format all` and
    `docket render`'s own export step degrade to an explanatory placeholder instead,
    because a package build must never fail just because one demonstration episode has
    no VV&A record yet.
    """
    from docket.exports import (
        export_filename,
        export_text,
        resolve_plan_id,
        resolve_vva_id,
        write_exports,
    )

    if out_dir is not None:
        # M3: a nested --out pollutes a store Task 2's `diff -r` determinism gate
        # walks — `Graph.load` still succeeds afterwards (verified), but the six
        # exports would sit inside `graph_dir` (or worse, `graph/objects/`) where
        # nothing expects them. Same check `render`'s `--out` uses.
        resolved_out = Path(out_dir).resolve()
        resolved_graph = Path(graph_dir).resolve()
        if resolved_out == resolved_graph or resolved_graph in resolved_out.parents:
            raise click.UsageError(
                f"--out {out_dir} must not be graph_dir or a subdirectory of it "
                f"({graph_dir})"
            )

    g = _load_graph(graph_dir)
    if not g.has(episode_id):
        raise click.ClickException(f"episode {episode_id!r} not found in the graph")

    if fmt == "all":
        if out_dir is None:
            raise click.UsageError("--format all requires --out")
        with _kernel_errors():
            pairs = write_exports(g, episode_id, rendering=rendering, out_dir=out_dir)
        for filename, digest in pairs:
            # M8: labelled exactly like the Machine annex's own lines, so the two are
            # greppable against each other.
            click.echo(f"{filename}  sha256:{digest}")
        return

    if fmt == "dmn" and plan_id is None:
        plan_id, err = resolve_plan_id(g, episode_id)
        if err:
            raise click.ClickException(err)
    elif fmt == "milstd3022" and vva_id is None:
        vva_id, err = resolve_vva_id(g, episode_id)
        if err:
            raise click.ClickException(err)
    if plan_id is not None and not g.has(plan_id):
        raise click.ClickException(f"plan {plan_id!r} not found in the graph")
    if vva_id is not None and not g.has(vva_id):
        raise click.ClickException(f"VVARecord {vva_id!r} not found in the graph")

    with _kernel_errors():
        text = export_text(
            g, name=fmt, episode_id=episode_id, rendering=rendering,
            plan_id=plan_id, vva_id=vva_id,
        )
    if out_dir is None:
        # I9: `nl=False` — every export already ends in its own "\n"; echo's default
        # would add a second byte, so stdout would not match the sha256 the Machine
        # annex pins for this same file.
        click.echo(text, nl=False)
        return
    from docket.canon import sha256_hex

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filename = export_filename(fmt, rendering)
    (out_path / filename).write_text(text, encoding="utf-8", newline="\n")
    click.echo(f"{filename}  sha256:{sha256_hex(text)}")


def _ensure_repo_on_path() -> None:
    """`demos/` and `eval/` are repository data, not package data (they sit beside
    `src/docket`, outside the wheel). The installed `docket` console script therefore
    cannot `import demos` unless the repository root is on `sys.path` — `uv run docket
    demo …` and `docket ui --seed-demos` failed with ModuleNotFoundError while the
    in-process test runner (rootdir on the path) passed. Put the root, found by the
    same walk-up `docket.api.config.repo_root` uses, at the front of the path once.
    """
    import sys

    from docket.api.config import repo_root

    root = str(repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)


@main.command("demo")
@click.argument("name")
@click.option(
    "--out", "out_root", type=click.Path(path_type=Path), default=None,
    help="Root to build into; each demo lands at <out>/demos/<name>/out, matching the "
         "layout scripts/determinism-check.sh diffs. Default: the repo root, i.e. the "
         "committed demos/*/out layout demos.run_all.run_all itself defaults to.",
)
def demo_cmd(name: str, out_root: Path | None) -> None:
    """Build one demo, or every demo (`docket demo all`), from public source into an
    `out/` directory (plan 05 Task 8). A thin wrapper: the demo-running logic lives in
    `demos/run_all.py` and each demo's own `run.py`, not here — this command exists so a
    reviewer without a Python REPL can reproduce a demo's output directly.

    Nothing here reads the network, a clock beyond the fixed timestamps each demo
    already bakes in, or an environment variable: two invocations with the same `--out`
    produce byte-identical files, the same guarantee `scripts/determinism-check.sh`
    checks across independent processes.
    """
    import importlib

    _ensure_repo_on_path()
    from demos.run_all import DEMOS, REPO_ROOT, run_all

    root = Path(out_root).resolve() if out_root is not None else REPO_ROOT

    if name == "all":
        for entry in run_all(root):
            if entry["present"]:
                click.echo(f"{entry['demo']}: ok — {entry['resultsFile']}")
            else:
                click.echo(f"{entry['demo']}: skipped — {entry['reason']}")
        return

    if name not in DEMOS:
        raise click.UsageError(
            f"unknown demo {name!r} — choose one of {', '.join(DEMOS)}, or 'all'"
        )
    out_dir = root / "demos" / name / "out"
    try:
        module = importlib.import_module(f"demos.{name}.run")
    except ModuleNotFoundError as e:
        raise click.ClickException(f"demos.{name}.run is absent ({e})") from e
    module.run(out_dir)
    click.echo(f"{name}: ok — {out_dir}")


def _seed_missing_demos(echo) -> None:
    """Build any demo store `GET /api/health`'s `demoStores` would report missing
    (plan 07 Task 9, Step 1), so whichever demo a visitor picks from the UI's
    SessionPicker is ready the first time they click it — not only the one named by
    `--demo`. Each `run()` is the same deterministic, offline build `demos/run_all.py`
    already documents: it reads no clock and no environment variable, so seeding here
    produces the identical store `demos/*/out/graph` would hold if it had been built by
    hand ahead of time.
    """
    _ensure_repo_on_path()
    import importlib

    from docket.api.config import DEMOS, demos_dir

    for key, module_name in DEMOS.items():
        out_dir = demos_dir() / module_name / "out"
        if (out_dir / "graph" / "log.jsonl").is_file():
            continue
        echo(f"Building the {key} demo store (first run only)…")
        run = importlib.import_module(f"demos.{module_name}.run").run
        run(out_dir)
        echo(f"  {key} ready at {out_dir}")


def _open_browser_when_healthy(host: str, port: int, demo: str) -> None:
    """Open the browser only once `GET /api/health` answers 200 — never before (plan 07
    Task 9, Step 1). A background daemon thread with a bounded deadline: if `uvicorn.run`
    below never actually brings the server up, this simply gives up rather than hanging
    the process open on a browser tab nobody will see.

    `--demo a`/`--demo b` additionally opens on that demo's session, by creating the
    session server-side (the same `POST /api/session` the SessionPicker button sends)
    and passing its id on the URL — there is no dedicated `/session/:id` route in the
    SPA's router yet (session ids live in `sessionStorage`, set by `ui/src/api/useSession.ts`;
    see that file's own header comment on why), so `?session=<id>` is the forward-compatible
    placeholder until Home (plan 07 Task 6) reads it on load. A session that fails to
    create (e.g. the store failed to seed) still opens the plain UI rather than nothing.
    """
    import threading

    def _wait_then_open() -> None:
        import time
        import webbrowser

        import httpx

        base = f"http://{host}:{port}"
        deadline = time.monotonic() + 30.0
        healthy = False
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{base}/api/health", timeout=1.0).status_code == 200:
                    healthy = True
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        if not healthy:
            return
        target = f"{base}/"
        if demo != "none":
            try:
                sid = httpx.post(
                    f"{base}/api/session", json={"source": f"demo-{demo}"}, timeout=10.0,
                ).json()["id"]
                target = f"{base}/?session={sid}"
            except Exception:
                pass
        webbrowser.open(target)

    threading.Thread(target=_wait_then_open, daemon=True).start()


@main.command()
@click.option("--port", default=8765, show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--open/--no-open", "open_browser", default=True)
@click.option("--demo", type=click.Choice(["a", "b", "none"]), default="none")
@click.option("--seed-demos/--no-seed-demos", default=True)
def ui(port: int, host: str, open_browser: bool, demo: str, seed_demos: bool) -> None:
    """Serve the demonstration UI and the API on 127.0.0.1.

    Localhost only, by default and by intent: this is a single-user demonstration with no
    authentication, and binding it to 0.0.0.0 would put an unauthenticated write API on a
    conference wifi. `--host` exists because a projector laptop is sometimes not the
    laptop, and the help text says what you are doing when you change it.
    """
    import uvicorn

    from docket.api.app import create_app
    from docket.api.config import UI_NOT_BUILT_MESSAGE, static_dir

    if seed_demos:
        _seed_missing_demos(click.echo)

    if not (static_dir() / "index.html").is_file():
        click.echo(UI_NOT_BUILT_MESSAGE)

    if open_browser:
        _open_browser_when_healthy(host, port, demo)

    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
