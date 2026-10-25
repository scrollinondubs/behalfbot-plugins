"""One heartbeat tick of the VCL runner.

Claims jobs from GET /api/founder-os/agent/jobs/next until it answers 204 or
three jobs are done, runs every step through `claude -p`, and posts the outputs
(or one error) to POST /api/founder-os/agent/jobs/:id/result. The HTTP contract
is section B of the agent-runner plan; the Hub owns parsing and checking. Each
output also carries the tokens and models Claude Code reported for that step,
so the Hub can show what the job would have cost on the student's API key.

The claude call is the whole of the model access. This module never reads
~/.claude, the keychain or any OAuth credential: it starts the CLI the student
already logged into and reads its stdout. ANTHROPIC_API_KEY is removed from the
child's environment so the work bills the student's Claude plan, the same
unset the chassis dispatcher does before its own `claude -p` calls, and the
agent key is removed too because the model has no use for it.

A tablet_send job has no model steps: the runner downloads the reading file the
Hub built (from the Hub's own origin, with the agent key) and uploads it to the
student's reMarkable with `rmapi`, then posts {"ok": true, "doc_path": ...} or
{"error": ...}.

A tablet_pull job has none either: the runner reads the student's marks back
off that document (`rmapi stat`, then `rmapi get` when it changed), sends the
Hub one PNG per page with handwriting and the PDF it sits on, and posts the
highlighted text with the result. annotations.py does the reading.

stdout is reserved for the one-line JSON summary the heartbeat gate prints;
every log line goes to stderr and names only the base URL, job id, kind, phase
and status codes.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from . import annotations

ENV_KEY = "FOUNDER_OS_AGENT_KEY"
ENV_BASE_URL = "FOUNDER_OS_AGENT_BASE_URL"
ENV_CLAUDE = "FOUNDER_OS_RUNNER_CLAUDE"
ENV_STEP_TIMEOUT = "FOUNDER_OS_RUNNER_STEP_TIMEOUT"
ENV_TICK_BUDGET = "FOUNDER_OS_RUNNER_TICK_BUDGET"
ENV_RETRY_BACKOFF = "FOUNDER_OS_RUNNER_RETRY_BACKOFF"
DEFAULT_BASE_URL = "https://vibecodelisboa.com"
KEY_PREFIX = "vcl_fos_"
NEXT_PATH = "/api/founder-os/agent/jobs/next"
RESULT_PATH = "/api/founder-os/agent/jobs/{id}/result"
MAX_JOBS = 3
DEFAULT_STEP_TIMEOUT = 300
DEFAULT_TICK_BUDGET = 600
# Stop starting steps this close to the lease deadline: the post has to land
# before the Hub hands the job to a later claim.
LEASE_MARGIN = 60
# One retry per step, after this pause, for a failure that looks transient.
RETRY_BACKOFF = 25
# A retry with less time than this left is not worth starting.
MIN_RETRY_TIMEOUT = 30
HTTP_TIMEOUT = 30
MAX_ERROR_CHARS = 300
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
# urllib's default User-Agent is refused by Cloudflare.
USER_AGENT = "behalfbot-vcl-runner/1"
CHILD_ENV_DROP = ("ANTHROPIC_API_KEY", ENV_KEY)
# Lines Claude Code writes to stderr on every run with a full model id, success
# included (CLI 2.1.280). Left in, they hide the real cause of a failure.
STDERR_NOISE = ("[claude-code:unrecognized_model]", "Warning: Advisor disabled")
ENV_RMAPI = "RMAPI_BIN"
TABLET_KIND = "tablet_send"
TABLET_TARGET = "remarkable"
TABLET_EXTENSIONS = (".pdf", ".epub")
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
RMAPI_TIMEOUT = 120
PULL_KIND = "tablet_pull"
# Vercel takes about 4.5 MB of request body.
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_PULL_PAGES = 40
MAX_PULL_HIGHLIGHTS = 500
# The Hub reads each handwritten page with a vision model before it answers.
UPLOAD_TIMEOUT = 150
# What rmapi -ni prints when it has no token to use.
RMAPI_UNPAIRED = ("missing token", "one-time code", "device token", "user token")
RMAPI_LOG_PREFIX = re.compile(r"^(?:(?:ERROR|WARNING|INFO|TRACE): \d{4}/\d\d/\d\d \d\d:\d\d:\d\d \S+: )?(?:Error:\s+)?")
TRANSIENT_STATUS = {408, 429}
TRANSIENT_WORDS = ("rate limit", "rate_limit", "overloaded", "timed out", "timeout", "econnreset",
                   "socket hang up", "network error", "internal server error", "service unavailable",
                   "bad gateway", "api error: 5")
PERMANENT_WORDS = ("not logged in", "/login", "authentication", "invalid api key", "unauthorized",
                   "oauth token", "credit balance")


class HubUnreachable(Exception):
    """Network failure or a 5xx: try again next tick."""


class AuthRejected(Exception):
    """401 or 403: the key is wrong, revoked or has the wrong scope."""


class StepFailed(Exception):
    """A claude call that produced no usable text. transient marks a failure
    worth one retry: rate limit, overload, a 5xx, or no parseable answer."""

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient
        self.usage: dict | None = None


class ClaudeMissing(StepFailed):
    """The claude binary is not on PATH."""


class TabletFailed(Exception):
    """A tablet_send that cannot finish. The message is the error posted."""


def log(msg: str) -> None:
    print(f"[vcl-runner] {msg}", file=sys.stderr, flush=True)


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, "") or default))
    except ValueError:
        return default


def _origin(url: str) -> tuple:
    parts = urllib.parse.urlsplit(url)
    return parts.scheme, parts.hostname, parts.port


class _KeepKeyOnHub(urllib.request.HTTPRedirectHandler):
    """urllib re-sends Authorization on every redirect. A redirect off the
    Hub's origin is followed without it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and _origin(newurl) != _origin(req.full_url):
            new.remove_header("Authorization")
        return new


class HubClient:
    def __init__(self, base_url: str, key: str, timeout: float = HTTP_TIMEOUT):
        parts = urllib.parse.urlsplit(base_url)
        if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOOPBACK):
            raise ValueError("the Hub base URL must be https (plain http only to localhost)")
        self.base_url = base_url.rstrip("/")
        self._key = key
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self._key}", "User-Agent": USER_AGENT,
                   "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read() or b""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise HubUnreachable(f"{method} {path}: {type(reason).__name__}") from None
        if status in (401, 403):
            raise AuthRejected(f"{method} {path}: HTTP {status}")
        if status >= 500:
            raise HubUnreachable(f"{method} {path}: HTTP {status}")
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
        return status, parsed if isinstance(parsed, dict) else None

    def download(self, url: str, limit: int = MAX_DOWNLOAD_BYTES) -> bytes:
        """GET a file the Hub built. Only from the Hub's own origin, because
        the agent key goes with the request."""
        url = urllib.parse.urljoin(self.base_url + "/", url)
        if _origin(url) != _origin(self.base_url):
            raise TabletFailed("file_url is not on the Hub")
        req = urllib.request.Request(url, method="GET", headers={
            "Authorization": f"Bearer {self._key}", "User-Agent": USER_AGENT, "Accept": "*/*"})
        try:
            with urllib.request.build_opener(_KeepKeyOnHub).open(req, timeout=self.timeout) as resp:
                data = resp.read(limit + 1)
        except urllib.error.HTTPError as exc:
            raise TabletFailed(f"download failed: HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise TabletFailed(f"download failed: {type(reason).__name__}") from None
        if len(data) > limit:
            raise TabletFailed("download failed: file too large")
        if not data:
            raise TabletFailed("download failed: empty file")
        return data

    def upload(self, url: str, data: bytes, content_type: str,
               timeout: float = UPLOAD_TIMEOUT) -> tuple[int, dict | None]:
        """POST a file to the Hub (a page image or the PDF of a tablet_pull).
        Only to the Hub's own origin, because the agent key goes with it. A
        401 or 403 raises AuthRejected; anything else is the caller's."""
        url = urllib.parse.urljoin(self.base_url + "/", url)
        if _origin(url) != _origin(self.base_url):
            raise TabletFailed("upload url is not on the Hub")
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"Bearer {self._key}", "User-Agent": USER_AGENT,
            "Content-Type": content_type, "Accept": "application/json"})
        try:
            with urllib.request.build_opener(_KeepKeyOnHub).open(req, timeout=timeout) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read() or b""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise TabletFailed(f"upload failed: {type(reason).__name__}") from None
        if status in (401, 403):
            raise AuthRejected(f"POST upload: HTTP {status}")
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
        return status, parsed if isinstance(parsed, dict) else None

    def next_job(self) -> dict | None:
        status, packet = self._request("GET", NEXT_PATH)
        if status == 204:
            return None
        if status != 200 or packet is None:
            raise HubUnreachable(f"GET {NEXT_PATH}: unexpected HTTP {status}")
        return packet

    def post_result(self, job_id: str, body: dict) -> tuple[int, dict | None]:
        return self._request("POST", RESULT_PATH.format(id=urllib.parse.quote(job_id, safe="")), body)


def claude_argv(claude_bin: str, system: str, model: str | None) -> list[str]:
    """The exact claude invocation. --tools "" leaves the model no built-in
    tool, --strict-mcp-config with no --mcp-config loads no MCP server,
    --setting-sources "" skips user and project settings (their hooks,
    permissions and extra tools), --disable-slash-commands drops skills, and
    --no-session-persistence keeps the student's session list clean. Not
    --bare: it never reads the OAuth login, so it would need an API key."""
    argv = [claude_bin, "-p", "--output-format", "json",
            "--tools", "", "--strict-mcp-config", "--setting-sources", "",
            "--disable-slash-commands", "--no-session-persistence",
            "--append-system-prompt", system]
    if model:
        argv += ["--model", model]
    return argv


def _short(text: str) -> str:
    text = " ".join((text or "").split())
    return text[:MAX_ERROR_CHARS]


def _strip_noise(stderr: str) -> str:
    return "\n".join(line for line in (stderr or "").splitlines()
                     if not any(line.strip().startswith(n) for n in STDERR_NOISE))


def _json_object(stdout: str) -> dict | None:
    try:
        out = json.loads(stdout or "")
    except ValueError:
        return None
    return out if isinstance(out, dict) else None


def _json_detail(out: dict) -> str:
    """The error claude put in its JSON result. subtype reads "success" even
    when is_error is set, so it is named only when it says something else."""
    parts = []
    status = out.get("api_error_status")
    if status is not None:
        parts.append(f"API error {status}")
    sub = out.get("subtype")
    if sub and sub != "success":
        parts.append(str(sub))
    head = " ".join(parts)
    text = _short(str(out.get("result") or ""))
    return f"{head}: {text}" if head and text else head or text


def _is_transient(status, text: str) -> bool:
    low = text.lower()
    if status in (401, 403) or any(w in low for w in PERMANENT_WORDS):
        return False
    if isinstance(status, int) and (status in TRANSIENT_STATUS or status >= 500):
        return True
    return any(w in low for w in TRANSIENT_WORDS)


def _json_failure(out: dict, prefix: str) -> StepFailed:
    detail = _json_detail(out)
    return StepFailed(prefix + (f": {detail}" if detail else ""),
                      transient=_is_transient(out.get("api_error_status"), detail))


def _int(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def claude_usage(out: dict) -> dict | None:
    """What one claude -p call used, from its JSON: token totals over every
    model it ran (modelUsage, else the usage block), the models, and
    total_cost_usd. The Hub prices the tokens itself; cost_usd is what Claude
    Code says the call would cost at API prices. None when the JSON has none
    of these."""
    per_model = out.get("modelUsage")
    totals = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0}
    models: list[str] = []
    if isinstance(per_model, dict) and per_model:
        for name, u in per_model.items():
            if not isinstance(u, dict):
                continue
            models.append(str(name))
            totals["input_tokens"] += _int(u.get("inputTokens"))
            totals["output_tokens"] += _int(u.get("outputTokens"))
            totals["cache_read_tokens"] += _int(u.get("cacheReadInputTokens"))
            totals["cache_creation_tokens"] += _int(u.get("cacheCreationInputTokens"))
    elif isinstance(out.get("usage"), dict):
        u = out["usage"]
        totals["input_tokens"] = _int(u.get("input_tokens"))
        totals["output_tokens"] = _int(u.get("output_tokens"))
        totals["cache_read_tokens"] = _int(u.get("cache_read_input_tokens"))
        totals["cache_creation_tokens"] = _int(u.get("cache_creation_input_tokens"))
    cost = out.get("total_cost_usd")
    cost = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0 else None
    if not models and cost is None and not any(totals.values()):
        return None
    return {**totals, "cost_usd": cost, "models": sorted(models)}


def add_usage(a: dict | None, b: dict | None) -> dict | None:
    """Two calls' usage as one: a retried step reports both attempts."""
    if a is None or b is None:
        return a or b
    costs = [c for c in (a.get("cost_usd"), b.get("cost_usd")) if c is not None]
    merged = {k: a.get(k, 0) + b.get(k, 0)
              for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens")}
    return {**merged, "cost_usd": round(sum(costs), 6) if costs else None,
            "models": sorted(set(a.get("models", [])) | set(b.get("models", [])))}


def run_claude(system: str, prompt: str, model: str | None, timeout: float, claude_bin: str) -> dict:
    """One claude -p call. Returns {"text", "usage"}; usage is None when the
    JSON carried none. A failure raises StepFailed with whatever usage the
    failed call reported on it."""
    env = {k: v for k, v in os.environ.items() if k not in CHILD_ENV_DROP}
    # An empty directory, so no CLAUDE.md from the install root rides along
    # into the student's job.
    with tempfile.TemporaryDirectory(prefix="vcl-runner-") as cwd:
        try:
            proc = subprocess.run(claude_argv(claude_bin, system, model), input=prompt, capture_output=True,
                                  text=True, timeout=timeout, cwd=cwd, env=env)
        except FileNotFoundError:
            raise ClaudeMissing(f"claude CLI not found ({claude_bin}); install Claude Code and log in") from None
        except subprocess.TimeoutExpired:
            # Not retried: it already spent the whole step timeout.
            raise StepFailed(f"claude timed out after {int(timeout)}s") from None
    out = _json_object(proc.stdout)
    if proc.returncode != 0:
        prefix = f"claude exited {proc.returncode}"
        if out is not None and (out.get("is_error") or out.get("result")):
            raise _with_usage(_json_failure(out, prefix), out)
        detail = _short(_strip_noise(proc.stderr)) or _short(proc.stdout)
        transient = not detail or _is_transient(None, detail)
        raise StepFailed(prefix + (f": {detail}" if detail else ""), transient=transient)
    if out is None:
        raise StepFailed("claude printed something other than JSON", transient=True)
    if out.get("is_error") or out.get("subtype", "success") != "success":
        sub = out.get("subtype")
        label = sub if sub and sub != "success" else "is_error"
        raise _with_usage(_json_failure(out, f"claude reported an error ({label})"), out)
    result = out.get("result")
    if not isinstance(result, str):
        raise _with_usage(StepFailed("claude returned no result text"), out)
    return {"text": result, "usage": claude_usage(out)}


def _with_usage(exc: StepFailed, out: dict) -> StepFailed:
    exc.usage = claude_usage(out)
    return exc


def _backoff() -> float:
    try:
        return max(0, int(os.environ.get(ENV_RETRY_BACKOFF, "") or RETRY_BACKOFF))
    except ValueError:
        return RETRY_BACKOFF


def _deadline(packet: dict) -> float | None:
    raw = packet.get("lease_expires_at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        when = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.timestamp()


def _packet_problem(packet: dict) -> str | None:
    if not isinstance(packet.get("id"), str) or not packet["id"]:
        return "no id"
    if not isinstance(packet.get("phase"), str):
        return "no phase"
    if not isinstance(packet.get("system"), str):
        return "no system prompt"
    steps = packet.get("steps")
    if not isinstance(steps, list) or not steps:
        return "no steps"
    for step in steps:
        if not (isinstance(step, dict) and isinstance(step.get("key"), str) and isinstance(step.get("prompt"), str)):
            return "a step without key and prompt"
    if packet.get("model") is not None and not isinstance(packet.get("model"), str):
        return "model is not a string"
    return None


def run_job(packet: dict, *, step_timeout: float, claude_bin: str,
            clock: Callable[[], float], sleep: Callable[[float], None] = time.sleep) -> tuple[dict, bool]:
    """Run every step. Returns (result body, stop_tick). stop_tick is set when
    the lease deadline cut the job short or claude is missing.

    A transient failure is retried once after the backoff, inside the same
    budget: the step's two attempts and the pause together stay within
    step_timeout and clear of the lease margin."""
    phase = packet["phase"]
    deadline = _deadline(packet)
    outputs = []
    for step in packet["steps"]:
        timeout = step_timeout
        if deadline is not None:
            left = deadline - clock() - LEASE_MARGIN
            if left <= 0:
                return {"phase": phase, "error": f"lease deadline reached before step {step['key']}"}, True
            timeout = min(timeout, left)
        step_end = clock() + timeout
        spent = None
        try:
            try:
                done = run_claude(packet["system"], step["prompt"], packet.get("model"), timeout, claude_bin)
            except ClaudeMissing:
                raise
            except StepFailed as exc:
                backoff = _backoff()
                left = step_end - clock() - backoff
                if not exc.transient or left < MIN_RETRY_TIMEOUT:
                    raise
                spent = exc.usage
                log(f"job {packet['id']}: step {step['key']} failed, retrying once in {backoff}s")
                sleep(backoff)
                done = run_claude(packet["system"], step["prompt"], packet.get("model"), left, claude_bin)
        except ClaudeMissing as exc:
            return {"phase": phase, "error": str(exc)}, True
        except StepFailed as exc:
            return {"phase": phase, "error": f"step {step['key']}: {exc}"}, False
        output = {"key": step["key"], "text": done["text"]}
        usage = add_usage(spent, done["usage"])
        if usage is not None:
            output["usage"] = usage
        outputs.append(output)
    return {"phase": phase, "outputs": outputs}, False


def _tablet_problem(packet: dict) -> str | None:
    if not isinstance(packet.get("id"), str) or not packet["id"]:
        return "no id"
    tablet = packet.get("tablet")
    if not isinstance(tablet, dict):
        return "no tablet"
    if tablet.get("target") != TABLET_TARGET:
        return f"unsupported tablet target {str(tablet.get('target'))[:32]!r}"
    for field in ("file_url", "filename", "folder"):
        if not isinstance(tablet.get(field), str) or (field != "folder" and not tablet[field]):
            return f"no tablet.{field}"
    name = posixpath.basename(tablet["filename"].replace("\\", "/")).strip()
    if name in ("", ".", "..") or not name.lower().endswith(TABLET_EXTENSIONS):
        return "tablet.filename must be a .pdf or .epub name"
    if ".." in tablet["folder"].split("/"):
        return "tablet.folder must not contain .."
    return None


def _folder_chain(folder: str) -> list[str]:
    """Every folder from the top down, so a missing parent is made first:
    /A/B -> [/A, /A/B]. The root is never made."""
    parts = [p for p in folder.split("/") if p]
    return ["/" + "/".join(parts[:i + 1]) for i in range(len(parts))]


def _rmapi_detail(text: str) -> str:
    lines = [RMAPI_LOG_PREFIX.sub("", line).strip() for line in (text or "").splitlines()]
    return _short(" ".join(line for line in lines if line))


def run_rmapi(rmapi_bin: str, args: list[str], timeout: float, *, cwd: str | None = None,
              failure: str = "upload failed") -> str:
    """One rmapi call; returns its stdout. -ni makes an unpaired rmapi exit
    instead of waiting forever for a one-time code; stdin is closed as a
    second guard. `get` writes into cwd."""
    env = {k: v for k, v in os.environ.items() if k not in CHILD_ENV_DROP}
    try:
        proc = subprocess.run([rmapi_bin, "-ni", *args], stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=timeout, env=env, cwd=cwd)
    except (FileNotFoundError, PermissionError):
        raise TabletFailed("rmapi not found") from None
    except subprocess.TimeoutExpired:
        raise TabletFailed(f"{failure}: rmapi {args[0]} timed out after {int(timeout)}s") from None
    if proc.returncode == 0:
        return proc.stdout
    text = f"{proc.stderr}\n{proc.stdout}"
    if any(marker in text.lower() for marker in RMAPI_UNPAIRED):
        raise TabletFailed("rmapi not paired")
    detail = _rmapi_detail(proc.stderr) or _rmapi_detail(proc.stdout) or f"rmapi exited {proc.returncode}"
    raise TabletFailed(f"{failure}: {args[0]}: {detail}")


def run_tablet(client: HubClient, packet: dict, *, rmapi_bin: str,
               clock: Callable[[], float]) -> tuple[dict, bool]:
    """Download the file the Hub built and put it on the reMarkable. Returns
    (result body, stop_tick); stop_tick is set only when the lease is too
    close to start."""
    tablet = packet["tablet"]
    timeout = RMAPI_TIMEOUT
    deadline = _deadline(packet)
    if deadline is not None:
        left = deadline - clock() - LEASE_MARGIN
        if left <= 0:
            return {"error": "lease deadline reached before upload"}, True
        timeout = min(timeout, left)
    name = posixpath.basename(tablet["filename"].replace("\\", "/")).strip()
    folders = _folder_chain(tablet["folder"])
    try:
        data = client.download(tablet["file_url"])
        with tempfile.TemporaryDirectory(prefix="vcl-runner-tablet-") as tmp:
            path = os.path.join(tmp, name)
            with open(path, "wb") as fh:
                fh.write(data)
            # mkdir on a folder that exists prints "entry already exists" and exits 0.
            for folder in folders:
                run_rmapi(rmapi_bin, ["mkdir", folder], timeout)
            target = folders[-1] if folders else "/"
            run_rmapi(rmapi_bin, ["put", path, target], timeout)
    except TabletFailed as exc:
        return {"error": str(exc)}, False
    except OSError as exc:
        return {"error": f"upload failed: could not write the file ({type(exc).__name__})"}, False
    # rmapi names the document after the file, without its extension.
    return {"ok": True, "doc_path": posixpath.join(target, os.path.splitext(name)[0])}, False


def _pull_problem(packet: dict) -> str | None:
    if not isinstance(packet.get("id"), str) or not packet["id"]:
        return "no id"
    tablet = packet.get("tablet")
    if not isinstance(tablet, dict):
        return "no tablet"
    if tablet.get("target") != TABLET_TARGET:
        return f"unsupported tablet target {str(tablet.get('target'))[:32]!r}"
    for name in ("doc_path", "pages_url", "document_url"):
        if not isinstance(tablet.get(name), str) or not tablet[name]:
            return f"no tablet.{name}"
    if not tablet["doc_path"].startswith("/") or ".." in tablet["doc_path"].split("/"):
        return "tablet.doc_path must be an absolute path without .."
    if tablet.get("since") is not None and not isinstance(tablet.get("since"), str):
        return "tablet.since is not a string"
    known = tablet.get("known_pages")
    if known is not None and not (isinstance(known, dict) and all(isinstance(v, str) for v in known.values())):
        return "tablet.known_pages is not a map of page to hash"
    return None


def doc_version(stat_stdout: str) -> str | None:
    """ModifiedClient from `rmapi stat`: when the tablet last changed the
    document. Any mark the student makes moves it."""
    try:
        meta = json.loads(stat_stdout)
    except ValueError:
        return None
    value = meta.get("ModifiedClient") if isinstance(meta, dict) else None
    return value if isinstance(value, str) and value else None


def _with_query(url: str, **params) -> str:
    sep = "&" if "?" in url else "?"
    return url + sep + urllib.parse.urlencode(params)


def run_pull(client: HubClient, packet: dict, *, rmapi_bin: str,
             clock: Callable[[], float]) -> tuple[dict, bool]:
    """Read the student's marks off the document the Hub sent. Returns
    (result body, stop_tick).

    `rmapi stat` first: when the document has not changed since `since`
    (the version the Hub last pulled) the result says so and nothing is
    downloaded. Otherwise `rmapi get`, then each page with handwriting is
    rendered and posted to pages_url, the PDF first to document_url, except
    pages whose image the Hub already has (known_pages). The highlights go
    in the result. A page the Hub refuses is reported, not retried."""
    tablet = packet["tablet"]
    doc_path = tablet["doc_path"]
    known = tablet.get("known_pages") or {}
    timeout = RMAPI_TIMEOUT
    deadline = _deadline(packet)

    def time_left() -> float | None:
        return None if deadline is None else deadline - clock() - LEASE_MARGIN

    left = time_left()
    if left is not None:
        if left <= 0:
            return {"error": "lease deadline reached before the pull"}, True
        timeout = min(timeout, left)
    try:
        version = doc_version(run_rmapi(rmapi_bin, ["stat", doc_path], timeout, failure="pull failed"))
        if version and tablet.get("since") and version == tablet["since"]:
            return {"ok": True, "unchanged": True, "doc_version": version}, False
        with tempfile.TemporaryDirectory(prefix="vcl-runner-pull-") as tmp:
            run_rmapi(rmapi_bin, ["get", doc_path], timeout, cwd=tmp, failure="pull failed")
            doc = annotations.read_document(annotations.find_download(tmp))
    except TabletFailed as exc:
        return {"error": str(exc)}, False
    except annotations.AnnotationsUnavailable as exc:
        return {"error": f"pull failed: {exc}"}, False

    highlights = [{"page": p.page, "inserted": p.inserted, **h}
                  for p in doc.pages for h in p.highlights][:MAX_PULL_HIGHLIGHTS]
    inked = [p for p in doc.pages if p.strokes][:MAX_PULL_PAGES]
    pages = []
    document_sent = False
    for p in inked:
        png = annotations.render_page(p.strokes)
        digest = annotations.page_hash(png)
        entry = {"page": p.page, "inserted": p.inserted, "hash": digest}
        pages.append(entry)
        if known.get(p.key) == digest:
            entry["status"] = "known"
            continue
        left = time_left()
        if left is not None and left <= 0:
            return {"error": "lease deadline reached while sending pages"}, True
        if len(png) > MAX_UPLOAD_BYTES:
            entry["status"] = "too large"
            continue
        try:
            if not document_sent:
                document_sent = True
                if doc.pdf and len(doc.pdf) <= MAX_UPLOAD_BYTES:
                    status, _ = client.upload(tablet["document_url"], doc.pdf, "application/pdf")
                    if status in (404, 409):
                        return {"error": f"the Hub refused the document (HTTP {status})"}, False
            status, reply = client.upload(_with_query(tablet["pages_url"], page=p.page, inserted=p.inserted),
                                          png, "image/png")
        except TabletFailed as exc:
            entry["status"] = str(exc)
            continue
        if status in (404, 409):
            return {"error": f"the Hub refused page {p.key} (HTTP {status})"}, False
        entry["status"] = str((reply or {}).get("status") or "sent")[:40] if status == 200 else f"HTTP {status}"
    body = {"ok": True, "doc_version": version, "highlights": highlights, "pages": pages}
    return body, False


def tick(client: HubClient | None = None, *, max_jobs: int = MAX_JOBS,
         clock: Callable[[], float] = time.time) -> dict:
    """One heartbeat. Always returns the gate summary, never raises.

    count is the number of things the student has to act on: a rejected key or
    a missing claude CLI. Everything else (nothing queued, a lost lease, a
    failed step the Hub already shows on the thread, the Hub being briefly
    unreachable) is count 0."""
    summary = {"count": 0, "jobs": 0, "posted": 0, "dropped": 0, "failed_steps": 0, "reason": ""}
    if client is None:
        key = os.environ.get(ENV_KEY, "").strip()
        if not key:
            summary["reason"] = "agent key not configured; run: vcl-runner setup"
            return summary
        base = os.environ.get(ENV_BASE_URL, "").strip() or DEFAULT_BASE_URL
        try:
            client = HubClient(base, key)
        except ValueError as exc:
            summary.update(count=1, error=True, reason=str(exc))
            return summary
    step_timeout = _int_env(ENV_STEP_TIMEOUT, DEFAULT_STEP_TIMEOUT)
    budget = _int_env(ENV_TICK_BUDGET, DEFAULT_TICK_BUDGET)
    claude_bin = os.environ.get(ENV_CLAUDE, "").strip() or "claude"
    rmapi_bin = os.environ.get(ENV_RMAPI, "").strip() or "rmapi"
    started = clock()
    try:
        while summary["jobs"] < max_jobs:
            if clock() - started >= budget:
                summary["reason"] = f"tick budget of {budget}s spent; the rest waits for the next tick"
                break
            packet = client.next_job()
            if packet is None:
                break
            summary["jobs"] += 1
            if packet.get("kind") == PULL_KIND:
                problem = _pull_problem(packet)
                if problem:
                    log(f"job {packet.get('id')!s:.64}: malformed tablet packet ({problem})")
                    if not (isinstance(packet.get("id"), str) and packet["id"]):
                        summary["reason"] = f"malformed task packet ({problem})"
                        break
                    body, stop = {"error": f"malformed task packet: {problem}"}, False
                else:
                    log(f"job {packet['id']}: {PULL_KIND} from {TABLET_TARGET}, base {client.base_url}")
                    body, stop = run_pull(client, packet, rmapi_bin=rmapi_bin, clock=clock)
                    if "error" in body:
                        log(f"job {packet['id']}: {body['error']}")
            elif packet.get("kind") == TABLET_KIND:
                problem = _tablet_problem(packet)
                if problem:
                    log(f"job {packet.get('id')!s:.64}: malformed tablet packet ({problem})")
                    if not (isinstance(packet.get("id"), str) and packet["id"]):
                        summary["reason"] = f"malformed task packet ({problem})"
                        break
                    body, stop = {"error": f"malformed task packet: {problem}"}, False
                else:
                    log(f"job {packet['id']}: {TABLET_KIND} to {TABLET_TARGET}, base {client.base_url}")
                    body, stop = run_tablet(client, packet, rmapi_bin=rmapi_bin, clock=clock)
                    if "error" in body:
                        log(f"job {packet['id']}: {body['error']}")
            elif problem := _packet_problem(packet):
                log(f"job {packet.get('id')!s:.64}: malformed task packet ({problem})")
                if isinstance(packet.get("id"), str) and packet["id"] and isinstance(packet.get("phase"), str):
                    body, stop = {"phase": packet["phase"], "error": f"malformed task packet: {problem}"}, False
                else:
                    summary["reason"] = f"malformed task packet ({problem})"
                    break
            else:
                log(f"job {packet['id']}: {packet.get('kind')} phase {packet['phase']}, "
                    f"{len(packet['steps'])} step(s), base {client.base_url}")
                body, stop = run_job(packet, step_timeout=step_timeout, claude_bin=claude_bin, clock=clock)
            if "error" in body:
                summary["failed_steps"] += 1
                log(f"job {packet['id']}: posting error")
            status, reply = client.post_result(packet["id"], body)
            if status == 200:
                summary["posted"] += 1
                log(f"job {packet['id']}: HTTP 200 {(reply or {}).get('status', '')}")
            elif status in (404, 409):
                summary["dropped"] += 1
                log(f"job {packet['id']}: HTTP {status}, dropped (lease lost, phase moved, or not this founder's job)")
            else:
                log(f"job {packet['id']}: unexpected HTTP {status} on result")
            if stop:
                if "claude CLI not found" in body.get("error", ""):
                    summary.update(count=1, error=True, reason=body["error"])
                else:
                    summary["reason"] = "lease deadline near; stopped this tick"
                break
        else:
            summary["reason"] = summary["reason"] or f"claimed the {max_jobs}-job maximum for one tick"
    except AuthRejected as exc:
        summary.update(count=1, error=True, reason=f"the Hub rejected the agent key ({exc}); "
                                                  "create a new one in the Hub settings and run: vcl-runner setup")
    except HubUnreachable as exc:
        summary.update(error=True, reason=f"Hub unreachable, will retry next tick ({exc})")
    if not summary["reason"]:
        summary["reason"] = "nothing queued" if summary["jobs"] == 0 else "queue drained"
    return summary
