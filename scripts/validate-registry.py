#!/usr/bin/env python3
"""validate-registry.py - check registry.json and the plugin manifests agree.

`registry.json` is how the chassis discovers what lives in this repo. A plugin
directory that is not listed is invisible; a listed path that does not exist is
a broken install. Neither failure shows up until someone tries to install the
plugin, which is exactly the kind of bug an outside contributor will introduce
by adding a directory and forgetting the registry entry (or the reverse).

Deliberately dependency-free so CI needs no install step, and deliberately
noisy: every problem found is printed, not just the first one.

Usage:
    python3 scripts/validate-registry.py
Exit 0 if consistent, 1 otherwise.
"""
from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
REGISTRY = REPO / "registry.json"
MANIFEST_NAME = "openclaw.plugin.json"

# Directories at the repo root that are not plugins and must not be expected to
# carry a manifest. Anything else at root with a manifest has to be registered.
NON_PLUGIN_DIRS = {"docs", "tools", "scripts", ".github", ".git"}

# Fields the chassis reads off every registry entry. Missing any of them means a
# plugin that resolves at discovery time and then fails at install time.
REQUIRED_REGISTRY_FIELDS = ("name", "path", "description", "min_chassis_version")

# Fields the chassis reads off every plugin manifest.
REQUIRED_MANIFEST_FIELDS = ("id", "name", "description", "version")


def fail(problems: list[str], msg: str) -> None:
    problems.append(msg)


def main() -> int:
    problems: list[str] = []

    if not REGISTRY.exists():
        print(f"FAIL: {REGISTRY.name} not found at repo root")
        return 1

    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: {REGISTRY.name} is not valid JSON: {exc}")
        return 1

    entries = registry.get("plugins")
    if not isinstance(entries, list):
        print(f"FAIL: {REGISTRY.name} has no 'plugins' array")
        return 1

    listed_paths: set[str] = set()
    seen_names: set[str] = set()

    for i, entry in enumerate(entries):
        where = f"registry.json plugins[{i}]"
        if not isinstance(entry, dict):
            fail(problems, f"{where}: not an object")
            continue

        for field in REQUIRED_REGISTRY_FIELDS:
            if not entry.get(field):
                fail(problems, f"{where} ({entry.get('name', '?')}): missing required field '{field}'")

        name = entry.get("name")
        if name in seen_names:
            fail(problems, f"{where}: duplicate plugin name '{name}'")
        seen_names.add(name)

        path = entry.get("path")
        if not path:
            continue
        listed_paths.add(path)

        plugin_dir = REPO / path
        if not plugin_dir.is_dir():
            fail(problems, f"{where} ({name}): path '{path}' does not exist in the repo")
            continue

        manifest_path = plugin_dir / MANIFEST_NAME
        if not manifest_path.exists():
            fail(problems, f"{name}: registered but has no {MANIFEST_NAME}")
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(problems, f"{name}: {MANIFEST_NAME} is not valid JSON: {exc}")
            continue

        for field in REQUIRED_MANIFEST_FIELDS:
            if not manifest.get(field):
                fail(problems, f"{name}: {MANIFEST_NAME} missing required field '{field}'")

    # The reverse direction, which is the one people actually forget: a plugin
    # directory that exists, carries a manifest, and is not registered. It looks
    # completely fine in the tree and is simply never discovered.
    for child in sorted(REPO.iterdir()):
        if not child.is_dir() or child.name in NON_PLUGIN_DIRS or child.name.startswith("."):
            continue
        if (child / MANIFEST_NAME).exists() and child.name not in listed_paths:
            fail(problems, f"{child.name}: has {MANIFEST_NAME} but is not listed in registry.json")

    if problems:
        print(f"FAIL: {len(problems)} problem(s) between registry.json and the plugin manifests\n")
        for p in problems:
            print(f"  - {p}")
        print("\nIf you added a plugin, add a matching entry to registry.json.")
        print("If you removed one, remove its entry too.")
        return 1

    print(f"OK: {len(entries)} plugin(s) registered, all paths and manifests consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
