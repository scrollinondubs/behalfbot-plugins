# BFL (Body for Life)

Quantified-self pipeline for the Body for Life program: notebook and food
photos go through vision extraction into Postgres, runs reconcile with Strava,
and meals can be enriched against USDA FoodData Central. The agent-facing
skill is `skills/bfl.md`; the manifest documents every knob. Dormant until
`chassis.config.yaml > modules.bfl.enabled` is true.

## Dashboard

When the chassis dashboard is running, this plugin adds a **BFL** tab at
`/bfl`, declared under `contracts.dashboard` in the manifest.

| Page | What it does |
|---|---|
| `/bfl` | Week grid (workout, sleep/readiness, meals, water), body composition, mindful minutes. `?week=2026-W05` picks a week. |
| `/bfl/day/<date>` | One day in full: exercises and sets, aerobic and runs, meals with macros. Forms fix an OCR'd date, rename an exercise, match or unmatch a food photo, override macros, and re-run FDC enrichment. |
| `/bfl/search?q=` | Exercises and meals matching a term. |

### Setup

- Tables come from `db/migrations/001_bfl.sql`. The dashboard reads through
  `scripts/_chassis_db.py`, so `USE_PG` and `BEHALFBOT_PG_DSN` apply as for the
  ingest scripts. If the database is unreachable the pages load with a notice.
- Photos are served from `BFL_ARCHIVE_DIR` (default `~/behalfbot-archive/bfl`).
  `BFL_ARCHIVE_EXTRA_DIRS` (os.pathsep-separated) adds older archive roots.
- Oura scores, body composition and mindfulness panels read `oura_daily`,
  `oura_sleep_sessions`, `bfl_body_composition` and `bfl_mindfulness` when an
  install has them. This plugin does not create those tables; without them the
  panels stay empty.
- "Re-run enrichment" runs `scripts/bfl-fdc-enrich.py` with the dashboard's
  own Python, so it needs `USDA_FDC_API_KEY` in that environment.

## Layout

- `openclaw.plugin.json` - manifest
- `dashboard/tab.py`, `dashboard/templates/` - the `/bfl` tab
- `scripts/` - ingest, vision extraction, enrichment, reconcile
- `db/migrations/001_bfl.sql` - Postgres schema
