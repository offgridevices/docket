"""`kernel.commit.sign` — the signature as a record object, bound to the package."""
import pytest

from docket.errors import AuthorityViolation, TransitionRefused, ValidationError
from docket.kernel.commit import sign
from docket.kernel.queue import needs
from docket.kernel.refresh import signer_return
from docket.kernel.render import build_package, latest_package_hash
from docket.store import Graph
from tests.kernel.conftest import (
    pending_signature_and_ready,
    readiness_report,
)

HUMAN = {"actorType": "human", "actorId": "shreyash"}
AGENT = {"actorType": "agent", "actorId": "gpt-test"}
NOW = "2013-05-01T00:00:00Z"
LATER = "2013-05-02T00:00:00Z"


@pytest.fixture
def demo_a(demo_a_graph: Graph) -> Graph:
    return demo_a_graph


def test_sign_writes_commitment_and_moves_to_signed(demo_a, tmp_path):
    build_package(demo_a, "ep-cbo-2013", rendering="full", now=NOW, out_dir=tmp_path)
    cm = sign(demo_a, "ep-cbo-2013", actor=HUMAN, now=NOW, selected="alt-gcv",
              role="Milestone Decision Authority",
              stop_rules=["Stop if unit cost exceeds the ceiling."])
    ep = demo_a.get("ep-cbo-2013")
    assert ep["lifecycleState"] == "SIGNED"
    assert ep["commitment"] == cm["id"] == "cm-ep-cbo-2013-1"
    assert cm["createdBy"] == HUMAN
    assert cm["signer"] == {"identity": "shreyash", "role": "Milestone Decision Authority"}
    assert cm["packageHash"] == latest_package_hash(demo_a, "ep-cbo-2013", rendering="full")
    assert ep["transitions"][-1]["to"] == "SIGNED"
    assert ep["transitions"][-1]["refused"] is False


def test_sign_refuses_without_a_full_package(two_alt_graph):
    """Demo A's committed store already ships a full package (`pkg-ep-cbo-2013-full-1`), so
    the refusal is proved on the shared fixture carried to PENDING_SIGNATURE with nothing
    rendered."""
    g = pending_signature_and_ready(two_alt_graph)
    assert latest_package_hash(g, "ep-1", rendering="full") is None
    with pytest.raises(ValidationError, match="rendered full package"):
        sign(g, "ep-1", actor=HUMAN, now=NOW, selected="alt-x", role="MDA", stop_rules=["x"])
    assert g.get("ep-1")["lifecycleState"] == "PENDING_SIGNATURE"
    assert not g.all("Commitment")


def test_sign_refuses_unknown_option_empty_stop_rules_and_agents(demo_a, tmp_path):
    build_package(demo_a, "ep-cbo-2013", rendering="full", now=NOW, out_dir=tmp_path)
    with pytest.raises(ValidationError, match="not one of this decision's options"):
        sign(demo_a, "ep-cbo-2013", actor=HUMAN, now=NOW, selected="alt-nope", role="MDA",
             stop_rules=["x"])
    with pytest.raises(ValidationError, match="at least one stop rule"):
        sign(demo_a, "ep-cbo-2013", actor=HUMAN, now=NOW, selected="alt-gcv", role="MDA",
             stop_rules=[])
    with pytest.raises(AuthorityViolation):
        sign(demo_a, "ep-cbo-2013", actor=AGENT, now=NOW, selected="alt-gcv", role="MDA",
             stop_rules=["x"])


def test_sign_refuses_an_actor_with_no_id(demo_a, tmp_path):
    """`signer.identity` is who committed, printed on the package and in the activity log;
    a nameless actor would record the string "None" and read as a person called None. The
    same silent stringification `refresh.signer_return` refuses for `source`."""
    build_package(demo_a, "ep-cbo-2013", rendering="full", now=NOW, out_dir=tmp_path)
    with pytest.raises(ValidationError) as raised:
        sign(demo_a, "ep-cbo-2013", actor={"actorType": "human"}, now=NOW,
             selected="alt-gcv", role="MDA", stop_rules=["x"])
    # The module's own refusal, in its own words, raised before anything is composed —
    # not the store's schema error on a `createdBy` it was handed anyway.
    assert any("records by name who committed" in str(e) for e in raised.value.errors)
    assert not demo_a.all("Commitment")
    assert demo_a.get("ep-cbo-2013")["lifecycleState"] == "PENDING_SIGNATURE"


def test_sign_refuses_when_not_pending_signature(demo_b_graph, tmp_path):
    with pytest.raises(ValidationError, match="PLAN_APPROVED"):
        sign(demo_b_graph, "ep-omfv-2020-02-r5", actor=HUMAN, now=NOW, selected="alt-x",
             role="MDA", stop_rules=["x"])


def test_sign_counts_only_this_episodes_own_commitments(two_alt_graph, tmp_path):
    """`cm-ep-1-` followed by digits only: a commitment filed under a prefix-sharing
    episode id (`ep-1-r2`) is not this episode's, and must not be counted as one."""
    g = pending_signature_and_ready(two_alt_graph)
    pkg, _ = build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path)
    g.put({"id": "cm-ep-1-r2-1", "type": "Commitment", "rev": 1, "createdBy": HUMAN,
           "createdAt": NOW, "episode": "ep-1", "selected": "alt-x",
           "signer": {"identity": "someone", "role": "r"}, "signedAt": NOW,
           "conditions": [], "stopRules": ["x"], "packageHash": pkg["hash"]}, HUMAN)
    cm = sign(g, "ep-1", actor=HUMAN, now=NOW, selected="alt-x", role="MDA", stop_rules=["x"])
    assert cm["id"] == "cm-ep-1-1"


def test_a_refused_sign_restores_the_commitment_pointer_and_a_later_sign_binds(
    two_alt_graph, tmp_path,
):
    """The gate refuses (`readiness-ready`): the Commitment and the refused transition stay
    on the record, but `episode.commitment` goes back to what it was — so the queue still
    lists the signature and the next package does not print a decision nobody took. A
    later, valid signature mints `cm-ep-1-2` and binds to the latest full package."""
    g = pending_signature_and_ready(two_alt_graph, ready=False)
    build_package(g, "ep-1", rendering="full", now=NOW, out_dir=tmp_path / "v1")
    with pytest.raises(TransitionRefused) as refused:
        sign(g, "ep-1", actor=HUMAN, now=NOW, selected="alt-x", role="MDA", stop_rules=["x"])
    assert refused.value.unsatisfied == ["readiness-ready"]
    ep = g.get("ep-1")
    assert ep["lifecycleState"] == "PENDING_SIGNATURE"
    assert "commitment" not in ep
    assert ep["transitions"][-1]["to"] == "SIGNED" and ep["transitions"][-1]["refused"] is True
    assert g.has("cm-ep-1-1")
    assert [i["kind"] for i in needs(g, "ep-1", now=NOW)["items"] if i["kind"] == "signature"] \
        == ["signature"]

    readiness_report(g, ready=True, n=2)
    build_package(g, "ep-1", rendering="full", now=LATER, out_dir=tmp_path / "v2")
    cm = sign(g, "ep-1", actor=HUMAN, now=LATER, selected="alt-x", role="MDA", stop_rules=["x"])
    ep = g.get("ep-1")
    assert cm["id"] == "cm-ep-1-2" and ep["commitment"] == "cm-ep-1-2"
    assert ep["lifecycleState"] == "SIGNED"
    assert cm["packageHash"] == latest_package_hash(g, "ep-1", rendering="full")


def test_sign_refuses_while_a_send_back_stands(demo_a, tmp_path):
    """The same predicate the queue uses for its `sent-back` item: a signer-return newer
    than the latest full package, not yet opened as a refresh, closes the gate up front."""
    build_package(demo_a, "ep-cbo-2013", rendering="full", now=NOW, out_dir=tmp_path)
    signer_return(demo_a, "ep-cbo-2013", actor=HUMAN, now=LATER, reason="the cost section is stale")
    assert any(i["kind"] == "sent-back" for i in needs(demo_a, "ep-cbo-2013", now=LATER)["items"])
    with pytest.raises(ValidationError, match="sent back for rework; answer the return"):
        sign(demo_a, "ep-cbo-2013", actor=HUMAN, now=LATER, selected="alt-gcv", role="MDA",
             stop_rules=["x"])
    assert demo_a.get("ep-cbo-2013")["lifecycleState"] == "PENDING_SIGNATURE"
    assert not demo_a.all("Commitment")
