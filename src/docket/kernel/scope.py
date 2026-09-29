"""Scope-of-validity checker (design §7.4). Detects GAO-23-106549 F1 and F4 mechanically.

Every check here must tolerate a hand-edited or partially-written store: a missing or
malformed catalogue field is reported once by the structural `schema` rule, and this
checker must never itself raise for it. Fields are read with `.get()` and a dangling
reference (an id that does not resolve in the graph) is skipped rather than followed —
ref-integrity is a different rule's job. A date that cannot be parsed is treated as
unknown, not as "in scope" or "lapsed": the lapsed/reaccreditation check it feeds is
skipped and a `scope-unknown` warning names the field instead. Date comparisons are at
day resolution — two dates in the same month are not treated as equal.
"""

from __future__ import annotations

from docket.kernel.findings import Finding
from docket.objects import is_content, is_exclusion_ref, is_gap_ref
from docket.schema import catalogue
from docket.store import Graph

# A private copy of the catalogue, taken at import and never mutated: catalogue() hands
# out a deep copy on every call, and LEVELS is looked up on every check.
LEVELS: list[str] = catalogue()["classification_levels"]


def level_rank(level: str) -> int:
    return LEVELS.index(level)


def _date_key(s: object) -> tuple[int, int, int] | None:
    """Parse `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` (a trailing `T...` time is dropped)
    into a (year, month, day) tuple, defaulting missing month/day to 1.

    Never raises: a non-string or unparsable value returns None so the caller can treat
    the comparison it feeds as unknown rather than as in-scope, lapsed, or current.
    """
    if not isinstance(s, str):
        return None
    parts = s.split("T", 1)[0].split("-")
    if not 1 <= len(parts) <= 3:
        return None
    try:
        y = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 1
        d = int(parts[2]) if len(parts) > 2 else 1
    except ValueError:
        return None
    return (y, m, d)


def _metadata_missing(ev: dict) -> list[str]:
    missing = []
    if not is_content(ev.get("pointer")):
        missing.append("pointer")
    if not is_content(ev.get("scopeOfValidity")):
        missing.append("scopeOfValidity")
    if ev.get("reviewStatus") == "draft":
        missing.append("review")
    if ev.get("evidenceType") == "MSStudy" and not is_content(ev.get("vvaRecord")):
        missing.append("vvaRecord")
    return missing


def _claim_level(c: dict) -> tuple[str | None, int | None]:
    """The claim's assessableAt.level and its rank, or (None, None) if unreadable."""
    at = c.get("assessableAt")
    level = at.get("level") if isinstance(at, dict) else None
    return level, (level_rank(level) if level in LEVELS else None)


def check_scope(g: Graph, episode_id: str) -> list[Finding]:
    ep = g.get(episode_id)
    charter_id = ep.get("charter")
    charter = g.get(charter_id) if isinstance(charter_id, str) and g.has(charter_id) else None
    out: list[Finding] = []

    as_of = ep.get("asOf")
    as_of_key = _date_key(as_of)
    if as_of_key is None:
        out.append(Finding("scope-unknown", "warning", (episode_id,),
                            "episode asOf could not be parsed as a date"))

    scenario_conditions: set[str] = set()
    for sid in ep.get("scenarios") or []:
        if not isinstance(sid, str) or not g.has(sid):
            continue
        conditions = g.get(sid).get("conditions")
        if isinstance(conditions, list):
            scenario_conditions |= {c for c in conditions if isinstance(c, str)}

    for cid in ep.get("claims") or []:
        if not isinstance(cid, str) or not g.has(cid):
            continue
        c = g.get(cid)
        sb = c.get("supportedBy")
        if not isinstance(sb, list):
            continue
        claim_qc = c.get("questionClass")
        claim_level_name, claim_level = _claim_level(c)

        for entry in sb:
            if not isinstance(entry, dict):
                continue
            ev_id = entry.get("evidence")
            if not isinstance(ev_id, str) or not g.has(ev_id):
                continue
            ev = g.get(ev_id)

            if ev.get("reviewStatus") == "rejected":
                out.append(Finding("claim-on-rejected-evidence", "blocking", (cid, ev_id),
                                    "claim rests on evidence a reviewer rejected"))

            sov = ev.get("scopeOfValidity")

            if not is_content(sov):
                out.append(Finding("scope-unknown", "warning", (cid, ev_id),
                                    "evidence scope of validity is a gap or exclusion"))
            elif isinstance(sov, dict):
                sov_qc = sov.get("questionClass")
                # A claim with no readable questionClass has already been reported by
                # the schema rule; comparing a real sov_qc against it would produce a
                # spurious ReusePastPurpose finding, not a meaningful one.
                if isinstance(claim_qc, str) and sov_qc != claim_qc:
                    justification = entry.get("reuseJustification")
                    if isinstance(justification, dict) and is_content(justification):
                        out.append(Finding(
                            "reuse-justified", "info", (cid, ev_id),
                            f"evidence built for {sov_qc} reused for {claim_qc} with "
                            f"justification by {justification.get('authority')}"))
                    else:
                        out.append(Finding(
                            "ReusePastPurpose", "blocking", (cid, ev_id),
                            f"evidence built to answer '{sov.get('builtToAnswer')}' "
                            f"({sov_qc}) supports a {claim_qc} claim with no reuse "
                            "justification (AR 5-11 ¶4-2i(1); GAO-23-106549 F1)"))
                conditions = sov.get("conditions")
                conds = ({c for c in conditions if isinstance(c, str)}
                         if isinstance(conditions, list) else set())
                if conds and scenario_conditions and not (conds & scenario_conditions):
                    out.append(Finding(
                        "condition-mismatch", "warning", (cid, ev_id),
                        "evidence conditions share nothing with the episode's scenarios"))
                vu = sov.get("validUntil")
                if vu is not None:
                    vu_key = _date_key(vu)
                    if vu_key is None:
                        out.append(Finding(
                            "scope-unknown", "warning", (ev_id,),
                            "scope validUntil could not be parsed as a date"))
                    elif as_of_key is not None and vu_key < as_of_key:
                        out.append(Finding(
                            "scope-lapsed", "warning", (ev_id,),
                            f"scope validUntil {vu} is before episode asOf {as_of}"))
            else:
                out.append(Finding("scope-unknown", "warning", (cid, ev_id),
                                    "evidence scope of validity is not an object"))

            if claim_level is None:
                continue
            cls = ev.get("classification")
            metadata_level = cls.get("metadataLevel") if isinstance(cls, dict) else None
            if metadata_level in LEVELS and level_rank(metadata_level) > claim_level:
                out.append(Finding(
                    "NotAssessableAtLevel", "blocking", (cid, ev_id),
                    f"evidence metadata is {metadata_level}; claim must be assessable "
                    f"at {claim_level_name}"))
                continue
            missing = _metadata_missing(ev)
            if missing:
                out.append(Finding(
                    "NotAssessableAtLevel", "blocking", (cid, ev_id),
                    "evidence metadata missing at claim level: " + ", ".join(missing) +
                    " (GAO-23-106549 F4/F5)"))
                continue
            ev_level = cls.get("level") if isinstance(cls, dict) else None
            if ev_level in LEVELS and level_rank(ev_level) > claim_level:
                out.append(Finding(
                    "assessable-with-classified-value", "info", (cid, ev_id),
                    f"claim assessable at {claim_level_name} while evidence value is "
                    f"{ev_level} (CDRL A013/A103 link)"))

    for mid in ep.get("models") or []:
        if not isinstance(mid, str) or not g.has(mid):
            continue
        m = g.get(mid)
        m_qc = m.get("questionClass")
        if charter is not None and m_qc != charter.get("questionClass"):
            # A model used outside its intended purpose is EXE-3's own subject matter
            # ("were the models used to support the analyses appropriate for their
            # intended purpose?"), so it gets a model-scoped rule of its own rather than
            # sharing ReusePastPurpose (which is about evidence a Claim rests on) or
            # ReaccreditationRequired (¶4-2i(3), the elapsed-time rule below).
            out.append(Finding(
                "ModelUsePastPurpose", "warning", (mid,),
                f"model intended for {m_qc} used for {charter.get('questionClass')} "
                "(AR 5-11 ¶4-2i(1); GAO-23-106549 F1)"))
        v = m.get("vvaRecord")
        if is_content(v) and isinstance(v, str) and g.has(v):
            acc = g.get(v).get("accreditationDecision")
            if is_content(acc) and isinstance(acc, dict):
                acc_key = _date_key(acc.get("date"))
                if acc_key is None:
                    out.append(Finding(
                        "scope-unknown", "warning", (mid, v),
                        "accreditationDecision.date could not be parsed as a date"))
                elif as_of_key is not None and as_of_key > (acc_key[0] + 3, acc_key[1], acc_key[2]):
                    out.append(Finding(
                        "ReaccreditationRequired", "warning", (mid, v),
                        f"accreditation dated {acc.get('date')} is more than 3 years "
                        f"before {as_of} (AR 5-11 ¶4-2i(3))"))
        elif is_gap_ref(v):
            out.append(Finding(
                "scope-unknown", "warning", (mid,),
                "model has no VVARecord; intended use cannot be checked"))
        elif is_exclusion_ref(v):
            # Symmetric with the gap branch: a typed exclusion is a recorded reason for
            # the absence, not content, so the accreditation check has nothing to read
            # and must say so rather than fall through in silence.
            out.append(Finding(
                "scope-unknown", "warning", (mid,),
                "model VV&A record is a typed exclusion; intended use cannot be checked"))

    return sorted(set(out))
