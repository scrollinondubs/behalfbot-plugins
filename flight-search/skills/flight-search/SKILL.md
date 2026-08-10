---
name: flight-search
description: Search Google Flights and monitor fares on tracked routes. Use when someone asks what a flight costs, when the cheapest day to fly is, or asks to be told when a fare drops. Also covers reading the daily flight-watch alert.
---

# Flight search

Six tools over the `flights` package, which scrapes Google Flights. Available as
MCP tools (`search_flights`, `search_dates`, `track_flight`, `check_prices`,
`list_tracked`, `remove_tracked`) and as a CLI at
`$FLIGHT_SEARCH_PLUGIN_DIR/scripts/flight_tools.py`.

## The one rule

**An empty result is not an answer until the plugin proves the scraper is alive.**

Everything here scrapes a page Google can change without notice. When it breaks,
the natural symptom is an empty list, which is indistinguishable from "this
route has no flights" and from "the price did not move". So the tools never hand
back a bare empty result as success. You will get one of:

- `status: "ok"` - real priced itineraries in the currency that was requested
- `status: "empty"` - empty, and a live control-route query confirmed the
  scraper works, so the emptiness is real
- `status: "error"` with an `error_kind` - anything else

**Never translate an error into "no flights" or "no price change" when you
report to a human.** That is the single failure this plugin was built to
prevent. If `error_kind` is `scraper_error`, the honest sentence is "the flight
scraper is broken, so I do not know what that fare is doing".

## Searching

```bash
python3 "$FLIGHT_SEARCH_PLUGIN_DIR/scripts/flight_tools.py" search \
  --from LIS --to JFK --date 2026-09-09 --limit 5
```

Filters worth knowing: `--adults`, `--children`, `--cabin`, `--max-stops`,
`--airlines TP,AA`, `--max-price`, `--max-duration-minutes`,
`--max-layover-minutes`, `--depart-after 6 --depart-before 20`,
`--arrive-before 23`. `--from` and `--to` take comma-separated lists for
multi-airport searches (`--from LIS,OPO --to JFK,EWR`).

Flexible dates:

```bash
python3 "$FLIGHT_SEARCH_PLUGIN_DIR/scripts/flight_tools.py" dates \
  --from LIS --to JFK --from-date 2026-09-01 --to-date 2026-09-30
```

That returns a price per departure day plus `cheapest`, `dearest` and `spread`.
Use it before `search` whenever the dates are soft, and lead the answer with the
spread: "the 13th is 70 EUR cheaper than the 12th" is the useful sentence.

One-way only in this version. A round trip is two searches and a caveat, not a
guess at what Google returned.

## Tracking

```bash
python3 "$FLIGHT_SEARCH_PLUGIN_DIR/scripts/flight_tools.py" track \
  --from LIS --to JFK --date 2026-09-09 --target-price 400 --label "NYC in September"
```

`--target-price` is required. It is the alert condition, and without one every
wobble in a volatile fare becomes a notification. If someone asks to "watch this
flight" without naming a number, ask for one - a sensible opening move is the
current cheapest fare minus ten percent.

Alerts fire on transitions, not states: crossing the target, dropping further
below an already-alerted target, breaking, and recovering. A fare sitting below
its target all week is one alert.

The daily heartbeat runs `check_prices` for you. Run it by hand only when
someone asks right now, and expect the run to have polled Google once already
that day.

## Reporting a price to a human

Lead with the number and the currency. The currency is asserted against the
request, so it is trustworthy - say it explicitly anyway, because a price with
no currency is a number with no meaning.

Include: price, currency, airline, stops, total duration, departure time. Skip
the leg-by-leg breakdown unless asked. If the cheapest option is a fourteen-hour
routing through the Azores and the next one up is three hours shorter for
twenty euros more, say that - the cheapest row is not always the answer.

## What this plugin does not do

It does not book, hold, pay for or cancel anything. It searches and it watches.
When a fare is worth acting on, propose it and let the principal decide.
