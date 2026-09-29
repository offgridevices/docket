"""Generate JSON Schema (Draft 2020-12) files from objects.yaml.

Run: python -m docket.schema.generate
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).parent
CATALOGUE = HERE / "objects.yaml"
OUT = HERE / "json"
ID_PATTERN = r"^[a-z0-9][a-z0-9._:-]*$"

DEFS: dict[str, Any] = {
    "id": {"type": "string", "pattern": ID_PATTERN},
    "exclusionRef": {"type": "object", "properties": {"$exclusion": {"$ref": "#/$defs/id"}},
                     "required": ["$exclusion"], "additionalProperties": False},
    "gapRef": {"type": "object", "properties": {"$gap": {"$ref": "#/$defs/id"}},
               "required": ["$gap"], "additionalProperties": False},
    "actor": {"type": "object",
              "properties": {"actorType": {"enum": ["human", "agent", "kernel"]},
                             "actorId": {"type": "string", "minLength": 1}},
              "required": ["actorType", "actorId"], "additionalProperties": False},
    "provenance": {
        "type": "object",
        "properties": {
            "sourceArtifact": {"type": "string"},
            "locator": {"type": "string"},
            "extractor": {"type": "string"},
            "extractedAt": {"type": "string"},
        },
        "required": ["sourceArtifact", "locator", "extractor", "extractedAt"],
        "additionalProperties": False,
    },
    "timestamp": {
        "type": "string",
        "pattern": r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?Z)?$",
    },
}
ENVELOPE: dict[str, Any] = {
    "id": {"$ref": "#/$defs/id"},
    "type": {"type": "string"},
    "rev": {"type": "integer", "minimum": 1},
    "createdBy": {"$ref": "#/$defs/actor"},
    "createdAt": {"$ref": "#/$defs/timestamp"},
    "ingestionProvenance": {"$ref": "#/$defs/provenance"},
    "supersedes": {"$ref": "#/$defs/id"},
    "confidence": {"enum": ["explicit", "inferred", "absent"]},
}
ENVELOPE_REQUIRED = ["id", "type", "rev", "createdBy", "createdAt"]


def load_catalogue() -> dict:
    return yaml.safe_load(CATALOGUE.read_text())


def field_schema(spec: Any) -> dict:
    if isinstance(spec, str):
        spec = {"type": spec}
    if "oneOfTypes" in spec:
        base: dict = {"oneOf": [field_schema(s) for s in spec["oneOfTypes"]]}
    elif "ref" in spec:
        base = {"$ref": "#/$defs/id"}
    elif "enum" in spec:
        base = {"enum": list(spec["enum"])}
    elif "const" in spec:
        base = {"const": spec["const"]}
    else:
        t = spec.get("type", "string")
        base = {"type": t}
        if t == "array":
            base["items"] = field_schema(spec.get("items", {"type": "string"}))
            if "minItems" in spec:
                base["minItems"] = spec["minItems"]
        elif t == "object":
            props = spec.get("properties")
            if props:
                base["properties"] = {k: field_schema(v) for k, v in props.items()}
                req = [k for k, v in props.items() if isinstance(v, dict) and v.get("required")]
                if req:
                    base["required"] = req
            ap = spec.get("additionalProperties", False)
            # A dict names a value schema (e.g. `{type: string}` for a plain id->id map);
            # anything else is the usual open/closed boolean. `bool({...})` would silently
            # collapse a value schema to `True` and lose the constraint entirely, so the
            # two shapes are handled separately rather than falling through one coercion.
            base["additionalProperties"] = field_schema(ap) if isinstance(ap, dict) else bool(ap)
        elif t == "string" and "minLength" in spec:
            base["minLength"] = spec["minLength"]
    if spec.get("slot"):
        return {"oneOf": [base, {"$ref": "#/$defs/exclusionRef"}, {"$ref": "#/$defs/gapRef"}]}
    return base


def _check_ref_targets(type_name: str, spec: dict, cat: dict) -> None:
    """Walk every field spec and confirm each `ref` target is a known type or 'any'."""
    known = set(cat["types"]) | {"any"}

    def check(target: Any, path: str) -> None:
        for name in target if isinstance(target, list) else [target]:
            if name not in known:
                raise ValueError(f"{type_name}.{path}: unknown ref target {name!r}")

    def walk(fs: Any, path: str) -> None:
        if not isinstance(fs, dict):
            return
        if "ref" in fs:
            check(fs["ref"], path)
        for i, alt in enumerate(fs.get("oneOfTypes") or []):
            walk(alt, f"{path}[{i}]")
        if "items" in fs:
            walk(fs["items"], f"{path}.items")
        for name, sub in (fs.get("properties") or {}).items():
            walk(sub, f"{path}.{name}")

    for name, fs in (spec.get("fields") or {}).items():
        walk(fs, name)
    for vname, vspec in (spec.get("variants") or {}).items():
        for name, fs in (vspec.get("fields") or {}).items():
            walk(fs, f"{vname}.{name}")


def build(type_name: str, spec: dict, cat: dict | None = None) -> dict:
    cat = cat if cat is not None else load_catalogue()
    _check_ref_targets(type_name, spec, cat)
    props = dict(ENVELOPE)
    props["type"] = {"const": type_name}
    required = list(ENVELOPE_REQUIRED)
    for name, fs in (spec.get("fields") or {}).items():
        props[name] = field_schema(fs)
        if isinstance(fs, dict) and fs.get("required"):
            required.append(name)
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://docket.offgriddevices.com/schema/{type_name}.schema.json",
        "title": type_name,
        "description": spec.get("doc", ""),
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
        "$defs": DEFS,
    }
    variants = spec.get("variants")
    if variants:
        disc = spec["discriminator"]
        all_of = []
        for value, vspec in variants.items():
            vfields = vspec.get("fields") or {}
            for k, v in vfields.items():
                props.setdefault(k, field_schema(v))
            vreq = [k for k, v in vfields.items() if isinstance(v, dict) and v.get("required")]
            then = {"required": vreq}
            all_of.append({
                "if": {"properties": {disc: {"const": value}}, "required": [disc]},
                "then": then,
            })
        schema["allOf"] = all_of
    return schema


def generate(out: Path | None = None) -> list[Path]:
    out = out or OUT
    out.mkdir(parents=True, exist_ok=True)
    cat = load_catalogue()
    written = []
    for name, spec in cat["types"].items():
        p = out / f"{name}.schema.json"
        p.write_text(json.dumps(build(name, spec, cat), indent=2, sort_keys=True) + "\n")
        written.append(p)
    return written


if __name__ == "__main__":
    for p in generate():
        print(p)
