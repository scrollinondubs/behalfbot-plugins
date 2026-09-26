#!/usr/bin/env python3
"""test_auditors.py - offline suite for the auditors, the Laya client and label capture.

Stdlib only, no network beyond 127.0.0.1. Laya is mocked by tests/fake_laya.py,
a real HTTP server with keyword rules, so the client's sockets, timeouts and
status handling are exercised for real. Fixtures in tests/fixtures/ are
synthetic, written for these tests.

Run:
    python3 founder-os/tests/test_auditors.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

TESTS = pathlib.Path(__file__).resolve().parent
PLUGIN_DIR = TESTS.parent
FIXTURES = TESTS / "fixtures"
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(TESTS))

from fake_laya import FakeLaya  # noqa: E402

from founder_audit import LayaClient, LayaRequestError, LayaUnavailable  # noqa: E402
from founder_audit import earlyvangelist, labels, mom_test, pain, pain_dream_fix, questions, tagger  # noqa: E402
from founder_audit.common import Recorder  # noqa: E402
from founder_ledger import LedgerError, SqliteLedger  # noqa: E402

EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
SETS = ("mom-test", "pain-tagger", "earlyvangelist", "pain-dream-fix")

# The #603 v1 wording. v2 must keep it so v1 and v2 labels train the same question.
V1_IS_PAIN = ("Does the author describe a problem, frustration or struggle that they personally have "
              "(not a general opinion, a product announcement, or advice to others)?")
V1_MONEY = ("Does the author mention paying for something, switching or cancelling a tool, or a "
            "workaround or hack they built themselves?")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class ClientTest(unittest.TestCase):
    def test_request_shape_and_bearer(self):
        with FakeLaya() as fake:
            client = LayaClient(fake.url, api_key="k1", timeout=5)
            out = client.systemone("I am stuck", {"is_pain": {"type": "noul", "instructions": "x?"}},
                                   model="english")
        self.assertEqual(out["answers"]["is_pain"]["noul"], 0.9)
        self.assertEqual(fake.requests[0]["model"], "english")
        self.assertEqual(fake.requests[0]["_auth"], "Bearer k1")

    def test_no_bearer_unless_configured(self):
        with FakeLaya() as fake, mock.patch.dict(os.environ, {"LAYA_API_KEY": ""}):
            LayaClient(fake.url, timeout=5).systemone("x", {"q": {"type": "noul", "instructions": "x?"}})
        self.assertIsNone(fake.requests[0]["_auth"])

    def test_timeout_degrades_and_trips_once(self):
        with FakeLaya("slow") as fake:
            client = LayaClient(fake.url, timeout=0.3)
            q = {"q": {"type": "noul", "instructions": "x?"}}
            t0 = time.monotonic()
            with self.assertRaises(LayaUnavailable):
                client.systemone("x", q)
            self.assertLess(time.monotonic() - t0, 1.5)
            with self.assertRaises(LayaUnavailable):
                client.systemone("y", q)
            self.assertEqual(len(fake.requests), 1, "a down client must not keep calling")

    def test_server_error_and_garbage_are_unavailable(self):
        for mode in ("error", "garbage"):
            with self.subTest(mode=mode), FakeLaya(mode) as fake:
                with self.assertRaises(LayaUnavailable):
                    LayaClient(fake.url, timeout=5).systemone("x", {"q": {"type": "noul", "instructions": "x?"}})

    def test_rejection_is_a_bug_not_an_outage(self):
        with FakeLaya("reject") as fake:
            with self.assertRaises(LayaRequestError):
                LayaClient(fake.url, timeout=5).systemone("x", {"q": {"type": "noul", "instructions": "x?"}})

    def test_unreachable_and_unconfigured(self):
        with self.assertRaises(LayaUnavailable):
            LayaClient("http://127.0.0.1:9", timeout=2).systemone("x", {})
        with mock.patch.dict(os.environ, {"LAYA_URL": ""}):
            client = LayaClient()
        self.assertFalse(client.configured)
        with self.assertRaises(LayaUnavailable):
            client.health()


class QuestionSetTest(unittest.TestCase):
    def test_every_set_loads_and_is_valid(self):
        for name in SETS:
            with self.subTest(name=name):
                self.assertEqual(questions.load(name).name, name)

    def test_pain_tagger_keeps_v1_wording(self):
        qs = questions.load("pain-tagger")
        self.assertEqual(qs.questions["is_pain"]["instructions"], V1_IS_PAIN)
        self.assertEqual(qs.questions["money_or_workaround"]["instructions"], V1_MONEY)

    def test_checkpoint_per_language_per_question(self):
        qs = questions.load("pain-tagger")
        self.assertEqual(qs.checkpoint_for("is_pain", "en"), "english")
        self.assertEqual(qs.checkpoint_for("is_pain", "pt"), "multilingual")
        self.assertEqual(qs.checkpoint_for("is_pain", None), "multilingual")
        self.assertEqual(qs.checkpoint_for("money_or_workaround", "en"), "multilingual")
        self.assertEqual(qs.trust_for("is_pain", "multilingual"), "chance")
        self.assertEqual(qs.trust_for("is_pain", "english"), "measured")

    def test_wire_strips_plugin_fields_and_fills_runtime(self):
        qs = questions.load("pain-tagger")
        self.assertEqual(set(qs.wire_question("is_pain")), {"type", "instructions"})
        self.assertIsNone(qs.wire_question("pain_category"))
        wire = qs.wire_question("pain_category", {"jobs": ["get paid", "find clients"]})
        self.assertEqual(wire["criteria"], ["get paid", "find clients"])

    def test_validate_catches_bad_sets(self):
        bad = {"name": "x", "version": "v1", "task": "x", "checkpoint": {"en": "english"},
               "questions": {"a": {"type": "noul", "instructions": "a?", "trust": "great",
                                   "criteria": {"yes": "y"}},
                             "b": {"type": "choice", "instructions": "b?"},
                             "c": {"type": "score", "instructions": "c?", "criteria": []}}}
        problems = questions.validate(bad)
        joined = " | ".join(problems)
        for needle in ("'default' checkpoint", "trust must be", "true/false", "choice question needs",
                       "score question needs"):
            self.assertIn(needle, joined)

    def test_guess_lang_only_trusts_script(self):
        self.assertIsNone(questions.guess_lang("Estou farto de esperar pelo pagamento"))
        self.assertEqual(questions.guess_lang("Я устал ждать оплату"), "non-latin")


class ChunkingTest(unittest.TestCase):
    def test_chunks_fit_and_keep_every_word_in_order(self):
        text = fixture("posts.json")
        for size in (50, 300, 1000):
            chunks = tagger.chunk_text(text, size)
            self.assertTrue(all(len(c) <= size for c in chunks))
            self.assertEqual(" ".join(" ".join(chunks).split()), " ".join(text.split()))

    def test_short_text_is_one_chunk(self):
        self.assertEqual(tagger.chunk_text("  hello  ", 100), ["hello"])

    def test_long_post_pain_at_the_end_is_found_not_truncated(self):
        posts = [p for p in json.loads(fixture("posts.json")) if p["id"] == "p4"]
        with FakeLaya() as fake:
            out = pain.rank_posts(posts, client=LayaClient(fake.url, timeout=5), lang="en")
            self.assertTrue(all(len(r["state"]) <= tagger.CHUNK_CHARS[r["model"]] for r in fake.requests))
        tags = out["posts"][0]["tags"]
        self.assertTrue(tags["is_pain"]["value"])
        self.assertGreater(tags["is_pain"]["chunks"], 1)
        self.assertIn("breaking me", tags["is_pain"]["excerpt"])
        self.assertTrue(tags["money_or_workaround"]["value"])

        # The control: send the whole post as one state, as a truncating caller
        # would, and the pain at the end is never seen.
        with FakeLaya() as fake, mock.patch.dict(tagger.CHUNK_CHARS, {"english": 10**6, "multilingual": 10**6}):
            out = pain.rank_posts(posts, client=LayaClient(fake.url, timeout=5), lang="en")
        self.assertFalse(out["posts"][0]["tags"]["is_pain"]["value"])


class MomTestTest(unittest.TestCase):
    def test_split_turns(self):
        turns = mom_test.split_turns(
            "[00:00:05] Me: When did that last happen?\n"
            "Sam: Last week.\nSo basically: the client never paid.\n"
            "Me: What did you do?\nSam: I phoned them.\n  Twice, actually.\n")
        self.assertEqual([(t.n, t.speaker, t.role) for t in turns],
                         [(1, "Me", "founder"), (2, "Sam", "interviewee"),
                          (3, "Me", "founder"), (4, "Sam", "interviewee")])
        self.assertIn("So basically: the client never paid.", turns[1].text)
        self.assertEqual(turns[3].text, "I phoned them. Twice, actually.")

    def test_founder_named_explicitly_or_first_speaker(self):
        t = "Ana: hi there\nBo: hello\nAna: how was it\nBo: fine\n"
        self.assertEqual(mom_test.split_turns(t)[0].role, "founder")
        self.assertEqual(mom_test.split_turns(t, founder="bo")[0].role, "interviewee")
        with self.assertRaises(ValueError):
            mom_test.split_turns(t, founder="Cy")
        with self.assertRaises(ValueError):
            mom_test.split_turns("Ana: just me talking\nAna: still me\n")

    def test_fixtures_match_expected(self):
        with FakeLaya() as fake:
            client = LayaClient(fake.url, timeout=5)
            for name, exp in EXPECTED["mom-test"].items():
                with self.subTest(name=name):
                    out = mom_test.audit(fixture(name), client=client, founder=exp["founder"], lang="en")
                    self.assertEqual(out["mode"], "laya")
                    by_n = {t["n"]: t for t in out["turns"]}
                    for n, tags in exp["turns"].items():
                        for qid, value in tags.items():
                            self.assertEqual(by_n[int(n)]["tags"][qid]["value"], value, f"turn {n} {qid}")
                    for key, value in exp["summary"].items():
                        self.assertEqual(out["summary"][key], value, key)
            founder_qs = {q for r in fake.requests for q in r["questions"]}
            self.assertIn("pitching", founder_qs)

    def test_founder_and_interviewee_get_different_questions(self):
        with FakeLaya() as fake:
            out = mom_test.audit(fixture("interview-pitchy.txt"), client=LayaClient(fake.url, timeout=5), lang="en")
        founder_turn = out["turns"][0]
        interviewee_turn = out["turns"][1]
        self.assertEqual(set(founder_turn["tags"]), {"hypothetical", "pitching"})
        self.assertNotIn("pitching", interviewee_turn["tags"])
        self.assertIn("commitment_money", interviewee_turn["tags"])

    def test_patterns(self):
        with FakeLaya() as fake:
            out = mom_test.audit(fixture("interview-pitchy.txt"), client=LayaClient(fake.url, timeout=5), lang="en")
        s = out["summary"]
        self.assertEqual(s["bare_yes_no"], [4, 8])
        self.assertIn(3, s["closed_questions"])
        self.assertIn(7, s["closed_questions"])
        self.assertGreater(s["founder_talk_share"], 0.4)

    def test_hypothetical_commitment_is_talk_not_commitment(self):
        transcript = ("Me: What happened last time?\nKim: Honestly I'd pay for the pilot if it worked.\n"
                      "Me: Anything else?\nKim: Fine, send the contract and I will pay the deposit today.\n")
        with FakeLaya() as fake:
            out = mom_test.audit(transcript, client=LayaClient(fake.url, timeout=5), lang="en")
        s = out["summary"]
        self.assertEqual(s["commitment_talk_only"]["money"], [2])
        self.assertEqual(s["commitment_candidates"]["money"], [4])
        self.assertEqual(s["suggested_commitment"], "money")
        with FakeLaya() as fake:
            out = mom_test.audit(transcript.rsplit("Kim: Fine", 1)[0], client=LayaClient(fake.url, timeout=5), lang="en")
        self.assertEqual(out["summary"]["suggested_commitment"], "none")

    def test_degrades_to_claude_only(self):
        with FakeLaya("error") as fake:
            out = mom_test.audit(fixture("interview-solid.txt"), client=LayaClient(fake.url, timeout=5))
        self.assertEqual(out["mode"], "claude-only")
        self.assertIn("500", out["degraded_reason"])
        self.assertTrue(all(t["tags"] is None for t in out["turns"]))
        self.assertEqual(len(out["turns"]), 10)
        self.assertIn("bare_yes_no", out["summary"])
        with mock.patch.dict(os.environ, {"LAYA_URL": ""}):
            out = mom_test.audit(fixture("interview-solid.txt"), client=LayaClient())
        self.assertEqual((out["mode"], out["degraded_reason"]), ("claude-only", "LAYA_URL is not set"))


class EarlyvangelistTest(unittest.TestCase):
    def test_fixtures(self):
        with FakeLaya() as fake:
            client = LayaClient(fake.url, timeout=5)
            strong = earlyvangelist.audit(fixture("earlyvangelist-strong.txt"), client=client,
                                          transcript=True, lang="en")
            weak = earlyvangelist.audit(fixture("earlyvangelist-weak.txt"), client=client,
                                        transcript=True, lang="en")
            sent = [r["state"] for r in fake.requests]
        self.assertTrue(strong["escalate"])
        self.assertGreaterEqual(len(strong["met"]), EXPECTED["earlyvangelist"]["earlyvangelist-strong.txt"]["met_at_least"])
        self.assertFalse(weak["escalate"])
        self.assertTrue(all("Tell me about the last time" not in s for s in sent),
                        "only the interviewee's words go to Laya")

    def test_degraded_lists_criteria_for_claude(self):
        with mock.patch.dict(os.environ, {"LAYA_URL": ""}):
            out = earlyvangelist.audit("notes", client=LayaClient())
        self.assertIsNone(out["escalate"])
        self.assertEqual(len(out["criteria_to_check"]), 5)


class PainDreamFixTest(unittest.TestCase):
    def test_paragraphs_and_headings(self):
        paras = pain_dream_fix.split_paragraphs(fixture("ebomb-premature.md"))
        self.assertEqual(len(paras), 4)
        self.assertTrue(paras[0].startswith("Meet InvoiceBot\n"))

    def test_fixtures(self):
        with FakeLaya() as fake:
            client = LayaClient(fake.url, timeout=5)
            for name, exp in EXPECTED["pain-dream-fix"].items():
                with self.subTest(name=name):
                    out = pain_dream_fix.audit(fixture(name), client=client, lang="en")
                    s = out["summary"]
                    self.assertEqual(s["premature_pitch"], exp["premature_pitch"])
                    if "sequence" in exp:
                        self.assertEqual(s["sequence"], exp["sequence"])
                    for f in exp.get("findings_include", []):
                        self.assertIn(f, s["findings"])

    def test_no_pain_means_every_pitch_is_premature(self):
        rows = [{"n": 1, "section": "dream", "pitches_product": False},
                {"n": 2, "section": "fix", "pitches_product": True}]
        s = pain_dream_fix.check_order(rows)
        self.assertEqual(s["premature_pitch"], [2])
        self.assertIn("no_pain", s["findings"])


class PainTest(unittest.TestCase):
    def test_rank_english_by_is_pain(self):
        posts = json.loads(fixture("posts.json"))
        with FakeLaya() as fake:
            out = pain.rank_posts(posts, client=LayaClient(fake.url, timeout=5), lang="en")
            models = {(q, r["model"]) for r in fake.requests for q in r["questions"]}
        self.assertIn(("is_pain", "english"), models)
        self.assertIn(("money_or_workaround", "multilingual"), models)
        self.assertNotIn("pain_category", {q for q, _ in models}, "no jobs, no category question")
        exp = EXPECTED["pain-tagger"]["posts.json"]
        by_id = {p["id"]: p for p in out["posts"]}
        for pid, value in exp["is_pain"].items():
            self.assertEqual(by_id[pid]["tags"]["is_pain"]["value"], value, pid)
        for pid, value in exp["money_or_workaround"].items():
            self.assertEqual(by_id[pid]["tags"]["money_or_workaround"]["value"], value, pid)
        self.assertTrue(out["ranked_by"].startswith("is_pain"))
        self.assertNotIn(out["posts"][0]["id"], ("p2", "p3"))

    def test_non_english_does_not_rank_on_chance_level_is_pain(self):
        posts = json.loads(fixture("posts.json"))
        with FakeLaya() as fake:
            out = pain.rank_posts(posts, client=LayaClient(fake.url, timeout=5), lang="pt")
        self.assertTrue(out["ranked_by"].startswith("money_or_workaround only"))
        self.assertEqual(out["posts"][0]["tags"]["is_pain"]["trust"], "chance")

    def test_jobs_add_the_category_question(self):
        with FakeLaya() as fake:
            out = pain.rank_posts([{"id": "a", "text": "stuck again"}], client=LayaClient(fake.url, timeout=5),
                                  lang="en", jobs=["get paid on time", "find clients"])
        self.assertEqual(out["posts"][0]["tags"]["pain_category"]["value"], "get paid on time")

    def test_pain_log_quality(self):
        ledger = SqliteLedger(":memory:")
        ledger.run_migrations()
        f = ledger.create_founder("Test founder")["founder_id"]
        ledger.add_pain(f, quote="I am stuck chasing the same client every week, it is exhausting.",
                        source_url="https://example.com/1", watering_hole="r/freelance", job="get paid")
        ledger.add_pain(f, quote="I am stuck chasing the same client every week, it is exhausting.",
                        source_url="https://example.com/2", watering_hole="r/freelance", job="get paid")
        ledger.add_pain(f, quote="Here is my new invoicing app, feedback welcome!", job="get paid")
        ledger.add_pain(f, quote="too short")
        pains = ledger.list_pains(f)
        with FakeLaya() as fake:
            out = pain.check_log(pains, client=LayaClient(fake.url, timeout=5), lang="en",
                                 recorder=Recorder(ledger, f, "pains", ""))
        issues = {p["quote"][:12]: p["issues"] for p in out["pains"]}
        self.assertTrue(any(i.startswith("duplicate_of:") for i in out["pains"][1]["issues"]))
        self.assertIn("not_a_pain", issues["Here is my n"])
        self.assertIn("no_source_url", issues["Here is my n"])
        self.assertIn("too_short", issues["too short"])
        self.assertIn("no_job", issues["too short"])
        self.assertEqual(out["log"]["thin_jobs"], [])
        self.assertTrue(out["log"]["too_few_watering_holes"])
        self.assertEqual(out["log"]["unclustered"], 1)
        # Each quote's labels hang on its own pains row; the runtime category is not recorded.
        rows = ledger.list_labels(f)
        self.assertEqual({r["target_id"] for r in rows}, {p["id"] for p in pains})
        self.assertNotIn("pain_tag.pain_category", {r["task"] for r in rows})
        self.assertEqual(len(rows), 4 * 3)
        ledger.close()

    def test_pain_log_structural_checks_survive_an_outage(self):
        rows = [{"id": "1", "quote": "short", "job": None, "source_url": None, "watering_hole": None}]
        with mock.patch.dict(os.environ, {"LAYA_URL": ""}):
            out = pain.check_log(rows, client=LayaClient())
        self.assertEqual(out["mode"], "claude-only")
        self.assertIn("too_short", out["pains"][0]["issues"])


class LabelCaptureTest(unittest.TestCase):
    def setUp(self):
        self.ledger = SqliteLedger(":memory:")
        self.ledger.run_migrations()
        self.f = self.ledger.create_founder("Founder A")["founder_id"]
        self.g = self.ledger.create_founder("Founder B")["founder_id"]
        self.iv = self.ledger.add_interview(self.f, interviewee="studio-owner-1",
                                            notes=fixture("interview-solid.txt"))["id"]

    def tearDown(self):
        self.ledger.close()

    def audit(self):
        with FakeLaya() as fake:
            return mom_test.audit(fixture("interview-solid.txt"), client=LayaClient(fake.url, timeout=5),
                                  lang="en", recorder=Recorder(self.ledger, self.f, "interviews", self.iv))

    def test_one_label_per_turn_and_question(self):
        out = self.audit()
        rows = self.ledger.list_labels(self.f)
        expected = sum(len(t["tags"]) for t in out["turns"])
        self.assertEqual(len(rows), expected)
        turn2 = out["turns"][1]
        row = next(r for r in rows if r["id"] == turn2["label_ids"]["past_behaviour"])
        self.assertEqual(row["task"], "mom_test.past_behaviour")
        self.assertEqual(row["input_text"], turn2["text"])
        self.assertIs(row["model_label"], True)
        self.assertEqual(row["model_version"], "laya:english:mom-test@v1")
        self.assertIsNone(row["corrected_at"])

    def test_accept_and_reject_reach_the_export_unreviewed_does_not(self):
        out = self.audit()
        ids = out["turns"][1]["label_ids"]
        labels.accept(self.ledger, self.f, ids["past_behaviour"], by="founder")
        labels.reject(self.ledger, self.f, ids["compliment"], by="sean")
        rows, warnings = labels.export_rows(self.ledger)
        self.assertEqual(warnings, [])
        self.assertEqual(len(rows), 2, "only reviewed labels are training examples")
        by_task = {r["task"]: r for r in rows}
        acc, rej = by_task["mom_test.past_behaviour"], by_task["mom_test.compliment"]
        self.assertTrue(acc["agreed"])
        self.assertEqual(acc["corrected_label"], True)
        self.assertFalse(rej["agreed"])
        self.assertEqual((rej["model_label"], rej["corrected_label"]), (False, True))
        self.assertEqual(acc["question"]["instructions"],
                         questions.load("mom-test").questions["past_behaviour"]["instructions"])
        self.assertEqual(acc["checkpoint"], "english")
        self.assertNotIn("founder_id", acc)
        self.assertNotIn(self.f, json.dumps(rows))

    def test_reject_needs_a_value_unless_yes_no(self):
        with FakeLaya() as fake:
            out = pain_dream_fix.audit(fixture("ebomb-ordered.md"), client=LayaClient(fake.url, timeout=5),
                                       lang="en", recorder=Recorder(self.ledger, self.f, "artifacts",
                                       self.ledger.add_artifact(self.f, stage=6, kind="ebomb",
                                                                body=fixture("ebomb-ordered.md"))["id"]))
        section_id = out["paragraphs"][2]["label_ids"]["section"]
        with self.assertRaises(LedgerError):
            labels.reject(self.ledger, self.f, section_id, by="founder")
        with self.assertRaises(LedgerError):
            labels.reject(self.ledger, self.f, section_id, by="founder", value="dream")
        row = labels.reject(self.ledger, self.f, section_id, by="founder", value="pain")
        self.assertEqual(row["corrected_label"], "pain")

    def test_cannot_review_another_founders_label(self):
        out = self.audit()
        with self.assertRaises(LedgerError):
            labels.accept(self.ledger, self.g, out["turns"][1]["label_ids"]["past_behaviour"], by="x")

    def test_degraded_run_writes_no_labels(self):
        with FakeLaya("error") as fake:
            mom_test.audit(fixture("interview-solid.txt"), client=LayaClient(fake.url, timeout=5),
                           recorder=Recorder(self.ledger, self.f, "interviews", self.iv))
        self.assertEqual(self.ledger.list_labels(self.f), [])


class CliTest(unittest.TestCase):
    """The scripts the skills call, end to end on a SQLite ledger file."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = pathlib.Path(self._tmp.name) / "ledger.db"
        with SqliteLedger(self.db) as ledger:
            ledger.run_migrations()
            self.f = ledger.create_founder("CLI founder")["founder_id"]
            self.iv = ledger.add_interview(self.f, interviewee="studio-owner-2",
                                           notes=fixture("interview-solid.txt"))["id"]
        self.env = {**os.environ, "FOUNDER_OS_LEDGER_BACKEND": "sqlite", "FOUNDER_OS_SQLITE_PATH": str(self.db),
                    "FOUNDER_OS_OPERATOR": ""}

    def tearDown(self):
        self._tmp.cleanup()

    def run_script(self, script, *args, env=None):
        return subprocess.run([sys.executable, str(PLUGIN_DIR / "scripts" / script), *args],
                              capture_output=True, text=True, env=env or self.env, timeout=60)

    def test_audit_record_review_export(self):
        with FakeLaya() as fake:
            env = {**self.env, "LAYA_URL": fake.url}
            r = self.run_script("audit.py", "mom-test", "--founder-id", self.f, "--interview-id", self.iv,
                                "--lang", "en", "--record", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["mode"], "laya")
        label_id = out["turns"][7]["label_ids"]["commitment_intro"]

        pending = json.loads(self.run_script("labels.py", "pending", "--founder-id", self.f).stdout)
        self.assertIn(label_id, {p["id"] for p in pending})
        r = self.run_script("labels.py", "accept", "--founder-id", self.f, "--by", "founder", label_id)
        self.assertEqual(r.returncode, 0, r.stderr)

        r = self.run_script("export_labels.py")
        self.assertEqual(r.returncode, 3)
        self.assertIn("operator-only", r.stderr)
        r = self.run_script("export_labels.py", env={**self.env, "FOUNDER_OS_OPERATOR": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = [json.loads(line) for line in r.stdout.splitlines()]
        self.assertEqual([x["label_id"] for x in rows], [label_id])

        r = self.run_script("record_audit.py", "--founder-id", self.f, "--table", "interviews", "--id", self.iv,
                            "--auditor", "claude", "--check", "mom_test", "--verdict", "pass",
                            "--findings", "turns 2, 4, 6 dated; intro at turn 8")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_audit_without_laya_is_claude_only(self):
        env = {**self.env, "LAYA_URL": ""}
        r = self.run_script("audit.py", "pain-dream-fix", "--input", str(FIXTURES / "ebomb-ordered.md"), env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["mode"], "claude-only")

    def test_record_needs_a_target(self):
        r = self.run_script("audit.py", "mom-test", "--input", str(FIXTURES / "interview-solid.txt"),
                            "--founder-id", self.f, "--record")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--interview-id", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
