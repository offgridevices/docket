# tests/kernel/test_refresh.py
import pytest

from docket.errors import AuthorityViolation, ValidationError
from docket.kernel.bias import bias_indicators
from docket.kernel.refresh import affected_episodes, diff_episodes, open_refresh, supersede
from docket.kernel.validate import validate
from tests.kernel.conftest import H, episode, obj, put_all

NOW = "2026-09-04T00:00:00Z"

BLOCKING_RULE_KINDS = {"schema", "ref-integrity", "authority"}


def _obj_asm(oid, text):
    return obj(oid, "Assumption", statement=text, linchpin=False, rationale="r", evidence="ev-doc",
               implicationsIfWrong="i", indicatorsThatWouldAlter=["x"], variedInSensitivity=False)


def _no_blocking_findings(g):
    return [f for f in validate(g) if f.rule in BLOCKING_RULE_KINDS]


def test_refresh_opens_new_episode_and_diff(base_graph):
    g = base_graph
    put_all(
        g,
        _obj_asm("as-manning-feb", "minimal crew"),
        obj("cl-1", "Claim", text="nine characteristics", questionClass="other",
            assessableAt={"level": "U"}, supportedBy=[{"evidence": "ev-doc"}]),
        {**episode(), "rev": 2, "lifecycleState": "SIGNED",
         "assumptions": ["as-manning-feb"], "claims": ["cl-1"],
         "evidenceRegister": ["ev-doc"]},
        obj("prg-1", "DecisionProgram", name="p", charter="ch-1", episodes=["ep-1"],
            refreshTriggers=[], diffs=[]),
        obj("rt-1", "RefreshTrigger", kind="assumption-changed",
            source="Dec 2020 Industry Day slide 5", description="Manning hardened",
            detectedAt="2020-12-09", affected=["as-manning-feb"]),
        _obj_asm("as-manning-dec", "30 dismounts per platoon; crew of two in the hull"),
    )
    assert affected_episodes(g, "rt-1") == {"ep-1"}
    new = open_refresh(g, "prg-1", "rt-1", actor=H, now=NOW,
                        replacements={"as-manning-feb": "as-manning-dec"})
    assert new["id"] == "ep-1-r2" and new["sequence"] == 2 and new["lifecycleState"] == "DRAFT"
    assert new["assumptions"] == ["as-manning-dec"]
    assert new["refreshedBecause"] == "rt-1" and new["supersedes"] == "ep-1"
    assert new["replacements"] == {"as-manning-feb": "as-manning-dec"}
    assert g.get("ep-1")["lifecycleState"] == "SUSPECT"
    assert g.get("prg-1")["episodes"] == ["ep-1", "ep-1-r2"]
    d = diff_episodes(g, "ep-1", "ep-1-r2", now=NOW)
    assert d["removed"] == ["as-manning-feb"] and d["added"] == ["as-manning-dec"]
    assert d["judgmentsConsistent"] == ["cl-1"] and d["judgmentsChanged"] == []
    assert d["pairing"] == "replacements"
    assert d["changed"] == [{"object": "as-manning-feb→as-manning-dec", "field": "statement",
                              "before": '"minimal crew"',
                              "after": '"30 dismounts per platoon; crew of two in the hull"'}]
    assert g.get("prg-1")["diffs"] == [d["id"]]
    supersede(g, "ep-1", now=NOW)
    assert g.get("ep-1")["lifecycleState"] == "SUPERSEDED"
    assert _no_blocking_findings(g) == []


def test_open_refresh_requires_human_actor(base_graph):
    g = base_graph
    put_all(g,
            obj("prg-3", "DecisionProgram", name="p3", charter="ch-1", episodes=["ep-1"],
                refreshTriggers=[], diffs=[]),
            obj("rt-3", "RefreshTrigger", kind="elapsed-time", source="s", description="d",
                detectedAt="2026-09-01", affected=[]))
    agent = {"actorType": "agent", "actorId": "agent-1"}
    with pytest.raises(AuthorityViolation):
        open_refresh(g, "prg-3", "rt-3", actor=agent, now=NOW)
    # Refused before any write: nothing about the graph moved.
    assert g.get("ep-1")["lifecycleState"] == "DRAFT"
    assert g.get("prg-3")["episodes"] == ["ep-1"]


def test_open_refresh_id_derivation_anchors_on_a_trailing_refresh_suffix(base_graph):
    """T4 ruling: the base id is the prior id with a trailing `-r<digits>` stripped by
    regex, not `split('-r')` — an id containing "-r" in the middle ("ep-review-2020")
    must not be truncated to "ep"."""
    g = base_graph
    put_all(g, episode("ep-review-2020", lifecycleState="SIGNED"),
            obj("prg-2", "DecisionProgram", name="p2", charter="ch-1",
                episodes=["ep-review-2020"], refreshTriggers=[], diffs=[]),
            obj("rt-2", "RefreshTrigger", kind="elapsed-time", source="policy clock",
                description="periodic review", detectedAt="2026-09-01", affected=[]))
    new = open_refresh(g, "prg-2", "rt-2", actor=H, now=NOW)
    assert new["id"] == "ep-review-2020-r2"
    assert new["supersedes"] == "ep-review-2020"


def test_supersede_direct_from_signed_without_suspect_detour(base_graph):
    g = base_graph
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "lifecycleState": "SIGNED"}, H)
    supersede(g, "ep-1", now=NOW)
    assert g.get("ep-1")["lifecycleState"] == "SUPERSEDED"
    last = g.get("ep-1")["transitions"][-1]
    assert last["from"] == "SIGNED" and last["to"] == "SUPERSEDED" and last["refused"] is False


def test_diff_episodes_refuses_a_target_with_no_refreshedBecause(base_graph):
    g = base_graph
    put_all(g, episode("ep-2"))
    with pytest.raises(ValidationError):
        diff_episodes(g, "ep-1", "ep-2", now=NOW)
    # Refused before any write: no EpisodeDiff was created.
    assert not g.has("diff-ep-1-ep-2")


def test_affected_episodes_tolerates_a_missing_affected_id(base_graph):
    g = base_graph
    put_all(g, obj("rt-x", "RefreshTrigger", kind="evidence-changed", source="s",
                    description="d", detectedAt="2026-09-01", affected=["does-not-exist"]))
    assert affected_episodes(g, "rt-x") == set()


def test_diff_episodes_pairs_changed_from_replacements_not_sort_order(base_graph):
    """Review C1: pairing must come from the `replacements` map the refresh actually
    applied, never from zipping `sorted(removed)` against `sorted(added)` — which
    mispairs whenever the alphabetical orders of the two lists don't line up with the
    real mapping. `as-aaa` truly maps to `as-new-z-content` (alphabetically last of the
    two additions) and `as-zzz` truly maps to `as-new-a-content` (alphabetically first)
    — a sort-order zip would swap them."""
    g = base_graph
    put_all(
        g,
        _obj_asm("as-aaa", "content A"),
        _obj_asm("as-zzz", "content Z"),
        {**episode(), "rev": 2, "lifecycleState": "SIGNED",
         "assumptions": ["as-aaa", "as-zzz"]},
        obj("prg-8", "DecisionProgram", name="p8", charter="ch-1", episodes=["ep-1"],
            refreshTriggers=[], diffs=[]),
        obj("rt-8", "RefreshTrigger", kind="assumption-changed", source="s", description="d",
            detectedAt="2026-09-01", affected=["as-aaa", "as-zzz"]),
        _obj_asm("as-new-z-content", "the content that actually replaces as-zzz"),
        _obj_asm("as-new-a-content", "the content that actually replaces as-aaa"),
    )
    new = open_refresh(g, "prg-8", "rt-8", actor=H, now=NOW,
                        replacements={"as-aaa": "as-new-z-content", "as-zzz": "as-new-a-content"})
    d = diff_episodes(g, "ep-1", new["id"], now=NOW)
    assert d["pairing"] == "replacements"
    paired = {c["object"] for c in d["changed"]}
    assert "as-aaa→as-new-z-content" in paired
    assert "as-zzz→as-new-a-content" in paired
    assert "as-aaa→as-new-a-content" not in paired
    assert "as-zzz→as-new-z-content" not in paired


def test_diff_episodes_pairing_is_unknown_without_a_replacements_map(base_graph):
    g = base_graph
    put_all(g, {**episode("ep-2"), "refreshedBecause": "rt-x",
                "supersedes": "ep-1"},
            obj("rt-x", "RefreshTrigger", kind="elapsed-time", source="s", description="d",
                detectedAt="2026-09-01", affected=[]))
    d = diff_episodes(g, "ep-1", "ep-2", now=NOW)
    assert d["pairing"] == "unknown"
    assert d["changed"] == []


def test_open_refresh_is_atomic_when_the_new_id_is_occupied(base_graph):
    """Review C2: a refusal while building the successor episode must not leave the
    prior stranded mid-refresh (SUSPECT, no successor). Pre-occupying the id
    `open_refresh` would assign with an object of a different type reproduces the
    reviewer's probe exactly."""
    g = base_graph
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "lifecycleState": "SIGNED"}, H)
    put_all(
        g,
        obj("ep-1-r2", "Claim", text="occupying the id", questionClass="other",
            assessableAt={"level": "U"}, supportedBy=[]),
        obj("prg-9", "DecisionProgram", name="p9", charter="ch-1", episodes=["ep-1"],
            refreshTriggers=[], diffs=[]),
        obj("rt-9", "RefreshTrigger", kind="elapsed-time", source="s", description="d",
            detectedAt="2026-09-01", affected=[]),
    )
    log_len_before = len(g.log())
    with pytest.raises(ValidationError):
        open_refresh(g, "prg-9", "rt-9", actor=H, now=NOW)
    assert g.get("ep-1")["lifecycleState"] == "SIGNED"
    assert len(g.log()) == log_len_before


def test_open_refresh_refuses_a_draft_prior(base_graph):
    """Review I1: a `DRAFT` prior has no standing to supersede (and no `DRAFT->SUSPECT`
    edge exists in `lifecycle.EDGES`), so `open_refresh` must refuse before any write."""
    g = base_graph
    put_all(g, obj("prg-10", "DecisionProgram", name="p10", charter="ch-1",
                    episodes=["ep-1"], refreshTriggers=[], diffs=[]),
            obj("rt-10", "RefreshTrigger", kind="elapsed-time", source="s", description="d",
                detectedAt="2026-09-01", affected=[]))
    log_len_before = len(g.log())
    with pytest.raises(ValidationError):
        open_refresh(g, "prg-10", "rt-10", actor=H, now=NOW)
    assert g.get("ep-1")["lifecycleState"] == "DRAFT"
    assert len(g.log()) == log_len_before


def test_open_refresh_refuses_a_malformed_sequence(base_graph):
    """Review M1: a hand-edited store missing `sequence` must raise `ValidationError`,
    not a raw `KeyError`, matching every other malformed-input path in this module."""
    g = base_graph
    put_all(g, obj("prg-11", "DecisionProgram", name="p11", charter="ch-1",
                    episodes=["ep-1"], refreshTriggers=[], diffs=[]),
            obj("rt-11", "RefreshTrigger", kind="elapsed-time", source="s", description="d",
                detectedAt="2026-09-01", affected=[]))
    # Simulate a hand-edited store, bypassing the schema check a clean `g.put()` would
    # otherwise enforce — same technique as tests/kernel/test_lifecycle.py's direct
    # `g._latest[...]` mutations.
    g._latest["ep-1"]["lifecycleState"] = "SIGNED"
    del g._latest["ep-1"]["sequence"]
    with pytest.raises(ValidationError):
        open_refresh(g, "prg-11", "rt-11", actor=H, now=NOW)


def test_diff_episodes_is_atomic_when_the_diff_id_is_occupied(base_graph):
    """Round 2 fix 1: `diff_episodes` checks `g.has` on the diff id and builds every
    linking program revision before its first write, so pre-occupying the diff id with
    an object of a different type refuses cleanly with nothing written."""
    g = base_graph
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "lifecycleState": "SIGNED"}, H)
    put_all(
        g,
        obj("prg-12", "DecisionProgram", name="p12", charter="ch-1", episodes=["ep-1"],
            refreshTriggers=[], diffs=[]),
        obj("rt-12", "RefreshTrigger", kind="elapsed-time", source="s", description="d",
            detectedAt="2026-09-01", affected=[]),
    )
    new = open_refresh(g, "prg-12", "rt-12", actor=H, now=NOW)
    diff_id = f"diff-ep-1-{new['id']}"
    put_all(g, obj(diff_id, "Claim", text="occupying the diff id", questionClass="other",
                   assessableAt={"level": "U"}, supportedBy=[]))
    log_len_before = len(g.log())
    with pytest.raises(ValidationError):
        diff_episodes(g, "ep-1", new["id"], now=NOW)
    assert len(g.log()) == log_len_before
    assert g.get("prg-12")["diffs"] == []


def test_open_refresh_stamps_program_createdAt_to_now(base_graph):
    """Round 2 fix 2: the `DecisionProgram` revision `open_refresh` writes stamps
    `createdAt` to the `now` passed in, not the timestamp inherited from the program's
    previous revision — every kernel-relevant revision this module writes does."""
    g = base_graph
    put_all(g,
            obj("prg-13", "DecisionProgram", name="p13", charter="ch-1",
                episodes=["ep-1"], refreshTriggers=[], diffs=[]),
            obj("rt-13", "RefreshTrigger", kind="elapsed-time", source="s", description="d",
                detectedAt="2026-09-01", affected=[]))
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "lifecycleState": "SIGNED"}, H)
    later = "2026-09-05T12:00:00Z"
    open_refresh(g, "prg-13", "rt-13", actor=H, now=later)
    assert g.get("prg-13")["createdAt"] == later


def test_open_refresh_refuses_a_malformed_replacement_value(base_graph):
    """Review C3 (the reviewer's exact probe): a `replacements` value that isn't even a
    valid id must be caught before the SUSPECT transition, not after it — otherwise the
    prior is left stranded `SUSPECT` with no successor, the same failure mode C2's fix
    was written to eliminate, reached through a different unvalidated input."""
    g = base_graph
    put_all(g, _obj_asm("as-manning-feb", "minimal crew"),
            {**episode(), "rev": 2, "lifecycleState": "SIGNED",
             "assumptions": ["as-manning-feb"]},
            obj("prg-14", "DecisionProgram", name="p14", charter="ch-1",
                episodes=["ep-1"], refreshTriggers=[], diffs=[]),
            obj("rt-14", "RefreshTrigger", kind="assumption-changed", source="s",
                description="d", detectedAt="2026-09-01", affected=["as-manning-feb"]))
    log_len_before = len(g.log())
    with pytest.raises(ValidationError):
        open_refresh(g, "prg-14", "rt-14", actor=H, now=NOW,
                      replacements={"as-manning-feb": "not a valid id!!"})
    assert g.get("ep-1")["lifecycleState"] == "SIGNED"
    assert len(g.log()) == log_len_before


def test_open_refresh_refuses_a_replacement_value_not_in_the_graph(base_graph):
    """A well-formed id that names nothing in the graph must also be refused before the
    SUSPECT transition — well-formedness alone isn't enough."""
    g = base_graph
    put_all(g, _obj_asm("as-manning-feb", "minimal crew"),
            {**episode(), "rev": 2, "lifecycleState": "SIGNED",
             "assumptions": ["as-manning-feb"]},
            obj("prg-15", "DecisionProgram", name="p15", charter="ch-1",
                episodes=["ep-1"], refreshTriggers=[], diffs=[]),
            obj("rt-15", "RefreshTrigger", kind="assumption-changed", source="s",
                description="d", detectedAt="2026-09-01", affected=["as-manning-feb"]))
    log_len_before = len(g.log())
    with pytest.raises(ValidationError):
        open_refresh(g, "prg-15", "rt-15", actor=H, now=NOW,
                      replacements={"as-manning-feb": "as-does-not-exist"})
    assert g.get("ep-1")["lifecycleState"] == "SIGNED"
    assert len(g.log()) == log_len_before


def test_open_refresh_refuses_a_replacement_key_the_prior_does_not_reference(base_graph):
    """A key that exists in the graph and is well-formed, but that the prior episode
    doesn't actually reference (directly or transitively), isn't a replacement at all —
    just an unrelated pair riding along in the map. Must be refused before the SUSPECT
    transition, same as the other two malformed-`replacements` cases."""
    g = base_graph
    put_all(g, _obj_asm("as-manning-feb", "minimal crew"),
            _obj_asm("as-unrelated", "not referenced by ep-1 at all"),
            {**episode(), "rev": 2, "lifecycleState": "SIGNED",
             "assumptions": ["as-manning-feb"]},
            obj("prg-16", "DecisionProgram", name="p16", charter="ch-1",
                episodes=["ep-1"], refreshTriggers=[], diffs=[]),
            obj("rt-16", "RefreshTrigger", kind="assumption-changed", source="s",
                description="d", detectedAt="2026-09-01", affected=["as-unrelated"]))
    log_len_before = len(g.log())
    with pytest.raises(ValidationError):
        open_refresh(g, "prg-16", "rt-16", actor=H, now=NOW,
                      replacements={"as-unrelated": "as-manning-feb"})
    assert g.get("ep-1")["lifecycleState"] == "SIGNED"
    assert len(g.log()) == log_len_before


def test_open_refresh_does_not_carry_computed_bias_risks_forward(base_graph):
    """A bias indicator the kernel computed for episode N is a fact about episode N.

    `bias_indicators` writes its findings as `Risk` objects under the kernel actor and
    appends them to the episode's `risks`. Before this, `risks` was carried forward like
    any other reference list, so after five refreshes a 2023 episode's `risks` held five
    `bias-selection` indicators computed in 2020, 2021 and 2022 — and any consumer
    reading `episode.risks` would report them as that episode's. The successor recomputes
    its own indicators from its own model; a Risk a *human* recorded is a statement about
    the decision and still carries forward.
    """
    g = base_graph
    put_all(
        g,
        _obj_asm("as-manning-feb", "minimal crew"),
        obj("rsk-human", "Risk", statement="the bridge population may not generalise",
            kind="data", consequence="the weight threshold is set against the wrong set",
            owner="unassigned", status="open", evidence=["ev-doc"]),
        # `ev-doc` sits in the register and no claim cites it, which is the
        # `silent-omission` that makes `_selection` fire.
        {**episode(), "rev": 2, "lifecycleState": "SIGNED",
         "assumptions": ["as-manning-feb"], "evidenceRegister": ["ev-doc"],
         "risks": ["rsk-human"]},
        obj("prg-17", "DecisionProgram", name="p17", charter="ch-1", episodes=["ep-1"],
            refreshTriggers=[], diffs=[]),
        obj("rt-17", "RefreshTrigger", kind="assumption-changed", source="s",
            description="d", detectedAt="2026-09-01", affected=["as-manning-feb"]),
    )
    computed = bias_indicators(g, "ep-1", now=NOW)
    assert [r["id"] for r in computed] == ["risk-bias-ep-1-selection"]
    assert g.get("ep-1")["risks"] == ["rsk-human", "risk-bias-ep-1-selection"]

    new = open_refresh(g, "prg-17", "rt-17", actor=H, now=NOW)
    assert "risk-bias-ep-1-selection" not in new["risks"]
    assert new["risks"] == ["rsk-human"]
    # The indicator is still on the episode it was computed for.
    assert "risk-bias-ep-1-selection" in g.get("ep-1")["risks"]
    # And the successor computes its own, under its own id.
    again = bias_indicators(g, new["id"], now=NOW)
    assert [r["id"] for r in again] == [f"risk-bias-{new['id']}-selection"]
    assert g.get(new["id"])["risks"] == ["rsk-human", f"risk-bias-{new['id']}-selection"]


# ---- plan 2026-09-11: send back with a named reason -----------------------------------

def _pending(g):
    ep = g.get("ep-1")
    g.put({**{k: v for k, v in ep.items() if k != "commitment"}, "rev": ep["rev"] + 1,
           "createdBy": H, "createdAt": NOW, "lifecycleState": "PENDING_SIGNATURE"}, H)
    return g


def test_signer_return_files_a_human_trigger_naming_the_episode():
    from docket.kernel.refresh import signer_return
    from tests.kernel.conftest import complete_graph, program_

    g = _pending(complete_graph())
    put_all(g, program_("prg-1", episodes=["ep-1"]))
    head = len(g.log())
    t = signer_return(g, "ep-1", actor=H, now="2026-09-11T00:00:00Z",
                      reason="the conditions are not specific enough to check")
    assert t["id"] == "rt-return-ep-1-1" and t["kind"] == "signer-return"
    assert t["affected"] == ["ep-1"] and t["source"] == "fixture"
    assert t["description"] == "the conditions are not specific enough to check"
    assert t["createdBy"] == H
    assert "rt-return-ep-1-1" in g.get("prg-1")["refreshTriggers"]
    assert len(g.log()) == head + 2          # the trigger and the programme revision
    # The episode names *itself* as affected, and `reachable_from` walks referrers and
    # drops the seed, so this trigger reaches no episode at all — which is exactly why
    # the queue and the clock find send-backs by kind and `affected` membership
    # (`clock.signed_return_triggers`) rather than through `affected_episodes`.
    assert affected_episodes(g, t["id"]) == set()
    second = signer_return(g, "ep-1", actor=H, now="2026-09-12T00:00:00Z", reason="again")
    assert second["id"] == "rt-return-ep-1-2"


def test_signer_return_refuses_an_agent_a_blank_reason_and_a_wrong_state():
    from docket.kernel.refresh import signer_return
    from tests.kernel.conftest import complete_graph

    g = complete_graph()
    with pytest.raises(ValidationError):        # PLAN_APPROVED, not PENDING_SIGNATURE
        signer_return(g, "ep-1", actor=H, now=NOW, reason="x")
    g = _pending(g)
    with pytest.raises(AuthorityViolation):
        signer_return(g, "ep-1", actor={"actorType": "agent", "actorId": "agent:x"},
                      now=NOW, reason="x")
    with pytest.raises(ValidationError):
        signer_return(g, "ep-1", actor=H, now=NOW, reason="   ")


def test_signer_return_refuses_a_signed_package():
    """Once it is signed, the way back is a refresh — nothing here rewrites the record."""
    from docket.kernel.refresh import signer_return
    from tests.kernel.conftest import complete_graph

    g = complete_graph()                       # carries its Commitment, cm-1
    ep = g.get("ep-1")
    g.put({**ep, "rev": ep["rev"] + 1, "createdBy": H, "createdAt": NOW,
           "lifecycleState": "SIGNED"}, H)
    with pytest.raises(ValidationError):
        signer_return(g, "ep-1", actor=H, now=NOW, reason="the conditions are too loose")
    assert g.all("RefreshTrigger") == []


def test_signer_return_counts_only_this_episodes_own_returns():
    """`rt-return-ep-1-` followed by digits only, closed the way `commit` closes its own
    counter: a send-back filed against a prefix-sharing episode (`ep-1-r2`) is not this
    episode's, and counting it would mint an id that collides with that episode's next
    return."""
    from docket.kernel.refresh import signer_return
    from tests.kernel.conftest import complete_graph

    g = _pending(complete_graph())
    put_all(g, obj("rt-return-ep-1-r2-1", "RefreshTrigger", kind="signer-return",
                   source="another signer", description="a different episode's return",
                   detectedAt=NOW, affected=["ep-1-r2"]))
    t = signer_return(g, "ep-1", actor=H, now=NOW, reason="the cost basis needs a source")
    assert t["id"] == "rt-return-ep-1-1"


def test_signer_return_refuses_an_actor_with_no_id():
    """`source` names who returned the package; a nameless actor would record "None"."""
    from docket.kernel.refresh import signer_return
    from tests.kernel.conftest import complete_graph

    g = _pending(complete_graph())
    with pytest.raises(ValidationError) as raised:
        signer_return(g, "ep-1", actor={"actorType": "human"}, now=NOW, reason="x")
    assert any("actorId" in str(e) for e in raised.value.errors)
    assert g.all("RefreshTrigger") == []
