#!/usr/bin/env python3
"""lint_content.py - check FounderOS content against the authoring templates.

Walks a content root (a directory holding core/, contrib/, gates/ and skills/)
and checks:

  - every content file has frontmatter with the fields its type requires
  - framework cards and gate specs carry every required section heading
  - ids are unique and match the filename (or the skill directory name)
  - every core framework card names a gate, and that gate exists in gates/
  - every stage skill names a gate that exists, at the same stage, and every
    gate has exactly one stage skill
  - coach skills name no gate and no stage: they gate nothing
  - skills sit at skills/<name>/SKILL.md, the only place chassis discovery
    looks, and when the root has a manifest its contracts.skills lists
    exactly the skills on disk
  - every gate lists its machine-checkable minimums in `evidence:`
  - every auditor skill names a Laya question set in laya/ that exists, and
    any gate it names exists
  - every question set in laya/ is well formed and named after its file
  - every [[wiki-link]] resolves, and core never links into contrib
  - no stage has more core lead cards than budget.yml allows
  - a card's status is a known value, and status: core only appears under core/
  - a card's `eval:` names a results file in evals/results/ with an entry for
    that card, and a core card either has a winning eval or is one of the seed
    cards in evals/seed-cards.txt (promotion into core is eval-gated)
  - every concept note is linked from somewhere, so none sits unused
  - the Basic track under basic/ (when present): five stages 0-4, three cards
    and one gate per stage, ids prefixed basic-, known submit values, choices
    exactly when submit has choice, the required sections, a link to the
    course, no em dash, and no database words in learner text
  - Basic skills (type: basic-skill) say their role, and a review skill ends
    in a founderos-verdict block

The format rules live in templates/authoring/README.md. Stdlib only, so it runs
in CI with no install step. That is also why frontmatter is a restricted subset
(`key: value` and `key: [a, b]`) rather than full YAML.

Usage:
    python3 lint_content.py [--root DIR]
Exit 0 when clean, 1 with every problem printed otherwise.
"""
from __future__ import annotations

import argparse
import json
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
    "auditor-skill": ("name", "description", "plugin", "type", "stage", "question_set"),
    "coach-skill": ("name", "description", "plugin", "type"),
    "basic-skill": ("name", "description", "plugin", "type", "track", "role"),
}
SKILL_KINDS = ("stage-skill", "auditor-skill", "coach-skill", "basic-skill")

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
    "stage-skill": ("Read the founder context first", "Current stage only", "Procedure", "Gate submission",
                    "Ledger writes"),
    "auditor-skill": ("When to run", "Laya pass", "Claude pass", "Without Laya", "Label capture", "Ledger writes"),
    "concept": (),
    "coach-skill": (),
    "basic-skill": (),
}

BASIC_DIR = "basic"
BASIC_STAGES = range(0, 5)
BASIC_CARDS_PER_STAGE = 3
BASIC_CARD_FIELDS = ("id", "type", "track", "stage", "order", "title", "gate", "submit", "sources")
BASIC_GATE_FIELDS = ("id", "type", "track", "stage", "title", "signoff")
BASIC_CARD_SECTIONS = ("What this is", "What you make", "How to submit", "Done when", "Coach checks", "Source")
BASIC_GATE_SECTIONS = ("What this is", "Why you care", "What you get", "Read the original")
BASIC_SUBMIT_VALUES = ("text", "link", "file", "choice")
BASIC_DONE_WHEN = range(2, 6)
BASIC_SKILL_SECTIONS = {
    "coach": ("Read first", "Current stage only", "How to coach", "Never do the work"),
    "review": ("Input", "How to review", "Reply", "Verdict"),
}
BASIC_VERDICT_FENCE = "```founderos-verdict"
COURSE_URL = "https://stackingthebricks.com/30x500/"
EM_DASH = "\u2014"
COACH_ONLY = "Coach checks"
LEARNER_BANNED = re.compile(r"\b(rows?|kinds?|artifacts?|ledgers?|meta)\b", re.IGNORECASE)
SNAKE_CASE = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b")

SIGNOFF_VALUES = ("claude", "claude+sean")
STATUS_VALUES = ("draft", "candidate", "core")
BUDGET_FILE = "budget.yml"
BUDGET_STAGE_KEY = re.compile(r"^stage-(\d)$")
PLUGIN_ID = "behalfbot-founder-os"
MANIFEST = "openclaw.plugin.json"
EVAL_RESULTS_DIR = "evals/results"
SEED_CARDS = "evals/seed-cards.txt"
EVAL_WIN = "win"

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

    fields, err = parse_fields(lines[1:end], first_lineno=2)
    if err:
        return None, text, err
    return fields, "\n".join(lines[end + 1:]), None


def parse_fields(lines: list[str], first_lineno: int = 1) -> tuple[dict[str, object], str | None]:
    """Parse the flat `key: value` / `key: [a, b]` subset. Returns (fields, error)."""
    fields: dict[str, object] = {}
    for n, raw in enumerate(lines, start=first_lineno):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            return {}, f"line {n}: expected 'key: value', got {raw!r}"
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            fields[key] = split_list(value[1:-1])
        else:
            fields[key] = _unquote(value)
    return fields, None


def split_list(inner: str) -> list[str]:
    """Split an inline list on commas outside quotes, so
    ["Amy Hoy and Alex Hillman, 30x500, pp 38-43"] stays one item."""
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
        return str(self.fields.get("name" if self.kind in SKILL_KINDS else "id", ""))


def collect(root: pathlib.Path, problems: list[str]) -> list[Item]:
    items: list[Item] = []
    sources: list[tuple[pathlib.Path, str | None]] = []
    for tier in TIERS:
        sources += [(p, tier) for p in sorted((root / tier).rglob("*.md"))]
    sources += [(p, None) for p in sorted((root / "gates").rglob("*.md"))]
    sources += [(p, None) for p in sorted((root / "skills").glob("*/SKILL.md"))]
    for nested in sorted((root / "skills").glob("*/*/**/SKILL.md")):
        problems.append(
            f"{nested.relative_to(root)}: skills live at skills/<name>/SKILL.md; "
            "chassis discovery does not look deeper"
        )

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


if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))


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
    expected = item.path.parent.name if item.kind in SKILL_KINDS else item.path.stem
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

    if item.kind == "framework-card" and "status" in f:
        status = f["status"]
        if status not in STATUS_VALUES:
            problems.append(f"{rel}: status {status!r} must be one of {', '.join(STATUS_VALUES)}")
        elif status == "core" and item.tier != "core":
            problems.append(
                f"{rel}: status: core but the card lives under {item.tier}/. "
                "Promotion moves the file into core/ (see CONTRIBUTING.md)"
            )
        elif item.tier == "core" and status != "core":
            problems.append(f"{rel}: status {status!r} under core/; a core card is status: core or leaves it out")

    if item.kind in SKILL_KINDS and f.get("plugin") != PLUGIN_ID:
        problems.append(f"{rel}: plugin must be {PLUGIN_ID!r}")

    if item.kind == "coach-skill":
        for field in ("gate", "stage"):
            if field in f:
                problems.append(f"{rel}: a coach skill gates nothing and works at any stage; drop '{field}'")

    if item.kind == "basic-skill":
        check_basic_skill(item, problems)

    if item.kind == "gate":
        from founder_stage.evidence import parse_evidence
        try:
            parse_evidence(f.get("evidence"))
        except ValueError as e:
            problems.append(f"{rel}: evidence: {e}")


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
    gate_stage = {i.ident: as_stage(i.fields.get("stage", "")) for i in items if i.kind == "gate"}
    stage_skills: dict[str, list[str]] = {}
    linked: set[str] = set()

    for item in items:
        gate = item.fields.get("gate")
        if item.kind == "framework-card":
            if item.tier == "core" and not gate:
                problems.append(f"{item.rel}: core cards must name the gate they serve")
            elif gate and gate not in gates:
                problems.append(f"{item.rel}: names gate {gate!r}, which does not exist in gates/")
        if item.kind in SKILL_KINDS and gate and gate not in gates:
            problems.append(f"{item.rel}: names gate {gate!r}, which does not exist in gates/")
        if item.kind == "stage-skill" and gate in gates:
            stage_skills.setdefault(str(gate), []).append(item.ident)
            if gate_stage[gate] != as_stage(item.fields.get("stage", "")):
                problems.append(f"{item.rel}: stage {item.fields.get('stage')} but its gate {gate!r} "
                                f"is at stage {gate_stage[gate]}")

        for m in WIKI_LINK.finditer(item.body):
            target_id = m.group(1).strip()
            target = by_id.get(target_id)
            if target_id != item.ident:
                linked.add(target_id)
            if target is None or target.kind not in ("concept", "framework-card"):
                problems.append(f"{item.rel}: [[{target_id}]] does not resolve to a concept note or card")
            elif item.tier != "contrib" and target.tier == "contrib":
                problems.append(f"{item.rel}: [[{target_id}]] links into contrib/, which core content must not depend on")

    for gate in sorted(gates):
        skills = stage_skills.get(gate, [])
        if len(skills) != 1:
            problems.append(f"gates: {gate!r} needs exactly one stage skill naming it, found "
                            f"{len(skills)}{' (' + ', '.join(sorted(skills)) + ')' if skills else ''}")

    for item in items:
        if item.kind == "concept" and item.ident and item.ident not in linked:
            problems.append(f"{item.rel}: no content links to [[{item.ident}]]; "
                            "a concept note earns its place by being linked")


def check_manifest(root: pathlib.Path, items: list[Item], problems: list[str]) -> None:
    """contracts.skills is how the chassis discovers skills. A skill on disk
    that is not listed never loads; a listed skill that is missing breaks it."""
    path = root / MANIFEST
    if not path.is_file():
        return
    try:
        listed = json.loads(path.read_text(encoding="utf-8"))["contracts"]["skills"]
    except (ValueError, KeyError, TypeError) as e:
        problems.append(f"{MANIFEST}: cannot read contracts.skills ({e})")
        return
    on_disk = {i.ident for i in items if i.kind in SKILL_KINDS}
    for name in sorted(on_disk - set(listed)):
        problems.append(f"{MANIFEST}: skill {name!r} is on disk but not in contracts.skills")
    for name in sorted(set(listed) - on_disk):
        problems.append(f"{MANIFEST}: contracts.skills lists {name!r}, which has no skills/{name}/SKILL.md")


def check_evals(root: pathlib.Path, items: list[Item], problems: list[str]) -> None:
    """Promotion into core is eval-gated (behalfbot-plugins#28).

    `eval: <run-id>` on a card names evals/results/<run-id>.json, which must
    hold subjects["card:<id>"]. A core card needs that entry's verdict to be a
    win, unless it is a seed card: one that was in core before the eval
    harness existed, listed in evals/seed-cards.txt.
    """
    seed_path = root / SEED_CARDS
    seeds: set[str] = set()
    if seed_path.is_file():
        seeds = {ln.strip() for ln in seed_path.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")}
    core_cards = {i.ident for i in items if i.kind == "framework-card" and i.tier == "core"}
    for stale in sorted(seeds - core_cards):
        problems.append(f"{SEED_CARDS}: {stale!r} is not a core card; take it off the seed list")

    for item in items:
        if item.kind != "framework-card":
            continue
        run = item.fields.get("eval")
        if not run:
            if item.tier == "core" and item.ident not in seeds:
                problems.append(f"{item.rel}: a core card needs `eval:` naming a winning eval run "
                                f"(or must be a seed card in {SEED_CARDS})")
            continue
        results = root / EVAL_RESULTS_DIR / f"{run}.json"
        try:
            subjects = json.loads(results.read_text(encoding="utf-8"))["subjects"]
        except OSError:
            problems.append(f"{item.rel}: eval {run!r} has no results file {EVAL_RESULTS_DIR}/{run}.json")
            continue
        except (ValueError, KeyError, TypeError) as e:
            problems.append(f"{EVAL_RESULTS_DIR}/{run}.json: unreadable results ({e})")
            continue
        entry = subjects.get(f"card:{item.ident}") if isinstance(subjects, dict) else None
        if not isinstance(entry, dict):
            problems.append(f"{item.rel}: eval {run!r} has no entry for card:{item.ident}")
        elif item.tier == "core" and item.ident not in seeds and entry.get("verdict") != EVAL_WIN:
            problems.append(f"{item.rel}: eval {run!r} verdict is {entry.get('verdict')!r}; "
                            f"core needs {EVAL_WIN!r} over plain Claude")


def resolve_budget_path(root: pathlib.Path) -> pathlib.Path:
    local = root / BUDGET_FILE
    return local if local.exists() else PLUGIN_DIR / BUDGET_FILE


def load_budget(path: pathlib.Path, problems: list[str]) -> dict[int, int] | None:
    """Return {stage: max core lead cards}, or None after recording why it is unusable.

    A missing or malformed budget fails the lint rather than falling back to a
    default, so the budget check can never pass by not running.
    """
    if not path.is_file():
        problems.append(f"{BUDGET_FILE}: not found at {path}")
        return None
    fields, err = parse_fields(path.read_text(encoding="utf-8").splitlines())
    if err:
        problems.append(f"{BUDGET_FILE}: {err}")
        return None

    def count(key: str, value: object) -> int | None:
        if isinstance(value, str) and value.isdigit():
            return int(value)
        problems.append(f"{BUDGET_FILE}: {key} must be a whole number, got {value!r}")
        return None

    if "default" not in fields:
        problems.append(f"{BUDGET_FILE}: missing required key 'default'")
        return None
    default = count("default", fields["default"])
    if default is None:
        return None
    budget = {stage: default for stage in STAGES}
    for key, value in fields.items():
        if key == "default":
            continue
        m = BUDGET_STAGE_KEY.match(key)
        if not m:
            problems.append(f"{BUDGET_FILE}: unknown key {key!r} (expected 'default' or 'stage-0' .. 'stage-9')")
            return None
        n = count(key, value)
        if n is None:
            return None
        budget[int(m.group(1))] = n
    return budget


def check_budget(items: list[Item], budget: dict[int, int], problems: list[str]) -> None:
    """A lead card is a core framework card. Concept notes do not count."""
    by_stage: dict[int, list[str]] = {}
    for item in items:
        if item.kind != "framework-card" or item.tier != "core":
            continue
        stage = as_stage(item.fields.get("stage", ""))
        if stage is not None:
            by_stage.setdefault(stage, []).append(item.ident)
    for stage, cards in sorted(by_stage.items()):
        if len(cards) > budget[stage]:
            problems.append(
                f"stage {stage}: {len(cards)} core lead cards, budget is {budget[stage]} "
                f"({', '.join(sorted(cards))}). Promoting a card means demoting another"
            )


def check_question_sets(root: pathlib.Path, items: list[Item], problems: list[str]) -> None:
    """Every laya/*.json is a valid question set named after its file, and
    every auditor skill's question_set is one of them."""
    sys.path.insert(0, str(PLUGIN_DIR))
    from founder_audit.questions import validate

    found: set[str] = set()
    for path in sorted((root / "laya").glob("*.json")):
        rel = str(path.relative_to(root))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            problems.append(f"{rel}: not valid JSON ({e})")
            continue
        for p in validate(data):
            problems.append(f"{rel}: {p}")
        if isinstance(data, dict) and data.get("name") != path.stem:
            problems.append(f"{rel}: name {data.get('name')!r} does not match the file name")
        found.add(path.stem)
    for item in items:
        if item.kind == "auditor-skill":
            qs = item.fields.get("question_set")
            if qs and qs not in found:
                problems.append(f"{item.rel}: question_set {qs!r} is not a question set in laya/")


# --- Basic track (basic/) ----------------------------------------------------
#
# A separate, smaller format from core/ and gates/: learner-facing cards whose
# acceptance the coach decides card by card, and gates that are only the stage
# panel. None of it goes through the Advanced checks above.

def section_text(body: str, heading: str) -> str:
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def without_section(body: str, heading: str) -> str:
    return re.sub(rf"^##\s+{re.escape(heading)}\s*$.*?(?=^##\s|\Z)", "", body, flags=re.MULTILINE | re.DOTALL)


def check_learner_text(rel: str, text: str, problems: list[str]) -> None:
    words = sorted({m.group(0).lower() for m in LEARNER_BANNED.finditer(text)})
    if words:
        problems.append(f"{rel}: learner text uses database word(s) {', '.join(words)}; "
                        f"keep them to ## {COACH_ONLY}")
    if "`" in text:
        problems.append(f"{rel}: learner text has backticks; keep them to ## {COACH_ONLY}")
    snake = sorted(set(SNAKE_CASE.findall(text)))
    if snake:
        problems.append(f"{rel}: learner text has snake_case id(s) {', '.join(snake)}")


def check_no_em_dash(item: Item, problems: list[str]) -> None:
    text = item.path.read_text(encoding="utf-8")
    if EM_DASH in text:
        problems.append(f"{item.rel}: has an em dash; use ' - '")
    if "/basic/" in "/" + str(item.rel).replace("\\", "/") and ("\\'" in text or '\\"' in text):
        problems.append(f"{item.rel}: has a backslash-escaped quote; write the plain quote")


def check_basic_skill(item: Item, problems: list[str]) -> None:
    f, rel = item.fields, item.rel
    if f.get("track") != "basic":
        problems.append(f"{rel}: a basic skill needs track: basic")
    role = f.get("role")
    if role not in BASIC_SKILL_SECTIONS:
        problems.append(f"{rel}: role {role!r} must be one of {', '.join(BASIC_SKILL_SECTIONS)}")
    else:
        missing = [s for s in BASIC_SKILL_SECTIONS[role] if s not in headings(item.body)]
        if missing:
            problems.append(f"{rel}: missing section(s) {', '.join('## ' + s for s in missing)}")
        if role == "review" and BASIC_VERDICT_FENCE not in item.body:
            problems.append(f"{rel}: a review skill must show its {BASIC_VERDICT_FENCE} output block")
    for field in ("gate", "stage"):
        if field in f:
            problems.append(f"{rel}: a basic skill works across the Basic stages; drop '{field}'")
    check_no_em_dash(item, problems)


def collect_basic(root: pathlib.Path, problems: list[str]) -> tuple[list[Item], list[Item]]:
    """(cards, gates) under basic/. Cards sit in basic/stage-<N>/, gates in basic/gates/."""
    cards: list[Item] = []
    gates: list[Item] = []
    base = root / BASIC_DIR
    for path in sorted(base.rglob("*.md")):
        if path.name == "README.md":
            continue
        rel = str(path.relative_to(root))
        parent = path.parent.relative_to(base)
        if str(parent) == "gates":
            bucket, kind = gates, "gate"
        elif re.fullmatch(r"stage-\d+", str(parent)):
            bucket, kind = cards, "card"
        else:
            problems.append(f"{rel}: basic content lives in basic/stage-<N>/ or basic/gates/")
            continue
        fields, body, err = parse_frontmatter(path.read_text(encoding="utf-8"))
        if err:
            problems.append(f"{rel}: {err}")
            continue
        if fields is None:
            problems.append(f"{rel}: no frontmatter")
            continue
        if fields.get("type") != kind:
            problems.append(f"{rel}: type must be {kind!r} here, got {fields.get('type')!r}")
            continue
        bucket.append(Item(path, rel, kind, fields, body, None))
    return cards, gates


def as_basic_stage(value: object) -> int | None:
    n = as_stage(value)
    return n if n in BASIC_STAGES else None


def check_basic_common(item: Item, required: tuple[str, ...], sections: tuple[str, ...],
                       problems: list[str]) -> int | None:
    f, rel = item.fields, item.rel
    for field in required:
        if f.get(field) in (None, "", []):
            problems.append(f"{rel}: missing required frontmatter field '{field}'")
    if f.get("track") not in (None, "", "basic"):
        problems.append(f"{rel}: track must be 'basic'")
    ident = str(f.get("id", ""))
    if ident:
        if not ident.startswith("basic-"):
            problems.append(f"{rel}: id {ident!r} must start with 'basic-'")
        elif not ID_SHAPE.match(ident):
            problems.append(f"{rel}: id {ident!r} must be lowercase kebab-case")
        elif ident != "basic-" + item.path.stem:
            problems.append(f"{rel}: id {ident!r} must be 'basic-{item.path.stem}' to match its file name")
    missing = [s for s in sections if s not in headings(item.body)]
    if missing:
        problems.append(f"{rel}: missing section(s) {', '.join('## ' + s for s in missing)}")
    check_no_em_dash(item, problems)
    stage = as_basic_stage(f.get("stage", ""))
    if "stage" in f and stage is None:
        problems.append(f"{rel}: stage {f['stage']!r} is not an integer 0-4")
    return stage


def check_basic_card(item: Item, gate_stage: dict[str, int | None], problems: list[str]) -> None:
    f, rel = item.fields, item.rel
    stage = check_basic_common(item, BASIC_CARD_FIELDS, BASIC_CARD_SECTIONS, problems)
    if stage is not None and item.path.parent.name != f"stage-{stage}":
        problems.append(f"{rel}: stage {stage} but the file lives under basic/{item.path.parent.name}/")

    order = f.get("order")
    if order not in (None, "") and str(order) not in ("1", "2", "3"):
        problems.append(f"{rel}: order {order!r} must be 1, 2 or 3")

    gate = f.get("gate")
    if gate:
        if gate not in gate_stage:
            problems.append(f"{rel}: names gate {gate!r}, which does not exist in basic/gates/")
        elif stage is not None and gate_stage[gate] != stage:
            problems.append(f"{rel}: stage {stage} but its gate {gate!r} is at stage {gate_stage[gate]}")

    submit = f.get("submit")
    if submit not in (None, "", []):
        if not isinstance(submit, list):
            problems.append(f"{rel}: submit must be a list, e.g. submit: [text]")
            submit = []
        bad = [v for v in submit if v not in BASIC_SUBMIT_VALUES]
        if bad:
            problems.append(f"{rel}: submit value(s) {', '.join(map(repr, bad))} not in "
                            f"{', '.join(BASIC_SUBMIT_VALUES)}")
        choices = f.get("choices")
        if "choice" in submit and (not isinstance(choices, list) or not choices):
            problems.append(f"{rel}: submit has choice, so choices must list the options")
        if "choice" not in submit and "choices" in f:
            problems.append(f"{rel}: choices is set but submit has no choice")

    if "sources" in f and not isinstance(f["sources"], list):
        problems.append(f"{rel}: sources must be a list")

    done = [ln for ln in section_text(item.body, "Done when").splitlines() if ln.startswith("- ")]
    if "Done when" in headings(item.body) and len(done) not in BASIC_DONE_WHEN:
        problems.append(f"{rel}: ## Done when has {len(done)} bullet(s); it needs 2 to 5")
    if "Source" in headings(item.body) and not section_text(item.body, "Source").endswith(COURSE_URL):
        problems.append(f"{rel}: ## Source must end with the link to the course, {COURSE_URL}")

    learner = "\n".join([str(f.get("title", "")), " ".join(map(str, f.get("choices") or [])),
                         without_section(item.body, COACH_ONLY)])
    check_learner_text(rel, learner, problems)


def check_basic_gate(item: Item, problems: list[str]) -> None:
    f, rel = item.fields, item.rel
    stage = check_basic_common(item, BASIC_GATE_FIELDS, BASIC_GATE_SECTIONS, problems)
    if stage is not None and not item.path.stem.startswith(f"stage-{stage}-"):
        problems.append(f"{rel}: stage {stage} but the file name does not start with 'stage-{stage}-'")
    if f.get("signoff") not in (None, "", "coach"):
        problems.append(f"{rel}: a basic gate has signoff: coach (the stage passes when every card is accepted)")
    if "Read the original" in headings(item.body) and COURSE_URL not in section_text(item.body, "Read the original"):
        problems.append(f"{rel}: ## Read the original must link to {COURSE_URL}")
    check_learner_text(rel, "\n".join([str(f.get("title", "")), item.body]), problems)


def check_basic(root: pathlib.Path, others: list[Item], problems: list[str]) -> None:
    """Runs only when the root has a basic/ tree."""
    if not (root / BASIC_DIR).is_dir():
        return
    cards, gates = collect_basic(root, problems)

    seen = {i.ident: i.rel for i in others if i.ident}
    for item in gates + cards:
        ident = str(item.fields.get("id", ""))
        if ident in seen:
            problems.append(f"{item.rel}: duplicate id {ident!r} (also {seen[ident]})")
        elif ident:
            seen[ident] = item.rel

    gate_stage = {str(g.fields.get("id")): as_basic_stage(g.fields.get("stage", "")) for g in gates}
    for gate in gates:
        check_basic_gate(gate, problems)
    for card in cards:
        check_basic_card(card, gate_stage, problems)

    for stage in BASIC_STAGES:
        here = [g.ident for g in gates if as_basic_stage(g.fields.get("stage", "")) == stage]
        if len(here) != 1:
            problems.append(f"basic: stage {stage} needs exactly one gate in basic/gates/, found {len(here)}")
        in_stage = [c for c in cards if as_basic_stage(c.fields.get("stage", "")) == stage]
        if len(in_stage) != BASIC_CARDS_PER_STAGE:
            problems.append(f"basic: stage {stage} needs {BASIC_CARDS_PER_STAGE} cards, found {len(in_stage)}")
        orders = [str(c.fields.get("order")) for c in in_stage]
        dupes = sorted({o for o in orders if orders.count(o) > 1})
        if dupes:
            problems.append(f"basic: stage {stage} has more than one card at order {', '.join(dupes)}")


def lint(root: pathlib.Path, budget_path: pathlib.Path | None = None) -> list[str]:
    problems: list[str] = []
    items = collect(root, problems)
    for item in items:
        check_item(item, problems)
    check_references(items, problems)
    check_question_sets(root, items, problems)
    check_manifest(root, items, problems)
    check_evals(root, items, problems)
    check_basic(root, items, problems)
    budget = load_budget(budget_path or resolve_budget_path(root), problems)
    if budget is not None:
        check_budget(items, budget, problems)
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=PLUGIN_DIR, help="content root (default: the plugin dir)")
    ap.add_argument(
        "--budget",
        type=pathlib.Path,
        default=None,
        help=f"card budget file (default: ROOT/{BUDGET_FILE}, else the plugin's {BUDGET_FILE})",
    )
    args = ap.parse_args(argv)

    problems = lint(args.root, args.budget)
    if problems:
        print(f"FAIL: {len(problems)} content problem(s) under {args.root}")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK: content under {args.root} is clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
