#!/usr/bin/env python3
"""test_safari_runner.py - offline suite for the Safari runner.

Stdlib only, no network beyond 127.0.0.1. The Hub is tests/fake_vcl.py, a real
HTTP server. The claude CLI is a fake script put first on PATH: it records its
argv, stdin, cwd and environment to a file and answers the way
`claude -p --output-format json` does. The runner runs as a subprocess through
the real heartbeat gate, scripts/gather-safari-runner.sh, so the stdout
contract is tested too.

Run:
    python3 founder-os/tests/test_safari_runner.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest

TESTS = pathlib.Path(__file__).resolve().parent
PLUGIN_DIR = TESTS.parent
GATHER = PLUGIN_DIR / "scripts" / "gather-safari-runner.sh"
CLI = PLUGIN_DIR / "bin" / "founder-os"
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(TESTS))

from fake_vcl import FakeVCL  # noqa: E402

from founder_runner import claude_argv, save_key  # noqa: E402

# Distinctive, so a leak anywhere is unambiguous.
KEY = "vcl_fos_TESTKEY0123456789abcdefLEAKCANARY"

FAKE_CLAUDE = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    prompt = sys.stdin.read()
    with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": sys.argv[1:], "stdin": prompt, "cwd": os.getcwd(),
                             "env": dict(os.environ)}) + "\\n")
    mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
    if mode == "fail" or (mode == "fail-second" and "second" in prompt):
        sys.stderr.write("Error: simulated model failure\\n")
        sys.exit(1)
    if mode == "is_error":
        print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                          "result": "overloaded"}))
        sys.exit(0)
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                      "result": json.dumps({"echo": prompt})}))
""")


def lease(minutes: float) -> str:
    when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
    return when.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def packet(job_id: str, prompts: list[str], *, model: str | None = None, kind: str = "painstorm",
           phase: str = "chunks", lease_minutes: float = 20) -> dict:
    return {"id": job_id, "kind": kind, "phase": phase, "model": model,
            "system": "You are the painstorm skill. Answer with one JSON object only.",
            "steps": [{"key": f"chunk-{i}", "prompt": p} for i, p in enumerate(prompts)],
            "lease_expires_at": lease(lease_minutes)}


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.bin = root / "bin"
        self.bin.mkdir()
        claude = self.bin / "claude"
        claude.write_text(FAKE_CLAUDE, encoding="utf-8")
        claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.claude_log = root / "claude.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def run_gate(self, fake: FakeVCL, mode: str = "ok", **extra) -> tuple[dict, subprocess.CompletedProcess]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("FOUNDER_OS_")}
        env.update({"PATH": f"{self.bin}{os.pathsep}{env.get('PATH', '')}",
                    "FOUNDER_OS_AGENT_KEY": KEY, "FOUNDER_OS_AGENT_BASE_URL": fake.url,
                    "FAKE_CLAUDE_LOG": str(self.claude_log), "FAKE_CLAUDE_MODE": mode,
                    "ANTHROPIC_API_KEY": "YOUR_API_KEY"})
        env.update(extra)
        proc = subprocess.run(["bash", str(GATHER)], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(len(lines), 1, f"gate stdout must be one JSON line, got {proc.stdout!r}")
        return json.loads(lines[0]), proc

    def claude_calls(self) -> list[dict]:
        if not self.claude_log.exists():
            return []
        return [json.loads(line) for line in self.claude_log.read_text(encoding="utf-8").splitlines()]

    def test_204_is_a_quiet_no_op(self):
        with FakeVCL([], key=KEY) as fake:
            summary, _ = self.run_gate(fake)
        self.assertEqual(summary["count"], 0)
        self.assertEqual(summary["jobs"], 0)
        self.assertEqual(summary["reason"], "nothing queued")
        self.assertEqual([r["method"] for r in fake.requests], ["GET"])
        self.assertEqual(fake.requests[0]["_auth"], f"Bearer {KEY}")
        self.assertTrue(fake.requests[0]["_ua"].startswith("behalfbot-founder-os-runner/"))
        self.assertEqual(self.claude_calls(), [])

    def test_multi_step_packet_posts_every_output_in_order(self):
        job = packet("run-1", ["first chunk text", "second chunk text", "third chunk text"],
                     model="claude-sonnet-4-5", phase="chunks")
        with FakeVCL([job], key=KEY) as fake:
            summary, _ = self.run_gate(fake)
        self.assertEqual((summary["count"], summary["jobs"], summary["posted"]), (0, 1, 1))
        posts = fake.results()
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["path"], "/api/founder-os/agent/jobs/run-1/result")
        body = posts[0]["body"]
        self.assertEqual(body["phase"], "chunks")
        self.assertNotIn("error", body)
        self.assertEqual([o["key"] for o in body["outputs"]], ["chunk-0", "chunk-1", "chunk-2"])
        self.assertEqual(json.loads(body["outputs"][1]["text"]), {"echo": "second chunk text"})

        calls = self.claude_calls()
        self.assertEqual([c["stdin"] for c in calls], ["first chunk text", "second chunk text", "third chunk text"])
        argv = calls[0]["argv"]
        self.assertEqual(argv[:3], ["-p", "--output-format", "json"])
        self.assertEqual(argv[argv.index("--tools") + 1], "", "every built-in tool must be disabled")
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "")
        self.assertIn("--strict-mcp-config", argv)
        self.assertNotIn("--mcp-config", argv)
        self.assertEqual(argv[argv.index("--append-system-prompt") + 1], job["system"])
        self.assertEqual(argv[argv.index("--model") + 1], "claude-sonnet-4-5")
        self.assertNotIn("--bare", argv, "--bare never reads the OAuth login")
        for call in calls:
            self.assertNotIn("ANTHROPIC_API_KEY", call["env"], "must bill the Claude plan, not an API key")
            self.assertNotIn("FOUNDER_OS_AGENT_KEY", call["env"])
            self.assertFalse(pathlib.Path(call["cwd"]).exists(), "claude runs in a throwaway empty directory")

    def test_model_null_omits_the_flag(self):
        with FakeVCL([packet("run-2", ["only"], model=None)], key=KEY) as fake:
            self.run_gate(fake)
        self.assertNotIn("--model", self.claude_calls()[0]["argv"])

    def test_claude_failure_posts_an_error(self):
        job = packet("run-3", ["first ok", "second breaks", "never run"])
        with FakeVCL([job], key=KEY) as fake:
            summary, _ = self.run_gate(fake, mode="fail-second")
        self.assertEqual((summary["count"], summary["failed_steps"], summary["posted"]), (0, 1, 1))
        body = fake.results()[0]["body"]
        self.assertEqual(body["phase"], "chunks")
        self.assertNotIn("outputs", body)
        self.assertIn("step chunk-1", body["error"])
        self.assertIn("claude exited 1", body["error"])
        self.assertIn("simulated model failure", body["error"])
        self.assertEqual(len(self.claude_calls()), 2, "a failed step ends the job")

    def test_claude_is_error_result_posts_an_error(self):
        with FakeVCL([packet("run-4", ["x"])], key=KEY) as fake:
            self.run_gate(fake, mode="is_error")
        self.assertIn("error_during_execution", fake.results()[0]["body"]["error"])

    def test_409_is_dropped_quietly_and_the_tick_continues(self):
        jobs = [packet("lost", ["a"]), packet("kept", ["b"], kind="ebomb_analysis", phase="analysis")]
        with FakeVCL(jobs, key=KEY, result_status={"lost": 409}) as fake:
            summary, proc = self.run_gate(fake)
        self.assertEqual((summary["count"], summary["jobs"], summary["posted"], summary["dropped"]), (0, 2, 1, 1))
        self.assertFalse(summary.get("error"))
        paths = [r["path"] for r in fake.results()]
        self.assertEqual(paths, ["/api/founder-os/agent/jobs/lost/result", "/api/founder-os/agent/jobs/kept/result"],
                         "one POST per job, no retry of the 409")
        self.assertIn("job lost: HTTP 409, dropped", proc.stderr)

    def test_at_most_three_jobs_per_tick(self):
        jobs = [packet(f"j{i}", ["p"]) for i in range(5)]
        with FakeVCL(jobs, key=KEY) as fake:
            summary, _ = self.run_gate(fake)
        self.assertEqual(summary["jobs"], 3)
        self.assertEqual(len(fake.jobs), 2, "two jobs left queued for the next tick")
        self.assertEqual(sum(1 for r in fake.requests if r["method"] == "GET"), 3)

    def test_lease_near_posts_error_and_stops_the_tick(self):
        jobs = [packet("late", ["a"], lease_minutes=0.5), packet("next", ["b"])]
        with FakeVCL(jobs, key=KEY) as fake:
            summary, _ = self.run_gate(fake)
        self.assertEqual(summary["jobs"], 1)
        self.assertIn("lease deadline", summary["reason"])
        self.assertIn("lease deadline reached before step chunk-0", fake.results()[0]["body"]["error"])
        self.assertEqual(self.claude_calls(), [])
        self.assertEqual(len(fake.jobs), 1, "the second job is not claimed")

    def test_rejected_key_alerts(self):
        with FakeVCL([packet("x", ["a"])], key="vcl_fos_someoneElsesKey0000000000") as fake:
            summary, _ = self.run_gate(fake)
        self.assertEqual(summary["count"], 1)
        self.assertIn("rejected the agent key", summary["reason"])
        self.assertEqual(fake.results(), [])

    def test_missing_claude_alerts_and_posts_error(self):
        with FakeVCL([packet("x", ["a"]), packet("y", ["b"])], key=KEY) as fake:
            summary, _ = self.run_gate(fake, FOUNDER_OS_RUNNER_CLAUDE=str(self.bin / "no-such-claude"))
        self.assertEqual(summary["count"], 1)
        self.assertIn("claude CLI not found", summary["reason"])
        self.assertIn("claude CLI not found", fake.results()[0]["body"]["error"])
        self.assertEqual(len(fake.jobs), 1)

    def test_unreachable_hub_is_not_an_alert(self):
        with FakeVCL([], key=KEY) as fake:
            url = fake.url
        env = {"FOUNDER_OS_AGENT_BASE_URL": url}
        with FakeVCL([], key=KEY) as other:
            summary, _ = self.run_gate(other, **env)
        self.assertEqual(summary["count"], 0)
        self.assertTrue(summary["error"])
        self.assertIn("Hub unreachable", summary["reason"])

    def test_no_key_is_a_quiet_no_op(self):
        with FakeVCL([packet("x", ["a"])], key=KEY) as fake:
            summary, _ = self.run_gate(fake, FOUNDER_OS_AGENT_KEY="")
        self.assertEqual(summary["count"], 0)
        self.assertIn("runner setup", summary["reason"])
        self.assertEqual(fake.requests, [])

    def test_plain_http_refused_off_localhost(self):
        with FakeVCL([], key=KEY) as fake:
            summary, _ = self.run_gate(fake, FOUNDER_OS_AGENT_BASE_URL="http://example.com")
        self.assertEqual(summary["count"], 1)
        self.assertIn("https", summary["reason"])

    def test_key_never_appears_in_logs_or_claude(self):
        jobs = [packet("a", ["one", "second two"]), packet("b", ["three"])]
        outputs = []
        bodies = []
        with FakeVCL(jobs, key=KEY, result_status={"b": 409}) as fake:
            _, proc = self.run_gate(fake, mode="fail-second")
            outputs += [proc.stdout, proc.stderr]
            bodies += [r["body"] for r in fake.results()]
        with FakeVCL([packet("c", ["x"])], key="vcl_fos_differentKey00000000000000") as fake:
            _, proc = self.run_gate(fake)
            outputs += [proc.stdout, proc.stderr]
        self.assertEqual(len(bodies), 2, "both jobs posted, one with an error")
        self.assertTrue(self.claude_calls(), "claude was exercised")
        outputs += [json.dumps(call) for call in self.claude_calls()]
        outputs += [json.dumps(body) for body in bodies]
        for text in outputs:
            self.assertNotIn(KEY, text)
            self.assertNotIn("TESTKEY0123456789", text, "not even a fragment of the key")


class ArgvTest(unittest.TestCase):
    def test_exact_flags(self):
        self.assertEqual(claude_argv("claude", "SYS", "claude-x"), [
            "claude", "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config",
            "--setting-sources", "", "--disable-slash-commands", "--no-session-persistence",
            "--append-system-prompt", "SYS", "--model", "claude-x"])


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def setup_cli(self, stdin: str, *args: str) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if not k.startswith("FOUNDER_OS_")}
        env["CUSTOMER_HOME"] = str(self.home)
        return subprocess.run([sys.executable, str(CLI), "runner", "setup", *args], input=stdin,
                              capture_output=True, text=True, env=env, timeout=60)

    def test_setup_writes_env_0600_and_never_prints_the_key(self):
        env_file = self.home / ".env"
        env_file.write_text("DISCORD_BOT_TOKEN=keep-me\nFOUNDER_OS_AGENT_KEY=vcl_fos_oldoldoldoldoldold\nOTHER=1\n")
        proc = self.setup_cli(KEY + "\n", "--base-url", "https://staging.example.com/")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(KEY, proc.stdout + proc.stderr)
        self.assertIn(str(env_file), proc.stdout)
        lines = env_file.read_text().splitlines()
        self.assertEqual(lines, ["DISCORD_BOT_TOKEN=keep-me", f"FOUNDER_OS_AGENT_KEY={KEY}", "OTHER=1",
                                 "FOUNDER_OS_AGENT_BASE_URL=https://staging.example.com"])
        self.assertEqual(stat.S_IMODE(env_file.stat().st_mode), 0o600)

    def test_setup_updates_env_baked_when_present(self):
        (self.home / ".env.baked").write_text("A=1\n")
        proc = self.setup_cli(KEY + "\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"FOUNDER_OS_AGENT_KEY={KEY}", (self.home / ".env").read_text())
        self.assertEqual((self.home / ".env.baked").read_text().splitlines(), ["A=1", f"FOUNDER_OS_AGENT_KEY={KEY}"])

    def test_setup_refuses_a_bad_key_without_echoing_it(self):
        bad = "not-an-agent-key-YOUR_API_KEY"
        proc = self.setup_cli(bad + "\n")
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn(bad, proc.stdout + proc.stderr)
        self.assertNotIn("YOUR_API_KEY", proc.stdout + proc.stderr)
        self.assertFalse((self.home / ".env").exists())

    def test_save_key_refuses_plain_http(self):
        with self.assertRaises(ValueError):
            save_key(KEY, self.home / ".env", "http://vibecodelisboa.com")


if __name__ == "__main__":
    unittest.main(verbosity=2)
