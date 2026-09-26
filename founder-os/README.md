# FounderOS

A gated coach for early-stage founders. It walks a founder through a fixed
sequence of stages. Each stage ends in a gate, and a gate needs evidence from the
founder's ledger, not the founder's say-so.

| # | Stage | Gate evidence |
|---|---|---|
| 0 | Why and founder fit | A problem the founder cares about, PR/FAQ v0 with assumptions listed |
| 1 | Audience | Named audience, 3+ active watering holes, first bowling-pin segment |
| 2 | Pain research | Quote-backed pain log clustered into jobs |
| 3 | Discovery | Audited interviews, commitment signals, earlyvangelists identified |
| 4 | Solution test | Sprint test results, app reshaped rather than reused as-is |
| 5 | Position and story | One-sentence job, foothold segment |
| 6 | Content and audience | Responsive list, published content wall |
| 7 | Validation and sales | Paying customers or signed pilots |
| 8 | Traction and PMF | PMF score, a metric that moves |
| 9 | Fundraise (optional) | Only if 7 and 8 justify it |

Status: **foundations only.** The layout, the authoring templates, the ledger
and the founder bundle are in place. No skills ship yet. The epic is
[behalfbot-plugins#22](https://github.com/scrollinondubs/behalfbot-plugins/issues/22).

## Content vs state

Two kinds of data, kept apart on purpose.

**Content lives in git, and git is canonical.** Framework cards, concept notes,
stage skills, gate specs, templates and Laya question sets are markdown files in
this directory. Changes arrive as PRs, with review and history. Nothing edits
content in a database and syncs it back.

**State lives in the ledger.** What a particular founder has done - stage
progress, artifacts, pain logs, interviews, audits, gate decisions, PR/FAQ
versions - is rows in a database behind a storage interface. One schema, two
backends: Postgres on a self-hosted Behalf.bot, Turso on the Vibecode Lisboa
dashboard. Every row carries a `founder_id`. Skills call `founder_ledger`, never
SQL. See [`schema/README.md`](schema/README.md).

Anything else a database holds, such as a retrieval index over the cards, is
derived from the markdown and can be rebuilt from it at any time.

## Moving a founder between installs

A founder's ledger travels as a founder bundle: one JSON file per table, the
artifacts as markdown, the original attached files, a manifest and checksums.
VCL exports it, and a self-hosted install imports it:

```
bin/founder-os export --founder-id <id> --out alice.zip
bin/founder-os import alice.zip
```

Import is idempotent and all-or-nothing, and it refuses a bundle from a newer
format version. A self-hosted graduate can opt in to a signed progress webhook
that tells their cohort instructor their stage and gate status, and nothing
else. The format, the id remapping rules and the webhook's privacy boundary are
in [`docs/bundle-format.md`](docs/bundle-format.md).

## Core vs contrib

**`core/` is the only thing the coach loads.** It is curated and small. The
maintainer is its code owner, and a card gets in only when evals show it beats
plain Claude on the gate it serves.

**`contrib/` is open to PRs and opt-in.** Community cards land here. Founders
never see contrib content unless the operator sets `include_contrib: true`.

Rules that keep core lean:

1. Every core card names the gate it serves. A card that serves no gate does not
   belong in core.
2. Each stage has a card budget. Promoting one card means demoting another.
3. Promotion from contrib to core is eval-gated.
4. A founder sees only the cards for their current stage.

The lint enforces 1 and 2. The budget is in [`budget.yml`](budget.yml), and the
full contribution rules are in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Layout

```
founder-os/
  openclaw.plugin.json   manifest
  setup.sh               dependency check, idempotent
  validate.sh            layout and manifest smoke check
  budget.yml             most core lead cards each stage may hold
  CONTRIBUTING.md        core vs contrib, the budget, promotion, attribution
  core/                  canonical cards and concept notes (the coach loads only this)
  contrib/               community cards, opt-in
  gates/                 gate specs and rubrics
  skills/                stage, auditor and coach SKILL.md files
  laya/                  Laya question sets
  templates/authoring/   templates for cards, concept notes, stage skills and gate specs
  templates/examples/    one filled example of each, linted like real content
  scripts/lint_content.py  content lint, run by validate.sh
  scripts/ledger_migrate.py  apply ledger migrations to the configured backend
  founder_ledger/        storage interface and its Postgres and SQLite adapters
  founder_bundle/        founder bundle export/import and the progress webhook
  bin/founder-os         CLI: export, import, progress
  docs/                  the bundle format, and implementation notes such as the ledger on Turso
  tests/                 offline test suites, run by CI
  schema/                ledger schema and migrations
  evals/                 evals that gate promotion into core
  ATTRIBUTION.md         every source the cards draw on
```

## Source text

Cards are original synthesis. No text from a book or course enters this
directory. Each card credits its sources and links to the original; the
plugin-wide list is in [`ATTRIBUTION.md`](ATTRIBUTION.md).
