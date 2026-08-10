#!/usr/bin/env python3
"""The supplier-neutral interface. One supplier is implemented; the shape is
designed for two.

Why this file exists at all
===========================
Amadeus is what can be signed up for today. Booking.com's Demand API is the one
that actually covers apartments, and its affiliate application is in progress.
When it lands it has to slot in behind this interface without any caller
changing a line, which means no Amadeus vocabulary is allowed to leak upward:
no `hotelIds`, no `cityCode`, no `offerId`, no eight-character property codes in
a tool signature.

So the request objects here are the ones a traveller's question maps onto - a
place, a stay, a ceiling on price - and the results are plain dicts with
supplier-neutral keys. Translating those into and out of a supplier's own
dialect is the supplier module's job and nobody else's.

Identifier namespacing
======================
Every id that crosses this boundary is prefixed with the supplier that issued
it: `amadeus:HLPAR266`, and later `booking:1234567`. Two reasons. An id handed
back to `accommodation_details` has to be routed to the supplier that can
resolve it, and an unprefixed id gives the router nothing to route on. And when
two suppliers eventually answer the same search, an unprefixed collision is a
silent wrong answer rather than a loud one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from accommodation_errors import BAD_REQUEST, SUPPLIER_NOT_IMPLEMENTED, AccommodationError

# Suppliers this plugin can answer with today.
IMPLEMENTED_SUPPLIERS = ("amadeus",)

# Suppliers the interface was designed to accept and which are not built yet.
# Named here rather than left out so that asking for one fails with an
# explanation instead of "unknown supplier", and so the reserved name cannot be
# quietly taken by something else.
RESERVED_SUPPLIERS = {
    "booking": (
        "Booking.com Demand API. Reserved, not implemented. This is the "
        "supplier that covers apartments and non-chain inventory; the "
        "affiliate application is separate and has not been approved. Until "
        "it is, use supplier 'amadeus' and expect hotels only."
    ),
}

_ID_RE = re.compile(r"^(?P<supplier>[a-z0-9_-]+):(?P<native>.+)$")


def namespaced_id(supplier: str, native_id: str) -> str:
    return f"{supplier}:{native_id}"


def split_id(value: str) -> tuple[str, str]:
    """Split `supplier:native` and validate the supplier half.

    Raises rather than guessing. A bare id used to be an Amadeus id and
    defaulting to that would make the second supplier's arrival a silent
    behaviour change on every existing caller.
    """
    if not isinstance(value, str) or not value.strip():
        raise AccommodationError(
            kind=BAD_REQUEST,
            message="property_id is required and must be a non-empty string.",
            what_to_do=["Pass a property_id exactly as a search result returned it."],
        )
    match = _ID_RE.match(value.strip())
    if not match:
        raise AccommodationError(
            kind=BAD_REQUEST,
            message=(
                f"'{value}' is not a namespaced id. Ids from this plugin look "
                f"like 'amadeus:HLPAR266' - the supplier that issued the id, a "
                f"colon, then the supplier's own code."
            ),
            what_to_do=[
                "Use the property_id or offer_id string exactly as the search "
                "result gave it, without stripping the prefix.",
            ],
        )
    supplier = match.group("supplier")
    if supplier not in IMPLEMENTED_SUPPLIERS:
        raise unsupported_supplier(supplier)
    return supplier, match.group("native")


def unsupported_supplier(name: str) -> AccommodationError:
    if name in RESERVED_SUPPLIERS:
        return AccommodationError(
            kind=SUPPLIER_NOT_IMPLEMENTED,
            message=f"Supplier '{name}' is reserved but not implemented. {RESERVED_SUPPLIERS[name]}",
            what_to_do=[
                f"Re-run with supplier='{IMPLEMENTED_SUPPLIERS[0]}'.",
                "Tell the traveller which supplier answered, because the "
                "inventory differs between them.",
            ],
        )
    return AccommodationError(
        kind=BAD_REQUEST,
        message=(
            f"Unknown supplier '{name}'. Implemented: "
            f"{', '.join(IMPLEMENTED_SUPPLIERS)}. Reserved: "
            f"{', '.join(sorted(RESERVED_SUPPLIERS))}."
        ),
        what_to_do=[f"Re-run with supplier='{IMPLEMENTED_SUPPLIERS[0]}'."],
    )


def _bad(message: str, *what_to_do: str) -> AccommodationError:
    return AccommodationError(kind=BAD_REQUEST, message=message, what_to_do=list(what_to_do))


def parse_date(value: object, field_name: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise _bad(f"{field_name} must be a YYYY-MM-DD string.")
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise _bad(
            f"{field_name} '{value}' is not a valid YYYY-MM-DD date.",
            "Resolve relative dates like 'next Friday' to a calendar date before calling.",
        ) from None


@dataclass(frozen=True)
class Place:
    """Where to search. Either a city code or a point with a radius."""

    city_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: int = 5

    def __post_init__(self) -> None:
        has_city = bool(self.city_code)
        has_point = self.latitude is not None and self.longitude is not None
        if has_city == has_point:
            raise _bad(
                "Give either city_code or both latitude and longitude, not both and not neither.",
                "For a named city, pass the three-letter IATA city code, e.g. LIS for Lisbon.",
                "For anywhere else, pass latitude and longitude with a radius_km.",
            )
        if has_city:
            code = self.city_code.strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", code):
                raise _bad(
                    f"city_code '{self.city_code}' is not a three-letter IATA city code.",
                    "Lisbon is LIS, London is LON, New York is NYC. A country "
                    "name or a full city name will not resolve.",
                )
            object.__setattr__(self, "city_code", code)
        if has_point:
            if not -90 <= float(self.latitude) <= 90:
                raise _bad(f"latitude {self.latitude} is outside -90..90.")
            if not -180 <= float(self.longitude) <= 180:
                raise _bad(f"longitude {self.longitude} is outside -180..180.")
        if not 1 <= int(self.radius_km) <= 300:
            raise _bad("radius_km must be between 1 and 300.")

    def describe(self) -> str:
        if self.city_code:
            return f"city {self.city_code} within {self.radius_km}km"
        return f"{self.latitude},{self.longitude} within {self.radius_km}km"


@dataclass(frozen=True)
class Stay:
    check_in: date
    check_out: date
    adults: int = 1
    rooms: int = 1

    def __post_init__(self) -> None:
        if self.check_out <= self.check_in:
            raise _bad(
                f"check_out {self.check_out} is not after check_in {self.check_in}.",
                "A one-night stay is check_in on day N and check_out on day N+1.",
            )
        if not 1 <= int(self.adults) <= 9:
            raise _bad("adults must be between 1 and 9.")
        if not 1 <= int(self.rooms) <= 9:
            raise _bad("rooms must be between 1 and 9.")

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    def describe(self) -> str:
        return (
            f"{self.check_in.isoformat()} to {self.check_out.isoformat()} "
            f"({self.nights} night{'s' if self.nights != 1 else ''}), "
            f"{self.adults} adult{'s' if self.adults != 1 else ''}, "
            f"{self.rooms} room{'s' if self.rooms != 1 else ''}"
        )


# One pricing call covers at most this many properties at Amadeus, and a search
# is deliberately capped at one pricing call. Chunking would spend a call per
# 20 properties against a monthly budget nobody can read from the API, and a
# chunked loop that hits a 429 halfway has to throw away the partial result to
# avoid presenting it as a complete one. Not worth it for a search a human
# reads ten rows of.
MAX_RESULTS_CEILING = 20
MAX_RESULTS_REASON = (
    "A search prices at most 20 properties in one supplier call, and this "
    "plugin makes exactly one pricing call per search so the quota cost stays "
    "predictable. Narrow the radius or the city rather than raising this."
)


@dataclass(frozen=True)
class SearchQuery:
    place: Place
    stay: Stay
    max_price: float | None = None
    currency: str | None = None
    max_results: int = 10
    amenities: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.max_price is not None:
            if float(self.max_price) <= 0:
                raise _bad("max_price must be a positive number.")
            if not self.currency:
                raise _bad(
                    "max_price needs a currency.",
                    "Pass currency as an ISO code, e.g. EUR, so the ceiling means something.",
                )
        if self.currency and not re.fullmatch(r"[A-Za-z]{3}", self.currency):
            raise _bad(f"currency '{self.currency}' is not a three-letter ISO code.")
        if not 1 <= int(self.max_results) <= MAX_RESULTS_CEILING:
            raise _bad(
                f"max_results must be between 1 and {MAX_RESULTS_CEILING}.",
                MAX_RESULTS_REASON,
            )

    def describe(self) -> str:
        parts = [f"Search of {self.place.describe()} for {self.stay.describe()}"]
        if self.max_price:
            parts.append(f"under {self.max_price} {self.currency}")
        return ", ".join(parts)


class Supplier:
    """What a supplier has to provide. Amadeus implements it; Booking.com will.

    Implementations raise AccommodationError for every failure, including a
    zero-result one. Returning an empty list is not an option any
    implementation has.
    """

    name = "unimplemented"

    def search(self, query: SearchQuery) -> dict:
        """Properties with prices for a place and a stay."""
        raise NotImplementedError

    def details(self, native_id: str, stay: Stay | None = None) -> dict:
        """Everything known about one property. Stay is optional: without it
        the answer is identity, location and reputation; with it, amenities,
        policies and rates for those dates as well."""
        raise NotImplementedError

    def offers(self, native_id: str, stay: Stay, **kwargs) -> dict:
        """Every bookable offer for one property and one stay, with prices."""
        raise NotImplementedError
