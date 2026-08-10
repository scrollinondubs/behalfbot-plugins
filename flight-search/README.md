# flight-search

Search Google Flights and watch fares on routes you care about. Six tools over
the MIT-licensed [`flights`](https://pypi.org/project/flights/) package
([punitarani/fli](https://github.com/punitarani/fli)), exposed over MCP and as a
CLI, plus a daily heartbeat that only speaks up when a fare crosses its target.

No account, no API key, no credentials anywhere in this plugin. It searches and
watches. It never books, holds or pays for anything.

| Tool | What it does |
|---|---|
| `search_flights` | Prices on a route for a date |
| `search_dates` | Cheapest departure day across a range |
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

**9. Clean up.**

```bash
python3 scripts/flight_tools.py remove "$RID"
unset FLIGHT_SEARCH_STORE
```

Steps 1, 2 and 4 need network. Steps 5 to 8 are deterministic and work offline,
so a recording is safe even on conference wifi.

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

One-way only in v0.1. `fli` returns round trips as tuples with price semantics
this plugin has not verified against live data, and a guess there would put a
wrong number into a price history that later gets compared against. Round trips
are the next addition, behind a live check of what the tuple actually carries.

Filters supported: passengers (adults, children, infants in seat, infants on
lap), cabin class, specific airlines, price ceiling, max total duration,
departure and arrival hour windows, max layover, multi-airport origins and
destinations (`--from LIS,OPO`), and date ranges via `search_dates`.

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
