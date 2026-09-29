"""Deterministic exports over one graph (design §6.3, §10 item 16).

Six pure, format-specific mappers (`prov.py`, `gsn.py`, `dmn.py`, `milstd3022.py`,
`madr.py`, `rtvm.py`) plus the registry and dispatch this module provides:

- `EXPORTS` names every format, its file extension and how its subject object
  (episode / plan / VVARecord) is selected.
- `export_text` renders exactly one format to text.
- `export_filename` names the file `export_text` will be written to.
- `write_exports` computes every format and writes it to `out_dir`, returning
  `(filename, sha256)` pairs — the single computation `build_package`'s Machine annex
  and the files on disk both come from (ruling R3).

**Two resolution policies, deliberately different.** `write_exports` (and therefore
`build_package`, called on every render regardless of how complete the record is) never
refuses: an episode with no approved Plan still gets a DMN file explaining why it is
empty, and the MIL-STD-3022 file renders every `VVARecord` forward-reachable from the
episode as its own section (review round 2, I2) — one, several or none, each named in
words when there is nothing to show, never guessing among several or interpolating a
bare `None` when the count is not exactly one. A `docket export` request for exactly one
named format is a human asking for one addressable document, and silently guessing the
wrong Plan or VVARecord there is worse than a loud refusal — the CLI layer (`cli.py`)
uses `resolve_plan_id`/`resolve_vva_id`'s returned error message to refuse instead of
degrading, unless `--plan`/`--vva` was given explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docket.canon import sha256_hex
from docket.exports._util import obj
from docket.objects import is_content
from docket.store import Graph


@dataclass(frozen=True)
class ExportSpec:
    name: str
    extension: str
    selector: str  # "episode" | "plan" | "vva"


EXPORTS: dict[str, ExportSpec] = {
    "prov": ExportSpec("prov", "json", "episode"),
    "gsn": ExportSpec("gsn", "json", "episode"),
    "dmn": ExportSpec("dmn", "xml", "plan"),
    "milstd3022": ExportSpec("milstd3022", "md", "vva"),
    "madr": ExportSpec("madr", "md", "episode"),
    "rtvm": ExportSpec("rtvm", "csv", "episode"),
}


def export_filename(name: str, rendering: str) -> str:
    return f"export-{name}-{rendering}.{EXPORTS[name].extension}"


def resolve_plan_id(g: Graph, episode_id: str) -> tuple[str | None, str | None]:
    """`(plan_id, error)`. `error` is set, and `plan_id` is `None`, when the episode's
    `plan` field is absent, a P3 marker, or does not resolve in `g`."""
    ep = obj(g, episode_id)
    pid = ep.get("plan") if ep is not None else None
    if not is_content(pid):
        return None, f"episode {episode_id} has no approved plan on record"
    if not isinstance(pid, str) or not g.has(pid):
        return None, f"episode {episode_id} names plan {pid!r}, which is not in the graph"
    return pid, None


def resolve_vva_id(g: Graph, episode_id: str) -> tuple[str | None, str | None]:
    """`(vva_id, error)`. `error` is set, and `vva_id` is `None`, unless exactly one
    `VVARecord` is forward-reachable from the episode — the same "never pick silently"
    rule `evaluate._lookup_observations` applies to an ambiguous Observation."""
    if not g.has(episode_id):
        return None, f"episode {episode_id} is not in the graph"
    reach = {episode_id} | g.reachable_from(episode_id, reverse=False)
    candidates = sorted(
        oid for oid in reach if g.has(oid) and g.get(oid).get("type") == "VVARecord"
    )
    if len(candidates) == 1:
        return candidates[0], None
    if not candidates:
        return None, f"no VVARecord is reachable from episode {episode_id}"
    return None, (
        f"{len(candidates)} VVARecord objects are reachable from episode {episode_id} "
        f"({', '.join(candidates)}); pass --vva to choose one"
    )


def export_text(
    g: Graph, *, name: str, episode_id: str, rendering: str,
    plan_id: str | None = None, vva_id: str | None = None,
) -> str:
    """Exactly one export's text. `plan_id`/`vva_id`, when omitted, are auto-resolved
    (tolerantly — see the module docstring); a caller wanting the strict refuse-if-
    ambiguous behaviour resolves them itself first (`cli.py` does, for a single named
    format) and passes the result in.
    """
    from docket.canon import canonical_json
    from docket.exports.dmn import to_dmn
    from docket.exports.gsn import to_gsn
    from docket.exports.madr import to_madr
    from docket.exports.milstd3022 import to_milstd3022, to_milstd3022_for_episode
    from docket.exports.prov import to_prov
    from docket.exports.rtvm import rtvm_csv, to_rtvm

    if name == "prov":
        return canonical_json(to_prov(g, episode_id, rendering=rendering)) + "\n"
    if name == "gsn":
        return canonical_json(to_gsn(g, episode_id, rendering=rendering)) + "\n"
    if name == "dmn":
        if plan_id is None:
            plan_id, _ = resolve_plan_id(g, episode_id)
        return to_dmn(g, plan_id, rendering=rendering)
    if name == "milstd3022":
        # I2 (review round 2): a caller who already named one record (`--vva`, or the
        # CLI's own strict single-format resolution) gets exactly that record;
        # everyone else (`write_exports`/`build_package`) gets every VVARecord
        # forward-reachable from the episode, each as its own section — never a
        # forced, possibly-wrong single choice, and never "no record resolves"
        # printed over records that plainly exist.
        if vva_id is not None:
            return to_milstd3022(g, vva_id, rendering=rendering)
        return to_milstd3022_for_episode(g, episode_id, rendering=rendering)
    if name == "madr":
        return to_madr(g, episode_id, rendering=rendering)
    if name == "rtvm":
        return rtvm_csv(to_rtvm(g, episode_id, rendering=rendering))
    raise ValueError(f"unknown export name {name!r}; choose one of {sorted(EXPORTS)}")


def compute_all(
    g: Graph, episode_id: str, *, rendering: str,
) -> list[tuple[str, str]]:
    """Every export's `(filename, text)`, computed but not written — the one
    computation `write_exports` (which also writes the files) and `render.py`'s
    Machine-annex listing (which only needs the hashes) both read from, so the annex's
    sha256 lines and the bytes on disk can never drift apart (ruling R3)."""
    return sorted(
        (export_filename(name, rendering),
         export_text(g, name=name, episode_id=episode_id, rendering=rendering))
        for name in EXPORTS
    )


def write_computed(out_dir: Path, exports: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Write already-computed `(filename, text)` pairs to `out_dir`, returning
    `sorted[(filename, sha256_hex(text)), ...]`.

    The shared write step behind `write_exports` and `kernel.render.build_package`.
    `build_package` computes the export texts exactly once — *before* it seals the new
    `DecisionPackage` into the graph, since `to_prov`'s own `DecisionPackage` entities
    would otherwise differ between "compute for the annex" and "compute to write to
    disk" (the package being built cannot cite itself) — and passes that one result
    both to the renderer, for the Machine annex's hash lines, and here, to write the
    bytes those hash lines actually describe. Basenames only (ruling R5): `out_dir` is
    never encoded into a filename.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    result: list[tuple[str, str]] = []
    for filename, text in exports:
        (out_path / filename).write_text(text, encoding="utf-8", newline="\n")
        result.append((filename, sha256_hex(text)))
    return sorted(result)


def write_exports(
    g: Graph, episode_id: str, *, rendering: str, out_dir: Path,
) -> list[tuple[str, str]]:
    """Compute every export from the graph as it stands now and write it next to
    `package-{rendering}.md` in `out_dir`. Returns `sorted[(filename,
    sha256_hex(text)), ...]` — basenames only (ruling R5).

    Used by the `docket export --format all` CLI path, which has no in-flight
    `DecisionPackage` write to stay consistent with. `kernel.render.build_package`
    does *not* call this — see `write_computed`'s docstring for why it computes once
    and calls that directly instead.
    """
    return write_computed(out_dir, compute_all(g, episode_id, rendering=rendering))


__all__ = [
    "EXPORTS", "ExportSpec", "compute_all", "export_filename", "export_text",
    "resolve_plan_id", "resolve_vva_id", "write_computed", "write_exports",
]
