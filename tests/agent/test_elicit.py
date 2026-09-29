import re
from pathlib import Path

import pytest

from docket.agent.backend import RecordedBackend
from docket.agent.elicit import ELICITATION_SCHEMA, elicit, elicit_into, slug
from docket.errors import AuthorityViolation, BackendError, ValidationError
from docket.objects import is_gap_ref
from docket.schema import validate_object
from docket.store import Graph
from tests.kernel.conftest import H, charter, policy

A = {"actorType": "agent", "actorId": "agent:recorded"}
REQ = Path("tests/fixtures/requests/omfv-con-2020-02-25.md").read_text()
SRC = "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md"
COMMON = dict(request_text=REQ, policy_id="pol-1", actor=A, now="2026-09-04T00:00:00Z",
              source_artifact=SRC, requested_by="NGCV CFT")

# A second, wholly unrelated synthetic request: the model gives no `isSourceArtifact: true`
# evidence item at all, exercising the source-artefact synthesis path (I3/M8) and doubling as
# the "different elicitation into the same graph" case for I1's positive probe.
NO_SRC_REQ = "A minimal synthetic request used only to exercise the no-source-item code path."
NO_SRC_ARTIFACT = "synthetic/no-source-item-test.md"
NO_SRC_COMMON = dict(request_text=NO_SRC_REQ, policy_id="pol-1", actor=A,
                     now="2026-09-04T00:00:00Z", source_artifact=NO_SRC_ARTIFACT,
                     requested_by="Someone")

# A response that will never validate against ELICITATION_SCHEMA, for the BackendError path.
FAIL_REQ = ("A request whose elicitation response will always fail schema validation, for "
            "testing BackendError.")
FAIL_ARTIFACT = "synthetic/always-invalid-test.md"
FAIL_COMMON = dict(request_text=FAIL_REQ, policy_id="pol-1", actor=A,
                   now="2026-09-04T00:00:00Z", source_artifact=FAIL_ARTIFACT,
                   requested_by="Someone")

# Two gaps[] entries sharing one owner, for I2.
DUP_REQ = "A minimal synthetic request used only to exercise duplicate-owner gap handling."
DUP_ARTIFACT = "synthetic/duplicate-gap-owner-test.md"
DUP_COMMON = dict(request_text=DUP_REQ, policy_id="pol-1", actor=A,
                  now="2026-09-04T00:00:00Z", source_artifact=DUP_ARTIFACT,
                  requested_by="Someone")


def test_slug():
    assert slug("Survivability (CBRN)") == "survivability-cbrn"


def test_slug_dedupes_on_the_40_char_truncation():
    from docket.agent.elicit import _unique

    used: set[str] = set()
    long_a = "Survivability of the crew and dismounted infantry under CBRN attack"
    long_b = "Survivability of the crew and dismounted infantry under direct fire"
    assert _unique("obj-", long_a, used) != _unique("obj-", long_b, used)


def test_elicit_maps_recorded_response_to_valid_draft_objects():
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    objs = elicit(b, **COMMON)
    for o in objs:
        assert validate_object(o) == [], (o["id"], validate_object(o))
        assert o["createdBy"] == A
        assert o["ingestionProvenance"]["extractor"].startswith("recorded")
        assert o["ingestionProvenance"]["sourceArtifact"] == SRC
        assert o["rev"] == 1
    types = [o["type"] for o in objs]
    assert types.count("Objective") == 9 and "Charter" in types
    assert "InsufficientEvidence" in types
    ch = next(o for o in objs if o["type"] == "Charter")
    assert is_gap_ref(ch["consequencesOfErroneousOutput"])   # the notice states no consequence
    assert ch["authority"]["signer"] == "NGCV CFT"           # caller, not the model [R4]
    assert ch["decisionClassPolicy"] == "pol-1"
    linch = [o for o in objs if o["type"] == "Assumption" and o["linchpin"]]
    assert linch and is_gap_ref(linch[0]["evidence"])
    assert all(o["variedInSensitivity"] is False
               for o in objs if o["type"] == "Assumption")   # [R4] constant, never claimed
    assert any(o.get("confidence") == "inferred" for o in objs)
    assert all(o["reviewStatus"] == "draft"
               for o in objs if o["type"] == "Evidence")
    assert all("confirmedBy" not in o
               for o in objs if o["type"] == "InsufficientEvidence")
    # every gap marker resolves to a gap object that is actually emitted
    gap_ids = {o["id"] for o in objs if o["type"] == "InsufficientEvidence"}
    for o in objs:
        for v in o.values():
            if is_gap_ref(v):
                assert v["$gap"] in gap_ids, (o["id"], v)


def test_priority_convention_and_rating_relevant_fields():
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    objs = elicit(b, **COMMON)
    objectives = [o for o in objs if o["type"] == "Objective"]
    for o in objectives:
        want = "primary" if o.get("priorityRank", 99) <= 3 else "secondary"
        assert o["priority"] == want


def test_elicit_into_creates_draft_episode_and_store_accepts_agent_objects():
    g = Graph()
    g.put(policy(), H)
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    ep = elicit_into(g, b, episode_id="ep-omfv-con", **COMMON)
    assert ep["lifecycleState"] == "DRAFT" and ep["transitions"] == []
    assert len(ep["objectives"]) == 9 and g.has(ep["charter"])
    assert ep["sequence"] == 1 and ep["asOf"] == "2026-09-04T00:00:00Z"
    assert all(g.get(e)["reviewStatus"] == "draft" for e in ep["evidenceRegister"])
    assert ELICITATION_SCHEMA["required"] == ["charter", "objectives", "alternatives",
                                              "groundRules", "constraints", "assumptions",
                                              "evidence", "gaps"]
    # M1: the episode itself carries ingestionProvenance like every other DRAFT object.
    assert ep["ingestionProvenance"]["sourceArtifact"] == SRC
    assert ep["ingestionProvenance"]["locator"] == "(no locator given)"


def test_elicit_refuses_a_human_actor():
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    with pytest.raises(AuthorityViolation):
        elicit(b, **{**COMMON, "actor": H})


def test_elicit_refuses_an_actor_id_not_prefixed_agent():
    """M7: the ledger's `agent:<model>` actor-id convention is enforced, not just assumed."""
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    bad_actor = {"actorType": "agent", "actorId": "recorded"}  # missing the "agent:" prefix
    with pytest.raises(AuthorityViolation):
        elicit(b, **{**COMMON, "actor": bad_actor})


def test_elicit_refuses_a_blank_requested_by():
    """M6: a blank `requested_by` would otherwise land as Charter.authority.signer == ""."""
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    with pytest.raises(ValidationError):
        elicit(b, **{**COMMON, "requested_by": "  "})


def test_elicit_into_is_not_rerunnable_against_the_same_graph():
    """`elicit()` is deterministic (same ids from the same input); `elicit_into()` refuses,
    all-or-nothing, before writing anything, when any generated id or the episode id already
    exists [ruling I1] — not a store-level failure partway through the write."""
    g = Graph()
    g.put(policy(), H)
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    elicit_into(g, b, episode_id="ep-omfv-con", **COMMON)
    ids_before = g.ids()
    with pytest.raises(ValidationError) as exc_info:
        elicit_into(g, b, episode_id="ep-omfv-con", **COMMON)
    assert "ep-omfv-con" in str(exc_info.value)
    assert g.ids() == ids_before  # nothing new written


def test_elicit_into_names_the_referencing_episode_on_a_content_id_collision():
    """A second elicitation of the SAME request under a DIFFERENT episode id still collides
    on the slug-derived ids (Charter, Objective, ..., the source Evidence) — those are not
    episode-scoped — and the refusal names the episode that already references them."""
    g = Graph()
    g.put(policy(), H)
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    elicit_into(g, b, episode_id="ep-omfv-con", **COMMON)
    ids_before = g.ids()
    with pytest.raises(ValidationError) as exc_info:
        elicit_into(g, b, episode_id="ep-omfv-con-again", **COMMON)
    assert "ep-omfv-con" in str(exc_info.value)
    assert g.ids() == ids_before


def test_elicit_into_a_second_different_elicitation_into_the_same_graph_succeeds():
    """The positive half of I1's probe: two genuinely different elicitations (different
    request, different source artefact) into one graph do not collide, because the purely
    ordinal ids (`gap-`, `gr-`, `con-`) are scoped by episode id."""
    g = Graph()
    g.put(policy(), H)
    b1 = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    ep1 = elicit_into(g, b1, episode_id="ep-omfv-con", **COMMON)
    b2 = RecordedBackend(Path("tests/fixtures/recorded/elicit-no-source-item.json"))
    ep2 = elicit_into(g, b2, episode_id="ep-synthetic-test", **NO_SRC_COMMON)
    assert g.has(ep1["id"]) and g.has(ep2["id"])
    # each episode has its own "gap-1" under its own prefix, coexisting in the same graph
    assert g.has("ep-omfv-con-gap-1")
    assert g.has("ep-synthetic-test-gap-1")


def test_elicit_into_refuses_all_or_nothing_on_a_preseeded_collision():
    """I1 probe (b): pre-seeding a graph with only the Charter that `elicit_into` would mint,
    then calling `elicit_into`, is refused before anything is written — no orphan objects,
    no episode, log/ids unchanged."""
    g = Graph()
    g.put(policy(), H)
    charter_id = "ch-" + slug("What characteristics should the OMFV have?")
    g.put(charter(oid=charter_id), H)
    ids_before = g.ids()
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit.json"))
    with pytest.raises(ValidationError) as exc_info:
        elicit_into(g, b, episode_id="ep-omfv-con", **COMMON)
    assert charter_id in str(exc_info.value)
    assert g.ids() == ids_before


def test_elicit_synthesises_source_evidence_when_the_model_omits_it():
    """I3/M8: the model's response has no `isSourceArtifact: true` item at all; the
    source-artefact Evidence is built entirely from caller-supplied, documented defaults,
    including its type (`source_evidence_type`, default `"Document"`)."""
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit-no-source-item.json"))
    objs = elicit(b, **NO_SRC_COMMON, source_title="Fallback Title",
                  source_classification="CUI")
    for o in objs:
        assert validate_object(o) == [], (o["id"], validate_object(o))
    src = next(o for o in objs if o["type"] == "Evidence")
    assert src["id"] == "ev-src-no-source-item-test"
    assert src["title"] == "Fallback Title"
    assert src["evidenceType"] == "Document"
    assert src["classification"] == {"level": "CUI", "metadataLevel": "CUI"}
    assert is_gap_ref(src["scopeOfValidity"])
    assert is_gap_ref(src["reliabilitySteps"])
    assert is_gap_ref(src["publisher"])
    assert is_gap_ref(src["published"])
    # Objective/GroundRule/Constraint provenance still resolves — no request had any of
    # these here, but the response's Charter is content, proving the rest of the mapper
    # runs normally around a fully-synthesised source item.
    assert "Charter" in [o["type"] for o in objs]


def test_elicit_into_raises_backend_error_after_exhausted_retries_and_writes_nothing():
    """M8: a response that never validates exhausts `complete_json`'s retries and raises
    `BackendError` — not `RecordingMissing` (a `BackendError` subclass, and the trap this
    guards against), and nothing is written to the graph."""
    g = Graph()
    g.put(policy(), H)
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit-failure.json"))
    with pytest.raises(BackendError) as exc_info:
        elicit_into(g, b, episode_id="ep-fail", **FAIL_COMMON)
    assert type(exc_info.value) is BackendError
    assert g.ids() == ["pol-1"]


def test_gaps_never_dropped_a_second_entry_sharing_an_owner_is_emitted_unattached():
    """I2: `gap_lookup` is owner -> list; the head is consumed by the matching field, and
    every remaining entry on that owner is still emitted, unattached, with the owner named
    in `whyNotFound` [M3]."""
    b = RecordedBackend(Path("tests/fixtures/recorded/elicit-duplicate-gap.json"))
    objs = elicit(b, **DUP_COMMON)
    gaps = [o for o in objs if o["type"] == "InsufficientEvidence"]
    # the source Evidence's reliabilitySteps is always gapped too (unrelated to this test);
    # only assert on the two duplicate-owner entries.
    sought = {g["sought"] for g in gaps}
    assert {"FIRST duplicate-owner entry", "SECOND duplicate-owner entry"} <= sought
    consumed = next(g for g in gaps if g["sought"] == "FIRST duplicate-owner entry")
    unattached = next(g for g in gaps if g["sought"] == "SECOND duplicate-owner entry")
    assert unattached["whyNotFound"] == (
        "second reason (model routed this to 'charter.consequencesOfErroneousOutput', "
        "which matched no field)"
    )
    ch = next(o for o in objs if o["type"] == "Charter")
    assert ch["consequencesOfErroneousOutput"] == {"$gap": consumed["id"]}


# ---- Carried from the T2 re-review: the prompt's "You fill:" lines and the schema agree ----

PROMPT_PATH = Path("src/docket/agent/prompts/object-typing.md")

# Heading (as it appears right after "## ", before " — ") -> the ELICITATION_SCHEMA content
# keys the model fills for that catalogue type. `confidence`/`locator` are the per-item
# envelope tags every block carries and are not named in a "You fill:" sentence, so they are
# excluded from both directions of the comparison.
_ENVELOPE_ONLY = {"confidence", "locator"}


def _content_keys(properties: dict) -> set[str]:
    return set(properties) - _ENVELOPE_ONLY


def _schema_keys_by_heading() -> dict[str, set[str]]:
    p = ELICITATION_SCHEMA["properties"]
    return {
        "Charter": _content_keys(p["charter"]["properties"]),
        "Objective": _content_keys(p["objectives"]["items"]["properties"]),
        "Alternative": _content_keys(p["alternatives"]["items"]["properties"]),
        "GroundRule": _content_keys(p["groundRules"]["items"]["properties"]),
        "Constraint": _content_keys(p["constraints"]["items"]["properties"]),
        "Assumption": _content_keys(p["assumptions"]["items"]["properties"]),
        "Evidence": _content_keys(p["evidence"]["items"]["properties"]),
        "InsufficientEvidence": _content_keys(p["gaps"]["items"]["properties"]),
    }


def _you_fill_sentence_by_heading(text: str) -> dict[str, str]:
    """Heading -> the text of its `You fill:` sentence (up to, not including, the first
    following period)."""
    sentences: dict[str, str] = {}
    for section in re.split(r"\n## ", text):
        heading = section.split("\n", 1)[0].split(" — ")[0].strip("# ").strip()
        m = re.search(r"You fill:(.*?)\.", section, re.DOTALL)
        if m is not None:
            sentences[heading] = m.group(1)
    return sentences


def _keys_in(text: str) -> set[str]:
    return set(re.findall(r"`([a-zA-Z][a-zA-Z0-9_]*)`", text))


# M4: the GroundRule/Constraint/Assumption guideline covers all three types in ONE "You
# fill:" sentence ("for a ground rule, ...; for a constraint, ...; for an assumption, ...").
# Checking that sentence's keys against the UNION of the three schema blocks cannot catch a
# key attributed to the wrong type of the three (e.g. `kind` moved into the assumption
# clause) — so each clause is split out and checked against its own block individually.
_GRCA_HEADING = "GroundRule, Constraint, Assumption"
_GRCA_CLAUSE_RE = re.compile(
    r"for a ground rule,(?P<GroundRule>.*?);\s*"
    r"for a constraint,(?P<Constraint>.*?);\s*"
    r"for an assumption,(?P<Assumption>.*)",
    re.DOTALL,
)


def test_every_you_fill_key_is_an_elicitation_schema_key():
    schema_keys = _schema_keys_by_heading()
    text = PROMPT_PATH.read_text()
    sentences = _you_fill_sentence_by_heading(text)

    assert _GRCA_HEADING in sentences, f"{_GRCA_HEADING} has no 'You fill:' sentence"
    clause_match = _GRCA_CLAUSE_RE.search(sentences[_GRCA_HEADING])
    assert clause_match, (
        "the GroundRule/Constraint/Assumption 'You fill:' sentence no longer splits into "
        "the three expected 'for a ground rule,'/'for a constraint,'/'for an assumption,' "
        "clauses"
    )

    for heading, keys in schema_keys.items():
        if heading in ("GroundRule", "Constraint", "Assumption"):
            found = _keys_in(clause_match.group(heading))
        else:
            assert heading in sentences, (
                f"{heading} has no 'You fill:' sentence in {PROMPT_PATH}"
            )
            found = _keys_in(sentences[heading])
        assert keys, f"no ELICITATION_SCHEMA content keys found for {heading}"
        extra = found - keys
        assert not extra, f"{heading}: You fill: names {extra}, not an ELICITATION_SCHEMA key"
        # the reverse direction: every schema key the model must fill is named somewhere
        missing = keys - found
        assert not missing, f"{heading}: ELICITATION_SCHEMA has {missing}, not in 'You fill:'"
