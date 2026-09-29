# tests/agent/test_authority_e2e.py
"""The agent authority boundary, end to end (plan 04 Task 9; design §8.7).

Five things an agent actor is not permitted to do, attempted one after another against a
single Demo A-shaped record, then an audit of everything that record holds afterwards.
The point of doing them in one sitting rather than five isolated fixtures is the audit at
the end: after five refusals the store must be *exactly* what a record with no agent
writes in it looks like, and its hash chain must still verify.

Nothing here reaches the network. `RecordedBackend` is the only backend a test may build
[ruling R9], and the one recorded case used here (`narrate-fabricated.json`) is already
committed — no new recording was made for this file.

What each refusal is:

* (a) an `EvaluationRun` written by the agent — `AGENT_FORBIDDEN_TYPES`, refused by
  `Graph._check_agent_authority` before the object reaches the log.
* (b) an agent driving `MODEL_APPROVED`, a human-only edge. Two paths could refuse this
  and the brief accepts either: `kernel.lifecycle.transition` builds the record first and
  hands it to `Graph.put`, so the *store* refuses (`AuthorityViolation`, "agent may not
  write transitions") before the gate's own `human-actor` check can turn into a
  `TransitionRefused`. Which one fires is recorded in the task report; the assertion that
  matters either way is that the state did not move and nothing was written.
* (c) a `Commitment` written by the agent — the signature object. Same mechanism as (a).
* (d) `narrate` with a recorded response that states a numeral no cited object holds.
  `kernel.render.check_citations` is what decides, and the agent's draft is thrown away.
* (e) `dispatch` against a plan no human has approved — G2, refused in
  `agent/dispatch.py` before the kernel is called at all.

`test_f_*` is the whole-store audit those five build up to. Everything after it is the
other half of the claim [ruling R14]: the boundary has to hold against a **hand-edited**
store as well as against the write path, because the log is unkeyed and a forger can
re-chain it perfectly. `forge()` does exactly that, and one test per agent rule confirms
the forged store *loads* — the chain, the hashes and the manifest all agree — and is
caught anyway, by authorship, in `kernel.validate.rule_authority`.

Two sections follow, both added in the T9 rework round:

* `test_blast_radius_*` — what a forgery costs, asserted as behaviour rather than as set
  membership. Every lifecycle target but `VOID` consults `WHOLE_STORE_RULES`, and so does
  `kernel.evaluate.evaluate`, so one forged authorship line on an object an episode never
  reaches shuts G1, refuses the computation and makes a regenerated `ReadinessReport`
  not-ready — while the *stored* report, which the forger leaves alone, still says ready.
* `test_defeat_*` — the twenty-one defeat attempts the T9 review tabled, re-run with each
  row's expected outcome pinned. Eleven of them got through the first time. The ones that
  are inherent (an agent process presenting a real human's actor dict; prose the store
  does not parse) are written down as inherent, with the control that does cover them
  named, so nobody re-discovers them and files them as a regression.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from docket import KERNEL_VERSION
from docket.agent.backend import RecordedBackend
from docket.agent.dispatch import dispatch
from docket.agent.narrate import narrate
from docket.canon import canonical_json, content_hash
from docket.errors import AuthorityViolation, TransitionRefused, UncitedSentenceError
from docket.kernel.lifecycle import EDGES, HUMAN_ONLY, KERNEL_ONLY, transition
from docket.kernel.validate import rule_authority, rule_log_chain, validate
from docket.objects import AGENT_FORBIDDEN_TYPES
from docket.store import GENESIS, Graph

A = {"actorType": "agent", "actorId": "agent:recorded"}
H = {"actorType": "human", "actorId": "shreyash"}
NOW = "2013-04-30T00:00:00Z"
EPISODE = "ep-cbo-2013"
PLAN = "pl-cbo"
SECTION = "evaluation-results"

FIXTURES = Path(__file__).parents[1] / "fixtures" / "recorded"

# The ids the agent tries to mint. None of them may exist afterwards.
FORGED_RUN = "run-agent-forged"
FORGED_COMMITMENT = "cmt-agent-forged"


def _attempt(fn):
    """Call `fn` and hand back the exception it raised, or `None` if it did not raise.

    A boundary that lets something through does not raise, and `None` makes that read as
    the failure it is in whichever test asserts on it — rather than the fixture itself
    blowing up somewhere the message would be less clear.
    """
    try:
        fn()
    except Exception as exc:  # broad on purpose: the test, not the fixture, asserts the type
        return exc
    return None


@pytest.fixture(scope="module")
def demo_a_graph_dir(tmp_path_factory):
    """Run Demo A once for this module, into a temp dir — never into `demos/*/out`."""
    from demos.a_cbo_gcv_2013.run import run

    d = tmp_path_factory.mktemp("demo-a-authority")
    run(d)
    return d / "graph"


@pytest.fixture(scope="module")
def boundary(demo_a_graph_dir):
    """Attempt (a)–(e) in order against one graph; return the graph and what happened.

    Module-scoped and read-only from here on: every test below asserts against the same
    post-refusal store, which is what makes `test_f_*`'s "after all of the above" real
    rather than five independent single-refusal snapshots.

    Order is deliberate. (a)–(c) write nothing at all, so (d)'s recorded prompt still
    hashes to the committed fixture key. (e) needs one *legitimate human* revision of the
    plan first — Demo A ships `pl-cbo` already approved, and this drops the approval the
    same way `tests/agent/test_plan.py::demo_a_draft` does — so it goes last.
    """
    g = Graph.load(demo_a_graph_dir)
    ep_before = g.get(EPISODE)
    out: dict = {
        "graph": g,
        "state_before": ep_before["lifecycleState"],
        "transitions_before": ep_before["transitions"],
        "log_at_start": len(g.log()),
    }

    # (a) an EvaluationRun. Copied from a real sealed run so it is schema-valid: the type
    # check must be what refuses it, not a missing field.
    real_run = g.get(g.get(EPISODE)["runs"][0])
    forged_run = {**real_run, "id": FORGED_RUN, "rev": 1, "createdBy": A, "createdAt": NOW}
    out["log_before_a"] = len(g.log())
    out["a"] = _attempt(lambda: g.put(forged_run, A))
    out["log_after_a"] = len(g.log())

    # (b) a human-only lifecycle edge.
    out["log_before_b"] = len(g.log())
    out["b"] = _attempt(lambda: transition(g, EPISODE, "MODEL_APPROVED", A, now=NOW))
    out["log_after_b"] = len(g.log())

    # (c) a Commitment — the object a signature lives in.
    forged_commitment = {
        "id": FORGED_COMMITMENT, "type": "Commitment", "rev": 1,
        "createdBy": A, "createdAt": NOW,
        "episode": EPISODE, "selected": "alt-puma",
        "signer": {"identity": "a name the agent chose", "role": "decision authority"},
        "signedAt": NOW, "conditions": [], "stopRules": [], "packageHash": "0" * 64,
    }
    out["log_before_c"] = len(g.log())
    out["c"] = _attempt(lambda: g.put(forged_commitment, A))
    out["log_after_c"] = len(g.log())

    # (d) a narrative sentence carrying a numeral no cited object holds. Every retry
    # prompt has its own recorded (still fabricated) response in the committed fixture
    # [pre-flight defect 11], so this exhausts the retries rather than dying of a missing
    # recording.
    backend = RecordedBackend(FIXTURES / "narrate-fabricated.json")
    out["log_before_d"] = len(g.log())
    out["d"] = _attempt(
        lambda: narrate(g, EPISODE, section=SECTION, backend=backend, actor=A, now=NOW)
    )
    out["log_after_d"] = len(g.log())
    out["d_backend_calls"] = len(backend.calls)

    # (e) dispatch against an unapproved plan. The approval is dropped by a human, which
    # is a legitimate write and the only thing in this fixture that changes the store.
    plan = g.get(PLAN)
    unapproved = {k: v for k, v in plan.items() if k != "approvedBy"}
    unapproved["rev"] = plan["rev"] + 1
    unapproved["createdBy"] = H
    unapproved["createdAt"] = NOW
    g.put(unapproved, H)
    out["log_before_e"] = len(g.log())
    out["e"] = _attempt(lambda: dispatch(g, PLAN, actor=A, seed=20130430, now=NOW))
    out["log_after_e"] = len(g.log())

    return out


# --- (a) the agent may not author a computed object --------------------------------


def test_a_the_agent_may_not_write_an_evaluation_run(boundary):
    exc = boundary["a"]
    assert isinstance(exc, AuthorityViolation), f"expected AuthorityViolation, got {exc!r}"
    assert "EvaluationRun" in str(exc)
    assert not boundary["graph"].has(FORGED_RUN)
    assert boundary["log_after_a"] == boundary["log_before_a"], "a refusal writes nothing"


# --- (b) the agent may not drive a human-only edge ----------------------------------


def test_b_the_agent_may_not_drive_the_human_only_model_approved_edge(boundary):
    """Either refusal is acceptable; the state not moving is not negotiable."""
    exc = boundary["b"]
    assert isinstance(exc, AuthorityViolation | TransitionRefused), (
        f"expected AuthorityViolation or TransitionRefused, got {exc!r}"
    )
    if isinstance(exc, TransitionRefused):
        # The gate refused it: "human-actor" must be among the named unsatisfied checks,
        # and the gate persists a refusal record naming who tried.
        assert "human-actor" in exc.unsatisfied
        record = boundary["graph"].get(EPISODE)["transitions"][-1]
        assert record["refused"] is True
        assert record["actor"] == A
        assert "human-actor" in record["checksUnsatisfied"]
    else:
        # The store refused it first, so the gate never got to write its record. Nothing
        # at all was appended.
        assert boundary["log_after_b"] == boundary["log_before_b"]
        assert boundary["graph"].get(EPISODE)["transitions"] == boundary["transitions_before"]

    assert boundary["graph"].get(EPISODE)["lifecycleState"] == boundary["state_before"]


def test_b_the_refusal_is_not_the_edge_rule_wearing_the_authority_rule_s_coat():
    """On a DRAFT episode, `DRAFT -> MODEL_APPROVED` is a legal edge and G1's checks are
    the only thing between a human and the transition. The agent is still refused — so
    what stops it is the actor, not the shape of the graph."""
    from demos.a_cbo_gcv_2013.build import build

    g = build()
    assert g.get(EPISODE)["lifecycleState"] == "DRAFT"
    assert "MODEL_APPROVED" in EDGES["DRAFT"]
    before = len(g.log())

    exc = _attempt(lambda: transition(g, EPISODE, "MODEL_APPROVED", A, now=NOW))

    assert isinstance(exc, AuthorityViolation | TransitionRefused), repr(exc)
    assert g.get(EPISODE)["lifecycleState"] == "DRAFT"
    assert len(g.log()) == before


def test_a_refused_human_attempt_is_written_down_which_is_why_the_agent_s_absence_matters():
    """The contrast that makes (b)'s "nothing was written" meaningful.

    `transition` records refusals — a human who tries an edge the gate will not allow
    leaves a `refused: true` record naming them. The agent leaves nothing, because the
    store stops it before the gate can write anything. So "no agent refusal record" is
    not the gate being quiet; it is the write path refusing earlier than the gate.
    """
    from demos.a_cbo_gcv_2013.build import build

    g = build()
    before = len(g.log())
    with pytest.raises(TransitionRefused) as exc:
        transition(g, EPISODE, "SIGNED", H, now=NOW)
    assert "edge-DRAFT-to-SIGNED" in exc.value.unsatisfied
    assert len(g.log()) == before + 1
    record = g.get(EPISODE)["transitions"][-1]
    assert record["refused"] is True and record["actor"] == H
    assert g.get(EPISODE)["lifecycleState"] == "DRAFT"


# --- (c) the agent may not sign --------------------------------------------------


def test_c_the_agent_may_not_write_a_commitment(boundary):
    exc = boundary["c"]
    assert isinstance(exc, AuthorityViolation), f"expected AuthorityViolation, got {exc!r}"
    assert "Commitment" in str(exc)
    assert not boundary["graph"].has(FORGED_COMMITMENT)
    assert boundary["log_after_c"] == boundary["log_before_c"]


# --- (d) the agent may not state a number nothing backs --------------------------


def test_d_a_fabricated_numeral_is_refused_and_nothing_is_written(boundary):
    exc = boundary["d"]
    assert isinstance(exc, UncitedSentenceError), f"expected UncitedSentenceError, got {exc!r}"
    # the structured attributes, so a caller need not parse the message string
    assert exc.narrative_id, "the refusal must name the candidate Narrative"
    assert exc.sentence, "the refusal must name the offending sentence"
    assert exc.sentence in str(exc)
    assert boundary["d_backend_calls"] == 3, "one draft plus two retries, all fabricated"
    assert not boundary["graph"].has(exc.narrative_id), "the rejected draft is not stored"
    assert boundary["log_after_d"] == boundary["log_before_d"], (
        "a rejected narrative writes nothing at all, not even a partial draft"
    )
    assert exc.narrative_id not in boundary["graph"].get(EPISODE)["narratives"]


# --- (e) the agent may not compute against an unapproved plan --------------------


def test_e_the_agent_may_not_dispatch_an_unapproved_plan(boundary):
    """Refused by `agent/dispatch.py`'s own G2 check, which runs before the kernel is
    called — so no `EvaluationRun` is minted and the error names the gate, not a schema
    field. (`kernel.evaluate` refuses the same plan on its own account [ruling R12]; this
    path simply gets there first and says so more clearly.)"""
    exc = boundary["e"]
    assert isinstance(exc, AuthorityViolation), f"expected AuthorityViolation, got {exc!r}"
    assert "G2" in str(exc) and "approv" in str(exc)
    assert boundary["log_after_e"] == boundary["log_before_e"]


def test_e_the_kernel_refuses_the_same_plan_even_when_dispatch_is_bypassed(boundary):
    """The gate is not decoration on the agent path: calling the kernel directly, as
    `docket evaluate` or any script would, is refused too."""
    from docket.errors import ValidationError
    from docket.kernel.evaluate import evaluate

    g = boundary["graph"]
    before = len(g.log())
    exc = _attempt(lambda: evaluate(g, PLAN, seed=20130430, now=NOW))
    assert isinstance(exc, ValidationError), f"the kernel let an unapproved plan through: {exc!r}"
    assert "G2" in str(exc)
    assert len(g.log()) == before


# --- the rest of the write-path boundary, in process -------------------------------


def _probe_objects(g) -> dict[str, dict]:
    """One schema-valid probe object per `AGENT_FORBIDDEN_TYPES` type, re-authored as the
    agent under a fresh id.

    Eight of the ten types are already in Demo A's record and are copied from the real
    stored object, so the *type* rule is what refuses each probe rather than a missing
    field. `Commitment` and `EpisodeDiff` are not in Demo A (it stops at
    `PENDING_SIGNATURE` and has one episode), so they are built here.
    """
    probes: dict[str, dict] = {}
    for o in g.all():
        t = o["type"]
        if t in AGENT_FORBIDDEN_TYPES and t not in probes:
            probes[t] = {**o, "id": f"probe-{t.lower()}", "rev": 1,
                         "createdBy": A, "createdAt": NOW}
    probes["Commitment"] = {
        "id": "probe-commitment", "type": "Commitment", "rev": 1, "createdBy": A,
        "createdAt": NOW, "episode": EPISODE, "selected": "alt-puma",
        "signer": {"identity": "a name the agent chose", "role": "decision authority"},
        "signedAt": NOW, "conditions": [], "stopRules": [], "packageHash": "0" * 64,
    }
    probes["EpisodeDiff"] = {
        "id": "probe-episodediff", "type": "EpisodeDiff", "rev": 1, "createdBy": A,
        "createdAt": NOW, "from": EPISODE, "to": EPISODE, "because": "rt-none",
        "changed": [], "added": [], "removed": [], "judgmentsChanged": [],
        "judgmentsConsistent": [], "ratingsChanged": [], "rankingBefore": [],
        "rankingAfter": [], "pairing": "unknown", "kernelVersion": "0.1.0",
    }
    return probes


def test_every_forbidden_type_is_refused_to_the_agent_not_only_the_two_in_the_brief(boundary):
    """`AGENT_FORBIDDEN_TYPES` is read from the catalogue, so a type added to the boundary
    later is exercised here without an edit — and the assertion at the end proves the loop
    actually covered all ten rather than silently skipping some."""
    g = boundary["graph"]
    probes = _probe_objects(g)
    assert set(probes) == set(AGENT_FORBIDDEN_TYPES), (
        f"probe set does not cover the boundary: missing "
        f"{sorted(set(AGENT_FORBIDDEN_TYPES) - set(probes))}"
    )
    before = len(g.log())
    for t, probe in sorted(probes.items()):
        exc = _attempt(lambda p=probe: g.put(p, A))
        assert isinstance(exc, AuthorityViolation), f"{t}: expected AuthorityViolation, {exc!r}"
        assert t in str(exc)
        assert not g.has(probe["id"])
    assert len(g.log()) == before, "ten refusals, nothing written"


def test_the_agent_may_not_approve_a_plan_or_take_any_g1_human_action(boundary):
    """The four functions that carry a human's decision refuse a non-human actor by name,
    before the graph is touched — so a partial write is impossible even where the action
    would have written several objects."""
    from docket.agent.plan import approve_plan
    from docket.agent.review import accept, confirm_gaps, reject

    g = boundary["graph"]
    before = len(g.log())
    attempts = {
        "approve_plan": lambda: approve_plan(g, PLAN, A, now=NOW),
        "confirm_gaps": lambda: confirm_gaps(g, EPISODE, A, now=NOW),
        "accept": lambda: accept(g, "ch-gcv-2013", A, now=NOW),
        "reject": lambda: reject(g, "alt-namer", A, now=NOW, reason="r",
                                 reason_type="out-of-scope", episode_id=EPISODE),
    }
    for name, fn in attempts.items():
        exc = _attempt(fn)
        assert isinstance(exc, AuthorityViolation), f"{name}: expected AuthorityViolation, {exc!r}"
    assert len(g.log()) == before, "four refusals, nothing written"


# --- (f) the whole store, after all five ------------------------------------------


def _agent_authored_forbidden(objects: list[dict], log: list[dict]) -> list[tuple[str, str]]:
    """Every `(id, type)` in `objects` or `log` that an agent actor authored and may not.

    Reads `AGENT_FORBIDDEN_TYPES` from the catalogue rather than restating the list, so a
    type added to the boundary later is audited here without an edit.
    """
    out: set[tuple[str, str]] = set()
    for o in objects:
        author = o.get("createdBy")
        if o.get("type") in AGENT_FORBIDDEN_TYPES and isinstance(author, dict) \
                and author.get("actorType") == "agent":
            out.add((o.get("id"), o.get("type")))
    for e in log:
        actor = e.get("actor")
        if e.get("type") in AGENT_FORBIDDEN_TYPES and isinstance(actor, dict) \
                and actor.get("actorType") == "agent":
            out.add((e.get("id"), e.get("type")))
    return sorted(out)


def test_f_the_log_holds_no_agent_authored_object_of_a_forbidden_type(boundary):
    g = boundary["graph"]
    assert _agent_authored_forbidden(g.all(), g.log()) == []
    # the same audit as the kernel runs it, from the store rather than the write path
    assert rule_authority(g) == []
    # neither forged id ever landed
    assert not g.has(FORGED_RUN) and not g.has(FORGED_COMMITMENT)


def test_f_no_agent_ever_moved_the_episode_or_wrote_a_transition(boundary):
    """Explicitly, not only by type: `DecisionEpisode` is not a forbidden type — an agent
    is allowed to revise one — so the type audit above would not catch an agent-driven
    state change. Walk every episode revision and check the author of each move."""
    g = boundary["graph"]
    for oid in g.ids():
        if g.get(oid)["type"] != "DecisionEpisode":
            continue
        latest = g.get(oid)
        for rev in range(2, latest["rev"] + 1):
            prev, cur = g.get(oid, rev - 1), g.get(oid, rev)
            if cur["createdBy"].get("actorType") != "agent":
                continue
            assert cur["lifecycleState"] == prev["lifecycleState"], (
                f"{oid}@{rev}: an agent changed lifecycleState"
            )
            assert cur["transitions"] == prev["transitions"], (
                f"{oid}@{rev}: an agent wrote a transition record"
            )
        for record in latest["transitions"]:
            assert record["actor"]["actorType"] != "agent", (
                f"{oid}: a transition record names an agent actor"
            )
            if record["to"] in HUMAN_ONLY:
                assert record["actor"]["actorType"] == "human"
            if record["to"] in KERNEL_ONLY:
                assert record["actor"]["actorType"] == "kernel"


def test_f_the_hash_chain_still_verifies_in_memory(boundary):
    assert rule_log_chain(boundary["graph"]) == []


def test_f_the_saved_store_reloads_clean_and_re_validates(boundary, tmp_path):
    """The chain, the manifest and every object hash, checked the way a third party
    holding nothing but the saved directory would check them — `Graph.load` verifies all
    three before it populates any state — followed by the whole-store rules again."""
    out = tmp_path / "after-the-refusals"
    boundary["graph"].save(out)

    reloaded = Graph.load(out)
    assert reloaded.snapshot_hash() == boundary["graph"].snapshot_hash()
    assert _agent_authored_forbidden(reloaded.all(), reloaded.log()) == []

    findings = validate(reloaded)
    assert [f for f in findings if f.rule == "authority"] == []
    assert [f for f in findings if f.rule == "log-chain"] == []


def test_f_the_five_refusals_left_the_record_exactly_one_human_write_longer(boundary):
    """The only thing added to Demo A's record across all five attempts is the human
    revision that dropped the plan's approval so (e) had something to refuse."""
    g = boundary["graph"]
    assert len(g.log()) == boundary["log_at_start"] + 1
    assert g.log()[-1]["actor"] == H
    assert g.log()[-1]["id"] == PLAN
    assert g.get(EPISODE)["lifecycleState"] == boundary["state_before"]


# --- the audit is not vacuous ------------------------------------------------------


def _hand_forged_store(directory: Path, obj: dict, actor: dict) -> Path:
    """Write a one-object store by hand whose chain and manifest verify perfectly.

    This is the forgery `Graph.put` cannot prevent: the log is unkeyed, so anyone who can
    write the directory can re-chain it. It is why `rule_authority` audits authorship from
    the store as well as at the write path (design §8.7).
    """
    (directory / "objects").mkdir(parents=True, exist_ok=True)
    (directory / "objects" / f"{obj['id']}@{obj['rev']}.json").write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    entry = {"seq": 1, "op": "put", "id": obj["id"], "type": obj["type"], "rev": obj["rev"],
             "hash": content_hash(obj), "actor": actor, "prevHash": GENESIS}
    entry["entryHash"] = content_hash(entry)
    (directory / "log.jsonl").write_text(
        canonical_json(entry) + "\n", encoding="utf-8", newline="\n")
    (directory / "manifest.json").write_text(
        json.dumps({"snapshotHash": content_hash([obj]), "kernelVersion": KERNEL_VERSION,
                    "objects": 1, "logEntries": 1, "logHead": entry["entryHash"]},
                   indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    return directory


def test_the_authority_audit_catches_a_hand_edited_store(boundary, tmp_path):
    """A verifying chain is not an honest record, and `test_f_*` above would be worth
    nothing if the audit could not tell the difference. Take a real sealed
    `EvaluationRun`, re-author it as the agent, write it into a store by hand with a
    correctly recomputed chain, and confirm: the store loads (so the chain is genuinely
    valid) and `rule_authority` still names it."""
    real_run = boundary["graph"].get(boundary["graph"].get(EPISODE)["runs"][0])
    forged = {**real_run, "id": FORGED_RUN, "rev": 1, "createdBy": A, "createdAt": NOW}
    store = _hand_forged_store(tmp_path / "forged", forged, A)

    g = Graph.load(store)  # the chain, the hashes and the manifest all check out
    assert rule_log_chain(g) == []

    findings = rule_authority(g)
    assert [f.rule for f in findings] == ["authority"]
    assert findings[0].objects == (FORGED_RUN,)
    assert "EvaluationRun" in findings[0].message
    assert _agent_authored_forbidden(g.all(), g.log()) == [(FORGED_RUN, "EvaluationRun")]


# --- the whole boundary, re-derived from a saved store [ruling R14] -----------------
#
# The type rule was already auditable from the store. The other seven were not, so a
# hand-edited record carrying an agent-approved plan, agent-reviewed evidence, an
# agent-confirmed gap, an agent exclusion claiming human authority, or an agent-driven
# lifecycle move used to load and validate clean. `rule_authority` now re-derives all
# eight, and these tests are the proof — one forgery per rule, each of which *loads*,
# because a forgery that does not load proves nothing.


def forge(src: Path, dst: Path, edits: dict[str, dict],
          log_actors: dict[str, dict] | None = None) -> Path:
    """Copy a saved store, apply `edits` (`{"<id>@<rev>": {field: value}}`) and re-chain
    the log and manifest so the forgery loads cleanly. `log_actors`, keyed the same way,
    overrides the log entry's `actor` *after* the re-derivation from `createdBy`.

    This is the threat model, not a shortcut. `Graph.load` verifies every object hash, the
    `prevHash` chain and the manifest — and the chain is unkeyed, so anyone who can write
    the directory can recompute all three. What they cannot make consistent is the
    authorship, which is exactly what `rule_authority` reads.

    The log entry's `actor` is re-derived from each object's `createdBy` by default,
    because that is the pairing `Graph.put` writes and therefore the honest forgery: a
    store where the two agree is the hardest one to tell from a real record. It is *not*
    done because a mismatch would be caught by something dumber — until the T9 review
    (I5) nothing compared the two at all, and forcing the log actor back to `human` while
    leaving `createdBy` openly naming an agent defeated rules 7 and 8 outright. Pass
    `log_actors` to build exactly that forgery; `rule_authority` now reports the
    disagreement and audits the revision as an agent's either way.
    """
    shutil.copytree(src, dst)
    for key, fields in edits.items():
        oid, _, rev = key.partition("@")
        path = dst / "objects" / f"{oid}@{rev}.json"
        obj = json.loads(path.read_text(encoding="utf-8"))
        obj.update(fields)
        path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")

    log_path = dst / "log.jsonl"
    entries = [json.loads(line)
               for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    latest: dict[str, dict] = {}
    prev = GENESIS
    for entry in entries:
        obj = json.loads(
            (dst / "objects" / f"{entry['id']}@{entry['rev']}.json").read_text(encoding="utf-8"))
        entry["type"] = obj["type"]
        entry["hash"] = content_hash(obj)
        entry["actor"] = (log_actors or {}).get(
            f"{entry['id']}@{entry['rev']}", obj["createdBy"])
        entry["prevHash"] = prev
        entry["entryHash"] = content_hash({k: v for k, v in entry.items() if k != "entryHash"})
        prev = entry["entryHash"]
        latest[entry["id"]] = obj
    log_path.write_text("".join(canonical_json(e) + "\n" for e in entries),
                        encoding="utf-8", newline="\n")

    manifest = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    manifest.update({"objects": len(latest), "logEntries": len(entries),
                     "snapshotHash": content_hash([latest[i] for i in sorted(latest)]),
                     "logHead": prev})
    (dst / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return dst


def _reauthored_as_agent(graph_dir: Path, dst: Path, oid: str, *, rev: int | None = None) -> Path:
    """Forge `oid`'s latest revision (or `rev`) so an agent appears to have written it."""
    g = Graph.load(graph_dir)
    rev = g.get(oid)["rev"] if rev is None else rev
    return forge(graph_dir, dst, {f"{oid}@{rev}": {"createdBy": A}})


def _first(graph_dir: Path, predicate) -> str:
    g = Graph.load(graph_dir)
    matches = [o["id"] for o in g.all() if predicate(o)]
    assert matches, "Demo A no longer carries an object this forgery needs"
    return sorted(matches)[0]


def test_the_honest_demo_a_store_has_no_authority_finding(demo_a_graph_dir):
    """The baseline every forgery below is measured against."""
    assert [f for f in validate(Graph.load(demo_a_graph_dir)) if f.rule == "authority"] == []


def _assert_forgery_is_caught(store: Path, oid: str, *, expect_in_message: str) -> None:
    g = Graph.load(store)  # loads clean: the chain and the manifest are consistent
    assert rule_log_chain(g) == [], "the forgery should be undetectable by the chain alone"
    findings = [f for f in validate(g) if f.rule == "authority"]
    assert findings, f"{oid}: the forgery was not caught"
    assert all(f.severity == "blocking" for f in findings)
    assert oid in {i for f in findings for i in f.objects}
    assert any(expect_in_message in f.message for f in findings), (
        f"{oid}: no finding mentions {expect_in_message!r}; got "
        f"{[f.message for f in findings]}"
    )


def test_forged_store_an_agent_approved_plan_is_caught(demo_a_graph_dir, tmp_path):
    store = _reauthored_as_agent(demo_a_graph_dir, tmp_path / "plan", PLAN)
    _assert_forgery_is_caught(store, PLAN, expect_in_message="only a human may approve a plan")


def test_forged_store_agent_reviewed_evidence_is_caught(demo_a_graph_dir, tmp_path):
    oid = _first(demo_a_graph_dir,
                 lambda o: o["type"] == "Evidence" and o.get("reviewStatus") == "reviewed")
    store = _reauthored_as_agent(demo_a_graph_dir, tmp_path / "evidence", oid)
    _assert_forgery_is_caught(store, oid, expect_in_message="only write draft evidence")


def test_forged_store_an_agent_confirmed_gap_is_caught(demo_a_graph_dir, tmp_path):
    oid = _first(demo_a_graph_dir,
                 lambda o: o["type"] == "InsufficientEvidence" and o.get("confirmedBy"))
    store = _reauthored_as_agent(demo_a_graph_dir, tmp_path / "gap", oid)
    _assert_forgery_is_caught(store, oid, expect_in_message="only a human may confirm")


def test_forged_store_an_agent_exclusion_claiming_human_authority_is_caught(
    demo_a_graph_dir, tmp_path
):
    oid = _first(demo_a_graph_dir,
                 lambda o: o["type"] == "Exclusion"
                 and (o.get("authority") or {}).get("role") != "agent-proposal")
    store = _reauthored_as_agent(demo_a_graph_dir, tmp_path / "exclusion", oid)
    _assert_forgery_is_caught(store, oid, expect_in_message="agent-proposal")


def test_forged_store_an_agent_driven_lifecycle_move_is_caught(demo_a_graph_dir, tmp_path):
    """Demo A's episode revision 3 is the human's `MODEL_APPROVED → PLAN_APPROVED` move.
    Re-authored as the agent it trips two findings at once: the state changed, and the
    transition history grew."""
    g = Graph.load(demo_a_graph_dir)
    rev = next(r for r in range(2, g.get(EPISODE)["rev"] + 1)
               if g.get(EPISODE, r)["lifecycleState"] != g.get(EPISODE, r - 1)["lifecycleState"])
    store = forge(demo_a_graph_dir, tmp_path / "lifecycle",
                  {f"{EPISODE}@{rev}": {"createdBy": A}})
    _assert_forgery_is_caught(store, EPISODE, expect_in_message="lifecycle edge")

    findings = [f for f in validate(Graph.load(store)) if f.rule == "authority"]
    assert any("transition history" in f.message for f in findings)


def test_the_boundary_is_checkable_from_the_store_alone(demo_a_graph_dir, tmp_path):
    """All eight write-path rules, re-derived from a saved store in one pass.

    One store, forged in every way at once, and the audit must name every offending
    object. This is the sentence the proposal makes — "checkable by a third party holding
    nothing but the saved store" — turned into an assertion.
    """
    g = Graph.load(demo_a_graph_dir)
    run_id = g.get(EPISODE)["runs"][0]
    evidence_id = _first(demo_a_graph_dir,
                         lambda o: o["type"] == "Evidence" and o.get("reviewStatus") == "reviewed")
    gap_id = _first(demo_a_graph_dir,
                    lambda o: o["type"] == "InsufficientEvidence" and o.get("confirmedBy"))
    exclusion_id = _first(demo_a_graph_dir,
                          lambda o: o["type"] == "Exclusion"
                          and (o.get("authority") or {}).get("role") != "agent-proposal")
    ep_rev = next(r for r in range(2, g.get(EPISODE)["rev"] + 1)
                  if g.get(EPISODE, r)["lifecycleState"] != g.get(EPISODE, r - 1)["lifecycleState"])

    store = forge(demo_a_graph_dir, tmp_path / "all", {
        f"{run_id}@1": {"createdBy": A},                       # rule 1: forbidden type
        f"{PLAN}@{g.get(PLAN)['rev']}": {"createdBy": A},       # rule 2: Plan.approvedBy
        f"{evidence_id}@{g.get(evidence_id)['rev']}": {"createdBy": A},   # rules 3 and 4
        f"{gap_id}@{g.get(gap_id)['rev']}": {"createdBy": A},   # rule 5: confirmedBy
        f"{exclusion_id}@{g.get(exclusion_id)['rev']}": {"createdBy": A},  # rule 6
        f"{EPISODE}@{ep_rev}": {"createdBy": A},                # rules 7 and 8
    })

    forged_graph = Graph.load(store)
    assert rule_log_chain(forged_graph) == []
    findings = [f for f in validate(forged_graph) if f.rule == "authority"]
    named = {i for f in findings for i in f.objects}
    assert named == {run_id, PLAN, evidence_id, gap_id, exclusion_id, EPISODE}
    assert all(f.severity == "blocking" for f in findings)
    # What that costs the forger is asserted behaviourally, not by set membership, in
    # `test_blast_radius_*` below: the first review's C1 was that this file asserted
    # `"authority" in WHOLE_STORE_RULES` and called it "holds every gate shut", which was
    # a statement about a frozenset and not about a gate.


# --- the blast radius, asserted as behaviour [T9 review C1] --------------------------
#
# "One forged authorship line and the record cannot be read at all" was a claim about a
# frozenset. It is a claim about gates now: `WHOLE_STORE_RULES` is consulted by every
# lifecycle target but `VOID`, and by `kernel.evaluate.evaluate` before it computes
# anything. These tests are that sentence, and its one exemption.


@pytest.fixture(scope="module")
def demo_a_draft_store(tmp_path_factory):
    """Demo A as `build()` leaves it — DRAFT, before any gate — saved to disk.

    G1 is the gate the forgery has to be measured against, and Demo A's *run* store is
    already at `PENDING_SIGNATURE`, where `MODEL_APPROVED` is not even a legal edge.
    """
    from demos.a_cbo_gcv_2013.build import build

    d = tmp_path_factory.mktemp("demo-a-draft") / "graph"
    build().save(d)
    return d


@pytest.fixture(scope="module")
def demo_a_plan_approved_store(tmp_path_factory):
    """Demo A with G1 and G2 driven honestly by a human, saved before anything is computed.

    The state row 21 of the review's table needs: a store where `evaluate()` is entitled
    to run, so that a forgery introduced afterwards is the only thing standing between the
    kernel and a computation.
    """
    from demos.a_cbo_gcv_2013.build import build

    g = build()
    transition(g, EPISODE, "MODEL_APPROVED", H, now=NOW)
    transition(g, EPISODE, "PLAN_APPROVED", H, now=NOW)
    d = tmp_path_factory.mktemp("demo-a-plan-approved") / "graph"
    g.save(d)
    return d


def _outside_the_episode(graph_dir: Path) -> str:
    """An object id the episode's forward reference graph does not reach.

    This is the honest-bug shape as much as the forgery shape: an `Exclusion` recorded
    against a part of the record this episode never touches. Forging one is how the
    blast radius gets tested — a finding that named something the episode reaches would
    be refused by reachability alone and would prove nothing about the whole-store rules.
    """
    g = Graph.load(graph_dir)
    reach = {EPISODE} | g.reachable_from(EPISODE, reverse=False)
    ids = sorted(o["id"] for o in g.all() if o["id"] not in reach)
    assert ids, "Demo A no longer holds an object outside the episode's reach"
    return ids[0]


def test_blast_radius_the_honest_draft_store_opens_g1(demo_a_draft_store):
    """The baseline, so the refusal below is the forgery's doing and not the store's."""
    g = Graph.load(demo_a_draft_store)
    assert g.get(EPISODE)["lifecycleState"] == "DRAFT"
    transition(g, EPISODE, "MODEL_APPROVED", H, now=NOW)
    assert g.get(EPISODE)["lifecycleState"] == "MODEL_APPROVED"


def test_blast_radius_a_forgery_the_episode_cannot_reach_still_shuts_g1(
    demo_a_draft_store, tmp_path
):
    oid = _outside_the_episode(demo_a_draft_store)
    store = forge(demo_a_draft_store, tmp_path / "g1", {f"{oid}@1": {"createdBy": A}})

    g = Graph.load(store)
    assert rule_log_chain(g) == [], "the chain must not be what catches this"
    findings = [f for f in validate(g) if f.rule == "authority"]
    assert {i for f in findings for i in f.objects} == {oid}
    assert oid not in ({EPISODE} | g.reachable_from(EPISODE, reverse=False))

    with pytest.raises(TransitionRefused) as exc:
        transition(g, EPISODE, "MODEL_APPROVED", H, now=NOW)
    assert "no-blocking-structural" in exc.value.unsatisfied
    assert "store-integrity" in exc.value.unsatisfied
    assert g.get(EPISODE)["lifecycleState"] == "DRAFT"
    # A human's refused attempt is still written down — the forgery shuts the gate, it
    # does not make the record silent about the attempt.
    assert g.get(EPISODE)["transitions"][-1]["refused"] is True


def test_blast_radius_void_is_the_one_edge_a_forgery_does_not_shut(
    demo_a_draft_store, tmp_path
):
    """Abandoning a record has to stay possible precisely when the record cannot be
    trusted. Every other target consults the whole-store rules; `VOID` does not."""
    oid = _outside_the_episode(demo_a_draft_store)
    store = forge(demo_a_draft_store, tmp_path / "void", {f"{oid}@1": {"createdBy": A}})

    g = Graph.load(store)
    transition(g, EPISODE, "VOID", H, now=NOW)
    assert g.get(EPISODE)["lifecycleState"] == "VOID"
    record = g.get(EPISODE)["transitions"][-1]
    assert record["refused"] is False and "store-integrity" not in record["checksUnsatisfied"]


def test_blast_radius_the_kernel_will_not_compute_on_a_forged_store(
    demo_a_plan_approved_store, tmp_path
):
    """Row 21 of the review's table: the gates were shut and `evaluate()` ran anyway.

    Baseline first — the honest store computes — then the same store with one forged
    authorship line on an object the plan never mentions.
    """
    from docket.errors import ValidationError
    from docket.kernel.evaluate import evaluate

    honest = Graph.load(demo_a_plan_approved_store)
    assert evaluate(honest, PLAN, seed=20130430, now=NOW), "the baseline must compute"

    oid = _outside_the_episode(demo_a_plan_approved_store)
    store = forge(demo_a_plan_approved_store, tmp_path / "eval",
                  {f"{oid}@1": {"createdBy": A}})
    g = Graph.load(store)
    before = len(g.log())
    with pytest.raises(ValidationError) as exc:
        evaluate(g, PLAN, seed=20130430, now=NOW)
    assert "nothing may be computed" in str(exc.value)
    assert oid in str(exc.value), "the refusal must name what it found"
    assert len(g.log()) == before, "a refused evaluation writes nothing"


def test_blast_radius_a_readiness_report_written_after_a_forgery_is_not_ready(
    demo_a_graph_dir, tmp_path
):
    """The other half of row 21. The stored `ReadinessReport` is a *stored* object and a
    forger simply leaves it in place — `c_readiness_ready` reads it and still says yes.
    What changes is that G3 no longer takes that answer on its own, and a report
    regenerated from the forged store says no."""
    from docket.kernel.lifecycle import c_readiness_ready
    from docket.kernel.readiness import readiness_report

    oid = _outside_the_episode(demo_a_graph_dir)
    store = forge(demo_a_graph_dir, tmp_path / "readiness", {f"{oid}@1": {"createdBy": A}})
    g = Graph.load(store)
    ep = g.get(EPISODE)

    assert c_readiness_ready(g, ep) is True, (
        "the stored report is untouched — this is exactly what the forger relies on"
    )
    with pytest.raises(TransitionRefused) as exc:
        transition(g, EPISODE, "SIGNED", H, now=NOW)
    assert "store-integrity" in exc.value.unsatisfied
    assert "readiness-ready" not in exc.value.unsatisfied, (
        "the stale report still passes its own check; store-integrity is what refuses"
    )

    fresh = readiness_report(g, EPISODE, seed=20130430, now=NOW)
    assert fresh["ready"] is False
    named = [b for b in fresh["blockers"] if b["rule"] == "authority"]
    assert [b["objects"] for b in named] == [[oid]], (
        f"the regenerated report must name the forged object: {fresh['blockers']}"
    )


def test_blast_radius_the_honest_store_names_no_store_integrity_check(demo_a_graph_dir):
    """The contrast that makes `store-integrity` mean something: on an honest store it is
    absent from every refusal, because a precondition that always fires is not a check."""
    g = Graph.load(demo_a_graph_dir)
    with pytest.raises(TransitionRefused) as exc:
        transition(g, EPISODE, "SIGNED", H, now=NOW)
    assert "store-integrity" not in exc.value.unsatisfied
    assert "commitment-present" in exc.value.unsatisfied


# --- the review's twenty-one defeat attempts, each pinned ----------------------------
#
# The T9 review tried twenty-one ways past the boundary and tabled what happened. Eleven
# got through. Re-running them here means the table is a test rather than a memory: the
# ones that are now caught stay caught, and the ones that are inherent are written down
# as inherent, with the control that actually covers them named, so nobody re-discovers
# them and calls them a regression.
#
# | #  | attempt                                             | now                            |
# |----|-----------------------------------------------------|--------------------------------|
# | 1  | liar actor writes an EvaluationRun                  | refused at `put`               |
# | 2  | liar actor sets `Plan.approvedBy`                   | refused at `put`               |
# | 3  | liar actor drives `PENDING_SIGNATURE -> SIGNED`     | refused at `put`               |
# | 4  | liar actor drives `-> VOID`                         | refused at `put`               |
# | 5  | an agent process presenting a human's actor dict    | inherent: impersonation        |
# | 6  | the same, on a `Commitment`                         | inherent: impersonation        |
# | 7  | agent `Narrative` embedding a serialised run        | inherent: no intent parsing    |
# | 8  | agent `Narrative` with a fabricated numeral         | caught on the narrate path     |
# | 9  | agent writes `Observation`, `WeightSet`, `Measure`  | permitted: a labelled proposal |
# | 10 | agent `put` of an episode carrying a refusal record | `AuthorityViolation`           |
# | 11 | agent `put` of an episode moving `lifecycleState`   | `AuthorityViolation`           |
# | 12 | in-process bypass of `put`, chain kept valid        | `rule_authority`               |
# | 13 | naive hand edit of a log entry, no re-chaining      | `Graph.load`                   |
# | 14 | naive hand edit of an object, no re-chaining        | `Graph.load`                   |
# | 15 | re-chained, log actor forced back to human          | `rule_authority` (new)         |
# | 16 | re-chained, log actor agent over a human object     | `rule_authority`               |
# | 17 | agent `pl-cbo@1`, superseded by a human `@2`        | `rule_authority` (new)         |
# | 18 | agent downgrades reviewed `Evidence` to `draft`     | `rule_authority` (new)         |
# | 19 | agent takes over a human `Exclusion`                | `rule_authority` (new)         |
# | 20 | forged object outside an episode's reach, then G1   | refused (unchanged)            |
# | 21 | the same store: `evaluate()` and a fresh readiness  | both refuse (new)              |

LIAR = {"actorType": "human", "actorId": "agent:recorded"}


def _draft_graph():
    """A fresh in-memory Demo A at DRAFT, for the attempts that would mutate a store."""
    from demos.a_cbo_gcv_2013.build import build

    return build()


def test_defeat_1_to_4_an_agent_id_declaring_itself_human_is_refused_at_the_write_path(
    boundary,
):
    """Rows 1–4. `{"actorType": "human", "actorId": "agent:recorded"}` used to be a human
    everywhere in the kernel: it wrote a run, set a plan approval, was named in a refusal
    record at G3, and drove a live episode to `VOID` with zero findings behind it. The
    store derives the actor class from the id now, so all four die at the same line."""
    g = boundary["graph"]
    before = len(g.log())
    state = g.get(EPISODE)["lifecycleState"]

    real_run = g.get(g.get(EPISODE)["runs"][0])
    plan = g.get(PLAN)
    attempts = {
        "run": lambda: g.put({**real_run, "id": "run-liar", "rev": 1,
                              "createdBy": LIAR, "createdAt": NOW}, LIAR),
        "plan approval": lambda: g.put(
            {**plan, "rev": plan["rev"] + 1, "createdBy": LIAR, "createdAt": NOW,
             "approvedBy": {"actorId": "agent:recorded", "date": NOW}}, LIAR),
        "SIGNED": lambda: transition(g, EPISODE, "SIGNED", LIAR, now=NOW),
        "VOID": lambda: transition(g, EPISODE, "VOID", LIAR, now=NOW),
    }
    for name, fn in attempts.items():
        exc = _attempt(fn)
        assert isinstance(exc, AuthorityViolation), f"{name}: expected refusal, got {exc!r}"
        assert "agent:recorded" in str(exc) and "malformed actor" in str(exc)

    assert len(g.log()) == before, "four refusals, nothing written"
    assert g.get(EPISODE)["lifecycleState"] == state
    assert not g.has("run-liar")


def test_defeat_5_and_6_a_process_holding_a_human_actor_dict_is_impersonation(boundary):
    """Rows 5–6, and they are **inherent**. An actor dict is a credential, and the store
    binds the credential presented, not the process presenting it: a human actor dict
    with no `agent:` anywhere in it is indistinguishable from a human. Nothing in the
    kernel can close this and nothing here pretends to.

    Where it is actually controlled: the API never reads an actor from a request body —
    `api/routes/agent.py` builds both actors server-side from configuration
    (`api.config.human_actor` / `agent_actor`), and `tests/api/test_agent_routes.py`
    asserts a client-supplied actor is ignored. Outside the API it is a machine-access
    question, not a validator question.
    """
    g = _draft_graph()
    commitment = {
        "id": "cmt-impersonated", "type": "Commitment", "rev": 1, "createdBy": H,
        "createdAt": NOW, "episode": EPISODE, "selected": "alt-puma",
        "signer": {"identity": "a name somebody chose", "role": "decision authority"},
        "signedAt": NOW, "conditions": [], "stopRules": [], "packageHash": "0" * 64,
    }
    g.put(commitment, H)  # accepted: this is a human writing, as far as anything can tell
    assert rule_authority(g) == [], (
        "an audit that flagged this would be flagging every human write"
    )


def test_defeat_7_and_8_the_store_does_not_read_a_narrative_s_prose(boundary):
    """Rows 7–8, also **inherent**, and worth being exact about. An agent may write a
    `Narrative`; a `Narrative` is free text; free text can contain the JSON of an
    `EvaluationRun` or a number nobody can source. The store does not parse intent out of
    prose and should not try — a rule that guessed at meaning would be the one part of
    this boundary a reviewer could not check.

    Two controls stand in front of it, and both are real. `check_citations` refuses a
    numeral no cited object holds, on the `narrate` path, before the draft is stored
    (case (d) above). And prose is not the numeric path: an `EvaluationRun` written out
    longhand inside a sentence is a string, read by nobody, while the sealed run objects
    the kernel and the exports read cannot be agent-authored at all.
    """
    from docket.kernel.render import check_citations

    g = _draft_graph()
    run_shaped = json.dumps({"type": "EvaluationRun", "value": 99.9})
    narrative = {
        "id": "nar-smuggled", "type": "Narrative", "rev": 1, "createdBy": A,
        "createdAt": NOW, "episode": EPISODE, "section": SECTION,
        "sentences": [{"text": f"The run record is {run_shaped} and the score is 99.9.",
                       "cites": [EPISODE]}],
    }
    g.put(narrative, A)  # the store accepts it: an allowed type carrying anything at all
    assert rule_authority(g) == []

    # …and the check that does read it says no.
    errs = check_citations(g, g.get("nar-smuggled"))
    assert errs and "99.9" in errs[0], errs
    # while the objects a reader's numbers actually come from stay closed to the agent.
    assert {"EvaluationRun", "Result"} <= set(AGENT_FORBIDDEN_TYPES)


def test_defeat_9_an_agent_proposed_number_is_a_proposal_and_is_labelled_as_one():
    """Row 9. `Observation` and `WeightSet` are the solver's *inputs*, and they are not on
    the forbidden list — deliberately, because a future elicitation stage that proposed a
    number would be proposing, not deciding. Today's `agent/elicit.py` produces neither
    (its module docstring says so and `tests/agent/test_elicit.py` holds it to that).

    What the record guarantees is the honest, checkable version: the proposal carries the
    agent's name, the package prints that name, and nothing the agent wrote is ever a run
    or a result.
    """
    from docket.kernel.render import ai_assistance_summary

    g = _draft_graph()
    real = g.get(sorted(o["id"] for o in g.all("Observation"))[0])
    proposed = {**real, "id": "ob-agent-proposed", "rev": 1, "createdBy": A,
                "createdAt": NOW}
    g.put(proposed, A)  # accepted — a proposed number is a proposal
    assert rule_authority(g) == []

    ep = g.get(EPISODE)
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "observations": [*ep["observations"], "ob-agent-proposed"]}, H)

    summary = ai_assistance_summary(g, g.get(EPISODE))
    assert summary["agentActors"] == ["agent:recorded"], (
        "an agent-proposed number must show up in the package's AI-assistance label"
    )
    assert summary["noAiAssistance"] is False
    assert summary["agentComputedNoResult"] is True, (
        "the proposal is a proposal: no agent-authored run reaches the episode"
    )


def test_defeat_10_and_11_an_agent_may_not_write_transitions_or_move_the_state():
    """Rows 10–11, unchanged and still the write path's own work: `transition()` is not
    the only way to reach those two fields, and `put` guards them directly."""
    g = _draft_graph()
    ep = g.get(EPISODE)
    before = len(g.log())
    record = {"from": "DRAFT", "to": "MODEL_APPROVED", "actor": dict(A), "at": NOW,
              "policyVersion": "0.1", "checksSatisfied": [],
              "checksUnsatisfied": ["human-actor"], "refused": True}

    with pytest.raises(AuthorityViolation, match="transitions"):
        g.put({**ep, "rev": ep["rev"] + 1, "createdBy": A, "createdAt": NOW,
               "transitions": [record]}, A)
    with pytest.raises(AuthorityViolation, match="lifecycleState"):
        g.put({**ep, "rev": ep["rev"] + 1, "createdBy": A, "createdAt": NOW,
               "lifecycleState": "MODEL_APPROVED"}, A)
    assert len(g.log()) == before


def test_defeat_12_bypassing_put_entirely_is_caught_by_the_store_audit():
    """Row 12, and the one the whole rule exists for. Skip `put`, write straight into the
    graph's own state, keep the chain valid — the in-process boundary never runs. The
    audit reads the record instead of the code path, so it sees it anyway."""
    g = _draft_graph()
    ep = g.get(EPISODE)
    moved = {**ep, "rev": ep["rev"] + 1, "createdBy": A, "createdAt": NOW,
             "lifecycleState": "MODEL_APPROVED"}
    g._latest[EPISODE] = moved
    g._history[EPISODE][moved["rev"]] = moved
    entry = {"seq": len(g._log) + 1, "op": "put", "id": EPISODE, "type": "DecisionEpisode",
             "rev": moved["rev"], "hash": content_hash(moved), "actor": A,
             "prevHash": g._log[-1]["entryHash"]}
    entry["entryHash"] = content_hash(entry)
    g._log.append(entry)

    assert g.get(EPISODE)["lifecycleState"] == "MODEL_APPROVED", "the bypass worked"
    assert rule_log_chain(g) == [], "and the chain does not notice"
    findings = rule_authority(g)
    assert [f.objects for f in findings] == [(EPISODE,)]
    assert "lifecycle edge" in findings[0].message


def _naive_edit(store: Path, dst: Path, edit) -> Path:
    """Copy a store and hand-edit one file, leaving the chain as it was."""
    shutil.copytree(store, dst)
    edit(dst)
    return dst


def test_defeat_13_and_14_a_careless_hand_edit_will_not_even_load(
    demo_a_draft_store, tmp_path
):
    """Rows 13–14. The chain catches the forger who does not re-chain — which is worth
    stating precisely, because it is the *only* tampering the chain catches on its own."""
    from docket.errors import ValidationError

    def edit_log(d: Path) -> None:
        lines = (d / "log.jsonl").read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[-1])
        entry["actor"] = dict(A)
        lines[-1] = canonical_json(entry)
        (d / "log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    def edit_object(d: Path) -> None:
        path = sorted((d / "objects").glob("*@1.json"))[0]
        obj = json.loads(path.read_text(encoding="utf-8"))
        obj["createdBy"] = dict(A)
        path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")

    for name, edit in (("log", edit_log), ("object", edit_object)):
        store = _naive_edit(demo_a_draft_store, tmp_path / f"naive-{name}", edit)
        with pytest.raises(ValidationError) as exc:
            Graph.load(store)
        assert "does not match" in str(exc.value), (name, str(exc.value))


def _episode_move_rev(graph_dir: Path) -> int:
    g = Graph.load(graph_dir)
    return next(r for r in range(2, g.get(EPISODE)["rev"] + 1)
                if g.get(EPISODE, r)["lifecycleState"] != g.get(EPISODE, r - 1)["lifecycleState"])


def test_defeat_15_a_log_actor_forced_back_to_human_no_longer_hides_the_move(
    demo_a_graph_dir, tmp_path
):
    """Row 15 — the cheapest defeat in the whole table, and the one the first version of
    `forge()` was quietly not building. The object openly says an agent moved the
    episode; one word in one log line said otherwise, and rules 7 and 8, which read the
    log actor, went quiet."""
    rev = _episode_move_rev(demo_a_graph_dir)
    store = forge(demo_a_graph_dir, tmp_path / "log-actor",
                  {f"{EPISODE}@{rev}": {"createdBy": A}},
                  log_actors={f"{EPISODE}@{rev}": dict(H)})

    g = Graph.load(store)
    assert rule_log_chain(g) == []
    messages = " | ".join(f.message for f in rule_authority(g))
    assert f"the log entry for {EPISODE}@{rev} names actor 'shreyash' ('human')" in messages
    assert "written by 'agent:recorded' ('agent')" in messages
    assert "lifecycle edge" in messages, "and the rule it was hiding still fires"


def test_defeat_16_a_log_actor_naming_an_agent_over_a_human_object_is_caught(
    demo_a_graph_dir, tmp_path
):
    """Row 16, the mirror image, caught before and caught now — with the disagreement
    itself named as well as the rule."""
    rev = _episode_move_rev(demo_a_graph_dir)
    store = forge(demo_a_graph_dir, tmp_path / "log-actor-agent", {},
                  log_actors={f"{EPISODE}@{rev}": dict(A)})

    g = Graph.load(store)
    assert rule_log_chain(g) == []
    messages = " | ".join(f.message for f in rule_authority(g))
    assert "names actor 'agent:recorded' ('agent')" in messages
    assert "lifecycle edge" in messages


def _with_human_revision(graph_dir: Path, dst: Path, oid: str, **fields) -> Path:
    """A copy of the store carrying one further, entirely legitimate, human revision.

    The two-revision shapes rows 17–19 need cannot be built by editing an existing
    revision — they are *about* the predecessor — so the honest revision is written
    through `put` first and the forgery is applied to it afterwards.
    """
    g = Graph.load(graph_dir)
    cur = g.get(oid)
    g.put({**cur, **fields, "rev": cur["rev"] + 1, "createdBy": H, "createdAt": NOW}, H)
    g.save(dst)
    return dst


def test_defeat_17_an_agent_approval_superseded_by_a_human_is_still_in_the_record(
    demo_a_graph_dir, tmp_path
):
    """Row 17. The head revision is honest and the audit used to read only heads, so an
    approval no human ever gave sat in the record's history saying nothing."""
    honest = _with_human_revision(demo_a_graph_dir, tmp_path / "superseded", PLAN)
    g = Graph.load(honest)
    assert g.get(PLAN)["rev"] >= 2 and g.get(PLAN)["createdBy"] == H
    assert g.get(PLAN, 1).get("approvedBy"), "Demo A's pl-cbo@1 must carry the approval"

    store = forge(honest, tmp_path / "superseded-forged", {f"{PLAN}@1": {"createdBy": A}})
    forged = Graph.load(store)
    assert rule_log_chain(forged) == []
    assert forged.get(PLAN)["createdBy"] == H, "the head revision is clean"
    findings = [f for f in validate(forged) if f.rule == "authority"]
    assert [f.objects for f in findings] == [(PLAN,)]
    assert "only a human may approve a plan" in findings[0].message


def test_defeat_18_an_agent_downgrading_reviewed_evidence_is_caught(
    demo_a_graph_dir, tmp_path
):
    """Row 18. The revision the agent lands on says `draft`, which is exactly what an
    agent is allowed to write — only the predecessor gives it away."""
    oid = _first(demo_a_graph_dir,
                 lambda o: o["type"] == "Evidence" and o.get("reviewStatus") == "reviewed")
    honest = _with_human_revision(demo_a_graph_dir, tmp_path / "downgrade", oid,
                                  reviewStatus="draft")
    rev = Graph.load(honest).get(oid)["rev"]
    store = forge(honest, tmp_path / "downgrade-forged", {f"{oid}@{rev}": {"createdBy": A}})

    g = Graph.load(store)
    assert rule_log_chain(g) == []
    findings = [f for f in validate(g) if f.rule == "authority"]
    assert [f.objects for f in findings] == [(oid,)]
    assert "revised evidence a human had marked 'reviewed'" in findings[0].message


def test_defeat_19_an_agent_taking_over_a_human_exclusion_is_caught(
    demo_a_graph_dir, tmp_path
):
    """Row 19. The agent relabels a human's exclusion as its own tidy `agent-proposal`,
    so the head revision passes rule 6 on its own terms and the human authority it
    overwrote survives only in the predecessor."""
    oid = _first(demo_a_graph_dir,
                 lambda o: o["type"] == "Exclusion"
                 and (o.get("authority") or {}).get("role") != "agent-proposal")
    prior = Graph.load(demo_a_graph_dir).get(oid)["authority"]
    honest = _with_human_revision(
        demo_a_graph_dir, tmp_path / "takeover", oid,
        authority={"who": A["actorId"], "role": "agent-proposal", "date": prior["date"]})
    rev = Graph.load(honest).get(oid)["rev"]
    store = forge(honest, tmp_path / "takeover-forged", {f"{oid}@{rev}": {"createdBy": A}})

    g = Graph.load(store)
    assert rule_log_chain(g) == []
    findings = [f for f in validate(g) if f.rule == "authority"]
    assert [f.objects for f in findings] == [(oid,)]
    assert "not the agent's to restate" in findings[0].message
    assert "agent-proposal" not in findings[0].message.split(";")[0], (
        "rule 6's create form must stay silent: the head revision is well-formed"
    )
