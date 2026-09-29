import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import docket.kernel.validate
from docket.canon import canonical_json, content_hash
from docket.kernel.findings import Finding
from docket.kernel.validate import KNOWN_RULES, validate
from docket.store import GENESIS, Graph

H = {"actorType": "human", "actorId": "t"}
A = {"actorType": "agent", "actorId": "agent:test"}


def base(oid, t, **kw):
    return {"id": oid, "type": t, "rev": 1, "createdBy": H, "createdAt": "2026-09-04", **kw}


def test_finding_is_sortable_and_frozen():
    a = Finding("a", "blocking", ("x",), "m")
    b = Finding("b", "warning", ("y",), "m")
    assert sorted([b, a])[0] == a


def test_ref_integrity():
    g = Graph()
    g.put(base("gr-1", "GroundRule", statement="s", source="ev-missing"), H)
    f = validate(g)
    assert any(
        x.rule == "ref-integrity" and x.objects == ("gr-1",) and "ev-missing" in x.message
        for x in f
    )


def test_marker_must_point_at_right_type():
    g = Graph()
    g.put(base("r-1", "Rationale", text="t", author="a"), H)
    g.put(base("gr-1", "GroundRule", statement="s", source={"$gap": "r-1"}), H)
    f = validate(g)
    assert any(x.rule == "marker-type" for x in f)


def test_silence_detects_empty_required_slot_content():
    g = Graph()
    g.put(
        base(
            "ch-1", "Charter", question="q", decisionToBeMade="d",
            consequencesOfErroneousOutput="", questionClass="other",
            scope={"included": ["x"], "excluded": []},
            authority={"signer": "s"}, decisionClassPolicy="pol-1",
        ),
        H,
    )
    f = validate(g)
    assert any(
        x.rule == "silence" and x.objects == ("ch-1",)
        and "consequencesOfErroneousOutput" in x.message
        for x in f
    )


def test_clean_graph_has_no_structural_findings():
    g = Graph()
    g.put(base("gap-1", "InsufficientEvidence", sought="s", whereLookedFor=["a"], whyNotFound="w",
               impact="degrading", indicatorsThatWouldResolve=[]), H)
    g.put(base("gr-1", "GroundRule", statement="s", source={"$gap": "gap-1"}), H)
    structural = {"schema", "ref-integrity", "silence", "marker-type", "log-chain"}
    assert [x for x in validate(g) if x.rule in structural] == []


def test_schema_rule_reports_invalid_object(monkeypatch):
    g = Graph()
    g.put(base("gap-1", "InsufficientEvidence", sought="s", whereLookedFor=["a"], whyNotFound="w",
               impact="degrading", indicatorsThatWouldResolve=[]), H)
    g.put(base("gr-1", "GroundRule", statement="s", source={"$gap": "gap-1"}), H)

    import docket.kernel.validate as validate_mod
    real_validate_object = validate_mod.validate_object

    def fake_validate_object(obj):
        if obj["id"] == "gr-1":
            return ["statement: 42 is not of type 'string'"]
        return real_validate_object(obj)

    monkeypatch.setattr(validate_mod, "validate_object", fake_validate_object)
    f = validate(g)
    assert any(
        x.rule == "schema" and x.objects == ("gr-1",)
        and x.message == "statement: 42 is not of type 'string'"
        for x in f
    )


def test_log_chain_rule_detects_tampering(monkeypatch):
    g = Graph()
    g.put(base("gap-1", "InsufficientEvidence", sought="s", whereLookedFor=["a"], whyNotFound="w",
               impact="degrading", indicatorsThatWouldResolve=[]), H)
    g.put(base("gr-1", "GroundRule", statement="s", source={"$gap": "gap-1"}), H)

    entries = g.log()
    entries[1]["hash"] = "0" * 64
    monkeypatch.setattr(g, "log", lambda: entries)

    findings = [x for x in validate(g) if x.rule == "log-chain"]
    assert len(findings) == 1
    assert "seq 2" in findings[0].message


def test_validate_survives_an_object_whose_type_is_not_in_the_catalogue():
    """A store written by a different docket version is exactly what the validator is for.

    Built by hand because put() would refuse it.
    """
    g = Graph()
    obj = base("x-1", "Nope")
    g._latest["x-1"] = obj
    g._history["x-1"][1] = obj
    entry = {"seq": 1, "op": "put", "id": "x-1", "type": "Nope", "rev": 1,
             "hash": content_hash(obj), "actor": H, "prevHash": GENESIS}
    entry["entryHash"] = content_hash(entry)
    g._log.append(entry)

    findings = validate(g)
    assert [f.rule for f in findings] == ["schema"]
    assert findings[0].objects == ("x-1",) and "Nope" in findings[0].message


def _write_json(path, obj):
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")


def _rechain_and_reseal(store):
    """Re-chain the log against the object files on disk and rewrite the manifest.

    The forger's job done properly: afterwards nothing short of a signature could tell
    the store had been hand-edited, which is why the audit has to look at authorship.
    """
    log_path = store / "log.jsonl"
    entries = [json.loads(line)
               for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    latest, prev = {}, GENESIS
    for e in entries:
        obj = json.loads(
            (store / "objects" / f"{e['id']}@{e['rev']}.json").read_text(encoding="utf-8"))
        e["type"] = obj["type"]
        e["hash"] = content_hash(obj)
        e["actor"] = obj["createdBy"]
        e["prevHash"] = prev
        e["entryHash"] = content_hash({k: v for k, v in e.items() if k != "entryHash"})
        prev = e["entryHash"]
        latest[e["id"]] = obj
    log_path.write_text("".join(canonical_json(e) + "\n" for e in entries),
                        encoding="utf-8", newline="\n")
    manifest = json.loads((store / "manifest.json").read_text(encoding="utf-8"))
    manifest.update({"objects": len(latest), "logEntries": len(entries),
                     "snapshotHash": content_hash([latest[i] for i in sorted(latest)]),
                     "logHead": prev})
    (store / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def test_authority_rule_catches_an_agent_authored_object_in_a_saved_store(tmp_path):
    """put() enforces the agent boundary in process; a saved store can be hand-edited.

    The chain is unkeyed, so a re-chained forgery still loads. The audit must be able to
    say so from the store alone.
    """
    store = tmp_path / "forged"
    g = Graph()
    g.put(base("pol-1", "Policy", name="n", version="v1", decisionClass="materiel",
               method="mavt", tailoring="full-36", aggregationK=1, requiredBiasChecks=[],
               requireAllLinchpinsVaried=True, prohibitedExclusionReasons=[],
               blockingRules=[], nSimplex=100), H)
    g.save(store)

    obj_path = store / "objects" / "pol-1@1.json"
    obj = json.loads(obj_path.read_text(encoding="utf-8"))
    obj["createdBy"] = A
    _write_json(obj_path, obj)
    _rechain_and_reseal(store)

    findings = validate(Graph.load(store))
    assert [f.rule for f in findings] == ["authority"]
    assert findings[0].objects == ("pol-1",) and findings[0].severity == "blocking"


# ---- authority: the seven non-type agent rules, audited from the store [ruling R14] ---
#
# `Graph.put` refuses every one of these in process, so each has to be seeded past `put`
# — which is the whole point: the question these tests answer is what a *hand-edited*
# store gives up, not what the write path stops. Seeding `_latest`/`_history`/`_log`
# directly is the cheapest honest way to build one; `_rechain_and_reseal` above proves
# separately that the same objects survive a save/load round trip with a valid chain.


def _seed(g, *objs_and_actors):
    """Put objects into a graph's state without going through `put`, keeping the chain
    valid so `log-chain` stays silent and `authority` is the only rule under test."""
    for obj, actor in objs_and_actors:
        g._latest[obj["id"]] = obj
        g._history[obj["id"]][obj["rev"]] = obj
        entry = {"seq": len(g._log) + 1, "op": "put", "id": obj["id"], "type": obj["type"],
                 "rev": obj["rev"], "hash": content_hash(obj), "actor": actor,
                 "prevHash": g._log[-1]["entryHash"] if g._log else GENESIS}
        entry["entryHash"] = content_hash(entry)
        g._log.append(entry)
    return g


def _authority(g):
    return [f for f in validate(g) if f.rule == "authority"]


def _agent(obj):
    return {**obj, "createdBy": A}


def _plan(**over):
    step = {"id": "primary", "evaluator": "mdl-1", "method": "mavt",
            "alternatives": ["alt-1"], "measures": ["m-1"], "weightSet": "ws-1",
            "authority": {"document": "DoDI 5000.84", "paragraph": "§3.1.c(2)"}}
    return _agent(base("pl-1", "Plan", episode="ep-1", policyBasis="pol-1", steps=[step],
                       **over))


def _episode(rev=1, **over):
    fields = dict(sequence=1, charter="ch-1", lifecycleState="DRAFT", transitions=[],
                  objectives=[], alternatives=[], groundRules=[], constraints=[],
                  assumptions=[], evidenceRegister=[], scenarios=[], claims=[], risks=[],
                  biasChecks=[], mandateElements=[], observations=[], weightSets=[],
                  models=[], runs=[], flipAnalyses=[], narratives=[], asOf="2026-09-04")
    fields.update(over)
    return {**_agent(base("ep-1", "DecisionEpisode", **fields)), "rev": rev}


def test_authority_catches_an_agent_authored_plan_approval():
    g = _seed(Graph(), (_plan(approvedBy={"actorId": "somebody", "date": "2026-09-04"}), A))
    findings = _authority(g)
    assert [f.objects for f in findings] == [("pl-1",)]
    assert findings[0].severity == "blocking" and "approve" in findings[0].message


def test_authority_is_silent_on_an_agent_authored_plan_with_no_approval():
    assert _authority(_seed(Graph(), (_plan(), A))) == []


def test_authority_catches_agent_authored_evidence_off_draft():
    ev = _agent(base("ev-1", "Evidence", title="t", evidenceType="Document", publisher="p",
                     published="2020", pointer={"uri": "u", "custodian": "c"},
                     classification={"level": "U", "metadataLevel": "U"},
                     scopeOfValidity={"builtToAnswer": "q", "questionClass": "other",
                                      "intendedUse": "u"},
                     reviewStatus="reviewed", reliabilitySteps=["drs-1"]))
    findings = _authority(_seed(Graph(), (ev, A)))
    assert [f.objects for f in findings] == [("ev-1",)]
    assert "reviewStatus" in findings[0].message and "reviewed" in findings[0].message


def test_authority_catches_an_agent_confirmed_gap():
    gap = _agent(base("gap-1", "InsufficientEvidence", sought="s", whereLookedFor=["a"],
                      whyNotFound="w", impact="degrading", indicatorsThatWouldResolve=[],
                      confirmedBy={"actorId": "somebody", "date": "2026-09-04"}))
    findings = _authority(_seed(Graph(), (gap, A)))
    assert [f.objects for f in findings] == [("gap-1",)]
    assert "confirm" in findings[0].message


def test_authority_catches_an_agent_exclusion_claiming_human_authority():
    ex = _agent(base("ex-1", "Exclusion",
                     target={"kind": "Alternative", "id": "alt-1", "label": "l"},
                     reasonType="out-of-scope", reason="r",
                     authority={"who": "a human", "role": "reviewer", "date": "2026-09-04"},
                     retainedInStructure=True))
    findings = _authority(_seed(Graph(), (ex, A)))
    assert [f.objects for f in findings] == [("ex-1",)]
    assert "agent-proposal" in findings[0].message


def test_authority_is_silent_on_a_properly_scoped_agent_proposal():
    ex = _agent(base("ex-1", "Exclusion",
                     target={"kind": "Alternative", "id": "alt-1", "label": "l"},
                     reasonType="out-of-scope", reason="r",
                     authority={"who": A["actorId"], "role": "agent-proposal",
                                "date": "2026-09-04"},
                     retainedInStructure=True))
    assert _authority(_seed(Graph(), (ex, A))) == []


def test_authority_catches_an_agent_created_episode_that_is_not_draft():
    findings = _authority(_seed(Graph(), (_episode(lifecycleState="MODEL_APPROVED"), A)))
    assert [f.objects for f in findings] == [("ep-1",)]
    assert "DRAFT" in findings[0].message


def test_authority_catches_an_agent_driven_lifecycle_move():
    g = _seed(Graph(),
              (_episode(rev=1), A),
              (_episode(rev=2, lifecycleState="MODEL_APPROVED"), A))
    findings = _authority(g)
    assert [f.objects for f in findings] == [("ep-1",)]
    assert "MODEL_APPROVED" in findings[0].message and "lifecycle edge" in findings[0].message


def test_authority_catches_an_agent_written_transition_record():
    record = {"from": "DRAFT", "to": "MODEL_APPROVED", "actor": dict(H), "at": "2026-09-04",
              "policyVersion": "0.1", "checksSatisfied": [], "checksUnsatisfied": [],
              "refused": False}
    g = _seed(Graph(), (_episode(rev=1), A), (_episode(rev=2, transitions=[record]), A))
    findings = _authority(g)
    assert [f.objects for f in findings] == [("ep-1",)]
    assert "transition history" in findings[0].message


def test_authority_is_silent_on_an_agent_revision_that_moves_nothing():
    """An agent *may* revise an episode — linking a narrative it just drafted, say — so
    long as the state and the transition history are untouched."""
    g = _seed(Graph(), (_episode(rev=1), A), (_episode(rev=2, narratives=["nar-1"]), A))
    assert _authority(g) == []


def test_authority_is_silent_on_a_human_doing_all_of_it():
    """Every one of the above, authored by a human, is simply the record working."""
    plan = {**_plan(approvedBy={"actorId": "t", "date": "2026-09-04"}), "createdBy": H}
    ep2 = {**_episode(rev=2, lifecycleState="MODEL_APPROVED"), "createdBy": H}
    ep1 = {**_episode(rev=1), "createdBy": H}
    assert _authority(_seed(Graph(), (plan, H), (ep1, H), (ep2, H))) == []


# ---- the same eight rules, re-derived from a SAVED store [T9 review C1/C2/I5/M1] ------
#
# The block above seeds a graph in memory. That is enough to exercise the rule, and not
# enough to prove the claim the task exists for: *a third party holding nothing but the
# saved directory can re-derive the boundary*. These round-trip through `Graph.save` and
# `Graph.load` — which verifies every object hash, the `prevHash` chain and the manifest
# — so each one is a forgery that a chain check cannot tell from an honest record, and is
# caught anyway, by authorship. One test per rule, plus the two cheaper forgeries the
# first review defeated the audit with (the log actor and the object's `createdBy` made
# to disagree; an `agent:` id declaring itself human).


def _saved(g, tmp_path, name="store"):
    """Save `g` and load it back — the store as a third party would receive it."""
    out = tmp_path / name
    g.save(out)
    return Graph.load(out)


def _saved_authority(g, tmp_path, name="store"):
    return _authority(_saved(g, tmp_path, name))


def _evidence(rev=1, actor=A, **over):
    fields = dict(title="t", evidenceType="Document", publisher="p", published="2020",
                  pointer={"uri": "u", "custodian": "c"},
                  classification={"level": "U", "metadataLevel": "U"},
                  scopeOfValidity={"builtToAnswer": "q", "questionClass": "other",
                                   "intendedUse": "u"},
                  reviewStatus="draft", reliabilitySteps=["drs-1"])
    fields.update(over)
    return {**base("ev-1", "Evidence", **fields), "createdBy": actor, "rev": rev}


def _exclusion(rev=1, actor=A, **over):
    fields = dict(target={"kind": "Alternative", "id": "alt-1", "label": "l"},
                  reasonType="out-of-scope", reason="r", retainedInStructure=True,
                  authority={"who": A["actorId"], "role": "agent-proposal",
                             "date": "2026-09-04"})
    fields.update(over)
    return {**base("ex-1", "Exclusion", **fields), "createdBy": actor, "rev": rev}


def test_saved_store_rule_1_an_agent_authored_forbidden_type(tmp_path):
    run = {**base("run-1", "EvaluationRun", plan="pl-1", step="primary", evaluator="mdl-1",
                  evaluatorVersion="1", method="mavt", inputsHash="0" * 64,
                  parameterBindings={"weightSet": "ws-1", "weights": {"m-1": 1.0},
                                     "observationIds": ["ob-1"]},
                  seed=1, kernelVersion="0.1.0", outputs=[], outputHashes=[],
                  runRecordHash="0" * 64, startedAt="2026-09-04", finishedAt="2026-09-04"),
           "createdBy": A}
    findings = _saved_authority(_seed(Graph(), (run, A)), tmp_path)
    assert [f.objects for f in findings] == [("run-1",)]
    assert "agents may not author EvaluationRun" in findings[0].message


def test_saved_store_rule_2_an_agent_approved_plan_survives_being_superseded(tmp_path):
    """The head-only audit\'s blind spot, now closed [T9 review C2].

    An agent writes `pl-1@1` carrying an approval; a human writes an honest `pl-1@2` over
    the top. The head revision is clean and the record still contains an approval no human
    ever gave — the audit reads every revision, so it says so.
    """
    approved = _plan(approvedBy={"actorId": "somebody", "date": "2026-09-04"})
    honest = {**approved, "rev": 2, "createdBy": H}
    findings = _saved_authority(_seed(Graph(), (approved, A), (honest, H)), tmp_path)
    assert [f.objects for f in findings] == [("pl-1",)]
    assert "only a human may approve a plan" in findings[0].message


def test_saved_store_rule_3_agent_authored_evidence_off_draft(tmp_path):
    findings = _saved_authority(_seed(Graph(), (_evidence(reviewStatus="reviewed"), A)),
                                tmp_path)
    assert [f.objects for f in findings] == [("ev-1",)]
    assert "only write draft evidence" in findings[0].message


def test_saved_store_rule_4_an_agent_downgrades_reviewed_evidence_to_draft(tmp_path):
    """The forgery the first audit was silent on: rule 3 sees nothing, because the
    revision the agent lands on says `draft` and that is exactly what an agent is allowed
    to write. Only the predecessor gives it away."""
    reviewed = _evidence(actor=H, reviewStatus="reviewed")
    downgraded = _evidence(rev=2, actor=A, reviewStatus="draft")
    findings = _saved_authority(_seed(Graph(), (reviewed, H), (downgraded, A)), tmp_path)
    assert [f.objects for f in findings] == [("ev-1",)]
    assert "revised evidence a human had marked 'reviewed'" in findings[0].message


def test_saved_store_rule_5_an_agent_confirmed_gap(tmp_path):
    gap = {**base("gap-1", "InsufficientEvidence", sought="s", whereLookedFor=["a"],
                  whyNotFound="w", impact="degrading", indicatorsThatWouldResolve=[],
                  confirmedBy={"actorId": "somebody", "date": "2026-09-04"}),
           "createdBy": A}
    findings = _saved_authority(_seed(Graph(), (gap, A)), tmp_path)
    assert [f.objects for f in findings] == [("gap-1",)]
    assert "only a human may confirm" in findings[0].message


def test_saved_store_rule_6_an_agent_exclusion_claiming_human_authority(tmp_path):
    ex = _exclusion(authority={"who": "a human", "role": "reviewer", "date": "2026-09-04"})
    findings = _saved_authority(_seed(Graph(), (ex, A)), tmp_path)
    assert [f.objects for f in findings] == [("ex-1",)]
    assert "agent-proposal" in findings[0].message


def test_saved_store_rule_6_an_agent_takes_over_a_human_exclusion(tmp_path):
    """The second forgery the first audit was silent on. The agent relabels a human\'s
    exclusion as its own well-formed proposal, so the head revision passes rule 6 on its
    own terms; the human authority it overwrote is only visible in the predecessor."""
    human_authored = _exclusion(
        actor=H, authority={"who": "Congressional Budget Office", "role": "analyst",
                            "date": "2013-04"})
    taken_over = _exclusion(rev=2, actor=A)  # its own tidy agent-proposal
    findings = _saved_authority(_seed(Graph(), (human_authored, H), (taken_over, A)),
                                tmp_path)
    assert [f.objects for f in findings] == [("ex-1",)]
    assert "human-authorised omission is not the agent's to restate" in findings[0].message


def test_saved_store_rule_6_one_agent_may_not_revise_another_agents_proposal(tmp_path):
    other = {"actorType": "agent", "actorId": "agent:other"}
    mine = _exclusion(actor=A)
    theirs = {**_exclusion(rev=2, actor=other),
              "authority": {"who": other["actorId"], "role": "agent-proposal",
                            "date": "2026-09-04"}}
    findings = _saved_authority(_seed(Graph(), (mine, A), (theirs, other)), tmp_path)
    assert [f.objects for f in findings] == [("ex-1",)]
    assert "proposal's authorship is as protected as its content" in findings[0].message


def test_saved_store_rule_7_an_agent_driven_lifecycle_move(tmp_path):
    g = _seed(Graph(), (_episode(rev=1), A),
              (_episode(rev=2, lifecycleState="MODEL_APPROVED"), A))
    findings = _saved_authority(g, tmp_path)
    assert [f.objects for f in findings] == [("ep-1",)]
    assert "lifecycle edge" in findings[0].message


def test_saved_store_rule_8_an_agent_rewrote_the_transition_history(tmp_path):
    record = {"from": "DRAFT", "to": "MODEL_APPROVED", "actor": dict(H), "at": "2026-09-04",
              "policyVersion": "0.1", "checksSatisfied": [], "checksUnsatisfied": [],
              "refused": False}
    g = _seed(Graph(), (_episode(rev=1), A), (_episode(rev=2, transitions=[record]), A))
    findings = _saved_authority(g, tmp_path)
    assert [f.objects for f in findings] == [("ep-1",)]
    assert "rewrote this episode's transition history" in findings[0].message


def test_saved_store_a_log_actor_that_disagrees_with_created_by_is_named(tmp_path):
    """[T9 review I5] The cheapest forgery of all: leave the object openly saying an agent
    wrote it and edit one word in one log line. `Graph.load` verifies the object hash
    against the entry, but the entry\'s actor is not part of the object, so the store
    loads. Both halves are reported — the disagreement, and the rule the agent broke."""
    g = _seed(Graph(), (_episode(rev=1), A),
              (_episode(rev=2, lifecycleState="MODEL_APPROVED"), A))
    g._log[-1]["actor"] = dict(H)  # the object still says A
    g._log[-1]["entryHash"] = content_hash(
        {k: v for k, v in g._log[-1].items() if k != "entryHash"})

    findings = _saved_authority(g, tmp_path)
    messages = " | ".join(f.message for f in findings)
    assert "log entry for ep-1@2 names actor 't' ('human')" in messages
    assert "written by 'agent:test' ('agent')" in messages
    assert "lifecycle edge" in messages, "the rule itself must still fire"


def test_saved_store_a_log_actor_naming_an_agent_over_a_human_object_is_named(tmp_path):
    """The mirror image: the log says agent, the object says human. Audited as an agent
    either way — the rule fails toward the actor class with fewer permissions."""
    ep1 = {**_episode(rev=1), "createdBy": H}
    ep2 = {**_episode(rev=2, lifecycleState="MODEL_APPROVED"), "createdBy": H}
    g = _seed(Graph(), (ep1, H), (ep2, A))

    findings = _saved_authority(g, tmp_path)
    messages = " | ".join(f.message for f in findings)
    assert "log entry for ep-1@2 names actor 'agent:test' ('agent')" in messages
    assert "lifecycle edge" in messages


def test_saved_store_an_agent_id_declaring_itself_human_is_malformed(tmp_path):
    """[T9 review M1] `{"actorType": "human", "actorId": "agent:liar"}` used to be a human
    everywhere in the kernel. `Graph.put` refuses it now; this is what a store that got
    one past the write path looks like to an auditor."""
    liar = {"actorType": "human", "actorId": "agent:liar"}
    plan = {**_plan(approvedBy={"actorId": "somebody", "date": "2026-09-04"}),
            "createdBy": liar}
    findings = _saved_authority(_seed(Graph(), (plan, liar)), tmp_path)
    messages = " | ".join(f.message for f in findings)
    assert "createdBy is malformed" in messages
    assert "an actorId beginning 'agent:' is an agent" in messages
    assert "only a human may approve a plan" in messages, (
        "the liar must also be held to the agent rules"
    )


def test_saved_store_an_agent_hiding_behind_an_unprefixed_id_is_malformed(tmp_path):
    """The other direction. An agent whose id does not begin `agent:` is malformed too —
    otherwise the convention the audit indexes authorship by is optional."""
    hidden = {"actorType": "agent", "actorId": "helpful-assistant"}
    findings = _saved_authority(_seed(Graph(), ({**_plan(), "createdBy": hidden}, hidden)),
                                tmp_path)
    messages = " | ".join(f.message for f in findings)
    assert "an agent's actorId must begin 'agent:'" in messages


def test_saved_store_an_honest_record_produces_nothing(tmp_path):
    """The baseline. Every forgery above is measured against this: the same objects,
    written by the actors entitled to write them, round-tripped the same way."""
    plan = {**_plan(approvedBy={"actorId": "t", "date": "2026-09-04"}), "createdBy": H}
    ep1 = {**_episode(rev=1), "createdBy": H}
    ep2 = {**_episode(rev=2, lifecycleState="MODEL_APPROVED"), "createdBy": H}
    g = _seed(Graph(), (plan, H), (ep1, H), (ep2, H),
              (_evidence(actor=A), A), (_exclusion(actor=A), A))
    assert _saved_authority(g, tmp_path) == []


# ---- run-seal: the sealed run still hashes to what it says it does -------------------


def _sealed_graph():
    """A two-alternative graph with one sealed run, built through the kernel."""
    from docket.kernel.evaluate import evaluate
    from tests.kernel.conftest import alternative, plan_approved
    from tests.kernel.conftest import eval_measure as measure
    from tests.kernel.conftest import eval_model as model
    from tests.kernel.conftest import eval_observation as observation
    from tests.kernel.conftest import obj as cobj
    from tests.kernel.conftest import put_all as cput
    from tests.kernel.test_evaluate import _fresh_base_graph

    g = _fresh_base_graph()
    cput(
        g,
        cobj("ex-crit", "Exclusion", target={"kind": "Measure", "label": "thresholds"},
             reasonType="data-unavailable", reason="none published",
             authority={"who": "w", "role": "r", "date": "2013"}, retainedInStructure=True),
        cobj("gap-v", "InsufficientEvidence", sought="s", whereLookedFor=["x"], whyNotFound="w",
             impact="informational", indicatorsThatWouldResolve=[],
             confirmedBy={"actorId": "fixture", "date": "2026"}),
        cobj("obj-1", "Objective", name="o", priority="primary", provenance="ev-doc",
             measures=["m-a"]),
        measure("m-a"), model(),
        alternative("alt-x", order=1), alternative("alt-y", baseline=True, order=2),
        observation("ob-xa", "alt-x", "m-a", 10), observation("ob-ya", "alt-y", "m-a", 4),
        cobj("ws-1", "WeightSet", name="w", method="stated", weights={"m-a": 1.0},
             provenance="ev-doc"),
        cobj("pl-1", "Plan", episode="ep-1", policyBasis="pol-1",
             approvedBy={"actorId": "fixture", "date": "2026"},
             steps=[{"id": "s1", "evaluator": "mdl-1", "method": "mavt",
                     "alternatives": ["alt-x", "alt-y"], "measures": ["m-a"],
                     "weightSet": "ws-1",
                     "authority": {"document": "DoDI 5000.84", "paragraph": "§4.2.i"}}]),
        {**g.get("ep-1"), "rev": 2, **plan_approved(), "alternatives": ["alt-x", "alt-y"],
         "observations": ["ob-xa", "ob-ya"], "weightSets": ["ws-1"], "models": ["mdl-1"],
         "plan": "pl-1", "objectives": ["obj-1"]},
    )
    run = evaluate(g, "pl-1", seed=1, now="2026-09-04T00:00:00Z")[0]
    return g, run


def _seal_findings(g):
    return [f for f in validate(g) if f.rule == "run-seal"]


def test_run_seal_is_silent_on_a_clean_kernel_written_run():
    from tests.kernel.conftest import assert_history_honest

    g, _ = _sealed_graph()
    assert_history_honest(g)
    assert _seal_findings(g) == []


def test_run_seal_catches_a_human_revision_of_a_sealed_run():
    """A human rewriting `ranking` after sealing keeps the stale rev-1 runRecordHash. The
    store accepts the revision — it is append-only, not immutable — so the audit has to
    be able to say so from the saved store alone."""
    g, run = _sealed_graph()
    stored = g.get(run["id"])
    g.put({**stored, "rev": 2, "createdBy": H, "ranking": list(reversed(stored["ranking"]))}, H)
    findings = _seal_findings(g)
    assert findings and all(f.severity == "blocking" for f in findings)
    assert all(f.objects == (run["id"],) for f in findings)
    messages = " ".join(f.message for f in findings)
    assert "immutable" in messages and "runRecordHash" in messages


def test_run_seal_catches_a_human_revision_of_a_sealed_result():
    g, run = _sealed_graph()
    res_id = run["outputs"][0]
    res = g.get(res_id)
    g.put({**res, "rev": 2, "createdBy": H, "value": res["value"] + 1}, H)
    findings = _seal_findings(g)
    # Both the Result's own immutability breach and the run's outputHash mismatch.
    assert any("immutable" in f.message and res_id in f.objects for f in findings)
    assert any("outputHash" in f.message and f.objects == (run["id"], res_id)
               for f in findings)


def test_run_seal_catches_an_edited_output_hash_list():
    """`outputHashes` edited by hand: the store will only take it as a new revision, so
    the rev-1 immutability finding fires too — but the hash mismatch must be named
    independently, because a store loaded from disk carries no revision history the
    auditor has to trust."""
    g, run = _sealed_graph()
    stored = g.get(run["id"])
    bad = list(stored["outputHashes"])
    bad[0] = "0" * 64
    g.put({**stored, "rev": 2, "createdBy": H, "outputHashes": bad}, H)
    findings = _seal_findings(g)
    assert any("outputHash" in f.message for f in findings)


def test_run_seal_reports_a_missing_output_object_rather_than_raising():
    g, run = _sealed_graph()
    stored = g.get(run["id"])
    hand_edited = {**stored, "outputs": stored["outputs"] + ["res-not-written"],
                   "outputHashes": stored["outputHashes"] + ["0" * 64]}
    g._latest[stored["id"]] = hand_edited
    g._history[stored["id"]][hand_edited["rev"]] = hand_edited
    findings = _seal_findings(g)
    assert any("is not in the graph" in f.message for f in findings)


def test_run_seal_tolerates_a_garbage_run():
    """A run with none of the fields the rule reads must yield findings, not a KeyError."""
    g = Graph()
    junk = base("run-junk", "EvaluationRun")
    g._latest["run-junk"] = junk
    g._history["run-junk"][1] = junk
    findings = [f for f in validate(g) if f.rule == "run-seal"]
    assert findings and all(f.objects == ("run-junk",) for f in findings)


def test_run_seal_warns_when_a_bound_input_was_revised_after_sealing():
    """A run whose inputs moved underneath it is stale, not dishonest: its own seal still
    verifies and it still records truthfully what it computed. That is a warning — re-run
    before relying on it — rather than a blocking integrity breach."""
    g, run = _sealed_graph()
    ob = g.get("ob-xa")
    g.put({**ob, "rev": ob["rev"] + 1, "createdBy": H, "value": 11}, H)
    findings = validate(g)
    changed = [f for f in findings if f.rule == "run-inputs-changed"]
    assert changed and changed[0].severity == "warning"
    assert changed[0].objects == (run["id"],)
    assert [f for f in findings if f.rule == "run-seal"] == []


def test_run_seal_is_silent_on_inputs_that_have_not_moved():
    g, _ = _sealed_graph()
    assert [f for f in validate(g) if f.rule == "run-inputs-changed"] == []


def test_run_seal_reports_a_run_whose_inputs_cannot_be_recomputed():
    """Malformed bindings must produce a finding, never an exception out of validate()."""
    g, run = _sealed_graph()
    stored = g.get(run["id"])
    hand_edited = {**stored,
                   "parameterBindings": {**stored["parameterBindings"],
                                         "observationIds": ["ob-never-written"]}}
    g._latest[stored["id"]] = hand_edited
    g._history[stored["id"]][hand_edited["rev"]] = hand_edited
    findings = validate(g)  # must not raise
    assert any(f.rule == "run-seal" and "cannot be recomputed" in f.message
               and f.severity == "blocking" for f in findings)


def test_every_rule_name_the_kernel_emits_is_declared_in_known_rules():
    """`KNOWN_RULES` is what makes a mistyped `Policy.blockingRules` entry detectable
    (`readiness.check_blocking_rules_known`), so it has to be the whole list. Derived
    from the `Finding("<rule>", "<severity>"` call sites rather than kept in step by
    hand, and asserted both ways: a rule added without declaring it fails here, and so
    does a declared name nothing emits.
    """
    kernel = Path(docket.kernel.validate.__file__).parent
    call = re.compile(r'Finding\(\s*"([^"]+)",\s*"(?:blocking|warning|info)"')
    emitted = {m.group(1) for path in sorted(kernel.rglob("*.py"))
               for m in call.finditer(path.read_text())}
    assert len(emitted) > 40, "no Finding calls found — the probe itself is broken"
    assert emitted - KNOWN_RULES == set(), "rules the kernel emits but KNOWN_RULES omits"
    assert KNOWN_RULES - emitted == set(), "names in KNOWN_RULES no kernel rule emits"


def test_kernel_modules_import_cleanly_in_every_order():
    """`orphan_gaps` lives in `validate`; `lifecycle` re-exports it and `policy_rules`
    imports it from there, and `validate._ensure_policy_rules` imports `policy_rules`
    lazily to keep `validate -> policy_rules -> lifecycle -> validate` from being a
    real load-time cycle. That only actually proves out if none of the three cares
    which of it or its neighbours a caller happens to import first — and the only way
    to see "first" is a process that has never imported any of them, since a second
    import within one process just hits `sys.modules` and tells you nothing. Every
    permutation is run in its own subprocess for exactly that reason.
    """
    modules = ["docket.kernel.policy_rules", "docket.kernel.lifecycle", "docket.kernel.validate"]
    for order in itertools.permutations(modules):
        code = "\n".join(f"import {m}" for m in order)
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
        )
        assert result.returncode == 0, f"import order {order} failed:\n{result.stderr}"
