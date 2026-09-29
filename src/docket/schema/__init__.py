"""Object catalogue, generated JSON Schemas, and per-object validation."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from docket.schema.generate import CATALOGUE, OUT, load_catalogue

__all__ = ["catalogue", "load_schema", "validate_object", "CATALOGUE", "OUT"]


@lru_cache(maxsize=1)
def _catalogue() -> dict:
    return load_catalogue()


@cache
def _schema(type_name: str) -> dict:
    return json.loads((OUT / f"{type_name}.schema.json").read_text())


def catalogue() -> dict:
    """The object catalogue. A fresh copy each call: callers may edit what they get."""
    return deepcopy(_catalogue())


def load_schema(type_name: str) -> dict:
    """One generated JSON Schema. A fresh copy each call, for the same reason."""
    return deepcopy(_schema(type_name))


@cache
def _validator(type_name: str) -> Draft202012Validator:
    return Draft202012Validator(_schema(type_name))


def validate_object(obj: Any) -> list[str]:
    if not isinstance(obj, dict):
        return ["object must be a JSON object"]
    t = obj.get("type")
    if t not in _catalogue()["types"]:
        return [f"unknown type {t!r}"]
    errs = sorted(_validator(t).iter_errors(obj), key=lambda e: (list(map(str, e.path)), e.message))
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errs]


def schema_dir() -> Path:
    return OUT
