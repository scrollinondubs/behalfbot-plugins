"""Store the agent key the way the chassis stores every other plugin secret.

The heartbeat dispatcher sources ${CUSTOMER_HOME}/.env.baked when it exists,
otherwise ${CUSTOMER_HOME}/.env, before it runs any gather script. So the key
goes into .env, and into .env.baked too when that file is present, or a baked
install would never see it. Both files are install-side and never committed.

The key is written with mode 0600 and replaced in place: one
FOUNDER_OS_AGENT_KEY line, every other line kept as it was.
"""
from __future__ import annotations

import os
import pathlib
import re
import tempfile
import urllib.parse

from .runner import ENV_BASE_URL, ENV_KEY, KEY_PREFIX, LOOPBACK

KEY_RE = re.compile(r"^" + re.escape(KEY_PREFIX) + r"[A-Za-z0-9_-]{16,256}$")


def default_env_file() -> pathlib.Path:
    for var in ("CUSTOMER_HOME", "CHASSIS_HOME"):
        home = os.environ.get(var, "").strip()
        if home:
            return pathlib.Path(home) / ".env"
    raise ValueError("neither CUSTOMER_HOME nor CHASSIS_HOME is set; pass --env-file")


def check_key(key: str) -> str:
    key = key.strip()
    if not KEY_RE.match(key):
        # The message never echoes the value: a near-miss is still most of a key.
        raise ValueError(f"that does not look like an agent key (it should start with {KEY_PREFIX} "
                         "and come from Safari Hub settings, Run Safari work on: My BehalfBot)")
    return key


def check_base_url(url: str) -> str:
    url = url.strip().rstrip("/")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOOPBACK):
        raise ValueError("the Hub base URL must be https (plain http only to localhost)")
    return url


def _upsert(path: pathlib.Path, values: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(values)
    out = []
    for line in lines:
        name = line.split("=", 1)[0].strip()
        prefix = ""
        if name.startswith("export "):
            name, prefix = name[len("export "):].strip(), "export "
        if name in values:
            if name in pending:
                out.append(f"{prefix}{name}={pending.pop(name)}")
            continue
        out.append(line)
    out.extend(f"{name}={value}" for name, value in pending.items())
    fd, tmp = tempfile.mkstemp(prefix=".env.", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def save_key(key: str, env_file: pathlib.Path | None = None, base_url: str | None = None) -> list[pathlib.Path]:
    """Write the key (and the base URL, when given) into .env and, if present,
    .env.baked. Returns the files written. Raises ValueError on a bad key or URL."""
    values = {ENV_KEY: check_key(key)}
    if base_url:
        values[ENV_BASE_URL] = check_base_url(base_url)
    env_file = env_file or default_env_file()
    if not env_file.parent.is_dir():
        raise ValueError(f"{env_file.parent} does not exist")
    written = []
    for path in (env_file, env_file.with_name(env_file.name + ".baked")):
        if path == env_file or path.exists():
            _upsert(path, values)
            written.append(path)
    return written
