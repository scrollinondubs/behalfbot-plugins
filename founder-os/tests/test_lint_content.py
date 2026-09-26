#!/usr/bin/env python3
"""test_lint_content.py - offline suite for founder-os/scripts/lint_content.py.

Stdlib only, per this repo's plugin-tests contract. Each case copies the filled
examples in templates/examples/ into a temp content root, breaks one thing, and
checks the lint fails for that reason and no other. The untouched copy has to
pass, which proves the examples match the templates.

Run:
    python3 founder-os/tests/test_lint_content.py
"""
from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile
import unittest

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = PLUGIN_DIR / "templates" / "examples"
sys.path.insert(0, str(PLUGIN_DIR / "scripts"))

import lint_content  # noqa: E402

CARD = "core/cards/map-the-watering-holes.md"
CONCEPT = "core/concepts/watering-hole.md"
GATE = "gates/stage-1-audience.md"
SKILL = "skills/founder-os-stage-1-audience/SKILL.md"


class LintContentTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "content"
        shutil.copytree(EXAMPLES, self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def edit(self, rel: str, old: str, new: str) -> None:
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"fixture drift: {old!r} not in {rel}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def assertOneProblem(self, needle: str) -> None:
        problems = lint_content.lint(self.root)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(needle, problems[0])

    def test_examples_pass(self) -> None:
        self.assertEqual(lint_content.lint(self.root), [])

    def test_real_plugin_tree_passes(self) -> None:
        self.assertEqual(lint_content.lint(PLUGIN_DIR), [])

    def test_missing_frontmatter(self) -> None:
        self.write("core/concepts/bare.md", "# No frontmatter here\n")
        self.assertOneProblem("no frontmatter")

    def test_missing_required_field(self) -> None:
        self.edit(CONCEPT, "tier: core\n", "")
        self.assertOneProblem("missing required frontmatter field 'tier'")

    def test_missing_section(self) -> None:
        self.edit(CARD, "## Anti-patterns", "## Pitfalls")
        self.assertOneProblem("## Anti-patterns")

    def test_core_card_without_gate(self) -> None:
        self.edit(CARD, "gate: stage-1-audience\n", "")
        self.assertOneProblem("core cards must name the gate")

    def test_core_card_names_missing_gate(self) -> None:
        self.edit(CARD, "gate: stage-1-audience", "gate: stage-1-nowhere")
        self.assertOneProblem("'stage-1-nowhere', which does not exist in gates/")

    def test_skill_names_missing_gate(self) -> None:
        self.edit(SKILL, "gate: stage-1-audience", "gate: stage-1-nowhere")
        self.assertOneProblem("'stage-1-nowhere', which does not exist in gates/")

    def test_contrib_card_may_omit_gate(self) -> None:
        text = (self.root / CARD).read_text(encoding="utf-8")
        text = text.replace("id: map-the-watering-holes", "id: contrib-card")
        text = text.replace("gate: stage-1-audience\n", "").replace("tier: core", "tier: contrib")
        self.write("contrib/contrib-card.md", text)
        self.assertEqual(lint_content.lint(self.root), [])

    def test_dangling_wiki_link(self) -> None:
        self.edit(CONCEPT, "[[audience-before-product]]", "[[no-such-note]]")
        self.assertOneProblem("[[no-such-note]] does not resolve")

    def test_core_must_not_link_into_contrib(self) -> None:
        self.write(
            "contrib/extra-idea.md",
            "---\nid: extra-idea\ntype: concept\ntitle: Extra\ntier: contrib\n---\n\nOne idea.\n",
        )
        self.edit(CONCEPT, "[[audience-before-product]]", "[[extra-idea]]")
        self.assertOneProblem("links into contrib/")

    def test_id_must_match_filename(self) -> None:
        self.edit(CONCEPT, "id: watering-hole", "id: watering-holes")
        problems = lint_content.lint(self.root)
        self.assertTrue(any("does not match its file" in p for p in problems), problems)

    def test_tier_must_match_directory(self) -> None:
        self.edit(CONCEPT, "tier: core", "tier: contrib")
        self.assertOneProblem("tier 'contrib' but the file lives under core/")

    def test_late_gate_needs_sean_signoff(self) -> None:
        self.edit(GATE, "stage: 1", "stage: 3")
        self.assertOneProblem("need signoff: claude+sean")

    def test_gate_cannot_route_forward(self) -> None:
        self.edit(GATE, "fail_routes_to: 1", "fail_routes_to: 2")
        self.assertOneProblem("ahead of the gate's own stage")

    def test_unclosed_frontmatter(self) -> None:
        self.write("core/concepts/broken.md", "---\nid: broken\n\nno closing fence\n")
        self.assertOneProblem("never closed")

    def test_cli_exit_codes(self) -> None:
        self.assertEqual(lint_content.main(["--root", str(self.root)]), 0)
        self.edit(CARD, "gate: stage-1-audience", "gate: stage-1-nowhere")
        self.assertEqual(lint_content.main(["--root", str(self.root)]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
