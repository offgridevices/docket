"""Deterministic Decision Package renderer (design §7.8, §10). Two renderings from one graph.

`render_package` walks the fixed §10 section order and prints, for each section, its
Narratives (citation-enforced) followed by a body assembled straight from the objects
the episode names. An empty section prints the typed `Exclusion` that targets it
(`target.kind == "Section"`, `target.label == <section key>`) if one exists, else the
literal "no objects filed" line — never silence. Design §10 numbers Cover as item 1 and
Machine annex as item 16; the printed headings leave Cover unnumbered and end at
"15. Machine annex" (plan 06 depends on this exact numbering) — every §10 item number in
this docstring and in review commentary is one higher than the heading actually printed.

**Citations.** Every Narrative sentence must name at least one object it cites, every
cited id must resolve, and every numeral the sentence prints must equal some numeric
leaf value (at any depth) inside one of the cited objects, skipping hash-shaped leaves so
a `runRecordHash` cannot smuggle an uncited number past the check — `check_citations`
says why when it does not. `render_package` raises `UncitedSentenceError` naming the
offending Narrative, the sentence's index and its text, rather than emit a page that
asserts a number nothing backs.

**Two renderings.** `rendering="full"` prints everything the graph holds.
`rendering="unclassified"` withholds any value whose *evidence classification level*
exceeds `U` — an aggregate Result tainted by even one non-U observation, an Observation
value itself, a Narrative sentence that cites any of those, the evidence register's
pointer/scope/review/reliability-step count when its *metadata* level exceeds `U` — and
says `[withheld: <level>]` (or, for a sentence, `_[sentence withheld: <level>]_`) in
place, never a blank cell and never the value itself.

**Independent of readiness.** Whether a run's seal verifies (`run-seal`) or its bound
inputs have moved since sealing (`run-inputs-changed`) is read live from `validate(g,
policy)` on every call, not from whatever `ReadinessReport` happens to be stored on the
episode — a package rendered before anyone runs `readiness_report` still tells the truth
about a tampered or stale run, and even prints live blocking findings in §10 when no
report exists yet. The weight-simplex robustness figure is the opposite case: it is
Monte Carlo output that only exists once `readiness_report` has computed a
`flipSummary`, so §8 prints it from the stored report — naming the run it describes and
any runs a multi-step plan left out — and, when the sealed run's inputs have moved far
enough that `flip_summary` itself refuses, prints the refusal (from the report's own
`run-stale`/`flip-summary-unavailable` blocker) instead of a robustness line, with a
badge on the per-parameter table above it naming which run its rows can no longer
reproduce — the table itself still comes from the always-current `FlipAnalysis` objects
on the episode.

**Idempotent re-rendering.** The Cover and Machine annex snapshot hash and object/log
counts are computed over the graph's *content* — every object except `DecisionPackage`
— because a `DecisionPackage` is an artefact of rendering, not part of the record it
renders. `build_package` stores that same value as `graphSnapshotHash`. Re-rendering an
otherwise-unchanged record at the same `now` therefore produces byte-identical text and
an identical package hash no matter how many packages already sit in the graph, which is
what keeps `kernel.lifecycle.c_commitment_hash` (G4) true after a benign re-render and
what plan 07's "identical bytes ✓" determinism button actually depends on.

**Phase I honesty, printed where it bites.** `refresh-log` states the diff's `pairing`
("replacements" or "unknown") and that judgments are compared by claim id only, not
content — the same limitation `docket.kernel.refresh` documents, restated here because
this is the page a reviewer actually reads. `readiness` prints a tailoring's own honesty
note verbatim (`load_tailoring(...)["note"]`) when it has one, e.g. gao-23-106549's
caveat that GAO published a 3×3 verdict grid and nine findings, not per-question labels,
so any per-question reading here is this project's own, not GAO's; it also prints the
GAO-11-82R rating-scale legend (level 4 is "indeterminate", not a failing grade) and the
stated aggregation rule, and qualifies "Ready" as "no blocking findings", never a claim
that the record meets the standard.

**Malformed tolerance.** This is the module most likely to be pointed at a hand-edited
or partially-built graph (the CLI, the plan-07 API), so every reference it follows —
the episode's charter and policy, and every id in every reference list — is resolved
before being followed and never assumed to exist; an id that does not resolve prints as
an explicit "unresolved"/"unavailable" marker naming the id, never a bare `KeyError`.

**The AI-assistance label** (Army CIO ADS-GOV-AI-024 ¶5.b(4)) is a standing Cover bullet
in both renderings, and the same fact as a structured `aiAssistance` block in the
Machine annex (`ai_assistance_summary`): the agent actor ids that authored anything
this episode reaches, the human actor ids behind its recorded G1/G2/G3 gate approvals
and its G4 refresh acceptance if it has one, and — read from the record, not asserted
from policy — whether an agent-authored `EvaluationRun` is reachable from it. No
citation: it is a record readout, not a narrative claim.
"""

from __future__ import annotations

import re
from pathlib import Path

from docket import KERNEL_ACTOR, KERNEL_VERSION
from docket.canon import canonical_json, content_hash, sha256_hex
from docket.errors import UncitedSentenceError, ValidationError
from docket.kernel.findings import Finding
from docket.kernel.validate import validate
from docket.objects import id_says_agent, is_content, is_exclusion_ref, is_gap_ref
from docket.standard import load_standard, load_tailoring
from docket.store import Graph

SECTIONS: list[tuple[str, str]] = [
    ("cover", "Cover"),
    ("problem-statement", "1. Problem statement (AR 5-11 ¶4-5b)"),
    ("mandate-elements", "2. Mandate elements"),
    ("objectives-and-measures", "3. Objectives and measures"),
    ("alternatives", "4. Alternatives"),
    ("grca", "5. Ground rules, constraints, assumptions"),
    ("evidence-register", "6. Evidence register"),
    ("evaluation-results", "7. Evaluation results"),
    ("what-flips", "8. What flips the decision"),
    ("bias-checks", "9. Bias checks"),
    ("readiness", "10. Readiness"),
    ("risks", "11. Risks"),
    ("refresh-log", "12. Refresh log"),
    ("commitment", "13. Commitment"),
    ("traceability", "14. Traceability matrix"),
    ("machine-annex", "15. Machine annex"),
]

NUM = re.compile(r"-?\d+(?:\.\d+)?")
_HEX_HASH = re.compile(r"^[0-9a-f]{32,}$")
NOT_STATED = "_[not stated]_"

# The three human gates that show up as a `DecisionEpisode.transitions` entry (design
# §5.2: G1 model approval, G2 plan approval, G3 package sign-off). `VOID` is human-only
# too but is the abandon edge, not an approval, so it is deliberately not a label here.
# G4 (refresh acceptance) never appears in `transitions` at all — see `_g4_gate`.
GATE_LABELS: dict[str, str] = {
    "MODEL_APPROVED": "G1", "PLAN_APPROVED": "G2", "SIGNED": "G3",
}


def _numbers_in(value: object) -> set[float]:
    """Every numeric leaf inside `value`, at any depth — dict values, list items, and
    numerals embedded in strings alike. Skips any dict key naming a hash (`*Hash`,
    `hash`, `outputHashes`) and any string that is itself a bare hex hash (32+ hex
    characters): a citation's numeral pool must not accept an arbitrary number just
    because it happens to appear as a substring of a `runRecordHash`/`inputsHash` the
    cited object also carries."""
    out: set[float] = set()
    if isinstance(value, bool):
        return out
    if isinstance(value, int | float):
        out.add(float(value))
    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and "hash" in k.lower():
                continue
            out |= _numbers_in(v)
    elif isinstance(value, list):
        for v in value:
            out |= _numbers_in(v)
    elif isinstance(value, str):
        if _HEX_HASH.match(value):
            return out
        out |= {float(m) for m in NUM.findall(value)}
    return out


def check_citations(g: Graph, narrative: dict) -> list[str]:
    """Every sentence must cite at least one id, every cited id must resolve, and every
    numeral the sentence prints must equal some numeric leaf value (rounded to the
    numeral's own precision) inside one of the cited objects. Returns error strings,
    each naming the sentence's index *and its text* (not the index alone, so a repair
    loop reading the error has something to act on); an empty list means the narrative
    may print as written."""
    errs: list[str] = []
    for i, s in enumerate(narrative.get("sentences") or []):
        text = s.get("text") if isinstance(s, dict) else None
        label = f"sentence {i} ({text!r})"
        cites = (s.get("cites") if isinstance(s, dict) else None) or []
        if not cites:
            errs.append(f"{label}: no citation")
            continue
        missing = [c for c in cites if not (isinstance(c, str) and g.has(c))]
        if missing:
            errs.append(f"{label}: unknown citation(s) {missing}")
            continue
        pool: set[float] = set()
        for c in cites:
            cited = {k: v for k, v in g.get(c).items() if k not in ("rev", "createdAt", "id")}
            pool |= _numbers_in(cited)
        for m in NUM.findall(text or ""):
            prec = len(m.split(".")[1]) if "." in m else 0
            val = float(m)
            if not any(round(p, prec) == val for p in pool):
                errs.append(f"{label}: numeral {m} not found in cited objects {cites}")
    return errs


def _slot(g: Graph, v: object, seen: set[str] | None = None) -> str:
    """A P3 slot's printable text: the typed exclusion or gap it holds, its content, or
    `NOT_STATED` when the slot holds neither — an empty required field must never print
    as a blank line, and an empty list must never print as though it were a deliberate
    "nothing to report" content marker.

    `seen`, when given, collects the id of every `Exclusion` this call prints — how
    `render_package` knows which typed exclusions the ordinary sections already
    showed, so the "Other exclusions on record" list (D1) names each Exclusion once,
    never twice.
    """
    if is_exclusion_ref(v):
        xid = v["$exclusion"]
        if seen is not None:
            seen.add(xid)
        x = _obj(g, xid)
        if x is None:
            return f"_[exclusion {xid} unresolved]_"
        return (
            f"**Excluded** ({x['reasonType']}; {x['authority']['who']}, "
            f"{x['authority']['date']}): {x['reason']}"
        )
    if is_gap_ref(v):
        gid = v["$gap"]
        x = _obj(g, gid)
        if x is None:
            return f"_[gap {gid} unresolved]_"
        where = ", ".join(x["whereLookedFor"])
        return (
            f"**Insufficient evidence** [{x['impact']}]: sought {x['sought']}; "
            f"looked in {where}; {x['whyNotFound']}"
        )
    if not is_content(v):
        return NOT_STATED
    if isinstance(v, list):
        return "; ".join(str(i) for i in v)
    if isinstance(v, dict):
        return canonical_json(v)
    return str(v)


def _withheld(g: Graph, ev_id: object, rendering: str) -> bool:
    """Whether a value backed by evidence `ev_id` must be hidden under `rendering`:
    only under `unclassified`, and only when the evidence's *value* classification
    (not its metadata level) is anything other than `U`."""
    if rendering == "full" or not isinstance(ev_id, str) or not g.has(ev_id):
        return False
    return g.get(ev_id)["classification"]["level"] != "U"


def _findings_for(findings: list[Finding], oid: str, rule: str) -> list[Finding]:
    return [f for f in findings if f.rule == rule and oid in f.objects]


# ---- tolerant reference resolution (malformed-graph safety; I8) ----------------------


def _obj(g: Graph, ref: object) -> dict | None:
    """The object `ref` names, or None — for any shape of `ref` at all. Same pattern as
    `readiness.py`'s own `_obj`: the renderer is the module most likely to be handed a
    hand-edited or partially-built graph, so every reference is resolved before being
    followed, never assumed."""
    if not isinstance(ref, str) or not g.has(ref):
        return None
    o = g.get(ref)
    return o if isinstance(o, dict) else None


def _ref_ids(ids: object) -> list[str]:
    """Every string entry of `ids`, in stored order, tolerant of `ids` not being a
    list at all."""
    return [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []


def _sorted_ref_ids(ids: object) -> list[str]:
    """`_ref_ids`, sorted — for the table sections whose text should not depend on the
    order the episode happens to list its references in (M2)."""
    return sorted(_ref_ids(ids))


def _each(g: Graph, ids: list[str]) -> list[tuple[str, dict | None]]:
    """`(id, object-or-None)` for every id in `ids`."""
    return [(i, _obj(g, i)) for i in ids]


def _cite_withheld_level(
    g: Graph, cite_id: object, rendering: str, obs_by_alt: dict[str, list[dict]],
) -> str | None:
    """The classification level that makes citing `cite_id` unsafe to quote verbatim
    under `rendering`, or `None` if this citation is not backed by anything withheld.

    Covers the shapes the withholding rule itself covers: an `Evidence` item cited
    directly, an `Observation` whose own value is withheld, and a `Result` tainted by
    a withheld `Observation` — for an aggregate `Result`, any observation behind the
    same alternative (the same taint rule `_evaluation_results_body` applies to the
    results table); for a **non-aggregate** `Result`, the one observation behind its
    own `(alternative, measure)` pair, since `evaluate()` stamps that Result's `raw`
    field with the untouched observation value — citing it is citing the observation
    in every way that matters to withholding, one object hop removed (R1). A citation
    of any other type (a `Claim`, a `FlipAnalysis`, an `EvaluationRun`...) is not
    itself a value the unclassified rendering withholds, so it is not flagged here.
    """
    if rendering == "full" or not isinstance(cite_id, str) or not g.has(cite_id):
        return None
    o = g.get(cite_id)
    t = o.get("type")
    if t == "Evidence":
        cls = o.get("classification")
        level = cls.get("level") if isinstance(cls, dict) else None
        return level if isinstance(level, str) and level != "U" else None
    if t == "Observation":
        ev = o.get("evidence")
        return g.get(ev)["classification"]["level"] if _withheld(g, ev, rendering) else None
    if t == "Result":
        alt_obs = obs_by_alt.get(o.get("alternative"), [])
        candidates = (
            alt_obs if o.get("aggregate")
            else [obs for obs in alt_obs if obs.get("measure") == o.get("measure")]
        )
        for obs in candidates:
            ev = obs.get("evidence")
            if _withheld(g, ev, rendering):
                return g.get(ev)["classification"]["level"]
    return None


def _content_snapshot(g: Graph) -> tuple[str, int, int]:
    """`(hash, object count, log-entry count)` over the graph's *content*: every object
    except `DecisionPackage`, and every log entry except one that wrote one.

    A `DecisionPackage` is an artefact of rendering, not part of the record it renders:
    including it would make re-rendering an unchanged record change the very snapshot
    hash and counts the Cover/annex print, which is what used to break
    `kernel.lifecycle.c_commitment_hash` (G4) and plan 07's determinism button after
    any benign re-render. `build_package` stores this exact value as
    `graphSnapshotHash`, so the value printed on the page and the value sealed in the
    package are always one value, and the two renderings of one graph print the same
    one.
    """
    ids = [i for i in g.ids() if g.get(i).get("type") != "DecisionPackage"]
    snapshot = content_hash([g.get(i) for i in ids])
    log_entries = sum(1 for e in g.log() if e.get("type") != "DecisionPackage")
    return snapshot, len(ids), log_entries


def content_snapshot_hash(g: Graph) -> str:
    """The public accessor for the hash `_content_snapshot` computes and
    `build_package` stores as `graphSnapshotHash` — every object except
    `DecisionPackage`.

    **R6: any caller comparing a live graph's snapshot against a stored
    `DecisionPackage.graphSnapshotHash` — plan 07's `/verify` handler in
    particular — must call this, never `g.snapshot_hash()`.** Since C2,
    `graphSnapshotHash` no longer means "the whole graph": it excludes package
    objects on purpose, so the two are hashes of two different views and will
    differ even on an untouched graph once a single package has been built.
    """
    snapshot, _, _ = _content_snapshot(g)
    return snapshot


# ---- small formatters -----------------------------------------------------------------


def rating_scale_legend() -> str:
    """The GAO-11-82R rating-scale sentence `_readiness_body` prints at the foot of
    every rendered package's Readiness section — public (plan 07 Task 7 fix round) so
    the API's `_readiness_view` can hand the UI the renderer's own sentence instead of
    a second, hand-copied constant in `ui/src/lib/captions.ts`. No output change: this
    is the same function under a name with no leading underscore, called the same way
    at its one call site below."""
    scale = load_standard()["rating_scale"]
    parts = "; ".join(f"{lvl['level']} {lvl['label']}" for lvl in scale["levels"])
    return f"Rating scale ({scale['source']}): {parts}."


def _criteria_text(g: Graph, criteria: object, seen: set[str] | None = None) -> str:
    """`Measure.criteria`: `objective X / threshold Y`, never raw JSON — this is a
    proposal-facing document, and a reader should not have to parse `{"objective":80,
    "threshold":50}` to know what it means."""
    if is_exclusion_ref(criteria) or is_gap_ref(criteria):
        return _slot(g, criteria, seen)
    if not is_content(criteria) or not isinstance(criteria, dict):
        return NOT_STATED
    parts = []
    if criteria.get("objective") is not None:
        parts.append(f"objective {criteria['objective']}")
    if criteria.get("threshold") is not None:
        parts.append(f"threshold {criteria['threshold']}")
    return " / ".join(parts) if parts else NOT_STATED


def _action_list_text(g: Graph, ids: object) -> str:
    """`Risk.mitigation`: each Action's description, or the bare id when an Action
    reference does not resolve."""
    ids = _ref_ids(ids)
    if not ids:
        return NOT_STATED
    parts = []
    for aid, a in _each(g, ids):
        parts.append(a["description"] if a is not None else f"{aid} (unresolved)")
    return "; ".join(parts)


# ---- AI-assistance label (Army CIO ADS-GOV-AI-024 ¶5.b(4)) ----------------------------


def _g4_gate(g: Graph, ep: dict) -> dict | None:
    """The G4 (refresh acceptance) human actor for this episode, or `None`.

    G4 never appears as a `DecisionEpisode.transitions` entry the way G1–G3 do —
    `kernel.refresh.open_refresh` requires a human actor and writes it directly onto
    the successor episode's own `createdBy` at that episode's first revision, not as
    a recorded transition on it — so it is read from `g.get(episode_id, rev=1)`
    rather than from `transitions`, and only when this episode is actually a
    refresh's successor (`refreshedBecause` present). A store that cannot produce
    that first revision (hand-edited, truncated history) reports no G4 rather than
    guessing.
    """
    episode_id = ep.get("id")
    if not is_content(ep.get("refreshedBecause")) or not isinstance(episode_id, str):
        return None
    try:
        rev1 = g.get(episode_id, rev=1)
    except KeyError:
        return None
    author = rev1.get("createdBy") if isinstance(rev1, dict) else None
    if not isinstance(author, dict) or author.get("actorType") != "human":
        return None
    return {"gate": "G4", "state": "refresh-accepted", "actorId": author.get("actorId"),
            "at": rev1.get("createdAt")}


def ai_assistance_summary(g: Graph, ep: dict) -> dict:
    """The record readout behind the AI-assistance label (Army CIO ADS-GOV-AI-024
    ¶5.b(4), read against the mapping in `docs/research/hai-guidance-mapping.md`).

    Every fact here is read from the stored graph, never asserted from policy — a
    hand-edited or forged store shows up honestly rather than being papered over by
    what the rules say ought to be true:

    - `agentActors`: every distinct agent `actorId` that authored the *latest*
      revision of an object this episode's forward reference graph reaches
      (`{episode_id} | g.reachable_from(episode_id, reverse=False)`, the same
      `reach` `kernel.lifecycle`/`kernel.readiness`/`kernel.standards` compute),
      including the episode itself. An object an agent drafted and a human later
      revised does not appear here — the human's name is what a reader finds on it
      now, and this reports authorship of the record as it stands, not as it was
      first drafted.
    - `humanGates`: this episode's own recorded, unrefused transitions into a
      human-only gate state (`GATE_LABELS`: G1/G2/G3), plus G4 when this episode is
      a refresh's successor (`_g4_gate`) — each naming the gate, the state, the
      human actor id and when.
    - `agentComputedNoResult`: true unless an agent-authored `EvaluationRun` is
      reachable from the episode. `Graph.put` already forbids any agent from
      creating one (`AGENT_FORBIDDEN_TYPES`), so this is never false from a store
      docket itself wrote — but it is re-derived from the record rather than
      trusted from that policy, the same defensive posture the lifecycle gates take
      toward a store this process did not write.
    - `noAiAssistance`: true when `agentActors` is empty — the record shows no
      agent touched anything this episode reaches.
    """
    episode_id = ep.get("id")
    reach = (
        {episode_id} | g.reachable_from(episode_id, reverse=False)
        if isinstance(episode_id, str) else set()
    )

    agent_actors: set[str] = set()
    agent_run = False
    for oid in reach:
        if not g.has(oid):
            continue
        o = g.get(oid)
        author = o.get("createdBy")
        # [T9 rework] an `agent:` id is an agent whatever the dict declares — the write path
        # refuses the mismatch, and a hand-edited store must not read as human-only here.
        if not isinstance(author, dict) or not (
            author.get("actorType") == "agent" or id_says_agent(author)
        ):
            continue
        actor_id = author.get("actorId")
        if isinstance(actor_id, str) and actor_id:
            agent_actors.add(actor_id)
        if o.get("type") == "EvaluationRun":
            agent_run = True

    gates: list[dict] = []
    for record in ep.get("transitions") or []:
        if not isinstance(record, dict) or record.get("refused"):
            continue
        gate = GATE_LABELS.get(record.get("to"))
        if gate is None:
            continue
        actor = record.get("actor") if isinstance(record.get("actor"), dict) else {}
        if actor.get("actorType") != "human" or id_says_agent(actor):
            continue
        gates.append({"gate": gate, "state": record.get("to"),
                      "actorId": actor.get("actorId"), "at": record.get("at")})
    g4 = _g4_gate(g, ep)
    if g4 is not None:
        gates.append(g4)
    gates.sort(key=lambda r: (r["gate"], r.get("at") or ""))

    return {
        "agentActors": sorted(agent_actors),
        "humanGates": gates,
        "agentComputedNoResult": not agent_run,
        "noAiAssistance": not agent_actors,
    }


def _ai_assistance_lines(ai: dict) -> list[str]:
    """The Cover section's AI-assistance bullets — the human-readable half of the
    `aiAssistance` block the Machine annex prints verbatim from the same dict. Every
    id prints as a code span: an actor id is data read off the record, not narrative
    prose, so the citation rule `check_citations` enforces on Narrative sentences
    elsewhere in this module does not apply here — this is a record readout, not a
    claim that needs a citation.
    """
    if ai["noAiAssistance"]:
        return ["- **AI assistance:** No AI assistance is recorded in this episode."]
    lines = ["- **AI assistance:**"]
    agents = ", ".join(f"`{a}`" for a in ai["agentActors"])
    lines.append(f"  - Agent-authored objects reachable from this episode: {agents}")
    if ai["humanGates"]:
        gate_bits = "; ".join(
            f"{gr['gate']} ({gr['state']}) by `{gr.get('actorId')}`" for gr in ai["humanGates"]
        )
        lines.append(f"  - Human gate approvals on record: {gate_bits}")
    else:
        lines.append("  - Human gate approvals on record: none")
    if ai["agentComputedNoResult"]:
        lines.append(
            "  - The agent did not compute any result: no agent-authored "
            "`EvaluationRun` is reachable from this episode."
        )
    else:
        lines.append(
            "  - **The record shows an agent-authored `EvaluationRun` reachable from "
            "this episode — the agent authority boundary was not held.**"
        )
    return lines


# ---- section bodies -------------------------------------------------------------------


def _cover_body(
    g: Graph, ep: dict, ch: dict, policy: dict | None, now: str, snapshot_hash: str,
    ai_assistance: dict,
) -> list[str]:
    policy_name = policy.get("name") if isinstance(policy, dict) else None
    policy_version = policy.get("version") if isinstance(policy, dict) else None
    policy_text = (
        f"{policy_name} v{policy_version}" if policy_name and policy_version
        else "_[policy unresolved]_"
    )
    authority = ch.get("authority") if isinstance(ch.get("authority"), dict) else {}
    signer = authority.get("signer") or "_[unavailable]_"
    return [
        f"- Episode: {ep['id']} (sequence {ep.get('sequence', '_[unavailable]_')}, "
        f"state {ep.get('lifecycleState', '_[unavailable]_')}, "
        f"as of {ep.get('asOf', '_[unavailable]_')})",
        f"- Program: {ep.get('program') or '—'}",
        f"- Kernel: {KERNEL_VERSION} · Policy: {policy_text}",
        f"- Graph snapshot: {snapshot_hash}",
        f"- Rendered: {now}",
        f"- Signer: {signer}",
        *_ai_assistance_lines(ai_assistance),
    ]


def _problem_statement_body(g: Graph, ch: dict, seen: set[str] | None = None) -> list[str]:
    body: list[str] = []
    if not ch:
        body.append("_(charter unavailable — the episode's charter reference does "
                     "not resolve)_")
    body += [
        f"- **Question:** {_slot(g, ch.get('question'), seen)}",
        f"- **Decision to be made:** {_slot(g, ch.get('decisionToBeMade'), seen)}",
        "- **Consequences of erroneous output:** "
        f"{_slot(g, ch.get('consequencesOfErroneousOutput'), seen)}",
    ]
    scope = ch.get("scope") if isinstance(ch.get("scope"), dict) else {}
    body.append(f"- **Scope in:** {'; '.join(scope.get('included') or []) or NOT_STATED}")
    body.append(f"- **Scope out:** {'; '.join(scope.get('excluded') or []) or '—'}")
    body.append(f"- **Question class:** {ch.get('questionClass') or '_[unavailable]_'}")
    authority = ch.get("authority") if isinstance(ch.get("authority"), dict) else {}
    if authority:
        extra = []
        if authority.get("board"):
            extra.append(f"board {authority['board']}")
        if authority.get("delegations"):
            extra.append(f"delegations: {', '.join(authority['delegations'])}")
        tail = f" ({'; '.join(extra)})" if extra else ""
        body.append(f"- **Authority:** {authority.get('signer') or '_[unavailable]_'}{tail}")
    for d in ch.get("definitions") or []:
        if isinstance(d, dict):
            body.append(f"- **Definition — {d.get('term')}:** {_slot(g, d.get('text'), seen)}")
    for x in ch.get("limitations") or []:
        if isinstance(x, dict):
            body.append(
                f"- **Limitation:** {x.get('statement')} — "
                f"mitigation: {_slot(g, x.get('mitigation'), seen)}"
            )
    return body


def _mandate_body(g: Graph, ep: dict) -> list[str]:
    body = []
    for mid, m in _each(g, _ref_ids(ep.get("mandateElements"))):
        if m is None:
            body.append(f"- _[mandate element {mid} unresolved]_")
            continue
        claims = ", ".join(_ref_ids(m.get("satisfiedBy"))) or "no claims"
        body.append(f"- [{m.get('status')}] {m.get('text')} ({m.get('source')}) → {claims}")
    return body


def _objectives_body(g: Graph, ep: dict, seen: set[str] | None = None) -> list[str]:
    body = []
    for oid, o in _each(g, _ref_ids(ep.get("objectives"))):
        if o is None:
            body.append(f"- _[objective {oid} unresolved]_")
            continue
        rank = f", rank {o['priorityRank']}" if o.get("priorityRank") else ""
        body.append(
            f"- **{o.get('name')}** ({o.get('priority')}{rank}) — "
            f"provenance: {_slot(g, o.get('provenance'), seen)}"
        )
        for mid, m in _each(g, _ref_ids(o.get("measures"))):
            if m is None:
                body.append(f"  - _[measure {mid} unresolved]_")
                continue
            metric = m.get("metric") if isinstance(m.get("metric"), dict) else {}
            body.append(
                f"  - {m.get('task')} · {m.get('attribute')} · {m.get('measure')} "
                f"[{metric.get('units', '_[unavailable]_')}, "
                f"{metric.get('direction', '_[unavailable]_')}] — "
                f"criteria: {_criteria_text(g, m.get('criteria'), seen)}"
            )
    return body


def _alternative_reason(g: Graph, a: dict, seen: set[str] | None = None) -> str:
    ref = a.get("statusReason")
    r = _obj(g, ref)
    if r is None:
        return ""
    if r.get("type") == "Exclusion":
        if seen is not None and isinstance(ref, str):
            seen.add(ref)
        authority = r.get("authority") if isinstance(r.get("authority"), dict) else {}
        return (
            f" — {r.get('reasonType')} ({authority.get('who')}, "
            f"{authority.get('date')}): {r.get('reason')}"
        )
    return f" — {r.get('text')}"


def _alternative_order_key(g: Graph, aid: str) -> tuple:
    """D4: alternatives sort by the record's own declared `enteredOrder`, then id —
    not by id alone. Order of entry is a first-class field (the anchoring indicator
    reads it), and CBO's own table order is meaningful; an alphabetised list forces a
    reader to re-sort mentally to compare against the source. An alternative with no
    readable `enteredOrder` sorts after every one that has it, then by id."""
    a = _obj(g, aid)
    order = a.get("enteredOrder") if a is not None else None
    has_order = isinstance(order, int) and not isinstance(order, bool)
    return (0 if has_order else 1, order if has_order else 0, aid)


def _alternatives_body(g: Graph, ep: dict, seen: set[str] | None = None) -> list[str]:
    ids = sorted(_ref_ids(ep.get("alternatives")), key=lambda aid: _alternative_order_key(g, aid))
    body = []
    for aid, a in _each(g, ids):
        if a is None:
            body.append(f"- _[alternative {aid} unresolved]_")
            continue
        baseline = ", baseline" if a.get("baselineFlag") else ""
        body.append(
            f"- **{a.get('name')}** [{a.get('status')}{baseline}]: {a.get('description')}"
            f"{_alternative_reason(g, a, seen)}"
        )
    return body


def _grca_body(g: Graph, ep: dict, seen: set[str] | None = None) -> list[str]:
    body = []
    for i, gr in _each(g, _ref_ids(ep.get("groundRules"))):
        if gr is None:
            body.append(f"- _[ground rule {i} unresolved]_")
            continue
        body.append(f"- Ground rule: {gr.get('statement')} "
                     f"(source: {_slot(g, gr.get('source'), seen)})")
    for i, c in _each(g, _ref_ids(ep.get("constraints"))):
        if c is None:
            body.append(f"- _[constraint {i} unresolved]_")
            continue
        body.append(
            f"- Constraint [{c.get('kind')}]: {c.get('statement')} — "
            f"implications: {_slot(g, c.get('implications'), seen)}"
        )
    for i, a in _each(g, _ref_ids(ep.get("assumptions"))):
        if a is None:
            body.append(f"- _[assumption {i} unresolved]_")
            continue
        linchpin = " **(linchpin)**" if a.get("linchpin") else ""
        body.append(
            f"- Assumption{linchpin}: {a.get('statement')}\n"
            f"  - rationale: {_slot(g, a.get('rationale'), seen)}\n"
            f"  - evidence: {_slot(g, a.get('evidence'), seen)}\n"
            f"  - if wrong: {_slot(g, a.get('implicationsIfWrong'), seen)}\n"
            f"  - indicators that would alter: "
            f"{_slot(g, a.get('indicatorsThatWouldAlter'), seen)}\n"
            f"  - varied in sensitivity: {a.get('variedInSensitivity')}"
        )
    return body


_EVIDENCE_HEADER = (
    "| id | title | type | class | metadata level | scope (built to answer) | "
    "accredited for | valid until | review | reliability steps | pointer |"
)
_EVIDENCE_SEP = "|---|---|---|---|---|---|---|---|---|---|---|"


def metadata_withheld(g: Graph, e: dict, rendering: str) -> str | None:
    """The evidence's `classification.metadataLevel` when the unclassified rendering
    must withhold everything that level gates — pointer, scope of validity,
    accreditedFor/validUntil, review status and reliability-step count — or `None`
    when nothing here is withheld (`rendering == "full"`, or `metadataLevel` is `U` or
    unreadable).

    The single definition of "is this evidence's metadata visible" — `_evidence_register_row`
    and every export in `docket.exports` that touches these fields (`docket.exports.rtvm`
    in particular; review round 1, C1/I8) call this rather than re-deriving the rule, so
    "withheld under unclassified" means the same six columns everywhere the record
    prints them, not five in one place and one in another.
    """
    cls = e.get("classification") if isinstance(e.get("classification"), dict) else {}
    meta_level = cls.get("metadataLevel")
    if rendering != "full" and meta_level not in (None, "U"):
        return meta_level
    return None


def evidence_pointer(g: Graph, e: dict, rendering: str, seen: set[str] | None = None) -> str:
    """The evidence register's `pointer` column: the `[withheld: <level>]` marker when
    `metadata_withheld` fires, otherwise the pointer's `uri` or its own slot rendering
    (a `$gap`/`$exclusion` marker, or `NOT_STATED`)."""
    level = metadata_withheld(g, e, rendering)
    if level is not None:
        return f"[withheld: {level}]"
    pointer = e.get("pointer")
    return (
        pointer["uri"] if is_content(pointer) and isinstance(pointer, dict)
        else _slot(g, pointer, seen)
    )


def evidence_title(g: Graph, e: dict, rendering: str) -> str:
    """The evidence register's `title` column, gated by the same `metadata_withheld`
    rule as `evidence_pointer` and the other five metadata columns (review round 2,
    I4): a title is descriptive metadata about an Evidence item, not its substantive
    value, so it belongs with `pointer`/`scope`/`accreditedFor`/`validUntil`/`review`/
    reliability-steps — gated on `classification.metadataLevel`, not on the separate
    *value* classification `_withheld` reads. Before this helper existed, the
    evidence-register row printed `e.get('title')` unconditionally (a renderer bug:
    round 2's probe found an S/S fixture's title in clear on `package-unclassified.md`)
    while `docket.exports.rtvm` blanked it to `""` under the *value* gate and
    `docket.exports.prov`/`docket.exports.gsn` withheld it under the same *value* gate
    too — three different rules for one column. This is now the single definition
    every one of those four surfaces calls, so they cannot disagree about whether a
    title is visible, and a withheld title never renders as an empty string: a blank
    cell reads as "we did not look," and a withholding marker reads as "there is
    something here you may not see" — the distinction the whole A013/A103
    demonstration turns on.
    """
    level = metadata_withheld(g, e, rendering)
    if level is not None:
        return f"[withheld: {level}]"
    title = e.get("title")
    return title if isinstance(title, str) and title else NOT_STATED


def _evidence_register_row(
    g: Graph, e: dict, rendering: str, seen: set[str] | None = None,
) -> str:
    cls = e.get("classification") if isinstance(e.get("classification"), dict) else {}
    meta_level = cls.get("metadataLevel")
    withheld_level = metadata_withheld(g, e, rendering)
    if withheld_level is not None:
        marker = f"[withheld: {withheld_level}]"
        scope = accredited_for = valid_until = review = rel = marker
    else:
        sov = e.get("scopeOfValidity")
        if is_content(sov) and isinstance(sov, dict):
            scope = f"{sov.get('builtToAnswer')} ({sov.get('questionClass')})"
            accredited_for = sov.get("accreditedFor") or NOT_STATED
            valid_until = sov.get("validUntil") or NOT_STATED
        else:
            scope = _slot(g, sov, seen)
            accredited_for = valid_until = "—"
        review = e.get("reviewStatus") or "_[unavailable]_"
        steps = e.get("reliabilitySteps")
        rel = str(len(steps)) if isinstance(steps, list) else _slot(g, steps, seen)
    ptr = evidence_pointer(g, e, rendering, seen)
    title = evidence_title(g, e, rendering)
    return (
        f"| {e['id']} | {title} | {e.get('evidenceType')} | "
        f"{cls.get('level', '_[unavailable]_')} | {meta_level or '_[unavailable]_'} | "
        f"{scope} | {accredited_for} | {valid_until} | {review} | {rel} | {ptr} |"
    )


def _evidence_register_body(
    g: Graph, ep: dict, rendering: str, seen: set[str] | None = None,
) -> list[str]:
    body = [_EVIDENCE_HEADER, _EVIDENCE_SEP]
    for i, e in _each(g, _sorted_ref_ids(ep.get("evidenceRegister"))):
        if e is None:
            body.append(f"| {i} | _[unresolved]_ | — | — | — | — | — | — | — | — | — |")
            continue
        body.append(_evidence_register_row(g, e, rendering, seen))
    return body if len(body) > 2 else []


def _seal_status(r: dict, findings: list[Finding]) -> str:
    """The tail of a run's cover line: either the record hash and a claim of a verified
    seal, or — when a `run-seal` finding names this run — neither, because printing a
    truncated hash next to a false claim of verification would be decoration, not
    evidence."""
    bad = _findings_for(findings, r["id"], "run-seal")
    if bad:
        msgs = "; ".join(f.message for f in bad)
        return f") — **seal not verified** (rule run-seal): {msgs}"
    return (
        f", record {r['runRecordHash'][:12]}…) — "
        "seal verified by `docket validate` (rule run-seal)"
    )


def _run_line(g: Graph, r: dict, findings: list[Finding]) -> str:
    line = (
        f"- **Run {r['id']}** (step {r['step']}, {r['method']}, seed {r['seed']}, "
        f"kernel {r['kernelVersion']}, inputs {r['inputsHash'][:12]}…"
    ) + _seal_status(r, findings)
    if _findings_for(findings, r["id"], "run-inputs-changed"):
        line += " — **inputs changed since sealing — re-evaluate**"
    return line


def _evaluation_results_body(
    g: Graph, ep: dict, rendering: str, findings: list[Finding],
    obs_by_alt: dict[str, list[dict]], seen: set[str] | None = None,
) -> list[str]:
    run_ids = _ref_ids(ep.get("runs"))
    obs_ids = _sorted_ref_ids(ep.get("observations"))

    body: list[str] = []
    for rid, r in _each(g, run_ids):
        if r is None:
            body.append(f"- _[run {rid} unresolved]_")
            continue
        body.append(_run_line(g, r, findings))
        body.append(f"  - ranking: {' > '.join(r.get('ranking') or [])}")
        for _res_id, res in _each(g, _ref_ids(r.get("outputs"))):
            if res is None or not res.get("aggregate"):
                continue
            tainted = any(
                _withheld(g, o.get("evidence"), rendering)
                for o in obs_by_alt.get(res.get("alternative"), [])
            )
            if tainted:
                val = "[withheld]"
            else:
                val = f"{res.get('value')} {res.get('units')}"
                if res.get("uncertainty"):
                    val += f" [{res['uncertainty']['lo']}, {res['uncertainty']['hi']}]"
            body.append(f"  - {res.get('alternative')}: {val}")
    if body:
        body.append("")
    body.append("| observation | alternative | measure | value | evidence |")
    body.append("|---|---|---|---|---|")
    for oid, o in _each(g, obs_ids):
        if o is None:
            body.append(f"| {oid} | _[unresolved]_ | — | — | — |")
            continue
        if _withheld(g, o.get("evidence"), rendering):
            v = f"[withheld: {g.get(o['evidence'])['classification']['level']}]"
        else:
            v = canonical_json(o.get("value"))
        ev = o.get("evidence")
        ev_text = ev if isinstance(ev, str) else _slot(g, ev, seen)
        body.append(f"| {o.get('id', oid)} | {o.get('alternative')} | {o.get('measure')} | "
                    f"{v} | {ev_text} |")
    return body if run_ids or obs_ids else []


def _flip_parameter_measure_id(g: Graph, param: dict) -> str | None:
    """The `Measure` id a flip parameter concerns, derived from `parameter.target`
    rather than trusted as a separate stored field (there isn't one): for
    `kind=weight`, `target` is `"<weightSetId>:<measureId>"`; for `kind=observation`,
    `target` is an `Observation` id whose own `measure` field names it."""
    kind, target = param.get("kind"), param.get("target")
    if kind == "weight" and isinstance(target, str) and ":" in target:
        return target.split(":", 1)[1]
    if kind == "observation":
        obs = _obj(g, target)
        measure_id = obs.get("measure") if obs is not None else None
        return measure_id if isinstance(measure_id, str) else None
    return None


def _flip_display_label(g: Graph, f: dict) -> str:
    """D3: the Measure's own `attribute` (e.g. "Capability"), not the whole
    `parameter.label` sentence `flip.py` builds for its own bookkeeping purposes
    (e.g. "weight on Composite capability score if the vehicle carries..."), which
    reads as a run-on in a table cell. Falls back to the stored label when the
    Measure cannot be resolved — this is a display preference, not a citation, so a
    hand-edited or mid-refresh graph must still print *something* rather than crash
    or blank the cell."""
    param = f.get("parameter") if isinstance(f.get("parameter"), dict) else {}
    measure_id = _flip_parameter_measure_id(g, param)
    m = _obj(g, measure_id) if measure_id else None
    attribute = m.get("attribute") if m is not None else None
    if not attribute:
        return param.get("label") or "_[unavailable]_"
    prefix = "weight on" if param.get("kind") == "weight" else "observed"
    return f"{prefix} {attribute}"


def _flip_row(g: Graph, fid: str, f: dict | None) -> str:
    if f is None:
        return f"| _[flip {fid} unresolved]_ | — | — | — | — | — | — | — |"
    rng = f.get("range") if isinstance(f.get("range"), dict) else {}
    run = f.get("run") if isinstance(f.get("run"), str) else "_[unavailable]_"
    threshold = f.get("flipThreshold")
    distance = f.get("flipDistance")
    return (
        f"| {run} | {_flip_display_label(g, f)} | {f.get('currentValue')} | "
        f"[{rng.get('lo')}, {rng.get('hi')}] ({rng.get('source')}) | "
        f"{threshold if threshold is not None else '—'} | "
        f"{distance if distance is not None else '—'} | {f.get('direction')} | "
        f"{f.get('assumption') or '—'} |"
    )


def _flip_refusal_message(rr: dict) -> str | None:
    """The message on `rr`'s own `run-stale`/`flip-summary-unavailable` blocker, if the
    stored `flipSummary` is empty *because* `flip_summary` refused the episode's last
    run — not merely because the episode has no runs at all, which is not a refusal.
    Returned as-is: the Finding's own message already states the refusal in full
    ("run stale; re-evaluate — the sensitivity summary refuses this run: ..."), so a
    caller must print it directly rather than wrapping it in another copy of the same
    clause (M1). `rr.get("blockers") or []`, not `rr["blockers"]`: `rr` may be a
    wrong-typed object read back from a dangling/mistyped `episode.readiness`
    reference (the same shape I8 already tolerates for `decisionClassPolicy`), and
    this function must not be the one bare `KeyError` left in that path (R3)."""
    blockers = rr.get("blockers") or []
    stale = [
        b for b in blockers
        if isinstance(b, dict) and b.get("rule") in ("run-stale", "flip-summary-unavailable")
    ]
    return stale[0].get("message") if stale else None


def _what_flips_body(
    g: Graph, ep: dict, rr: dict | None, findings: list[Finding],
) -> list[str]:
    flip_pairs = _each(g, _ref_ids(ep.get("flipAnalyses")))
    flips_by_id = {fid: f for fid, f in flip_pairs if f is not None}
    ordered = sorted(
        flip_pairs,
        key=lambda pair: (
            pair[1] is None,
            pair[1] is not None and pair[1].get("flipDistance") is None,
            (pair[1] or {}).get("flipDistance") or 0,
            pair[0],
        ),
    )

    body: list[str] = []
    stale_runs = sorted({
        f["run"] for f in flips_by_id.values()
        if isinstance(f.get("run"), str) and _findings_for(findings, f["run"], "run-inputs-changed")
    })
    for run_id in stale_runs:
        body.append(
            f"_(inputs changed since sealing for run {run_id} — re-evaluate; the flip "
            "analyses below computed from it no longer reflect the current graph)_"
        )
    if stale_runs:
        body.append("")
    body.append(
        "| run | parameter | current | range | flip threshold | distance | direction | "
        "assumption |"
    )
    body.append("|---|---|---|---|---|---|---|---|")
    body.extend(_flip_row(g, fid, f) for fid, f in ordered)

    if rr and rr.get("flipSummary"):
        fs = rr["flipSummary"]
        robustness = ", ".join(f"{a}: {v}" for a, v in fs["simplexRobustness"].items())
        not_summarised = _ref_ids(fs.get("runsNotSummarised"))
        tail = f"; not summarised: {', '.join(not_summarised)}" if not_summarised else ""
        body.append("")
        body.append(
            f"Weight-simplex robustness for run {fs['run']} (fraction of the simplex "
            f"in which each alternative ranks first; n={fs['nSimplex']}, "
            f"seed {fs['seed']}): {robustness}{tail}"
        )
    elif rr:
        msg = _flip_refusal_message(rr)
        if msg:
            body.append("")
            body.append(f"_(weight-simplex robustness withheld: {msg})_")
    return body if ordered else []


def _bias_checks_body(
    g: Graph, ep: dict, rr: dict | None, seen: set[str] | None = None,
) -> list[str]:
    body = []
    for bid, c in _each(g, _ref_ids(ep.get("biasChecks"))):
        if c is None:
            body.append(f"- _[bias check {bid} unresolved]_")
            continue
        body.append(
            f"- {c.get('checkType')} [{c.get('status')}] — "
            f"evidence: {_slot(g, c.get('producedEvidence'), seen)}"
        )
    if rr:
        for rid, r in _each(g, _ref_ids(rr.get("computedBiasRisks"))):
            if r is None:
                body.append(f"- _[computed indicator {rid} unresolved]_")
                continue
            body.append(f"- computed indicator: {r.get('kind')} — {r.get('statement')}")
    return body


def tailoring_note(tailoring_name: str) -> str | None:
    """The tailoring's own honesty note, or `None` if it has none or cannot be loaded —
    a hand-edited store or a tailoring file removed after scoring must not crash the
    renderer over a footnote. Public (plan 07 Task 7 fix round) for the same reason as
    `rating_scale_legend`: `_readiness_view` calls this directly so the API's
    `standardsCaptions.tailoringNote` is the kernel's own string, e.g. gao-23-106549's
    caveat that GAO published a 3×3 verdict grid, not per-question labels — never a
    second copy retyped in the UI."""
    try:
        return load_tailoring(tailoring_name).get("note")
    except (ValueError, OSError):
        return None


def _new_blocking_findings(rr: dict, findings: list[Finding]) -> list[Finding]:
    """R2: `rr["blockers"]` is what the report said *when it was computed* — it does
    not update itself when the episode is edited afterwards. A live blocking `Finding`
    not already in that stored list (compared by content — rule, objects, message —
    not identity, since a stored blocker went through `Finding.to_dict()` and back)
    means the record has moved since. Shared by `ready_text` (whether to say so) and
    `_readiness_body` (what to name)."""
    stored_blockers = {
        (b.get("rule"), tuple(_ref_ids(b.get("objects"))), b.get("message"))
        for b in (rr.get("blockers") or []) if isinstance(b, dict)
    }
    return sorted(
        f for f in findings
        if f.severity == "blocking" and (f.rule, f.objects, f.message) not in stored_blockers
    )


def ready_text(rr: dict, findings: list[Finding]) -> str:
    """The renderer's own text for "Ready (no blocking findings)": `str(rr["ready"])`
    (`True`/`False`, an f-string's own `str()` — see the three committed demo packages'
    "## 10. Readiness" section) unless a live blocking `Finding` exists that is not
    already among `rr["blockers"]` (the report's own list, frozen at compute time),
    in which case the substitution `"unavailable — record changed since the readiness
    report"` — the record has moved since the report was produced and the stored
    `ready` value would otherwise contradict the findings this same render call just
    printed. Extracted from `_readiness_body` (plan 07 Task 7 fix round) so
    `docket.api.routes.kernel._readiness_view` can hand the API the exact string the
    package would print for the same episode, rather than a second, independently
    computed guess (`str(report.ready)` in the browser) that can drift from it.
    """
    if _new_blocking_findings(rr, findings):
        return "unavailable — record changed since the readiness report"
    return str(rr.get("ready"))


def readiness_ready_text(g: Graph, episode_id: str, rr: dict) -> str:
    """`ready_text(rr, findings)` for `episode_id`, resolving `findings` the exact way
    `render_package` does (`validate(g, policy)` over the episode's own charter/policy,
    line ~1353 below) — so an API caller (`GET`/`POST .../readiness`) never has to
    duplicate that policy-resolution walk to ask the same question the renderer already
    knows how to answer. Tolerant of a missing/dangling charter or policy, exactly like
    `render_package` itself: `_obj` returns `None` rather than raising, and `validate`
    accepts `None` as "no policy" (`policy if policy is not None else {}`)."""
    ep = g.get(episode_id)
    ch = _obj(g, ep.get("charter")) or {}
    policy = _obj(g, ch.get("decisionClassPolicy"))
    findings = validate(g, policy if policy is not None else {})
    return ready_text(rr, findings)


def _readiness_body(g: Graph, rr: dict | None, findings: list[Finding]) -> list[str]:
    if not rr:
        body = ["_(no readiness report has been produced for this episode)_"]
        blocking = sorted(f for f in findings if f.severity == "blocking")
        if blocking:
            body.append("")
            body.append("Live blocking findings (`docket validate`), not yet a full "
                        "readiness assessment:")
            for f in blocking:
                body.append(f"- **{f.rule}** [{', '.join(f.objects)}]: {f.message}")
        return body
    sa = _obj(g, rr.get("standardsAssessment")) or {}
    new_blocking = _new_blocking_findings(rr, findings)
    rt = ready_text(rr, findings)
    body = [f"**Ready (no blocking findings):** {rt} · "
            f"tailoring {sa.get('tailoring', '_[unavailable]_')} · "
            f"k={sa.get('k', '_[unavailable]_')}"]
    note = tailoring_note(sa["tailoring"]) if isinstance(sa.get("tailoring"), str) else None
    if note:
        body.append(f"> {note}")
    verdicts = sa.get("dimensionVerdicts") if isinstance(sa.get("dimensionVerdicts"), dict) else {}
    # Fixed order, not dict order: the store sorts keys on save, so raw iteration would print
    # the verdicts in a different order after a load than before it and break re-render
    # byte-identity. Known dimensions first, in the standard's order, then anything else sorted.
    known = [d for d in ("objectivity", "validity", "reliability") if d in verdicts]
    ordered = known + sorted(d for d in verdicts if d not in known)
    for dim in ordered:
        v = verdicts[dim]
        v = v if isinstance(v, dict) else {}
        qualifier = f" — {v.get('qualifier')}" if v.get("qualifier") else ""
        body.append(f"- **{dim}:** {v.get('verdict', '_[unavailable]_')}{qualifier}")
    if isinstance(sa.get("aggregationRule"), str):
        body.append(f"- Aggregation rule: {sa['aggregationRule']}")
    body.append("")
    body.append(rating_scale_legend())
    body.append("")
    body.append("| question | applicable | state | rule | justification |")
    body.append("|---|---|---|---|---|")
    for r in sa.get("ratings") or []:
        if not isinstance(r, dict):
            continue
        rule = r.get("rule") if r.get("applicable") else r.get("tailoringReason")
        just_ids = _ref_ids(r.get("justification"))
        just = ", ".join(just_ids[:6]) + ("…" if len(just_ids) > 6 else "")
        state = r.get("state") if r.get("state") is not None else "—"
        body.append(
            f"| {r.get('questionId')} | {r.get('applicable')} | {state} | {rule} | {just} |"
        )
    body.append("")
    for b in rr.get("blockers") or []:
        if isinstance(b, dict):
            body.append(f"- **Blocker** {b.get('rule')} "
                        f"[{', '.join(_ref_ids(b.get('objects')))}]: {b.get('message')}")
    if new_blocking:
        body.append("")
        body.append("**Blocking findings since the readiness report:**")
        for f in new_blocking:
            body.append(f"- **{f.rule}** [{', '.join(f.objects)}]: {f.message}")
    for gid, gp in _each(g, _ref_ids(rr.get("openGaps"))):
        if gp is None:
            body.append(f"- _[open gap {gid} unresolved]_")
            continue
        body.append(f"- Open gap: {gid} — {gp.get('sought')} [{gp.get('impact')}]")
    for xid, x in _each(g, _ref_ids(rr.get("openExclusions"))):
        if x is None:
            body.append(f"- _[open exclusion {xid} unresolved]_")
            continue
        target = x.get("target") if isinstance(x.get("target"), dict) else {}
        body.append(f"- Open exclusion: {xid} — {target.get('label')} ({x.get('reasonType')})")
    ms = _obj(g, rr.get("mandateScorecard"))
    for row in (ms or {}).get("rows") or []:
        if isinstance(row, dict):
            body.append(f"- Mandate: {row.get('element')} → {row.get('status')}")
    return body


def _risks_body(g: Graph, ep: dict) -> list[str]:
    body = []
    for rid, r in _each(g, _ref_ids(ep.get("risks"))):
        if r is None:
            body.append(f"- _[risk {rid} unresolved]_")
            continue
        body.append(
            f"- [{r.get('kind')}, {r.get('status')}] {r.get('statement')} — "
            f"owner {r.get('owner')}; consequence: {r.get('consequence')}; "
            f"mitigation: {_action_list_text(g, r.get('mitigation'))}; "
            f"monitor: {r.get('monitor') or NOT_STATED}"
        )
    return body


def _refresh_log_body(g: Graph, ep: dict) -> list[str]:
    body = []
    trigger_id = ep.get("refreshedBecause")
    t = _obj(g, trigger_id)
    if isinstance(trigger_id, str) and t is None:
        body.append(f"- _[refresh trigger {trigger_id} unresolved]_")
    elif t is not None:
        body.append(
            f"- Trigger {t.get('id')} [{t.get('kind')}] {t.get('description')} "
            f"(source: {t.get('source')}; detected {t.get('detectedAt')}); "
            f"supersedes {ep.get('supersedes')}"
        )
    for d in g.all("EpisodeDiff"):
        if d.get("to") != ep.get("id"):
            continue
        before = " > ".join(_ref_ids(d.get("rankingBefore"))) or "—"
        after = " > ".join(_ref_ids(d.get("rankingAfter"))) or "—"
        changed = d.get("changed") if isinstance(d.get("changed"), list) else []
        added, removed = _ref_ids(d.get("added")), _ref_ids(d.get("removed"))
        judgments_changed = d.get("judgmentsChanged")
        judgments_changed_n = len(judgments_changed) if isinstance(judgments_changed, list) else 0
        judgments_consistent = _ref_ids(d.get("judgmentsConsistent"))
        ratings_changed = d.get("ratingsChanged")
        ratings_changed_n = len(ratings_changed) if isinstance(ratings_changed, list) else 0
        body.append(
            f"- Diff {d.get('id')} ({d.get('pairing', 'unknown')} pairing): "
            f"{len(changed)} field changes, {len(added)} added, {len(removed)} removed; "
            f"judgments changed {judgments_changed_n}, consistent "
            f"{len(judgments_consistent)} (Phase I: judgments are compared by claim id "
            f"only, not content); ratings changed {ratings_changed_n}; "
            f"ranking {before} → {after}"
        )
        for c in changed:
            if isinstance(c, dict):
                body.append(f"  - {c.get('object')}.{c.get('field')}: "
                           f"{c.get('before')} → {c.get('after')}")
    return body


def _commitment_body(g: Graph, ep: dict) -> list[str]:
    c = _obj(g, ep.get("commitment"))
    if c is None:
        return []
    signer = c.get("signer") if isinstance(c.get("signer"), dict) else {}
    package_hash = c.get("packageHash")
    package_hash_text = package_hash[:12] if isinstance(package_hash, str) else "_[unavailable]_"
    body = [
        f"- Selected: {c.get('selected')} · signer {signer.get('identity')} "
        f"({signer.get('role')}) at {c.get('signedAt')} · "
        f"package hash {package_hash_text}…"
    ]
    for x in c.get("conditions") or []:
        if isinstance(x, dict):
            body.append(f"  - condition: {x.get('text')} "
                        f"(verify by {x.get('verifyBy')}, due {x.get('dueDate')})")
    for s in c.get("stopRules") or []:
        body.append(f"  - stop rule: {s}")
    for d in c.get("dissent") or []:
        if isinstance(d, dict):
            body.append(f"  - dissent ({d.get('who')}): {d.get('text')}")
    return body


def _traceability_row(
    g: Graph, cid: str, c: dict, seen: set[str] | None = None,
) -> list[str]:
    text = c.get("text")
    level = (c.get("assessableAt") or {}).get("level") if isinstance(c.get("assessableAt"), dict) \
        else None
    qc = c.get("questionClass")
    sb = c.get("supportedBy")
    if not isinstance(sb, list):
        return [f"| {cid} | {text} | {level} | {qc} | {_slot(g, sb, seen)} | — | — |"]
    rows = []
    for e in sb:
        if not isinstance(e, dict):
            continue
        ev = _obj(g, e.get("evidence"))
        if ev is None:
            rows.append(f"| {cid} | {text} | {level} | {qc} | "
                       f"_[{e.get('evidence')} unresolved]_ | — | — |")
            continue
        ev_cls = ev.get("classification") if isinstance(ev.get("classification"), dict) else {}
        reuse = e.get("reuseJustification", {})
        reuse_text = reuse.get("text", "—") if isinstance(reuse, dict) else "—"
        rows.append(f"| {cid} | {text} | {level} | {qc} | {ev.get('id')} | "
                    f"{ev_cls.get('level', '_[unavailable]_')} | {reuse_text} |")
    return rows or [f"| {cid} | {text} | {level} | {qc} | _[no evidence]_ | — | — |"]


def _traceability_body(g: Graph, ep: dict, seen: set[str] | None = None) -> list[str]:
    body = [
        "| claim | text | level | question class | evidence | evidence level | "
        "reuse justification |",
        "|---|---|---|---|---|---|---|",
    ]
    claim_ids = _sorted_ref_ids(ep.get("claims"))
    for cid, c in _each(g, claim_ids):
        if c is None:
            body.append(f"| {cid} | _[unresolved]_ | — | — | — | — | — |")
            continue
        body.extend(_traceability_row(g, cid, c, seen))
    return body if claim_ids else []


def _machine_annex_body(
    exports: list[tuple[str, str]],
    snapshot_hash: str, object_count: int, log_entry_count: int,
    unresolved_narratives: list[str], ai_assistance: dict,
) -> list[str]:
    """The Machine annex body — design §10 item 16: "graph snapshot, PROV bundle, GSN
    export, run manifests." **[ruling R3]** replaces the placeholder "(see `docket
    export`)" line with one line per export, named and hashed.

    Takes the already-computed `[(filename, text), ...]` pairs rather than the graph —
    kept a pure function of its arguments, as the brief requires, and it must be the
    *same* computation `build_package` later writes to disk, or the annex would name a
    hash that does not belong to the file next to it (see `write_computed`'s docstring
    in `docket.exports` for the ordering hazard this avoids: a `DecisionPackage` cannot
    cite itself in its own PROV bundle, so exports must be computed before the package
    being built is put into the graph, not after).

    `ai_assistance` is the same dict `ai_assistance_summary` computed for the Cover's
    prose bullets (`_ai_assistance_lines`), printed here verbatim as one canonical-JSON
    line so a machine reader gets the structured form and a human reader gets the
    prose form of one fact, never two that could disagree.
    """
    export_lines = [f"- {filename}  sha256:{sha256_hex(text)}" for filename, text in exports]
    body = [
        f"- graph snapshot hash: {snapshot_hash}",
        f"- objects (excluding rendered packages): {object_count}",
        f"- log entries (excluding package writes): {log_entry_count}",
        *export_lines,
        f"- aiAssistance: {canonical_json(ai_assistance)}",
    ]
    if unresolved_narratives:
        body.append(f"- unresolved narrative references: {', '.join(unresolved_narratives)}")
    return body


def episode_exclusions(g: Graph, episode_id: str) -> list[dict]:
    """Every `Exclusion` that belongs to `episode_id`: forward-reachable from the
    episode, **or** referenced by nothing at all (review round 2, R1).

    `readiness.py`'s own `openExclusions` already lists everything the episode's
    forward reference graph reaches — including through P3 slot markers, since
    `iter_refs` treats a `{"$exclusion": id}` marker as an edge too — but a
    standalone `Exclusion` that nothing at all references (e.g. "CBO excluded
    long-distance transportability" with no slot, no `statusReason`, no section
    target) has no inbound *or* outbound edge to the episode, so it is unreachable
    in either direction and would otherwise never appear on the page at all.

    `Exclusion` carries no `episode` field to say which episode a free-floating one
    belongs to, so a completely unreferenced Exclusion is treated as on the record
    for whichever episode is being rendered — a documented Phase I assumption (one
    episode's package rendered at a time), not a claim this disambiguates ownership
    in a multi-episode graph. An Exclusion that *is* referenced, but only from
    outside this episode's reach, belongs to whichever episode actually reaches it
    and is correctly left off this one's list.

    This is the single definition of "belongs to this episode" for an Exclusion —
    `_other_exclusions_body`'s round-1 inline check, promoted here so that this
    module's own `section_excl` lookup (`render_package`) and
    `docket.exports.madr`'s `_section_exclusion` cannot disagree about which
    Exclusion belongs to which episode. They used to: the round-1 C3 fix scoped the
    MADR side to *only* the forward-reachable half of this rule, which silently
    dropped Demo A's own Section-targeted, wholly unreferenced `ex-no-commitment`
    from the MADR the day the package right beside it still printed it and its
    authority.
    """
    reach = {episode_id} | g.reachable_from(episode_id, reverse=False)
    return [x for x in g.all("Exclusion") if x["id"] in reach or not g.refs_to(x["id"])]


def _other_exclusions_body(g: Graph, episode_id: str, printed: set[str]) -> list[str]:
    """D1: every `Exclusion` on record for this episode that no other section already
    printed."""
    body = []
    for x in episode_exclusions(g, episode_id):
        xid = x["id"]
        if xid in printed:
            continue
        authority = x.get("authority") if isinstance(x.get("authority"), dict) else {}
        target = x.get("target") if isinstance(x.get("target"), dict) else {}
        body.append(
            f"- {xid} [{target.get('kind')}: {target.get('label')}] "
            f"{x.get('reasonType')} ({authority.get('who')}, {authority.get('date')}): "
            f"{x.get('reason')}"
        )
    return body


# ---- assembly ---------------------------------------------------------------------


def render_package(
    g: Graph, episode_id: str, *, rendering: str, now: str,
    exports: list[tuple[str, str]] | None = None,
) -> str:
    """Render the Decision Package text.

    `exports`, when given, is the already-computed `[(filename, text), ...]` list the
    Machine annex quotes verbatim (`build_package` passes its own single computation
    through here so the annex's hashes and the files it writes to disk can never
    diverge — see `docket.exports.write_computed`'s docstring). When omitted (every
    other caller, including a bare `render_package(...)` call in a test or the `docket
    render` CLI command), the exports are computed here, from the graph as it stands
    right now — imported lazily; see `_machine_annex_body`'s docstring for why a
    module-level import in either direction between this module and `docket.exports`
    would be circular.
    """
    if not isinstance(episode_id, str) or not g.has(episode_id):
        raise ValidationError([f"episode {episode_id!r} is not in the graph"])
    if exports is None:
        from docket.exports import compute_all

        exports = compute_all(g, episode_id, rendering=rendering)
    ep = g.get(episode_id)
    ch = _obj(g, ep.get("charter")) or {}
    policy = _obj(g, ch.get("decisionClassPolicy"))
    findings = validate(g, policy if policy is not None else {})

    narratives: dict[str, list[dict]] = {}
    unresolved_narratives: list[str] = []
    for nid in _ref_ids(ep.get("narratives")):
        n = _obj(g, nid)
        if n is None:
            unresolved_narratives.append(nid)
            continue
        errs = check_citations(g, n)
        if errs:
            raise UncitedSentenceError(f"{nid}: " + "; ".join(errs))
        narratives.setdefault(n.get("section"), []).append(n)

    # R1: scoped to this episode's own Exclusions (`episode_exclusions`), the same
    # membership rule `_other_exclusions_body` and `docket.exports.madr` use — a
    # graph-wide `g.all("Exclusion")` scan would let a Section-targeted Exclusion
    # belonging to a different episode (Demo B's three sub-episodes share one graph)
    # stand in for this episode's own missing section.
    section_excl = {
        x["target"]["label"]: x for x in episode_exclusions(g, episode_id)
        if x["target"]["kind"] == "Section"
    }
    rr = _obj(g, ep.get("readiness"))

    obs_by_alt: dict[str, list[dict]] = {}
    for _oid, o in _each(g, _ref_ids(ep.get("observations"))):
        if o is not None:
            obs_by_alt.setdefault(o.get("alternative"), []).append(o)

    content_snapshot, content_objects, content_log_entries = _content_snapshot(g)

    # Computed once and handed to both the Cover's prose bullets and the Machine
    # annex's structured line, so the two can never print two different answers to
    # "was AI assistance used here" — see `ai_assistance_summary`'s own docstring.
    ai_assistance = ai_assistance_summary(g, ep)

    # D1: every Exclusion a body below actually prints is recorded here as it is
    # built, so "Other exclusions on record" (appended to §10 further down) can name
    # every remaining one exactly once. Bodies are computed into a dict first, in
    # section order, rather than emitted immediately, because a later section
    # (traceability, §14) can also print an Exclusion and §10 is built before it.
    printed_exclusions: set[str] = set()

    bodies: dict[str, list[str]] = {
        "cover": _cover_body(g, ep, ch, policy, now, content_snapshot, ai_assistance),
        "problem-statement": _problem_statement_body(g, ch, printed_exclusions),
        "mandate-elements": _mandate_body(g, ep),
        "objectives-and-measures": _objectives_body(g, ep, printed_exclusions),
        "alternatives": _alternatives_body(g, ep, printed_exclusions),
        "grca": _grca_body(g, ep, printed_exclusions),
        "evidence-register": _evidence_register_body(g, ep, rendering, printed_exclusions),
        "evaluation-results": _evaluation_results_body(
            g, ep, rendering, findings, obs_by_alt, printed_exclusions
        ),
        "what-flips": _what_flips_body(g, ep, rr, findings),
        "bias-checks": _bias_checks_body(g, ep, rr, printed_exclusions),
        "readiness": _readiness_body(g, rr, findings),
        "risks": _risks_body(g, ep),
        "refresh-log": _refresh_log_body(g, ep),
        "commitment": _commitment_body(g, ep),
        "traceability": _traceability_body(g, ep, printed_exclusions),
        "machine-annex": _machine_annex_body(
            exports,
            content_snapshot, content_objects, content_log_entries, unresolved_narratives,
            ai_assistance,
        ),
    }

    # A Section-targeted Exclusion prints (below) only when that section's own body
    # is empty; when it will, it counts as printed too.
    for key, x in section_excl.items():
        if not bodies.get(key):
            printed_exclusions.add(x["id"])

    other_exclusions = _other_exclusions_body(g, episode_id, printed_exclusions)
    if other_exclusions:
        header = ["", "**Other exclusions on record:**"]
        bodies["readiness"] = [*bodies["readiness"], *header, *other_exclusions]

    lines: list[str] = []

    def section(key: str, title: str) -> None:
        body = bodies[key]
        lines.append(f"\n## {title}\n")
        for n in narratives.get(key, []):
            for s in n.get("sentences") or []:
                cites = s.get("cites") or []
                level = None
                for c in cites:
                    level = _cite_withheld_level(g, c, rendering, obs_by_alt)
                    if level:
                        break
                if level:
                    lines.append(f"_[sentence withheld: {level}]_")
                else:
                    lines.append(f"{s.get('text', '')} [{', '.join(cites)}]")
            lines.append("")
        if body:
            lines.extend(body)
        elif key in section_excl:
            x = section_excl[key]
            lines.append(
                f"**Excluded** ({x['reasonType']}; {x['authority']['who']}, "
                f"{x['authority']['date']}): {x['reason']}"
            )
        else:
            lines.append("_(no objects filed for this section)_")

    lines.append(f"# Decision Package — {ep['id']} ({rendering} rendering)")
    for key, title in SECTIONS:
        section(key, title)
    return "\n".join(lines).rstrip() + "\n"


def build_package(
    g: Graph, episode_id: str, *, rendering: str, now: str, out_dir: Path | None = None,
) -> tuple[dict, str]:
    """Render, seal a `DecisionPackage`, and optionally write the Markdown to disk.

    `graphSnapshotHash` is the content-view hash `_content_snapshot` computes
    (excluding `DecisionPackage` objects), so re-rendering an unchanged record — even
    with earlier packages already sitting in the graph — reproduces the same value
    every time. `path`, when written, is the file's basename only — never an absolute
    or directory-dependent path — so two builds of the same graph into different
    `out/` roots produce byte-identical `DecisionPackage` objects.

    The object is `g.put` *before* the file is written (not after): a validation
    failure on the `put` then leaves nothing on disk, and a failure writing the file
    leaves a `DecisionPackage` the graph already has and a caller can regenerate the
    file from — never an orphan file whose hash is in no graph.

    **[ruling R3]** Every one of the six exports (`docket.exports`) is written next to
    `package-{rendering}.md` in the same `out_dir`, and the Machine annex lists their
    filenames and sha256. The export texts are computed exactly *once*, here, before
    `g.put` — a `DecisionPackage` cannot cite itself in its own PROV bundle, so
    computing the exports again *after* the put (when the new package is already in the
    graph) would produce different bytes than the ones the annex just hashed. Passing
    that one computation into `render_package` (for the annex) and into
    `write_computed` (for the disk write) is what keeps the two from disagreeing.
    """
    snapshot, _, _ = _content_snapshot(g)
    # Lazy import — see `_machine_annex_body`'s docstring for why a module-level import
    # between this module and `docket.exports` in either direction would be circular.
    from docket.exports import compute_all, write_computed

    exports = compute_all(g, episode_id, rendering=rendering)
    text = render_package(g, episode_id, rendering=rendering, now=now, exports=exports)
    n = 1 + sum(
        1 for o in g.all("DecisionPackage")
        if o["episode"] == episode_id and o["rendering"] == rendering
    )
    pkg = {
        "id": f"pkg-{episode_id}-{rendering}-{n}", "type": "DecisionPackage", "rev": 1,
        "createdBy": KERNEL_ACTOR, "createdAt": now, "episode": episode_id,
        "rendering": rendering, "hash": sha256_hex(text), "kernelVersion": KERNEL_VERSION,
        "graphSnapshotHash": snapshot, "renderedAt": now,
    }
    file_name = f"package-{rendering}.md"
    if out_dir is not None:
        pkg["path"] = file_name
    g.put(pkg, KERNEL_ACTOR)
    if out_dir is not None:
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / file_name).write_text(text, encoding="utf-8", newline="\n")
        write_computed(out_path, exports)
    return pkg, text


def latest_package(g: Graph, episode_id: str, *, rendering: str = "full") -> dict | None:
    """The most recently built `DecisionPackage` for `episode_id` under `rendering`, or
    `None` if none has been built yet.

    **"Most recent" means latest log position, not highest `rev`.** `build_package`
    never revises an existing `DecisionPackage` — every build mints a fresh id
    (`pkg-{episode}-{rendering}-{n}`) at `rev` 1 — so comparing `rev` across
    candidates would almost always find a tie. The only signal that actually orders
    two builds is the append-only log's own sequence: this walks `g.log()` and keeps
    the *last* `DecisionPackage` log entry whose currently-stored object still matches
    `episode_id`/`rendering`, which is well-defined even in the (currently impossible,
    but not schema-forbidden) case of a package later revised in place — `g.get(id)`
    always returns its latest revision regardless of which log entry pointed at it.

    Tolerant of a hand-edited store: a log entry, or the object it names, that is
    missing, of the wrong type, or shaped wrong is skipped rather than raised — this
    is G4's own binding check (via `latest_package_hash`) reading back an artefact it
    did not just produce, so it cannot assume the shape a clean `build_package` call
    would have left.

    Returns the whole object — not just `hash` — so a caller needing another stored
    field (`graphSnapshotHash`, `kernelVersion`; `to_madr`'s "More Information" line,
    pre-flight defect D18) reads it from *this* package, never from a value recomputed
    against the live graph, which a `DecisionPackage` built earlier no longer matches.
    """
    best_seq = -1
    best_pkg: dict | None = None
    for entry in g.log():
        if not isinstance(entry, dict) or entry.get("type") != "DecisionPackage":
            continue
        seq = entry.get("seq")
        oid = entry.get("id")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq <= best_seq:
            continue
        if not isinstance(oid, str) or not g.has(oid):
            continue
        pkg = g.get(oid)
        if pkg.get("episode") != episode_id or pkg.get("rendering") != rendering:
            continue
        h = pkg.get("hash")
        if not isinstance(h, str) or not h:
            continue
        best_seq, best_pkg = seq, pkg
    return best_pkg


def latest_package_hash(g: Graph, episode_id: str, *, rendering: str = "full") -> str | None:
    """The `hash` of `latest_package(g, episode_id, rendering=rendering)`, or `None`."""
    pkg = latest_package(g, episode_id, rendering=rendering)
    return pkg.get("hash") if pkg is not None else None


__all__ = [
    "GATE_LABELS", "SECTIONS", "ai_assistance_summary", "build_package", "check_citations",
    "content_snapshot_hash", "episode_exclusions", "evidence_pointer", "evidence_title",
    "latest_package", "latest_package_hash", "metadata_withheld", "ready_text",
    "readiness_ready_text", "render_package", "rating_scale_legend", "tailoring_note",
]
