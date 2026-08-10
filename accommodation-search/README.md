# accommodation-search

Search Airbnb from an agent. Airbnb only, search only, no booking.

Wraps [`@openbnb/mcp-server-airbnb`](https://github.com/openbnb-org/mcp-server-airbnb)
(MIT) at a pinned version, behind a small stdio proxy that turns an empty result
set into a visible warning instead of a confident "nothing available".

## Read this before you enable it

Two things are true right now and both change what you can expect. Neither is
hidden further down.

**1. Search does not work with robots compliance on, and this ships with robots
compliance on.** Airbnb's `robots.txt` carries `Disallow: /s/*/*` under
`User-agent: *`. Every Airbnb search URL has the shape `/s/<location>/homes`, so
every search matches that rule. With compliance on, `airbnb_search` refuses
before it makes a request. Verified against the live file on 2026-08-10:

```
$ python3 scripts/robots_preflight.py
DISALLOWED  airbnb_search
            /s/Lisbon--Portugal/homes?checkin=2026-09-09&adults=2
            matched: Disallow: /s/*/*
ALLOWED     airbnb_listing_details
            /rooms/46175267?check_in=2026-09-09&adults=2
            matched: no rule, allowed by default
```

Turning that off is a terms-of-service decision for whoever owns the install. It
is not a default a plugin gets to pick, so this one does not pick it. Run the
preflight before assuming either answer is still current.

**2. As of upstream 0.3.0, the robots check has a bug that blocks everything.**
`isPathAllowed()` hands a bare path to `robots-parser`, whose `isAllowed()`
requires an absolute URL and returns `undefined` for anything else. `undefined`
is falsy, so the server treats every path as disallowed. The practical effect is
that with compliance on, both tools refuse, including listing details on
`/rooms/<id>` that robots.txt genuinely allows.

```
$ node -e '... robotsParser(url, txt).isAllowed("/rooms/46175267", UA)'
undefined
$ node -e '... robotsParser(url, txt).isAllowed("https://www.airbnb.com/rooms/46175267", UA)'
true
```

The fix is one line upstream and belongs upstream. Until it lands, listing
details are blocked by a bug rather than by a rule.

## What it is for

| Tool | What it does |
|---|---|
| `airbnb_search` | Listings for a location, dates, guests, price ceiling, property type. Returns prices, ratings and direct links. |
| `airbnb_listing_details` | Amenities, house rules, policies and location for one listing id. |

Booking is out of scope. Deliberately, permanently, not "in a later version".
The plugin hands over a link and the person books it themselves.

Booking.com, VRBO and Expedia are not covered. There is no programmatic path to
their inventory for an install this size - Airbnb has had no public API since
2026 and is partner-only, Expedia Rapid and Booking.com's Demand API both need
signed partner agreements. Airbnb via a maintained MIT scraper is the best
available trade, not a complete one.

## Install

```bash
bash setup.sh      # idempotent, safe to re-run
bash validate.sh   # offline smoke check
```

`setup.sh` installs the upstream server with `npm ci` from the committed
`package-lock.json` into this plugin's `node_modules`. Re-running when the
pinned version is already installed does nothing and touches no network.

The dependency is pinned to an exact version and the lockfile is committed, so
the code that executes on your machine is the code a human chose. Nothing here
resolves a package at install time and nothing calls `npx`.

### Registering the MCP server

The manifest declares the server under `contracts.mcpServers`, which is the
documented chassis contract in [`docs/MANIFEST.md`](../docs/MANIFEST.md).

Checked on 2026-08-10: no `activate-plugins.sh` exists in
`scrollinondubs/behalfbot` at HEAD, and `.mcp.json` is hydrated from the chassis
template by `bootstrap-mcp-config.sh`. So nothing consumes `contracts.mcpServers`
yet. Until it does, add the entry by hand:

```json
{
  "mcpServers": {
    "accommodation-search": {
      "command": "python3",
      "args": ["/absolute/path/to/accommodation-search/scripts/airbnb_mcp_proxy.py"]
    }
  }
}
```

## Demo path

Repeatable, and it drives the same stdio transport the agent uses - so what you
see on screen is what the agent gets, warning blocks included.

```bash
# 1. What does Airbnb allow today? Answer read from the live file.
python3 scripts/robots_preflight.py

# 2. A European search. "Lisbon, Portugal" must return listings in Lisbon,
#    which is the whole reason the geocoders stay on.
python3 scripts/demo_search.py --location "Lisbon, Portugal" --limit 3

# 3. The same search with a price ceiling.
python3 scripts/demo_search.py --location "Lisbon, Portugal" --max-price 120

# 4. Details for one listing: amenities, house rules, what is NOT included.
python3 scripts/demo_search.py --details 46175267

# 5. Raw payloads, for showing what the model actually receives.
python3 scripts/demo_search.py --location "Porto, Portugal" --json
```

Exit codes: `0` results, `2` empty or refused, which is what makes step 2 a
usable check rather than a thing you have to squint at.

With robots compliance on, steps 2 and 3 currently return the robots error
described at the top. That is not a broken demo, it is the demo - it shows the
plugin declining to fetch a path Airbnb asked crawlers not to fetch.

## An empty result is treated as suspicious

This is a scraper. When Airbnb changes its markup the parse can still succeed
against a page with no listings in it, and the result is an empty list with no
error attached. A rotted selector and a genuinely empty search are the same
bytes.

So `scripts/airbnb_mcp_proxy.py` sits between the client and the server and
rewrites those responses. An empty or missing result set comes back with a
leading text block:

```
SUSPICIOUS EMPTY RESULT - do not report this to the user as 'nothing available'.

Observed: 'searchResults' is an empty list.

This plugin reads airbnb.com by scraping it. When Airbnb changes its page
markup the scrape degrades into an empty result set that looks exactly like a
search that genuinely matched nothing. [...]
```

and a `_behalfbot_warning` block inside the JSON payload. Both, because an agent
might read either.

The proxy fails open by design. Anything it cannot parse, any tool it does not
know, any shape it does not recognise passes through untouched. A bug in the
annotation must never break the transport.

## What leaves your machine

| Host | Why | What is sent |
|---|---|---|
| `www.airbnb.com` | The listings, and `/robots.txt` before every request | Search parameters as a query string |
| `photon.komoot.io` | Primary geocoder, every search without a `placeId` | The location string, nothing else |
| `nominatim.openstreetmap.org` | Fallback geocoder, only when Photon returns no bounding box | The location string, nothing else |

The geocoders are on by default and the plugin's proxy clears `DISABLE_GEOCODING`
on startup so that default cannot drift. The reason is accuracy: Airbnb's own
geocoder places "Copenhagen, Denmark" in Wisconsin and "Paris, France" in
Vendée. The cost is that every search tells a third party where someone is
thinking of going. That trade is stated here rather than buried in a dependency,
because it is a real one - if the location itself is sensitive, pass a `placeId`
instead and no third party is contacted.

Nominatim's usage policy caps at roughly one request per second. Fine for
interactive use, which is all this plugin does. There is no monitoring loop and
adding one is a separate decision.

## Tests

```bash
python3 tests/test_empty_results_are_suspicious.py
python3 tests/test_robots_preflight.py
```

Stdlib only, no network, no node. The MCP responses are canned payloads in the
shapes the upstream server actually emits, so CI does not depend on Airbnb being
up - which matters, since what is under test is what happens when Airbnb goes
sideways. The robots verdicts in the fixture were cross-checked against the
`robots-parser` library the upstream server itself uses.

Both suites are picked up automatically by the repo's plugin-tests workflow.

## Bumping the pin

1. Read the upstream diff. That is the point of pinning.
2. `npm install @openbnb/mcp-server-airbnb@<version>` and commit both
   `package.json` and `package-lock.json`.
3. `bash setup.sh && bash validate.sh`, then run the demo path.
4. Re-check the response shapes in `tests/`. The empty-result guard keys on
   `searchResults` and `details`; if upstream renames either, the guard silently
   stops guarding, which is the failure mode it exists to prevent.

## Licence

This plugin is MIT, same as the repo. The upstream server is MIT with a real
LICENSE file in its published tarball, checked 2026-08-10.
