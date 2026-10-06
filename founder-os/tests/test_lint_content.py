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

    def card_copy_text(self) -> str:
        """The example card as a starting point for a new card. Its `eval:`
        entry belongs to map-the-watering-holes, so a copy starts without one."""
        text = (self.root / CARD).read_text(encoding="utf-8")
        return text.replace("eval: example-run\n", "")

    def seed(self, ident: str) -> None:
        path = self.root / "evals" / "seed-cards.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(ident + "\n")

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
        problems = lint_content.lint(self.root)
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("'stage-1-nowhere', which does not exist in gates/", problems[0])
        self.assertIn("'stage-1-audience' needs exactly one stage skill", problems[1])

    def test_contrib_card_may_omit_gate(self) -> None:
        text = self.card_copy_text()
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
        self.edit(SKILL, "stage: 1", "stage: 3")
        self.assertOneProblem("need signoff: claude+sean")

    def test_gate_cannot_route_forward(self) -> None:
        self.edit(GATE, "fail_routes_to: 1", "fail_routes_to: 2")
        self.assertOneProblem("ahead of the gate's own stage")

    def test_unclosed_frontmatter(self) -> None:
        self.write("core/concepts/broken.md", "---\nid: broken\n\nno closing fence\n")
        self.assertOneProblem("never closed")

    # Governance (behalfbot-plugins#29): card budget and card status.

    def add_core_card(self, ident: str, stage: int = 1) -> None:
        text = self.card_copy_text()
        text = text.replace("id: map-the-watering-holes", f"id: {ident}")
        if stage != 1:
            text = text.replace("stage: 1\n", f"stage: {stage}\n", 1)
        self.write(f"core/cards/{ident}.md", text)
        self.seed(ident)

    def add_contrib_card(self, ident: str, status: str | None) -> None:
        text = self.card_copy_text()
        text = text.replace("id: map-the-watering-holes", f"id: {ident}").replace("tier: core", "tier: contrib")
        if status is not None:
            text = text.replace("tier: contrib\n", f"tier: contrib\nstatus: {status}\n")
        self.write(f"contrib/{ident}.md", text)

    def test_real_budget_file_parses(self) -> None:
        problems: list[str] = []
        budget = lint_content.load_budget(PLUGIN_DIR / "budget.yml", problems)
        self.assertEqual(problems, [])
        self.assertEqual(sorted(budget), list(range(10)))

    def test_stage_at_budget_passes(self) -> None:
        self.add_core_card("second-card")
        self.add_core_card("third-card")
        self.assertEqual(lint_content.lint(self.root), [])

    def test_stage_over_budget(self) -> None:
        for ident in ("second-card", "third-card", "fourth-card"):
            self.add_core_card(ident)
        self.assertOneProblem("stage 1: 4 core lead cards, budget is 3")

    def test_budget_is_per_stage(self) -> None:
        for ident in ("second-card", "third-card"):
            self.add_core_card(ident)
        self.add_core_card("stage-two-card", stage=2)
        self.assertEqual(lint_content.lint(self.root), [])

    def test_concept_notes_do_not_count(self) -> None:
        self.write("budget.yml", "default: 1\n")
        self.assertEqual(lint_content.lint(self.root), [])

    def test_contrib_cards_do_not_count(self) -> None:
        self.write("budget.yml", "default: 1\n")
        self.add_contrib_card("community-card", status="candidate")
        self.assertEqual(lint_content.lint(self.root), [])

    def test_budget_default_is_configurable(self) -> None:
        self.write("budget.yml", "# tighter\ndefault: 0\n")
        self.assertOneProblem("stage 1: 1 core lead cards, budget is 0")

    def test_budget_stage_override(self) -> None:
        self.write("budget.yml", "default: 1\nstage-1: 2\n")
        self.add_core_card("second-card")
        self.assertEqual(lint_content.lint(self.root), [])
        self.add_core_card("third-card")
        self.assertOneProblem("stage 1: 3 core lead cards, budget is 2")

    def test_budget_missing_fails(self) -> None:
        problems = lint_content.lint(self.root, budget_path=self.root / "nope.yml")
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("budget.yml: not found", problems[0])

    def test_budget_needs_default(self) -> None:
        self.write("budget.yml", "stage-1: 2\n")
        self.assertOneProblem("missing required key 'default'")

    def test_budget_rejects_non_number(self) -> None:
        self.write("budget.yml", "default: three\n")
        self.assertOneProblem("default must be a whole number")

    def test_budget_rejects_unknown_key(self) -> None:
        self.write("budget.yml", "default: 3\nstage-10: 2\n")
        self.assertOneProblem("unknown key 'stage-10'")

    def test_contrib_card_cannot_claim_core_status(self) -> None:
        self.add_contrib_card("self-promoted", status="core")
        self.assertOneProblem("status: core but the card lives under contrib/")

    def test_contrib_card_statuses_pass(self) -> None:
        self.add_contrib_card("drafted", status="draft")
        self.add_contrib_card("nominated", status="candidate")
        self.add_contrib_card("unset", status=None)
        self.assertEqual(lint_content.lint(self.root), [])

    def test_unknown_status(self) -> None:
        self.add_contrib_card("odd", status="promoted")
        self.assertOneProblem("status 'promoted' must be one of")

    def test_core_card_status_must_be_core(self) -> None:
        self.edit(CARD, "tier: core\n", "tier: core\nstatus: candidate\n")
        self.assertOneProblem("status 'candidate' under core/")

    def test_cli_exit_codes(self) -> None:
        self.assertEqual(lint_content.main(["--root", str(self.root)]), 0)
        self.edit(CARD, "gate: stage-1-audience", "gate: stage-1-nowhere")
        self.assertEqual(lint_content.main(["--root", str(self.root)]), 1)

    def test_cli_budget_flag(self) -> None:
        self.write("tight.yml", "default: 0\n")
        self.assertEqual(lint_content.main(["--root", str(self.root), "--budget", str(self.root / "tight.yml")]), 1)

    # --- auditor skills and Laya question sets -------------------------------

    AUDITOR_SECTIONS = ("When to run", "Laya pass", "Claude pass", "Without Laya", "Label capture", "Ledger writes")

    def add_auditor(self, name: str = "founder-os-audit-x", question_set: str = "x-set",
                    gate: str | None = None, drop: str | None = None) -> None:
        gate_line = f"gate: {gate}\n" if gate else ""
        body = "".join(f"## {s}\n\nText.\n\n" for s in self.AUDITOR_SECTIONS if s != drop)
        self.write(f"skills/{name}/SKILL.md",
                   f"---\nname: {name}\ndescription: An auditor.\nplugin: behalfbot-founder-os\n"
                   f"type: auditor-skill\nstage: 1\nquestion_set: {question_set}\n{gate_line}---\n\n"
                   f"# Auditor\n\n{body}")

    def add_question_set(self, stem: str = "x-set", **overrides: object) -> None:
        import json
        data = {"name": stem, "version": "v1", "task": "x", "checkpoint": {"default": "multilingual"},
                "questions": {"q": {"type": "noul", "instructions": "Is it?"}}}
        data.update(overrides)
        self.write(f"laya/{stem}.json", json.dumps(data))

    def test_auditor_skill_passes(self) -> None:
        self.add_question_set()
        self.add_auditor(gate="stage-1-audience")
        self.assertEqual(lint_content.lint(self.root), [])

    def test_auditor_skill_needs_an_existing_question_set(self) -> None:
        self.add_auditor(question_set="nowhere")
        self.assertOneProblem("question_set 'nowhere' is not a question set in laya/")

    def test_auditor_skill_missing_section(self) -> None:
        self.add_question_set()
        self.add_auditor(drop="Without Laya")
        self.assertOneProblem("## Without Laya")

    def test_auditor_skill_names_missing_gate(self) -> None:
        self.add_question_set()
        self.add_auditor(gate="stage-1-nowhere")
        self.assertOneProblem("names gate 'stage-1-nowhere'")

    def test_question_set_name_must_match_file(self) -> None:
        self.add_question_set("x-set", name="other")
        self.assertOneProblem("does not match the file name")

    def test_malformed_question_set(self) -> None:
        self.add_question_set(checkpoint={"en": "gpt"})
        problems = lint_content.lint(self.root)
        self.assertTrue(problems and all("laya/x-set.json" in p for p in problems), problems)


    # Stage skills, coach skills, discovery and evals (behalfbot-plugins#49, #28).

    COACH = (
        "---\nname: founder-os-coach-example\ndescription: A coach skill.\nplugin: behalfbot-founder-os\n"
        "type: coach-skill\n---\n\n# Coach\n\nWorks at any stage.\n"
    )

    def test_coach_skill_passes(self) -> None:
        self.write("skills/founder-os-coach-example/SKILL.md", self.COACH)
        self.assertEqual(lint_content.lint(self.root), [])

    def test_coach_skill_cannot_name_a_gate(self) -> None:
        self.write("skills/founder-os-coach-example/SKILL.md",
                   self.COACH.replace("type: coach-skill\n", "type: coach-skill\ngate: stage-1-audience\n"))
        self.assertOneProblem("a coach skill gates nothing")

    def test_nested_skill_is_not_discovered(self) -> None:
        self.write("skills/coach/founder-os-coach-example/SKILL.md", self.COACH)
        self.assertOneProblem("chassis discovery does not look deeper")

    def test_manifest_must_list_every_skill(self) -> None:
        self.write("openclaw.plugin.json", '{"contracts": {"skills": ["founder-os-stage-1-audience"]}}')
        self.assertEqual(lint_content.lint(self.root), [])
        self.write("skills/founder-os-coach-example/SKILL.md", self.COACH)
        self.assertOneProblem("'founder-os-coach-example' is on disk but not in contracts.skills")

    def test_manifest_must_not_list_missing_skills(self) -> None:
        self.write("openclaw.plugin.json",
                   '{"contracts": {"skills": ["founder-os-stage-1-audience", "founder-os-ghost"]}}')
        self.assertOneProblem("lists 'founder-os-ghost', which has no skills/")

    def test_gate_needs_evidence_minimums(self) -> None:
        self.edit(GATE, "evidence: [artifacts/audience>=1, artifacts/watering_holes>=1]\n", "")
        self.assertOneProblem("evidence: evidence must be a non-empty inline list")

    def test_gate_evidence_syntax(self) -> None:
        self.edit(GATE, "artifacts/watering_holes>=1", "artifacts/watering_holes>=")
        self.assertOneProblem("is not <table>[/<kind>][:<filter>]>=<n>")
        self.edit(GATE, "artifacts/watering_holes>=", "pains:earlyvangelist>=1")
        self.assertOneProblem("filter 'earlyvangelist' does not apply to pains")

    def test_stage_skill_must_match_its_gate_stage(self) -> None:
        self.edit(SKILL, "stage: 1", "stage: 2")
        self.assertOneProblem("stage 2 but its gate 'stage-1-audience' is at stage 1")

    def test_gate_needs_one_stage_skill(self) -> None:
        text = (self.root / SKILL).read_text(encoding="utf-8").replace(
            "name: founder-os-stage-1-audience", "name: founder-os-stage-1-again")
        self.write("skills/founder-os-stage-1-again/SKILL.md", text)
        self.assertOneProblem("needs exactly one stage skill naming it, found 2")

    def test_stage_skill_needs_gate_submission_section(self) -> None:
        self.edit(SKILL, "## Gate submission", "## Handing over")
        self.assertOneProblem("## Gate submission")

    def test_unlinked_concept_note(self) -> None:
        self.write("core/concepts/lonely.md",
                   "---\nid: lonely\ntype: concept\ntitle: Lonely\ntier: core\n---\n\nOne idea.\n")
        self.assertOneProblem("no content links to [[lonely]]")

    def test_core_card_needs_eval_or_seed(self) -> None:
        self.write("core/cards/unevaluated.md", self.card_copy_text().replace(
            "id: map-the-watering-holes", "id: unevaluated"))
        self.assertOneProblem("a core card needs `eval:` naming a winning eval run")
        self.seed("unevaluated")
        self.assertEqual(lint_content.lint(self.root), [])

    def test_core_card_eval_must_be_a_win(self) -> None:
        path = self.root / "evals" / "results" / "example-run.json"
        path.write_text(path.read_text(encoding="utf-8").replace('"verdict": "win"', '"verdict": "null"'),
                        encoding="utf-8")
        self.assertOneProblem("verdict is 'null'; core needs 'win'")

    def test_eval_must_resolve(self) -> None:
        self.edit(CARD, "eval: example-run", "eval: no-such-run")
        self.assertOneProblem("has no results file evals/results/no-such-run.json")

    def test_contrib_eval_may_be_a_loss(self) -> None:
        path = self.root / "evals" / "results" / "example-run.json"
        text = path.read_text(encoding="utf-8").replace("card:map-the-watering-holes", "card:hopeful")
        path.write_text(text.replace('"verdict": "win"', '"verdict": "loss"'), encoding="utf-8")
        self.edit(CARD, "eval: example-run\n", "")
        self.seed("map-the-watering-holes")
        contrib = self.card_copy_text().replace("id: map-the-watering-holes", "id: hopeful")
        contrib = contrib.replace("tier: core", "tier: contrib\nstatus: candidate\neval: example-run")
        self.write("contrib/hopeful.md", contrib)
        self.assertEqual(lint_content.lint(self.root), [])

    def test_stale_seed_entry(self) -> None:
        self.seed("long-gone")
        self.assertOneProblem("'long-gone' is not a core card; take it off the seed list")


BASIC_CARD = "basic/stage-0/find-where-they-talk.md"
BASIC_CHOICE_CARD = "basic/stage-0/choose-your-audience.md"
BASIC_GATE = "basic/gates/stage-0-people.md"


class BasicTrackLintTest(LintContentTest):
    """The Basic track (basic/). Each case starts from the real basic/ tree
    copied next to the template examples, breaks one thing, and expects
    exactly that one problem."""

    def setUp(self) -> None:
        super().setUp()
        shutil.copytree(PLUGIN_DIR / "basic", self.root / "basic")

    def test_basic_tree_passes(self) -> None:
        self.assertEqual(lint_content.lint(self.root), [])

    def test_basic_absent_is_not_required(self) -> None:
        shutil.rmtree(self.root / "basic")
        self.assertEqual(lint_content.lint(self.root), [])

    def test_quoted_list_item_keeps_its_commas(self) -> None:
        fields, _ = lint_content.parse_fields(['sources: ["Amy Hoy and Alex Hillman, 30x500, pp 38-43", other]'])
        self.assertEqual(fields["sources"], ["Amy Hoy and Alex Hillman, 30x500, pp 38-43", "other"])
        fields, _ = lint_content.parse_fields(["sources: [a, b]", "submit: []"])
        self.assertEqual(fields, {"sources": ["a", "b"], "submit": []})

    def test_card_id_needs_basic_prefix(self) -> None:
        self.edit(BASIC_CARD, "id: basic-find-where-they-talk", "id: find-where-they-talk")
        self.assertOneProblem("must start with 'basic-'")

    def test_card_id_matches_file(self) -> None:
        self.edit(BASIC_CARD, "id: basic-find-where-they-talk", "id: basic-find-them")
        self.assertOneProblem("must be 'basic-find-where-they-talk'")

    def test_card_id_unique_across_plugin(self) -> None:
        text = (self.root / BASIC_CARD).read_text(encoding="utf-8")
        self.write("basic/stage-1/find-where-they-talk.md", text.replace("stage: 0", "stage: 1").replace(
            "order: 2", "order: 4").replace("basic-stage-0-people", "basic-stage-1-sales-safari"))
        problems = lint_content.lint(self.root)
        self.assertTrue(any("duplicate id 'basic-find-where-they-talk'" in p for p in problems), problems)

    def test_missing_required_field(self) -> None:
        self.edit(BASIC_CARD, "order: 2\n", "")
        self.assertOneProblem("missing required frontmatter field 'order'")

    def test_stage_out_of_range(self) -> None:
        self.edit(BASIC_GATE, "stage: 0", "stage: 5")
        problems = lint_content.lint(self.root)
        self.assertIn("basic/gates/stage-0-people.md: stage '5' is not an integer 0-4", problems)

    def test_card_stage_matches_directory(self) -> None:
        self.edit(BASIC_CARD, "stage: 0", "stage: 1")
        problems = lint_content.lint(self.root)
        self.assertIn(f"{BASIC_CARD}: stage 1 but the file lives under basic/stage-0/", problems)

    def test_three_cards_per_stage(self) -> None:
        (self.root / BASIC_CARD).unlink()
        self.assertOneProblem("basic: stage 0 needs 3 cards, found 2")

    def test_order_unique_in_stage(self) -> None:
        self.edit(BASIC_CARD, "order: 2", "order: 1")
        self.assertOneProblem("stage 0 has more than one card at order 1")

    def test_gate_per_stage(self) -> None:
        (self.root / "basic/gates/stage-4-ship-and-launch.md").unlink()
        problems = lint_content.lint(self.root)
        self.assertIn("basic: stage 4 needs exactly one gate in basic/gates/, found 0", problems)

    def test_card_names_missing_gate(self) -> None:
        self.edit(BASIC_CARD, "gate: basic-stage-0-people", "gate: basic-stage-0-nowhere")
        self.assertOneProblem("names gate 'basic-stage-0-nowhere', which does not exist in basic/gates/")

    def test_card_gate_at_other_stage(self) -> None:
        self.edit(BASIC_CARD, "gate: basic-stage-0-people", "gate: basic-stage-1-sales-safari")
        self.assertOneProblem("stage 0 but its gate 'basic-stage-1-sales-safari' is at stage 1")

    def test_gate_signoff_is_coach(self) -> None:
        self.edit(BASIC_GATE, "signoff: coach", "signoff: claude")
        self.assertOneProblem("a basic gate has signoff: coach")

    def test_submit_values(self) -> None:
        self.edit(BASIC_CARD, "submit: [text]", "submit: [text, video]")
        self.assertOneProblem("submit value(s) 'video' not in text, link, file, choice")

    def test_choice_needs_choices(self) -> None:
        self.edit(BASIC_CHOICE_CARD, "choices: [Peers, Newcomers, Clients]\n", "")
        self.assertOneProblem("submit has choice, so choices must list the options")

    def test_choices_need_choice(self) -> None:
        self.edit(BASIC_CARD, "submit: [text]", "submit: [text]\nchoices: [Yes, No]")
        self.assertOneProblem("choices is set but submit has no choice")

    def test_card_missing_section(self) -> None:
        self.edit(BASIC_CARD, "## How to submit", "## Sending it in")
        self.assertOneProblem("missing section(s) ## How to submit")

    def test_gate_missing_section(self) -> None:
        self.edit(BASIC_GATE, "## Why you care", "## Why it matters")
        self.assertOneProblem("missing section(s) ## Why you care")

    def test_done_when_bullet_count(self) -> None:
        self.edit(BASIC_CARD, "- You have not posted anything in any of them yet.\n", "")
        self.edit(BASIC_CARD, "- You list three or more watering holes, each with a working link.\n", "")
        self.assertOneProblem("## Done when has 2 bullet(s); it needs 3 to 5")

    def test_source_links_the_course(self) -> None:
        self.edit(BASIC_CARD, " Want the full version? Take the course: https://stackingthebricks.com/30x500/", "")
        self.assertOneProblem("## Source must end with the link to the course")

    def test_gate_links_the_course(self) -> None:
        self.edit(BASIC_GATE, "\nhttps://stackingthebricks.com/30x500/", "")
        self.assertOneProblem("## Read the original must link to")

    def test_em_dash(self) -> None:
        self.edit(BASIC_CARD, "Find where they talk\n", "Find where they talk \u2014 now\n")
        self.assertOneProblem("has an em dash")

    def test_backslash_escaped_quote(self) -> None:
        self.edit(BASIC_CARD, "Find where they talk\n", "Find where they\\'re talking\n")
        self.assertOneProblem("backslash-escaped quote")

    def test_em_dash_in_coach_checks_still_fails(self) -> None:
        self.edit(BASIC_CARD, "- A mix of formats", "- A mix \u2014 of formats")
        self.assertOneProblem("has an em dash")

    def test_database_word_in_learner_text(self) -> None:
        self.edit(BASIC_CARD, "each with a link, what sort of place", "each with a link, what kind of place")
        self.assertOneProblem("learner text uses database word(s) kind")

    def test_database_word_in_title(self) -> None:
        self.edit(BASIC_CARD, "title: Find where they talk", "title: Log a ledger of where they talk")
        self.assertOneProblem("learner text uses database word(s) ledger")

    def test_database_word_in_gate(self) -> None:
        self.edit(BASIC_GATE, "A named audience you already belong to", "An audience artifact")
        self.assertOneProblem("learner text uses database word(s) artifact")

    def test_database_words_allowed_in_coach_checks(self) -> None:
        self.edit(BASIC_CARD, "- A mix of formats", "- Stored as an `artifacts` row of kind watering_holes. A mix of formats")
        self.assertEqual(lint_content.lint(self.root), [])

    def test_backticks_in_learner_text(self) -> None:
        self.edit(BASIC_CARD, "add the search words you used", "add the `search words` you used")
        self.assertOneProblem("learner text has backticks")

    def test_snake_case_in_learner_text(self) -> None:
        self.edit(BASIC_CARD, "add the search words you used", "add the search_words you used")
        self.assertOneProblem("snake_case id(s) search_words")

    def test_stray_file(self) -> None:
        self.write("basic/notes.md", "---\nid: basic-notes\ntype: card\n---\n")
        self.assertOneProblem("basic content lives in basic/stage-<N>/ or basic/gates/")

    def test_wrong_type_in_gates_dir(self) -> None:
        self.edit(BASIC_GATE, "type: gate", "type: card")
        problems = lint_content.lint(self.root)
        self.assertIn(f"{BASIC_GATE}: type must be 'gate' here, got 'card'", problems)

    # Basic skills.

    BASIC_REVIEW = (
        "---\nname: founder-os-basic-example\ndescription: A review.\nplugin: behalfbot-founder-os\n"
        "type: basic-skill\ntrack: basic\nrole: review\n---\n\n# Review\n\n## Input\n\nx\n\n"
        "## How to review\n\nx\n\n## Reply\n\nx\n\n## Verdict\n\n"
        "```founderos-verdict\n{\"card_id\": \"basic-x\", \"verdict\": \"accepted\", \"failed\": []}\n```\n"
    )

    def test_basic_review_skill_passes(self) -> None:
        self.write("skills/founder-os-basic-example/SKILL.md", self.BASIC_REVIEW)
        self.assertEqual(lint_content.lint(self.root), [])

    def test_review_skill_needs_verdict_block(self) -> None:
        self.write("skills/founder-os-basic-example/SKILL.md",
                   self.BASIC_REVIEW.replace("```founderos-verdict", "```json"))
        self.assertOneProblem("must show its ```founderos-verdict output block")

    def test_basic_skill_role(self) -> None:
        self.write("skills/founder-os-basic-example/SKILL.md",
                   self.BASIC_REVIEW.replace("role: review", "role: judge"))
        self.assertOneProblem("role 'judge' must be one of coach, review")

    def test_basic_skill_sections(self) -> None:
        self.write("skills/founder-os-basic-example/SKILL.md",
                   self.BASIC_REVIEW.replace("## Reply", "## Answer"))
        self.assertOneProblem("missing section(s) ## Reply")

    def test_basic_skill_names_no_stage(self) -> None:
        self.write("skills/founder-os-basic-example/SKILL.md",
                   self.BASIC_REVIEW.replace("role: review\n", "role: review\nstage: 0\n"))
        self.assertOneProblem("a basic skill works across the Basic stages; drop 'stage'")

    def test_basic_skill_em_dash(self) -> None:
        self.write("skills/founder-os-basic-example/SKILL.md",
                   self.BASIC_REVIEW.replace("# Review", "# Review \u2014 one card"))
        self.assertOneProblem("has an em dash")

    def test_real_basic_skills_are_in_manifest(self) -> None:
        import json
        listed = json.loads((PLUGIN_DIR / "openclaw.plugin.json").read_text(encoding="utf-8"))["contracts"]["skills"]
        self.assertIn("founder-os-basic-coach", listed)
        self.assertIn("founder-os-basic-review", listed)


class BasicContentLoaderTest(unittest.TestCase):
    def test_loader_reads_the_basic_tree(self) -> None:
        sys.path.insert(0, str(PLUGIN_DIR))
        from founder_stage.content import Content
        content = Content(PLUGIN_DIR, include_contrib=False)
        for stage in range(5):
            cards = content.basic_cards(stage)
            self.assertEqual([c.fields["order"] for c in cards], ["1", "2", "3"])
            self.assertTrue(all(c.fields["gate"] == content.basic_gate(stage).id for c in cards))
        first = content.basic_cards(0)[0]
        self.assertEqual(first.fields["sources"], ["Amy Hoy and Alex Hillman, 30x500, pp 5-9, 30, 38-43"])
        self.assertEqual(content.basic_gate(0).id, "basic-stage-0-people")
        with self.assertRaises(LookupError):
            content.basic_gate(5)

    def test_basic_cards_stay_out_of_the_advanced_stages(self) -> None:
        sys.path.insert(0, str(PLUGIN_DIR))
        from founder_stage.content import Content
        content = Content(PLUGIN_DIR, include_contrib=False)
        for stage in range(10):
            self.assertFalse(any(c.id.startswith("basic-") for c in content.cards(stage)))
            self.assertFalse(content.gate(stage).id.startswith("basic-"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
