#!/usr/bin/env python3
"""Six small checks for CSV, JSON, JSONL, and local datasets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"{path}: missing or duplicate CSV headers")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError(f"{path}: inconsistent column count")
        return rows


def profile(path: Path) -> dict:
    rows = read_csv(path)
    fields = list(rows[0]) if rows else csv_headers(path)
    return {"rows": len(rows), "columns": {
        field: {"empty": sum(not row[field].strip() for row in rows),
                "distinct": len({row[field] for row in rows})} for field in fields}}


def csv_headers(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return next(csv.reader(handle), [])


def validate(path: Path, schema: dict) -> list[str]:
    rows = read_csv(path)
    required = schema.get("required", [])
    types = schema.get("types", {})
    unique = schema.get("unique", [])
    if not isinstance(required, list) or not isinstance(types, dict) or not isinstance(unique, list):
        raise ValueError("schema needs required/unique arrays and a types object")
    fields = set(csv_headers(path))
    issues = [f"missing column: {key}" for key in required if key not in fields]
    seen: dict[str, set[str]] = {key: set() for key in unique}
    for line, row in enumerate(rows, 2):
        for key in required:
            if key in row and not row[key].strip():
                issues.append(f"line {line}: {key} is empty")
        for key, kind in types.items():
            if key not in row or not row[key].strip():
                continue
            try:
                if kind == "integer":
                    int(row[key])
                elif kind == "decimal":
                    value = Decimal(row[key])
                    if not value.is_finite():
                        raise ValueError()
                elif kind == "date":
                    date.fromisoformat(row[key])
                elif kind != "string":
                    raise ValueError(f"unsupported type: {kind}")
            except (ValueError, InvalidOperation):
                issues.append(f"line {line}: {key} is not {kind}")
        for key in unique:
            if key not in row:
                continue
            if row[key] in seen[key]:
                issues.append(f"line {line}: duplicate {key}: {row[key]}")
            seen[key].add(row[key])
    return issues


def shape(value: object) -> object:
    if isinstance(value, dict):
        return {key: shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def shape_diff(left: object, right: object, prefix: str = "$") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        issues = [f"{prefix}.{key}: removed" for key in sorted(left.keys() - right.keys())]
        issues += [f"{prefix}.{key}: added" for key in sorted(right.keys() - left.keys())]
        for key in sorted(left.keys() & right.keys()):
            issues += shape_diff(left[key], right[key], prefix + "." + key)
        return issues
    return [] if left == right else [f"{prefix}: {left} -> {right}"]


def duplicates(root: Path) -> list[list[str]]:
    groups: dict[str, list[str]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        groups.setdefault(digest, []).append(str(path.relative_to(root)))
    return [group for group in groups.values() if len(group) > 1]


def jsonl_count(path: Path, field: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(item, dict) or field not in item:
            raise ValueError(f"{path}:{line_number}: missing {field}")
        counts[str(item[field])] += 1
    return dict(sorted(counts.items()))


def date_gaps(path: Path, column: str) -> list[str]:
    rows = read_csv(path)
    if not rows or column not in rows[0]:
        raise ValueError(f"missing date column: {column}")
    dates = sorted({date.fromisoformat(row[column]) for row in rows})
    date_set = set(dates)
    missing = []
    current = dates[0]
    while current <= dates[-1]:
        if current not in date_set:
            missing.append(current.isoformat())
        current += timedelta(days=1)
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("profile", "duplicates"):
        commands.add_parser(name).add_argument("path", type=Path)
    check = commands.add_parser("validate")
    check.add_argument("path", type=Path)
    check.add_argument("schema", type=Path)
    diff = commands.add_parser("shape-diff")
    diff.add_argument("old", type=Path)
    diff.add_argument("new", type=Path)
    count = commands.add_parser("jsonl-count")
    count.add_argument("path", type=Path)
    count.add_argument("field")
    gaps = commands.add_parser("date-gaps")
    gaps.add_argument("path", type=Path)
    gaps.add_argument("column")
    args = parser.parse_args(argv)
    try:
        if args.command == "profile":
            result, issues = profile(args.path), []
        elif args.command == "validate":
            result = issues = validate(args.path, json.loads(args.schema.read_text(encoding="utf-8")))
        elif args.command == "shape-diff":
            old = shape(json.loads(args.old.read_text(encoding="utf-8")))
            new = shape(json.loads(args.new.read_text(encoding="utf-8")))
            result = issues = shape_diff(old, new)
        elif args.command == "duplicates":
            result, issues = duplicates(args.path), []
        elif args.command == "jsonl-count":
            result, issues = jsonl_count(args.path, args.field), []
        else:
            result = issues = date_gaps(args.path, args.column)
    except (OSError, UnicodeError, ValueError, InvalidOperation) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
