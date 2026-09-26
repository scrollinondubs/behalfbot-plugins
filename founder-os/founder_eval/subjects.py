"""What gets evaluated, and what each arm loads before the task.

- baseline: plain Claude. The task text and the item, nothing else.
- card: one core card plus the concept notes it links.
- auditor: the auditor SKILL.md, its Laya question set, and the auditor's own
  deterministic pass on the item (scripts/audit.py's output), as the skill
  would have in a real session. With a Laya URL that pass includes Laya's tags;
  without one it is the Claude-only output.
- stage: the stage SKILL.md, the stage's core cards and their concept notes,
  and, where the stage calls an auditor on this kind of evidence, that auditor
  skill and its output too.

The sample covers every auditor, one card per fixture set and the stage skills
for stages 0 to 3 (#28's done-when: stage 0-3 results published).
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field

from founder_audit import LayaClient, earlyvangelist, mom_test, pain, pain_dream_fix
from founder_stage.content import Content

from .sets import FIXTURES, item_text

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Subject:
    id: str
    kind: str
    fixture_set: str
    stage: int
    files: tuple[str, ...] = ()
    auditor: str | None = None
    laya: bool = False
    extra: tuple[str, ...] = field(default=())


AUDITOR_FILES = {
    "mom-test": ("skills/founder-os-mom-test-auditor/SKILL.md", "laya/mom-test.json"),
    "earlyvangelist": ("skills/founder-os-earlyvangelist-qualifier/SKILL.md", "laya/earlyvangelist.json"),
    "pain-log": ("skills/founder-os-pain-tagger/SKILL.md", "laya/pain-tagger.json"),
    "pain-dream-fix": ("skills/founder-os-pain-dream-fix-checker/SKILL.md", "laya/pain-dream-fix.json"),
}


def _card_files(card_id: str, content: Content) -> tuple[str, ...]:
    for stage in range(10):
        for card in content.cards(stage):
            if card.id == card_id:
                return (card.rel, *[c.rel for c in content.concepts(card.links())])
    raise LookupError(f"no core card {card_id!r}")


def _stage_files(stage: int, content: Content) -> tuple[str, ...]:
    skill = content.stage_skill(stage)
    if skill is None:
        raise LookupError(f"no stage skill for stage {stage}")
    cards = content.cards(stage)
    links = sorted({link for c in cards for link in c.links()} | set(skill.links()))
    return (skill.rel, *[c.rel for c in cards], *[c.rel for c in content.concepts(links)])


def subjects(*, laya: bool = False, content: Content | None = None) -> list[Subject]:
    content = content or Content(PLUGIN_DIR, include_contrib=False)
    out = [
        Subject("skill:founder-os-mom-test-auditor", "auditor", "interviews", 3,
                AUDITOR_FILES["mom-test"], auditor="mom-test"),
        Subject("skill:founder-os-earlyvangelist-qualifier", "auditor", "profiles", 3,
                AUDITOR_FILES["earlyvangelist"], auditor="earlyvangelist"),
        Subject("skill:founder-os-pain-tagger", "auditor", "pain-logs", 2,
                AUDITOR_FILES["pain-log"], auditor="pain-log"),
        Subject("skill:founder-os-pain-dream-fix-checker", "auditor", "ebombs", 6,
                AUDITOR_FILES["pain-dream-fix"], auditor="pain-dream-fix"),
    ]
    if laya:
        out += [Subject(s.id + "+laya", s.kind, s.fixture_set, s.stage, s.files, s.auditor, laya=True)
                for s in list(out)]
    for card_id, fset, stage in (
        ("plan-a-riskiest-assumption", "assumptions", 0),
        ("audience-first", "audiences", 1),
        ("sales-safari-pain-log", "pain-logs", 2),
        ("interviews-without-fooling-yourself", "interviews", 3),
        ("earlyvangelists-and-commitment", "profiles", 3),
        ("pain-dream-fix", "ebombs", 6),
    ):
        out.append(Subject(f"card:{card_id}", "card", fset, stage, _card_files(card_id, content)))
    for stage, fset, auditor in ((0, "assumptions", None), (1, "audiences", None),
                                 (2, "pain-logs", "pain-log"), (3, "interviews", "mom-test")):
        skill = content.stage_skill(stage)
        files = _stage_files(stage, content)
        if auditor:
            files = files + AUDITOR_FILES[auditor]
        out.append(Subject(f"skill:{skill.id}", "stage", fset, stage, files, auditor=auditor))
    return out


def auditor_output(subject: Subject, set_name: str, item: dict, laya_url: str | None,
                   root: pathlib.Path = FIXTURES) -> dict:
    """The auditor's own pass on the item, as scripts/audit.py would print it."""
    client = LayaClient(laya_url if subject.laya and laya_url else "")
    text = item_text(set_name, item, root)
    if subject.auditor == "mom-test":
        return mom_test.audit(text, client=client, founder="Founder", lang="en")
    if subject.auditor == "earlyvangelist":
        return earlyvangelist.audit(text, client=client, lang="en")
    if subject.auditor == "pain-dream-fix":
        return pain_dream_fix.audit(text, client=client, lang="en")
    if subject.auditor == "pain-log":
        pains = [{"id": e["id"], "quote": e["quote"], "source_url": e["source_url"],
                  "watering_hole": e["watering_hole"], "job": e["job"]} for e in item["input"]["entries"]]
        return pain.check_log(pains, client=client, lang="en")
    raise ValueError(f"no auditor {subject.auditor!r}")


BASE_SYSTEM = "You are a helpful assistant."


def system_prompt(subject: Subject | None, set_name: str, item: dict, laya_url: str | None = None,
                  root: pathlib.Path = FIXTURES) -> str:
    """The system prompt for one arm on one item. None is plain Claude."""
    if subject is None:
        return BASE_SYSTEM
    parts = [BASE_SYSTEM, "You are working as the FounderOS coach. The material below is loaded for this task. "
             "Apply its method, and follow the task's own definitions and output format exactly."]
    for rel in subject.files:
        parts.append(f"=== {rel} ===\n{(PLUGIN_DIR / rel).read_text(encoding='utf-8')}")
    if subject.auditor:
        out = auditor_output(subject, set_name, item, laya_url, root)
        parts.append("=== output of the auditor's own pass on this item (scripts/audit.py) ===\n"
                     + json.dumps(out, indent=1, ensure_ascii=False, default=str))
    return "\n\n".join(parts)
