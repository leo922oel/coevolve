#!/usr/bin/env python3
"""Validate an exported cowork profile before it leaves the machine.

Two gates in one pass, because they protect the same moment — the instant a
profile stops being local:

  * **shape** — the subset of JSON Schema the profile contract actually uses.
    Implemented here rather than pulled from PyPI so the plugin installs and
    self-tests on a machine with nothing but python3.
  * **de-identification** — the same denylist that guards every other exit. A
    single hit blocks the export and names the term, so it can be re-abstracted
    rather than guessed at.

A missing denylist fails **open** with a loud warning: a broken guard must not
silently become a wall, but it must never be silent either.

Exit 0 = safe to export. Non-zero = do not export; stderr says why and where.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "profile.schema.json"


class Invalid(Exception):
    pass


def _resolve(schema: dict, root: dict) -> dict:
    seen = 0
    while "$ref" in schema and seen < 10:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            raise Invalid(f"unsupported $ref: {ref}")
        node = root
        for part in ref[2:].split("/"):
            node = node[part]
        schema = node
        seen += 1
    return schema


def validate(value, schema: dict, root: dict, path: str, errors: list[str]) -> None:
    schema = _resolve(schema, root)

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}, got {value!r}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")
        return

    expected = schema.get("type")
    if expected and not _type_ok(value, expected):
        errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
        return

    if expected == "object" or isinstance(value, dict) and ("properties" in schema or "required" in schema):
        _validate_object(value, schema, root, path, errors)
    elif expected == "array":
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                validate(item, item_schema, root, f"{path}[{i}]", errors)
    elif expected == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: must not be empty")
        pattern = schema.get("pattern")
        if pattern and not re.match(pattern, value):
            errors.append(f"{path}: {value!r} does not match {pattern}")
    elif expected == "integer":
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below the minimum of {schema['minimum']}")


def _validate_object(value, schema, root, path, errors) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object")
        return
    for key in schema.get("required", []):
        if key not in value:
            errors.append(f"{path or '<root>'}: missing required field {key!r}")
    props = schema.get("properties", {})
    extra = schema.get("additionalProperties", True)
    for key, sub in value.items():
        here = f"{path}.{key}" if path else key
        if key in props:
            validate(sub, props[key], root, here, errors)
        elif isinstance(extra, dict):
            validate(sub, extra, root, here, errors)
        elif extra is False:
            errors.append(f"{path or '<root>'}: unexpected field {key!r} — "
                          f"the profile contract lists what may be exported, and this is not on it")


def _type_ok(value, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return {
        "object": dict, "array": list, "string": str, "boolean": bool,
    }.get(expected, object) is not object and isinstance(value, {
        "object": dict, "array": list, "string": str, "boolean": bool,
    }[expected])


def denylist_hits(text: str, denylist: Path) -> list[str]:
    hits = []
    for raw in denylist.read_text(encoding="utf-8", errors="replace").splitlines():
        term = raw.strip()
        if not term or term.startswith("#"):
            continue
        if term.lower() in text.lower():
            hits.append(term)
    return hits


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("profile", type=Path)
    parser.add_argument("--denylist", type=Path, default=None,
                        help="terms that must never be exported")
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    args = parser.parse_args(argv)

    try:
        data = json.loads(args.profile.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"validate_profile: cannot read profile: {exc}", file=sys.stderr)
        return 2

    root = json.loads(args.schema.read_text(encoding="utf-8"))
    errors: list[str] = []
    try:
        validate(data, root, root, "", errors)
    except Invalid as exc:
        errors.append(str(exc))

    if args.denylist is not None:
        if not args.denylist.exists():
            print(f"validate_profile warning: denylist not found at {args.denylist} — "
                  f"shape was checked but nothing was screened. Create it to enable the guard.",
                  file=sys.stderr)
        else:
            hits = denylist_hits(json.dumps(data, ensure_ascii=False), args.denylist)
            for term in hits:
                errors.append(f"de-identification: profile contains the denylisted term {term!r} — "
                              f"re-abstract the claim; do not export")

    if errors:
        for err in errors:
            print(f"validate_profile: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
