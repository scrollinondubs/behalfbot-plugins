#!/usr/bin/env python3
"""chef_plant_count.py - deterministic plant-diversity and repetition analysis.

The load-bearing, testable core of the chef skill. It maps free-text food-log
item names onto canonical plant species via the shipped taxonomy, counts
DISTINCT plants over a trailing window, and flags monotony in proteins and in
genuinely high-mercury fish.

Scope, deliberately narrow:

- A plant COUNT is defensible from photo-derived logs because it does not depend
  on portion grams. You either ate a leek or you did not.
- This module NEVER estimates micronutrients, deficiency, or physiological
  status. It reports what the log shows, not what anyone's body is doing. That
  line is the whole design.
- Mercury flagging is variety-framed and species-gated. Only genuinely
  high-mercury fish flag. Salmon never does.

The model layers on top: it decomposes composite dishes the token mapper cannot
see ("bolognese sauce" -> tomato + onion) and writes the advisory copy. This
module gives it a deterministic, reproducible baseline.

CLI:
    python3 chef_plant_count.py --days 7 [--json]

Reads the meal tables written by the companion food-logging plugin. Prints a
JSON summary suitable for both the heartbeat gate and the prompt's input.

Env:
    CHEF_TAXONOMY_PATH   taxonomy JSON        (default: ../data/plant-taxonomy.json)
    CHEF_PLANT_TARGET    weekly plant target  (default: 30)
    CHEF_MEALS_TABLE     meals table name     (default: bfl_meals)
    CHEF_DAYS_TABLE      days table name      (default: bfl_days)
    BEHALFBOT_PG_DSN | CHASSIS_PG_DSN         Postgres DSN
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from collections import Counter
from typing import Iterable

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_TAXONOMY_PATH = PLUGIN_ROOT / "data" / "plant-taxonomy.json"
DEFAULT_PLANT_TARGET = 30


def taxonomy_path() -> pathlib.Path:
    explicit = os.environ.get("CHEF_TAXONOMY_PATH", "").strip()
    return pathlib.Path(explicit).expanduser() if explicit else DEFAULT_TAXONOMY_PATH


def plant_target() -> int:
    raw = os.environ.get("CHEF_PLANT_TARGET", "").strip()
    if not raw:
        return DEFAULT_PLANT_TARGET
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PLANT_TARGET


def load_taxonomy(path: pathlib.Path | None = None) -> dict:
    with open(path or taxonomy_path(), encoding="utf-8") as fh:
        return json.load(fh)


def _normalize(name: str) -> str:
    """Lowercase, strip, fold the accents that show up in vision output."""
    s = name.lower().strip()
    s = (s.replace("ñ", "n").replace("é", "e").replace("è", "e")
          .replace("ç", "c").replace("ã", "a").replace("í", "i")
          .replace("ó", "o").replace("ü", "u").replace("á", "a"))
    s = re.sub(r"\s+", " ", s)
    return s


class PlantMapper:
    """Resolves free-text item names to canonical plant species."""

    def __init__(self, taxonomy: dict | None = None):
        self.tax = taxonomy or load_taxonomy()
        # Reverse lookup: synonym -> canonical species.
        self._syn: dict[str, str] = {}
        for species, synonyms in self.tax.get("plants", {}).items():
            self._syn[_normalize(species)] = species
            for syn in synonyms:
                self._syn[_normalize(syn)] = species
        self._non_plants = {_normalize(x) for x in self.tax.get("non_plants", [])}
        mercury = self.tax.get("high_mercury_fish", {})
        self._mercury_tokens: dict[str, str] = {}
        for fish, tokens in mercury.get("match_tokens", {}).items():
            for tok in tokens:
                self._mercury_tokens[_normalize(tok)] = fish
        self._mercury_meta = mercury
        self._low_mercury = {_normalize(x) for x in self.tax.get("low_mercury_do_not_flag", [])}

    def is_non_plant(self, name: str) -> bool:
        return _normalize(name) in self._non_plants

    def resolve_plant(self, name: str) -> str | None:
        """Canonical plant species for a free-text item, or None.

        None means: a known non-plant, or a token the deterministic mapper
        cannot resolve. Unknowns are left for the model to decompose. The module
        never guesses a plant it is not sure about - a count that only ever goes
        up must not be inflated by fuzzy matching.
        """
        norm = _normalize(name)
        if not norm:
            return None
        if norm in self._syn:
            return self._syn[norm]
        if norm in self._non_plants:
            return None
        # Token-level fallback for multi-word items: "sliced red onion" -> onion,
        # without needing a synonym for every adjective permutation. Longest
        # phrase wins first so "green beans" does not resolve as "beans".
        words = norm.split()
        for phrase_len in (3, 2):
            for i in range(len(words) - phrase_len + 1):
                phrase = " ".join(words[i:i + phrase_len])
                if phrase in self._syn:
                    return self._syn[phrase]
        for w in words:
            if w in self._syn:
                return self._syn[w]
        return None

    def mercury_flag(self, name: str) -> str | None:
        """Canonical high-mercury fish key for this item, else None.

        Low-mercury species return None by design. Their repetition is a variety
        observation, never a mercury one.
        """
        norm = _normalize(name)
        if norm in self._low_mercury:
            return None
        for tok, fish in self._mercury_tokens.items():
            if re.search(rf"\b{re.escape(tok)}\b", norm):
                return fish
        return None

    def mercury_ppm(self, fish_key: str) -> float | None:
        for bucket in ("avoid_species", "good_choice_but_watch"):
            entry = self._mercury_meta.get(bucket, {}).get(fish_key)
            if entry:
                return entry.get("ppm")
        return None


# ---- Meal-level parsing --------------------------------------------------

# Separators people actually use when typing a meal by hand: "rice + egg x3 +
# salad", "cottage cheese, carrots, hummus", "omelette & salmon",
# "turkey sandwich w/ tomato".
_DESC_SPLIT = re.compile(r"\s*(?:,|\+|&|/|;| with | w/ | and )\s*", re.IGNORECASE)
# Trailing quantity noise: "egg x3", "salmon poke 2/2", "rice 1/2", "chicken 200g".
_DESC_QTY = re.compile(r"\b(?:x\s*\d+|\d+\s*/\s*\d+|\d+g|\d+\s*(?:oz|ml|pcs?))\b", re.IGNORECASE)


def split_description(description: str) -> list[str]:
    """Split a hand-typed meal description into candidate item fragments.

    Free text, so this is deliberately dumb: split on the common separators,
    strip quantity noise, hand each fragment to the same resolver the vision
    items go through. Fragments that resolve to nothing cost nothing - they land
    in `unresolved_tokens` and the count is unaffected. The alternative is to
    ignore descriptions entirely, which silently scores zero plants for every
    meal logged without a photo.
    """
    cleaned = _DESC_QTY.sub(" ", description)
    return [frag.strip(" -.\t") for frag in _DESC_SPLIT.split(cleaned) if frag.strip(" -.\t")]


def extract_items(description: str | None, vision_items_json: str | None) -> list[str]:
    """Candidate item strings from a meal row's description plus vision JSON.

    Both sources feed one list. Double-counting is not a risk: `analyze` tracks
    distinct species in a set, so an item appearing in both the description and
    the vision output resolves to the same single species either way.
    """
    items: list[str] = []
    if vision_items_json:
        try:
            parsed = json.loads(vision_items_json)
            if isinstance(parsed, list):
                for it in parsed:
                    if isinstance(it, str):
                        items.append(it)
                    elif isinstance(it, dict):
                        name = it.get("name") or it.get("item") or ""
                        if name:
                            items.append(str(name))
        except (json.JSONDecodeError, TypeError):
            pass
    if description:
        items.extend(split_description(description))
    return items


def analyze(rows: Iterable[dict], mapper: PlantMapper | None = None) -> dict:
    """Analyze meal rows into a plant-count and repetition summary.

    Each row is a dict with keys: date, description, vision_items_json.
    Returns a JSON-serializable dict. Counts only, no physiological claims.
    """
    mapper = mapper or PlantMapper()

    plant_days: dict[str, set] = {}
    plant_counts: Counter = Counter()
    mercury_hits: Counter = Counter()
    unresolved: Counter = Counter()
    days_with_meals: set = set()

    for row in rows:
        date = row.get("date")
        days_with_meals.add(date)
        items = extract_items(row.get("description"), row.get("vision_items_json"))
        for raw in items:
            species = mapper.resolve_plant(raw)
            if species:
                plant_counts[species] += 1
                plant_days.setdefault(species, set()).add(date)
                continue
            fish = mapper.mercury_flag(raw)
            if fish:
                mercury_hits[fish] += 1
            elif not mapper.is_non_plant(raw):
                unresolved[_normalize(raw)] += 1

    distinct_plants = sorted(plant_days.keys())
    mercury_report = []
    for fish, n in mercury_hits.most_common():
        mercury_report.append({
            "fish": fish,
            "appearances": n,
            "ppm": mapper.mercury_ppm(fish),
            "flag": n >= 3,  # a note only when it recurs
        })

    return {
        "distinct_plant_count": len(distinct_plants),
        "target": plant_target(),
        "distinct_plants": distinct_plants,
        "plant_appearances": dict(plant_counts.most_common()),
        "days_logged": len(days_with_meals),
        "high_mercury_fish": mercury_report,
        "unresolved_tokens": dict(unresolved.most_common(25)),
    }


# ---- DB read path --------------------------------------------------------

def _pg_dsn() -> str:
    dsn = os.environ.get("BEHALFBOT_PG_DSN") or os.environ.get("CHASSIS_PG_DSN")
    if dsn:
        return dsn
    raise RuntimeError(
        "BEHALFBOT_PG_DSN (or CHASSIS_PG_DSN) is not set. The chef plugin reads the "
        "meal tables written by the companion food-logging plugin and shares its DB "
        "contract. Format: postgresql://user:PASSWORD@host:5432/dbname"
    )


def fetch_window_rows(days: int = 7) -> list[dict]:
    """Read the trailing `days` of meals.

    Table names are configurable because the meal log is owned by a companion
    plugin, and an install that renamed its tables should not have to patch this
    file. They are interpolated rather than parameterized - Postgres does not
    accept a bound parameter in a FROM clause - so they are validated as plain
    identifiers first.
    """
    import psycopg

    meals_table = os.environ.get("CHEF_MEALS_TABLE", "bfl_meals")
    days_table = os.environ.get("CHEF_DAYS_TABLE", "bfl_days")
    for name in (meals_table, days_table):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Refusing to query table name {name!r}: not a plain identifier.")

    sql = (
        f"SELECT d.date, m.description, m.vision_items_json "  # noqa: S608 - identifiers validated above
        f"FROM {meals_table} m "
        f"JOIN {days_table} d ON m.day_id = d.id "
        f"WHERE d.date >= to_char(CURRENT_DATE - %s::int, 'YYYY-MM-DD') "
        f"ORDER BY d.date, m.meal_num"
    )

    with psycopg.connect(_pg_dsn()) as conn:
        cur = conn.cursor()
        cur.execute(sql, (days,))
        return [
            {"date": r[0], "description": r[1], "vision_items_json": r[2]}
            for r in cur.fetchall()
        ]


def main(argv: list[str]) -> int:
    days = 7
    as_json = "--json" in argv
    if "--days" in argv:
        days = int(argv[argv.index("--days") + 1])
    rows = fetch_window_rows(days)
    result = analyze(rows)
    result["window_days"] = days
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Distinct plants (last {days}d): {result['distinct_plant_count']}/{result['target']}")
        print(f"Days logged: {result['days_logged']}")
        print("Plants: " + ", ".join(result["distinct_plants"]))
        if result["high_mercury_fish"]:
            print("High-mercury fish: " + ", ".join(
                f"{f['fish']} x{f['appearances']}" for f in result["high_mercury_fish"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
