"""fake_vcl.py - a scripted stand-in for the Hub's agent job routes.

A real HTTP server on 127.0.0.1, so the runner's sockets, status handling and
headers are exercised for real. `jobs` is the queue GET jobs/next serves, one
packet per call, then 204. `result_status` maps a job id to the status its
result POST gets (200 by default). Every request is recorded with its
Authorization header and parsed body.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NEXT = "/api/founder-os/agent/jobs/next"
RESULT_PREFIX = "/api/founder-os/agent/jobs/"


class FakeVCL:
    def __init__(self, jobs=None, *, key="", result_status=None, next_status=None):
        self.jobs = list(jobs or [])
        self.key = key
        self.result_status = dict(result_status or {})
        self.next_status = next_status
        self.requests: list[dict] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status, body=None):
                raw = b"" if body is None else json.dumps(body).encode("utf-8")
                self.send_response(status)
                if raw:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _record(self, body=None):
                fake.requests.append({"method": self.command, "path": self.path, "body": body,
                                      "_auth": self.headers.get("Authorization"),
                                      "_ua": self.headers.get("User-Agent")})

            def _authorised(self):
                return not fake.key or self.headers.get("Authorization") == f"Bearer {fake.key}"

            def do_GET(self):
                self._record()
                if self.path != NEXT:
                    return self._send(404, {"error": "not found"})
                if not self._authorised():
                    return self._send(401, {"error": "bad key"})
                if fake.next_status:
                    return self._send(fake.next_status, {"error": "scripted"})
                if not fake.jobs:
                    return self._send(204)
                return self._send(200, fake.jobs.pop(0))

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"null")
                self._record(body)
                if not (self.path.startswith(RESULT_PREFIX) and self.path.endswith("/result")):
                    return self._send(404, {"error": "not found"})
                if not self._authorised():
                    return self._send(401, {"error": "bad key"})
                job_id = self.path[len(RESULT_PREFIX):-len("/result")]
                status = fake.result_status.get(job_id, 200)
                if status == 200:
                    return self._send(200, {"status": "failed" if "error" in body else "done"})
                return self._send(status, {"error": "scripted"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def results(self) -> list[dict]:
        return [r for r in self.requests if r["method"] == "POST"]

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
