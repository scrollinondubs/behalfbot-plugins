#!/usr/bin/env python3
"""Helpers for the Postgres-backed swipe review store (dating_profiles,
dating_reviews, dating_recovery_queue - see db/migrations/002_dating_swipes.sql).

Pure SQL + parsing: every function takes an open cursor, so callers choose how
to connect (the dashboard tab loads _chassis_db by path; scripts can import it
the way _dating_db.py does).

Filename contract (set by the swipe subagent at screenshot time):
    Name_Age_App_YYYY-MM-DD_action.png
Legacy 4-segment shape Name_App_Date_Action (no age) is tolerated. Age "unk"
maps to NULL.
"""
from __future__ import annotations

import re

BUCKETS = ("like", "super-like", "pass", "no-opinion")

NAME_RE = re.compile(
    r"^(?P<name>[^_]+)_(?P<age>[^_]+)_(?P<platform>[^_]+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<action>[a-z\-]+?)(?:_photo\d+)?(?:\.(?:png|jpe?g))?$",
    re.IGNORECASE,
)
NAME_RE_4SEG = re.compile(
    r"^(?P<name>[^_]+)_(?P<platform>[^_]+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<action>[a-z\-]+?)(?:_photo\d+)?(?:\.(?:png|jpe?g))?$",
    re.IGNORECASE,
)


def parse_screenshot_name(filename: str) -> dict | None:
    """Parse a screenshot filename or basename into its contract fields.
    Returns dict(name, age:int|None, platform, date, action) or None."""
    m = NAME_RE.match(filename)
    age_raw = None
    if m:
        age_raw = m["age"]
    else:
        m = NAME_RE_4SEG.match(filename)
    if not m:
        return None
    age: int | None = None
    if age_raw and age_raw.lower() != "unk":
        try:
            age = int(age_raw)
        except ValueError:
            age = None
    return {
        "name": m["name"],
        "age": age,
        "platform": m["platform"],
        "date": m["date"],
        "action": m["action"].lower(),
    }


def classify_outcome(agent_action: str | None, installer_bucket: str) -> str:
    """Same truth table as dating-reconcile.py. incoming-like counts as an
    agent like (the installer reciprocated by sorting it)."""
    if installer_bucket == "no-opinion":
        return "no_opinion"
    agent_liked = (agent_action or "") in ("like", "super-like", "incoming-like")
    installer_positive = installer_bucket in ("like", "super-like")
    if installer_positive and agent_liked:
        return "tp"
    if installer_positive and not agent_liked:
        return "fn"
    if not installer_positive and not agent_liked:
        return "tn"
    return "fp"


def upsert_profile(
    cur,
    *,
    screenshot_basename: str,
    name: str,
    age: int | None,
    platform: str,
    encountered_on: str | None,
    agent_action: str | None,
    screenshot_path: str | None = None,
) -> int:
    """Insert-or-fetch a profile row keyed on screenshot_basename. Returns id.
    On conflict only screenshot_path is refreshed (files move between dirs);
    identity fields are immutable once written."""
    cur.execute(
        """INSERT INTO dating_profiles
               (screenshot_basename, screenshot_path, name, age, platform,
                encountered_on, agent_action)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (screenshot_basename) DO UPDATE
               SET screenshot_path = COALESCE(EXCLUDED.screenshot_path,
                                              dating_profiles.screenshot_path)
           RETURNING id""",
        (screenshot_basename, screenshot_path, name, age, platform,
         encountered_on, agent_action),
    )
    return cur.fetchone()[0]


def record_review(cur, profile_id: int, installer_bucket: str, source: str) -> str:
    """Insert a review row and sync the recovery queue. Returns the computed
    outcome. Latest review per profile wins; older rows are the audit trail."""
    if installer_bucket not in BUCKETS:
        raise ValueError(f"invalid bucket: {installer_bucket!r}")
    cur.execute("SELECT agent_action FROM dating_profiles WHERE id = %s", (profile_id,))
    row = cur.fetchone()
    if not row:
        raise LookupError(f"no dating_profiles row with id {profile_id}")
    outcome = classify_outcome(row[0], installer_bucket)
    cur.execute(
        """INSERT INTO dating_reviews (profile_id, installer_bucket, outcome, source)
           VALUES (%s, %s, %s, %s)""",
        (profile_id, installer_bucket, outcome, source),
    )
    sync_recovery_queue(cur, profile_id, outcome)
    return outcome


def sync_recovery_queue(cur, profile_id: int, outcome: str) -> None:
    """False negatives belong on the lost list; nothing else does. Recovered
    rows are history and never deleted - only a still-pending row is withdrawn
    when a correction flips the outcome away from FN."""
    if outcome == "fn":
        cur.execute(
            """INSERT INTO dating_recovery_queue (profile_id)
               VALUES (%s)
               ON CONFLICT (profile_id) DO NOTHING""",
            (profile_id,),
        )
    else:
        cur.execute(
            "DELETE FROM dating_recovery_queue WHERE profile_id = %s AND status = 'pending'",
            (profile_id,),
        )


def latest_reviews_subquery() -> str:
    """SQL fragment: latest review row per profile (DISTINCT ON)."""
    return (
        "SELECT DISTINCT ON (profile_id) profile_id, installer_bucket, outcome, source, reviewed_at "
        "FROM dating_reviews ORDER BY profile_id, reviewed_at DESC"
    )
