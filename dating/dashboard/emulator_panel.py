"""Dating AVD health rows for the chassis DevOps page.

Stdlib only, and panel() never raises: each signal degrades to its own row,
so a host with no Android SDK still renders DevOps.

Env (all optional):
    DATING_ADB_SERIAL           device serial                 (default emulator-5554)
    DATING_AVD_NAME             AVD whose snapshot dir is sized (default Dating_Pixel)
    DATING_EMULATOR_LOG_DIR     recovery hook log dir          (default <home>/logs/scheduled)
    DATING_EMULATOR_LOG         emulator stdout log for the gfxstream canary; row is skipped when unset
    DATING_SWIPE_SLOTS          heartbeat freshness checks, "name@hour,name@hour"
                                (e.g. dating-swipe-1@11,dating-swipe-2@15); rows skipped when unset
    DATING_SNAPSHOT_WARN_MB     snapshot dir size that flips to warn (default 500)
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
from datetime import datetime


def _customer_home() -> pathlib.Path:
    for var in ("CUSTOMER_HOME", "CHASSIS_HOME"):
        if os.environ.get(var):
            return pathlib.Path(os.environ[var]).expanduser()
    home = pathlib.Path.home() / ".behalfbot"
    return home if home.is_dir() else pathlib.Path("/app/customer")


def _row(label: str, value: str, status: str, detail: str = "") -> dict:
    return {"label": label, "value": value, "status": status, "detail": detail}


def _human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def _elapsed_human(dt: datetime) -> str:
    total_s = int((datetime.now() - dt).total_seconds())
    if total_s < 0:
        return "0s"
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _adb_state() -> dict:
    serial = os.environ.get("DATING_ADB_SERIAL", "emulator-5554")
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=8)
    except FileNotFoundError:
        return _row("ADB device state", "adb not installed", "warn", "Android platform-tools not on PATH")
    state = "missing"
    for line in r.stdout.splitlines():
        if line.startswith(serial):
            parts = line.split()
            state = parts[1] if len(parts) > 1 else "unknown"
            break
    return _row("ADB device state", state, "ok" if state == "device" else "fail", serial)


def _last_restart() -> dict:
    log_dir = pathlib.Path(os.environ.get("DATING_EMULATOR_LOG_DIR")
                           or _customer_home() / "logs" / "scheduled")
    log = log_dir / "dating-emulator-recovery.log"
    label = "Uptime since last cold boot"
    last = None
    if log.exists():
        pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] Restart successful")
        with open(log, errors="replace") as f:
            for line in f:
                m = pattern.match(line)
                if m:
                    last = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    if last is None:
        return _row(label, "no restarts logged", "ok", "" if log.exists() else "recovery log missing")
    hours = (datetime.now() - last).total_seconds() / 3600
    return _row(label, _elapsed_human(last), "warn" if hours < 1 else "ok",
                f"last restart: {last.strftime('%Y-%m-%d %H:%M:%S')}")


def _gfxstream_canary() -> dict | None:
    path = os.environ.get("DATING_EMULATOR_LOG")
    if not path:
        return None
    log = pathlib.Path(path).expanduser()
    label = "gfxstream error canary"
    if not log.exists():
        return _row(label, "0 errors", "ok", "log missing")
    with open(log, errors="replace") as f:
        count = sum(1 for line in f if "bad window surface handle" in line)
    fresh = (datetime.now().timestamp() - log.stat().st_mtime) < 3600
    return _row(label, f"{count} error{'s' if count != 1 else ''}", "warn" if count else "ok",
                "recent log" if fresh else "log not modified in 60 min")


def _slots() -> list[tuple[str, int]]:
    out = []
    for item in os.environ.get("DATING_SWIPE_SLOTS", "").split(","):
        name, _, hour = item.strip().partition("@")
        if name and hour.isdigit():
            out.append((name, int(hour)))
    return out


def _slot_rows() -> list[dict]:
    slots = _slots()
    if not slots:
        return []
    state_path = _customer_home() / "scheduled-tasks" / "heartbeat-state.json"
    try:
        hb_state = json.loads(state_path.read_text())
    except Exception:
        hb_state = {}
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    rows = []
    for name, threshold_hour in slots:
        label = f"{name} last fired"
        state = hb_state.get(name, {})
        raw = state.get("last_fired") or state.get("last_fire") if isinstance(state, dict) else None
        if not raw:
            rows.append(_row(label, "never", "warn"))
            continue
        try:
            fired = datetime.fromisoformat(raw)
        except ValueError:
            rows.append(_row(label, raw, "warn", "unparseable timestamp"))
            continue
        fired_today = fired.strftime("%Y-%m-%d") == today
        past = now.hour >= threshold_hour or (now.hour == threshold_hour - 1 and now.minute >= 30)
        rows.append(_row(
            label,
            fired.strftime("%H:%M") if fired_today else fired.strftime("%Y-%m-%d %H:%M"),
            "fail" if past and not fired_today else "ok",
            "today" if fired_today else "not today",
        ))
    return rows


def _snapshot_size() -> dict:
    avd = os.environ.get("DATING_AVD_NAME", "Dating_Pixel")
    snaps = pathlib.Path.home() / ".android" / "avd" / f"{avd}.avd" / "snapshots"
    label = "Snapshot dir size"
    if not snaps.exists():
        return _row(label, "0 B", "ok", "dir missing")
    total = sum(f.stat().st_size for f in snaps.rglob("*") if f.is_file())
    warn_mb = int(os.environ.get("DATING_SNAPSHOT_WARN_MB", "500"))
    warn = total > warn_mb * 1024 * 1024
    return _row(label, _human_bytes(total), "warn" if warn else "ok",
                f">{warn_mb} MB may indicate unintended snapshot accumulation" if warn else "")


def panel() -> dict:
    rows: list[dict] = []
    for label, probe in (
        ("ADB device state", _adb_state),
        ("Uptime since last cold boot", _last_restart),
        ("gfxstream error canary", _gfxstream_canary),
        ("Heartbeat freshness", _slot_rows),
        ("Snapshot dir size", _snapshot_size),
    ):
        try:
            result = probe()
        except Exception as e:
            result = _row(label, "error", "fail", f"{type(e).__name__}: {e}")
        if isinstance(result, list):
            rows.extend(result)
        elif result is not None:
            rows.append(result)
    return {"title": "Dating emulator", "rows": rows}
