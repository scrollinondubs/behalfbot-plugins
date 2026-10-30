"""Dating dashboard tab - the swipe review UI.

Swipe sessions drop profile screenshots in the inbox; the installer rates them
here (keyboard-driven). Each rating writes to the Postgres review store
(db/migrations/002_dating_swipes.sql) and makes the same file moves
dating-reconcile.py makes for a hand-sorted pick:

  FN (agent passed, installer likes)  -> copy to taste-refs/positive/, lost list,
                                         file -> processed
  FP (agent liked, installer passes)  -> file -> rhl-picks/pass/ (curation pool)
  TP / TN / no-opinion                -> file -> processed

Loaded by the chassis dashboard from contracts.dashboard in openclaw.plugin.json.
Postgres or psycopg missing renders the page with an error notice, never a 500.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import time

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load(name: str, path: pathlib.Path):
    # By path under a plugin-unique name: the bfl plugin ships its own
    # _chassis_db.py, and a shared sys.path entry would hand one plugin the
    # other's copy.
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_db = _load("behalfbot_dating_chassis_db", PLUGIN_DIR / "scripts" / "_chassis_db.py")
ds = _load("behalfbot_dating_swipes", PLUGIN_DIR / "scripts" / "_dating_swipes.py")


def _customer_home() -> pathlib.Path:
    for var in ("CUSTOMER_HOME", "CHASSIS_HOME"):
        if os.environ.get(var):
            return pathlib.Path(os.environ[var]).expanduser()
    home = pathlib.Path.home() / ".behalfbot"
    return home if home.is_dir() else pathlib.Path("/app/customer")


def _dir(env: str, *default: str) -> pathlib.Path:
    if os.environ.get(env):
        return pathlib.Path(os.environ[env]).expanduser()
    return _customer_home().joinpath(*default)


# Resolved per request so env changes and a late-mounted CUSTOMER_HOME apply
# without a restart. Defaults match dating-reconcile.py and skills/dating.md.
def inbox() -> pathlib.Path:
    return _dir("DATING_SWIPES_INBOX", "logs", "dating")


def picks_root() -> pathlib.Path:
    return _dir("DATING_RHL_PICKS_DIR", "rhl-picks")


def processed() -> pathlib.Path:
    return _dir("DATING_RHL_PROCESSED_DIR", "rhl-processed")


def taste_refs() -> pathlib.Path:
    return _dir("DATING_TASTE_REFS_DIR", "data", "dating", "taste-refs")


IMAGE_EXTS = (".png", ".jpg", ".jpeg")
EMPTY_STATS = {"pending": 0, "queue_pending": 0, "fn": 0, "fp": 0, "agree": 0, "accuracy": None}

router = APIRouter()


def _render(request: Request, name: str, ctx: dict):
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _connect():
    return _db.connect_pg()


def _db_error(e: Exception) -> str:
    return f"Review store unavailable ({type(e).__name__}: {e}). See the dating plugin README, Dashboard section."


# ───────── helpers ─────────

def _screenshot_roots() -> list[pathlib.Path]:
    picks = picks_root()
    refs = taste_refs()
    return [
        inbox(),
        processed(),
        picks / "like",
        picks / "super-like",
        picks / "pass",
        picks / "no-opinion",
        refs / "positive",
        refs / "negative",
    ]


def _safe_basename(name: str) -> str:
    if not name or "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise HTTPException(400, f"invalid basename: {name!r}")
    return name


def _resolve_screenshot(basename: str) -> pathlib.Path | None:
    """Basename is sanitized and extensions are fixed, so the constructed
    paths cannot escape the allowed roots."""
    basename = _safe_basename(basename)
    for root in _screenshot_roots():
        for ext in IMAGE_EXTS:
            p = root / f"{basename}{ext}"
            if p.exists():
                return p
    return None


def sync_inbox(cur) -> int:
    """Upsert every contract-matching inbox screenshot as a dating_profiles row
    (no review). Idempotent - keyed on screenshot_basename."""
    box = inbox()
    if not box.is_dir():
        return 0
    seen = 0
    for fp in sorted(box.iterdir()):
        if not fp.is_file() or fp.suffix.lower() not in IMAGE_EXTS:
            continue
        parsed = ds.parse_screenshot_name(fp.name)
        if not parsed:
            continue
        seen += 1
        ds.upsert_profile(
            cur,
            screenshot_basename=fp.stem,
            name=parsed["name"],
            age=parsed["age"],
            platform=parsed["platform"],
            encountered_on=parsed["date"],
            agent_action=parsed["action"],
            screenshot_path=str(fp),
        )
    return seen


def _move_file(src: pathlib.Path, dest_dir: pathlib.Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / src.name
    if target.exists():
        ts = time.strftime("%Y%m%d-%H%M%S")
        target = dest_dir / f"{src.stem}.{ts}{src.suffix}"
    shutil.move(str(src), str(target))


def _apply_file_side_effects(basename: str, outcome: str) -> str:
    """Mirror dating-reconcile.py's file handling for a single rating.
    Returns a short description for the UI."""
    current = _resolve_screenshot(basename)
    if current is None:
        return "no file found - DB only"
    actions = []
    if outcome == "fn":
        pos = taste_refs() / "positive"
        pos.mkdir(parents=True, exist_ok=True)
        target = pos / current.name
        if not target.exists():
            shutil.copy2(current, target)
            actions.append("copied to taste-refs/positive")
    if current.parent == inbox():
        if outcome == "fp":
            # Curation pool for negative refs, reviewed by hand before it
            # poisons the embedding - same convention as dating-reconcile.py.
            _move_file(current, picks_root() / "pass")
            actions.append("moved to rhl-picks/pass for curation")
        else:
            _move_file(current, processed())
            actions.append("moved to processed")
    return "; ".join(actions) if actions else "no file changes needed"


def _stats(cur) -> dict:
    cur.execute(
        f"""SELECT
                (SELECT COUNT(*) FROM dating_profiles p
                 WHERE NOT EXISTS (SELECT 1 FROM dating_reviews r WHERE r.profile_id = p.id)),
                (SELECT COUNT(*) FROM dating_recovery_queue WHERE status = 'pending'),
                (SELECT COUNT(*) FROM ({ds.latest_reviews_subquery()}) lr WHERE lr.outcome = 'fn'),
                (SELECT COUNT(*) FROM ({ds.latest_reviews_subquery()}) lr WHERE lr.outcome = 'fp'),
                (SELECT COUNT(*) FROM ({ds.latest_reviews_subquery()}) lr WHERE lr.outcome IN ('tp', 'tn'))
        """)
    pending, queue_pending, fn, fp, agree = cur.fetchone()
    decided = fn + fp + agree
    return {
        "pending": pending,
        "queue_pending": queue_pending,
        "fn": fn,
        "fp": fp,
        "agree": agree,
        "accuracy": round(100.0 * agree / decided, 1) if decided else None,
    }


# ───────── routes ─────────

@router.get("/", response_class=HTMLResponse)
def review(request: Request):
    ctx = {"pending": [], "stats": EMPTY_STATS, "error": None, "inbox": str(inbox())}
    try:
        conn = _connect()
        try:
            cur = conn.cursor()
            sync_inbox(cur)
            conn.commit()
            cur.execute(
                """SELECT p.id, p.screenshot_basename, p.name, p.age, p.platform,
                          p.encountered_on, p.agent_action
                   FROM dating_profiles p
                   WHERE NOT EXISTS (SELECT 1 FROM dating_reviews r WHERE r.profile_id = p.id)
                   ORDER BY p.encountered_on NULLS LAST, p.id""",
            )
            ctx["pending"] = [
                {
                    "id": r[0], "basename": r[1], "name": r[2],
                    "age": r[3] if r[3] is not None else "unk",
                    "platform": r[4],
                    "date": r[5].isoformat() if r[5] else "",
                    "agent_action": r[6] or "?",
                }
                for r in cur.fetchall()
            ]
            ctx["stats"] = _stats(cur)
        finally:
            conn.close()
    except Exception as e:
        ctx["error"] = _db_error(e)
    return _render(request, "dating_review.html", ctx)


@router.post("/rate")
def rate(profile_id: int = Form(...), bucket: str = Form(...)):
    if bucket not in ds.BUCKETS:
        raise HTTPException(400, f"bucket must be one of {ds.BUCKETS}")
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT screenshot_basename FROM dating_profiles WHERE id = %s", (profile_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "profile not found")
        basename = row[0]
        outcome = ds.record_review(cur, profile_id, bucket, "dashboard")
        conn.commit()
    finally:
        conn.close()
    file_result = _apply_file_side_effects(basename, outcome)
    return {"ok": True, "profile_id": profile_id, "bucket": bucket,
            "outcome": outcome, "files": file_result}


@router.get("/lost", response_class=HTMLResponse)
def lost_list(request: Request, status: str = "all"):
    ctx = {"entries": [], "stats": EMPTY_STATS, "status_filter": status, "error": None}
    where = ""
    params: tuple = ()
    if status in ("pending", "recovered", "lost"):
        where = "WHERE q.status = %s"
        params = (status,)
    try:
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute(
                f"""SELECT q.id, p.screenshot_basename, p.name, p.age, p.platform,
                           p.encountered_on, r.installer_bucket, q.status, q.added_at,
                           q.recovered_at, q.match_method
                    FROM dating_recovery_queue q
                    JOIN dating_profiles p ON p.id = q.profile_id
                    LEFT JOIN ({ds.latest_reviews_subquery()}) r ON r.profile_id = p.id
                    {where}
                    ORDER BY (q.status = 'pending') DESC, q.added_at DESC""",
                params,
            )
            ctx["entries"] = [
                {
                    "queue_id": r[0], "basename": r[1], "name": r[2],
                    "age": r[3] if r[3] is not None else "unk",
                    "platform": r[4],
                    "date": r[5].isoformat() if r[5] else "",
                    "installer_bucket": r[6] or "?",
                    "status": r[7],
                    "added_at": r[8].date().isoformat() if r[8] else "",
                    "recovered_at": r[9].date().isoformat() if r[9] else "",
                    "match_method": r[10] or "",
                }
                for r in cur.fetchall()
            ]
            ctx["stats"] = _stats(cur)
        finally:
            conn.close()
    except Exception as e:
        ctx["error"] = _db_error(e)
    return _render(request, "dating_lost.html", ctx)


@router.post("/lost/{queue_id}/status")
def set_lost_status(queue_id: int, status: str = Form(...),
                    match_method: str = Form("")):
    if status not in ("pending", "recovered", "lost"):
        raise HTTPException(400, "status must be pending, recovered, or lost")
    recovered_at = "NOW()" if status == "recovered" else "NULL"
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""UPDATE dating_recovery_queue
                SET status = %s, recovered_at = {recovered_at},
                    match_method = COALESCE(NULLIF(%s, ''), match_method)
                WHERE id = %s""",
            (status, match_method, queue_id),
        )
        updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if not updated:
        raise HTTPException(404, "queue entry not found")
    return {"ok": True, "queue_id": queue_id, "status": status}


@router.get("/reviewed", response_class=HTMLResponse)
def reviewed(request: Request, limit: int = 200):
    ctx = {"rows": [], "stats": EMPTY_STATS, "limit": limit, "error": None}
    try:
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute(
                f"""SELECT p.id, p.screenshot_basename, p.name, p.age, p.platform,
                           p.encountered_on, p.agent_action, r.installer_bucket, r.outcome,
                           r.source, r.reviewed_at
                    FROM dating_profiles p
                    JOIN ({ds.latest_reviews_subquery()}) r ON r.profile_id = p.id
                    ORDER BY r.reviewed_at DESC
                    LIMIT %s""",
                (limit,),
            )
            ctx["rows"] = [
                {
                    "id": r[0], "basename": r[1], "name": r[2],
                    "age": r[3] if r[3] is not None else "unk",
                    "platform": r[4],
                    "date": r[5].isoformat() if r[5] else "",
                    "agent_action": r[6] or "?",
                    "installer_bucket": r[7], "outcome": r[8], "source": r[9],
                    "reviewed_at": r[10].strftime("%Y-%m-%d %H:%M") if r[10] else "",
                }
                for r in cur.fetchall()
            ]
            ctx["stats"] = _stats(cur)
        finally:
            conn.close()
    except Exception as e:
        ctx["error"] = _db_error(e)
    return _render(request, "dating_reviewed.html", ctx)


@router.get("/screenshot/{basename}")
def screenshot(basename: str):
    p = _resolve_screenshot(basename)
    if p is None:
        raise HTTPException(404, f"screenshot not found for {basename}")
    return FileResponse(str(p))
