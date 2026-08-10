---
name: restaurant-booking
description: >
  Book a restaurant table via TheFork (Lisbon-strong). Triggers on natural-language
  booking requests from Discord. Handles the full flow: parse intent, drive TheFork
  via Playwright, soft-confirm with the installer via Discord reaction, submit booking, and
  optionally create a Google Calendar event.
---

# Restaurant Booking Plugin

## When to invoke

Invoke this skill when the installer says anything in Discord like:

- "book me a table at [restaurant] for [time] [party]"
- "reserve [restaurant] tomorrow at 1pm for 4"
- "can you book Contrabando Saldanha for lunch Friday, party of 6"
- "book the Contrabando https://www.thefork.com/restaurant/... for 8 people at 13:00"

Do NOT invoke for:
- Restaurants not on TheFork (redirect to the installer with the restaurant's direct website)
- Past dates
- Requests where intent_confidence < 0.7 (ask for clarification first)

## Step-by-step execution

### 1. Parse the intent

```bash
python3 $CHASSIS_HOME/plugins/restaurant-booking/scripts/parse-booking-intent.py \
  "<the installer's free-text message>"
```

Parse the JSON output. If `intent_confidence < 0.7`, reply to the installer asking for
clarification before continuing. Do NOT proceed with a low-confidence parse.

Example clarification message:
> I can see you want to book somewhere, but I'm not sure about the date/time/party size.
> Could you rephrase? e.g. "book Contrabando Saldanha for 4 tomorrow at 1pm"

### 2. If restaurant_url_hint is null, confirm the URL with the installer

TheFork has two Contrabando locations. When `restaurant_url_hint` is null and
multiple locations might match the name:

Reply to the installer with the options and ask which one:
> "Found two Contrabando locations on TheFork. Which one?
>   A: Saldanha - https://www.thefork.com/restaurant/contrabando-restaurante-e-bar-saldanha-r832103
>   B: 24 de Julho - https://www.thefork.com/restaurant/contrabando-restaurante-e-bar-24-de-julho-r362875"

The installer replies "A" or "B" (or pastes a URL) - then proceed.

### 3. Run the booking flow

```bash
python3 $CHASSIS_HOME/plugins/restaurant-booking/scripts/book-restaurant.py \
  --restaurant-url "<THEFORK_URL>" \
  --restaurant-name "<NAME>" \
  --datetime "<ISO8601>" \
  --party-size <N> \
  [--notes "<special requests>"] \
  [--dry-run]
```

This script:
- Fetches TheFork credentials from Vaultwarden (`thefork-credentials` item)
- Launches headless Chromium, logs in, navigates to the restaurant
- Selects date, time, and party size
- Screenshots the pre-confirm form
- Calls `confirm-via-discord.py` (sends screenshot + summary to Discord, waits for reaction)
- On the installer's checkmark reaction: clicks Confirm, captures confirmation number
- On X reaction or timeout: aborts

### 4. Report outcome

On success, report back to the installer in Discord:
> "Booked! Contrabando Saldanha on Thursday 15 May at 13:00, party of 4. Confirmation: #ABC123."

Branch on the exit code. Do not paraphrase these into each other.

| Exit | Say |
|---|---|
| 0 | "Booked! Contrabando Saldanha on Thursday 15 May at 13:00, party of 4. Confirmation: #ABC123." |
| 2 | "Booking aborted. No reservation made." |
| 3 | "Dry run only. Nothing was submitted. Screenshot: [path]" |
| 4 | "TheFork blocked the automated browser, so I could not read the page at all. Nothing was submitted. This says nothing about whether tables are free - book directly at [URL] if you need it today." |
| 5 | "I reached the booking form and could not fill it (reason: [reason], missing: [fields]). I do NOT know whether the restaurant has availability - the form is either full or broken and I cannot tell which from here. Screenshot: [path]" |
| 1 with `submitted_outcome_unknown` | "I clicked reserve and could not read a confirmation back. A reservation may exist. Check the TheFork account before I retry." |

**Never turn exit 4 or exit 5 into "no availability" or "the restaurant is
full".** The script does not know that and neither do you. A moved selector and
a fully booked Saturday produce the same result here, and the operator's next
move is opposite in each case. Report what was observed, then say the screenshot
is the way to tell.

## Dry-run smoke test (before real use)

To test the flow without actually booking:

```bash
python3 $CHASSIS_HOME/plugins/restaurant-booking/scripts/book-restaurant.py \
  --restaurant-url "https://www.thefork.com/restaurant/contrabando-restaurante-e-bar-saldanha-r832103" \
  --restaurant-name "Contrabando Saldanha" \
  --datetime "2026-05-15T13:00:00+01:00" \
  --party-size 4 \
  --dry-run
```

Exit code 3 = dry run complete. Check the screenshot saved to
`logs/booking-*-preconfirm.png`.

**As of 2026-08-10 this returns exit 4, not 3.** TheFork serves a bot-detection
interstitial to automated browsers and the plugin stays `enabled: false` until an
anti-bot posture is decided. See the status section in the plugin README before
telling anyone this flow works.

## Google Calendar setup (one-time, optional)

To enable automatic calendar event creation after a booking:

1. Create a Google Cloud project (or use the existing ${ASSISTANT_NAME} project)
2. Enable the Google Calendar API
3. Create OAuth2 credentials (Desktop app type)
4. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to $CHASSIS_HOME/.env
5. Run the one-time authorization:
   ```bash
   python3 $CHASSIS_HOME/plugins/restaurant-booking/scripts/create-calendar-event.py --setup
   ```

If calendar is not set up, the booking still completes - the calendar step is
non-fatal and the installer can create the event manually.

## Vaultwarden prerequisite

The booking flow requires a Vaultwarden item named `thefork-credentials` with:
- **username**: the installer's TheFork email address
- **password**: the installer's TheFork password

The installer adds this item themselves in Vaultwarden. The plugin never stores or logs credentials.

## Known limitations (V1)

- **TheFork blocks automated browsers.** HTTP 403 plus an interstitial, escalating
  per IP. Detected and reported as exit 4. The flow cannot complete until this is
  resolved, and retrying in a loop makes it worse for the operator's own browsing.
- TheFork UI changes break Playwright selectors, and the current selectors were
  written against a form that no longer exists. Check `logs/booking-*-error.png`
  or the screenshot named in the exit-5 payload.
- If the requested time is not available, the script takes the nearest slot within
  `time_slot_tolerance_minutes` and shows it in the soft-confirm message. If
  nothing is within tolerance it exits 5 rather than guessing why.
- With `confirm_user_id` unset, any non-bot member of the confirm channel can
  approve a booking made in the operator's name.
- The `--dry-run` screenshot shows the form state BEFORE time/date/party-size are
  submitted (depends on TheFork's SPA update cycle). The screenshot may look different
  from the final confirmed form.
- Google Calendar event creation requires one-time OAuth setup (see above).

## Future chassis port

This plugin directory is structured to be cleanly portable to `scrollinondubs/behalfbot`
via `git mv plugins/restaurant-booking/ chassis/plugins/restaurant-booking/`.
No <assistant>-specific deps other than `scripts/_loadenv.py` (path is parameterized).
