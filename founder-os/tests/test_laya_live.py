#!/usr/bin/env python3
"""test_laya_live.py - the auditors against a real Laya server. Optional.

Skipped unless LAYA_URL is set, so CI (which never sets it) skips every case
and exits 0. Point it at a local laya-serve to run it:

    LAYA_URL=http://127.0.0.1:8765 python3 founder-os/tests/test_laya_live.py

It asserts what must hold for any model: every auditor comes back in laya mode,
every item is tagged with a well-formed answer, checkpoints route by language,
and no chunk reaches the model's window. Accuracy against the expected tags in
fixtures/expected.json is printed, not asserted: no accuracy target has been
set for these question sets yet (behalfbot-plugins#28), and a zero-shot base
checkpoint is not expected to agree with them.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import unittest

TESTS = pathlib.Path(__file__).resolve().parent
PLUGIN_DIR = TESTS.parent
FIXTURES = TESTS / "fixtures"
sys.path.insert(0, str(PLUGIN_DIR))

from founder_audit import LayaClient  # noqa: E402
from founder_audit import earlyvangelist, mom_test, pain, pain_dream_fix  # noqa: E402

LIVE = bool(os.environ.get("LAYA_URL"))
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def report(name: str, hits: int, total: int) -> None:
    print(f"  live agreement {name}: {hits}/{total}", file=sys.stderr)


@unittest.skipUnless(LIVE, "LAYA_URL not set; live Laya test skipped")
class LiveLayaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = LayaClient(timeout=float(os.environ.get("LAYA_TIMEOUT", "60")))
        cls.client.health()

    def assertLaya(self, out):
        self.assertEqual(out["mode"], "laya", out.get("degraded_reason"))

    def test_mom_test(self):
        for name, exp in EXPECTED["mom-test"].items():
            out = mom_test.audit(fixture(name), client=self.client, founder=exp["founder"], lang="en")
            self.assertLaya(out)
            hits = total = 0
            for t in out["turns"]:
                self.assertTrue(t["tags"], f"turn {t['n']} untagged")
                for tag in t["tags"].values():
                    self.assertIsInstance(tag["value"], bool)
                    self.assertTrue(0.0 <= tag["p"] <= 1.0)
                for qid, value in exp["turns"].get(str(t["n"]), {}).items():
                    total += 1
                    hits += t["tags"][qid]["value"] == value
            report(name, hits, total)

    def test_earlyvangelist(self):
        for name, exp in EXPECTED["earlyvangelist"].items():
            out = earlyvangelist.audit(fixture(name), client=self.client, transcript=True, lang="en")
            self.assertLaya(out)
            self.assertEqual(len(out["criteria"]), 5)
            report(f"{name} escalate={out['escalate']} met={out['met']}", int(out["escalate"] == exp["escalate"]), 1)

    def test_pain_dream_fix(self):
        for name, exp in EXPECTED["pain-dream-fix"].items():
            out = pain_dream_fix.audit(fixture(name), client=self.client, lang="en")
            self.assertLaya(out)
            seq = out["summary"]["sequence"]
            self.assertTrue(all(s in ("pain", "dream", "fix") for s in seq))
            report(f"{name} sequence={seq} premature={out['summary']['premature_pitch']}",
                   int(out["summary"]["premature_pitch"] == exp["premature_pitch"]), 1)

    def test_pain_tagger_routing_and_chunking(self):
        posts = json.loads(fixture("posts.json"))
        out = pain.rank_posts(posts, client=self.client, lang="en", jobs=["get paid on time", "find clients"])
        self.assertLaya(out)
        exp = EXPECTED["pain-tagger"]["posts.json"]
        hits = total = 0
        for p in out["posts"]:
            tags = p["tags"]
            self.assertEqual(tags["is_pain"]["checkpoint"], "english")
            self.assertEqual(tags["money_or_workaround"]["checkpoint"], "multilingual")
            self.assertFalse(tags["is_pain"]["truncated"], f"{p['id']} reached the window")
            if p["id"] == "p4":
                self.assertGreater(tags["is_pain"]["chunks"], 1)
            for qid in ("is_pain", "money_or_workaround"):
                if p["id"] in exp[qid]:
                    total += 1
                    hits += tags[qid]["value"] == exp[qid][p["id"]]
        report("posts.json " + ", ".join(f"{p['id']}={p['tags']['is_pain']['p']}" for p in out["posts"]), hits, total)


if __name__ == "__main__":
    unittest.main(verbosity=2)
