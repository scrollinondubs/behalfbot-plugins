# Accommodation search

Find a traveller somewhere to stay. Three tools, all read-only.

## Read this before you use the results

**This is hotel inventory. Not apartments.** It searches the Amadeus travel
distribution system, which carries chain hotels, GDS-connected independents and
chain-operated aparthotels. It does not carry flats, short lets, Airbnb-style
listings or anything that is not distributed through the trade.

So when someone asks for "a place in Lisbon for a week", what comes back is the
hotel answer to that question. Say so. If they wanted an apartment, this tool
cannot see the market they are asking about, and answering with three hotels
without mentioning that is the failure mode here.

**It never books.** There is no booking path and there is not meant to be one.
Find the property, give the traveller the name, the price and what the
cancellation terms say, and let them book it themselves.

## The tools

### `search_accommodation`

| Argument | Notes |
|---|---|
| `city_code` | Three-letter IATA city code. LIS Lisbon, LON London, NYC New York, PAR Paris. A city name will be refused. |
| `latitude` / `longitude` | Instead of a city code, for anywhere without one. |
| `radius_km` | How far out to look. Default 5. |
| `check_in` / `check_out` | `YYYY-MM-DD`. Resolve "next Friday" to a date before calling. |
| `adults` / `rooms` | Defaults 1 and 1. |
| `max_price` | Ceiling on the total for the stay. Needs `currency`. |
| `max_results` | How many properties to price, up to 20. |
| `amenities` | Filter, e.g. `WIFI`, `PARKING`, `SWIMMING_POOL`. |
| `supplier` | Only `amadeus` today. |

Costs two supplier calls: one to list the properties in the area, one to price
them. It prices the **nearest** properties to the centre, not the cheapest in
the city - it cannot know which are cheapest before pricing them. The response
says how many were found and how many were priced. Quote that honestly: "the
cheapest of the eight nearest the centre" is true, "the cheapest in Lisbon" is
not.

### `accommodation_details`

Takes a `property_id` from a search result, exactly as it came back, prefix
included: `amadeus:MCLONGHM`. Do not strip the prefix and do not invent one.

Without dates it returns identity, location and guest ratings. With dates it
also returns rates, policies and whatever amenities the supplier attaches. The
ratings are 0-100 with sub-scores for things like location, service and value.

Amenity coverage is thin, because the supplier's v3 hotel search dropped most
descriptive fields. **A missing amenity means unknown, not absent.** Do not tell
a traveller a hotel has no air conditioning on the strength of it not being
listed.

### `list_accommodation_offers`

Every bookable rate for one property and one stay, cheapest first, with board
type, payment terms and cancellation deadline for each.

Prices expire. The supplier does not publish how fast. Anything more than a few
minutes old is indicative - re-run before quoting a number a person will act on.

## An empty result is an error here

Every one of these tools raises rather than returning an empty list. When you
see `EMPTY_RESULT`, the search came back with nothing and the plugin cannot tell
which of these it was:

- the properties really are full on those nights
- the city code resolved somewhere other than where the traveller meant
- the price ceiling filtered everything out at the supplier
- these are test credentials, which carry only a subset of chains

Only the first is a fact about the world. **Never turn an empty result into
"there is nothing available".** Say what happened: the search came back empty
and it could not be confirmed why. Then try the specific next steps in the
error, which name the ones that apply.

## Failures worth telling apart

| Kind | What it means | What to do |
|---|---|---|
| `EMPTY_RESULT` | Zero results, cause unknown | Widen the search. Never report as unavailability. |
| `SUPPLIER_REPORTED_NO_MATCH` | The supplier said explicitly that nothing matched | Widen the search. Still not a statement about the city. |
| `RATE_LIMITED` | Too many calls per second | Wait a second, repeat. It will work. |
| `QUOTA_EXHAUSTED` | The month's allowance is gone | Retrying does nothing until the month turns over. Tell the traveller the search could not be run, not that nothing was found. |
| `LOCAL_BUDGET_EXHAUSTED` | This plugin's own ceiling, no request was sent | The supplier refused nothing. A human can raise the ceiling. |
| `AUTH_FAILED` | Credentials rejected or expired | Report it. Never print the credential values while debugging. |
| `CREDENTIALS_MISSING` | No keys in the environment | The install owner supplies them; there is nothing to work around. |

`RATE_LIMITED` and `QUOTA_EXHAUSTED` both arrive from the supplier as HTTP 429
and mean opposite things. The distinction is already made for you - use it
rather than retrying blindly.

## Quota

The account has a monthly allowance and the supplier will not tell you how much
of it is left. Every successful result carries a `usage` block with the local
count and a warning past 80%. Do not loop searches. A search is two calls; do
not spend twenty of them exploring when one well-chosen query answers the
question.

## What leaves the machine

Per search: a city code or coordinates, a radius, dates, guest and room counts,
an optional price ceiling. No traveller name, no contact details, no payment
details - none of those exist anywhere in this plugin. Credentials come from the
environment and are never written to disk.
