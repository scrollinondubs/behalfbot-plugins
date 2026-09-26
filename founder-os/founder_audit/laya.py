"""Client for a Laya server over the TypeSafe-shaped /v1/systemone endpoint.

laya-serve and Ollaya both speak it: POST {"state", "questions", "model"} and
get back {"model", "answers", "usage", "routing"}. Stdlib only.

    LAYA_URL      base URL, e.g. http://laya:8000 (the chassis compose service)
    LAYA_API_KEY  optional bearer token, sent only when set
    LAYA_TIMEOUT  seconds per request, default 20. A cold checkpoint load takes
                  a few seconds, so keep this well above one warm call.

Failures split in two. LayaUnavailable means the server cannot answer right
now (not configured, unreachable, timed out, 5xx, garbage body): the auditors
catch it and fall back to a Claude-only audit. LayaRequestError means the
server understood the request and refused it (4xx): that is a bug in a
question set or in the chunking, and it is raised, not papered over.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any

DEFAULT_TIMEOUT = 20.0
USER_AGENT = "behalfbot-founder-os/0.2"
# Per-question token window of each checkpoint, including the question head.
# Laya cuts the state's tail past it without saying so.
CHECKPOINT_MAX_TOKENS = {"english": 512, "multilingual": 1024, "typed-decisions": 1024}


class LayaUnavailable(RuntimeError):
    """Laya cannot answer right now. Degrade to a Claude-only audit."""


class LayaRequestError(RuntimeError):
    """Laya rejected the request. A bug on our side; do not degrade silently."""


class LayaClient:
    def __init__(self, url: str | None = None, *, api_key: str | None = None,
                 timeout: float | None = None) -> None:
        raw_url = url if url is not None else os.environ.get("LAYA_URL", "")
        self.url = raw_url.strip().rstrip("/")
        self.api_key = api_key if api_key is not None else (os.environ.get("LAYA_API_KEY") or None)
        if timeout is None:
            try:
                timeout = float(os.environ.get("LAYA_TIMEOUT", DEFAULT_TIMEOUT))
            except ValueError:
                timeout = DEFAULT_TIMEOUT
        self.timeout = timeout
        # Set on the first unavailability, so a run over 40 turns waits for one
        # timeout rather than 40.
        self.down_reason: str | None = None if self.url else "LAYA_URL is not set"

    @property
    def configured(self) -> bool:
        return bool(self.url)

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        if self.down_reason:
            raise LayaUnavailable(self.down_reason)
        headers = {"User-Agent": USER_AGENT}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        req = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            if 400 <= e.code < 500:
                raise LayaRequestError(f"laya {path} answered {e.code}: {detail}") from e
            self.down_reason = f"laya {path} answered {e.code}"
            raise LayaUnavailable(self.down_reason) from e
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
            self.down_reason = f"laya unreachable at {self.url}: {getattr(e, 'reason', e)}"
            raise LayaUnavailable(self.down_reason) from e
        try:
            parsed = json.loads(raw)
        except ValueError as e:
            self.down_reason = f"laya {path} returned a body that is not JSON"
            raise LayaUnavailable(self.down_reason) from e
        if not isinstance(parsed, dict):
            self.down_reason = f"laya {path} returned {type(parsed).__name__}, not an object"
            raise LayaUnavailable(self.down_reason)
        return parsed

    def health(self) -> dict:
        return self._request("GET", "/health")

    def systemone(self, state: Any, questions: dict, *, model: str | None = None) -> dict:
        """One decision call. Returns the parsed body; `answers` is guaranteed
        to hold every question asked."""
        body: dict[str, Any] = {"state": state, "questions": questions}
        if model:
            body["model"] = model
        result = self._request("POST", "/v1/systemone", body)
        answers = result.get("answers")
        if not isinstance(answers, dict) or any(q not in answers for q in questions):
            self.down_reason = "laya returned answers that do not cover the questions asked"
            raise LayaUnavailable(self.down_reason)
        return result
