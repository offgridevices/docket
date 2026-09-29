"""The graph: append-only object store with a hash-chained log and the agent authority boundary."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path

from docket import KERNEL_VERSION
from docket.canon import canonical_json, content_hash
from docket.errors import AuthorityViolation, ValidationError
from docket.objects import (
    AGENT_FORBIDDEN_TYPES,
    actor_class_mismatch,
    is_agent_actor,
    is_content,
    iter_refs,
)
from docket.schema import validate_object
from docket.schema.generate import ID_PATTERN

GENESIS = "0" * 64
_ID_RE = re.compile(ID_PATTERN)


def _read_text(path: Path) -> str:
    """Read UTF-8 text with newline translation disabled, so a tampered CRLF is visible."""
    with open(path, encoding="utf-8", newline="\n") as f:
        return f.read()


def _parse_json_object(text: str, what: str) -> dict:
    """Parse `text` as a JSON object, naming `what` in any failure.

    A hand-edited or truncated store must fail as a ValidationError naming the offending
    file, never as a raw JSONDecodeError/AttributeError from code downstream that assumes
    the parsed value is a dict.
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError([f"{what} is not valid JSON: {exc}"]) from exc
    if not isinstance(parsed, dict):
        raise ValidationError(
            [f"{what} must be a JSON object, got {type(parsed).__name__}"]
        )
    return parsed


class Graph:
    def __init__(self) -> None:
        self._latest: dict[str, dict] = {}
        self._history: dict[str, dict[int, dict]] = defaultdict(dict)
        self._log: list[dict] = []
        self._reverse: dict[str, set[str]] | None = None

    # ---- writes ---------------------------------------------------------
    def put(self, obj: dict, actor: dict) -> dict:
        obj = deepcopy(obj)
        actor = deepcopy(actor)
        errs = validate_object(obj)
        if errs:
            raise ValidationError(errs)
        # The schema's `pattern` is applied with re.search, so `$` lets a trailing newline
        # through. fullmatch here makes the write side agree with load()'s read side.
        if not isinstance(obj["id"], str) or not _ID_RE.fullmatch(obj["id"]):
            raise ValidationError([f"id {obj['id']!r} does not match the id pattern"])
        if obj["createdBy"] != actor:
            raise ValidationError(
                [f"createdBy {obj['createdBy']} does not match actor {actor}"]
            )
        # The one choke point. `put` is the only public write, and `lifecycle.transition`
        # reaches the log through it too, so deriving the actor class here binds every
        # write and every gate attempt in the process [T9 review M1].
        mismatch = actor_class_mismatch(actor)
        if mismatch is not None:
            raise AuthorityViolation(f"malformed actor: {mismatch}")
        if is_agent_actor(actor):
            self._check_agent_authority(obj, actor)
        existing = self._latest.get(obj["id"])
        if existing is not None and obj["type"] != existing["type"]:
            raise ValidationError(
                [f"{obj['id']}: type may not change across revisions "
                 f"(was {existing['type']}, got {obj['type']})"]
            )
        if existing is None and obj["rev"] != 1:
            raise ValidationError(
                [f"{obj['id']}: first revision must be rev 1, got {obj['rev']}"]
            )
        if existing is not None and obj["rev"] != existing["rev"] + 1:
            raise ValidationError(
                [f"{obj['id']}: append-only — expected rev {existing['rev'] + 1}, "
                 f"got {obj['rev']}"]
            )
        h = content_hash(obj)
        prev = self._log[-1]["entryHash"] if self._log else GENESIS
        entry = {"seq": len(self._log) + 1, "op": "put", "id": obj["id"], "type": obj["type"],
                 "rev": obj["rev"], "hash": h, "actor": actor, "prevHash": prev}
        entry["entryHash"] = content_hash(entry)
        self._latest[obj["id"]] = obj
        self._history[obj["id"]][obj["rev"]] = obj
        self._log.append(entry)
        self._reverse = None
        return deepcopy(obj)

    def _check_agent_authority(self, obj: dict, actor: dict) -> None:
        t = obj["type"]
        if t in AGENT_FORBIDDEN_TYPES:
            raise AuthorityViolation(f"agent may not create {t}")
        if t == "Evidence":
            prev = self._latest.get(obj["id"])
            required_status = prev.get("reviewStatus") if prev is not None else "draft"
            # Reviewed evidence is frozen against agents entirely, not just its status: a
            # human reviewed particular content, so the content may not change underneath
            # the review.
            if prev is not None and required_status != "draft":
                raise AuthorityViolation("agent may not revise non-draft evidence")
            if obj.get("reviewStatus") != required_status:
                raise AuthorityViolation("agent may not change Evidence.reviewStatus")
        if t == "Exclusion":
            prev = self._latest.get(obj["id"])
            prev_authority = (prev.get("authority") or {}) if prev is not None else {}
            # A human-authorised exclusion is not the agent's to touch at all, even to
            # re-propose it under its own name: the stored authority is what's protected.
            if prev is not None and prev_authority.get("role") != "agent-proposal":
                raise AuthorityViolation("agent may not revise a human-authorised exclusion")
            # Nor may one agent take over another agent's proposal by revising it under a
            # different actorId: a proposal's authorship is as protected as its content.
            if prev is not None and prev_authority.get("who") != actor["actorId"]:
                raise AuthorityViolation(
                    "agent may not take over another agent's proposed exclusion"
                )
            # An agent may propose an omission, never assert that a human authorised one.
            authority = obj.get("authority")
            if (not isinstance(authority, dict)
                    or authority.get("who") != actor["actorId"]
                    or authority.get("role") != "agent-proposal"):
                raise AuthorityViolation("agent may not assert exclusion authority")
        if t == "Plan" and obj.get("approvedBy"):
            raise AuthorityViolation("agent may not approve a Plan")
        if t == "InsufficientEvidence" and is_content(obj.get("confirmedBy")):
            raise AuthorityViolation("agent may not confirm an InsufficientEvidence object")
        if t == "DecisionEpisode":
            prev = self._latest.get(obj["id"])
            if prev is None:
                if obj["lifecycleState"] != "DRAFT":
                    raise AuthorityViolation("agent may only create DRAFT episodes")
                if obj.get("transitions") != []:
                    raise AuthorityViolation("agent may not write transitions")
            else:
                if prev["lifecycleState"] != obj["lifecycleState"]:
                    raise AuthorityViolation("agent may not change lifecycleState")
                if prev.get("transitions") != obj.get("transitions"):
                    raise AuthorityViolation("agent may not write transitions")

    # ---- reads ----------------------------------------------------------
    def get(self, obj_id: str, rev: int | None = None) -> dict:
        if obj_id not in self._latest:
            raise KeyError(obj_id)
        if rev is None:
            return deepcopy(self._latest[obj_id])
        history = self._history.get(obj_id, {})
        if rev not in history:
            raise KeyError(obj_id)
        return deepcopy(history[rev])

    def has(self, obj_id: str) -> bool:
        return obj_id in self._latest

    def ids(self) -> list[str]:
        return sorted(self._latest)

    def all(self, type_name: str | None = None) -> list[dict]:
        objs = (o for o in self._latest.values() if type_name is None or o["type"] == type_name)
        return [deepcopy(o) for o in sorted(objs, key=lambda o: o["id"])]

    @property
    def objects_by_type(self) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = defaultdict(list)
        for o in self.all():
            out[o["type"]].append(o)
        return dict(out)

    def log(self) -> list[dict]:
        return deepcopy(self._log)

    def refs_from(self, obj_id: str) -> list[str]:
        return sorted({t for _, t in iter_refs(self._latest[obj_id])})

    def _reverse_index(self) -> dict[str, set[str]]:
        if self._reverse is None:
            rev: dict[str, set[str]] = defaultdict(set)
            for oid, obj in self._latest.items():
                for _, target in iter_refs(obj):
                    rev[target].add(oid)
            self._reverse = rev
        return self._reverse

    def refs_to(self, obj_id: str) -> list[str]:
        return sorted(self._reverse_index().get(obj_id, set()))

    def reachable_from(self, obj_id: str, reverse: bool = True) -> set[str]:
        """reverse=True: everything that (transitively) references obj_id — the affected set."""
        seen: set[str] = set()
        queue = deque([obj_id])
        while queue:
            cur = queue.popleft()
            nxt = self.refs_to(cur) if reverse else (self.refs_from(cur) if self.has(cur) else [])
            for n in nxt:
                if n not in seen and n != obj_id:
                    seen.add(n)
                    queue.append(n)
        return seen

    def snapshot_hash(self) -> str:
        return content_hash([self._latest[i] for i in self.ids()])

    # ---- persistence ----------------------------------------------------
    def save(self, path: Path) -> None:
        """Write the complete new store into a temp sibling dir, then swap the whole directory
        in with two renames, so no reader ever sees a store built from two snapshots."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.mkdtemp(dir=path.parent))
        aside = path.with_name(f"{path.name}.aside-{os.getpid()}")
        aside_is_the_only_copy = False
        try:
            tmp_objects = tmp_dir / "objects"
            tmp_objects.mkdir(parents=True, exist_ok=True)
            for oid in self.ids():
                for rev, obj in sorted(self._history[oid].items()):
                    (tmp_objects / f"{oid}@{rev}.json").write_text(
                        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
            (tmp_dir / "log.jsonl").write_text(
                "".join(canonical_json(e) + "\n" for e in self._log),
                encoding="utf-8", newline="\n")
            (tmp_dir / "manifest.json").write_text(
                json.dumps(
                    {"snapshotHash": self.snapshot_hash(), "kernelVersion": KERNEL_VERSION,
                     "objects": len(self._latest), "logEntries": len(self._log),
                     "logHead": self._log[-1]["entryHash"] if self._log else GENESIS},
                    indent=2, sort_keys=True) + "\n",
                encoding="utf-8", newline="\n")

            # mkdtemp gives 0700, and the directory is about to become the store. Keep the
            # permissions the store already had; for a brand-new one, what mkdir would give.
            had_old = path.exists()
            if had_old:
                mode = stat.S_IMODE(path.stat().st_mode)
            else:
                umask = os.umask(0o077)
                os.umask(umask)
                mode = 0o777 & ~umask
            os.chmod(tmp_dir, mode)

            # Swap the store as one unit. Two renames, never a partial store: a failure of
            # the second puts the original back untouched, so there is no window in which
            # objects/, log.jsonl and manifest.json come from different snapshots.
            if had_old:
                os.rename(path, aside)
                aside_is_the_only_copy = True
            try:
                os.rename(tmp_dir, path)
            except BaseException as swap_exc:
                if aside_is_the_only_copy:
                    try:
                        os.rename(aside, path)
                    except OSError as restore_exc:
                        # Both renames failed. The store exists only under `aside`, so say
                        # where it is and let the finally block leave it alone.
                        raise OSError(
                            f"store swap failed ({swap_exc}) and the original could not be "
                            f"restored; the only copy is at {aside}"
                        ) from restore_exc
                    aside_is_the_only_copy = False
                raise
            aside_is_the_only_copy = False
        finally:
            if not aside_is_the_only_copy:
                shutil.rmtree(aside, ignore_errors=True)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @classmethod
    def load(cls, path: Path) -> Graph:
        """Verify the entire hash chain and every object before populating any state."""
        path = Path(path)
        log_path = path / "log.jsonl"
        # No log means there is no store here. An empty graph is something you construct
        # with Graph(); loading must never invent one, or a crash between save()'s two
        # renames would look like a fresh start instead of the data loss it is.
        if not log_path.is_file():
            raise ValidationError([f"store not found at {path}"])
        log = [
            _parse_json_object(line, f"{log_path}: line {lineno}")
            for lineno, line in enumerate(_read_text(log_path).splitlines(), start=1)
            if line
        ]

        objects_dir = path / "objects"
        loaded_objects: list[dict] = []
        expected_rev: dict[str, int] = {}
        prev_hash = GENESIS
        for i, entry in enumerate(log):
            seq = i + 1
            if entry.get("seq") != seq:
                raise ValidationError(
                    [f"seq {seq}: seq field does not match its log position "
                     f"(got {entry.get('seq')!r})"]
                )
            if entry.get("prevHash") != prev_hash:
                raise ValidationError(
                    [f"seq {seq}: prevHash does not chain from the previous entryHash"]
                )
            entry_wo_hash = {k: v for k, v in entry.items() if k != "entryHash"}
            recomputed_entry_hash = content_hash(entry_wo_hash)
            if entry.get("entryHash") != recomputed_entry_hash:
                raise ValidationError([f"seq {seq}: entryHash does not match its recomputed hash"])
            prev_hash = entry["entryHash"]

            oid = entry.get("id")
            # fullmatch, not match: `$` alone would let a trailing newline through and into
            # the object path we are about to build.
            if not isinstance(oid, str) or not _ID_RE.fullmatch(oid):
                raise ValidationError([f"seq {seq}: id {oid!r} does not match the id pattern"])
            rev = entry.get("rev")
            if not isinstance(rev, int) or isinstance(rev, bool) or rev < 1:
                raise ValidationError([f"seq {seq}: rev {rev!r} is not a positive integer"])
            want = expected_rev.get(oid, 1)
            if rev != want:
                raise ValidationError(
                    [f"seq {seq}: {oid} rev {rev} is out of order — expected rev {want}"]
                )
            expected_rev[oid] = rev + 1
            obj_path = objects_dir / f"{oid}@{rev}.json"
            if not obj_path.is_file():
                raise ValidationError([f"seq {seq}: object file missing for {oid}@{rev}"])
            obj = _parse_json_object(_read_text(obj_path), f"object file {obj_path}")
            if obj.get("id") != oid:
                raise ValidationError([f"seq {seq}: object file id does not match the log entry"])
            if obj.get("rev") != rev:
                raise ValidationError([f"seq {seq}: object file rev does not match the log entry"])
            if obj.get("type") != entry.get("type"):
                raise ValidationError([f"seq {seq}: object file type does not match the log entry"])
            if content_hash(obj) != entry.get("hash"):
                raise ValidationError(
                    [f"seq {seq}: object content hash does not match the log entry"]
                )
            loaded_objects.append(obj)

        g = cls()
        for entry, obj in zip(log, loaded_objects, strict=True):
            g._latest[entry["id"]] = obj
            g._history[entry["id"]][entry["rev"]] = obj
        g._log = log

        # The manifest is required, for the same reason the log is: a store missing it is a
        # partial copy, not a valid store. Optional, it could be deleted to switch off the
        # only check that catches a re-chained forgery or a truncated log.
        manifest_path = path / "manifest.json"
        if not manifest_path.is_file():
            raise ValidationError([f"manifest not found at {manifest_path}"])
        manifest = _parse_json_object(_read_text(manifest_path), f"manifest {manifest_path}")
        log_head = log[-1]["entryHash"] if log else GENESIS
        # snapshotHash before logHead: a forger who re-chains the log moves the head too, and
        # naming the snapshot is the more informative refusal.
        checks = (
            ("objects", manifest.get("objects"), len(g._latest)),
            ("logEntries", manifest.get("logEntries"), len(log)),
            ("snapshotHash", manifest.get("snapshotHash"), g.snapshot_hash()),
            ("logHead", manifest.get("logHead"), log_head),
        )
        for field, claimed, actual in checks:
            if claimed != actual:
                raise ValidationError(
                    [f"manifest {field} ({claimed!r}) does not match the loaded store "
                     f"({actual!r})"]
                )
        return g
