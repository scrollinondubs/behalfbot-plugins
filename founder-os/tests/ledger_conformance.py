"""Adapter conformance suite for the FounderOS ledger.

Not a test file on its own: test_ledger_sqlite.py and test_ledger_postgres.py
each subclass LedgerConformance with a make_ledger() that returns a freshly
migrated, empty ledger. Every adapter has to pass every case here unchanged.
VCL's Turso implementation should port these cases (docs/ledger-on-turso.md).
"""
from __future__ import annotations

import pathlib
import sys
import unittest

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))

from founder_ledger import LedgerError, NotFound  # noqa: E402
from founder_ledger.migrate import migration_files  # noqa: E402

LEDGER_TABLES = (
    "founders", "stage_progress", "artifacts", "pains", "interviews",
    "audits", "gate_decisions", "prfaq_versions", "labels",
)


class LedgerConformance:
    """Mixin. Subclasses are unittest.TestCase and define make_ledger()."""

    def make_ledger(self):
        raise NotImplementedError

    def setUp(self):
        self.ledger = self.make_ledger()
        self.alice = self.ledger.create_founder("Alice", cohort="c4", context={"idea": "bike repair"})
        self.bob = self.ledger.create_founder("Bob", cohort="c4")
        self.a = self.alice["founder_id"]
        self.b = self.bob["founder_id"]

    def tearDown(self):
        self.ledger.close()

    # --- helpers ------------------------------------------------------------

    def artifact(self, fid=None, stage=0, kind="note"):
        return self.ledger.add_artifact(fid or self.a, stage=stage, kind=kind, body="some evidence")

    def pass_gate(self, stage, **extra):
        art = self.artifact(stage=stage, kind=f"evidence-{stage}")
        kwargs = dict(stage=stage, gate_id=f"stage-{stage}-gate", decision="pass", decided_by="claude",
                      evidence=[{"table": "artifacts", "id": art["id"]}], rationale="looks good")
        if stage >= 3:
            kwargs.update(decided_by="claude+sean", sean_signoff=True)
        kwargs.update(extra)
        return self.ledger.record_gate_decision(self.a, **kwargs)

    # --- schema -------------------------------------------------------------

    def test_migrations_are_recorded_and_idempotent(self):
        expected = [v for v, _ in migration_files()]
        recorded = [r["version"] for r in self.ledger._fetch("SELECT version FROM ledger_migrations ORDER BY version")]
        self.assertEqual(recorded, expected)
        self.assertEqual(self.ledger.run_migrations(), [])

    def test_every_table_exists_and_carries_founder_id(self):
        for table in LEDGER_TABLES:
            with self.subTest(table=table):
                rows = self.ledger._fetch(f"SELECT founder_id FROM {table} WHERE 1 = 0")
                self.assertEqual(rows, [])

    def test_schema_rejects_pass_without_sean_at_stage_3(self):
        # The rule lives in the schema too, so an implementation that skips the
        # interface check still cannot write the row.
        with self.assertRaises(Exception):
            with self.ledger._tx():
                self.ledger._execute(
                    "INSERT INTO gate_decisions (id, founder_id, stage, gate_id, decision, decided_by,"
                    " sean_signoff, evidence, rationale, created_at)"
                    " VALUES ('x', ?, 3, 'g', 'pass', 'claude', 0, '[1]', 'r', 't')", (self.a,))

    def test_schema_rejects_empty_evidence(self):
        with self.assertRaises(Exception):
            with self.ledger._tx():
                self.ledger._execute(
                    "INSERT INTO gate_decisions (id, founder_id, stage, gate_id, decision, decided_by,"
                    " sean_signoff, evidence, rationale, created_at)"
                    " VALUES ('x', ?, 0, 'g', 'pass', 'claude', 0, '[]', 'r', 't')", (self.a,))

    def test_foreign_keys_are_enforced(self):
        with self.assertRaises(Exception):
            with self.ledger._tx():
                self.ledger._execute(
                    "INSERT INTO pains (id, founder_id, quote, tags, created_at) VALUES ('x', 'ghost', 'q', '[]', 't')")

    # --- founders -----------------------------------------------------------

    def test_create_founder_starts_at_stage_0(self):
        self.assertEqual(self.alice["current_stage"], 0)
        self.assertEqual(self.alice["context"], {"idea": "bike repair"})
        self.assertEqual(self.alice["cohort"], "c4")
        progress = self.ledger.list_stage_progress(self.a)
        self.assertEqual([(p["stage"], p["status"]) for p in progress], [(0, "in_progress")])

    def test_explicit_founder_id_and_missing_founder(self):
        f = self.ledger.create_founder("Cara", founder_id="vcl-user-42")
        self.assertEqual(f["founder_id"], "vcl-user-42")
        self.assertIsNone(self.ledger.get_founder("nobody"))
        with self.assertRaises(NotFound):
            self.ledger.add_pain("nobody", quote="q")

    def test_update_context(self):
        f = self.ledger.update_founder_context(self.a, {"idea": "tool library", "hours": 10})
        self.assertEqual(f["context"], {"hours": 10, "idea": "tool library"})

    def test_delete_founder_cascades(self):
        art = self.artifact()
        self.ledger.add_pain(self.a, quote="it hurts")
        self.ledger.add_label(self.a, task="pain_tag", target_table="artifacts", target_id=art["id"],
                              input_text="x", model_label="pain", model_version="laya-0")
        self.ledger.delete_founder(self.a)
        self.assertIsNone(self.ledger.get_founder(self.a))
        for table in LEDGER_TABLES:
            with self.subTest(table=table):
                self.assertEqual(self.ledger._fetch(f"SELECT 1 AS hit FROM {table} WHERE founder_id = ?", (self.a,)), [])
        self.assertIsNotNone(self.ledger.get_founder(self.b))

    # --- tenant isolation ---------------------------------------------------

    def test_founders_cannot_see_each_others_rows(self):
        art = self.artifact()
        self.ledger.add_pain(self.a, quote="alice pain")
        self.ledger.add_interview(self.a, interviewee="p1", notes="n")
        self.ledger.add_prfaq_version(self.a, stage=0, body="v0")
        self.assertIsNone(self.ledger.get_artifact(self.b, art["id"]))
        self.assertEqual(self.ledger.list_artifacts(self.b), [])
        self.assertEqual(self.ledger.list_pains(self.b), [])
        self.assertEqual(self.ledger.list_interviews(self.b), [])
        self.assertIsNone(self.ledger.latest_prfaq(self.b))

    def test_cannot_cite_another_founders_evidence(self):
        bobs = self.artifact(fid=self.b)
        with self.assertRaises(LedgerError):
            self.ledger.record_gate_decision(
                self.a, stage=0, gate_id="g", decision="pass", decided_by="claude",
                evidence=[{"table": "artifacts", "id": bobs["id"]}], rationale="r")
        self.assertEqual(self.ledger.list_gate_decisions(self.a), [])

    def test_cannot_audit_or_label_another_founders_row(self):
        bobs = self.artifact(fid=self.b)
        with self.assertRaises(NotFound):
            self.ledger.add_audit(self.a, target_table="artifacts", target_id=bobs["id"],
                                  auditor="claude", check_name="c", verdict="pass")
        with self.assertRaises(NotFound):
            self.ledger.add_label(self.a, task="t", target_table="artifacts", target_id=bobs["id"],
                                  input_text="x", model_label=1, model_version="v")
        label = self.ledger.add_label(self.b, task="t", target_table="artifacts", target_id=bobs["id"],
                                      input_text="x", model_label=1, model_version="v")
        with self.assertRaises(NotFound):
            self.ledger.correct_label(self.a, label["id"], corrected_label=0, corrected_by="alice")

    # --- artifacts, pains, interviews, audits -------------------------------

    def test_artifacts_version_per_kind_and_never_overwrite(self):
        a1 = self.ledger.add_artifact(self.a, stage=1, kind="audience", body="v1", meta={"n": 1})
        a2 = self.ledger.add_artifact(self.a, stage=1, kind="audience", body="v2")
        w1 = self.ledger.add_artifact(self.a, stage=1, kind="watering_holes", body="w1", title="Places")
        self.assertEqual((a1["version"], a2["version"], w1["version"]), (1, 2, 1))
        self.assertEqual(a1["meta"], {"n": 1})
        self.assertEqual(a2["meta"], {})
        self.assertEqual(self.ledger.get_artifact(self.a, a1["id"])["body"], "v1")
        self.assertEqual(len(self.ledger.list_artifacts(self.a, stage=1)), 3)
        self.assertEqual([r["version"] for r in self.ledger.list_artifacts(self.a, kind="audience")], [1, 2])

    def test_pains_filter_by_job_and_keep_tags(self):
        self.ledger.add_pain(self.a, quote="q1", job="get paid", tags=["money", "late"],
                             source_url="https://example.com/t/1", watering_hole="forum")
        self.ledger.add_pain(self.a, quote="q2", job="find clients")
        paid = self.ledger.list_pains(self.a, job="get paid")
        self.assertEqual(len(paid), 1)
        self.assertEqual(paid[0]["tags"], ["money", "late"])
        self.assertEqual(len(self.ledger.list_pains(self.a)), 2)

    def test_pains_keep_capture_columns_and_reject_a_bad_source(self):
        p = self.ledger.add_pain(self.a, quote="receipts again", page_title="Month-end", note="typed by me",
                                 screenshot_url="https://blob.example/s.png", source="extension")
        self.assertEqual((p["page_title"], p["note"], p["screenshot_url"], p["source"]),
                         ("Month-end", "typed by me", "https://blob.example/s.png", "extension"))
        plain = self.ledger.add_pain(self.a, quote="older shape")
        self.assertEqual((plain["page_title"], plain["note"], plain["screenshot_url"], plain["source"]),
                         (None, None, None, None))
        with self.assertRaises(LedgerError):
            self.ledger.add_pain(self.a, quote="q", source="scraper")

    def test_interviews_round_trip_bools_and_reject_bad_commitment(self):
        i = self.ledger.add_interview(self.a, interviewee="P1", notes="n", commitment="money", earlyvangelist=True)
        self.assertIs(i["earlyvangelist"], True)
        self.assertEqual(i["commitment"], "money")
        with self.assertRaises(LedgerError):
            self.ledger.add_interview(self.a, interviewee="P2", notes="n", commitment="vibes")

    def test_audits(self):
        i = self.ledger.add_interview(self.a, interviewee="P1", notes="n")
        au = self.ledger.add_audit(self.a, target_table="interviews", target_id=i["id"], auditor="laya",
                                   check_name="mom-test:no-pitching", verdict="flag", findings="pitched at 12:30")
        self.assertEqual(au["verdict"], "flag")
        self.assertEqual(len(self.ledger.list_audits(self.a, target_table="interviews", target_id=i["id"])), 1)
        with self.assertRaises(LedgerError):
            self.ledger.add_audit(self.a, target_table="founders", target_id=self.a,
                                  auditor="laya", check_name="c", verdict="pass")

    # --- PR/FAQ -------------------------------------------------------------

    def test_prfaq_versions_start_at_zero(self):
        self.assertIsNone(self.ledger.latest_prfaq(self.a))
        v0 = self.ledger.add_prfaq_version(self.a, stage=0, body="v0", assumptions=["people will pay"])
        v1 = self.ledger.add_prfaq_version(self.a, stage=5, body="v2 draft")
        self.assertEqual((v0["version"], v1["version"]), (0, 1))
        self.assertEqual(v0["assumptions"], ["people will pay"])
        self.assertEqual(self.ledger.latest_prfaq(self.a)["id"], v1["id"])
        self.assertEqual(len(self.ledger.list_prfaq_versions(self.a)), 2)

    # --- gates --------------------------------------------------------------

    def test_gate_needs_evidence(self):
        for evidence in ([], None, [{"table": "artifacts"}], [{"table": "founders", "id": self.a}],
                         [{"table": "artifacts", "id": "missing"}]):
            with self.subTest(evidence=evidence), self.assertRaises(LedgerError):
                self.ledger.record_gate_decision(self.a, stage=0, gate_id="g", decision="pass",
                                                 decided_by="claude", evidence=evidence, rationale="r")
        self.assertEqual(self.ledger.get_founder(self.a)["current_stage"], 0)

    def test_pass_advances_the_founder(self):
        d = self.pass_gate(0)
        self.assertEqual(d["decision"], "pass")
        self.assertIsInstance(d["evidence"], list)
        self.assertEqual(self.ledger.get_founder(self.a)["current_stage"], 1)
        progress = {p["stage"]: p for p in self.ledger.list_stage_progress(self.a)}
        self.assertEqual(progress[0]["status"], "passed")
        self.assertIsNotNone(progress[0]["passed_at"])
        self.assertEqual(progress[1]["status"], "in_progress")

    def test_gate_only_for_current_stage(self):
        with self.assertRaises(LedgerError):
            self.pass_gate(1)
        with self.assertRaises(LedgerError):
            self.ledger.mark_gate_pending(self.a, 2)

    def test_mark_gate_pending(self):
        p = self.ledger.mark_gate_pending(self.a, 0)
        self.assertEqual(p["status"], "gate_pending")

    def test_stage_3_pass_needs_sean(self):
        for s in (0, 1, 2):
            self.pass_gate(s)
        with self.assertRaises(LedgerError):
            self.pass_gate(3, decided_by="claude", sean_signoff=False)
        with self.assertRaises(LedgerError):
            self.pass_gate(3, decided_by="claude", sean_signoff=True)
        self.assertEqual(self.ledger.get_founder(self.a)["current_stage"], 3)
        self.pass_gate(3)
        self.assertEqual(self.ledger.get_founder(self.a)["current_stage"], 4)

    def test_fail_routes_back_and_reopens(self):
        self.pass_gate(0)
        self.pass_gate(1)
        art = self.artifact(stage=2)
        with self.assertRaises(LedgerError):
            self.ledger.record_gate_decision(self.a, stage=2, gate_id="g", decision="fail", decided_by="claude",
                                             evidence=[{"table": "artifacts", "id": art["id"]}], rationale="r")
        with self.assertRaises(LedgerError):
            self.ledger.record_gate_decision(self.a, stage=2, gate_id="g", decision="fail", decided_by="claude",
                                             evidence=[{"table": "artifacts", "id": art["id"]}], rationale="r",
                                             routes_to_stage=3)
        d = self.ledger.record_gate_decision(self.a, stage=2, gate_id="g", decision="fail", decided_by="claude",
                                             evidence=[{"table": "artifacts", "id": art["id"]}],
                                             rationale="audience too broad", routes_to_stage=1)
        self.assertEqual(d["routes_to_stage"], 1)
        self.assertEqual(self.ledger.get_founder(self.a)["current_stage"], 1)
        progress = {p["stage"]: p for p in self.ledger.list_stage_progress(self.a)}
        self.assertEqual(progress[1]["status"], "in_progress")
        self.assertIsNone(progress[1]["passed_at"])
        self.assertEqual(len(self.ledger.list_gate_decisions(self.a, stage=2)), 1)

    def test_final_stage_pass_stays_at_9(self):
        for s in range(10):
            self.pass_gate(s)
        self.assertEqual(self.ledger.get_founder(self.a)["current_stage"], 9)
        self.assertEqual(len(self.ledger.list_gate_decisions(self.a)), 10)

    def test_failed_write_rolls_back(self):
        # Evidence is checked inside the transaction after the founder is read;
        # nothing may be left half-written when it fails.
        with self.assertRaises(LedgerError):
            self.ledger.record_gate_decision(self.a, stage=0, gate_id="g", decision="pass", decided_by="claude",
                                             evidence=[{"table": "pains", "id": "missing"}], rationale="r")
        self.assertEqual(self.ledger.list_gate_decisions(self.a), [])
        self.pass_gate(0)
        self.assertEqual(len(self.ledger.list_gate_decisions(self.a)), 1)

    # --- labels -------------------------------------------------------------

    def test_label_flywheel(self):
        p = self.ledger.add_pain(self.a, quote="invoices take forever")
        pb = self.ledger.add_pain(self.b, quote="nobody pays on time")
        la = self.ledger.add_label(self.a, task="pain_tag", target_table="pains", target_id=p["id"],
                                   input_text=p["quote"], model_label={"pain": True, "job": "get paid"},
                                   model_version="laya-0.1", confidence=0.75)
        lb = self.ledger.add_label(self.b, task="pain_tag", target_table="pains", target_id=pb["id"],
                                   input_text=pb["quote"], model_label={"pain": False}, model_version="laya-0.1")
        self.assertEqual(la["model_label"], {"job": "get paid", "pain": True})
        self.assertAlmostEqual(la["confidence"], 0.75)
        self.assertIsNone(la["corrected_label"])
        self.assertEqual(self.ledger.list_labels(self.a, corrected_only=True), [])

        c = self.ledger.correct_label(self.b, lb["id"], corrected_label={"pain": True}, corrected_by="sean")
        self.assertEqual(c["corrected_label"], {"pain": True})
        self.assertIsNotNone(c["corrected_at"])
        self.assertEqual(len(self.ledger.list_labels(self.b, task="pain_tag", corrected_only=True)), 1)
        exported = self.ledger.export_corrected_labels(task="pain_tag")
        self.assertEqual([r["id"] for r in exported], [lb["id"]])
        self.assertEqual(self.ledger.export_corrected_labels(task="other"), [])


def run(case: type) -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(case)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1
