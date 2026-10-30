# Dating

Dating-app automation for a sandboxed subagent. The playbook lives in
`skills/dating.md` and the subagent's rules in `CLAUDE.md`; the manifest
(`openclaw.plugin.json`) documents every knob. Dormant until
`chassis.config.yaml > modules.dating.enabled` is true.

## Dashboard

When the chassis dashboard is running, this plugin adds a **Dating** tab at
`/dating` and an emulator panel on `/devops`. Both are declared under
`contracts.dashboard` in the manifest.

| Page | What it does |
|---|---|
| `/dating` | Keyboard-driven review of swipe screenshots (L like, S super-like, X/P pass, N no opinion, U back, arrow keys skip). Each rating is stored and the screenshot is moved the way `dating-reconcile.py` moves a hand-sorted pick. |
| `/dating/lost` | Profiles the agent passed on that you rated like or super-like. Mark each one recovered or lost. |
| `/dating/reviewed` | Latest rating per profile. Changing a bucket re-syncs the lost list. |
| DevOps panel | ADB device state, time since the recovery hook last restarted the AVD, gfxstream error canary, swipe heartbeat freshness, AVD snapshot size. |

### Setup

1. Apply the review-store migration once:
   `psql "$BEHALFBOT_PG_DSN" -f db/migrations/002_dating_swipes.sql`
2. Make sure the dashboard process has `BEHALFBOT_PG_DSN` and `psycopg` (v3).
   Without them the pages still load and show what is missing.
3. Optional env (defaults in brackets, `<home>` is `CUSTOMER_HOME`):

| Env | Meaning |
|---|---|
| `DATING_SWIPES_INBOX` | Where swipe sessions drop screenshots [`<home>/logs/dating`] |
| `DATING_RHL_PICKS_DIR` | Hand-sort tree, shared with `dating-reconcile.py` [`<home>/rhl-picks`] |
| `DATING_RHL_PROCESSED_DIR` | Rated screenshots move here [`<home>/rhl-processed`] |
| `DATING_TASTE_REFS_DIR` | False negatives are copied into `positive/` [`<home>/data/dating/taste-refs`] |
| `DATING_ADB_SERIAL` | Device the panel checks [`emulator-5554`] |
| `DATING_AVD_NAME` | AVD whose snapshot dir is sized [`Dating_Pixel`] |
| `DATING_EMULATOR_LOG_DIR` | Recovery hook log dir [`<home>/logs/scheduled`] |
| `DATING_EMULATOR_LOG` | Emulator stdout log for the gfxstream canary [unset: row hidden] |
| `DATING_SWIPE_SLOTS` | `name@hour` pairs, e.g. `dating-swipe-1@11,dating-swipe-2@15`; a slot that has not fired today by that hour fails [unset: rows hidden] |
| `DATING_SNAPSHOT_WARN_MB` | Snapshot size that flips to warn [`500`] |

Opening `/dating` registers any new inbox screenshots that match the filename
contract (`Name_Age_App_YYYY-MM-DD_action.png`) as profiles awaiting review.

## Layout

- `openclaw.plugin.json` - manifest
- `dashboard/tab.py`, `dashboard/templates/` - the `/dating` tab
- `dashboard/emulator_panel.py` - DevOps panel rows
- `scripts/` - swipe host, reconcile, verification, DB helpers
- `db/migrations/` - Postgres schema
- `tests/` - `test-emulator-state.sh`, `test_dashboard.py`
