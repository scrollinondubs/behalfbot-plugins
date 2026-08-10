# flight-search

Search Google Flights and watch fares on routes you care about. Six tools over
the MIT-licensed [`flights`](https://pypi.org/project/flights/) package
([punitarani/fli](https://github.com/punitarani/fli)), exposed over MCP and as a
CLI, plus a daily heartbeat that only speaks up when a fare crosses its target.

No account, no API key, no credentials anywhere in this plugin. It searches and
watches. It never books, holds or pays for anything.

| Tool | What it does |
|---|---|
| `search_flights` | Prices on a route for a date. One-way, round trip, or multi-city |
| `search_dates` | Cheapest departure day across a range, one-way |
| `search_flexible` | Cheapest round trips across an outbound window and a return window |
| `plan_trip` | A multi-city trip that has to touch a list of cities, across flexible windows |
| `track_flight` | Register a route with a target price |
| `check_prices` | Poll tracked routes, emit alerts |
| `list_tracked` | Tracked routes with their price history |
| `remove_tracked` | Stop tracking |

## The thing to understand before using it

`flights` scrapes Google Flights. It will break, because Google changes their
response shape whenever they feel like it, and when it breaks the natural
symptom is an empty list.

An empty list is indistinguishable from "this route has no flights", and once
something is polling on a schedule it is indistinguishable from "the price did
not move". A price monitor that goes quiet when its data source dies reports
good news forever, which is worse than having no monitor.

So nothing here returns a bare empty result as success:

| Outcome | Meaning |
|---|---|
| `status: "ok"` | Real priced itineraries, in the currency that was requested |
| `status: "empty"` | Empty, and a live control-route query confirmed the scraper works, so the emptiness is real |
| `status: "error"` + `error_kind` | Everything else |

The control route is the load-bearing part. When a search comes back empty, a
second search runs against a dense route that is never legitimately empty
(JFK-LAX, roughly a month out). Also empty means the scraper is broken and the
first result means nothing: `error_kind: scraper_error`. Priced means the
scraper works and the empty result is genuine.

Three more cases are errors rather than emptiness, for the same reason:

- `unpriced` - itineraries came back with no prices attached
- `currency_mismatch` - Google answered in a currency we did not ask for, so the
  number is not comparable with the recorded history
- `dependency_missing` - the `flights` package is not installed

The heartbeat gate inherits this: a failed check emits `count: 1` with an error
payload, and the prompt template tells the model to say the fares are *unknown*,
not unchanged.

## Trip shapes, and where the price comes from

One-way, round trip and multi-city are the same call with different legs:

```bash
# one-way
python3 scripts/flight_tools.py search --from LIS --to JFK --date 2026-09-19

# round trip - one fare, not two searches
python3 scripts/flight_tools.py search --from LIS --to JFK --date 2026-09-19 --return-date 2026-09-26

# multi-city - legs in travel order
python3 scripts/flight_tools.py search \
  --leg LIS:PHX:2026-12-20 --leg PHX:SFO:2026-12-27 \
  --leg SFO:LAX:2027-01-02 --leg LAX:LIS:2027-01-06
```

**Nothing here stitches legs together.** Google prices the whole itinerary in one
shopping session: the chosen outbound is sent back as the selected flight and
Google is asked for the next leg in the context of that choice, which is exactly
what the website does when you click through a multi-city search. A price built
by adding up separate one-way searches would not be a fare anyone can book, so it
is not built that way.

Each result carries a `price` and a list of `segments`. **The price is the whole
itinerary, not a leg.** `fli` returns a tuple of results for a multi-leg trip and
every element carries a price, but those are running totals through Google's
selection flow, not per-leg fares. Verified live on 2026-08-10:

| Trip | What came back | The fare |
|---|---|---|
| LIS-JFK one-way | `442.0` | 442 EUR |
| LIS-JFK-LIS round trip | `(490.0, 490.0)` | 490 EUR, not 980 |
| LIS-PHX-SFO-LAX-LIS | `(1577.0, 1577.0, 1577.0, 1595.0)` | 1595 EUR, the last element |

So the itinerary price is the **last** element's price. `fli` agrees with itself
here: `get_booking_options` builds its booking token from `results[-1].price`,
which is the number Google is asked to honour. Each segment still reports its
own `price_at_this_step` if you want to see the ladder.

Cost note: a multi-leg search costs roughly `top_n ** (legs - 1)` requests, where
`top_n` is how many outbound candidates get expanded (default 2, max 5). A
four-leg trip at `top_n=2` took 43 to 90 seconds live. Keep it low, and never put
a multi-city search on a tight schedule.

## Flexible dates

For a round trip with soft dates at both ends:

```bash
python3 scripts/flight_tools.py flexible --from LIS --to PHX \
  --out-window 2026-12-20:2026-12-23 --back-window 2027-01-05:2027-01-08
```

This sweeps trip **lengths**, not day pairs. Google's calendar grid answers a
round-trip query with the single cheapest (out, back) pair at a given trip
length, so every length that can land both ends inside the two windows costs one
request. Four days against four days is seven requests, not sixteen searches.
Those are indicative calendar prices; run `search` on a pair you like for real
itineraries.

For the trip that has to touch several cities:

```bash
python3 scripts/flight_tools.py plan --from LIS --visit PHX,SFO,LAX \
  --out-window 2026-12-20:2026-12-23 --back-window 2027-01-05:2027-01-08 \
  --nights PHX=6 --max-searches 4
```

`plan` ranks the date pairs with the cheap calendar grid first, then runs real
multi-city searches on the best few and reports their actual fares. **The
ranking is a heuristic and never becomes a reported price** - it prices a plain
return to the first city on the list, purely to decide which dates are worth the
expensive search. Every number in the output comes from a real itinerary search.
There is a test that holds that line.

Nights are split evenly across the cities unless you name some with `--nights`;
the last unnamed city absorbs the remainder. A date combination that returns
nothing is listed under `failures` rather than quietly dropped, and if every
combination fails you get an error, not an empty list.

`plan` is slow by construction: `max_searches` full searches, tens of seconds
each. It is a planning question you ask once, not something to schedule.

## When it says `scraper_error`

Two different things produce it, and they need different responses.

**Google is refusing this client.** The most common cause, and the one seen
during development: after a burst of searching, Google stops answering. Same
code, same minute, same IP, one machine gets prices and another gets nothing -
observed on 2026-08-10 between a macOS build of `curl_cffi` and the Linux build
in a container, with identical pinned versions. The likely mechanism is the TLS
fingerprint plus request volume, and the cure is to stop searching for a while.
It clears on its own.

**Google changed their response shape.** `fli` needs a fix or a version bump.

Telling them apart: wait an hour and try one plain search. If it works, it was
throttling. If a `parse_error` shows up rather than an empty result, it is a
shape change and the upstream needs attention.

Either way the plugin refuses to call it "no flights", which is the whole point.
The multi-leg searches are the expensive ones - a four-leg trip at `top_n=2` is
seven requests and can be dozens with a wider breadth - so a run of `plan` is the
most likely thing to trip a throttle. Space them out.

## Install

```bash
bash flight-search/setup.sh
bash flight-search/validate.sh
```

`setup.sh` is idempotent - re-running it when the pinned version is already
present is a no-op. It installs from `requirements.lock.txt`, which pins the
full transitive closure to exact versions, and refuses to run if that file is
missing. `validate.sh` is offline: it checks the pieces are present, the pin
matches, and that an empty result with a dead control route still raises rather
than returning "no flights".

Then enable it in the install's `chassis.config.yaml`:

```yaml
modules:
  flight-search:
    enabled: true
    currency: EUR
    discord_channel_id: "<your channel id>"
```

## Demo path

Reproducible from a clean install, no waiting for a real fare to move. Every
step prints JSON.

```bash
cd flight-search
export FLIGHT_SEARCH_STORE=/tmp/flight-demo.json   # keep the demo out of the real store
NEAR=$(date -d '+30 days' +%F)                     # macOS: date -v+30d +%F
LATE=$(date -d '+44 days' +%F)                     # macOS: date -v+44d +%F
```

**1. Live prices on a route.** Real fares, straight off Google.

```bash
python3 scripts/flight_tools.py search --from LIS --to JFK --date "$NEAR" --limit 3
```

**2. The cheapest day across two weeks.** This is the one that gets a reaction -
`spread` is what a flexible traveller is actually buying.

```bash
python3 scripts/flight_tools.py dates --from LIS --to JFK --from-date "$NEAR" --to-date "$LATE"
```

**3. Track it, deliberately below the current price so nothing fires yet.**
Copy the `id` from the output into `RID`.

```bash
python3 scripts/flight_tools.py track --from LIS --to JFK --date "$NEAR" \
  --target-price 300 --label "demo route"
RID=$(python3 scripts/flight_tools.py list | python3 -c 'import json,sys; print(json.load(sys.stdin)["routes"][0]["id"])')
```

**4. A check with nothing to report.** Live search, price recorded, no alert.

```bash
python3 scripts/flight_tools.py check | head -20
```

**5. A price drop.** Exactly one alert, carrying the previous price for context.

```bash
python3 scripts/flight_tools.py check --simulate-drop "$RID=249"
```

**6. The same price again.** Silence - alerts fire on transitions, not states.
This is the step that shows it will not nag.

```bash
python3 scripts/flight_tools.py check --simulate-drop "$RID=249"
```

**7. A broken scraper.** The important one. Exits nonzero, `status: "error"`,
`error_kind: "scraper_error"`, and the alert says the fare is unknown rather
than unchanged.

```bash
python3 scripts/flight_tools.py check --simulate-failure all; echo "exit=$?"
```

**8. The heartbeat gate, free when nothing moved.**

```bash
FLIGHT_SEARCH_FORCE=1 bash scripts/gather-flight-prices.sh
FLIGHT_SEARCH_FORCE=1 FLIGHT_SEARCH_SIMULATE_DROP="$RID=199" bash scripts/gather-flight-prices.sh
```

The first prints `{"count": 0, ...}` and costs nothing. The second prints
`{"count": 1, "alert_kinds": ["target_met"], ...}`, which is what wakes the
model.

**9. The trip that is actually worth demoing.** A round trip, then the real
multi-city planning question. Both live; the plan step takes a couple of minutes,
so start it and talk over it.

```bash
python3 scripts/flight_tools.py search --from LIS --to JFK --date "$NEAR" --return-date "$LATE" --limit 2
python3 scripts/flight_tools.py plan --from LIS --visit PHX,SFO,LAX \
  --out-window 2026-12-20:2026-12-23 --back-window 2027-01-05:2027-01-08 --max-searches 2
```

**10. Clean up.**

```bash
python3 scripts/flight_tools.py remove "$RID"
unset FLIGHT_SEARCH_STORE
```

Steps 1, 2, 4 and 9 need network. Steps 5 to 8 are deterministic and work
offline, so the part of the recording that shows the alert and failure paths is
safe even on conference wifi.

## Configuration

| Key | Default | What it controls |
|---|---|---|
| `enabled` | `false` | Master switch |
| `currency` | `EUR` | Requested from Google and asserted on the response. A reply in any other currency is an error, never a recorded price. |
| `store_path` | `${CHASSIS_HOME}/data/flight-search/tracked-routes.json` | Tracked routes and price history. Must be on bind-mounted storage or every tracked route dies with the container. |
| `state_dir` | `${CHASSIS_HOME}/scheduled-tasks` | The heartbeat's once-per-day marker and the last check result |
| `discord_channel_id` | *(none)* | Where alerts get posted. Install-specific. |
| `max_history_points` | `60` | Price points kept per route, roughly two months of daily checks |
| `error_repeat_days` | `3` | How long a still-broken route stays quiet before shouting again. The first failure always alerts. |
| `canary_route` | `JFK-LAX` | The control route. Must be dense enough that an empty answer is never legitimate. |
| `canary_lead_days` | `30` | How far ahead the control route is priced |
| `top_n` | `2` | Expansion breadth for multi-leg trips. Cost is roughly `top_n ** (legs - 1)` requests. |
| `max_plan_searches` | `4` | Ceiling on full itinerary searches in one `plan_trip` call |

## Heartbeat

Register `flight-watch` in the install's heartbeat config, pointed at
`scripts/gather-flight-prices.sh` with
`scheduled-tasks/flight-watch-prompt.md.template` as the prompt. Daily cadence,
condition `threshold`, criticality `background` so conservation mode suppresses
it - a fare alert is never worth spending a constrained budget on.

The gate is free. It exits `count: 0` without touching a model when no route is
tracked, when nothing moved, and on every dispatcher tick after the day's single
poll. It polls Google at most once per calendar day regardless of how often the
dispatcher ticks. `FLIGHT_SEARCH_FORCE=1` bypasses the day gate for a demo.

The one place it deliberately differs from `chef`'s gate: a failure is loud. An
unreadable store, a check that produced no output, or a route that could not be
priced all emit `count: 1` with an error payload. Do not "fix" that to match.

## Alert policy

A target price is required at track time. It is the alert condition, and without
one every wobble in a volatile fare becomes a notification. Alerts fire on
transitions rather than states:

- **target_met** - the fare crossed its target, or dropped further below a
  target it had already crossed
- **error** - the route could not be priced, first failure and then at most once
  every `error_repeat_days`
- **recovered** - a broken route is being priced again

A fare sitting below its target for a week is one alert, not seven.

## Scope

Trip shapes: one-way, round trip, and multi-city up to six legs. All three can be
searched, and all three can be tracked.

Filters supported: passengers (adults, children, infants in seat, infants on
lap), cabin class, specific airlines, price ceiling, max total duration,
departure and arrival hour windows, max layover, multi-airport origins and
destinations (`--from LIS,OPO`), and date ranges via `search_dates`,
`search_flexible` and `plan`.

Hour windows apply to the first leg only. Google takes them per segment, but
"leave after 6am" rarely means the same thing on a return four weeks later, and
applying it to every leg would silently drop itineraries nobody asked to exclude.

Not supported: reordering the cities in a `plan` call. The visit list is followed
in the order given. Trying every permutation of three cities would be six times
the searches for a question that usually has a natural answer, so pick the order
and re-run if you want to compare.

## Layout

```
flight-search/
  openclaw.plugin.json                       manifest: config schema, contracts, declarations
  .claude-plugin/plugin.json                 Claude Code compatibility shim
  setup.sh / validate.sh                     pinned dependency setup, offline smoke check
  requirements.txt                           the direct dependency, exact version
  requirements.lock.txt                      full transitive closure, exact versions
  scripts/flight_tools.py                    the six tools, plus the CLI
  scripts/flight_search_mcp.py               stdio MCP server over the same functions
  scripts/gather-flight-prices.sh            the heartbeat gate
  scheduled-tasks/flight-watch-prompt.md.template
  skills/flight-search/SKILL.md              the agent-facing skill
  tests/test_flight_search.py                offline suite, fake `fli`, no network
  tests/test-gather-gate.sh                  offline suite for the gate
```

## Tests

```bash
python3 flight-search/tests/test_flight_search.py
bash flight-search/tests/test-gather-gate.sh
```

Both are stdlib-only with no network, per this repo's plugin-test contract. The
python suite injects a fake `fli` into `sys.modules` before importing the module
under test, which is why the real import in `flight_tools.py` is lazy. Leave it
lazy.

What the suites cannot catch: `fli`'s own drift against Google. Nothing offline
can. That is what the canary covers at runtime and what "Verifying a bump" below
covers at upgrade time.

## Verifying a bump

The dependency is a scraper, so a version bump is exactly when its behaviour is
most likely to have moved. After changing the pin in `requirements.txt`:

1. Regenerate the lock on the platform the chassis runs on, not a laptop:
   `docker run --rm python:3.12-slim sh -c "pip install -q flights==<new> && pip freeze"`
2. `bash flight-search/setup.sh && bash flight-search/validate.sh`
3. Run demo steps 1 and 2 live and confirm prices come back in the configured
   currency
4. Run demo steps 5 to 7 and confirm the alert and failure paths still behave
5. `python3 flight-search/tests/test_flight_search.py`

Note that `requirements.lock.txt` carries no `--hash` pins. `curl_cffi` ships
platform-specific binary wheels, so a hash set is valid for exactly one arch and
one Python minor and would fail every other host. Exact version pinning is what
protects the install; the hashes would add nothing and break arm64.

## Upstream

`flights` 0.9.0, MIT. The licence was checked in the upstream repo
(`LICENSE.txt`), not inferred from the README - per `CONTRIBUTING.md`, a repo
with no licence file is all rights reserved whatever its README implies.

It is one maintainer, so the wrapper here is deliberately ours and deliberately
small: the surface this plugin depends on is a handful of filter models and two
search classes, all resolved in one place (`_Fli` in `flight_tools.py`). If the
upstream stops, that is the one class to repoint at another source.
