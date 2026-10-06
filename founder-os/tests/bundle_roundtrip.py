"""Founder bundle suite, shared by test_bundle_sqlite.py and test_bundle_postgres.py.

Not a test file on its own. Subclasses are unittest.TestCase and define
make_ledger(), which returns a new, freshly migrated, empty ledger on every
call, so a case can export from one database and import into another.
"""
from __future__ import annotations

import hashlib
import http.server
import json
import os
import pathlib
import sys
import tempfile
import threading
import unittest

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))

from founder_bundle import (  # noqa: E402
    BundleError, export_bundle, import_bundle, progress_payload, read_bundle, send_progress,
)
from founder_bundle.bundle import build_bundle, load_files  # noqa: E402
from founder_bundle.progress import ENV_KEY, ENV_URL, SIGNATURE_HEADER, TIMESTAMP_HEADER, verify  # noqa: E402
from founder_ledger import LedgerError  # noqa: E402
from founder_ledger.interface import BUNDLE_TABLES, TABLE_COLUMNS  # noqa: E402

ATTACHMENT = b"%PDF-1.4 pretend sprint test recording notes\n"


def populate(ledger, files_dir: pathlib.Path) -> str:
    """One founder with a row in every table, a gate pass, a gate fail and an
    attached file. A second founder exists so the export has something to leave out."""
    alice = ledger.create_founder("Alice", cohort="c4", context={"idea": "bike repair", "lang": "pt"})
    fid = alice["founder_id"]
    other = ledger.create_founder("Bob", cohort="c4")
    ledger.add_pain(other["founder_id"], quote="not alice's pain")

    sha = hashlib.sha256(ATTACHMENT).hexdigest()
    (files_dir / sha).write_bytes(ATTACHMENT)

    why = ledger.add_artifact(fid, stage=0, kind="why", title="Why bikes",
                              body="# Why\n\nCommuters lose a day when a bike breaks. Ação!\n")
    ledger.add_artifact(fid, stage=0, kind="why", body="Second draft.", meta={"source": "coach"})
    ledger.add_artifact(fid, stage=0, kind="Sprint Notes", body="See the attachment.",
                        meta={"files": [{"sha256": sha, "name": "notes.pdf", "media_type": "application/pdf"}]})
    pr = ledger.add_prfaq_version(fid, stage=0, body="PR/FAQ v0", assumptions=["commuters care", "they pay"])
    ledger.record_gate_decision(fid, stage=0, gate_id="stage-0-why", decision="pass", decided_by="claude",
                                evidence=[{"table": "artifacts", "id": why["id"]},
                                          {"table": "prfaq_versions", "id": pr["id"]}],
                                rationale="clear why")
    pain = ledger.add_pain(fid, quote="my chain snapped again", source_url="https://example.com/t/1",
                           watering_hole="r/bikecommuting", segment="commuters", job="get to work",
                           tags=["repair", "time"])
    ledger.add_pain(fid, quote="I spend every Sunday chasing receipts", source_url="https://example.com/t/2",
                    watering_hole="example.com", tags=["receipts"], page_title="Month-end is killing me",
                    note="weekly, and the clients cause it", screenshot_url="https://blob.example/s.png",
                    source="extension")
    audit = ledger.add_audit(fid, target_table="pains", target_id=pain["id"], auditor="laya",
                             check_name="is-real-quote", verdict="pass")
    ledger.record_gate_decision(fid, stage=1, gate_id="stage-1-audience", decision="pass", decided_by="claude",
                                evidence=[{"table": "pains", "id": pain["id"]}, {"table": "audits", "id": audit["id"]}],
                                rationale="audience named")
    ledger.add_interview(fid, interviewee="P1", notes="Talked about last breakdown.", conducted_on="2026-09-01",
                         segment="commuters", commitment="time", earlyvangelist=True)
    label = ledger.add_label(fid, task="pain_tag", target_table="pains", target_id=pain["id"],
                             input_text=pain["quote"], model_label={"pain": True}, model_version="laya-0.1",
                             confidence=0.8125)
    ledger.correct_label(fid, label["id"], corrected_label={"pain": True, "job": "commute"}, corrected_by="sean")
    ledger.record_gate_decision(fid, stage=2, gate_id="stage-2-pain", decision="fail", decided_by="claude",
                                evidence=[{"table": "pains", "id": pain["id"]}], rationale="too few quotes",
                                routes_to_stage=1)
    ledger.mark_gate_pending(fid, 1)
    return fid


def without_export_time(files: dict[str, bytes]) -> dict[str, bytes]:
    out = dict(files)
    manifest = json.loads(out["manifest.json"])
    manifest.pop("exported_at")
    out["manifest.json"] = json.dumps(manifest, sort_keys=True).encode()
    return out


class BundleRoundTrip:
    """Mixin. Subclasses are unittest.TestCase and define make_ledger()."""

    def make_ledger(self):
        raise NotImplementedError

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.files_src = self.tmp / "files-src"
        self.files_src.mkdir()
        self.ledgers = []
        self.src = self.fresh()
        self.fid = populate(self.src, self.files_src)

    def tearDown(self):
        for ledger in self.ledgers:
            ledger.close()
        self._tmp.cleanup()

    def fresh(self):
        ledger = self.make_ledger()
        self.ledgers.append(ledger)
        return ledger

    def export(self, ledger, name, fid=None, files_dir=None):
        path = self.tmp / name
        export_bundle(ledger, fid or self.fid, path, files_dir=files_dir or self.files_src)
        return path

    # --- the done-when criterion --------------------------------------------

    def test_round_trip_is_identical(self):
        first = self.export(self.src, "first")
        dst = self.fresh()
        files_dst = self.tmp / "files-dst"
        result = import_bundle(dst, first, files_dir=files_dst)
        self.assertEqual(result["files"], 1)
        second = self.export(dst, "second", files_dir=files_dst)
        a, b = load_files(first), load_files(second)
        self.assertEqual(sorted(a), sorted(b))
        self.assertEqual(without_export_time(a), without_export_time(b))
        for path in a:
            if path != "manifest.json":
                self.assertEqual(a[path], b[path], path)

    def test_zip_round_trip_matches_directory(self):
        as_dir = self.export(self.src, "dir")
        as_zip = self.export(self.src, "alice.zip")
        self.assertEqual(without_export_time(load_files(as_dir)), without_export_time(load_files(as_zip)))
        dst = self.fresh()
        import_bundle(dst, as_zip, files_dir=self.tmp / "fz")
        again = self.export(dst, "again.zip", files_dir=self.tmp / "fz")
        self.assertEqual(without_export_time(load_files(as_zip)), without_export_time(load_files(again)))

    # --- contents -----------------------------------------------------------

    def test_bundle_layout_and_scope(self):
        files = load_files(self.export(self.src, "b"))
        for table in BUNDLE_TABLES:
            rows = json.loads(files[f"ledger/{table}.json"])
            self.assertTrue(rows, f"{table} should have rows in the fixture")
            self.assertTrue(all(r["founder_id"] == self.fid for r in rows), table)
            self.assertEqual(set(rows[0]), set(TABLE_COLUMNS[table]), f"{table} columns drifted from the schema")
        self.assertIn("artifacts/stage-0/why-v1.md", files)
        self.assertIn("artifacts/stage-0/sprint-notes-v1.md", files)
        self.assertIn("prfaq/v0.md", files)
        sha = hashlib.sha256(ATTACHMENT).hexdigest()
        self.assertEqual(files[f"files/{sha}"], ATTACHMENT)
        md = files["artifacts/stage-0/why-v1.md"].decode()
        self.assertTrue(md.startswith("---\nid: "))
        self.assertIn("Ação!", md)
        manifest = json.loads(files["manifest.json"])
        self.assertEqual(manifest["format_version"], 1)
        self.assertEqual(manifest["schema_version"], "002")
        self.assertEqual(manifest["source"], "self-hosted")
        self.assertEqual(manifest["founder_id"], self.fid)
        self.assertEqual(manifest["counts"]["gate_decisions"], 3)

    # --- import rules -------------------------------------------------------

    def test_import_is_idempotent(self):
        bundle = self.export(self.src, "b")
        dst = self.fresh()
        fdir = self.tmp / "fd"
        first = import_bundle(dst, bundle, files_dir=fdir)
        second = import_bundle(dst, bundle, files_dir=fdir)
        self.assertGreater(sum(c["inserted"] for c in first["counts"].values()), 0)
        self.assertEqual(sum(c["inserted"] for c in second["counts"].values()), 0)
        self.assertEqual(second["files"], 0)
        self.assertEqual(without_export_time(build_bundle(dst, self.fid, source="self-hosted", files_dir=fdir)),
                         without_export_time(load_files(bundle)))

    def test_import_into_source_is_a_no_op(self):
        bundle = self.export(self.src, "b")
        result = import_bundle(self.src, bundle, files_dir=self.files_src)
        self.assertEqual(sum(c["inserted"] for c in result["counts"].values()), 0)

    def test_conflict_refuses_and_replace_wins(self):
        bundle = self.export(self.src, "b")
        dst = self.fresh()
        fdir = self.tmp / "fd"
        import_bundle(dst, bundle, files_dir=fdir)
        dst.update_founder_context(self.fid, {"idea": "changed locally"})
        dst.add_pain(self.fid, quote="added after import")
        with self.assertRaises(LedgerError) as ctx:
            import_bundle(dst, bundle, files_dir=fdir)
        self.assertIn("founders/", str(ctx.exception))
        self.assertEqual(dst.get_founder(self.fid)["context"], {"idea": "changed locally"})
        import_bundle(dst, bundle, files_dir=fdir, replace=True)
        self.assertEqual(without_export_time(build_bundle(dst, self.fid, source="self-hosted", files_dir=fdir)),
                         without_export_time(load_files(bundle)))

    def test_remap_under_a_new_founder_id(self):
        bundle = self.export(self.src, "b")
        dst = self.fresh()
        fdir = self.tmp / "fd"
        import_bundle(dst, bundle, files_dir=fdir)
        copy = import_bundle(dst, bundle, files_dir=fdir, as_founder="alice-selfhosted")
        again = import_bundle(dst, bundle, files_dir=fdir, as_founder="alice-selfhosted")
        self.assertEqual(copy["founder_id"], "alice-selfhosted")
        self.assertEqual(sum(c["inserted"] for c in again["counts"].values()), 0)
        orig_ids = {r["id"] for r in dst.list_pains(self.fid)}
        new_pains = dst.list_pains("alice-selfhosted")
        self.assertEqual(len(new_pains), 2)
        self.assertFalse({p["id"] for p in new_pains} & orig_ids)
        capture = next(p for p in new_pains if p["source"] == "extension")
        self.assertEqual((capture["page_title"], capture["note"]), ("Month-end is killing me",
                                                                    "weekly, and the clients cause it"))
        for d in dst.list_gate_decisions("alice-selfhosted"):
            for ref in d["evidence"]:
                self.assertTrue(dst._owns(ref["table"], "alice-selfhosted", ref["id"]))
        self.assertEqual(dst.list_audits("alice-selfhosted")[0]["target_id"], new_pains[0]["id"])

    def test_refuses_newer_format_version(self):
        bundle = self.export(self.src, "b")
        manifest = json.loads((bundle / "manifest.json").read_text())
        manifest["format_version"] = 2
        (bundle / "manifest.json").write_text(json.dumps(manifest))
        dst = self.fresh()
        with self.assertRaisesRegex(BundleError, "newer than this plugin"):
            import_bundle(dst, bundle, files_dir=self.tmp / "fd")
        self.assertIsNone(dst.get_founder(self.fid))

    def test_refuses_tampered_bundle(self):
        bundle = self.export(self.src, "b")
        path = bundle / "ledger" / "pains.json"
        path.write_text(path.read_text().replace("snapped", "SNAPPED"))
        with self.assertRaisesRegex(BundleError, "checksum mismatch: ledger/pains.json"):
            read_bundle(bundle)
        extra = self.export(self.src, "c")
        (extra / "ledger" / "extra.json").write_text("[]")
        with self.assertRaisesRegex(BundleError, "do not match SHA256SUMS"):
            read_bundle(extra)

    def test_refuses_dangling_reference(self):
        bundle = self.export(self.src, "b")
        manifest, tables, _ = read_bundle(bundle)
        tables["pains"] = []
        dst = self.fresh()
        with self.assertRaisesRegex(LedgerError, "does not own"):
            dst.import_founder_rows(self.fid, tables)
        self.assertIsNone(dst.get_founder(self.fid))

    def test_refuses_rows_of_another_founder_or_unknown_columns(self):
        _, tables, _ = read_bundle(self.export(self.src, "b"))
        dst = self.fresh()
        bad = dict(tables, pains=[dict(tables["pains"][0], founder_id="someone-else")])
        with self.assertRaisesRegex(LedgerError, "another founder"):
            dst.import_founder_rows(self.fid, bad)
        bad = dict(tables, pains=[dict(tables["pains"][0], sentiment="angry")])
        with self.assertRaisesRegex(LedgerError, "newer schema"):
            dst.import_founder_rows(self.fid, bad)

    # --- progress webhook ---------------------------------------------------

    def test_progress_payload_is_three_fields(self):
        payload = progress_payload(self.src, self.fid)
        self.assertEqual(set(payload), {"stage", "gate_status", "updated_at"})
        self.assertEqual(payload["stage"], 1)
        self.assertEqual(payload["gate_status"], "gate_pending")


class _Capture(http.server.BaseHTTPRequestHandler):
    received: list = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        _Capture.received.append((self.headers, body))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


class ProgressWebhookTest(unittest.TestCase):
    KEY = "test-signing-key-not-real"
    PAYLOAD = {"stage": 3, "gate_status": "gate_pending", "updated_at": "2026-09-26T10:00:00.000000Z"}

    def setUp(self):
        self.saved = {k: os.environ.pop(k, None) for k in (ENV_URL, ENV_KEY)}

    def tearDown(self):
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def test_off_unless_configured(self):
        self.assertIsNone(send_progress(self.PAYLOAD))

    def test_url_without_key_is_refused(self):
        os.environ[ENV_URL] = "https://example.com/hook"
        with self.assertRaisesRegex(ValueError, "signed"):
            send_progress(self.PAYLOAD)

    def test_posts_exactly_the_payload_signed(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), _Capture)
        threading.Thread(target=server.handle_request, daemon=True).start()
        try:
            os.environ[ENV_URL] = f"http://127.0.0.1:{server.server_port}/hook/c4-alice"
            os.environ[ENV_KEY] = self.KEY
            self.assertEqual(send_progress(self.PAYLOAD), 204)
        finally:
            server.server_close()
        headers, body = _Capture.received[-1]
        self.assertEqual(json.loads(body), self.PAYLOAD)
        self.assertTrue(headers["User-Agent"].startswith("behalfbot-founder-os"))
        ts, sig = headers[TIMESTAMP_HEADER], headers[SIGNATURE_HEADER]
        self.assertTrue(verify(self.KEY, ts, body, sig))
        self.assertFalse(verify("wrong-key", ts, body, sig))
        self.assertFalse(verify(self.KEY, ts, body.replace(b"3", b"4"), sig))
        self.assertFalse(verify(self.KEY, ts, body, sig, now=int(ts) + 301))
        self.assertTrue(verify(self.KEY, ts, body, sig, now=int(ts) + 299))
        self.assertFalse(verify(self.KEY, "not-a-number", body, sig))

    def test_refuses_extra_fields_and_plain_http(self):
        with self.assertRaises(ValueError):
            send_progress(dict(self.PAYLOAD, founder_id="a"), "https://example.com/h", self.KEY)
        with self.assertRaises(ValueError):
            send_progress(self.PAYLOAD, "http://example.com/h", self.KEY)


def run(*cases: type) -> int:
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite(loader.loadTestsFromTestCase(c) for c in cases)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1

