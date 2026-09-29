"""The GAO 36-question research standard, tailorings and doctrine crosswalk, as data."""

from __future__ import annotations

import re
from copy import deepcopy
from functools import cache, lru_cache
from pathlib import Path

import yaml

HERE = Path(__file__).parent
_TAILORING_NAME_RE = re.compile(r"^[a-z0-9-]+$")


@lru_cache(maxsize=1)
def _standard() -> dict:
    return yaml.safe_load((HERE / "research-standards-36.yaml").read_text())


@lru_cache(maxsize=1)
def _crosswalk() -> list[dict]:
    return yaml.safe_load((HERE / "crosswalk.yaml").read_text())


@lru_cache(maxsize=1)
def _rules() -> list[dict]:
    return yaml.safe_load((HERE / "rules.yaml").read_text())


def load_standard() -> dict:
    """The 36-question standard. A fresh copy each call: callers may edit what they get."""
    return deepcopy(_standard())


def question_ids() -> list[str]:
    return [q["id"] for q in _standard()["questions"]]


def published_21() -> list[str]:
    return [q["id"] for q in _standard()["questions"] if q["in_published_21"]]


def question(qid: str) -> dict:
    for q in _standard()["questions"]:
        if q["id"] == qid:
            return deepcopy(q)
    raise KeyError(qid)


@cache
def _tailoring(name: str) -> dict:
    raw = yaml.safe_load((HERE / "tailorings" / f"{name}.yaml").read_text())
    default = bool(raw.get("default_applicable", False))
    applicable = set(raw.get("applicable") or [])
    overrides = raw.get("overrides") or {}
    questions = {}
    for qid in question_ids():
        app = default or qid in applicable
        reason = None if app else raw.get("default_reason")
        if qid in overrides:
            reason = overrides[qid].get("tailoringReason", reason)
        questions[qid] = {"applicable": app, "tailoringReason": reason}
    return {"name": raw["name"], "source": raw["source"], "note": raw.get("note"),
            "questions": questions}


def load_tailoring(name: str) -> dict:
    # The name becomes a path segment; keep it to a bare slug so it cannot escape the
    # tailorings directory.
    if not isinstance(name, str) or not _TAILORING_NAME_RE.fullmatch(name):
        raise ValueError(f"tailoring name {name!r} is not a bare slug ([a-z0-9-]+)")
    return deepcopy(_tailoring(name))


def load_crosswalk() -> list[dict]:
    return deepcopy(_crosswalk())


def load_rules() -> list[dict]:
    """The 36 scoring rules, one per question. A fresh copy each call."""
    return deepcopy(_rules())
