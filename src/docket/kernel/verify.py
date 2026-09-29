"""The CI/local determinism gate (design §9.6; §11 M2 row — "determinism tests in
CI"): prove a saved graph renders the same bytes twice.

`scripts/determinism-check.sh` builds the whole demo tree twice, in two independent
`uv run` processes (so a fresh, potentially different, hash seed lands on each build),
diffs every byte on disk, then reuses one tree against committed `demos/*/out` (no third
rebuild). `verify_determinism` here is the cheap, in-process complement
`tests/test_determinism_gate.py` runs on every `pytest`, and the one function the CLI's
`docket verify` command and `docket.api.verify`'s `/verify` route (via the shared
`render_hashes` helper below) both build on — one implementation of "render and hash",
so the CI gate, the CLI and the on-stage "identical bytes ✓" affordance can never
disagree about what "identical" means (ruling R4).

It never re-runs `evaluate` and never touches a clock beyond the `now` it is given.
`render_package` and every export (`docket.exports`) are pure functions of the graph, so
calling them twice against the same loaded `Graph` and comparing hashes is a direct test
of that purity — not a rebuild. Contrast this with `kernel.render.build_package`, which
`put`s a new `DecisionPackage` into the graph on every call: calling it twice here would
mean the second render ran against a graph the first call had already changed, measuring
the wrong thing (see `build_package`'s own docstring). `render_hashes` calls
`render_package` directly instead, exactly as ruling R4 specifies.

`seed` is accepted, not consumed. Every other kernel CLI command that reads a saved graph
(`docket evaluate`, `docket readiness`, `docket flip`) takes `--seed` because it draws
something from it; this command only re-renders what those commands already sealed, so
there is nothing left to seed. It stays in the signature — ruling R4's own interface —
so the CLI, the tests and the API's verify affordance share one call shape, and so a
future check that *does* need to re-derive something (a full re-evaluation, not just a
re-render) has somewhere to put it without changing every caller.
"""
from __future__ import annotations

from pathlib import Path

from docket.canon import sha256_hex
from docket.kernel.render import render_package
from docket.store import Graph


def render_hashes(g: Graph, episode_id: str, *, rendering: str, now: str) -> dict[str, str]:
    """One render pass's hashes: `{"package": sha256, "export-<name>-<rendering>.<ext>":
    sha256, ...}` — one entry per `docket.exports.EXPORTS` name plus the package itself.

    Exports are computed exactly once and passed into `render_package` — the same order
    `kernel.render.build_package` uses (see its own docstring for why) — so the Machine
    annex's hash lines and the per-export hashes returned here always describe the same
    bytes. Lazy import: see `render.py`'s `_machine_annex_body` docstring for why a
    module-level import between `docket.kernel.render` and `docket.exports`, in either
    direction, would be circular.

    Validates `episode_id` itself, with the same message `render_package` raises for it,
    *before* touching `compute_all`: unlike `render_package`, the export mappers do not
    all guard a missing episode at their own top (`to_prov` walks straight into
    `check_scope` → `Graph.get`, which raises a bare `KeyError`), and computing exports
    runs first here, so without this check a bad `episode_id` would surface as a
    `KeyError` from deep inside `docket.exports` rather than the same clean
    `ValidationError` every other kernel entry point raises for it.
    """
    if not isinstance(episode_id, str) or not g.has(episode_id):
        from docket.errors import ValidationError

        raise ValidationError([f"episode {episode_id!r} is not in the graph"])

    from docket.exports import compute_all

    exports = compute_all(g, episode_id, rendering=rendering)
    package_text = render_package(g, episode_id, rendering=rendering, now=now, exports=exports)
    hashes = {"package": sha256_hex(package_text)}
    for filename, text in exports:
        hashes[filename] = sha256_hex(text)
    return hashes


def verify_determinism(
    graph_dir: Path,
    episode_id: str,
    *,
    seed: int,
    now: str,
    rendering: str = "unclassified",
) -> dict:
    """Load the saved graph at `graph_dir` and render the package and every export
    twice, comparing hashes.

    Returns `{"identical": bool, "hashes": {...}, "second": {...same keys...},
    "differing": [...]}` — `differing` is the sorted list of names whose two hashes
    disagree, empty when `identical` is true. `hashes`/`second` are two independent
    calls to `render_hashes` against the *same* loaded `Graph`: this proves the render is
    a pure function of that graph, not that two different processes (or two different
    `--out` roots) agree with each other — `scripts/determinism-check.sh` is the check
    for that, and it is the one that actually exercises a second process.
    """
    g = Graph.load(Path(graph_dir))
    first = render_hashes(g, episode_id, rendering=rendering, now=now)
    second = render_hashes(g, episode_id, rendering=rendering, now=now)
    differing = sorted(name for name in first if first[name] != second.get(name))
    return {
        "identical": not differing,
        "hashes": first,
        "second": second,
        "differing": differing,
    }


__all__ = ["render_hashes", "verify_determinism"]
