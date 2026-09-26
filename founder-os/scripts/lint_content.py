#!/usr/bin/env python3
"""lint_content.py - check FounderOS content against the authoring templates.

Walks a content root (a directory holding core/, contrib/, gates/ and skills/)
and checks:

  - every content file has frontmatter with the fields its type requires
  - framework cards and gate specs carry every required section heading
  - ids are unique and match the filename (or the skill directory name)
  - every core framework card names a gate, and that gate exists in gates/
  - every stage skill names a gate that exists
  - every [[wiki-link]] resolves, and core never links into contrib

The format rules live in templates/authoring/README.md. Stdlib only, so it runs
in CI with no install step. That is also why frontmatter is a restricted subset
(`key: value` and `key: [a, b]`) rather than full YAML.

Usage:
    python3 lint_content.py [--root DIR]
Exit 0 when clean, 1 with every problem printed otherwise.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent

TIERS = ("core", "contrib")
STAGES = range(0, 10)

REQUIRED_FIELDS = {
    "framework-card": ("id", "type", "title", "stage", "tier", "sources"),
    "concept": ("id", "type", "title", "tier"),
    "gate": ("id", "type", "title", "stage", "signoff", "fail_routes_to"),
    "stage-skill": ("name", "description", "plugin", "type", "stage", "gate"),
}

REQUIRED_SECTIONS = {
    "framework-card": (
        "Purpose",
        "When to use",
        "Principles",
        "Procedure",
        "Artifacts produced",
        "Anti-patterns",
        "Gate criteria",
        "Sources",
        "Sean's notes",
    ),
    "gate": ("Required evidence", "Auditor checks", "Pass/fail rubric", "Failure routing"),
    "stage-skill": ("Read the founder context first", "Current stage only", "Procedure", "Ledger writes"),
    "concept": (),
}

SIGNOFF_VALUES = ("claude", "claude+sean")
PLUGIN_ID = "behalfbot-founder-os"

WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
ID_SHAPE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_frontmatter(text: str) -> tuple[dict[str, object] | None, str, str | None]:
    """Return (fields, body, error). fields is None when there is no frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, text, "frontmatter opened with --- but never closed"

    fields: dict[str, object] = {}
    for n, raw in enumerate(lines[1:end], start=2):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            return None, text, f"line {n}: expected 'key: value', got {raw!r}"
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fields[key] = [_unquote(v.strip()) for v in inner.split(",")] if inner else []
        else:
            fields[key] = _unquote(value)
    return fields, "\n".join(lines[end + 1:]), None


def _unquote(v: str) -> str:
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def headings(body: str) -> set[str]:
    return {m.group(1).strip() for m in re.finditer(r"^##\s+(.+?)\s*$", body, re.MULTILINE)}


def as_stage(value: object) -> int | None:
    try:
        n = int(str(value))
    except ValueError:
        return None
    return n if n in STAGES else None


class Item:
    def __init__(self, path: pathlib.Path, rel: str, kind: str, fields: dict, body: str, tier: str | None):
        self.path, self.rel, self.kind, self.fields, self.body, self.tier = path, rel, kind, fields, body, tier

    @property
    def ident(self) -> str:
        return str(self.fields.get("name" if self.kind == "stage-skill" else "id", ""))


def collect(root: pathlib.Path, problems: list[str]) -> list[Item]:
    items: list[Item] = []
    sources: list[tuple[pathlib.Path, str | None]] = []
    for tier in TIERS:
        sources += [(p, tier) for p in sorted((root / tier).rglob("*.md"))]
    sources += [(p, None) for p in sorted((root / "gates").rglob("*.md"))]
    sources += [(p, None) for p in sorted((root / "skills").glob("*/SKILL.md"))]

    for path, tier in sources:
        if path.name == "README.md":
            continue
        rel = str(path.relative_to(root))
        fields, body, err = parse_frontmatter(path.read_text(encoding="utf-8"))
        if err:
            problems.append(f"{rel}: {err}")
            continue
        if fields is None:
            problems.append(f"{rel}: no frontmatter")
            continue
        kind = str(fields.get("type", ""))
        if kind not in REQUIRED_FIELDS:
            problems.append(f"{rel}: unknown or missing type {kind!r} (expected one of {', '.join(REQUIRED_FIELDS)})")
            continue
        items.append(Item(path, rel, kind, fields, body, tier))
    return items


def check_item(item: Item, problems: list[str]) -> None:
    f, rel = item.fields, item.rel

    for field in REQUIRED_FIELDS[item.kind]:
        value = f.get(field)
        if value in (None, "", []):
            problems.append(f"{rel}: missing required frontmatter field '{field}'")

    missing = [s for s in REQUIRED_SECTIONS[item.kind] if s not in headings(item.body)]
    if missing:
        problems.append(f"{rel}: missing section(s) {', '.join('## ' + s for s in missing)}")

    ident = item.ident
    if ident and not ID_SHAPE.match(ident):
        problems.append(f"{rel}: id {ident!r} must be lowercase kebab-case")
    expected = item.path.parent.name if item.kind == "stage-skill" else item.path.stem
    if ident and ident != expected:
        problems.append(f"{rel}: id {ident!r} does not match its file or directory name {expected!r}")

    if "stage" in f and as_stage(f["stage"]) is None:
        problems.append(f"{rel}: stage {f['stage']!r} is not an integer 0-9")

    if item.tier and "tier" in f and f["tier"] != item.tier:
        problems.append(f"{rel}: tier {f['tier']!r} but the file lives under {item.tier}/")

    if item.kind == "framework-card" and not isinstance(f.get("sources"), list):
        problems.append(f"{rel}: sources must be a list, e.g. sources: [some-source-id]")

    if item.kind == "gate":
        if f.get("signoff") not in SIGNOFF_VALUES:
            problems.append(f"{rel}: signoff must be one of {', '.join(SIGNOFF_VALUES)}")
        stage, back = as_stage(f.get("stage", "")), as_stage(f.get("fail_routes_to", ""))
        if back is None:
            problems.append(f"{rel}: fail_routes_to must be a stage number 0-9")
        elif stage is not None and back > stage:
            problems.append(f"{rel}: fail_routes_to {back} is ahead of the gate's own stage {stage}")
        if stage is not None and stage >= 3 and f.get("signoff") != "claude+sean":
            problems.append(f"{rel}: gates from stage 3 onward need signoff: claude+sean")

    if item.kind == "stage-skill" and f.get("plugin") != PLUGIN_ID:
        problems.append(f"{rel}: plugin must be {PLUGIN_ID!r}")


def check_references(items: list[Item], problems: list[str]) -> None:
    by_id: dict[str, Item] = {}
    for item in items:
        if not item.ident:
            continue
        if item.ident in by_id:
            problems.append(f"{item.rel}: duplicate id {item.ident!r} (also {by_id[item.ident].rel})")
        else:
            by_id[item.ident] = item

    gates = {i.ident for i in items if i.kind == "gate"}

    for item in items:
        gate = item.fields.get("gate")
        if item.kind == "framework-card":
            if item.tier == "core" and not gate:
                problems.append(f"{item.rel}: core cards must name the gate they serve")
            elif gate and gate not in gates:
                problems.append(f"{item.rel}: names gate {gate!r}, which does not exist in gates/")
        if item.kind == "stage-skill" and gate and gate not in gates:
            problems.append(f"{item.rel}: names gate {gate!r}, which does not exist in gates/")

        for m in WIKI_LINK.finditer(item.body):
            target_id = m.group(1).strip()
            target = by_id.get(target_id)
            if target is None or target.kind not in ("concept", "framework-card"):
                problems.append(f"{item.rel}: [[{target_id}]] does not resolve to a concept note or card")
            elif item.tier != "contrib" and target.tier == "contrib":
                problems.append(f"{item.rel}: [[{target_id}]] links into contrib/, which core content must not depend on")


def lint(root: pathlib.Path) -> list[str]:
    problems: list[str] = []
    items = collect(root, problems)
    for item in items:
        check_item(item, problems)
    check_references(items, problems)
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=PLUGIN_DIR, help="content root (default: the plugin dir)")
    args = ap.parse_args(argv)

    problems = lint(args.root)
    if problems:
        print(f"FAIL: {len(problems)} content problem(s) under {args.root}")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK: content under {args.root} is clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
