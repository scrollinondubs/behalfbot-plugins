-- 001_ledger.sql - FounderOS ledger, initial schema.
--
-- Written in the SQLite-compatible subset described in schema/README.md, so
-- this exact file runs on Postgres (self-hosted), SQLite (tests) and
-- libSQL/Turso (VCL). No transaction statements: the runner owns the
-- transaction and records the version in ledger_migrations.
--
-- Every table carries founder_id. ids are app-generated UUID strings and
-- timestamps are app-generated ISO-8601 UTC strings, so rows move between
-- installs in a founder bundle without id collisions or format drift.

CREATE TABLE founders (
  founder_id     TEXT PRIMARY KEY,
  display_name   TEXT NOT NULL,
  cohort         TEXT,
  current_stage  INTEGER NOT NULL DEFAULT 0 CHECK (current_stage BETWEEN 0 AND 9),
  context        TEXT NOT NULL DEFAULT '{}',
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS founders_cohort_idx ON founders (cohort);

CREATE TABLE stage_progress (
  id          TEXT PRIMARY KEY,
  founder_id  TEXT NOT NULL REFERENCES founders (founder_id) ON DELETE CASCADE,
  stage       INTEGER NOT NULL CHECK (stage BETWEEN 0 AND 9),
  status      TEXT NOT NULL CHECK (status IN ('in_progress', 'gate_pending', 'passed')),
  started_at  TEXT NOT NULL,
  passed_at   TEXT,
  updated_at  TEXT NOT NULL,
  UNIQUE (founder_id, stage)
);

CREATE TABLE artifacts (
  id          TEXT PRIMARY KEY,
  founder_id  TEXT NOT NULL REFERENCES founders (founder_id) ON DELETE CASCADE,
  stage       INTEGER NOT NULL CHECK (stage BETWEEN 0 AND 9),
  kind        TEXT NOT NULL,
  version     INTEGER NOT NULL CHECK (version >= 1),
  title       TEXT,
  body        TEXT NOT NULL,
  meta        TEXT NOT NULL DEFAULT '{}',
  created_at  TEXT NOT NULL,
  UNIQUE (founder_id, kind, version)
);

CREATE INDEX IF NOT EXISTS artifacts_founder_stage_idx ON artifacts (founder_id, stage);

CREATE TABLE pains (
  id             TEXT PRIMARY KEY,
  founder_id     TEXT NOT NULL REFERENCES founders (founder_id) ON DELETE CASCADE,
  quote          TEXT NOT NULL,
  source_url     TEXT,
  watering_hole  TEXT,
  segment        TEXT,
  job            TEXT,
  tags           TEXT NOT NULL DEFAULT '[]',
  created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS pains_founder_job_idx ON pains (founder_id, job);

CREATE TABLE interviews (
  id              TEXT PRIMARY KEY,
  founder_id      TEXT NOT NULL REFERENCES founders (founder_id) ON DELETE CASCADE,
  interviewee     TEXT NOT NULL,
  segment         TEXT,
  conducted_on    TEXT,
  notes           TEXT NOT NULL,
  commitment      TEXT NOT NULL DEFAULT 'none'
                  CHECK (commitment IN ('none', 'time', 'reputation', 'money')),
  earlyvangelist  INTEGER NOT NULL DEFAULT 0 CHECK (earlyvangelist IN (0, 1)),
  created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS interviews_founder_idx ON interviews (founder_id);

CREATE TABLE audits (
  id            TEXT PRIMARY KEY,
  founder_id    TEXT NOT NULL REFERENCES founders (founder_id) ON DELETE CASCADE,
  target_table  TEXT NOT NULL
                CHECK (target_table IN ('artifacts', 'pains', 'interviews', 'prfaq_versions')),
  target_id     TEXT NOT NULL,
  auditor       TEXT NOT NULL CHECK (auditor IN ('laya', 'claude', 'sean')),
  check_name    TEXT NOT NULL,
  verdict       TEXT NOT NULL CHECK (verdict IN ('pass', 'fail', 'flag')),
  findings      TEXT,
  created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS audits_target_idx ON audits (founder_id, target_table, target_id);

CREATE TABLE prfaq_versions (
  id           TEXT PRIMARY KEY,
  founder_id   TEXT NOT NULL REFERENCES founders (founder_id) ON DELETE CASCADE,
  version      INTEGER NOT NULL CHECK (version >= 0),
  stage        INTEGER NOT NULL CHECK (stage BETWEEN 0 AND 9),
  body         TEXT NOT NULL,
  assumptions  TEXT NOT NULL DEFAULT '[]',
  created_at   TEXT NOT NULL,
  UNIQUE (founder_id, version)
);

-- Rules from the epic, enforced in the schema as well as the interface so a
-- second implementation (VCL on Turso) cannot skip them:
--   every decision cites evidence (a non-empty JSON list of ledger refs);
--   a pass from stage 3 onward carries Sean's sign-off;
--   a fail says which stage the founder goes back to, never a later one.
CREATE TABLE gate_decisions (
  id               TEXT PRIMARY KEY,
  founder_id       TEXT NOT NULL REFERENCES founders (founder_id) ON DELETE CASCADE,
  stage            INTEGER NOT NULL CHECK (stage BETWEEN 0 AND 9),
  gate_id          TEXT NOT NULL,
  decision         TEXT NOT NULL CHECK (decision IN ('pass', 'fail')),
  decided_by       TEXT NOT NULL CHECK (decided_by IN ('claude', 'claude+sean')),
  sean_signoff     INTEGER NOT NULL DEFAULT 0 CHECK (sean_signoff IN (0, 1)),
  evidence         TEXT NOT NULL CHECK (evidence <> '[]' AND evidence <> ''),
  rationale        TEXT NOT NULL,
  routes_to_stage  INTEGER CHECK (routes_to_stage BETWEEN 0 AND 9),
  created_at       TEXT NOT NULL,
  CHECK (decision <> 'pass' OR stage < 3 OR (sean_signoff = 1 AND decided_by = 'claude+sean')),
  CHECK (decision <> 'fail' OR (routes_to_stage IS NOT NULL AND routes_to_stage <= stage))
);

CREATE INDEX IF NOT EXISTS gate_decisions_founder_stage_idx ON gate_decisions (founder_id, stage);

-- One row per Laya judgment. A correction fills corrected_label, and every
-- corrected row is a fine-tuning example. input_text is copied in so a label
-- stays usable after the row it judged is edited or deleted.
CREATE TABLE labels (
  id               TEXT PRIMARY KEY,
  founder_id       TEXT NOT NULL REFERENCES founders (founder_id) ON DELETE CASCADE,
  task             TEXT NOT NULL,
  target_table     TEXT NOT NULL,
  target_id        TEXT NOT NULL,
  input_text       TEXT NOT NULL,
  model_label      TEXT NOT NULL,
  model_version    TEXT NOT NULL,
  confidence       DOUBLE PRECISION,
  corrected_label  TEXT,
  corrected_by     TEXT,
  corrected_at     TEXT,
  created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS labels_founder_task_idx ON labels (founder_id, task);
CREATE INDEX IF NOT EXISTS labels_task_corrected_idx ON labels (task, corrected_at);
