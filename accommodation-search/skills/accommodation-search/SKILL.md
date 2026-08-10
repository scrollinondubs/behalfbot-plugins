# Accommodation search

Search Airbnb for a place to stay. Two tools, both read-only.

## What this can and cannot do

**Can:** find listings for a location, date range, guest count and price ceiling;
pull amenities, house rules and policies for one listing; give a direct link.

**Cannot:** book anything. There is no booking path in this plugin and there is
not meant to be one. When the traveller has picked a place, hand them the link
and let them book it themselves. Do not offer to complete a reservation.

**Does not cover:** Booking.com, VRBO, Expedia, hotels generally. Airbnb only.
If someone asks for the best price across sites, say plainly that this searches
Airbnb and nothing else. Do not imply wider coverage by hedging.

## Tools

### `airbnb_search`

| Argument | Notes |
|---|---|
| `location` | Required, free text: "Lisbon, Portugal". This string is sent to a third-party geocoder - see the privacy note below. |
| `checkin` / `checkout` | `YYYY-MM-DD`. |
| `adults` / `children` / `infants` / `pets` | Counts. Defaults to 1 adult. |
| `minPrice` / `maxPrice` | Per night, in the currency Airbnb shows for the region. |
| `propertyType` | `entire_home`, `private_room`, `shared_room`, `hotel_room`. |
| `cursor` | Pagination cursor from a previous response's `paginationInfo`. |
| `placeId` | A Google Maps Place ID. Skips the third-party geocoder entirely. |

Always pass a country with the city. "Lisbon" alone is ambiguous; "Lisbon,
Portugal" is not.

### `airbnb_listing_details`

Takes an `id` from a search result, plus the same date and guest arguments.
Returns amenities grouped by category, house rules, policies and location. Note
the `"Not included"` amenity group: those are the things Airbnb shows struck
through, meaning the place does NOT have them. Reading that group as amenities
is the easy mistake here - no air conditioning is exactly the sort of thing a
traveller needs told.

## An empty result is a warning, not an answer

This reads Airbnb by scraping its pages. When Airbnb changes its markup, the
scrape can still succeed against a page with no listings in it, and what comes
back is an empty list that looks identical to a search that genuinely matched
nothing.

The proxy in front of these tools detects that and returns a block starting
`SUSPICIOUS EMPTY RESULT`. When you see it:

1. Re-run with the filters relaxed. Drop the price ceiling, widen the dates,
   drop the property type. A broad search that is also empty points at the
   scraper, not the market.
2. Open the `searchUrl` from the response and look at it.
3. Tell the person what actually happened: the search came back empty and it
   could not be confirmed whether that is real.

Never turn an empty result into "there is nothing available on those dates".
That is a claim about the world, and this tool cannot support it.

## Robots.txt, and why search may refuse

Robots compliance is on. As of 2026-08-10 Airbnb's robots.txt carries
`Disallow: /s/*/*` under `User-agent: *`, which covers every search URL, so
`airbnb_search` returns a robots error rather than results. `airbnb_listing_details`
uses `/rooms/<id>`, which robots.txt does allow.

If a search comes back with `This path is disallowed by Airbnb's robots.txt`,
that is the plugin working as configured. Do not suggest working around it and
do not set `IGNORE_ROBOTS_TXT`. Report it and let the install's owner decide.
`python3 scripts/robots_preflight.py` prints the current answer read from
Airbnb's live file.

## What leaves the machine

Every search without a `placeId` sends the location string to Photon
(`photon.komoot.io`), and to Nominatim (`nominatim.openstreetmap.org`) when
Photon returns no bounding box. Only that string, nothing else about the
request. This is on by default because Airbnb's own geocoder puts "Copenhagen,
Denmark" in Wisconsin.

If someone is searching a location that is itself sensitive - a place they have
not told anyone they are going - that string reaching a third party is worth
mentioning before running the search, not after.

## Rate limits

On demand only. No polling, no monitoring loops. Nominatim's usage policy caps
at roughly one request per second and Airbnb rate-limits on its own terms. A
price-monitoring loop over this is a separate decision, not something to start
because a traveller asked twice.
