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

Status: **a founder can be walked from stage 0 to a gate submission using
only the plugin.** The stage 0-9 cards and gates, the ten stage skills,
concept notes, four auditor skills, the coach skills, the ledger, the founder
bundle and the eval harness are in place. Gate minimums were ruled by Sean on 2026-09-26. The epic is
[behalfbot-plugins#22](https://github.com/scrollinondubs/behalfbot-plugins/issues/22).

## Basic track

`basic/` is a second, shorter track: five stages, three cards each (stage 0
opens with a fourth, the program overview, and stage 2 ends with a fourth, the next four e-bombs), built on
Amy Hoy and Alex Hillman's [30x500](https://30x500.com).
It ends at a first sale to a stranger. Cards are paraphrased, name the 30x500
lesson they draw on and point to the course; they are a short version, not a substitute. The ten
stages above are the Advanced track and are unchanged.

| # | Stage (learners see 1 to 5) | Cards |
|---|---|---|
| 0 | Pick your people | Audience you belong to, watering holes, weekly research time |
| 1 | Sales Safari | Painstorm one thread, themes and saved threads, Safari gold and e-bomb ideas |
| 2 | E-bombs and your list | Home base, the first e-bomb, sharing it and the first email, the next four e-bombs |
| 3 | Your first tiny product | Pain into dream, ten pitches, plinko and a sign-up page |
| 4 | Ship it small and launch | Build it, sales page and price, launch and the first sale |

Each card says what to make, how to submit it (`text`, `link`, `file`,
`choice`) and the lines it is done when. `## Coach checks` on a card is for the
coach only and is never shown to the founder. `basic/gates/` holds one panel per
stage. A Basic stage passes when every card in it is accepted; there is no
separate gate submission. Two skills serve it: `founder-os-basic-coach` (chat,
any Basic stage) and `founder-os-basic-review` (one submission against one
card, ending in a `founderos-verdict` block the host app reads). The lint checks
the format, the course link, and that learner text has no em dashes or database
words.

## Post-revenue track

`post-revenue/` is a third track in the Basic format, for founders who
already sell: seven stages, twenty-three cards, from lifecycle marketing to
fundraising. It draws on many sources, each listed on the card with a link,
and frames the work as "your agent executes, you gather the context and
steer". It is visible in the app but not startable yet, and has no coach or
review skill of its own.

| # | Stage (learners see 1 to 7) | Cards |
|---|---|---|
| 0 | Basic lifecycle marketing | Lifecycle marketing, analytics and instrumentation, map your funnel |
| 1 | Unkink the garden hose | Decide where to focus, ad experiments, A/B tests |
| 2 | Automate all the things | Lead magnet and follow-up, a CRM, We do / They do |
| 3 | Viral loops and other distro channels | Affiliate program, viral loops, automated Safari and e-bombs |
| 4 | Doing cold outreach | Flintstone a campaign, outreach tools, advanced techniques |
| 5 | Other distribution channels | Partnerships, retargeting and lookalikes, feeder sites |
| 6 | Miscellaneous force multipliers | Modeling, Behalf.bot, Business Model Canvas, advisory board, fundraising |

Every source any card cites lives in [`sources.json`](sources.json), the
registry the app renders sources from. Cards may also carry the optional path
fields (`author`, `requires`, `teaches`, `fits_when`, `produces`) described in
[`templates/authoring/README.md`](templates/authoring/README.md).

## Stage skills and gates

Each stage has one skill, `skills/founder-os-stage-<N>-<slug>`. It reads the
founder's context and ledger first, loads only the current stage's core cards,
calls the stage's auditors, and records artifacts through `scripts/stage.py`.
Then it hands over to the gate:

1. `stage.py submit` counts the gate's `evidence:` minimums in the ledger,
   writes a `gate_submission` artifact and marks the stage `gate_pending`.
2. Claude rules on every auditor check in the gate spec, one `audits` row per
   check against the submission.
3. From stage 3, Sean signs off (`stage.py signoff`, operator-only).
4. `stage.py decide` records the pass or fail. A pass is refused while a
   minimum is missing, a check is unruled or failed, or Sean's sign-off is
   missing. A fail sends the founder to the stage the gate's failure routing
   names.

A founder cannot pass a gate by saying the work is done. `tests/test_stage_walk.py`
walks a synthetic founder through all of this against a SQLite ledger.

## Evals

`evals/` scores the auditor skills, a card per fixture set and the stage 0-3
skills against plain Claude, and publishes nulls with wins. Promotion into
core needs a win, and the lint checks it. See [`evals/README.md`](evals/README.md).

## Auditors

Laya does the per-item tagging. Claude confirms the tags and writes the
feedback. Every tag a founder accepts or rejects becomes a fine-tuning label.

| Skill | Question set | What it checks |
|---|---|---|
| `founder-os-mom-test-auditor` | `laya/mom-test.json` | Each interview turn: compliment, hypothetical, pitching, past behaviour, commitment (time, intro, money) |
| `founder-os-pain-tagger` | `laya/pain-tagger.json` | Ranks watering-hole posts by pain; checks the founder's pain log |
| `founder-os-earlyvangelist-qualifier` | `laya/earlyvangelist.json` | Blank's five criteria; escalates at 4 or more |
| `founder-os-pain-dream-fix-checker` | `laya/pain-dream-fix.json` | Each paragraph as pain, dream or fix; flags premature pitching |

Laya is optional. Set `LAYA_URL` (and `LAYA_API_KEY` if the server wants a
bearer token) to a laya-serve or Ollaya instance. Without it, or when it is
down or slow, each auditor returns `"mode": "claude-only"` and Claude does the
tagging. How the auditors route checkpoints, chunk long text and capture labels
is in [`docs/laya-auditors.md`](docs/laya-auditors.md).

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

## Safari runner

The Safari Hub on vibecodelisboa.com runs two model-heavy jobs on a student's
Sales Safari work: the painstorm over a thread, and the e-bomb analysis. By
default it bills the student's Anthropic API key. The runner is the other
option: **the jobs run on the student's own Claude plan, through Claude Code on
their own machine**, and the Hub never sees a Claude credential.

When "Run Safari work on" is set to My BehalfBot, the Hub queues
the job instead of running it. A heartbeat on the student's install claims it
(`GET /api/founder-os/agent/jobs/next`), runs every step through the local
`claude -p` with the skill as the system prompt, and posts the raw answers back
(`POST /api/founder-os/agent/jobs/:id/result`). The Hub parses and checks them
the same way it checks its own model output. Up to three jobs per tick. Nothing
queued costs one HTTP request and zero tokens.

The model gets no tools. Every call is:

```
claude -p --output-format json --tools "" --strict-mcp-config --setting-sources "" \
  --disable-slash-commands --no-session-persistence \
  --append-system-prompt <skill> [--model <model>]      # prompt on stdin
```

`--tools ""` removes every built-in tool and `--strict-mcp-config` with no
config loads no MCP server. Claude Code's own start-up event confirms both:
`tools: []`, `mcp_servers: []`. `--setting-sources ""` tells it not to load the
student's user or project settings files. It runs in an empty temporary
directory, so no `CLAUDE.md` from the install gets pulled in, and with
`ANTHROPIC_API_KEY` removed from its environment, so Claude Code uses the login
and not an API key. The runner never reads `~/.claude` or the keychain.

### Setup

1. In the Safari Hub, Settings, "Run Safari work on", choose My BehalfBot and
   copy the agent key. It is shown once.
2. On the install, run this and paste the key when asked (input is hidden):

   ```
   bin/founder-os runner setup
   ```

   It writes `FOUNDER_OS_AGENT_KEY` to `$CUSTOMER_HOME/.env` (mode 0600). If
   `.env.baked` exists it goes there too, since the dispatcher reads that one
   first. The key never goes on the command line and is never printed. In a
   shell where `CUSTOMER_HOME` is not set, add `--env-file <install root>/.env`.
   `--base-url http://localhost:3000` points it at a local Hub for testing.
   No restart needed: the heartbeat gate reads the key from those files when
   it is not already in its environment.
3. Make sure `claude` is installed and logged in on the account that runs the
   heartbeat: run `claude` once.
4. Add the heartbeat to `$CUSTOMER_HOME/HEARTBEATS.md`, under a
   `## founder-os-safari-runner` heading:

   ```yaml
   schedule: every 2m
   gather: ${FOUNDER_OS_RUNNER_GATHER_SCRIPT}
   condition: threshold count > 0
   prompt: <plugin dir>/scheduled-tasks/founder-os-safari-runner-prompt.md
   model: haiku
   budget: 0.05
   criticality: normal
   max_fires_per_day: 2
   realert_after: 24h
   ```

   Render the prompt from `scheduled-tasks/founder-os-safari-runner-prompt.md.template`
   like any other plugin prompt. It fires only when the student has to act:
   the Hub rejected the key, or `claude` is missing.

**The dispatcher tick is the floor on cadence.** It ticks every 900 seconds by
default, so `every 2m` means every 15 minutes unless the install sets
`DISPATCHER_INTERVAL_SECONDS=120`. The Hub shows when the runner last checked
in, so the student can see a slow tick.

A tick stops claiming new jobs after `FOUNDER_OS_RUNNER_TICK_BUDGET` seconds
(600), so other heartbeats are not kept waiting, and each claude call times out
after `FOUNDER_OS_RUNNER_STEP_TIMEOUT` seconds (300). A step that fails with a
transient error (rate limit, overloaded, a 5xx, or no readable answer) is
retried once after 25 seconds (`FOUNDER_OS_RUNNER_RETRY_BACKOFF`), inside the
same step timeout and lease margin; an auth error, a missing CLI or a step that
timed out is not retried. A step that still fails posts an error, which the Hub
shows on the thread with a Retry. The error is the one claude put in its JSON
output, not the warnings Claude Code prints to stderr on every run. A step that
would start within a minute of the 20-minute lease ending posts an error
instead of racing it. A 409 (the lease moved on) is dropped quietly.

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
  basic/                 the Basic track: stage-<N>/ cards and gates/ panels, stages 0-4
  post-revenue/          the Post-revenue track, same format, stages 0-6
  sources.json           the sources registry: every source a card cites, plus a few not cited yet
  skills/                stage, auditor, coach and Basic SKILL.md files, one per skills/<name>/
  laya/                  Laya question sets (JSON)
  founder_audit/         Laya client, chunking and the auditors' Laya half
  scripts/stage.py       ledger and gate calls the stage skills make
  scripts/audit.py       run an auditor; the skills call it
  scripts/run_evals.py   validate fixtures; run the live eval (manual)
  scripts/labels.py      accept or reject Laya tags
  scripts/record_audit.py  write Claude's verdict as an audits row
  scripts/export_labels.py  the fine-tune set, operator-only
  templates/authoring/   templates for cards, concept notes, stage skills and gate specs
  templates/examples/    one filled example of each, linted like real content
  scripts/lint_content.py  content lint, run by validate.sh
  scripts/ledger_migrate.py  apply ledger migrations to the configured backend
  scripts/gather-safari-runner.sh  the Safari runner's heartbeat gate
  founder_ledger/        storage interface and its Postgres and SQLite adapters
  founder_bundle/        founder bundle export/import and the progress webhook
  founder_stage/         gate evidence counting, submissions and decisions
  founder_eval/          eval sets, scoring and the runner
  founder_runner/        the Safari runner: claim Hub jobs, run them through claude -p, post results
  bin/founder-os         CLI: export, import, progress, runner setup and tick
  scheduled-tasks/       the Safari runner heartbeat's prompt template
  docs/                  the bundle format, and implementation notes such as the ledger on Turso
  tests/                 offline test suites, run by CI
  schema/                ledger schema and migrations
  evals/                 fixtures, published results and the seed-card list
  ATTRIBUTION.md         every source the cards draw on
```

## Source text

Cards are original synthesis. No text from a book or course enters this
directory. Each card credits its sources and links to the original; the
plugin-wide list is in [`ATTRIBUTION.md`](ATTRIBUTION.md).

## License

Content (cards, concept notes, gates, template prose, Laya question wording) is CC BY-NC-SA 4.0; code is MIT. See [LICENSE.md](LICENSE.md).
