#!/usr/bin/env python3
"""Amadeus behind the neutral supplier interface.

Everything Amadeus-shaped lives here. Above this file nothing knows what a
hotelId is, that a price arrives as a string, or that the policies key is
sometimes `cancellation` and sometimes `cancellations`.

What this supplier can actually see
===================================
GDS and chain hotel inventory. Hotels, aparthotels and the chains' own
serviced-apartment brands - not the apartment market. Amadeus is a travel
distribution system, so what it lists is what a distribution system carries: a
Hilton, a Marriott, an independent property that has bothered to be
GDS-connected. A flat in Alfama is not in there and will never be in there.
That is stated in the manifest, in the README, in the skill file, and it is
attached to the payload of every response this module builds so that a model
summarising the results cannot lose it on the way.

Call cost per tool, which is the quota story
============================================
    search_accommodation      2 supplier calls (hotel list, then pricing)
    accommodation_details     2 without dates, 3 with them
    list_accommodation_offers 1

Plus one token call whenever the cached token is within ten seconds of
expiring - roughly one every half hour, not one per call.
"""
from __future__ import annotations

from accommodation_errors import AccommodationError, empty_result
from amadeus_client import SUPPLIER, AmadeusClient
from supplier import SearchQuery, Stay, Supplier, namespaced_id

HOTEL_LIST_BY_CITY = "/v1/reference-data/locations/hotels/by-city"
HOTEL_LIST_BY_GEOCODE = "/v1/reference-data/locations/hotels/by-geocode"
HOTEL_LIST_BY_HOTELS = "/v1/reference-data/locations/hotels/by-hotels"
HOTEL_OFFERS = "/v3/shopping/hotel-offers"
HOTEL_SENTIMENTS = "/v2/e-reputation/hotel-sentiments"

INVENTORY_NOTE = (
    "Amadeus carries GDS and chain hotel inventory. These are hotels, not "
    "apartments - short-let flats and other non-chain inventory are not in "
    "this supplier at all, so an absence here is not evidence of an absence in "
    "the city."
)

BOOKING_NOTE = (
    "Search only. This plugin never books. Hand the traveller the property and "
    "the price and let them book it themselves."
)


def _text(value) -> str | None:
    """Amadeus wraps free text as {'text': ..., 'lang': ...}, sometimes."""
    if isinstance(value, dict):
        return value.get("text")
    if isinstance(value, str):
        return value
    return None


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_property(raw: dict) -> dict:
    """A Hotel List or hotel-offers `hotel` object, in neutral terms."""
    geo = raw.get("geoCode") if isinstance(raw.get("geoCode"), dict) else {}
    latitude = geo.get("latitude", raw.get("latitude"))
    longitude = geo.get("longitude", raw.get("longitude"))
    address = raw.get("address") if isinstance(raw.get("address"), dict) else {}
    distance = raw.get("distance") if isinstance(raw.get("distance"), dict) else {}
    return {
        "property_id": namespaced_id(SUPPLIER, raw.get("hotelId")),
        "supplier": SUPPLIER,
        "name": raw.get("name"),
        "inventory_type": "hotel",
        "chain_code": raw.get("chainCode"),
        "city_code": raw.get("cityCode") or raw.get("iataCode"),
        "country_code": address.get("countryCode"),
        "coordinates": (
            {"latitude": latitude, "longitude": longitude}
            if latitude is not None and longitude is not None
            else None
        ),
        "distance_km": _distance_km(distance),
        "amenities": raw.get("amenities") or None,
    }


def _distance_km(distance: dict):
    value = _as_float(distance.get("value"))
    if value is None:
        return None
    unit = str(distance.get("unit") or "KM").upper()
    if unit.startswith("MI"):
        return round(value * 1.609344, 2)
    return value


def normalize_offer(raw: dict, property_id: str) -> dict:
    """One `offers[]` element, in neutral terms.

    Prices stay as the strings Amadeus sends. Reformatting a monetary value
    through a float is how a rate ends up displayed as 361.88999999999996, and
    nothing here needs to do arithmetic on it.
    """
    price = raw.get("price") if isinstance(raw.get("price"), dict) else {}
    room = raw.get("room") if isinstance(raw.get("room"), dict) else {}
    room_type = room.get("typeEstimated") if isinstance(room.get("typeEstimated"), dict) else {}
    guests = raw.get("guests") if isinstance(raw.get("guests"), dict) else {}
    variations = price.get("variations") if isinstance(price.get("variations"), dict) else {}
    average = variations.get("average") if isinstance(variations.get("average"), dict) else {}
    taxes = price.get("taxes") if isinstance(price.get("taxes"), list) else []

    return {
        "offer_id": namespaced_id(SUPPLIER, raw.get("id")),
        "property_id": property_id,
        "supplier": SUPPLIER,
        "check_in": raw.get("checkInDate"),
        "check_out": raw.get("checkOutDate"),
        "rooms": raw.get("roomQuantity"),
        "board_type": raw.get("boardType"),
        "rate_code": (raw.get("rateCode") or "").strip() or None,
        "room": {
            "category": room_type.get("category") or room.get("type"),
            "beds": room_type.get("beds"),
            "bed_type": room_type.get("bedType"),
            "description": _text(room.get("description")),
        },
        "guests": {"adults": guests.get("adults"), "child_ages": guests.get("childAges")},
        "price": {
            "currency": price.get("currency"),
            "total_for_stay": price.get("total"),
            "base": price.get("base"),
            "average_per_night": average.get("base") or average.get("total"),
            "taxes": [
                {
                    "amount": tax.get("amount"),
                    "currency": tax.get("currency") or price.get("currency"),
                    "code": tax.get("code"),
                    "included_in_total": tax.get("included"),
                }
                for tax in taxes
                if isinstance(tax, dict)
            ],
        },
        "policies": normalize_policies(raw.get("policies")),
        "booking": BOOKING_NOTE,
    }


def normalize_policies(raw) -> dict:
    """Cancellation arrives as `cancellations` (array, per the schema) or
    `cancellation` (object, per every published example). Accept both rather
    than betting on one."""
    if not isinstance(raw, dict):
        return {}
    cancellations = raw.get("cancellations")
    if not isinstance(cancellations, list):
        single = raw.get("cancellation")
        cancellations = [single] if isinstance(single, dict) else []
    check = raw.get("checkInOut") if isinstance(raw.get("checkInOut"), dict) else {}
    return {
        "payment_type": (raw.get("paymentType") or "").upper() or None,
        "cancellation": [
            {
                "type": item.get("type"),
                "amount": item.get("amount"),
                "deadline": item.get("deadline"),
                "number_of_nights": item.get("numberOfNights"),
                "description": _text(item.get("description")),
            }
            for item in cancellations
            if isinstance(item, dict)
        ],
        "check_in_time": check.get("checkIn"),
        "check_out_time": check.get("checkOut"),
        "accepted_payment_methods": _accepted_methods(raw),
    }


def _accepted_methods(raw: dict):
    for key in ("guarantee", "deposit", "prepay"):
        block = raw.get(key)
        if isinstance(block, dict):
            accepted = block.get("acceptedPayments")
            if isinstance(accepted, dict):
                return accepted.get("methods")
    return None


def normalize_rating(raw: dict) -> dict:
    return {
        "overall_rating": raw.get("overallRating"),
        "number_of_reviews": raw.get("numberOfReviews"),
        "number_of_ratings": raw.get("numberOfRatings"),
        "sentiments": raw.get("sentiments"),
        "_scale": "0-100, from the supplier's own review aggregation.",
    }


def _cheapest_first(entry: dict):
    """Sort key: cheapest priced offer, unpriced entries last."""
    offers = entry.get("offers") or []
    prices = [
        _as_float((offer.get("price") or {}).get("total_for_stay"))
        for offer in offers
    ]
    prices = [price for price in prices if price is not None]
    return (0, min(prices)) if prices else (1, 0.0)


class AmadeusSupplier(Supplier):
    name = SUPPLIER

    def __init__(self, client: AmadeusClient) -> None:
        self.client = client

    def _envelope(self, extra: dict) -> dict:
        base = {
            "supplier": SUPPLIER,
            "data_source": self.client.data_source,
            "inventory_note": INVENTORY_NOTE,
            "booking_note": BOOKING_NOTE,
            "usage": self.client.budget.usage(),
        }
        base.update(extra)
        return base

    def _hotel_ids(self, query: SearchQuery) -> list[dict]:
        place = query.place
        if place.city_code:
            path = HOTEL_LIST_BY_CITY
            params = {"cityCode": place.city_code, "radius": place.radius_km, "radiusUnit": "KM"}
        else:
            path = HOTEL_LIST_BY_GEOCODE
            params = {
                "latitude": place.latitude,
                "longitude": place.longitude,
                "radius": place.radius_km,
                "radiusUnit": "KM",
            }
        if query.amenities:
            params["amenities"] = list(query.amenities)

        payload = self.client.get(path, params, "hotel-list")
        found = [item for item in (payload.get("data") or []) if isinstance(item, dict) and item.get("hotelId")]
        if not found:
            raise empty_result(
                what_was_searched=f"The property list for {place.describe()}",
                what_to_do=[
                    "Check the city code is the city that was meant. LIS is "
                    "Lisbon, LON is London, NYC is New York. A valid code for "
                    "the wrong place returns a confident empty list.",
                    "Widen radius_km. The default is 5km from the city centre.",
                    "On test credentials the property list covers only a subset "
                    "of chains, so an empty list there says nothing about the "
                    "real city.",
                    INVENTORY_NOTE,
                ],
                supplier=SUPPLIER,
                detail={"place": place.describe(), "endpoint": "hotel-list"},
            )
        # Nearest first, because the pricing call takes at most 20 properties
        # and "the 20 closest to the centre" is a defensible slice while "the
        # 20 the supplier happened to list first" is not.
        found.sort(key=lambda item: _distance_km(item.get("distance") or {}) or 1e6)
        return found

    def search(self, query: SearchQuery) -> dict:
        listed = self._hotel_ids(query)
        wanted = listed[: query.max_results]
        params = {
            "hotelIds": ",".join(item["hotelId"] for item in wanted),
            "adults": query.stay.adults,
            "checkInDate": query.stay.check_in.isoformat(),
            "checkOutDate": query.stay.check_out.isoformat(),
            "roomQuantity": query.stay.rooms,
            "bestRateOnly": "true",
        }
        if query.currency:
            params["currency"] = query.currency.upper()
        if query.max_price:
            params["priceRange"] = f"-{int(query.max_price)}"

        payload = self.client.get(HOTEL_OFFERS, params, "hotel-offers")
        priced = [item for item in (payload.get("data") or []) if isinstance(item, dict)]

        # The list call knows the distance from the centre and the country; the
        # pricing call does not carry either. Merging them here is the only
        # place both halves are in scope, and "2.4km from the centre" is most
        # of what makes a list of hotel names readable.
        listed_by_id = {item["hotelId"]: item for item in wanted}

        results = []
        for item in priced:
            hotel = item.get("hotel") if isinstance(item.get("hotel"), dict) else {}
            prop = normalize_property(hotel)
            from_list = normalize_property(listed_by_id.get(hotel.get("hotelId"), {}))
            for key, value in from_list.items():
                if prop.get(key) is None and value is not None:
                    prop[key] = value
            results.append(
                {
                    "property": prop,
                    "available": item.get("available"),
                    "offers": [
                        normalize_offer(offer, prop["property_id"])
                        for offer in (item.get("offers") or [])
                        if isinstance(offer, dict)
                    ],
                }
            )
        results = [entry for entry in results if entry["offers"]]

        if not results:
            raise empty_result(
                what_was_searched=(
                    f"Pricing for the {len(wanted)} properties nearest "
                    f"{query.place.describe()}, {query.stay.describe()}"
                ),
                what_to_do=[
                    "Drop the price ceiling and search again. A ceiling filters "
                    "at the supplier, so an over-tight one empties the result "
                    "before it reaches here.",
                    "Move the dates. These properties may be full on exactly "
                    "these nights while the city is not.",
                    "Widen radius_km so a different set of properties gets priced "
                    f"- only the {len(wanted)} nearest were, out of "
                    f"{len(listed)} found.",
                    INVENTORY_NOTE,
                ],
                supplier=SUPPLIER,
                detail={
                    "properties_found": len(listed),
                    "properties_priced": len(wanted),
                    "endpoint": "hotel-offers",
                    "price_ceiling": query.max_price,
                },
            )

        results.sort(key=_cheapest_first)
        return self._envelope(
            {
                "query": {
                    "place": query.place.describe(),
                    "stay": query.stay.describe(),
                    "price_ceiling": (
                        f"{query.max_price} {query.currency}" if query.max_price else None
                    ),
                },
                "properties_found": len(listed),
                "properties_priced": len(wanted),
                "results": results,
                "_coverage_note": (
                    f"{len(listed)} properties matched the area; the "
                    f"{len(wanted)} nearest the centre were priced. Properties "
                    f"beyond that were not checked, so this is not the cheapest "
                    f"room in the city, it is the cheapest of what was priced."
                ),
            }
        )

    def _identity(self, native_id: str) -> dict:
        payload = self.client.get(HOTEL_LIST_BY_HOTELS, {"hotelIds": native_id}, "hotel-list")
        found = [item for item in (payload.get("data") or []) if isinstance(item, dict)]
        if not found:
            raise empty_result(
                what_was_searched=f"Property lookup for {native_id}",
                what_to_do=[
                    "Confirm the property_id came from a search result of this "
                    "plugin and was not edited.",
                    "Property codes are supplier-specific and do not survive "
                    "being moved between environments - a code from production "
                    "may not resolve on test credentials.",
                ],
                supplier=SUPPLIER,
                detail={"native_id": native_id, "endpoint": "hotel-list"},
            )
        return found[0]

    def _rating(self, native_id: str) -> dict | None:
        """Reputation is a nice-to-have. A failure here degrades the answer, it
        does not fail the tool - and the degradation is reported rather than
        silently swallowed."""
        try:
            payload = self.client.get(
                HOTEL_SENTIMENTS, {"hotelIds": native_id}, "hotel-sentiments"
            )
        except AccommodationError as error:
            return {"unavailable": error.kind, "detail": error.message}
        data = [item for item in (payload.get("data") or []) if isinstance(item, dict)]
        warnings = payload.get("warnings")
        if not data:
            note = "This supplier holds no review data for this property."
            if isinstance(warnings, list) and warnings:
                note = f"{note} Supplier warning: {warnings[0].get('title')}."
            return {"unavailable": "NO_REVIEW_DATA", "detail": note}
        return normalize_rating(data[0])

    def details(self, native_id: str, stay: Stay | None = None) -> dict:
        identity = self._identity(native_id)
        prop = normalize_property(identity)
        body = {"property": prop, "rating": self._rating(native_id)}

        if stay is None:
            body["rates"] = None
            body["_note"] = (
                "No dates given, so no rates, amenities or policies were "
                "fetched. Pass check_in and check_out to get those; it costs "
                "one more supplier call."
            )
            return self._envelope(body)

        payload = self.client.get(
            HOTEL_OFFERS,
            {
                "hotelIds": native_id,
                "adults": stay.adults,
                "checkInDate": stay.check_in.isoformat(),
                "checkOutDate": stay.check_out.isoformat(),
                "roomQuantity": stay.rooms,
                "bestRateOnly": "true",
            },
            "hotel-offers",
        )
        priced = [item for item in (payload.get("data") or []) if isinstance(item, dict)]
        if not priced:
            raise empty_result(
                what_was_searched=f"Rates for {prop['name'] or native_id}, {stay.describe()}",
                what_to_do=[
                    "The property exists - only its rates came back empty. It "
                    "is either full on these dates or not selling through this "
                    "supplier for them.",
                    "Try adjacent dates, or call search_accommodation for the "
                    "area to see what else is priced.",
                ],
                supplier=SUPPLIER,
                detail={"native_id": native_id, "endpoint": "hotel-offers"},
            )

        first = priced[0]
        hotel = first.get("hotel") if isinstance(first.get("hotel"), dict) else {}
        priced_property = normalize_property(hotel)
        for key, value in priced_property.items():
            if value is not None and prop.get(key) is None:
                prop[key] = value

        offers = [
            normalize_offer(offer, prop["property_id"])
            for offer in (first.get("offers") or [])
            if isinstance(offer, dict)
        ]
        body["property"] = prop
        body["available"] = first.get("available")
        body["rates"] = offers
        body["policies"] = offers[0]["policies"] if offers else None
        body["_amenities_note"] = (
            "Amenity coverage is thin by design of the supplier's v3 hotel "
            "search, which dropped most descriptive fields from the priced "
            "hotel object. Treat a missing amenity as unknown, never as absent."
        )
        return self._envelope(body)

    def offers(self, native_id: str, stay: Stay, currency=None, all_rates: bool = True) -> dict:
        params = {
            "hotelIds": native_id,
            "adults": stay.adults,
            "checkInDate": stay.check_in.isoformat(),
            "checkOutDate": stay.check_out.isoformat(),
            "roomQuantity": stay.rooms,
            "bestRateOnly": "false" if all_rates else "true",
        }
        if currency:
            params["currency"] = str(currency).upper()

        payload = self.client.get(HOTEL_OFFERS, params, "hotel-offers")
        priced = [item for item in (payload.get("data") or []) if isinstance(item, dict)]
        offers = []
        prop = None
        for item in priced:
            hotel = item.get("hotel") if isinstance(item.get("hotel"), dict) else {}
            # One property was asked for, so one property comes back. Anything
            # else in the response is dropped rather than merged - offers
            # attributed to the wrong hotel is the worst shape of wrong answer
            # this tool could give.
            if hotel.get("hotelId") and hotel["hotelId"] != native_id:
                continue
            prop = prop or normalize_property(hotel)
            offers.extend(
                normalize_offer(offer, prop["property_id"])
                for offer in (item.get("offers") or [])
                if isinstance(offer, dict)
            )

        if not offers:
            raise empty_result(
                what_was_searched=f"Bookable offers for {native_id}, {stay.describe()}",
                what_to_do=[
                    "The property returned no bookable rate for these dates. "
                    "That is usually sold out, but it is also what a property "
                    "that has stopped distributing through this supplier looks "
                    "like.",
                    "Try adjacent dates before concluding anything about the "
                    "property.",
                ],
                supplier=SUPPLIER,
                detail={"native_id": native_id, "endpoint": "hotel-offers"},
            )

        offers.sort(key=lambda offer: _as_float(offer["price"]["total_for_stay"]) or 1e12)
        return self._envelope(
            {
                "property": prop,
                "stay": stay.describe(),
                "offers": offers,
                "_offer_lifetime_note": (
                    "Offer ids have a limited lifetime and the supplier does "
                    "not publish how long. Treat a price older than a few "
                    "minutes as indicative and re-run before quoting it."
                ),
            }
        )
