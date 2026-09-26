#!/usr/bin/env python3
"""test_stage_walk.py - a synthetic founder walked through the stage skills' CLI.

End to end against a SQLite ledger, using only what the stage SKILL.md files
tell Claude to run: scripts/stage.py, scripts/record_audit.py and
scripts/audit.py (in Claude-only mode, since CI has no Laya). The content is
invented for this test.

The walk:
- stage 0 from an empty ledger to a passed gate, including the refusals on
  the way (a pass with missing rows, a pass before Claude has ruled, a founder
  writing Sean's verdict)
- stages 1 and 2 with minimal rows, to reach stage 3
- a stage 3 attempt on two pitchy interviews that fails and stays in stage 3
- a stage 3 attempt with every minimum met that is refused until Sean signs
  off, then passes as claude+sean
- a stage 3 fail routed back to stage 2, and a forward route refused

Stdlib only, no network. Run:
    python3 founder-os/tests/test_stage_walk.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_DIR / "scripts"

PITCHY = """Founder: We're building an app that plans delivery routes for florists. Would you use it?
Bea: Oh, I love that, it sounds really useful.
Founder: Would you pay twenty euros a month?
Bea: Probably, yes. Everyone in floristry hates planning routes.
Founder: Great, I'll keep you posted.
Bea: Please do!
"""

SOLID = """Founder: When did a delivery last go wrong?
Rita: On Saturday the 14th two wedding orders went to the wrong venue and I refunded 90 euros.
Founder: How do you plan the routes now?
Rita: I write them on the back of the order slips every morning, it takes about forty minutes.
Founder: What would a next step look like?
Rita: Come to the shop on Tuesday at 8 and watch me plan the day's route.
"""


class StageWalk(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("FOUNDER_OS_OPERATOR", "LAYA_URL", "FOUNDER_OS_INCLUDE_CONTRIB")}
        self.env.update({
            "FOUNDER_OS_LEDGER_BACKEND": "sqlite",
            "FOUNDER_OS_SQLITE_PATH": str(self.tmp / "ledger.db"),
            "FOUNDER_OS_DIR": str(PLUGIN_DIR),
        })
        self.fid = self.stage("new-founder", "--name", "Walk Test", "--context",
                              '{"parked_app": "a route planner for florists"}')["founder_id"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- helpers --------------------------------------------------------------

    def run_script(self, script: str, *args: str, ok: bool = True, env: dict | None = None):
        proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True,
                              text=True, env=env or self.env, timeout=60)
        if ok:
            self.assertEqual(proc.returncode, 0, f"{script} {args}: {proc.stderr}")
            return json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, 0, f"{script} {args} should have been refused: {proc.stdout}")
        return proc.stderr

    def stage(self, *args: str, ok: bool = True):
        return self.run_script("stage.py", *args, ok=ok)

    def artifact(self, kind: str, body: str = "synthetic", meta: dict | None = None) -> str:
        args = ["add-artifact", "--founder-id", self.fid, "--kind", kind, "--body", body]
        if meta:
            args += ["--meta", json.dumps(meta)]
        return self.stage(*args)["id"]

    def rule_all(self, submission: dict, verdict: str = "pass") -> None:
        for check in submission["checks"]:
            self.run_script("record_audit.py", "--founder-id", self.fid, "--table", "artifacts",
                            "--id", submission["submission_id"], "--auditor", "claude",
                            "--check", check["check"], "--verdict", verdict,
                            "--findings", f"synthetic ruling on {check['check']}")

    def context(self) -> dict:
        return self.stage("context", "--founder-id", self.fid)

    def interview(self, label: str, notes: str, commitment: str = "none", ev: bool = False,
                  verdict: str = "pass") -> str:
        path = self.tmp / f"{label}.txt"
        path.write_text(notes, encoding="utf-8")
        args = ["add-interview", "--founder-id", self.fid, "--interviewee", label, "--notes-file", str(path),
                "--conducted-on", "2026-09-01", "--segment", "florists", "--commitment", commitment]
        if ev:
            args.append("--earlyvangelist")
        iid = self.stage(*args)["id"]
        audit = self.run_script("audit.py", "mom-test", "--input", str(path), "--founder", "Founder",
                                "--lang", "en")
        # No Laya in CI: the turns are split and patterned, and Claude does the
        # tagging. Here the test plays Claude and supplies the verdict.
        self.assertEqual(audit["mode"], "claude-only")
        self.assertEqual(audit["summary"]["turns"], len(notes.strip().splitlines()))
        self.run_script("record_audit.py", "--founder-id", self.fid, "--table", "interviews", "--id", iid,
                        "--auditor", "claude", "--check", "mom_test", "--verdict", verdict,
                        "--findings", "synthetic audit")
        return iid

    def pass_gate(self, sean: bool = False) -> dict:
        sub = self.stage("submit", "--founder-id", self.fid)
        self.assertTrue(sub["ready"], sub["missing"])
        self.rule_all(sub)
        if sean:
            self.run_script("stage.py", "signoff", "--founder-id", self.fid, "--verdict", "pass",
                            "--findings", "synthetic sign-off", env={**self.env, "FOUNDER_OS_OPERATOR": "1"})
        return self.stage("decide", "--founder-id", self.fid, "--decision", "pass",
                          "--rationale", "synthetic: every minimum met and every check passed")

    def walk_stage_0(self) -> None:
        self.artifact("why_statement", "I believe small shops deserve evenings off.")
        self.artifact("why_evidence", "2019, 2021, 2023: three dated things done before the idea")
        self.artifact("fit_check", "problem: fits; audience: fits")
        self.artifact("lean_canvas", "Plan A canvas", meta={"plan_a": True})
        self.stage("add-prfaq", "--founder-id", self.fid, "--body", "Press release, external FAQ, internal FAQ",
                   "--assumptions", json.dumps([f"assumption {n}: who, number, threshold" for n in range(5)]))
        self.artifact("riskiest_assumption", "Florists with 3+ vans pay 30 euros a month")
        self.pass_gate()

    def walk_to_stage_3(self) -> None:
        self.walk_stage_0()
        self.artifact("audience", "Florists who deliver their own orders", meta={"bowling_pin": "Lisbon florists"})
        self.artifact("watering_holes", "three kept places")
        self.pass_gate()
        self.artifact("problem_hypothesis", "Florists lose an hour a day to route planning")
        for n in range(3):
            self.artifact("safari_session", f"session {n}")
        for n in range(30):
            pid = self.stage("add-pain", "--founder-id", self.fid, "--quote", f"synthetic quote {n}",
                             "--source-url", f"https://forum.example/t/{n}", "--watering-hole",
                             f"hole-{n % 3}", "--job", "plan-deliveries")["id"]
            self.run_script("record_audit.py", "--founder-id", self.fid, "--table", "pains", "--id", pid,
                            "--auditor", "claude", "--check", "pain_log", "--verdict", "pass")
        for n in range(3):
            self.artifact("saturation_check", f"check {n}")
        self.artifact("jobs", "plan-deliveries")
        self.pass_gate()
        self.assertEqual(self.context()["current_stage"], 3)

    # --- tests ----------------------------------------------------------------

    def test_stage_0_to_gate_submission_and_pass(self) -> None:
        ctx = self.context()
        self.assertEqual(ctx["current_stage"], 0)
        self.assertEqual(ctx["stage_skill"], "founder-os-stage-0-why")
        self.assertEqual(ctx["gate_id"], "stage-0-why")

        cards = self.stage("cards", "--founder-id", self.fid)
        self.assertEqual({c["id"] for c in cards["cards"]},
                         {"find-your-why", "prfaq-v0", "plan-a-riskiest-assumption"})
        self.assertTrue(all(c["path"].startswith("core/stage-0/") for c in cards["cards"]))
        self.assertIn("riskiest-assumption", {c["id"] for c in cards["concepts"]})

        # Handing over with nothing written: the submission says what is short,
        # and a pass is refused.
        empty = self.stage("submit", "--founder-id", self.fid)
        self.assertFalse(empty["ready"])
        self.assertIn("prfaq_versions>=1", empty["missing"])
        err = self.stage("decide", "--founder-id", self.fid, "--decision", "pass", "--rationale", "x", ok=False)
        self.assertIn("a pass needs every minimum", err)

        self.artifact("why_statement", "I believe small shops deserve evenings off.")
        self.artifact("why_evidence", "2019, 2021, 2023")
        self.artifact("fit_check", "problem: fits; audience: fits")
        self.artifact("lean_canvas", "Plan A canvas", meta={"plan_a": True})
        self.stage("add-prfaq", "--founder-id", self.fid, "--body", "PR/FAQ v0",
                   "--assumptions", json.dumps([f"assumption {n}" for n in range(5)]))
        self.artifact("riskiest_assumption", "Florists with 3+ vans pay 30 euros a month")

        sub = self.stage("submit", "--founder-id", self.fid)
        self.assertTrue(sub["ready"], sub["missing"])
        self.assertEqual(sub["gate_id"], "stage-0-why")
        self.assertEqual(len(sub["checks"]), 13)
        progress = {p["stage"]: p["status"] for p in self.context()["progress"]}
        self.assertEqual(progress[0], "gate_pending")

        err = self.stage("decide", "--founder-id", self.fid, "--decision", "pass", "--rationale", "x", ok=False)
        self.assertIn("Claude has not ruled", err)

        # A founder session cannot write Sean's verdict.
        err = self.run_script("record_audit.py", "--founder-id", self.fid, "--table", "artifacts",
                              "--id", sub["submission_id"], "--auditor", "sean", "--check", "gate_signoff",
                              "--verdict", "pass", ok=False)
        self.assertIn("operator-only", err)

        self.rule_all(sub)
        decision = self.stage("decide", "--founder-id", self.fid, "--decision", "pass",
                              "--rationale", "every minimum met, every check passed")
        self.assertEqual((decision["decision"], decision["decided_by"]), ("pass", "claude"))
        cited = {(e["table"], e["id"]) for e in decision["evidence"]}
        self.assertIn(("artifacts", sub["submission_id"]), cited)
        self.assertTrue(any(t == "prfaq_versions" for t, _ in cited))
        self.assertEqual(self.context()["current_stage"], 1)

    def test_stage_3_attempt_fails_then_needs_sean(self) -> None:
        self.walk_to_stage_3()
        cards = self.stage("cards", "--founder-id", self.fid)
        self.assertTrue(all(c["path"].startswith("core/stage-3/") for c in cards["cards"]))

        # Attempt 1: two pitchy interviews. The gate fails and stays in stage 3.
        self.interview("florist-1", PITCHY, verdict="fail")
        self.interview("florist-2", PITCHY, verdict="fail")
        sub = self.stage("submit", "--founder-id", self.fid)
        self.assertFalse(sub["ready"])
        self.assertEqual(set(sub["missing"]), {"interviews>=10", "interviews:audited>=10",
                                               "interviews:committed>=5", "interviews:earlyvangelist>=1",
                                               "artifacts/big_questions>=1"})
        self.rule_all(sub, verdict="fail")
        err = self.stage("decide", "--founder-id", self.fid, "--decision", "pass", "--rationale", "x", ok=False)
        self.assertIn("a pass needs every minimum", err)
        fail = self.stage("decide", "--founder-id", self.fid, "--decision", "fail", "--rationale",
                          "Two interviews, both pitched before any fact and no commitment. "
                          "Rewrite the questions: interviews-without-fooling-yourself, steps 1 and 2.")
        self.assertEqual((fail["decision"], fail["routes_to_stage"]), ("fail", 3))
        ctx = self.context()
        self.assertEqual(ctx["current_stage"], 3)
        self.assertEqual(ctx["gate_history"][-1]["decision"], "fail")

        # Attempt 2: every minimum met and every check passed by Claude. Still no
        # pass until Sean signs off, and only the operator can sign.
        for n in range(8):
            self.interview(f"florist-{n + 3}", SOLID, commitment="time" if n < 5 else "none", ev=(n == 0))
        self.artifact("big_questions", "which questions got answered, with interview ids")
        sub = self.stage("submit", "--founder-id", self.fid)
        self.assertTrue(sub["ready"], sub["missing"])
        self.rule_all(sub)
        err = self.stage("decide", "--founder-id", self.fid, "--decision", "pass", "--rationale", "x", ok=False)
        self.assertIn("needs Sean's sign-off", err)
        err = self.stage("signoff", "--founder-id", self.fid, "--verdict", "pass", "--findings", "me", ok=False)
        self.assertIn("operator-only", err)
        decision = self.pass_gate(sean=True)
        self.assertEqual((decision["decided_by"], decision["sean_signoff"]), ("claude+sean", True))
        self.assertEqual(self.context()["current_stage"], 4)

    def test_stage_3_fail_routes_back_to_stage_2(self) -> None:
        self.walk_to_stage_3()
        self.interview("florist-1", PITCHY, verdict="fail")
        self.stage("submit", "--founder-id", self.fid)
        err = self.stage("decide", "--founder-id", self.fid, "--decision", "fail", "--rationale", "x",
                         "--routes-to", "4", ok=False)
        self.assertIn("cannot route a founder forward", err)
        self.stage("decide", "--founder-id", self.fid, "--decision", "fail", "--routes-to", "2",
                   "--rationale", "Interviewees did not recognise the problem: back to the pain log.")
        ctx = self.context()
        self.assertEqual(ctx["current_stage"], 2)
        self.assertEqual(ctx["stage_skill"], "founder-os-stage-2-pain-research")
        progress = {p["stage"]: p["status"] for p in ctx["progress"]}
        self.assertEqual(progress[2], "in_progress")

    def test_decide_needs_a_submission(self) -> None:
        err = self.stage("decide", "--founder-id", self.fid, "--decision", "fail", "--rationale", "x", ok=False)
        self.assertIn("not gate_pending", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
