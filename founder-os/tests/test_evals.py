#!/usr/bin/env python3
"""test_evals.py - the deterministic half of the FounderOS evals.

CI runs this: fixture validation, the scoring code, and the whole pipeline
with a mocked model. The live eval (scripts/run_evals.py live) calls Claude,
costs money and is run by hand; its committed results are checked for shape
here, not re-run.

Stdlib only, no network. Run:
    python3 founder-os/tests/test_evals.py
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
import unittest

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(PLUGIN_DIR / "scripts"))

import lint_content  # noqa: E402
from founder_eval import runner  # noqa: E402
from founder_eval.sets import SET_NAMES, TASKS, f1, load_set, render, score, validate_set  # noqa: E402
from founder_eval.subjects import BASE_SYSTEM, subjects, system_prompt  # noqa: E402

RESULTS = PLUGIN_DIR / "evals" / "results"


def answer_key() -> dict[str, dict]:
    """user prompt -> the expected answer, for a mocked model that knows it."""
    key = {}
    for name in SET_NAMES:
        for item in load_set(name)["items"]:
            key[runner.user_prompt(name, item)] = item["expected"]
    return key


class FixtureTest(unittest.TestCase):
    def test_every_set_is_valid(self):
        for name in SET_NAMES:
            with self.subTest(set=name):
                self.assertEqual(validate_set(name), [])

    def test_every_set_has_a_task(self):
        self.assertEqual(set(SET_NAMES), {p.stem for p in (PLUGIN_DIR / "evals" / "fixtures").glob("*.json")})

    def test_each_set_has_both_kinds_of_case(self):
        """A set where every item has the same verdict cannot tell a judge from a coin."""
        for name, key in (("interviews", "verdict"), ("profiles", "earlyvangelist"),
                          ("pain-logs", "verdict"), ("audiences", "verdict"), ("ebombs", "premature_pitch")):
            with self.subTest(set=name):
                values = {json.dumps(i["expected"][key]) for i in load_set(name)["items"]}
                self.assertGreaterEqual(len(values), 2, values)

    def test_validation_catches_a_contradiction(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        shutil.copytree(PLUGIN_DIR / "evals" / "fixtures", root, dirs_exist_ok=True)
        data = json.loads((root / "profiles.json").read_text(encoding="utf-8"))
        data["items"][0]["expected"]["earlyvangelist"] = False
        (root / "profiles.json").write_text(json.dumps(data), encoding="utf-8")
        problems = validate_set("profiles", root)
        self.assertTrue(any("earlyvangelist False with 5 criteria met" in p for p in problems), problems)

    def test_rendering_numbers_turns_and_paragraphs(self):
        item = load_set("interviews")["items"][0]
        self.assertTrue(render("interviews", item).startswith("[1] Founder (founder): "))
        item = load_set("ebombs")["items"][0]
        self.assertIn("\n\n[2] ", render("ebombs", item))


class ScoringTest(unittest.TestCase):
    def test_expected_answer_scores_one(self):
        for name in SET_NAMES:
            for item in load_set(name)["items"]:
                with self.subTest(item=item["id"]):
                    self.assertEqual(score(name, item["expected"], item)[0], 1.0)

    def test_unparseable_answer_scores_zero(self):
        item = load_set("interviews")["items"][0]
        self.assertEqual(score("interviews", None, item), (0.0, {}))

    def test_wrong_types_do_not_crash(self):
        for name in SET_NAMES:
            item = load_set(name)["items"][0]
            with self.subTest(set=name):
                s, _ = score(name, {"flagged": 3, "sections": "pain", "fact_turns": None, "falsifiable": 1}, item)
                self.assertGreaterEqual(s, 0.0)

    def test_f1(self):
        self.assertEqual(f1([], []), 1.0)
        self.assertEqual(f1([1], []), 0.0)
        self.assertEqual(f1([1, 2], [2, 3]), 0.5)
        self.assertEqual(f1([12, 2], [2], ignore=[12]), 1.0)

    def test_talk_about_paying_is_not_money(self):
        item = next(i for i in load_set("interviews")["items"] if i["id"] == "int-3")
        wrong = dict(item["expected"], commitment="money")
        self.assertLess(score("interviews", wrong, item)[0], 1.0)

    def test_parse_json(self):
        self.assertEqual(runner.parse_json('Sure:\n```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(runner.parse_json('{"a": {"b": 2}} trailing'), {"a": {"b": 2}})
        self.assertEqual(runner.parse_json("text {not json} then {\"ok\": true}"), {"ok": True})
        self.assertIsNone(runner.parse_json("no json here"))
        self.assertIsNone(runner.parse_json(""))

    def test_decide(self):
        self.assertEqual(runner.decide(0.05), "win")
        self.assertEqual(runner.decide(0.049), "null")
        self.assertEqual(runner.decide(-0.05), "loss")


class SubjectsTest(unittest.TestCase):
    def test_every_subject_loads(self):
        subs = subjects()
        self.assertEqual(len({s.id for s in subs}), len(subs))
        for s in subs:
            with self.subTest(subject=s.id):
                self.assertIn(s.fixture_set, SET_NAMES)
                for rel in s.files:
                    self.assertTrue((PLUGIN_DIR / rel).is_file(), rel)

    def test_sample_covers_stages_0_to_3(self):
        stages = {s.stage for s in subjects() if s.kind == "stage"}
        self.assertTrue({0, 1, 2, 3} <= stages)
        kinds = {s.kind for s in subjects()}
        self.assertEqual(kinds, {"auditor", "card", "stage"})

    def test_every_auditor_skill_is_a_subject(self):
        auditors = {p.parent.name for p in (PLUGIN_DIR / "skills").glob("*/SKILL.md")
                    if "type: auditor-skill" in p.read_text(encoding="utf-8")}
        self.assertEqual({s.id.split(":", 1)[1] for s in subjects() if s.kind == "auditor"}, auditors)

    def test_baseline_is_plain(self):
        item = load_set("profiles")["items"][0]
        self.assertEqual(system_prompt(None, "profiles", item), BASE_SYSTEM)

    def test_auditor_arm_carries_the_claude_only_pass(self):
        sub = next(s for s in subjects() if s.id == "skill:founder-os-mom-test-auditor")
        item = load_set("interviews")["items"][0]
        prompt = system_prompt(sub, "interviews", item)
        self.assertIn('"mode": "claude-only"', prompt)
        self.assertIn("=== skills/founder-os-mom-test-auditor/SKILL.md ===", prompt)

    def test_same_task_text_for_every_arm(self):
        for name in SET_NAMES:
            item = load_set(name)["items"][0]
            self.assertTrue(runner.user_prompt(name, item).startswith(TASKS[name]))


class MockedRunTest(unittest.TestCase):
    """The whole pipeline, with a model that only knows the answers when it has
    FounderOS material loaded. Every subject should win, and the lint should
    accept the result as a card's eval."""

    def setUp(self):
        self.key = answer_key()

    def model_that_prefers_skills(self, system: str, user: str) -> dict:
        exp = self.key[user]
        if system == BASE_SYSTEM:
            return {"text": "I think: {\"verdict\": \"nope\"}", "model": "mock", "cost_usd": 0.0}
        return {"text": "```json\n" + json.dumps(exp) + "\n```", "model": "mock", "cost_usd": 0.001}

    def test_skills_that_help_win(self):
        subs = subjects()
        out = runner.run(subs, self.model_that_prefers_skills, repeats=2, jobs=4)
        res = runner.summarise(out["calls"], subs, run_id="mock", mode="mock", model="mock", repeats=2, laya=None)
        self.assertEqual(set(res["subjects"]), {s.id for s in subs})
        for sid, s in res["subjects"].items():
            with self.subTest(subject=sid):
                self.assertEqual(s["score"], 1.0)
                self.assertEqual(s["verdict"], "win")
                self.assertEqual(len(s["delta_per_repeat"]), 2)
        self.assertIn("| **win** |", runner.markdown(res))

    def test_no_difference_is_a_null_result(self):
        subs = [s for s in subjects() if s.fixture_set == "audiences"]
        same = lambda system, user: {"text": json.dumps(self.key[user]), "model": "mock", "cost_usd": 0.0}  # noqa: E731
        out = runner.run(subs, same, repeats=1, jobs=2)
        res = runner.summarise(out["calls"], subs, run_id="mock", mode="mock", model="mock", repeats=1, laya=None)
        self.assertTrue(all(s["verdict"] == "null" for s in res["subjects"].values()))

    def test_failed_calls_are_scored_not_dropped(self):
        subs = [s for s in subjects() if s.fixture_set == "audiences"]

        def broken(system, user):
            raise RuntimeError("model down")

        out = runner.run(subs, broken, repeats=1, jobs=2)
        self.assertTrue(all(c["score"] == 0.0 and c["error"] for c in out["calls"]))
        res = runner.summarise(out["calls"], subs, run_id="mock", mode="mock", model="mock", repeats=1, laya=None)
        self.assertEqual(res["baselines"]["audiences"]["parse_failures"], 6)

    def test_lint_reads_the_result(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name) / "content"
        shutil.copytree(PLUGIN_DIR / "templates" / "examples", root)
        subs = [s for s in subjects() if s.id == "card:audience-first"]
        out = runner.run(subs, self.model_that_prefers_skills, repeats=1, jobs=2)
        res = runner.summarise(out["calls"], subs, run_id="mock", mode="mock", model="mock", repeats=1, laya=None)
        res["subjects"]["card:map-the-watering-holes"] = res["subjects"].pop("card:audience-first")
        (root / "evals" / "results" / "mock-run.json").write_text(json.dumps(res), encoding="utf-8")
        card = root / "core" / "cards" / "map-the-watering-holes.md"
        card.write_text(card.read_text(encoding="utf-8").replace("eval: example-run", "eval: mock-run"),
                        encoding="utf-8")
        self.assertEqual(lint_content.lint(root), [])
        res["subjects"]["card:map-the-watering-holes"]["verdict"] = "loss"
        (root / "evals" / "results" / "mock-run.json").write_text(json.dumps(res), encoding="utf-8")
        self.assertEqual(len(lint_content.lint(root)), 1)


class PublishedResultsTest(unittest.TestCase):
    """The committed live run: present, complete, and honest about nulls."""

    def live_runs(self) -> list[dict]:
        runs = []
        for path in sorted(RESULTS.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("mode") == "live":
                runs.append(data)
        return runs

    def test_a_live_run_is_published(self):
        self.assertTrue(self.live_runs(), "no live results in evals/results/ (run scripts/run_evals.py live)")

    def test_live_runs_are_complete(self):
        for run in self.live_runs():
            with self.subTest(run=run["run_id"]):
                self.assertTrue((RESULTS / f"{run['run_id']}.md").is_file())
                self.assertTrue((RESULTS / f"{run['run_id']}.calls.jsonl").is_file())
                stages = {s["stage"] for s in run["subjects"].values() if s["kind"] == "stage"}
                self.assertTrue({0, 1, 2, 3} <= stages)
                for sid, s in run["subjects"].items():
                    self.assertEqual(s["verdict"], runner.decide(s["delta"]), sid)
                calls = (RESULTS / f"{run['run_id']}.calls.jsonl").read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(calls), run["calls"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
