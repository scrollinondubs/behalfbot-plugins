#!/usr/bin/env python3
"""Dashboard pieces of the dating plugin that run without FastAPI or a DB:
the emulator DevOps panel and the swipe-store parsing/truth table.

Stdlib only. adb is stubbed on PATH (or removed from it) per case.
Run: python3 dating/tests/test_dashboard.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import stat
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

PLUGIN = pathlib.Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


panel_mod = _load("t_emulator_panel", "dashboard/emulator_panel.py")
swipes = _load("t_dating_swipes", "scripts/_dating_swipes.py")


class PanelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = {
            "CUSTOMER_HOME": str(self.home),
            "PATH": str(self.bin),
            "HOME": str(self.root / "userhome"),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def _adb(self, devices_output: str):
        script = self.bin / "adb"
        script.write_text(f"#!/bin/sh\nprintf '{devices_output}'\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

    def _rows(self, **extra):
        with mock.patch.dict(os.environ, {**self.env, **extra}, clear=True):
            result = panel_mod.panel()
        self.assertEqual(set(result), {"title", "rows"})
        for row in result["rows"]:
            self.assertEqual(set(row), {"label", "value", "status", "detail"})
            self.assertIn(row["status"], ("ok", "warn", "fail"))
        return {r["label"]: r for r in result["rows"]}

    def test_no_adb_degrades_to_warn(self):
        rows = self._rows()
        self.assertEqual(rows["ADB device state"]["status"], "warn")
        self.assertEqual(rows["ADB device state"]["value"], "adb not installed")

    def test_device_attached(self):
        self._adb("List of devices attached\\nemulator-5556\\tdevice\\n")
        rows = self._rows(DATING_ADB_SERIAL="emulator-5556")
        self.assertEqual(rows["ADB device state"]["status"], "ok")

    def test_device_offline_fails(self):
        self._adb("List of devices attached\\nemulator-5554\\toffline\\n")
        rows = self._rows()
        self.assertEqual(rows["ADB device state"]["value"], "offline")
        self.assertEqual(rows["ADB device state"]["status"], "fail")

    def test_optional_rows_skipped_when_unconfigured(self):
        rows = self._rows()
        self.assertNotIn("gfxstream error canary", rows)
        self.assertFalse(any(k.endswith("last fired") for k in rows))

    def test_recent_restart_warns(self):
        log_dir = self.home / "logs" / "scheduled"
        log_dir.mkdir(parents=True)
        ts = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        (log_dir / "dating-emulator-recovery.log").write_text(
            f"[{ts}] Restart successful - emulator X now ready (reason=emulator_ready)\n")
        rows = self._rows()
        self.assertEqual(rows["Uptime since last cold boot"]["status"], "warn")

    def test_swipe_slot_freshness(self):
        state = self.home / "scheduled-tasks"
        state.mkdir()
        now = datetime.now()
        (state / "heartbeat-state.json").write_text(json.dumps({
            "slot-a": {"last_fired": now.isoformat()},
            "slot-b": {"last_fired": (now - timedelta(days=2)).isoformat()},
        }))
        rows = self._rows(DATING_SWIPE_SLOTS="slot-a@0,slot-b@0,slot-c@0")
        self.assertEqual(rows["slot-a last fired"]["status"], "ok")
        self.assertEqual(rows["slot-b last fired"]["status"], "fail")
        self.assertEqual(rows["slot-c last fired"]["value"], "never")

    def test_probe_exception_becomes_fail_row(self):
        with mock.patch.object(panel_mod, "_snapshot_size", side_effect=OSError("boom")):
            rows = self._rows()
        self.assertEqual(rows["Snapshot dir size"]["status"], "fail")


class SwipesTest(unittest.TestCase):
    def test_parse_contract_names(self):
        p = swipes.parse_screenshot_name("Ana_33_Hinge_2026-05-08_like.png")
        self.assertEqual((p["name"], p["age"], p["platform"], p["action"]), ("Ana", 33, "Hinge", "like"))
        self.assertIsNone(swipes.parse_screenshot_name("Bee_unk_Hinge_2026-05-02_pass")["age"])
        self.assertEqual(swipes.parse_screenshot_name("Cy_Tinder_2026-05-02_pass.jpg")["platform"], "Tinder")
        self.assertIsNone(swipes.parse_screenshot_name("random.png"))

    def test_outcome_truth_table(self):
        c = swipes.classify_outcome
        self.assertEqual(c("like", "super-like"), "tp")
        self.assertEqual(c("incoming-like", "like"), "tp")
        self.assertEqual(c("pass", "like"), "fn")
        self.assertEqual(c("pass", "pass"), "tn")
        self.assertEqual(c("like", "pass"), "fp")
        self.assertEqual(c("like", "no-opinion"), "no_opinion")


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "fastapi not installed")
class TabImportTest(unittest.TestCase):
    def test_tab_imports_without_db(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BEHALFBOT_PG_DSN", None)
            os.environ.pop("CHASSIS_PG_DSN", None)
            tab = _load("t_dating_tab", "dashboard/tab.py")
        self.assertTrue(hasattr(tab, "router"))


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "fastapi not installed")
class SessionGalleryTest(unittest.TestCase):
    def setUp(self):
        from fastapi import HTTPException
        self.HTTPException = HTTPException
        self.tab = _load("t_dating_tab_gallery", "dashboard/tab.py")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"DATING_SESSIONS_DIR": str(self.root)})
        self.env.start()
        self.sess = self.root / "2030-01-02-slot1-123"
        self.sess.mkdir()
        for n in ("Ana_31_Hinge_2030-01-02_like.png", "Bea_unk_Tinder_2030-01-02_pass.jpg",
                  "loose.png", "notes.txt"):
            (self.sess / n).write_bytes(b"x")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_manifest_order_then_leftovers_with_labels(self):
        (self.sess / "manifest.json").write_text(json.dumps({"items": [
            {"file": "Bea_unk_Tinder_2030-01-02_pass.jpg"},
            {"file": "gone.png", "name": "Gone"},
            {"file": "Ana_31_Hinge_2030-01-02_like.png", "name": "Ana Maria"},
        ]}))
        items = self.tab.session_items(self.sess)
        self.assertEqual([i["file"] for i in items], [
            "Bea_unk_Tinder_2030-01-02_pass.jpg", "Ana_31_Hinge_2030-01-02_like.png", "loose.png"])
        bea, ana, loose = items
        self.assertEqual((bea["name"], bea["age"], bea["platform"], bea["action"]),
                         ("Bea", None, "Tinder", "pass"))
        self.assertEqual((ana["name"], ana["age"]), ("Ana Maria", 31))
        self.assertEqual((loose["name"], loose["platform"]), ("loose", ""))

    def test_no_manifest_lists_images_by_name(self):
        names = [i["name"] for i in self.tab.session_items(self.sess)]
        self.assertEqual(names, ["Ana", "Bea", "loose"])

    def test_bad_manifest_is_ignored(self):
        (self.sess / "manifest.json").write_text("{not json")
        self.assertEqual(len(self.tab.session_items(self.sess)), 3)

    def test_session_id_is_validated(self):
        for bad in ("../etc", ".hidden", "a/b", "a..b", ""):
            with self.assertRaises(self.HTTPException) as cm:
                self.tab._session_dir(bad)
            self.assertEqual(cm.exception.status_code, 400, bad)
        with self.assertRaises(self.HTTPException) as cm:
            self.tab._session_dir("2030-01-02-nope")
        self.assertEqual(cm.exception.status_code, 404)

    def test_image_route_serves_only_images_in_the_session(self):
        sid = self.sess.name
        resp = self.tab.session_image(sid, "Ana_31_Hinge_2030-01-02_like.png")
        self.assertEqual(pathlib.Path(resp.path), self.sess / "Ana_31_Hinge_2030-01-02_like.png")
        for bad, code in (("notes.txt", 404), ("manifest.json", 404), ("..", 400),
                          (".DS_Store", 400), ("missing.png", 404)):
            with self.assertRaises(self.HTTPException) as cm:
                self.tab.session_image(sid, bad)
            self.assertEqual(cm.exception.status_code, code, bad)


if __name__ == "__main__":
    unittest.main()
