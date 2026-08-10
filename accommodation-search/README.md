# accommodation-search

> ## DORMANT: the supplier no longer exists
>
> **Amadeus decommissioned its Self-Service portal on 17 July 2026.** New
> registration was paused months earlier and existing keys were disabled on that
> date. There is no way to obtain credentials for this plugin, and there will not
> be. What remains at `developers.amadeus.com` is the Enterprise portal, which
> means a sales conversation and a contract, not a signup form.
>
> Amadeus confirmed the shutdown in a letter to developers, first reported by
> [PhocusWire](https://www.phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers)
> in February 2026, and the notice sits on their developer homepage today.
>
> **This plugin was written after that date, against documentation that was still
> published.** It was specified on the strength of third-party articles
> describing a free self-service tier that had already been switched off. The
> code was never wrong; the supplier was gone.
>
> **It stays here, dormant, deliberately.** It is disabled by default and every
> tool call will fail authentication. It is kept because the work that survives a
> supplier change is most of the work: a supplier-neutral tool interface with a
> second supplier already reserved, a local call ledger, three test suites, and a
> five-way distinction between an empty result and a broken integration. A
> RateHawk, Duffel or Booking.com Demand API implementation slots in behind the
> same three tools without changing a single caller.
>
> **Do not enable this plugin.** If you are here because you want accommodation
> search, the live question is which supplier replaces Amadeus, not how to get
> this one working.

Search places to stay from an agent, through the
[Amadeus Self-Service API](https://developers.amadeus.com/). Search only, no
booking.

**This is GDS and chain hotel inventory. Hotels, not apartments.** Amadeus is a
travel distribution system, so what it lists is what the trade distributes:
chain properties, GDS-connected independents, chain-operated aparthotels. Flats,
short lets and Airbnb-style listings are not in it in any form. This is not an
Airbnb replacement and nothing here should be read as one. An empty result from
this plugin is evidence about Amadeus's inventory and nothing more.

The gap closes when Booking.com affiliate approval lands, not before. The tool
interface is already shaped for it.

## One step is left, and it is not a code change

Nobody has registered an Amadeus account yet, because doing so means accepting
their terms and that is the account owner's decision, not an agent's. So:

1. Register free at [developers.amadeus.com](https://developers.amadeus.com/),
   create an app, and copy the API Key and API Secret.
2. Export them and run `validate.sh`, then the live demo:

   ```bash
   export AMADEUS_CLIENT_ID=...        # the API Key
   export AMADEUS_CLIENT_SECRET=...    # the API Secret
   bash validate.sh
   python3 scripts/demo.py --city LON
   ```

3. That is it. Everything else is built, tested and demonstrable today.

Until then the plugin is fully exercisable offline against committed response
fixtures - see the demo path below - and **every path in it has been tested that
way, including the failure paths that are hard to produce on demand against a
live account.** What offline testing cannot prove is that live credentials
authenticate and that the live API returns the shapes its documentation
describes. That is what step 2 confirms.

Credentials live in the environment and nowhere else. This plugin never reads a
credential from a file, never writes one, and scrubs both the secret and the
bearer token from anything on its way out to a model or a log. Do not put them
in a file inside this repo.

### Test keys or production keys?

Amadeus issues both, and they are different keys.

| | Test | Production |
|---|---|---|
| Data | Cached, restricted to a subset of hotel chains | Live inventory |
| Cost | Free up to a monthly allowance | Free up to the same allowance, billed above it |
| Good for | Building, CI, checking the plumbing | Quoting a real price to a real traveller |

**Recommendation: start on test, move to production before anything is
recorded or shown to a customer.** A demo that returns cached prices for three
chains is a demo of the plumbing, not of the product. `AMADEUS_ENVIRONMENT`
switches between them and defaults to `test`.

## The three tools

| Tool | What it does | Supplier calls |
|---|---|---|
| `search_accommodation` | Properties in a city or around a point, priced for a stay | 2 |
| `accommodation_details` | One property: address, location, guest ratings, and with dates also rates and policies | 2, or 3 with dates |
| `list_accommodation_offers` | Every bookable rate for one property and stay, cheapest first | 1 |

Plus one token call roughly every half hour, not one per request.

The tool arguments are supplier-neutral by design - `city_code`, `check_in`,
`max_price`, not `hotelIds` or `cityCode`. Booking.com's Demand API is meant to
slot in behind the same three tools with no caller changing, and
`tests/test_supplier_neutrality.py` fails if a supplier's vocabulary reaches a
tool schema. Ids are namespaced by the supplier that issued them
(`amadeus:MCLONGHM`) so that a second supplier cannot collide with the first.

Asking for `supplier: "booking"` today returns a clear "reserved, not
implemented" error rather than falling back to Amadeus, because a silent
fallback would be a wrong answer about which inventory was searched.

## An empty search is an error, never "nothing available"

This is the rule the whole plugin is shaped around, carried over from the
scraper-based attempt that preceded it
([#15](https://github.com/scrollinondubs/behalfbot-plugins/pull/15), closed).

A zero-result search has at least five causes that look identical from the
outside: the properties are genuinely full, the city code resolved to the wrong
city, the price ceiling filtered everything out, the test environment carries
only a subset of chains, or the supplier degraded. Only the first is a fact about
the world. So none of the tools can return an empty list - they raise a named
error with the specific next steps that apply.

And the failures are told apart from each other, which matters more here than it
sounds:

| Kind | Retrying helps? | Meaning |
|---|---|---|
| `EMPTY_RESULT` | No | Zero results, cause unknown |
| `SUPPLIER_REPORTED_NO_MATCH` | No | The supplier said explicitly that nothing matched |
| `RATE_LIMITED` (code 38194) | Yes, in a second | Too many calls per second |
| `QUOTA_EXHAUSTED` (code 38195) | No, not until next month | The month's free allowance is gone |
| `LOCAL_BUDGET_EXHAUSTED` | Only after a human raises it | This plugin's own ceiling; no request was sent |
| `AUTH_FAILED` | No | Credentials rejected, expired or revoked |

**38194 and 38195 both arrive as HTTP 429 and mean opposite things.** An agent
that collapses them into "429, back off" retries for three weeks. They are
separate kinds here, with separate advice, and there is a test named after
exactly that.

## Quota

The free monthly allowance is real and Amadeus will not tell you where you are
in it: the number is published nowhere in the API documentation, it is visible
only inside their workspace UI, and it lags by up to twelve minutes. The first
signal that it is gone is a 429 in the middle of somebody's trip planning.

So this counts locally. `var/call-ledger.json` holds a per-UTC-month count of
supplier calls by endpoint - integers and endpoint labels, no credentials, no
request parameters, no responses. Every successful result carries a `usage`
block, warns past 80%, and refuses locally at the ceiling with a failure kind
that says plainly that the supplier refused nothing.

**The default ceiling of 2000 is a working assumption, not a published figure.**
Amadeus documents only that the free allowance "varies from one API to another".
Raise it with `ACCOMMODATION_MONTHLY_CALL_BUDGET` once the account's real
allowance is visible in the workspace.

## Install

```bash
bash setup.sh      # idempotent, safe to re-run, installs nothing
bash validate.sh   # offline smoke check, no credentials needed
```

There are no third-party dependencies. That is the dependency pin, not a gap in
one - see [`requirements.txt`](requirements.txt) for the reasoning, and
`scripts/check_stdlib_only.py`, which parses every file in the plugin and fails
both `setup.sh` and `validate.sh` if an import outside the standard library ever
appears.

`validate.sh` runs the three test suites and then drives the MCP server over its
real stdio transport three times on canned data, asserting that a working search
exits 0 and that both an empty search and an exhausted quota exit 2. A check
that accepted 0 for an empty search would be checking nothing.

### Registering the MCP server

The manifest declares it under `contracts.mcpServers`, per
[`docs/MANIFEST.md`](../docs/MANIFEST.md). Where nothing consumes that yet, add
it by hand:

```json
{
  "mcpServers": {
    "accommodation-search": {
      "command": "python3",
      "args": ["/absolute/path/to/accommodation-search/scripts/mcp_server.py"]
    }
  }
}
```

## Demo path

Repeatable, and it drives the same stdio transport the agent uses, so what is on
screen is what the agent gets - error blocks included.

**Offline, no account needed.** Three fixture sets, three outcomes:

```bash
# 1. A search that works. Two hotels priced, cheapest first, with cancellation terms.
python3 scripts/demo.py --fixtures happy --city LON

# 2. The same search coming back empty. Exits 2, and the first thing on screen
#    is EMPTY_RESULT with "do not report this as nothing available".
python3 scripts/demo.py --fixtures empty --city LON

# 3. The monthly quota gone. Exits 2, and it is visibly a different failure
#    from the empty one - QUOTA_EXHAUSTED, not retryable, "the allowance resets
#    at the start of the next calendar month".
python3 scripts/demo.py --fixtures quota --city LON

# 4. One property in full: ratings with sub-scores, rates, policies.
python3 scripts/demo.py --fixtures happy --details amadeus:MCLONGHM

# 5. Every rate for one property, cheapest first.
python3 scripts/demo.py --fixtures happy --offers amadeus:ACLON371
```

Every fixture-mode call prints a banner to stderr naming the file it served
instead of the request it did not make, and every result carries
`data_source: "fixture"`. It cannot be mistaken for live data.

**Live, once the keys exist.** The same commands without `--fixtures`:

```bash
export AMADEUS_CLIENT_ID=... AMADEUS_CLIENT_SECRET=...

python3 scripts/demo.py --city LON --check-in 2026-09-14 --check-out 2026-09-16
python3 scripts/demo.py --city LON --max-price 400 --currency GBP
python3 scripts/demo.py --details amadeus:MCLONGHM --check-in 2026-09-14 --check-out 2026-09-16
python3 scripts/demo.py --offers amadeus:MCLONGHM --check-in 2026-09-14 --check-out 2026-09-16
```

Use `LON` or `NYC` on test credentials - the test environment carries only a
subset of chains and other cities may legitimately return nothing there. On
production, any city with an IATA code works. `--json` prints the raw tool
payload for a closer look.

## Layout

```
openclaw.plugin.json          manifest: credentials, egress, inventory limits
requirements.txt              the dependency pin: none, and why
setup.sh / validate.sh        idempotent setup, offline smoke check
scripts/
  mcp_server.py               MCP stdio server, the three tools, JSON-RPC by hand
  supplier.py                 the supplier-neutral interface and its request types
  amadeus_supplier.py         Amadeus behind that interface, and all its dialect
  amadeus_client.py           HTTP, OAuth2, error translation, secret redaction
  call_budget.py              the monthly call ledger and the local ceiling
  accommodation_errors.py     the failure vocabulary, and the empty-result rule
  check_stdlib_only.py        the dependency policy, enforced
  demo.py                     the demo path and the live acceptance harness
skills/accommodation-search/  the agent-facing skill
tests/                        three suites, 77 tests, stdlib only, no network
```
