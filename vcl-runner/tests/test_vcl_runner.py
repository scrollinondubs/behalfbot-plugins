#!/usr/bin/env python3
"""test_vcl_runner.py - offline suite for the VCL runner.

Stdlib only, no network beyond 127.0.0.1. The Hub is tests/fake_hub.py, a real
HTTP server. The claude CLI is a fake script put first on PATH: it records its
argv, stdin, cwd and environment to a file and answers the way
`claude -p --output-format json` does. rmapi is faked the same way for
tablet_send and tablet_pull jobs; the document a pull reads is built with
rmscene's own writer (tests/rm_fixtures.py), and the tests that parse it skip
when rmscene is not installed. The runner runs as a subprocess through
the real heartbeat gate, scripts/gather-vcl-runner.sh, so the stdout
contract is tested too.

Run:
    python3 vcl-runner/tests/test_vcl_runner.py
"""
from __future__ import annotations

import base64
import datetime as dt
import importlib.util
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
GATHER = PLUGIN_DIR / "scripts" / "gather-vcl-runner.sh"
CLI = PLUGIN_DIR / "bin" / "vcl-runner"
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(TESTS))

from fake_hub import FakeHub  # noqa: E402

from vcl_runner import annotations, claude_argv, save_key  # noqa: E402
from vcl_runner.runner import doc_version  # noqa: E402

HAVE_RMSCENE = importlib.util.find_spec("rmscene") is not None
NEEDS_RMSCENE = unittest.skipUnless(HAVE_RMSCENE, "rmscene is not installed (the BehalfBot image has it)")

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
    with open(os.environ["FAKE_CLAUDE_LOG"], encoding="utf-8") as fh:
        call_no = sum(1 for _ in fh)
    # What CLI 2.1.280 writes to stderr for a full model id, success included.
    noise = ('Warning: Advisor disabled for this model\\n'
             '[claude-code:unrecognized_model] {"model":"claude-sonnet-5-5","query_source":"sdk"}\\n')
    if mode in ("model-404", "auth", "overloaded-once", "overloaded-always", "garbled-once", "ok-noisy"):
        sys.stderr.write(noise)
    if mode == "model-404":
        print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "api_error_status": 404,
                          "result": "There's an issue with the selected model (claude-sonnet-5-5)."}))
        sys.exit(1)
    if mode == "auth":
        print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "api_error_status": 401,
                          "result": "Invalid API key - Please run /login"}))
        sys.exit(1)
    if mode == "overloaded-always" or (mode == "overloaded-once" and call_no == 1):
        print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "api_error_status": 529,
                          "result": "API Error: 529 Overloaded", "total_cost_usd": 0.01,
                          "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 100, "outputTokens": 0,
                                                               "cacheReadInputTokens": 0,
                                                               "cacheCreationInputTokens": 0}}}))
        sys.exit(1)
    if mode == "garbled-once" and call_no == 1:
        sys.exit(1)
    if mode == "fail" or (mode == "fail-second" and "second" in prompt):
        sys.stderr.write("Error: simulated model failure\\n")
        sys.exit(1)
    if mode == "is_error":
        print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                          "result": "overloaded"}))
        sys.exit(0)
    out = {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps({"echo": prompt})}
    if mode == "usage-legacy":
        out["usage"] = {"input_tokens": 7, "output_tokens": 9, "cache_read_input_tokens": 3,
                        "cache_creation_input_tokens": 5}
    elif mode != "no-usage":
        out["total_cost_usd"] = 0.123456
        out["modelUsage"] = {
            "claude-sonnet-5-5": {"inputTokens": 1200, "outputTokens": 3400, "cacheReadInputTokens": 600,
                                  "cacheCreationInputTokens": 2900, "costUSD": 0.12},
            "claude-haiku-5-5": {"inputTokens": 10, "outputTokens": 20, "cacheReadInputTokens": 0,
                                 "cacheCreationInputTokens": 0, "costUSD": 0.003456},
        }
    print(json.dumps(out))
""")


FAKE_RMAPI = textwrap.dedent("""\
    #!/usr/bin/env python3
    import base64, json, os, sys
    args = sys.argv[1:]
    entry = {"argv": args, "stdin": sys.stdin.read(), "env": dict(os.environ), "cwd": os.getcwd()}
    if len(args) >= 3 and args[1] == "put" and os.path.isfile(args[2]):
        with open(args[2], "rb") as fh:
            entry["file"] = base64.b64encode(fh.read()).decode()
    with open(os.environ["FAKE_RMAPI_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\\n")
    if args[:1] != ["-ni"]:
        print("Enter one-time code (go to https://my.remarkable.com/device/desktop/connect): ")
        sys.exit(3)
    mode = os.environ.get("FAKE_RMAPI_MODE", "ok")
    if mode == "not-paired":
        sys.stderr.write("ERROR: 2026/10/25 13:06:35 auth.go:30: missing token, not asking, aborting\\n")
        sys.exit(1)
    if mode == "put-fails" and args[1] == "put":
        sys.stderr.write("ERROR: 2026/10/25 13:06:35 main.go:95: Error:  entry already exists\\n")
        sys.exit(1)
    if mode == "folder-exists" and args[1] == "mkdir":
        print("entry already exists")
    if args[1] == "stat":
        if mode == "no-doc":
            sys.stderr.write("ERROR: 2026/10/25 13:06:35 main.go:95: Error:  file doesn't exist\\n")
            sys.exit(1)
        print(json.dumps({"ID": "0a1b", "Name": os.path.basename(args[2]), "Version": 3,
                          "ModifiedClient": os.environ.get("FAKE_RMAPI_VERSION", "2026-10-25T15:00:00Z"),
                          "Type": "DocumentType"}, indent=2))
    if args[1] == "get":
        name = os.path.basename(args[2]) + ".rmdoc"
        with open(os.environ["FAKE_RMAPI_DOC"], "rb") as src, open(name, "wb") as dst:
            dst.write(src.read())
        print("downloading: [" + os.path.basename(args[2]) + "]...")
""")

PDF = b"%PDF-1.7\n% not really a pdf\n" + bytes(range(256))
FILE_PATH = "/api/founder-os/agent/tablet/files/abc123"


def lease(minutes: float) -> str:
    when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
    return when.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def packet(job_id: str, prompts: list[str], *, model: str | None = None, kind: str = "job_a",
           phase: str = "chunks", lease_minutes: float = 20) -> dict:
    return {"id": job_id, "kind": kind, "phase": phase, "model": model,
            "system": "You are a test skill. Answer with one JSON object only.",
            "steps": [{"key": f"chunk-{i}", "prompt": p} for i, p in enumerate(prompts)],
            "lease_expires_at": lease(lease_minutes)}


def tablet_packet(job_id: str, file_url: str, *, folder: str = "/Safari",
                  filename: str = "Safari reading 2026-10-25.pdf", lease_minutes: float = 20) -> dict:
    return {"id": job_id, "kind": "tablet_send", "lease_expires_at": lease(lease_minutes),
            "tablet": {"target": "remarkable", "file_url": file_url, "filename": filename, "folder": folder}}


DOC_PATH = "/Safari/Safari reading 2026-10-25 1342"
PULL_BASE = "/api/founder-os/agent/tablet-pulls/pull-1"


def pull_packet(job_id: str = "pull-1", *, since: str | None = None, known: dict | None = None,
                lease_minutes: float = 20, base: str = "") -> dict:
    return {"id": job_id, "kind": "tablet_pull", "phase": "pull", "model": None, "system": "", "steps": [],
            "lease_expires_at": lease(lease_minutes),
            "tablet": {"target": "remarkable", "doc_path": DOC_PATH, "since": since,
                       "document_url": f"{base}/api/founder-os/agent/tablet-pulls/{job_id}/document",
                       "pages_url": f"{base}/api/founder-os/agent/tablet-pulls/{job_id}/pages",
                       "known_pages": known or {}}}


def png_size(png: bytes) -> tuple[int, int]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")


def png_alpha(png: bytes, x: int, y: int) -> int:
    """The alpha of one pixel of a grey + alpha PNG the runner wrote (filter 0 on every row)."""
    import zlib
    width, _ = png_size(png)
    pos, idat = 8, b""
    while pos < len(png):
        length = int.from_bytes(png[pos:pos + 4], "big")
        if png[pos + 4:pos + 8] == b"IDAT":
            idat += png[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    row = y * (1 + width * 2)
    return raw[row + 1 + x * 2 + 1]


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
        rmapi = self.bin / "rmapi"
        rmapi.write_text(FAKE_RMAPI, encoding="utf-8")
        rmapi.chmod(rmapi.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.rmapi_log = root / "rmapi.jsonl"
        self.home = root / "home"
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_gate(self, fake: FakeHub, mode: str = "ok", **extra) -> tuple[dict, subprocess.CompletedProcess]:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("FOUNDER_OS_") and k not in ("CUSTOMER_HOME", "CHASSIS_HOME")}
        env.update({"PATH": f"{self.bin}{os.pathsep}{env.get('PATH', '')}", "CUSTOMER_HOME": str(self.home),
                    "FOUNDER_OS_AGENT_KEY": KEY, "FOUNDER_OS_AGENT_BASE_URL": fake.url,
                    "FAKE_CLAUDE_LOG": str(self.claude_log), "FAKE_CLAUDE_MODE": mode,
                    "RMAPI_BIN": str(self.bin / "rmapi"), "FAKE_RMAPI_LOG": str(self.rmapi_log),
                    "ANTHROPIC_API_KEY": "YOUR_API_KEY", "FOUNDER_OS_RUNNER_RETRY_BACKOFF": "0"})
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

    def rmapi_calls(self) -> list[dict]:
        if not self.rmapi_log.exists():
            return []
        return [json.loads(line) for line in self.rmapi_log.read_text(encoding="utf-8").splitlines()]

    def test_tablet_send_uploads_to_remarkable_without_claude(self):
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs.append(tablet_packet("tab-1", fake.url + FILE_PATH, folder="/Safari/Reading"))
            summary, proc = self.run_gate(fake)
        self.assertEqual((summary["count"], summary["jobs"], summary["posted"], summary["failed_steps"]),
                         (0, 1, 1, 0))
        posts = fake.results()
        self.assertEqual(posts[0]["path"], "/api/founder-os/agent/jobs/tab-1/result")
        self.assertEqual(posts[0]["body"], {"ok": True, "doc_path": "/Safari/Reading/Safari reading 2026-10-25"})
        download = [r for r in fake.requests if r["path"] == FILE_PATH]
        self.assertEqual(len(download), 1)
        self.assertEqual(download[0]["_auth"], f"Bearer {KEY}")
        self.assertEqual(self.claude_calls(), [], "a tablet_send never calls claude")

        calls = self.rmapi_calls()
        self.assertEqual([c["argv"] for c in calls[:2]],
                         [["-ni", "mkdir", "/Safari"], ["-ni", "mkdir", "/Safari/Reading"]],
                         "a missing parent folder is made first")
        self.assertEqual(len(calls), 3)
        put = calls[2]["argv"]
        self.assertEqual(put[:2], ["-ni", "put"])
        self.assertEqual(pathlib.Path(put[2]).name, "Safari reading 2026-10-25.pdf")
        self.assertEqual(put[3], "/Safari/Reading")
        self.assertEqual(base64.b64decode(calls[2]["file"]), PDF, "rmapi gets the bytes the Hub served")
        self.assertFalse(pathlib.Path(put[2]).exists(), "the downloaded file is cleaned up")
        for call in calls:
            self.assertEqual(call["stdin"], "")
            self.assertNotIn("FOUNDER_OS_AGENT_KEY", call["env"])
            self.assertNotIn(KEY, json.dumps(call))
        self.assertNotIn(KEY, proc.stdout + proc.stderr)

    def test_tablet_send_to_the_root_folder(self):
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs.append(tablet_packet("tab-root", FILE_PATH, folder="/", filename="Week 3.pdf"))
            self.run_gate(fake)
        self.assertEqual(fake.results()[0]["body"], {"ok": True, "doc_path": "/Week 3"})
        self.assertEqual([c["argv"][1] for c in self.rmapi_calls()], ["put"])
        self.assertEqual(self.rmapi_calls()[0]["argv"][3], "/")

    def test_tablet_send_into_an_existing_folder(self):
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs.append(tablet_packet("tab-2", FILE_PATH))
            self.run_gate(fake, FAKE_RMAPI_MODE="folder-exists")
        self.assertEqual(fake.results()[0]["body"], {"ok": True, "doc_path": "/Safari/Safari reading 2026-10-25"},
                         "a relative file_url resolves on the Hub")
        self.assertEqual([c["argv"][1] for c in self.rmapi_calls()], ["mkdir", "put"])

    def test_tablet_send_without_rmapi(self):
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs.append(tablet_packet("tab-3", fake.url + FILE_PATH))
            summary, _ = self.run_gate(fake, RMAPI_BIN=str(self.bin / "no-such-rmapi"))
        self.assertEqual(fake.results()[0]["body"], {"error": "rmapi not found"})
        self.assertEqual((summary["count"], summary["posted"], summary["failed_steps"]), (0, 1, 1))

    def test_tablet_send_with_rmapi_not_paired(self):
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs.append(tablet_packet("tab-4", fake.url + FILE_PATH))
            self.run_gate(fake, FAKE_RMAPI_MODE="not-paired")
        self.assertEqual(fake.results()[0]["body"], {"error": "rmapi not paired"})
        self.assertEqual(len(self.rmapi_calls()), 1, "stops at the first call")

    def test_tablet_send_upload_failure(self):
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs.append(tablet_packet("tab-5", fake.url + FILE_PATH))
            self.run_gate(fake, FAKE_RMAPI_MODE="put-fails")
        self.assertEqual(fake.results()[0]["body"], {"error": "upload failed: put: entry already exists"})

    def test_tablet_send_refuses_a_file_url_off_the_hub(self):
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs.append(tablet_packet("tab-6", "https://example.com" + FILE_PATH))
            self.run_gate(fake)
        self.assertEqual(fake.results()[0]["body"], {"error": "file_url is not on the Hub"})
        self.assertEqual(self.rmapi_calls(), [])

    def test_tablet_send_rmapi_bin_read_from_env_file(self):
        (self.home / ".env").write_text(f"RMAPI_BIN={self.bin / 'rmapi'}\n")
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs.append(tablet_packet("tab-env", FILE_PATH))
            self.run_gate(fake, RMAPI_BIN="", PATH="/usr/bin:/bin")
        self.assertTrue(fake.results()[0]["body"]["ok"])
        self.assertEqual(self.rmapi_calls()[-1]["argv"][1], "put")

    def test_tablet_send_redirect_off_the_hub_drops_the_key(self):
        with FakeHub(files={"/blob.pdf": PDF}) as blob, FakeHub(key=KEY) as fake:
            blob_url = blob.url.replace("127.0.0.1", "localhost") + "/blob.pdf"
            fake.redirects[FILE_PATH] = blob_url
            fake.jobs.append(tablet_packet("tab-redir", FILE_PATH))
            self.run_gate(fake)
        self.assertTrue(fake.results()[0]["body"]["ok"])
        self.assertEqual([r["_auth"] for r in blob.requests], [None])

    def test_tablet_send_download_failure(self):
        with FakeHub(key=KEY) as fake:
            fake.jobs.append(tablet_packet("tab-7", fake.url + "/missing.pdf"))
            self.run_gate(fake)
        self.assertEqual(fake.results()[0]["body"], {"error": "download failed: HTTP 404"})
        self.assertEqual(self.rmapi_calls(), [])

    def test_tablet_send_bad_filename_is_a_malformed_packet(self):
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs.append(tablet_packet("tab-8", FILE_PATH, filename="notes.sh"))
            self.run_gate(fake)
        self.assertIn("malformed task packet", fake.results()[0]["body"]["error"])
        self.assertEqual(self.rmapi_calls(), [])

    def test_tablet_send_then_a_claude_job_in_one_tick(self):
        with FakeHub(key=KEY, files={FILE_PATH: PDF}) as fake:
            fake.jobs += [tablet_packet("tab-9", FILE_PATH), packet("run-after", ["after tablet"])]
            summary, _ = self.run_gate(fake)
        bodies = [r["body"] for r in fake.results()]
        self.assertEqual(summary["posted"], 2)
        self.assertTrue(bodies[0]["ok"])
        self.assertEqual(json.loads(bodies[1]["outputs"][0]["text"]), {"echo": "after tablet"})
        self.assertEqual(len(self.claude_calls()), 1)

    def write_doc(self) -> str:
        path = pathlib.Path(self.tmp.name) / "doc.rmdoc"
        import rm_fixtures
        path.write_bytes(rm_fixtures.build_rmdoc())
        return str(path)

    def test_tablet_pull_unchanged_downloads_nothing(self):
        with FakeHub(key=KEY) as fake:
            fake.jobs.append(pull_packet(since="2026-10-25T15:00:00Z"))
            summary, _ = self.run_gate(fake)
        self.assertEqual(fake.results()[0]["body"],
                         {"ok": True, "unchanged": True, "doc_version": "2026-10-25T15:00:00Z"})
        self.assertEqual([c["argv"] for c in self.rmapi_calls()], [["-ni", "stat", DOC_PATH]])
        self.assertEqual(fake.uploads, [])
        self.assertEqual((summary["posted"], summary["failed_steps"]), (1, 0))
        self.assertEqual(self.claude_calls(), [])

    @NEEDS_RMSCENE
    def test_tablet_pull_reads_highlights_and_sends_handwritten_pages(self):
        doc = self.write_doc()
        with FakeHub(key=KEY) as fake:
            fake.jobs.append(pull_packet(since="2026-10-24T09:00:00Z"))
            summary, proc = self.run_gate(fake, FAKE_RMAPI_DOC=doc)
        import rm_fixtures
        calls = self.rmapi_calls()
        self.assertEqual([c["argv"][1:] for c in calls], [["stat", DOC_PATH], ["get", DOC_PATH]])
        self.assertTrue(calls[1]["cwd"].startswith(tempfile.gettempdir()) or "vcl-runner-pull-" in calls[1]["cwd"])
        self.assertFalse(pathlib.Path(calls[1]["cwd"]).exists(), "the download is cleaned up")

        paths = [u["path"] for u in fake.uploads]
        self.assertEqual(paths, [f"{PULL_BASE}/document", f"{PULL_BASE}/pages?page=2&inserted=0",
                                 f"{PULL_BASE}/pages?page=2&inserted=1"],
                         "the PDF once, then each page with handwriting; the deleted page is left out")
        self.assertEqual(fake.uploads[0]["data"], rm_fixtures.PDF_BYTES)
        self.assertEqual(fake.uploads[0]["type"], "application/pdf")
        for u in fake.uploads:
            self.assertEqual(u["_auth"], f"Bearer {KEY}")
        page2 = fake.uploads[1]["data"]
        self.assertEqual(fake.uploads[1]["type"], "image/png")
        self.assertEqual(png_size(page2), (1404, 1872))
        self.assertEqual(png_alpha(page2, 702 - 525, 400), 255, "a pen stroke at x=-525, y=400 is ink")
        self.assertEqual(png_alpha(page2, 702, 900), annotations.HIGHLIGHT_ALPHA, "a highlighter is a wash")
        self.assertEqual(png_alpha(page2, 702, 1500), 0, "the rest of the page is clear")

        body = fake.results()[0]["body"]
        self.assertEqual(body["doc_version"], "2026-10-25T15:00:00Z")
        self.assertEqual(body["highlights"], [
            {"page": 1, "inserted": 0, "text": rm_fixtures.HIGHLIGHT_1, "color": 3},
            {"page": 1, "inserted": 0, "text": rm_fixtures.HIGHLIGHT_2, "color": 3},
            {"page": 1, "inserted": 0, "text": rm_fixtures.LEGACY_HIGHLIGHT, "color": 3},
        ])
        self.assertEqual([(p["page"], p["inserted"], p["status"]) for p in body["pages"]],
                         [(2, 0, "imported"), (2, 1, "imported")])
        self.assertEqual(body["pages"][0]["hash"], annotations.page_hash(page2))
        self.assertEqual((summary["posted"], summary["failed_steps"]), (1, 0))
        self.assertEqual(self.claude_calls(), [], "a pull never calls claude")
        for call in calls:
            self.assertNotIn(KEY, json.dumps(call))
        self.assertNotIn(KEY, proc.stdout + proc.stderr)

    @NEEDS_RMSCENE
    def test_tablet_pull_without_since_always_reads(self):
        doc = self.write_doc()
        with FakeHub(key=KEY) as fake:
            fake.jobs.append(pull_packet(since=None))
            self.run_gate(fake, FAKE_RMAPI_DOC=doc)
        self.assertEqual([c["argv"][1] for c in self.rmapi_calls()], ["stat", "get"])
        self.assertEqual(len(fake.results()[0]["body"]["highlights"]), 3)

    @NEEDS_RMSCENE
    def test_tablet_pull_skips_pages_the_hub_already_has(self):
        doc = self.write_doc()
        with FakeHub(key=KEY) as fake:
            fake.jobs.append(pull_packet())
            self.run_gate(fake, FAKE_RMAPI_DOC=doc)
            hashes = {f"{p['page']}" + (f"+{p['inserted']}" if p["inserted"] else ""): p["hash"]
                      for p in fake.results()[0]["body"]["pages"]}
            fake.uploads.clear()
            fake.requests.clear()
            fake.jobs.append(pull_packet(known=hashes))
            self.run_gate(fake, FAKE_RMAPI_DOC=doc)
        self.assertEqual(fake.uploads, [], "no page and no PDF when every page is already on the Hub")
        self.assertEqual([p["status"] for p in fake.results()[0]["body"]["pages"]], ["known", "known"])

    @NEEDS_RMSCENE
    def test_tablet_pull_stops_when_the_hub_refuses_a_page(self):
        doc = self.write_doc()
        with FakeHub(key=KEY, upload_status={f"{PULL_BASE}/pages": 409}) as fake:
            fake.jobs.append(pull_packet())
            self.run_gate(fake, FAKE_RMAPI_DOC=doc)
        self.assertEqual(fake.results()[0]["body"], {"error": "the Hub refused page 2 (HTTP 409)"})
        self.assertEqual(len([u for u in fake.uploads if "/pages" in u["path"]]), 1)

    @NEEDS_RMSCENE
    def test_tablet_pull_reports_a_page_the_hub_could_not_read(self):
        doc = self.write_doc()
        with FakeHub(key=KEY, upload_status={f"{PULL_BASE}/pages?page=2&inserted=0": 502}) as fake:
            fake.jobs.append(pull_packet())
            self.run_gate(fake, FAKE_RMAPI_DOC=doc)
        pages = fake.results()[0]["body"]["pages"]
        self.assertEqual([p["status"] for p in pages], ["HTTP 502", "imported"], "one bad page does not stop the rest")

    def test_tablet_pull_without_rmscene_posts_a_clear_error(self):
        shadow = pathlib.Path(self.tmp.name) / "shadow"
        (shadow / "rmscene").mkdir(parents=True)
        (shadow / "rmscene" / "__init__.py").write_text("raise ImportError('simulated: not installed')\n")
        doc = pathlib.Path(self.tmp.name) / "doc.rmdoc"
        doc.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
        with FakeHub(key=KEY) as fake:
            fake.jobs.append(pull_packet())
            summary, _ = self.run_gate(fake, FAKE_RMAPI_DOC=str(doc), PYTHONPATH=str(shadow))
        self.assertEqual(fake.results()[0]["body"],
                         {"error": "pull failed: rmscene not installed: pip install 'rmscene>=0.6,<1' on the BehalfBot"})
        self.assertEqual(summary["count"], 0, "the Hub shows it on the send; the heartbeat stays quiet")

    def test_tablet_pull_with_rmapi_not_paired(self):
        with FakeHub(key=KEY) as fake:
            fake.jobs.append(pull_packet())
            self.run_gate(fake, FAKE_RMAPI_MODE="not-paired")
        self.assertEqual(fake.results()[0]["body"], {"error": "rmapi not paired"})

    def test_tablet_pull_of_a_document_that_is_gone(self):
        with FakeHub(key=KEY) as fake:
            fake.jobs.append(pull_packet())
            self.run_gate(fake, FAKE_RMAPI_MODE="no-doc")
        self.assertEqual(fake.results()[0]["body"], {"error": "pull failed: stat: file doesn't exist"})
        self.assertEqual(len(self.rmapi_calls()), 1)

    def test_tablet_pull_without_rmapi(self):
        with FakeHub(key=KEY) as fake:
            fake.jobs.append(pull_packet())
            self.run_gate(fake, RMAPI_BIN=str(self.bin / "no-such-rmapi"))
        self.assertEqual(fake.results()[0]["body"], {"error": "rmapi not found"})

    @NEEDS_RMSCENE
    def test_tablet_pull_never_sends_the_key_off_the_hub(self):
        doc = self.write_doc()
        with FakeHub() as other, FakeHub(key=KEY) as fake:
            off = other.url.replace("127.0.0.1", "localhost")
            p = pull_packet()
            p["tablet"]["pages_url"] = off + "/api/founder-os/agent/tablet-pulls/pull-1/pages"
            p["tablet"]["document_url"] = off + "/api/founder-os/agent/tablet-pulls/pull-1/document"
            fake.jobs.append(p)
            self.run_gate(fake, FAKE_RMAPI_DOC=doc)
        self.assertEqual(other.requests, [])
        self.assertEqual({p["status"] for p in fake.results()[0]["body"]["pages"]}, {"upload url is not on the Hub"})

    def test_tablet_pull_bad_doc_path_is_a_malformed_packet(self):
        with FakeHub(key=KEY) as fake:
            p = pull_packet()
            p["tablet"]["doc_path"] = "../etc/passwd"
            fake.jobs.append(p)
            self.run_gate(fake)
        self.assertIn("malformed task packet", fake.results()[0]["body"]["error"])
        self.assertEqual(self.rmapi_calls(), [])

    def test_204_is_a_quiet_no_op(self):
        with FakeHub([], key=KEY) as fake:
            summary, _ = self.run_gate(fake)
        self.assertEqual(summary["count"], 0)
        self.assertEqual(summary["jobs"], 0)
        self.assertEqual(summary["reason"], "nothing queued")
        self.assertEqual([r["method"] for r in fake.requests], ["GET"])
        self.assertEqual(fake.requests[0]["_auth"], f"Bearer {KEY}")
        self.assertTrue(fake.requests[0]["_ua"].startswith("behalfbot-vcl-runner/"))
        self.assertEqual(self.claude_calls(), [])

    def test_multi_step_packet_posts_every_output_in_order(self):
        job = packet("run-1", ["first chunk text", "second chunk text", "third chunk text"],
                     model="claude-sonnet-4-5", phase="chunks")
        with FakeHub([job], key=KEY) as fake:
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

    def test_each_output_carries_what_claude_says_it_used(self):
        with FakeHub([packet("run-u", ["one", "two"], model="claude-sonnet-5-5")], key=KEY) as fake:
            self.run_gate(fake)
        outputs = fake.results()[0]["body"]["outputs"]
        self.assertEqual(len(outputs), 2)
        for out in outputs:
            self.assertEqual(out["usage"], {"input_tokens": 1210, "output_tokens": 3420, "cache_read_tokens": 600,
                                            "cache_creation_tokens": 2900, "cost_usd": 0.123456,
                                            "models": ["claude-haiku-5-5", "claude-sonnet-5-5"]})

    def test_usage_block_is_read_when_model_usage_is_missing(self):
        with FakeHub([packet("run-l", ["one"])], key=KEY) as fake:
            self.run_gate(fake, mode="usage-legacy")
        self.assertEqual(fake.results()[0]["body"]["outputs"][0]["usage"],
                         {"input_tokens": 7, "output_tokens": 9, "cache_read_tokens": 3,
                          "cache_creation_tokens": 5, "cost_usd": None, "models": []})

    def test_no_usage_in_the_json_sends_no_usage(self):
        with FakeHub([packet("run-n", ["one"])], key=KEY) as fake:
            self.run_gate(fake, mode="no-usage")
        self.assertNotIn("usage", fake.results()[0]["body"]["outputs"][0])

    def test_model_null_omits_the_flag(self):
        with FakeHub([packet("run-2", ["only"], model=None)], key=KEY) as fake:
            self.run_gate(fake)
        self.assertNotIn("--model", self.claude_calls()[0]["argv"])

    def test_claude_failure_posts_an_error(self):
        job = packet("run-3", ["first ok", "second breaks", "never run"])
        with FakeHub([job], key=KEY) as fake:
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
        with FakeHub([packet("run-4", ["x"])], key=KEY) as fake:
            self.run_gate(fake, mode="is_error")
        self.assertIn("error_during_execution", fake.results()[0]["body"]["error"])

    def test_real_error_in_stdout_json_beats_stderr_noise(self):
        # The 2026-10-21 prod failure: exit 1, only noise on stderr, the cause in stdout JSON.
        with FakeHub([packet("run-404", ["x", "never run"], model="claude-sonnet-5-5")], key=KEY) as fake:
            summary, proc = self.run_gate(fake, mode="model-404")
        error = fake.results()[0]["body"]["error"]
        self.assertIn("claude exited 1: API error 404: There's an issue with the selected model", error)
        self.assertNotIn("unrecognized_model", error)
        self.assertNotIn("Advisor disabled", error)
        self.assertEqual(len(self.claude_calls()), 1, "a 404 is not transient, no retry")
        self.assertNotIn("retrying", proc.stderr)

    def test_noise_alone_on_stderr_is_not_the_error(self):
        with FakeHub([packet("run-garbled", ["x"])], key=KEY) as fake:
            self.run_gate(fake, mode="garbled-once")
        body = fake.results()[0]["body"]
        self.assertNotIn("error", body, "an unparseable failure is retried and the retry succeeded")
        self.assertEqual(len(self.claude_calls()), 2)

    def test_noisy_stderr_on_success_is_ignored(self):
        with FakeHub([packet("run-noisy", ["a", "b"])], key=KEY) as fake:
            self.run_gate(fake, mode="ok-noisy")
        self.assertEqual([o["key"] for o in fake.results()[0]["body"]["outputs"]], ["chunk-0", "chunk-1"])

    def test_transient_failure_is_retried_once_and_succeeds(self):
        job = packet("run-529", ["first", "second"])
        with FakeHub([job], key=KEY) as fake:
            summary, proc = self.run_gate(fake, mode="overloaded-once")
        body = fake.results()[0]["body"]
        self.assertNotIn("error", body)
        self.assertEqual([o["key"] for o in body["outputs"]], ["chunk-0", "chunk-1"])
        self.assertEqual([c["stdin"] for c in self.claude_calls()], ["first", "first", "second"])
        self.assertEqual(summary["failed_steps"], 0)
        self.assertIn("step chunk-0 failed, retrying once", proc.stderr)
        first = body["outputs"][0]["usage"]
        self.assertEqual(first["input_tokens"], 1310, "the failed attempt's tokens count too")
        self.assertEqual(first["cost_usd"], 0.133456)
        self.assertEqual(body["outputs"][1]["usage"]["input_tokens"], 1210)

    def test_transient_failure_is_retried_only_once(self):
        with FakeHub([packet("run-529s", ["x"])], key=KEY) as fake:
            self.run_gate(fake, mode="overloaded-always")
        self.assertIn("API error 529: API Error: 529 Overloaded", fake.results()[0]["body"]["error"])
        self.assertEqual(len(self.claude_calls()), 2)

    def test_auth_failure_is_not_retried(self):
        with FakeHub([packet("run-401", ["x"])], key=KEY) as fake:
            self.run_gate(fake, mode="auth")
        self.assertIn("API error 401: Invalid API key", fake.results()[0]["body"]["error"])
        self.assertEqual(len(self.claude_calls()), 1)

    def test_retry_skipped_when_the_step_budget_cannot_fit_it(self):
        with FakeHub([packet("run-tight", ["x"])], key=KEY) as fake:
            self.run_gate(fake, mode="overloaded-always", FOUNDER_OS_RUNNER_RETRY_BACKOFF="295")
        self.assertIn("529", fake.results()[0]["body"]["error"])
        self.assertEqual(len(self.claude_calls()), 1, "300s step timeout minus 295s backoff is under the floor")

    def test_409_is_dropped_quietly_and_the_tick_continues(self):
        jobs = [packet("lost", ["a"]), packet("kept", ["b"], kind="job_b", phase="analysis")]
        with FakeHub(jobs, key=KEY, result_status={"lost": 409}) as fake:
            summary, proc = self.run_gate(fake)
        self.assertEqual((summary["count"], summary["jobs"], summary["posted"], summary["dropped"]), (0, 2, 1, 1))
        self.assertFalse(summary.get("error"))
        paths = [r["path"] for r in fake.results()]
        self.assertEqual(paths, ["/api/founder-os/agent/jobs/lost/result", "/api/founder-os/agent/jobs/kept/result"],
                         "one POST per job, no retry of the 409")
        self.assertIn("job lost: HTTP 409, dropped", proc.stderr)

    def test_at_most_three_jobs_per_tick(self):
        jobs = [packet(f"j{i}", ["p"]) for i in range(5)]
        with FakeHub(jobs, key=KEY) as fake:
            summary, _ = self.run_gate(fake)
        self.assertEqual(summary["jobs"], 3)
        self.assertEqual(len(fake.jobs), 2, "two jobs left queued for the next tick")
        self.assertEqual(sum(1 for r in fake.requests if r["method"] == "GET"), 3)

    def test_lease_near_posts_error_and_stops_the_tick(self):
        jobs = [packet("late", ["a"], lease_minutes=0.5), packet("next", ["b"])]
        with FakeHub(jobs, key=KEY) as fake:
            summary, _ = self.run_gate(fake)
        self.assertEqual(summary["jobs"], 1)
        self.assertIn("lease deadline", summary["reason"])
        self.assertIn("lease deadline reached before step chunk-0", fake.results()[0]["body"]["error"])
        self.assertEqual(self.claude_calls(), [])
        self.assertEqual(len(fake.jobs), 1, "the second job is not claimed")

    def test_rejected_key_alerts(self):
        with FakeHub([packet("x", ["a"])], key="vcl_fos_someoneElsesKey0000000000") as fake:
            summary, _ = self.run_gate(fake)
        self.assertEqual(summary["count"], 1)
        self.assertIn("rejected the agent key", summary["reason"])
        self.assertEqual(fake.results(), [])

    def test_missing_claude_is_not_retried(self):
        with FakeHub([packet("x", ["a"])], key=KEY) as fake:
            _, proc = self.run_gate(fake, FOUNDER_OS_RUNNER_CLAUDE=str(self.bin / "no-such-claude"))
        self.assertNotIn("retrying", proc.stderr)

    def test_missing_claude_alerts_and_posts_error(self):
        with FakeHub([packet("x", ["a"]), packet("y", ["b"])], key=KEY) as fake:
            summary, _ = self.run_gate(fake, FOUNDER_OS_RUNNER_CLAUDE=str(self.bin / "no-such-claude"))
        self.assertEqual(summary["count"], 1)
        self.assertIn("claude CLI not found", summary["reason"])
        self.assertIn("claude CLI not found", fake.results()[0]["body"]["error"])
        self.assertEqual(len(fake.jobs), 1)

    def test_unreachable_hub_is_not_an_alert(self):
        with FakeHub([], key=KEY) as fake:
            url = fake.url
        env = {"FOUNDER_OS_AGENT_BASE_URL": url}
        with FakeHub([], key=KEY) as other:
            summary, _ = self.run_gate(other, **env)
        self.assertEqual(summary["count"], 0)
        self.assertTrue(summary["error"])
        self.assertIn("Hub unreachable", summary["reason"])

    def test_no_key_is_a_quiet_no_op(self):
        with FakeHub([packet("x", ["a"])], key=KEY) as fake:
            summary, _ = self.run_gate(fake, FOUNDER_OS_AGENT_KEY="")
        self.assertEqual(summary["count"], 0)
        self.assertIn("runner setup", summary["reason"])
        self.assertEqual(fake.requests, [])

    def test_key_read_from_env_file_when_not_exported(self):
        # What the dispatcher leaves behind: .env sourced without set -a.
        with FakeHub([packet("from-file", ["a"])], key=KEY) as fake:
            (self.home / ".env").write_text(f"OTHER=1\nexport FOUNDER_OS_AGENT_KEY={KEY}\n"
                                            f"FOUNDER_OS_AGENT_BASE_URL={fake.url}\n")
            summary, proc = self.run_gate(fake, FOUNDER_OS_AGENT_KEY="", FOUNDER_OS_AGENT_BASE_URL="")
        self.assertEqual((summary["count"], summary["posted"]), (0, 1))
        self.assertEqual(fake.requests[0]["_auth"], f"Bearer {KEY}")
        self.assertNotIn(KEY, proc.stdout + proc.stderr)

    def test_env_baked_wins_over_env(self):
        with FakeHub([packet("baked", ["a"])], key=KEY) as fake:
            (self.home / ".env").write_text("FOUNDER_OS_AGENT_KEY=vcl_fos_staleStaleStaleStale000000\n")
            (self.home / ".env.baked").write_text(f"FOUNDER_OS_AGENT_KEY={KEY}\n")
            summary, _ = self.run_gate(fake, FOUNDER_OS_AGENT_KEY="")
        self.assertEqual(summary["posted"], 1)

    def test_plain_http_refused_off_localhost(self):
        with FakeHub([], key=KEY) as fake:
            summary, _ = self.run_gate(fake, FOUNDER_OS_AGENT_BASE_URL="http://example.com")
        self.assertEqual(summary["count"], 1)
        self.assertIn("https", summary["reason"])

    def test_key_never_appears_in_logs_or_claude(self):
        jobs = [packet("a", ["one", "second two"]), packet("b", ["three"])]
        outputs = []
        bodies = []
        with FakeHub(jobs, key=KEY, result_status={"b": 409}) as fake:
            _, proc = self.run_gate(fake, mode="fail-second")
            outputs += [proc.stdout, proc.stderr]
            bodies += [r["body"] for r in fake.results()]
        with FakeHub([packet("c", ["x"])], key="vcl_fos_differentKey00000000000000") as fake:
            _, proc = self.run_gate(fake)
            outputs += [proc.stdout, proc.stderr]
        self.assertEqual(len(bodies), 2, "both jobs posted, one with an error")
        self.assertTrue(self.claude_calls(), "claude was exercised")
        outputs += [json.dumps(call) for call in self.claude_calls()]
        outputs += [json.dumps(body) for body in bodies]
        for text in outputs:
            self.assertNotIn(KEY, text)
            self.assertNotIn("TESTKEY0123456789", text, "not even a fragment of the key")


class AnnotationsTest(unittest.TestCase):
    def test_render_is_deterministic_and_grows_for_writing_below_the_page(self):
        strokes = [annotations.Stroke([(-100.0, 100.0), (100.0, 2100.0)])]
        png = annotations.render_page(strokes)
        self.assertEqual(png, annotations.render_page(strokes), "the same ink hashes the same")
        self.assertEqual(png_size(png), (1404, 2108))
        self.assertEqual(png_alpha(png, 702 - 100, 100), 255)

    def test_render_caps_the_height(self):
        png = annotations.render_page([annotations.Stroke([(0.0, 0.0), (0.0, 99999.0)])])
        self.assertEqual(png_size(png), (1404, annotations.MAX_HEIGHT))

    def test_doc_version_reads_modified_client(self):
        self.assertEqual(doc_version('{"ModifiedClient": "2026-10-25T15:00:00Z"}'), "2026-10-25T15:00:00Z")
        self.assertIsNone(doc_version("not json"))
        self.assertIsNone(doc_version('{"ModifiedClient": ""}'))

    def test_page_order_from_both_content_formats(self):
        v2 = {"cPages": {"pages": [
            {"id": "b", "idx": {"value": "bb"}, "redir": {"value": 1}},
            {"id": "a", "idx": {"value": "ba"}, "redir": {"value": 0}},
            {"id": "x", "idx": {"value": "bc"}},
            {"id": "d", "idx": {"value": "bd"}, "redir": {"value": 2}, "deleted": {"value": 1}}]}}
        self.assertEqual(annotations._page_order(v2), [("a", 0), ("b", 1), ("x", None)])
        v1 = {"pages": ["a", "b", "x"], "redirectionPageMap": [0, 1, -1]}
        self.assertEqual(annotations._page_order(v1), [("a", 0), ("b", 1), ("x", None)])

    def test_a_zip_with_an_escaping_path_is_not_read(self):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../evil.content", "{}")
        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf:
            self.assertEqual(annotations._safe_members(zf), {})

    @NEEDS_RMSCENE
    def test_read_document_maps_pages(self):
        import rm_fixtures
        path = pathlib.Path(tempfile.mkdtemp()) / "doc.rmdoc"
        path.write_bytes(rm_fixtures.build_rmdoc())
        doc = annotations.read_document(str(path))
        self.assertEqual([(p.key, len(p.highlights), len(p.strokes)) for p in doc.pages],
                         [("1", 3, 0), ("2", 0, 3), ("2+1", 0, 1)])
        self.assertEqual([s.highlighter for s in doc.pages[1].strokes], [False, False, True])
        self.assertEqual(doc.pdf, rm_fixtures.PDF_BYTES)


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
        return subprocess.run([sys.executable, str(CLI), "setup", *args], input=stdin,
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

    def test_setup_keeps_an_export_prefix(self):
        (self.home / ".env").write_text("export FOUNDER_OS_AGENT_KEY=vcl_fos_oldoldoldoldoldold\n")
        proc = self.setup_cli(KEY + "\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.home / ".env").read_text(), f"export FOUNDER_OS_AGENT_KEY={KEY}\n")

    def test_setup_accepts_the_hub_key_shape(self):
        # VCL mints vcl_fos_ + 43 base64url characters (extension-keys.ts).
        hub_key = "vcl_fos_" + "Ab9_-" * 8 + "xyz"
        self.assertEqual(len(hub_key), len("vcl_fos_") + 43)
        proc = self.setup_cli(hub_key + "\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)

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
