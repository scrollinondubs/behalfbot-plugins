# restaurant-booking - Behalf.bot Chassis Plugin

A TheFork-based restaurant booking plugin for the Behalf.bot chassis pattern. Handles
the full booking flow: parse free-text intent, drive TheFork via Playwright, soft-confirm
with the operator via Discord, submit the booking, and optionally create a Google Calendar event.

**Aggregator:** TheFork (`thefork.com` / `thefork.pt`)
**Target locale:** Lisbon (works anywhere TheFork operates)
**Status:** dormant, and currently blocked upstream. Read the next section before using it.

---

## Current status: TheFork blocks automated browsers

Smoke-tested 2026-08-10, the first time this plugin had ever been run. TheFork
answers automated traffic with an HTTP 403 and a branded interstitial:

> Access is temporarily restricted
> We detected unusual activity from your device or network.
> Reasons may include: rapid taps or clicks, JavaScript disabled or not working,
> automated (bot) activity on your network, use of developer or inspection tools.

What was observed, in order:

| Configuration | Restaurant page | Sign-in page |
|---|---|---|
| `curl` with a browser user agent | 403 | 403 |
| Playwright default headless (headless shell, `HeadlessChrome` in the UA) | 403 | 403 |
| Playwright `channel: 'chromium'` with a desktop user agent | 200, page and booking widget fully rendered | 403 |
| Same configuration, a few requests later | 403 | 403 |

Three things follow from that table.

**The block escalates at the network level.** The one configuration that loaded a
page loaded exactly one before the whole IP started getting 403s, including
configurations that had worked a minute earlier. This is not a user-agent trick
that was missed; it is detection with memory.

**The sign-in route is refused separately.** `/signin`, `/login` and `/entrar` all
returned 403 even while the restaurant page rendered. Login is the harder wall.

**The selectors are dead independently of all of the above.** The one page that
did render showed a multi-step wizard - a calendar, then a time step, then a
party-size step - with no `select[name*="guest"]`, no `input[type="date"]` and no
`data-testid` attributes at all. Every selector this plugin carries was written
against a form that no longer exists.

Getting past the first wall means stealth-patched browser paths, residential
proxies, or request pacing. **That is an anti-bot posture decision, not an
engineering task, and it has not been made.** Nothing in this plugin patches a
fingerprint. Until that ruling exists, the booking flow cannot complete and the
plugin stays `enabled: false`.

The hardening in place now is the part that survives the ruling either way: the
block is detected and reported as a block, never as a booking failure and never
as an absence of tables.

TheFork is also mid-acquisition (American Express buying it from Tripadvisor),
so a UI overhaul under new ownership is plausible within the year. Keep the
selector layer thin.

---

## Directory structure

```
restaurant-booking/
├── README.md                         # this file
├── openclaw.plugin.json              # manifest: metadata, config schema, contracts
├── setup.sh                          # idempotent dependency setup (Linux-first)
├── validate.sh                       # offline post-setup smoke check
├── package.json / package-lock.json  # playwright, pinned exactly
├── skills/
│   └── restaurant-booking.md         # invocation rules + step-by-step
├── scripts/
│   ├── parse-booking-intent.py       # free-text -> structured JSON via Claude Haiku
│   ├── book-restaurant.py            # Playwright-driven TheFork booking flow
│   ├── confirm-via-discord.py        # Discord soft-confirm + reaction polling
│   └── create-calendar-event.py      # Google Calendar event on confirmed booking
├── config/
│   └── restaurant-booking.yaml       # per-installer settings
├── tests/
│   ├── test_parse_intent.py          # intent parser (mocked Haiku API)
│   └── test_booking_outcomes.py      # refusal paths, exit codes, credential handling
└── logs/                             # per-booking audit logs + screenshots (gitignored)
```

---

## Exit codes

`book-restaurant.py` and the Playwright flow it generates share one contract. The
orchestrator branches on these, so they are part of the plugin's public surface.

| Code | Meaning | What to do |
|---|---|---|
| 0 | Booking confirmed, with a confirmation reference read back from the page | Nothing |
| 1 | Error. Includes `submitted_outcome_unknown`: the reserve button was clicked and no reference could be read back | Check the account. A reservation may exist |
| 2 | Aborted. The operator reacted with the cross, or the confirm timed out. Nothing was submitted | Nothing |
| 3 | Dry run complete. Stopped at the pre-confirm screenshot | Look at the screenshot |
| 4 | `blocked_by_bot_detection`. TheFork served an interstitial. Nothing was read, nothing was submitted | Do not retry in a loop. Each attempt deepens the block |
| 5 | `no_usable_slot`. The form could not be filled completely | Open the screenshot. See below |

**Code 5 is never a claim that the restaurant is full.** A moved selector and a
fully booked Saturday are indistinguishable from inside the browser, and the two
call for opposite responses from the operator. The payload carries `reason`
(`selector_not_found`, `slot_list_empty`, `no_slot_within_tolerance`,
`form_fields_not_set`), `missing_fields` and `slots_seen` so the difference can
be read rather than guessed. The string "no availability" does not appear
anywhere in this plugin, and a test asserts it stays that way.

---

## Prerequisites

### 1. TheFork credentials in Vaultwarden

Add a Vaultwarden item named `thefork-credentials`:
- **username**: your TheFork email
- **password**: your TheFork password

The booking script fetches these fresh at invocation time via the chassis
`scripts/bw-fetch.sh`. They are never written to `.env`, never written to the
per-booking session file, and the password reaches the browser subprocess only
as an environment variable. Verified 2026-08-10: the item resolves and both
fields are populated.

### 2. Playwright and Node.js

```bash
bash setup.sh
```

Idempotent, Linux-first, safe to re-run. It installs from the committed lockfile
with `npm ci` and downloads Chromium with the local playwright binary. The full
Chromium build is required, not the headless shell - the shell advertises
`HeadlessChrome` in its user agent and is refused on every request.

### 3. Python 3

Stdlib only. No pip install step.

### 4. Google Calendar (optional)

To enable automatic calendar events after booking:

1. Create or use a Google Cloud project with the Calendar API enabled
2. Create OAuth2 credentials (Desktop app type) in the Google Cloud Console
3. Add to `$CHASSIS_HOME/.env`:
   ```
   GOOGLE_CLIENT_ID=<your-client-id>
   GOOGLE_CLIENT_SECRET=<your-client-secret>
   ```
4. Run once to authorize:
   ```bash
   python3 scripts/create-calendar-event.py --setup
   ```

If not set up, the booking completes without a calendar event (non-fatal).

---

## Quick start

### Offline checks (these pass today)

```bash
bash validate.sh
python3 tests/test_booking_outcomes.py
python3 tests/test_parse_intent.py
```

### Dry-run smoke test

```bash
CHASSIS_HOME=$HOME/.behalfbot python3 scripts/book-restaurant.py \
  --restaurant-url "https://www.thefork.pt/restaurante/contrabando-restaurante-e-bar-saldanha-r832103" \
  --restaurant-name "Contrabando Saldanha" \
  --datetime "2026-08-19T13:00:00+01:00" \
  --party-size 2 \
  --dry-run
```

Runs everything up to the pre-confirm screenshot and stops. It does not call
Discord and does not submit anything.

**As of 2026-08-10 this exits 4**, not 3, and writes a `-blocked.png` screenshot
of the interstitial. That is the plugin working correctly against a site that is
refusing it. Exit 3 with a `-preconfirm.png` is the intended result and requires
the access problem to be solved first.

Whichever code comes back, open the screenshot. A page that loaded wrong still
screenshots successfully, which is how the original version of this plugin got
written against markup nobody had looked at.

### Intent parser

```bash
python3 scripts/parse-booking-intent.py "book Contrabando Saldanha for 4 people tomorrow at 1pm"
```

---

## Booking flow detail

1. **Credential fetch** - TheFork username and password from Vaultwarden at start, never cached
2. **Browser launch** - Chromium via Playwright, `channel: 'chromium'`, headless
3. **Login** - navigates to the configured `thefork_login_url`, fills credentials, submits
4. **Restaurant navigation** - goes to the provided TheFork URL
5. **Block check** - after each navigation. A detected interstitial stops the run at exit 4
6. **Form fill** - party size, date, and time slot (nearest within `time_slot_tolerance_minutes`)
7. **Completeness gate** - if any of the three did not get set, stop at exit 5. A half-filled form is never sent for approval
8. **Pre-confirm screenshot** - captures form state before submission
9. **Discord soft-confirm** - sends screenshot and summary, adds the two reactions, polls every 10s
10. **On confirm** - clicks reserve, reads the confirmation reference
11. **On abort, timeout, or any failure to reach Discord** - closes the browser, exits 2, submits nothing
12. **Calendar event** - Google Calendar event on a verified success, if configured

Step 11 is the important one. Consent failures fail closed: if the Discord
message cannot be sent, if the poll errors, if the JSON comes back malformed,
the answer is no.

---

## Who can approve

The soft-confirm gate is the entire safety property of this plugin, so it is
worth being precise about who can trip it.

- Bot reactions never count, including the plugin's own two reactions, which
  exist only as tap targets.
- With `confirm_user_id` set, only that Discord user's reaction counts.
- With it empty, any non-bot member of the channel can approve a booking made in
  the operator's name. `setup.sh` and `validate.sh` both warn about this. Set it.
- The cross is checked before the checkmark, so if both are present the run
  aborts.

---

## Demo path for the course recording

**Blocked pending the anti-bot ruling.** Do not schedule a recording against
this until a dry run returns exit 3 with a screenshot of a correctly loaded
booking form.

When it is unblocked, this is the script:

1. **Restaurant:** Contrabando Restaurante e Bar - Saldanha, Av. Duque de Ávila 169d,
   Lisboa. Chosen because it takes TheFork bookings, sits in the middle of the
   -50% promotion band most days, and is a walk-in-friendly room where a
   cancelled table costs nobody anything.
2. **Slot:** a weekday lunch, 13:00, party of 2. Off-peak, always the least
   contended slot of the week, and the least disruptive to cancel.
3. **Date:** 2 to 5 days out. Far enough that slots exist, near enough that the
   calendar does not need paging.
4. **Refusals first, on camera:**
   - `--dry-run` and show the pre-confirm screenshot. Nothing submitted.
   - Full run, react with the cross. Show exit 2 and an empty TheFork account.
   - Full run with `--timeout 60`, react with nothing. Show the timeout abort.
5. **Only then the happy path:** full run, react with the checkmark, show the
   confirmation reference and the calendar event.
6. **Cancel the booking immediately** through TheFork's own confirmation email
   or the account's reservations page, on camera. The cancellation is part of
   the demo, not cleanup afterwards.

The `--timeout` flag genuinely works for step 4 now. It used to be silently
overridden by the 600s config value, which made the timeout path a ten-minute
wait to demonstrate, which meant it was never demonstrated.

---

## Troubleshooting

**Exit 4, or "Access is temporarily restricted" in the screenshot**
- TheFork's bot detection. Read the status section at the top of this file.
- Do not retry in a loop. The block escalates per network and it applies to the
  operator's own browser on the same connection.

**Exit 5**
- The form did not fill. Open the screenshot named in the payload.
- If the page rendered but the fields were not found, the selectors need
  extending. If the page did not render, it is the block wearing a different hat.

**"Could not fetch TheFork credentials from Vaultwarden"**
- Verify the item `thefork-credentials` exists with `username` and `password`
- Check the session: `bw status`
- Check `CHASSIS_HOME` points at the install that owns `scripts/bw-fetch.sh`

**"Google Calendar not authorized"**
- Run `python3 scripts/create-calendar-event.py --setup`

**"DISCORD_BOT_TOKEN not found"**
- Ensure the Vaultwarden item `discord-bot-token` is reachable via `bw-fetch.sh`

---

## Configuration

Edit `config/restaurant-booking.yaml`:

| Key | Meaning |
|---|---|
| `discord_channel_id` | Where the soft-confirm message is posted. Falls back to `DISCORD_PRIMARY_CHANNEL_ID`; errors out rather than guessing |
| `confirm_user_id` | The only Discord user whose reaction counts. Empty means anyone in the channel |
| `confirm_timeout_seconds` | Abort after this long with no reaction (default 600). `--timeout` overrides it |
| `time_slot_tolerance_minutes` | Nearest-slot search window (default 30) |
| `vaultwarden_item_name` | Vaultwarden item holding TheFork credentials |
| `thefork_base_url` | Locale root |
| `thefork_login_url` | Sign-in URL, separate because that route moves on its own |
| `gcal_calendar_id` | Which calendar to add events to |

---

## Chassis portability

Set `CHASSIS_HOME` to the install root that owns `scripts/bw-fetch.sh` and
`.env`. The scripts fall back to walking up from their own location, which only
resolves correctly for one of the layouts this plugin ships into, so on any
non-default layout the env var is not optional.

---

## Scope

Implemented: TheFork via Playwright, free-text intent parsing via Claude Haiku,
Discord soft-confirm with screenshot and reaction polling, Google Calendar on
success, dry-run mode, block and slot-failure detection, offline tests for the
refusal paths.

Deferred: phone-call automation, multi-restaurant comparison, payment on file,
an auto-book threshold, non-TheFork providers, scheduled triggers.

`omarshahine/restaurant-cli` (MIT) is the documented path if multi-provider
support is ever wanted - Resy, OpenTable and Tock behind a `Provider` interface
where adding a platform is a two-file change. Its site-automation flag turns on
stealth-patched browser paths that its own README says may breach those
platforms' terms. That flag stays off, same as the posture here.
