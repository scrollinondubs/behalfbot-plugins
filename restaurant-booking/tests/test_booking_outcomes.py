#!/usr/bin/env python3
"""test_booking_outcomes.py - the refusal paths, tested without touching TheFork.

The dangerous outcome for this plugin is not a failed booking, it is a real
reservation in the operator's name that nobody approved, or a confident
"no availability" that was actually a moved selector. Both are decided by code
that can be exercised offline, so it is.

Stdlib only, no network, no browser - the bar every plugin suite in this repo
has to meet.

Run:
    python3 tests/test_booking_outcomes.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SCRIPTS = PLUGIN_ROOT / "scripts"


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, str(PLUGIN_SCRIPTS / filename))
    module = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(module)  # type: ignore
    return module


book = _load("book_restaurant", "book-restaurant.py")
confirm = _load("confirm_via_discord", "confirm-via-discord.py")


def _script(dry_run: bool = False) -> str:
    return book._build_playwright_script(
        username="operator@example.com",
        password="never-embedded",
        restaurant_url="https://www.thefork.pt/restaurante/example-r1",
        restaurant_name="Example",
        date_str="2026-09-01",
        time_str="13:00",
        party_size=2,
        notes=None,
        dry_run=dry_run,
        logs_dir="/tmp/restaurant-booking-test",
        tolerance_minutes=30,
    )


class TestGeneratedScript(unittest.TestCase):
    """The Playwright flow is a generated template string, so nothing in it is
    checked by the interpreter until a booking is attempted for real. These are
    the assertions that would otherwise only fire in front of a live form."""

    def test_script_is_valid_javascript(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(_script())
            path = fh.name
        proc = subprocess.run([node, "--check", path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"generated script is not valid JS: {proc.stderr}")

    def test_password_never_embedded_in_generated_script(self):
        self.assertNotIn("never-embedded", _script())
        self.assertIn("process.env.THEFORK_PASSWORD", _script())

    def test_block_detection_runs_after_every_navigation(self):
        script = _script()
        self.assertEqual(script.count("await assertNotBlocked("), 2)
        for signature in ("access is temporarily restricted", "we detected unusual activity"):
            self.assertIn(signature, script)

    def test_blocked_page_exits_with_its_own_code(self):
        self.assertIn("EXIT_BLOCKED = 4", _script())
        self.assertIn("blocked_by_bot_detection", _script())

    def test_incomplete_form_never_reaches_the_confirm_step(self):
        """A half-filled form used to be a stderr warning that carried on to ask a
        human to approve a screenshot of it. A soft-confirm gate is only a gate
        if what is shown is what would be submitted."""
        script = _script()
        gate = script.index("if (!partySizeSet || !dateSet || !timeSet)")
        confirm_call = script.index("Calling Discord soft-confirm")
        self.assertLess(gate, confirm_call)
        self.assertIn("EXIT_NO_USABLE_SLOT", script[gate:confirm_call])

    def test_never_claims_no_availability(self):
        """A rotted selector and a full restaurant are indistinguishable from
        here, and only one of them is the operator's problem to act on."""
        script = _script()
        self.assertNotIn("no_availability", script)
        self.assertNotIn("fully booked", script.lower())
        self.assertIn("no_usable_slot", script)

    def test_empty_and_broken_slot_lookups_are_distinguishable(self):
        script = _script()
        for outcome in ("selector_not_found", "slot_list_empty", "no_slot_within_tolerance"):
            self.assertIn(outcome, script)

    def test_tolerance_comes_from_config_not_a_literal(self):
        script = book._build_playwright_script(
            username="u", password="p",
            restaurant_url="https://www.thefork.pt/restaurante/example-r1",
            restaurant_name="Example", date_str="2026-09-01", time_str="13:00",
            party_size=2, notes=None, dry_run=False, logs_dir="/tmp/x",
            tolerance_minutes=45,
        )
        self.assertIn("const TOLERANCE_MINUTES = 45;", script)
        self.assertIn("nearestDiff <= TOLERANCE_MINUTES", script)

    def test_confirm_subprocess_takes_an_argv_array(self):
        """The restaurant name arrives from a chat message. Interpolating it into
        a shell string is a command-injection path into the host."""
        script = _script()
        self.assertNotIn("execSync(", script)
        self.assertIn("spawnSync('python3', [", script)

    def test_consent_failure_fails_closed(self):
        script = _script()
        tail = script[script.index("Calling Discord soft-confirm"):]
        catch = tail.index("Discord confirm error")
        self.assertIn("confirmed = false;", tail[catch:catch + 400])

    def test_dry_run_stops_before_the_confirm_step(self):
        script = _script(dry_run=True)
        self.assertIn("const DRY_RUN = true;", script)
        stop = script.index("DRY RUN: stopping before confirm button")
        self.assertLess(stop, script.index("Calling Discord soft-confirm"))

    def test_unverified_submission_is_not_reported_as_confirmed(self):
        script = _script()
        self.assertIn("submitted_outcome_unknown", script)
        marker = script.index("if (confirmationNumber === 'unknown')")
        self.assertLess(marker, script.index("status: 'confirmed',"))


class TestReactionGate(unittest.TestCase):
    """Who is allowed to say yes."""

    SEAN = "925210608310312991"
    BOT = "111111111111111111"
    BYSTANDER = "222222222222222222"

    def test_bot_only_reaction_is_not_approval(self):
        users = [{"id": self.BOT, "bot": True}]
        self.assertFalse(confirm.reaction_is_authorised(users))
        self.assertFalse(confirm.reaction_is_authorised(users, self.SEAN))

    def test_approver_reaction_is_approval(self):
        users = [{"id": self.BOT, "bot": True}, {"id": self.SEAN}]
        self.assertTrue(confirm.reaction_is_authorised(users, self.SEAN))

    def test_bystander_cannot_approve_when_an_approver_is_configured(self):
        """The old rule counted any second reactor, so in a multi-party channel
        someone else could book a table in the operator's name."""
        users = [{"id": self.BOT, "bot": True}, {"id": self.BYSTANDER}]
        self.assertFalse(confirm.reaction_is_authorised(users, self.SEAN))
        self.assertTrue(confirm.reaction_is_authorised(users))

    def test_empty_and_malformed_payloads_are_not_approval(self):
        for payload in ([], None, {}, "ok", [None], ["x"]):
            self.assertFalse(confirm.reaction_is_authorised(payload, self.SEAN))
            self.assertFalse(confirm.reaction_is_authorised(payload))

    def test_cancel_is_checked_before_confirm(self):
        """If both emoji are set, the tie has to resolve to not booking."""
        source = (PLUGIN_SCRIPTS / "confirm-via-discord.py").read_text()
        poll = source[source.index("def _poll_for_reaction"):]
        self.assertLess(poll.index("CANCEL_EMOJI"), poll.index("CONFIRM_EMOJI"))


class TestTimeoutPrecedence(unittest.TestCase):
    """The abort-on-timeout path was untestable in under ten minutes because the
    shipped config value silently overrode --timeout."""

    def test_cli_beats_config(self):
        self.assertEqual(confirm.resolve_timeout(30, {"confirm_timeout_seconds": "600"}), 30)

    def test_config_used_when_no_cli_value(self):
        self.assertEqual(confirm.resolve_timeout(None, {"confirm_timeout_seconds": "120"}), 120)

    def test_default_when_neither(self):
        self.assertEqual(confirm.resolve_timeout(None, {}), confirm.TIMEOUT_SECONDS)

    def test_unparseable_config_falls_back_rather_than_crashing(self):
        self.assertEqual(
            confirm.resolve_timeout(None, {"confirm_timeout_seconds": "ten minutes"}),
            confirm.TIMEOUT_SECONDS,
        )

    def test_timeout_flag_defaults_to_none(self):
        source = (PLUGIN_SCRIPTS / "confirm-via-discord.py").read_text()
        block = source[source.index('"--timeout"'):]
        self.assertIn("default=None", block[:400])


class TestExitCodeContract(unittest.TestCase):
    """The orchestrator branches on these, and the README documents them."""

    def test_codes_are_distinct_and_documented(self):
        codes = {
            book.EXIT_OK: 0, book.EXIT_ERROR: 1, book.EXIT_ABORTED: 2,
            book.EXIT_DRY_RUN: 3, book.EXIT_BLOCKED: 4, book.EXIT_NO_USABLE_SLOT: 5,
        }
        self.assertEqual(len(codes), 6)
        readme = (PLUGIN_ROOT / "README.md").read_text()
        for code, meaning in ((4, "blocked_by_bot_detection"), (5, "no_usable_slot")):
            self.assertRegex(readme, re.compile(rf"^\| {code} \|", re.MULTILINE))
            self.assertIn(meaning, readme)

    def test_js_and_python_exit_codes_agree(self):
        script = _script()
        for name, value in [
            ("EXIT_OK", book.EXIT_OK), ("EXIT_ERROR", book.EXIT_ERROR),
            ("EXIT_ABORTED", book.EXIT_ABORTED), ("EXIT_DRY_RUN", book.EXIT_DRY_RUN),
            ("EXIT_BLOCKED", book.EXIT_BLOCKED), ("EXIT_NO_USABLE_SLOT", book.EXIT_NO_USABLE_SLOT),
        ]:
            self.assertRegex(script, rf"{name} = {value}\b")


class TestCredentialHandling(unittest.TestCase):
    """Vaultwarden at invocation, nothing persisted, nothing in .env."""

    def test_password_is_not_written_to_the_session_file(self):
        source = (PLUGIN_SCRIPTS / "book-restaurant.py").read_text()
        run_booking = source[source.index("def run_booking("):source.index("def _parse_json_or_none")]
        self.assertIn("password intentionally excluded from session file", run_booking)
        self.assertNotIn('session_data["password"]', run_booking)

    def test_credentials_come_from_vaultwarden_not_env(self):
        source = (PLUGIN_SCRIPTS / "book-restaurant.py").read_text()
        self.assertIn("bw-fetch.sh", source)
        for env_name in ("THEFORK_USERNAME", "THEFORK_EMAIL"):
            self.assertNotIn(f'environ.get("{env_name}"', source)
        # The one env var that does carry the password is the handoff to the
        # child process, which never touches disk.
        self.assertIn('"THEFORK_PASSWORD": password', source)

    def test_config_ships_no_credentials(self):
        config = (PLUGIN_ROOT / "config" / "restaurant-booking.yaml").read_text()
        self.assertIn('vaultwarden_item_name: "thefork-credentials"', config)
        for banned in ("password:", "secret:", "token:"):
            self.assertNotIn(banned, config.lower())


class TestManifest(unittest.TestCase):
    def test_plugin_stays_dormant_by_default(self):
        manifest = json.loads((PLUGIN_ROOT / "openclaw.plugin.json").read_text())
        enabled = manifest["configSchema"]["properties"]["enabled"]
        self.assertFalse(enabled["default"])
        self.assertIn("enabled", manifest["configSchema"]["required"])

    def test_playwright_is_pinned_exactly(self):
        pkg = json.loads((PLUGIN_ROOT / "package.json").read_text())
        version = pkg["dependencies"]["playwright"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$", "playwright must be an exact pin")
        lock = json.loads((PLUGIN_ROOT / "package-lock.json").read_text())
        self.assertEqual(lock["packages"][""]["dependencies"]["playwright"], version)
        self.assertEqual(lock["packages"]["node_modules/playwright"]["version"], version)

    def test_no_em_dashes(self):
        for path in [
            PLUGIN_ROOT / "README.md",
            PLUGIN_ROOT / "openclaw.plugin.json",
            PLUGIN_ROOT / "config" / "restaurant-booking.yaml",
            PLUGIN_SCRIPTS / "book-restaurant.py",
            PLUGIN_SCRIPTS / "confirm-via-discord.py",
        ]:
            self.assertNotIn("—", path.read_text(), f"em dash in {path.name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
