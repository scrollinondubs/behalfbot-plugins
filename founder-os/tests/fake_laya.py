"""A stand-in Laya server for the offline tests.

A real HTTP server on 127.0.0.1 speaking the /v1/systemone shape laya-serve
uses, so the tests go through the real client: sockets, timeouts, status codes
and bodies. Answers come from keyword rules, not a model. Like the real thing
it reads only the start of a long state and drops the tail, so a test can show
that chunking finds what truncation would miss.

Modes: "ok", "slow" (sleeps past any sane timeout), "error" (500),
"garbage" (200 with a body that is not JSON), "reject" (422).
"""
from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# How many state characters each checkpoint "reads" before silently dropping
# the rest, like a real token window.
WINDOW_CHARS = {"english": 1200, "multilingual": 2800, None: 2800}

RULES = {
    "compliment": r"\blove\b|great idea|sounds great|awesome",
    "hypothetical": r"\bwould\b|\bprobably\b|\bmaybe\b|\bmight\b|do you think|\bpeople\b|\beveryone\b",
    "past_behaviour": r"last (month|week|year|tuesday)|\bin (june|march)\b|\bspent\b|\bpaid\b|\bwe used\b|\bphoned\b",
    "pitching": r"we're building|our app|our tool|it will automatically",
    "commitment_time": r"book a call|next tuesday|share my screen",
    "commitment_intro": r"introduce you|put you in touch",
    "commitment_money": r"pre-?order|deposit|letter of intent|pay for the pilot",
    "has_problem": r"happens every month|nearly missed payroll|to us\b",
    "knows_problem": r"biggest operational problem|i know this",
    "searching": r"testing two|asked three|want something in place",
    "has_workaround": r"built a spreadsheet|a script|pay a bookkeeper",
    "has_budget": r"budget line|i can spend|we pay",
    "is_pain": r"frustrat|\bstuck\b|\bhate\b|breaking me",
    "money_or_workaround": r"\bswitched\b|spreadsheet|\bscript\b|\bpaid for\b|cancel",
    "pitches_product": r"invoicebot|sign up|try it|click the link",
}
SECTION_FIX = r"invoicebot|sign up|try it|click the link|\btool\b"
SECTION_PAIN = r"frustrat|\bstuck\b|lose hours|hours lost|awkward|waited"


def answer(qid: str, q: dict, state: str) -> dict:
    s = state.lower()
    if q["type"] == "noul":
        p = 0.9 if re.search(RULES.get(qid, r"(?!x)x"), s) else 0.1
        return {"type": "noul", "noul": p, "confidence": max(p, 1 - p), "answer_confidence": max(p, 1 - p)}
    if q["type"] == "choice":
        keys = list(q["criteria"]) if isinstance(q["criteria"], (dict, list)) else []
        if {"pain", "dream", "fix"} <= set(keys):
            pick = "fix" if re.search(SECTION_FIX, s) else "pain" if re.search(SECTION_PAIN, s) else "dream"
        else:
            pick = keys[0]
        rest = (1 - 0.8) / max(len(keys) - 1, 1)
        probs = {k: (0.8 if k == pick else rest) for k in keys}
        return {"type": "choice", "choice": pick, "probabilities": probs, "confidence": 0.5,
                "answer_confidence": 0.8}
    levels = len(q["criteria"])
    score = float(levels - 1) if re.search(RULES["is_pain"], s) else 0.0
    return {"type": "score", "score": score, "probabilities": {str(i): 1.0 if i == int(score) else 0.0
                                                               for i in range(levels)},
            "confidence": 0.9, "answer_confidence": 0.9}


class FakeLaya:
    def __init__(self, mode: str = "ok") -> None:
        self.mode = mode
        self.requests: list[dict] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output clean
                pass

            def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._send(200, json.dumps({"status": "ok", "loaded": ["english", "multilingual"]}).encode())

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                body["_auth"] = self.headers.get("Authorization")
                fake.requests.append(body)
                if fake.mode == "slow":
                    time.sleep(2.0)
                if fake.mode == "error":
                    return self._send(500, b'{"detail": "inference failed"}')
                if fake.mode == "garbage":
                    return self._send(200, b"<html>not json</html>", "text/html")
                if fake.mode == "reject":
                    return self._send(422, b'{"detail": "question x: unknown type"}')
                model = body.get("model")
                state = str(body.get("state") or "")[:WINDOW_CHARS.get(model, 2800)]
                answers = {qid: answer(qid, q, state) for qid, q in body["questions"].items()}
                tokens = len(state) // 4 * len(body["questions"])
                self._send(200, json.dumps({
                    "model": model or "multilingual", "answers": answers,
                    "usage": {"input_tokens": tokens, "output_tokens": 0},
                    "routing": {"model": model or "multilingual"},
                }).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeLaya":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()
