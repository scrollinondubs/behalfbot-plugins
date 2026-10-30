"""BFL dashboard tab - week grid, day detail, search, and meal fix-ups.

Loaded by the chassis dashboard from contracts.dashboard in openclaw.plugin.json.
Reads the plugin's own tables (db/migrations/001_bfl.sql) through
scripts/_chassis_db.py. Optional tables other plugins or the install may add
(oura_daily, oura_sleep_sessions, bfl_body_composition, bfl_mindfulness) are
read through _safe_read, so their absence renders an empty panel. A database
that is down renders the page with an error notice, never a 500.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import time
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load(name: str, path: pathlib.Path):
    # By path under a plugin-unique name: the dating plugin ships its own
    # _chassis_db.py, and a shared sys.path entry would hand one plugin the
    # other's copy.
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_db = _load("behalfbot_bfl_chassis_db", PLUGIN_DIR / "scripts" / "_chassis_db.py")


def archive_root() -> pathlib.Path:
    """Same resolution as scripts/bfl-vision-extract.py."""
    explicit = os.environ.get("BFL_ARCHIVE_DIR")
    if explicit:
        return pathlib.Path(explicit).expanduser()
    return pathlib.Path.home() / "behalfbot-archive" / "bfl"


def archive_roots() -> list[pathlib.Path]:
    """archive_root() first, then BFL_ARCHIVE_EXTRA_DIRS (os.pathsep-separated)
    for installs whose older photos live in a previous archive location."""
    extra = os.environ.get("BFL_ARCHIVE_EXTRA_DIRS", "")
    return [archive_root()] + [pathlib.Path(x).expanduser() for x in extra.split(os.pathsep) if x]


router = APIRouter()


def _render(request: Request, name: str, ctx: dict):
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _db_error(e: Exception) -> str:
    return f"BFL database unavailable ({type(e).__name__}: {e}). See the bfl plugin README, Dashboard section."


# ───────── DB helpers ─────────

def db():
    """Active chassis backend (USE_PG). Use _cur() for dict-row access."""
    return _db.connect()


def _cur(conn):
    """Templates use row['col'] access, which needs dict_row on PG."""
    return _db.cursor(conn, dict_rows=True)


def _now_epoch() -> int:
    """Dialect-neutral substitute for SQLite's `unixepoch()` function."""
    return int(time.time())


def iso_week_bounds(iso_week: str) -> tuple[date, date]:
    y, w = iso_week.split("-W")
    monday = date.fromisocalendar(int(y), int(w), 1)
    return monday, monday + timedelta(days=6)


def current_iso_week() -> str:
    today = date.today()
    return f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"


def _authoritative_macros(meal: dict) -> None:
    """Resolve which macro layer is authoritative (manual > vision > fdc) and
    annotate the meal dict in place with `macros_source` + `auth_kcal/protein/carbs/fat`.
    The dashboard reads these fields - keep the priority order here and the
    template in sync.

    Precedence is vision-primary: the FDC photo-
    enrichment path consumes vision's own portion guess and adds lexical-match
    error on top, so it cannot beat vision for home-cooked plates (40% divergence
    even at full match coverage). FDC is retired as a photo-enrichment source and
    sits LAST here purely as a fallback for the ~82 legacy meals (Apr 23 - May 8)
    that predate the retirement and have no vision macros. Anything with vision
    macros must show them, not the discredited FDC numbers."""
    if meal.get("manual_kcal") is not None:
        src = "manual"
        k, p, c, f = meal["manual_kcal"], meal["manual_protein_g"], meal["manual_carbs_g"], meal["manual_fat_g"]
    elif meal.get("est_calories") is not None:
        src = "vision"
        k, p, c, f = meal["est_calories"], meal["est_protein_g"], meal["est_carbs_g"], meal["est_fat_g"]
    elif meal.get("fdc_kcal") is not None:
        src = "fdc"
        k, p, c, f = meal["fdc_kcal"], meal["fdc_protein_g"], meal["fdc_carbs_g"], meal["fdc_fat_g"]
    else:
        src = None
        k = p = c = f = None
    meal["macros_source"] = src
    meal["auth_kcal"] = k
    meal["auth_protein_g"] = p
    meal["auth_carbs_g"] = c
    meal["auth_fat_g"] = f


def load_oura(conn, d: str) -> dict | None:
    """Return {'daily': {...}, 'sessions': [...]} for a date, or None.

    Oura tables are not part of this plugin's migration; callers go through
    _safe_read so an install without them renders no Oura panel.
    """
    cur = _cur(conn)
    daily = cur.execute("SELECT * FROM oura_daily WHERE date = ?", (d,)).fetchone()
    if not daily:
        return None
    out: dict = dict(daily)
    for k in ("readiness_contributors_json", "sleep_contributors_json"):
        raw = out.get(k)
        if raw:
            try:
                out[k.replace("_json", "")] = json.loads(raw)
            except Exception:
                out[k.replace("_json", "")] = {}
    sessions = [dict(r) for r in cur.execute(
        "SELECT * FROM oura_sleep_sessions WHERE date = ? ORDER BY bedtime_start",
        (d,),
    ).fetchall()]
    out["sessions"] = sessions
    return out


# ───────── Body composition + mindfulness ─────────

# Rendered on the week view. Ordered so the numbers worth steering by -
# fat lost, lean held - sit next to the scale weight rather than under it.
BODY_COMP_METRICS = (
    ("weight_kg", "Weight", "kg", 1),
    ("body_fat_pct", "Body fat", "%", 1),
    ("fat_mass_kg", "Fat mass", "kg", 1),
    ("lean_mass_kg", "Lean mass", "kg", 1),
    ("bmi", "BMI", "", 1),
)

# Lower is better for these, so a negative delta is progress. Lean mass and
# BMI are deliberately absent: holding lean flat while fat drops is the win,
# and colouring it green or red either way would be a lie.
BODY_COMP_LOWER_IS_BETTER = {"weight_kg", "body_fat_pct", "fat_mass_kg"}


def _safe_read(conn, fn, default):
    """Run a read that touches tables or columns this plugin's migration does
    not create. On Postgres a failed statement poisons the transaction, so
    every later read on the same connection would fail too. Swallow, roll
    back, render the empty state.
    """
    try:
        return fn(conn)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[bfl] skipping panel, read failed: {type(e).__name__}: {e}", flush=True)
        return default


def _delta(latest: dict, baseline: dict | None, column: str) -> float | None:
    """Change in a column between two readings, or None when there is nothing
    honest to report. A trend needs two distinct readings with the value
    present in both; one row on the books is not a trend."""
    if not baseline or baseline["id"] == latest["id"]:
        return None
    now, then = latest.get(column), baseline.get(column)
    if now is None or then is None:
        return None
    return round(float(now) - float(then), 2)


def load_body_composition(conn) -> dict | None:
    """Latest weigh-in plus its deltas against the first ever reading and the
    last reading at least 7 days older. Returns None when nothing has been
    recorded yet."""
    cur = _cur(conn)
    latest = cur.execute(
        "SELECT * FROM bfl_body_composition ORDER BY measured_at DESC LIMIT 1"
    ).fetchone()
    if not latest:
        return None
    latest = dict(latest)

    first = cur.execute(
        "SELECT * FROM bfl_body_composition ORDER BY measured_at ASC LIMIT 1"
    ).fetchone()
    week_ago = cur.execute(
        "SELECT * FROM bfl_body_composition WHERE measured_at <= ? "
        "ORDER BY measured_at DESC LIMIT 1",
        (latest["measured_at"] - 7 * 86400,),
    ).fetchone()
    first = dict(first) if first else None
    week_ago = dict(week_ago) if week_ago else None

    derived = {
        c.strip() for c in (latest.get("derived_fields") or "").split(",") if c.strip()
    }
    metrics = []
    for column, label, unit, places in BODY_COMP_METRICS:
        value = latest.get(column)
        if value is None:
            continue
        metrics.append({
            "column": column,
            "label": label,
            "unit": unit,
            "value": round(float(value), places),
            "derived": column in derived,
            "lower_is_better": column in BODY_COMP_LOWER_IS_BETTER,
            "delta_first": _delta(latest, first, column),
            "delta_week": _delta(latest, week_ago, column),
        })

    return {
        "date": latest["date"],
        "metrics": metrics,
        "has_first": bool(first and first["id"] != latest["id"]),
        "has_week": bool(week_ago and week_ago["id"] != latest["id"]),
        "first_date": first["date"] if first else None,
        "week_date": week_ago["date"] if week_ago else None,
    }


def load_mindfulness_week(conn, monday: date) -> dict:
    """Meditation minutes for the seven days of the displayed week.

    `ever` distinguishes "nothing has ever synced" from "a quiet week", which
    are different problems - the first is a broken pipeline, the second is
    just a week without practice.
    """
    cur = _cur(conn)
    sunday = monday + timedelta(days=6)
    rows = {
        r["date"]: dict(r)
        for r in cur.execute(
            "SELECT * FROM bfl_mindfulness WHERE date >= ? AND date <= ? ORDER BY date",
            (monday.isoformat(), sunday.isoformat()),
        ).fetchall()
    }
    ever = cur.execute("SELECT 1 FROM bfl_mindfulness LIMIT 1").fetchone() is not None

    days = []
    for offset in range(7):
        d = monday + timedelta(days=offset)
        row = rows.get(d.isoformat())
        days.append({
            "date": d,
            "minutes": round(float(row["minutes"]), 1) if row else 0.0,
            "sessions": row["session_count"] if row else 0,
        })

    total = round(sum(d["minutes"] for d in days), 1)
    practiced = sum(1 for d in days if d["minutes"] > 0)
    return {
        "days": days,
        "total_minutes": total,
        "sessions": sum(d["sessions"] for d in days),
        "days_practiced": practiced,
        # Bar heights are a percentage of this. Never zero, so the template
        # cannot divide by it and get an error on an empty week.
        "peak_minutes": max([d["minutes"] for d in days] + [1.0]),
        "ever": ever,
    }


def load_day(conn, d: str) -> dict | None:
    cur = _cur(conn)
    row = cur.execute("SELECT * FROM bfl_days WHERE date = ?", (d,)).fetchone()
    if not row:
        return None
    day = dict(row)
    day["meals"] = [dict(m) for m in cur.execute(
        "SELECT * FROM bfl_meals WHERE day_id = ? ORDER BY meal_num", (row["id"],)).fetchall()]
    for m in day["meals"]:
        # Key name intentionally NOT "items" - that collides with dict.items() in Jinja attribute access.
        m["fdc_items"] = [dict(r) for r in cur.execute(
            "SELECT * FROM bfl_meal_items WHERE meal_id = ? ORDER BY item_order",
            (m["id"],)).fetchall()]
        _authoritative_macros(m)
    day["workouts"] = [dict(w) for w in cur.execute(
        "SELECT * FROM bfl_workouts WHERE day_id = ? ORDER BY exercise_order, set_number",
        (row["id"],)).fetchall()]
    exercises: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for w in day["workouts"]:
        if not current or current["exercise_name"] != w["exercise_name"] or current["exercise_order"] != w["exercise_order"]:
            current = {
                "exercise_order": w["exercise_order"],
                "exercise_name": w["exercise_name"],
                "muscle_group": w["muscle_group"],
                "is_main": w["is_main"],
                "sets": [],
            }
            exercises.append(current)
        current["sets"].append(w)
    day["exercises"] = exercises
    day["aerobic"] = [dict(a) for a in cur.execute(
        "SELECT * FROM bfl_aerobic WHERE day_id = ?", (row["id"],)).fetchall()]
    for a in day["aerobic"]:
        if a.get("actual_intensities_json"):
            try:
                a["actual_intensities"] = json.loads(a["actual_intensities_json"])
            except Exception:
                a["actual_intensities"] = []
        # apple-health-receiver._upsert_hike stashes structured hike data
        # (distance/HR/UUID) as JSON in notes because bfl_aerobic lacks those
        # columns. Parse it back out so the template can render it like a run
        # instead of dumping the blob.
        if a.get("notes"):
            stripped = a["notes"].strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    a["notes_meta"] = json.loads(stripped)
                except Exception:
                    a["notes_meta"] = None
    day["runs"] = [dict(r) for r in cur.execute(
        "SELECT * FROM bfl_runs WHERE day_id = ? ORDER BY start_time", (row["id"],)).fetchall()]
    # Drop aerobic rows that are the apple-health-receiver's mirror of a
    # bfl_runs row (same activity, mirrored so the briefing's aerobic-day
    # reader sees apple-health-only days). Dashboard reads both tables, so
    # without dedup the same run shows up twice.
    if day["runs"]:
        run_starts = [r["start_time"] for r in day["runs"] if r.get("start_time")]
        def _is_run_mirror(a: dict) -> bool:
            if (a.get("activity_type") or "").lower() != "run":
                return False
            if a.get("start_time") is None:
                return False
            return any(abs(a["start_time"] - s) <= 120 for s in run_starts)
        day["aerobic"] = [a for a in day["aerobic"] if not _is_run_mirror(a)]
    return day


# ───────── routes ─────────

def _oura_scores(conn, d: date) -> dict | None:
    r = _cur(conn).execute(
        "SELECT readiness_score, sleep_score FROM oura_daily WHERE date = ?",
        (d.isoformat(),),
    ).fetchone()
    return dict(r) if r else None


@router.get("/", response_class=HTMLResponse)
def home(request: Request, week: str | None = None):
    iso = week or current_iso_week()
    try:
        monday, sunday = iso_week_bounds(iso)
    except ValueError:
        raise HTTPException(400, "week must look like 2026-W05")
    days = [{"date": monday + timedelta(days=o), "data": None, "oura": None} for o in range(7)]
    body_comp = mindful = error = None
    try:
        conn = db()
        try:
            for slot in days:
                slot["data"] = load_day(conn, slot["date"].isoformat())
                slot["oura"] = _safe_read(conn, lambda c, d=slot["date"]: _oura_scores(c, d), None)
            body_comp = _safe_read(conn, load_body_composition, None)
            mindful = _safe_read(conn, lambda c: load_mindfulness_week(c, monday), None)
        finally:
            conn.close()
    except Exception as e:
        error = _db_error(e)
    prev_mon = monday - timedelta(days=7)
    next_mon = monday + timedelta(days=7)
    prev_week = f"{prev_mon.isocalendar()[0]}-W{prev_mon.isocalendar()[1]:02d}"
    next_week = f"{next_mon.isocalendar()[0]}-W{next_mon.isocalendar()[1]:02d}"
    return _render(request, "bfl_home.html", {
        "days": days, "iso": iso, "monday": monday, "sunday": sunday,
        "prev_week": prev_week, "next_week": next_week, "current_week": current_iso_week(),
        "body_comp": body_comp, "mindful": mindful, "error": error,
    })


@router.get("/day/{d}", response_class=HTMLResponse)
def day_detail(request: Request, d: str):
    ctx = {"date": d, "day": None, "prev_date": None, "next_date": None,
           "unmatched_extractions": [], "oura": None, "error": None}
    try:
        conn = db()
        try:
            cur = _cur(conn)
            ctx["day"] = load_day(conn, d)
            adj = cur.execute(
                "SELECT date FROM bfl_days WHERE date < ? ORDER BY date DESC LIMIT 1", (d,)).fetchone()
            ctx["prev_date"] = adj["date"] if adj else None
            adj2 = cur.execute(
                "SELECT date FROM bfl_days WHERE date > ? ORDER BY date ASC LIMIT 1", (d,)).fetchone()
            ctx["next_date"] = adj2["date"] if adj2 else None
            ctx["unmatched_extractions"] = list_unmatched_extractions_for_date(conn, d)
            ctx["oura"] = _safe_read(conn, lambda c: load_oura(c, d), None)
        finally:
            conn.close()
    except Exception as e:
        ctx["error"] = _db_error(e)
    return _render(request, "bfl_day.html", ctx)


@router.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    results_workouts = []
    results_meals = []
    error = None
    if q and len(q) >= 2:
        like = f"%{q}%"
        try:
            conn = db()
            try:
                cur = _cur(conn)
                results_workouts = [dict(r) for r in cur.execute(
                    "SELECT bfl_days.date, bfl_workouts.* FROM bfl_workouts "
                    "JOIN bfl_days ON bfl_workouts.day_id = bfl_days.id "
                    "WHERE exercise_name LIKE ? ORDER BY bfl_days.date DESC LIMIT 200", (like,)).fetchall()]
                results_meals = [dict(r) for r in cur.execute(
                    "SELECT bfl_days.date, bfl_meals.* FROM bfl_meals "
                    "JOIN bfl_days ON bfl_meals.day_id = bfl_days.id "
                    "WHERE description LIKE ? ORDER BY bfl_days.date DESC LIMIT 200", (like,)).fetchall()]
            finally:
                conn.close()
        except Exception as e:
            error = _db_error(e)
    return _render(request, "bfl_search.html", {
        "q": q, "workouts": results_workouts, "meals": results_meals, "error": error,
    })


@router.get("/photo/{basename}")
def photo(basename: str):
    if "/" in basename or ".." in basename:
        raise HTTPException(400, "invalid basename")
    candidates = []
    for root in archive_roots():
        raw = root / "raw"
        for d in (raw, raw / "backfill"):
            candidates.extend(d / f"{basename}{ext}" for ext in (".jpeg", ".jpg", ".png"))
    for candidate in candidates:
        if candidate.exists():
            return FileResponse(str(candidate))
    raise HTTPException(404, f"photo not found for {basename}")


@router.post("/day/{d}/change-date")
def change_date(d: str, new_date: str = Form(...)):
    try:
        date.fromisoformat(new_date)
    except ValueError:
        raise HTTPException(400, "new_date must be YYYY-MM-DD")
    conn = db()
    cur = _cur(conn)
    row = cur.execute("SELECT id FROM bfl_days WHERE date = ?", (d,)).fetchone()
    if not row:
        raise HTTPException(404, "day not found")
    clash = cur.execute("SELECT id FROM bfl_days WHERE date = ? AND id != ?", (new_date, row["id"])).fetchone()
    if clash:
        raise HTTPException(409, f"a day already exists on {new_date}; resolve manually first")
    cur.execute("UPDATE bfl_days SET date = ?, updated_at = ? WHERE id = ?", (new_date, _now_epoch(), row["id"]))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/bfl/day/{new_date}", status_code=303)


@router.post("/workout/{workout_id}/rename")
def rename_exercise(workout_id: int, new_name: str = Form(...), cascade: bool = Form(False)):
    conn = db()
    cur = _cur(conn)
    row = cur.execute("SELECT id, day_id, exercise_name FROM bfl_workouts WHERE id = ?", (workout_id,)).fetchone()
    if not row:
        raise HTTPException(404, "workout not found")
    if cascade:
        cur.execute("UPDATE bfl_workouts SET exercise_name = ? WHERE day_id = ? AND exercise_name = ?",
                    (new_name, row["day_id"], row["exercise_name"]))
    else:
        cur.execute("UPDATE bfl_workouts SET exercise_name = ? WHERE id = ?", (new_name, workout_id))
    conn.commit()
    day_row = cur.execute("SELECT date FROM bfl_days WHERE id = ?", (row["day_id"],)).fetchone()
    conn.close()
    return RedirectResponse(url=f"/bfl/day/{day_row['date']}", status_code=303)


@router.post("/meal/{meal_id}/match-photo")
def match_photo(meal_id: int, food_photo_basename: str = Form(...), autoenrich: bool = Form(True)):
    if "/" in food_photo_basename or ".." in food_photo_basename:
        raise HTTPException(400, "invalid basename")
    conn = db()
    cur = _cur(conn)
    row = cur.execute("SELECT id, day_id FROM bfl_meals WHERE id = ?", (meal_id,)).fetchone()
    if not row:
        raise HTTPException(404, "meal not found")
    candidates = []
    for root in archive_roots():
        raw = root / "raw"
        candidates.extend([
            raw / f"{food_photo_basename}.jpeg",
            raw / f"{food_photo_basename}.jpg",
            raw / f"{food_photo_basename}.png",
        ])
    for candidate in candidates:
        if candidate.exists():
            path = str(candidate)
            break
    else:
        raise HTTPException(404, "photo file not found")
    cur.execute(
        "UPDATE bfl_meals SET food_photo_path = ?, photo_matched = 1 WHERE id = ?",
        (path, meal_id))
    conn.commit()
    day_row = cur.execute("SELECT date FROM bfl_days WHERE id = ?", (row["day_id"],)).fetchone()
    conn.close()
    if autoenrich:
        _run_enrichment(food_photo_basename)
    return RedirectResponse(url=f"/bfl/day/{day_row['date']}", status_code=303)


# ───────── Macro editing, unmatching, requeuing (#238) ─────────

def _safe_basename(name: str) -> str:
    if not name or "/" in name or ".." in name:
        raise HTTPException(400, f"invalid basename: {name!r}")
    return name


def _parse_optional_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        raise HTTPException(400, f"expected a number, got {s!r}")


def _meal_date(conn, meal_id: int) -> str:
    row = _cur(conn).execute(
        "SELECT d.date FROM bfl_meals m JOIN bfl_days d ON m.day_id=d.id WHERE m.id = ?",
        (meal_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "meal not found")
    return row["date"]


def _basename_from_path(path: str | None) -> str | None:
    if not path:
        return None
    stem = pathlib.Path(path).stem
    return stem or None


def _run_enrichment(basename: str, timeout_s: int = 120) -> str:
    """Invoke bfl-fdc-enrich.py for a single extraction basename. Returns stdout.
    Fire-and-report; any error is surfaced via HTTPException so the form POST
    shows a useful response rather than silently failing."""
    script = PLUGIN_DIR / "scripts" / "bfl-fdc-enrich.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--only", basename, "--force"],
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        raise HTTPException(504, f"enrichment timed out after {timeout_s}s: {e}")
    if proc.returncode != 0:
        raise HTTPException(500, f"enrichment failed: {proc.stderr or proc.stdout}")
    return proc.stdout


@router.post("/meal/{meal_id}/edit-macros")
def edit_macros(
    meal_id: int,
    kcal: str = Form(""),
    protein_g: str = Form(""),
    carbs_g: str = Form(""),
    fat_g: str = Form(""),
    notes: str = Form(""),
    clear: str = Form(""),
):
    """Write installer-authored macro values into the `manual_*` columns. These take
    priority over FDC and vision in the dashboard. Pass clear=1 to wipe the
    manual override (dashboard falls back to FDC/vision)."""
    conn = db()
    cur = _cur(conn)
    d = _meal_date(conn, meal_id)
    if clear:
        cur.execute(
            "UPDATE bfl_meals SET manual_kcal=NULL, manual_protein_g=NULL, "
            "manual_carbs_g=NULL, manual_fat_g=NULL, manual_macros_at=NULL, "
            "manual_macros_notes=NULL WHERE id = ?", (meal_id,))
    else:
        vals = {
            "manual_kcal": _parse_optional_float(kcal),
            "manual_protein_g": _parse_optional_float(protein_g),
            "manual_carbs_g": _parse_optional_float(carbs_g),
            "manual_fat_g": _parse_optional_float(fat_g),
        }
        if all(v is None for v in vals.values()) and not notes.strip():
            raise HTTPException(400, "provide at least one of kcal/protein_g/carbs_g/fat_g, or clear=1")
        cur.execute(
            "UPDATE bfl_meals SET manual_kcal=?, manual_protein_g=?, manual_carbs_g=?, "
            "manual_fat_g=?, manual_macros_at=?, manual_macros_notes=? "
            "WHERE id = ?",
            (vals["manual_kcal"], vals["manual_protein_g"], vals["manual_carbs_g"],
             vals["manual_fat_g"], _now_epoch(), notes.strip() or None, meal_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/bfl/day/{d}", status_code=303)


@router.post("/meal/{meal_id}/unmatch-photo")
def unmatch_photo(meal_id: int):
    """Clear the photo linkage and all FDC enrichment for this meal. Vision
    macros (est_*) are preserved since they came from the extraction, not the
    link. Run /match-photo again to re-link; FDC auto-enriches if autoenrich=1."""
    conn = db()
    cur = _cur(conn)
    d = _meal_date(conn, meal_id)
    cur.execute("DELETE FROM bfl_meal_items WHERE meal_id = ?", (meal_id,))
    cur.execute(
        "UPDATE bfl_meals SET food_photo_path=NULL, photo_matched=0, "
        "fdc_kcal=NULL, fdc_protein_g=NULL, fdc_carbs_g=NULL, fdc_fat_g=NULL, "
        "fdc_enriched_at=NULL, fdc_match_coverage=NULL WHERE id = ?",
        (meal_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/bfl/day/{d}", status_code=303)


@router.post("/meal/{meal_id}/requeue-enrichment")
def requeue_enrichment(meal_id: int):
    """Re-run FDC enrichment for this meal's current photo. Useful after a
    manual photo swap or to pick up fdc_food_cache corrections."""
    conn = db()
    cur = _cur(conn)
    row = cur.execute("SELECT food_photo_path FROM bfl_meals WHERE id = ?", (meal_id,)).fetchone()
    if not row or not row["food_photo_path"]:
        conn.close()
        raise HTTPException(400, "no food_photo_path on this meal - match a photo first")
    d = _meal_date(conn, meal_id)
    basename = _basename_from_path(row["food_photo_path"])
    conn.close()
    if not basename:
        raise HTTPException(400, "could not derive extraction basename from photo path")
    _run_enrichment(basename)
    return RedirectResponse(url=f"/bfl/day/{d}", status_code=303)


def list_unmatched_extractions_for_date(conn, day: str) -> list[dict]:
    """Return food_photo extraction basenames whose source image isn't linked
    to any bfl_meals row. Used to populate the dashboard dropdown."""
    matched_paths = {
        row["food_photo_path"]
        for row in _cur(conn).execute(
            "SELECT food_photo_path FROM bfl_meals WHERE food_photo_path IS NOT NULL"
        ).fetchall()
    }
    out = []
    extractions = archive_root() / "extractions"
    if not extractions.is_dir():
        return out
    for p in sorted(extractions.glob("*.json")):
        if p.stem.endswith("_fdc") or p.name == "_costs.jsonl":
            continue
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        if data.get("classification") != "food_photo":
            continue
        src = data.get("source")
        if not src or src in matched_paths:
            continue
        ext = data.get("extraction") or {}
        out.append({
            "basename": p.stem,
            "item_names": ext.get("items") or [],
            "vision_kcal": ext.get("estimated_calories"),
            "portion_g": ext.get("estimated_portion_grams"),
            "source_path": src,
        })
    return out
