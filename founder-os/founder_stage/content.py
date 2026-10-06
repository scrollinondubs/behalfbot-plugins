"""Read FounderOS content (cards, concept notes, gate specs, skills) from disk.

The frontmatter parser here is the same flat subset scripts/lint_content.py
enforces: `key: value` and `key: [a, b]`, one per line.
"""
from __future__ import annotations

import os
import pathlib
import re

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text
    fields: dict[str, object] = {}
    for raw in lines[1:end]:
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            fields[key] = split_list(value[1:-1])
        else:
            fields[key] = _unquote(value)
    return fields, "\n".join(lines[end + 1:])


def split_list(inner: str) -> list[str]:
    """Split an inline list on commas outside quotes. Same rule as
    scripts/lint_content.py, so a quoted source citation stays one item."""
    if not inner.strip():
        return []
    parts, buf, quote = [], "", ""
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
        elif ch in "\"'" and not buf.strip():
            quote = ch
            buf += ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [_unquote(v.strip()) for v in parts]


def _unquote(v: str) -> str:
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def section(body: str, heading: str) -> str:
    """The text under one `## heading`, up to the next `##`."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def bullets(text: str) -> list[str]:
    """Top-level `- ` bullets, continuation lines folded in."""
    out: list[str] = []
    for line in text.splitlines():
        if line.startswith("- "):
            out.append(line[2:].strip())
        elif out and line.startswith("  ") and line.strip():
            out[-1] += " " + line.strip()
    return out


class Doc:
    def __init__(self, path: pathlib.Path, root: pathlib.Path):
        self.path = path
        self.rel = str(path.relative_to(root))
        self.fields, self.body = parse_frontmatter(path.read_text(encoding="utf-8"))

    @property
    def id(self) -> str:
        return str(self.fields.get("name") or self.fields.get("id") or "")

    @property
    def stage(self) -> int | None:
        try:
            return int(str(self.fields.get("stage")))
        except ValueError:
            return None

    def links(self) -> list[str]:
        return sorted({m.group(1).strip() for m in WIKI_LINK.finditer(self.body)})


class Content:
    """The plugin's content tree. include_contrib defaults to the operator's
    FOUNDER_OS_INCLUDE_CONTRIB, which the manifest exports from include_contrib."""

    def __init__(self, root: pathlib.Path | str | None = None, *, include_contrib: bool | None = None):
        self.root = pathlib.Path(root) if root else PLUGIN_DIR
        if include_contrib is None:
            include_contrib = os.environ.get("FOUNDER_OS_INCLUDE_CONTRIB", "").strip().lower() in ("1", "true", "yes")
        self.include_contrib = include_contrib

    def _docs(self, pattern: str) -> list[Doc]:
        return [Doc(p, self.root) for p in sorted(self.root.glob(pattern)) if p.name != "README.md"]

    def gate(self, stage: int) -> Doc:
        for doc in self._docs("gates/*.md"):
            if doc.fields.get("type") == "gate" and doc.stage == stage:
                return doc
        raise LookupError(f"no gate spec for stage {stage} in gates/")

    def stage_skill(self, stage: int) -> Doc | None:
        for doc in self._docs("skills/*/SKILL.md"):
            if doc.fields.get("type") == "stage-skill" and doc.stage == stage:
                return doc
        return None

    def cards(self, stage: int) -> list[Doc]:
        """Framework cards for one stage: core always, contrib only when opted in."""
        tiers = ("core", "contrib") if self.include_contrib else ("core",)
        out = []
        for tier in tiers:
            for doc in self._docs(f"{tier}/**/*.md"):
                if doc.fields.get("type") == "framework-card" and doc.stage == stage:
                    out.append(doc)
        return out

    def concepts(self, ids: list[str]) -> list[Doc]:
        tiers = ("core", "contrib") if self.include_contrib else ("core",)
        wanted = set(ids)
        out = []
        for tier in tiers:
            for doc in self._docs(f"{tier}/**/*.md"):
                if doc.fields.get("type") == "concept" and doc.id in wanted:
                    out.append(doc)
        return out

    def basic_cards(self, stage: int) -> list[Doc]:
        """The Basic track's cards for one stage (0-4), in their `order`."""
        docs = [d for d in self._docs(f"basic/stage-{stage}/*.md") if d.fields.get("type") == "card"]
        return sorted(docs, key=lambda d: str(d.fields.get("order", "")))

    def basic_gate(self, stage: int) -> Doc:
        for doc in self._docs(f"basic/gates/stage-{stage}-*.md"):
            if doc.fields.get("type") == "gate" and doc.stage == stage:
                return doc
        raise LookupError(f"no Basic gate for stage {stage} in basic/gates/")
