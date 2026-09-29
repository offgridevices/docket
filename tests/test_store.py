import json
import os
import stat

import pytest

from docket import KERNEL_ACTOR
from docket.canon import canonical_json, content_hash
from docket.errors import AuthorityViolation, ValidationError
from docket.store import Graph

H = {"actorType": "human", "actorId": "shreyash"}
A = {"actorType": "agent", "actorId": "agent:test"}


def rationale(i, actor=H, rev=1, **kw):
    return {"id": f"r-{i}", "type": "Rationale", "rev": rev, "createdBy": actor,
            "createdAt": "2026-09-04T00:00:00Z", "text": f"t{i}", "author": "a", **kw}


def test_put_get_all_sorted():
    g = Graph()
    g.put(rationale(2), H)
    g.put(rationale(1), H)
    assert [o["id"] for o in g.all()] == ["r-1", "r-2"]
    assert g.get("r-1")["text"] == "t1" and g.has("r-2") and not g.has("r-9")


def test_put_validates_schema():
    g = Graph()
    with pytest.raises(ValidationError):
        g.put({**rationale(1), "bogus": 1}, H)


def test_put_requires_created_by_to_match_actor():
    g = Graph()
    with pytest.raises(ValidationError):
        g.put(rationale(1, actor=A), H)
    with pytest.raises(ValidationError):
        g.put(rationale(3), KERNEL_ACTOR)


def test_append_only_revisions():
    g = Graph()
    g.put(rationale(1), H)
    with pytest.raises(ValidationError):
        g.put(rationale(1), H)  # same rev
    g.put(rationale(1, rev=2, text="changed"), H)
    assert g.get("r-1")["text"] == "changed" and g.get("r-1", rev=1)["text"] == "t1"
    with pytest.raises(ValidationError):
        g.put(rationale(1, rev=4), H)  # skipped rev


def test_log_is_hash_chained():
    g = Graph()
    g.put(rationale(1), H)
    g.put(rationale(2), H)
    log = g.log()
    assert log[0]["prevHash"] == "0" * 64 and log[1]["prevHash"] == log[0]["entryHash"]
    assert log[1]["seq"] == 2


def test_an_agent_id_declaring_itself_human_is_refused_as_malformed():
    """[T9 review M1] The boundary used to bind whatever `actorType` claimed, so
    `{"actorType": "human", "actorId": "agent:recorded"}` could approve a plan, sign a
    commitment and drive a human-only edge. The actor class is derived from the id now:
    an id beginning `agent:` is an agent, and a dict that says otherwise is malformed.
    """
    g = Graph()
    liar = {"actorType": "human", "actorId": "agent:recorded"}
    with pytest.raises(AuthorityViolation, match="an actorId beginning 'agent:' is an agent"):
        g.put({**rationale(1), "createdBy": liar}, liar)
    assert not g.has("r-1") and g.log() == []


def test_an_agent_whose_id_does_not_say_so_is_refused_as_malformed():
    """The other direction, and the reason the first one can be trusted: if an agent could
    take an id that does not begin `agent:`, the id would carry no information and
    deriving the actor class from it would be theatre."""
    g = Graph()
    hidden = {"actorType": "agent", "actorId": "helpful-assistant"}
    with pytest.raises(AuthorityViolation, match="must begin 'agent:'"):
        g.put({**rationale(1), "createdBy": hidden}, hidden)
    assert not g.has("r-1") and g.log() == []


def test_a_kernel_actor_may_not_wear_an_agent_id_either():
    """`kernel` is held to the same rule as `human`: nothing but an agent carries an
    `agent:` id, or the kernel actor becomes the hiding place."""
    g = Graph()
    pretender = {"actorType": "kernel", "actorId": "agent:recorded"}
    with pytest.raises(AuthorityViolation, match="an actorId beginning 'agent:' is an agent"):
        g.put({**rationale(1), "createdBy": pretender}, pretender)


def test_the_ordinary_three_actor_shapes_are_untouched():
    """The rule refuses a disagreement, not an actor. A human, the kernel and a
    conventionally-named agent all still write."""
    g = Graph()
    g.put(rationale(1), H)
    g.put({**rationale(2), "createdBy": KERNEL_ACTOR}, KERNEL_ACTOR)
    g.put({**rationale(3), "createdBy": A}, A)
    assert [e["actor"]["actorType"] for e in g.log()] == ["human", "kernel", "agent"]


def test_agent_cannot_create_forbidden_types():
    g = Graph()
    bad = {"id": "res-1", "type": "Result", "rev": 1, "createdBy": A, "createdAt": "2026-09-04",
           "run": "run-1", "alternative": "alt-1", "aggregate": True, "value": 1.0, "units": "pct",
           "method": "mavt"}
    with pytest.raises(AuthorityViolation):
        g.put(bad, A)


def test_agent_cannot_review_evidence_or_approve_plan_or_confirm_gap():
    g = Graph()
    ev = {"id": "ev-1", "type": "Evidence", "rev": 1, "createdBy": A, "createdAt": "2026-09-04",
          "title": "d", "evidenceType": "Document", "publisher": "p", "published": "2020",
          "pointer": {"uri": "u", "custodian": "c"},
          "classification": {"level": "U", "metadataLevel": "U"},
          "scopeOfValidity": {"builtToAnswer": "q", "questionClass": "other", "intendedUse": "u"},
          "reviewStatus": "reviewed", "reliabilitySteps": []}
    with pytest.raises(AuthorityViolation):
        g.put(ev, A)
    g.put({**ev, "reviewStatus": "draft", "reliabilitySteps": {"$gap": "gap-1"}}, A)
    gap = {"id": "gap-1", "type": "InsufficientEvidence", "rev": 1, "createdBy": A,
           "createdAt": "2026-09-04",
           "sought": "s", "whereLookedFor": ["x"], "whyNotFound": "w", "impact": "degrading",
           "indicatorsThatWouldResolve": [], "confirmedBy": {"actorId": "agent", "date": "2026"}}
    with pytest.raises(AuthorityViolation):
        g.put(gap, A)


def test_agent_cannot_change_lifecycle_state():
    g = Graph()
    ep = {"id": "ep-1", "type": "DecisionEpisode", "rev": 1, "createdBy": H,
          "createdAt": "2026-09-04",
          "sequence": 1, "charter": "ch-1", "lifecycleState": "MODEL_APPROVED", "transitions": [],
          "objectives": [], "alternatives": [], "groundRules": [], "constraints": [],
          "assumptions": [],
          "evidenceRegister": [], "scenarios": [], "claims": [], "risks": [], "biasChecks": [],
          "mandateElements": [], "observations": [], "weightSets": [], "models": [], "runs": [],
          "flipAnalyses": [], "narratives": [], "asOf": "2026-09-04"}
    g.put(ep, H)
    with pytest.raises(AuthorityViolation):
        g.put({**ep, "rev": 2, "createdBy": A, "lifecycleState": "PLAN_APPROVED"}, A)
    g.put({**ep, "rev": 2, "createdBy": A, "claims": ["cl-1"]}, A)  # same state: allowed


def test_refs_and_reachability():
    g = Graph()
    g.put({"id": "ev-1", "type": "Evidence", "rev": 1, "createdBy": H, "createdAt": "2026-09-04",
           "title": "d", "evidenceType": "Document", "publisher": "p", "published": "2020",
           "pointer": {"uri": "u", "custodian": "c"},
           "classification": {"level": "U", "metadataLevel": "U"},
           "scopeOfValidity": {"builtToAnswer": "q", "questionClass": "other", "intendedUse": "u"},
           "reviewStatus": "reviewed", "reliabilitySteps": []}, H)
    g.put({"id": "as-1", "type": "Assumption", "rev": 1, "createdBy": H, "createdAt": "2026-09-04",
           "statement": "s", "linchpin": True, "rationale": "r", "evidence": "ev-1",
           "implicationsIfWrong": "i", "indicatorsThatWouldAlter": ["x"],
           "variedInSensitivity": False}, H)
    g.put({"id": "cl-1", "type": "Claim", "rev": 1, "createdBy": H, "createdAt": "2026-09-04",
           "text": "c",
           "questionClass": "other", "assessableAt": {"level": "U"},
           "supportedBy": [{"evidence": "ev-1"}]}, H)
    assert g.refs_from("as-1") == ["ev-1"]
    assert sorted(g.refs_to("ev-1")) == ["as-1", "cl-1"]
    assert g.reachable_from("ev-1") == {"as-1", "cl-1"}
    assert g.reachable_from("cl-1", reverse=False) == {"ev-1"}


def test_save_load_roundtrip_is_byte_identical(tmp_path):
    g = Graph()
    g.put(rationale(1), H)
    g.put(rationale(1, rev=2, text="v2"), H)
    g.put(rationale(2, actor=KERNEL_ACTOR), KERNEL_ACTOR)
    g.save(tmp_path / "a")
    g.save(tmp_path / "b")
    files_a = sorted(p.relative_to(tmp_path / "a")
                      for p in (tmp_path / "a").rglob("*") if p.is_file())
    assert files_a == sorted(p.relative_to(tmp_path / "b")
                              for p in (tmp_path / "b").rglob("*") if p.is_file())
    for rel in files_a:
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes()
    g2 = Graph.load(tmp_path / "a")
    assert g2.snapshot_hash() == g.snapshot_hash() and g2.get("r-1")["text"] == "v2"
    assert g2.get("r-1", rev=1)["text"] == "t1" and g2.log() == g.log()
    manifest = json.loads((tmp_path / "a" / "manifest.json").read_text())
    assert manifest["snapshotHash"] == g.snapshot_hash()


def test_snapshot_hash_changes_with_content():
    g = Graph()
    g.put(rationale(1), H)
    h1 = g.snapshot_hash()
    g.put(rationale(2), H)
    assert g.snapshot_hash() != h1


def _evidence(i, actor=H, rev=1, review_status="draft", **kw):
    return {"id": f"ev-{i}", "type": "Evidence", "rev": rev, "createdBy": actor,
            "createdAt": "2026-09-04",
            "title": "d", "evidenceType": "Document", "publisher": "p", "published": "2020",
            "pointer": {"uri": "u", "custodian": "c"},
            "classification": {"level": "U", "metadataLevel": "U"},
            "scopeOfValidity": {"builtToAnswer": "q", "questionClass": "other",
                                "intendedUse": "u"},
            "reviewStatus": review_status, "reliabilitySteps": [], **kw}


def _episode(i, actor=H, rev=1, lifecycle_state="DRAFT", transitions=None, **kw):
    return {"id": f"ep-{i}", "type": "DecisionEpisode", "rev": rev, "createdBy": actor,
            "createdAt": "2026-09-04",
            "sequence": 1, "charter": "ch-1", "lifecycleState": lifecycle_state,
            "transitions": transitions if transitions is not None else [],
            "objectives": [], "alternatives": [], "groundRules": [], "constraints": [],
            "assumptions": [], "evidenceRegister": [], "scenarios": [], "claims": [],
            "risks": [], "biasChecks": [], "mandateElements": [], "observations": [],
            "weightSets": [], "models": [], "runs": [], "flipAnalyses": [], "narratives": [],
            "asOf": "2026-09-04", **kw}


def test_agent_cannot_approve_a_plan():
    g = Graph()
    plan = {"id": "pl-1", "type": "Plan", "rev": 1, "createdBy": A, "createdAt": "2026-09-04",
            "episode": "ep-9", "policyBasis": "pol-1",
            "steps": [{"id": "step-1", "evaluator": "model-1", "method": "mavt",
                       "alternatives": ["alt-1"], "measures": ["m-1"], "weightSet": "ws-1",
                       "authority": {"document": "doc-1", "paragraph": "p1"}}],
            "approvedBy": {"actorId": "shreyash", "date": "2026-09-04"}}
    with pytest.raises(AuthorityViolation):
        g.put(plan, A)


def test_agent_cannot_create_episode_with_non_draft_lifecycle():
    g = Graph()
    with pytest.raises(AuthorityViolation):
        g.put(_episode(10, actor=A, lifecycle_state="MODEL_APPROVED"), A)


def test_agent_cannot_create_new_episode_with_transitions():
    g = Graph()
    transition = {"from": "DRAFT", "to": "MODEL_APPROVED",
                  "actor": {"actorType": "human", "actorId": "shreyash"},
                  "at": "2026-09-04", "policyVersion": "v1",
                  "checksSatisfied": [], "checksUnsatisfied": [], "refused": False}
    with pytest.raises(AuthorityViolation):
        g.put(_episode(11, actor=A, transitions=[transition]), A)


def test_agent_cannot_revert_evidence_review_status():
    g = Graph()
    ev = _evidence(10, review_status="reviewed")
    g.put(ev, H)
    with pytest.raises(AuthorityViolation):
        g.put({**ev, "rev": 2, "createdBy": A, "reviewStatus": "draft"}, A)


def test_load_detects_tampered_object_hash_field(tmp_path):
    g = Graph()
    g.put(rationale(1), H)
    g.save(tmp_path / "a")
    log_path = tmp_path / "a" / "log.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[-1])
    entry["hash"] = "0" * 64
    entry_wo_hash = {k: v for k, v in entry.items() if k != "entryHash"}
    entry["entryHash"] = content_hash(entry_wo_hash)
    lines[-1] = canonical_json(entry)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        Graph.load(tmp_path / "a")


def test_load_detects_tampered_object_file(tmp_path):
    g = Graph()
    g.put(rationale(1), H)
    g.save(tmp_path / "a")
    obj_path = tmp_path / "a" / "objects" / "r-1@1.json"
    obj = json.loads(obj_path.read_text(encoding="utf-8"))
    obj["text"] = "tampered"
    obj_path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        Graph.load(tmp_path / "a")


def test_load_detects_snapshot_mismatch_when_log_entry_missing(tmp_path):
    g = Graph()
    g.put(rationale(1), H)
    g.put(rationale(2), H)
    g.save(tmp_path / "a")
    log_path = tmp_path / "a" / "log.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    log_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        Graph.load(tmp_path / "a")


def test_objects_by_type_groups_correctly():
    g = Graph()
    g.put(rationale(1), H)
    g.put(rationale(2), H)
    g.put(_evidence(20), H)
    out = g.objects_by_type
    assert set(out) == {"Rationale", "Evidence"}
    assert [o["id"] for o in out["Rationale"]] == ["r-1", "r-2"]
    assert [o["id"] for o in out["Evidence"]] == ["ev-20"]


def test_get_result_is_a_copy_not_a_live_reference():
    g = Graph()
    g.put(rationale(1), H)
    h1 = g.snapshot_hash()
    obj = g.get("r-1")
    obj["text"] = "mutated-in-place"
    assert g.snapshot_hash() == h1


def test_get_unknown_id_raises_key_error_without_mutating_state():
    g = Graph()
    with pytest.raises(KeyError):
        g.get("nope")
    assert "nope" not in g._history


def _rewrite_entry(log_path, index, **changes):
    """Rewrite one log entry, re-chaining every entryHash/prevHash after it."""
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    entries[index].update(changes)
    prev = "0" * 64
    for e in entries:
        e["prevHash"] = prev
        e["entryHash"] = content_hash({k: v for k, v in e.items() if k != "entryHash"})
        prev = e["entryHash"]
    log_path.write_text(
        "".join(canonical_json(e) + "\n" for e in entries), encoding="utf-8", newline="\n"
    )


def test_load_rejects_non_monotonic_revisions(tmp_path):
    g = Graph()
    g.put(rationale(1), H)
    g.put(rationale(1, rev=2, text="v2"), H)
    g.save(tmp_path / "a")
    objects = tmp_path / "a" / "objects"
    obj = json.loads((objects / "r-1@2.json").read_text(encoding="utf-8"))
    obj["rev"] = 3
    (objects / "r-1@3.json").write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    (objects / "r-1@2.json").unlink()
    _rewrite_entry(tmp_path / "a" / "log.jsonl", 1, rev=3, hash=content_hash(obj))
    with pytest.raises(ValidationError, match="out of order"):
        Graph.load(tmp_path / "a")


def test_load_rejects_a_path_traversal_rev_before_reading_any_file(tmp_path):
    g = Graph()
    g.put(rationale(1), H)
    g.save(tmp_path / "a")
    _rewrite_entry(tmp_path / "a" / "log.jsonl", 0, rev="1/../x")
    with pytest.raises(ValidationError, match="not a positive integer"):
        Graph.load(tmp_path / "a")


def _watch_renames(monkeypatch, fail_on=()):
    """Patch the store's os.rename: record every call, raise on the ones named in fail_on.

    Returns the list of calls made so far, so a test can both inject a failure and learn
    how many rename operations one save actually performs.
    """
    fail_on = {fail_on} if isinstance(fail_on, int) else set(fail_on)
    real_rename = os.rename
    calls = []

    def watched(src, dst):
        calls.append((src, dst))
        if len(calls) in fail_on:
            raise OSError("injected failure mid-swap")
        return real_rename(src, dst)

    monkeypatch.setattr("docket.store.os.rename", watched)
    return calls


def _two_stores(tmp_path):
    """An on-disk store holding r-1, and an in-memory graph holding r-1 and r-2."""
    g1 = Graph()
    g1.put(rationale(1), H)
    g2 = Graph()
    g2.put(rationale(1), H)
    g2.put(rationale(2), H)
    return g1, g2


def test_save_over_an_existing_store_survives_a_failed_swap(tmp_path, monkeypatch):
    store = tmp_path / "a"
    g1, g2 = _two_stores(tmp_path)
    g1.save(store)
    before = g1.snapshot_hash()

    _watch_renames(monkeypatch, fail_on=2)
    with pytest.raises(OSError, match="injected failure mid-swap"):
        g2.save(store)
    monkeypatch.undo()

    assert Graph.load(store).snapshot_hash() == before


def test_save_survives_a_failure_on_the_last_swap_operation(tmp_path, monkeypatch):
    """Whatever the final swap operation is, failing it must leave the old store loadable.

    The per-artefact swap this replaced failed exactly here: manifest.json stayed on the
    old snapshot while objects/ and log.jsonl moved to the new one, and the store would
    no longer load at all.
    """
    store = tmp_path / "a"
    probe = tmp_path / "probe"
    g1, g2 = _two_stores(tmp_path)
    g1.save(store)
    g1.save(probe)
    before = g1.snapshot_hash()

    # Count the rename operations a clean save over an existing store performs.
    calls = _watch_renames(monkeypatch)
    g2.save(probe)
    monkeypatch.undo()
    total = len(calls)
    assert total >= 2

    _watch_renames(monkeypatch, fail_on=total)
    with pytest.raises(OSError, match="injected failure mid-swap"):
        g2.save(store)
    monkeypatch.undo()

    assert Graph.load(store).snapshot_hash() == before
    assert not list(tmp_path.glob("a.aside-*"))


def test_put_rejects_an_id_with_a_trailing_newline():
    g = Graph()
    with pytest.raises(ValidationError, match="does not match the id pattern"):
        g.put({**rationale(1), "id": "r-1\n"}, H)


def test_save_keeps_the_only_copy_when_the_restore_also_fails(tmp_path, monkeypatch):
    """Swap fails, then the restore fails too. The aside copy must survive and be named."""
    store = tmp_path / "a"
    g1, g2 = _two_stores(tmp_path)
    g1.save(store)
    before = g1.snapshot_hash()

    _watch_renames(monkeypatch, fail_on=(2, 3))
    with pytest.raises(OSError, match="the only copy is at"):
        g2.save(store)
    monkeypatch.undo()

    asides = list(tmp_path.glob("a.aside-*"))
    assert len(asides) == 1
    assert Graph.load(asides[0]).snapshot_hash() == before


def test_save_preserves_the_permissions_an_existing_store_had(tmp_path):
    store = tmp_path / "a"
    g1, g2 = _two_stores(tmp_path)
    g1.save(store)
    store.chmod(0o700)
    g2.save(store)
    assert stat.S_IMODE(store.stat().st_mode) == 0o700


def test_load_refuses_a_missing_store(tmp_path):
    with pytest.raises(ValidationError, match="store not found at"):
        Graph.load(tmp_path / "nope")


def test_load_refuses_a_directory_with_no_log(tmp_path):
    store = tmp_path / "a"
    store.mkdir()
    (store / "manifest.json").write_text('{"snapshotHash": "x"}\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="store not found at"):
        Graph.load(store)


def _read_manifest(store):
    return json.loads((store / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(store, manifest):
    (store / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def test_save_records_the_log_head_in_the_manifest(tmp_path):
    g = Graph()
    g.put(rationale(1), H)
    g.put(rationale(2), H)
    g.save(tmp_path / "a")
    manifest = _read_manifest(tmp_path / "a")
    assert manifest["logHead"] == g.log()[-1]["entryHash"]
    assert manifest["objects"] == 2 and manifest["logEntries"] == 2

    Graph().save(tmp_path / "empty")
    assert _read_manifest(tmp_path / "empty")["logHead"] == "0" * 64


def test_load_requires_a_manifest(tmp_path):
    g = Graph()
    g.put(rationale(1), H)
    g.save(tmp_path / "a")
    (tmp_path / "a" / "manifest.json").unlink()
    with pytest.raises(ValidationError, match="manifest not found"):
        Graph.load(tmp_path / "a")


def test_load_detects_a_truncated_log_even_when_the_manifest_looks_consistent(tmp_path):
    """The forger drops the last entry and fixes the counts and the snapshot hash.

    Only logHead is left to notice, which is exactly why it is written down.
    """
    store = tmp_path / "a"
    g = Graph()
    g.put(rationale(1), H)
    g.put(rationale(2), H)
    g.save(store)

    log_path = store / "log.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    log_path.write_text(lines[0] + "\n", encoding="utf-8", newline="\n")
    kept = json.loads((store / "objects" / "r-1@1.json").read_text(encoding="utf-8"))
    manifest = _read_manifest(store)
    manifest.update({"objects": 1, "logEntries": 1, "snapshotHash": content_hash([kept])})
    _write_manifest(store, manifest)

    with pytest.raises(ValidationError, match="logHead"):
        Graph.load(store)


def test_load_detects_a_rechained_forgery_against_the_manifest(tmp_path):
    """Edit an object, recompute its entry hash and re-chain the log: the chain verifies
    again, so the manifest's snapshot hash is the only thing that still disagrees."""
    store = tmp_path / "a"
    g = Graph()
    g.put(rationale(1), H)
    g.save(store)

    obj_path = store / "objects" / "r-1@1.json"
    obj = json.loads(obj_path.read_text(encoding="utf-8"))
    obj["text"] = "forged"
    obj_path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    _rewrite_entry(store / "log.jsonl", 0, hash=content_hash(obj))

    with pytest.raises(ValidationError, match="snapshotHash"):
        Graph.load(store)


def test_agent_may_not_revise_reviewed_evidence():
    """The human reviewed content X; an agent must not be able to make it say Y."""
    g = Graph()
    ev = _evidence(11, review_status="reviewed")
    g.put(ev, H)
    with pytest.raises(AuthorityViolation, match="non-draft evidence"):
        g.put({**ev, "rev": 2, "createdBy": A, "title": "rewritten"}, A)


def _policy(actor=H, **kw):
    return {"id": "pol-1", "type": "Policy", "rev": 1, "createdBy": actor,
            "createdAt": "2026-09-04", "name": "n", "version": "v1",
            "decisionClass": "materiel", "method": "mavt", "tailoring": "full-36",
            "aggregationK": 1, "requiredBiasChecks": [], "requireAllLinchpinsVaried": True,
            "prohibitedExclusionReasons": ["time-or-resource"], "blockingRules": [],
            "nSimplex": 100, **kw}


def test_agent_cannot_create_a_policy():
    """The gate's own parameters are not the agent's to write."""
    g = Graph()
    with pytest.raises(AuthorityViolation, match="agent may not create Policy"):
        g.put(_policy(actor=A), A)
    g.put(_policy(), H)


def _exclusion(i, actor=H, authority=None, **kw):
    return {"id": f"ex-{i}", "type": "Exclusion", "rev": 1, "createdBy": actor,
            "createdAt": "2026-09-04",
            "target": {"kind": "Alternative", "label": "an option"},
            "reasonType": "out-of-scope", "reason": "r",
            "authority": authority or {"who": "COL Smith", "role": "PM",
                                       "date": "2026-09-04"},
            "retainedInStructure": True, **kw}


def test_agent_exclusion_may_only_be_a_proposal():
    g = Graph()
    with pytest.raises(AuthorityViolation, match="exclusion authority"):
        g.put(_exclusion(1, actor=A), A)
    g.put(
        _exclusion(1, actor=A,
                   authority={"who": A["actorId"], "role": "agent-proposal",
                              "date": "2026-09-04"}),
        A,
    )


def test_human_may_assert_any_exclusion_authority():
    g = Graph()
    g.put(_exclusion(2), H)
    assert g.get("ex-2")["authority"]["role"] == "PM"


def test_agent_may_not_revise_a_human_authorised_exclusion():
    """A human authorised this omission; an agent may not touch the record at all."""
    g = Graph()
    g.put(_exclusion(3), H)
    with pytest.raises(AuthorityViolation, match="human-authorised exclusion"):
        g.put(
            {**_exclusion(3), "rev": 2, "createdBy": A,
             "authority": {"who": A["actorId"], "role": "agent-proposal",
                           "date": "2026-09-04"}},
            A,
        )


def test_agent_may_revise_its_own_proposed_exclusion():
    g = Graph()
    proposal = {"who": A["actorId"], "role": "agent-proposal", "date": "2026-09-04"}
    g.put(_exclusion(4, actor=A, authority=proposal), A)
    g.put({**_exclusion(4, actor=A, authority=proposal), "rev": 2, "reason": "updated"}, A)
    assert g.get("ex-4")["reason"] == "updated"


def test_agent_may_not_take_over_another_agents_proposed_exclusion():
    """One agent's proposal is not another agent's to revise, even both being agents."""
    g = Graph()
    other = {"actorType": "agent", "actorId": "agent:other"}
    proposal = {"who": A["actorId"], "role": "agent-proposal", "date": "2026-09-04"}
    g.put(_exclusion(5, actor=A, authority=proposal), A)
    with pytest.raises(AuthorityViolation, match="take over another agent's proposed exclusion"):
        g.put(
            {**_exclusion(5, actor=other, authority={**proposal, "who": other["actorId"]}),
             "rev": 2, "createdBy": other},
            other,
        )


def test_put_forbids_changing_type_across_revisions():
    """Append-only means the id keeps identifying the same kind of thing, for any actor."""
    g = Graph()
    g.put(rationale(1), H)
    with pytest.raises(ValidationError, match="type may not change across revisions"):
        g.put({**_evidence(1), "id": "r-1", "rev": 2, "createdBy": H}, H)


def test_load_detects_a_non_json_manifest(tmp_path):
    store = tmp_path / "a"
    g = Graph()
    g.put(rationale(1), H)
    g.save(store)
    (store / "manifest.json").write_text("not json at all", encoding="utf-8")
    with pytest.raises(ValidationError, match="manifest.*not valid JSON"):
        Graph.load(store)


def test_load_detects_a_json_array_log_line(tmp_path):
    store = tmp_path / "a"
    g = Graph()
    g.put(rationale(1), H)
    g.save(store)
    (store / "log.jsonl").write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="must be a JSON object"):
        Graph.load(store)
