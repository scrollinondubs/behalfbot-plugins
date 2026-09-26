"""Opt-in progress webhook: stage and gate status, back to a cohort instructor.

Off unless both FOUNDER_OS_PROGRESS_WEBHOOK_URL and
FOUNDER_OS_PROGRESS_WEBHOOK_SECRET are set, which only happens when the operator
configures them. The body is exactly three fields and nothing else. Each POST is
signed with HMAC-SHA256 over "<timestamp>.<body>" so the instructor can reject
forged and replayed reports. See "Progress webhook" in docs/bundle-format.md
for the privacy boundary and how a receiver verifies a request.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request

from founder_ledger.interface import Ledger, NotFound

ENV_URL = "FOUNDER_OS_PROGRESS_WEBHOOK_URL"
ENV_KEY = "FOUNDER_OS_PROGRESS_WEBHOOK_SECRET"
PAYLOAD_KEYS = ("stage", "gate_status", "updated_at")
TIMESTAMP_HEADER = "X-FounderOS-Timestamp"
SIGNATURE_HEADER = "X-FounderOS-Signature"
MAX_AGE_SECONDS = 300
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
# urllib's default User-Agent is refused by Cloudflare, which fronts most
# hosted endpoints an instructor would use.
USER_AGENT = "behalfbot-founder-os-progress/1"


def progress_payload(ledger: Ledger, founder_id: str) -> dict:
    """{stage, gate_status, updated_at} for the founder's current stage."""
    founder = ledger.get_founder(founder_id)
    if founder is None:
        raise NotFound(f"no founder {founder_id!r}")
    stage = founder["current_stage"]
    row = next(r for r in ledger.list_stage_progress(founder_id) if r["stage"] == stage)
    return {"stage": stage, "gate_status": row["status"], "updated_at": row["updated_at"]}


def webhook_config() -> tuple[str, str] | None:
    """(url, key) when the webhook is configured, None when it is off. A URL
    without a signing key is a misconfiguration, not a quiet unsigned send."""
    url = os.environ.get(ENV_URL, "").strip()
    key = os.environ.get(ENV_KEY, "").strip()
    if not url:
        return None
    if not key:
        raise ValueError(f"{ENV_URL} is set but {ENV_KEY} is not; the webhook only sends signed requests")
    return url, key


def sign(key: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(key.encode("utf-8"), timestamp.encode("ascii") + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def verify(key: str, timestamp: str, body: bytes, signature: str, *,
           now: float | None = None, max_age: int = MAX_AGE_SECONDS) -> bool:
    """The receiver's check: the signature matches and the timestamp is within
    max_age seconds of now, either way. Reference for any receiver's port."""
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs((time.time() if now is None else now) - ts) > max_age:
        return False
    return hmac.compare_digest(sign(key, timestamp, body), signature or "")


def send_progress(payload: dict, url: str | None = None, key: str | None = None, *,
                  timeout: float = 10.0) -> int | None:
    """POST the signed payload to the instructor URL. Returns the HTTP status,
    or None when the webhook is off. Refuses any key outside PAYLOAD_KEYS."""
    if url is None:
        config = webhook_config()
        if config is None:
            return None
        url, key = config
    if not key:
        raise ValueError("the progress webhook needs a signing key")
    if set(payload) != set(PAYLOAD_KEYS):
        raise ValueError(f"the progress payload is exactly {', '.join(PAYLOAD_KEYS)}")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOOPBACK):
        raise ValueError("the progress webhook URL must be https (plain http only to localhost)")
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": USER_AGENT,
        TIMESTAMP_HEADER: timestamp, SIGNATURE_HEADER: sign(key, timestamp, body),
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status
