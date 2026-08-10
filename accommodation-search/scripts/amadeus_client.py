#!/usr/bin/env python3
"""HTTP transport, OAuth2 and error translation for the Amadeus Self-Service API.

Credentials
===========
Read from the process environment and nowhere else. AMADEUS_CLIENT_ID and
AMADEUS_CLIENT_SECRET are never written to a file, never echoed into a log line,
and never placed in an error payload - the bearer token is not either. Both are
registered with the redactor on the way in, so even a supplier error that
somehow quoted the request back would be scrubbed before it reached the model.

Two error envelopes
===================
The token endpoint answers with a flat object; every other endpoint answers
with `{"errors": [...]}`. And the documented example for code 38191 ships
`code` and `status` as strings while every other example ships integers. Both
shapes are handled and both types are coerced, because the one time this parser
matters is the one time the response is unusual.

The codes that matter most
==========================
38194 and 38195 both arrive as HTTP 429 and they mean opposite things. 38194 is
the per-second rate limit: wait and it works. 38195 is the monthly quota:
waiting does nothing until the month turns over. Collapsing them into "429,
back off" produces an agent that retries for three weeks.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from accommodation_errors import (
    AUTH_FAILED,
    BAD_REQUEST,
    CREDENTIALS_MISSING,
    QUOTA_EXHAUSTED,
    RATE_LIMITED,
    SUPPLIER_ERROR,
    SUPPLIER_REPORTED_NO_MATCH,
    TRANSPORT_ERROR,
    AccommodationError,
)
from call_budget import CallBudget, budget_from_env

SUPPLIER = "amadeus"
VERSION = "0.1.0"
USER_AGENT = f"behalfbot-accommodation-search/{VERSION}"

HOSTS = {
    "test": "https://test.api.amadeus.com",
    "production": "https://api.amadeus.com",
}

TOKEN_PATH = "/v1/security/oauth2/token"

# Refresh this many seconds before the token's stated expiry. Matches the
# official SDK's buffer. A token that expires between the check and the request
# costs a retry and a wasted call against the quota.
TOKEN_REFRESH_BUFFER_SECONDS = 10

# The test environment documents both 10 transactions per second and a minimum
# gap of 100ms between requests. A single-threaded client that honours the gap
# cannot breach the rate, so the gap is the only thing enforced here.
MIN_REQUEST_INTERVAL_SECONDS = 0.1

CODE_KINDS = {
    38194: RATE_LIMITED,
    38195: QUOTA_EXHAUSTED,
    38187: AUTH_FAILED,
    38190: AUTH_FAILED,
    38191: AUTH_FAILED,
    38192: AUTH_FAILED,
    38193: AUTH_FAILED,
    39683: AUTH_FAILED,
    39686: AUTH_FAILED,
    38197: AUTH_FAILED,
    20: AUTH_FAILED,
    451: AUTH_FAILED,
    424: SUPPLIER_REPORTED_NO_MATCH,
    3664: SUPPLIER_REPORTED_NO_MATCH,
    1797: SUPPLIER_REPORTED_NO_MATCH,
    795: SUPPLIER_REPORTED_NO_MATCH,
    141: SUPPLIER_ERROR,
    38189: SUPPLIER_ERROR,
    450: SUPPLIER_ERROR,
    784: SUPPLIER_ERROR,
}

WHAT_TO_DO = {
    RATE_LIMITED: [
        "This is the per-second rate limit, not the monthly quota. Wait a "
        "second and repeat the same call; it will work.",
        "If it repeats, something else on this machine is calling the same "
        "account concurrently. The limit is per account, not per process.",
    ],
    QUOTA_EXHAUSTED: [
        "This is the monthly free-tier quota, not the per-second rate limit. "
        "Retrying will not work - the allowance resets at the start of the "
        "next calendar month.",
        "Check usage under 'My Self-Service Workspace' at "
        "developers.amadeus.com; the API does not report remaining quota.",
        "Tell the traveller the search could not be run this month, not that "
        "nothing was found.",
    ],
    AUTH_FAILED: [
        "Confirm AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET are set in the "
        "environment and belong to the environment being called - test keys "
        "do not work against production and the reverse is also true.",
        "Keys are revoked automatically if they were ever committed to a "
        "public repository. Regenerate at developers.amadeus.com if so.",
        "Do not print the credential values while debugging this.",
    ],
    SUPPLIER_REPORTED_NO_MATCH: [
        "The supplier said explicitly that nothing matched, which is not the "
        "same as a silent empty response and not the same as a quota failure.",
        "Widen the search: a larger radius, different dates, no price ceiling.",
        "Check the city code resolves to the city that was meant. A valid code "
        "for the wrong city returns a confident no-match.",
    ],
    BAD_REQUEST: [
        "The supplier rejected a parameter. The detail below names it.",
        "Do not retry the identical call; it will fail identically.",
    ],
    SUPPLIER_ERROR: [
        "A supplier-side failure. Retrying once after a short pause is "
        "reasonable; repeated failures are not this plugin's to fix.",
    ],
    TRANSPORT_ERROR: [
        "The request did not complete. Check network egress to the Amadeus "
        "host, then retry once.",
    ],
}


class Redactor:
    """Removes registered secret values from anything on its way out.

    Belt and braces. Nothing in this plugin deliberately puts a credential into
    an output, but tool output is read by a model and forwarded into logs, and
    SECURITY.md treats a credential reaching either as a vulnerability. So the
    values are scrubbed at the boundary regardless of how they got there.
    """

    def __init__(self) -> None:
        self._secrets: list[str] = []

    def register(self, value: str | None) -> None:
        if isinstance(value, str) and len(value.strip()) >= 8:
            self._secrets.append(value.strip())

    def scrub(self, value):
        if isinstance(value, str):
            for secret in self._secrets:
                if secret in value:
                    value = value.replace(secret, "[redacted]")
            return value
        if isinstance(value, dict):
            return {key: self.scrub(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.scrub(item) for item in value]
        return value


REDACTOR = Redactor()


def _coerce_int(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def map_error(http_status: int, body: object, endpoint: str) -> AccommodationError:
    """Translate an Amadeus failure into this plugin's vocabulary.

    Handles the flat token envelope and the errors[] envelope, and never
    assumes a numeric field arrived as a number.
    """
    code = None
    title = None
    detail = None
    source = None

    if isinstance(body, dict):
        errors = body.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            first = errors[0]
            code = _coerce_int(first.get("code"))
            title = first.get("title")
            detail = first.get("detail")
            source = first.get("source")
            http_status = _coerce_int(first.get("status")) or http_status
        elif "error" in body or "error_description" in body:
            code = _coerce_int(body.get("code"))
            title = body.get("title") or body.get("error")
            detail = body.get("error_description")

    kind = CODE_KINDS.get(code)
    if kind is None:
        if http_status == 429:
            kind = RATE_LIMITED
        elif http_status in (401, 403):
            kind = AUTH_FAILED
        elif http_status == 404:
            kind = SUPPLIER_REPORTED_NO_MATCH
        elif 400 <= http_status < 500:
            kind = BAD_REQUEST
        else:
            kind = SUPPLIER_ERROR

    summary = " - ".join(str(part) for part in (title, detail) if part) or "no detail given"
    message = (
        f"Amadeus refused {endpoint}: {summary} "
        f"(HTTP {http_status}, code {code if code is not None else 'none'})."
    )
    return AccommodationError(
        kind=kind,
        message=REDACTOR.scrub(message),
        what_to_do=WHAT_TO_DO.get(kind, WHAT_TO_DO[SUPPLIER_ERROR]),
        supplier=SUPPLIER,
        detail=REDACTOR.scrub(
            {
                "http_status": http_status,
                "supplier_code": code,
                "supplier_title": title,
                "supplier_detail": detail,
                "supplier_source": source,
                "endpoint": endpoint,
            }
        ),
    )


class HttpTransport:
    """urllib, with a User-Agent because a request without one gets refused by
    the edge in front of some hosts and the failure looks nothing like an auth
    problem."""

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def request(self, method: str, url: str, headers: dict, body: bytes | None):
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("User-Agent", USER_AGENT)
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            raise AccommodationError(
                kind=TRANSPORT_ERROR,
                message=REDACTOR.scrub(f"Could not reach Amadeus: {error}"),
                what_to_do=WHAT_TO_DO[TRANSPORT_ERROR],
                supplier=SUPPLIER,
            ) from None


class FixtureTransport:
    """Serves committed JSON fixtures instead of calling the supplier.

    This is how the plugin is demonstrable, testable and reviewable with no
    account at all. It is also the shape of a lie if it is ever quiet about
    itself, so it is not quiet: every call prints a banner to stderr, and every
    result built from it carries data_source "fixture" all the way out to the
    tool response.
    """

    def __init__(self, directory: str | os.PathLike, stderr=None) -> None:
        self.directory = Path(directory)
        self._stderr = stderr

    def request(self, method: str, url: str, headers: dict, body: bytes | None):
        name = fixture_name_for(url)
        path = self.directory / f"{name}.json"
        if self._stderr is not None:
            self._stderr.write(
                f"[accommodation-search] FIXTURE MODE: serving {path.name} "
                f"instead of calling {url.split('?')[0]}. This is canned data.\n"
            )
            self._stderr.flush()
        try:
            raw = path.read_bytes()
        except OSError:
            raise AccommodationError(
                kind=TRANSPORT_ERROR,
                message=(
                    f"Fixture mode is on and there is no fixture at {path}. "
                    f"Fixture mode only answers the calls the committed "
                    f"fixtures cover."
                ),
                what_to_do=[
                    "Unset ACCOMMODATION_FIXTURE_DIR to make real calls, which "
                    "needs credentials.",
                    f"Or add {path.name} to the fixture directory.",
                ],
                supplier=SUPPLIER,
            ) from None
        # Always 200. A fixture that represents a failure carries the
        # supplier's own errors[] envelope, and the error mapper reads the
        # status out of that envelope - so a failure fixture is just a file,
        # with no out-of-band status to keep in sync with it.
        return 200, raw


def fixture_name_for(url: str) -> str:
    """Map a request URL onto a fixture filename. Path-based and version-free,
    so a fixture set is readable at a glance, does not depend on query-string
    ordering, and does not have to be renamed when an endpoint goes to v4."""
    segments = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    if segments and len(segments[0]) >= 2 and segments[0][0] == "v" and segments[0][1:].isdigit():
        segments = segments[1:]
    return "-".join(segments)


class AmadeusClient:
    def __init__(
        self,
        client_id: str | None,
        client_secret: str | None,
        environment: str = "test",
        transport=None,
        budget: CallBudget | None = None,
        clock=None,
        sleeper=None,
        fixture_mode: bool = False,
    ) -> None:
        if environment not in HOSTS:
            raise AccommodationError(
                kind=BAD_REQUEST,
                message=(
                    f"Unknown Amadeus environment '{environment}'. "
                    f"Use 'test' or 'production'."
                ),
                what_to_do=["Set AMADEUS_ENVIRONMENT to test or production."],
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.environment = environment
        self.host = HOSTS[environment]
        self.transport = transport or HttpTransport()
        self.budget = budget or CallBudget(Path("/dev/null"))
        self.fixture_mode = fixture_mode
        self._clock = clock or time.time
        self._sleep = sleeper if sleeper is not None else time.sleep
        self._token = None
        self._token_expires_at = 0.0
        self._last_request_at = 0.0
        REDACTOR.register(client_secret)

    @classmethod
    def from_env(cls, env=None, transport=None, budget=None, stderr=None):
        env = os.environ if env is None else env
        fixture_dir = env.get("ACCOMMODATION_FIXTURE_DIR")
        fixture_mode = bool(fixture_dir)
        if transport is None and fixture_mode:
            transport = FixtureTransport(fixture_dir, stderr=stderr)
        client_id = env.get("AMADEUS_CLIENT_ID")
        client_secret = env.get("AMADEUS_CLIENT_SECRET")
        if not fixture_mode and not (client_id and client_secret):
            raise AccommodationError(
                kind=CREDENTIALS_MISSING,
                message=(
                    "AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET are not both "
                    "set. This plugin reads them from the environment only and "
                    "never from a file, so there is nothing to fall back to."
                ),
                what_to_do=[
                    "Register a free Self-Service account at "
                    "developers.amadeus.com, create an app, and export the API "
                    "Key as AMADEUS_CLIENT_ID and the API Secret as "
                    "AMADEUS_CLIENT_SECRET.",
                    "Set ACCOMMODATION_FIXTURE_DIR to the plugin's "
                    "tests/fixtures directory to exercise the tools offline "
                    "against canned data instead.",
                    "Do not write the values into a file inside this repo.",
                ],
                supplier=SUPPLIER,
            )
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            environment=env.get("AMADEUS_ENVIRONMENT", "test").strip().lower(),
            transport=transport,
            budget=budget if budget is not None else budget_from_env(env),
            fixture_mode=fixture_mode,
        )

    @property
    def data_source(self) -> str:
        return "fixture" if self.fixture_mode else f"amadeus-{self.environment}"

    def _pace(self) -> None:
        if self.fixture_mode:
            return
        elapsed = self._clock() - self._last_request_at
        if 0 <= elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            self._sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request_at = self._clock()

    def _spend(self, endpoint: str) -> None:
        if not self.fixture_mode:
            self.budget.check()
        self.budget.record(endpoint, fixture=self.fixture_mode)

    def _decode(self, raw: bytes) -> object:
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def access_token(self) -> str:
        now = self._clock()
        if self._token and now + TOKEN_REFRESH_BUFFER_SECONDS < self._token_expires_at:
            return self._token
        if self.fixture_mode:
            self._token = "fixture-token"
            self._token_expires_at = now + 1799
            return self._token

        self._spend("token")
        self._pace()
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        ).encode("utf-8")
        status, raw = self.transport.request(
            "POST",
            f"{self.host}{TOKEN_PATH}",
            {"Content-Type": "application/x-www-form-urlencoded"},
            body,
        )
        payload = self._decode(raw)
        if status != 200 or not isinstance(payload, dict) or not payload.get("access_token"):
            raise map_error(status, payload, "the OAuth2 token endpoint")
        self._token = payload["access_token"]
        REDACTOR.register(self._token)
        try:
            lifetime = int(payload.get("expires_in") or 0)
        except (TypeError, ValueError):
            lifetime = 0
        self._token_expires_at = now + max(lifetime, 60)
        return self._token

    def get(self, path: str, params: dict, label: str) -> dict:
        """One authenticated GET. Returns the decoded body or raises."""
        token = self.access_token()
        query = urllib.parse.urlencode(
            {key: value for key, value in params.items() if value not in (None, "", [])},
            doseq=True,
        )
        url = f"{self.host}{path}" + (f"?{query}" if query else "")

        self._spend(label)
        self._pace()
        status, raw = self.transport.request(
            "GET", url, {"Authorization": f"Bearer {token}", "Accept": "application/json"}, None
        )
        payload = self._decode(raw)
        if status != 200 or not isinstance(payload, dict):
            raise map_error(status, payload, label)
        if isinstance(payload.get("errors"), list) and payload["errors"]:
            raise map_error(status, payload, label)
        return payload
