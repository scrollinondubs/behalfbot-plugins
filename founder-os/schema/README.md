# Ledger schema

The ledger holds founder state: what each founder has done, and the evidence
behind each gate decision. Content (cards, gates, skills) stays in git and never
goes in here.

- Migrations: [`migrations/`](migrations/), applied in order by
  `founder_ledger/migrate.py`, or `scripts/ledger_migrate.py` from the shell.
- Storage interface: [`../founder_ledger/interface.py`](../founder_ledger/interface.py).
- Adapters: Postgres (self-hosted) and SQLite (tests, and the reference for
  Turso). VCL implements the same interface on Turso, see
  [`../docs/ledger-on-turso.md`](../docs/ledger-on-turso.md).

## Tables

| Table | One row per | Notes |
|---|---|---|
| `founders` | founder | `founder_id` is the key everywhere. `cohort` is for VCL. `current_stage` is 0-9. `context` is the JSON blob stage skills read first. |
| `stage_progress` | founder x stage reached | `in_progress`, `gate_pending` or `passed`. A failed gate reopens the stage it routes to. |
| `artifacts` | artifact version | Append-only. Each new artifact of the same `kind` gets the next `version`. |
| `pains` | quote | Quote-backed pain log. `job` is the JTBD cluster. |
| `interviews` | interview | `interviewee` is a pseudonymous label, never a name or contact. `commitment` and `earlyvangelist` are the Mom Test and Blank signals. |
| `audits` | check on a row | Who checked (`laya`, `claude`, `sean`), which check, and the verdict. |
| `gate_decisions` | decision | Cites `evidence` as a JSON list of `{table, id}` refs. |
| `prfaq_versions` | PR/FAQ version | Version 0 is the stage 0 draft. |
| `labels` | Laya judgment | `model_label`, then `corrected_label` once a human fixes it. Corrected rows are the fine-tuning set. |
| `ledger_migrations` | applied migration | Created by the runner, not by a migration file. |

Every table except `ledger_migrations` has a `founder_id`, and every child
table references `founders` with `ON DELETE CASCADE`. Deleting a founder removes
everything they own.

## Rules the schema enforces

The interface checks these, and the schema checks them again with `CHECK`
constraints. An implementation that skips the interface, such as a new adapter
with a bug, still cannot write a row that breaks them:

- a gate decision's `evidence` is never empty
- a pass at stage 3 or later has `sean_signoff = 1` and `decided_by = 'claude+sean'`
- a fail has a `routes_to_stage`, at or before the gate's own stage

What only the interface can check, because it needs a lookup: each evidence ref
points at a row that the same founder owns.

## The dialect: a subset both engines accept

The same `.sql` file runs on Postgres, SQLite and libSQL/Turso. To keep it that
way, a migration may only use:

- types `TEXT`, `INTEGER` and `DOUBLE PRECISION`. Booleans are `INTEGER` with
  `CHECK (x IN (0, 1))`. JSON is `TEXT`.
- `PRIMARY KEY`, `NOT NULL`, `DEFAULT` with a literal, `UNIQUE`, `CHECK`,
  `REFERENCES ... ON DELETE CASCADE`
- `CREATE TABLE` and `CREATE INDEX IF NOT EXISTS`

And must not use:

- `SERIAL`, `AUTOINCREMENT` or identity columns. ids are UUID strings made by
  the application, so a founder bundle can move between installs without id
  collisions.
- `DEFAULT CURRENT_TIMESTAMP` or `now()`. The two engines format timestamps
  differently. Timestamps are ISO-8601 UTC strings made by the application.
- `JSONB`, `BOOLEAN`, `TIMESTAMPTZ`, `::` casts, or any other engine-specific
  syntax
- `BEGIN` or `COMMIT`. The runner wraps each migration in a transaction and
  records its version in the same transaction.
- `;` or `--` inside a string literal. The runner splits statements on `;`
  after stripping `--` comments.

Adding a column later means a new `NNN_name.sql` file. `ALTER TABLE ... ADD
COLUMN` is portable, but SQLite cannot drop or change a constraint in place, so
think twice before adding a `CHECK` to an existing table.

## Postgres: its own schema

On Postgres the tables live in their own schema, `founder_os` by default
(`ledger_pg_schema` in the manifest). The adapter creates it if it is missing
and sets `search_path` to it, so the migration files stay unqualified. Table
names like `artifacts` and `labels` cannot collide with anything else in the
chassis database, and the plugin never reads or writes outside its schema.
