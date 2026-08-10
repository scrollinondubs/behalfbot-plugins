#!/usr/bin/env python3
"""Fail if anything in this plugin imports outside the standard library.

The plugin's whole dependency policy is that it has no dependencies, which
CONTRIBUTING.md's pinning rule is satisfied by in the strongest way available.
A policy like that survives exactly as long as something checks it, so this
runs from setup.sh and again from validate.sh.

Parses rather than greps: an import inside a function or a try block is still
an import.

Usage:  python3 scripts/check_stdlib_only.py [plugin_dir]
"""
from __future__ import annotations

import ast
import pathlib
import sys

# Modules this plugin ships, which import each other by bare name because
# scripts/ is on sys.path at runtime.
LOCAL_MODULES = {
    "accommodation_errors",
    "amadeus_client",
    "amadeus_supplier",
    "call_budget",
    "check_stdlib_only",
    "mcp_server",
    "supplier",
    "_harness",
}


def top_level_imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # A relative import has no module of its own to check.
            if node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1] if len(argv) > 1 else pathlib.Path(__file__).resolve().parent.parent)
    stdlib = getattr(sys, "stdlib_module_names", None)
    if stdlib is None:
        print(
            "[accommodation-search] WARN: python3 < 3.10 cannot enumerate the "
            "standard library, so the import audit was skipped."
        )
        return 0

    allowed = set(stdlib) | LOCAL_MODULES | {"__future__"}
    offenders: list[str] = []
    checked = 0

    for path in sorted(root.rglob("*.py")):
        if "node_modules" in path.parts or "__pycache__" in path.parts:
            continue
        checked += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as error:
            print(f"[accommodation-search] FAIL: cannot parse {path}: {error}", file=sys.stderr)
            return 1
        for name in sorted(top_level_imports(tree) - allowed):
            offenders.append(f"{path.relative_to(root)}: {name}")

    if offenders:
        print(
            "[accommodation-search] FAIL: these imports are not in the standard "
            "library, and this plugin has no dependency file to pin them in:",
            file=sys.stderr,
        )
        for line in offenders:
            print(f"[accommodation-search]   {line}", file=sys.stderr)
        print(
            "[accommodation-search] Either drop the import or add it to "
            "requirements.txt with an exact pin and a lockfile, per "
            "CONTRIBUTING.md.",
            file=sys.stderr,
        )
        return 1

    print(f"[accommodation-search] import audit clean: {checked} file(s), standard library only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
