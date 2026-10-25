# vcl-runner

Runs a student's queued Vibecode Lisboa Hub jobs on their own install, on
their own Claude plan, through Claude Code on their own machine. The Hub never
sees a Claude credential, and this plugin ships no course content: the Hub
builds every prompt, sends it with the job, and checks every answer.

By default the Hub runs these jobs on the student's Anthropic API key. When
the student picks My BehalfBot as the runner in the Hub settings, the Hub
queues the job instead. A heartbeat on the install claims it
(`GET /api/founder-os/agent/jobs/next`), runs every step through the local
`claude -p` with the job's skill as the system prompt, and posts the raw
answers back (`POST /api/founder-os/agent/jobs/:id/result`). Up to three jobs
per tick. Nothing queued costs one HTTP request and zero tokens.

The model gets no tools. Every call is:

```
claude -p --output-format json --tools "" --strict-mcp-config --setting-sources "" \
  --disable-slash-commands --no-session-persistence \
  --append-system-prompt <skill> [--model <model>]      # prompt on stdin
```

`--tools ""` removes every built-in tool and `--strict-mcp-config` with no
config loads no MCP server. `--setting-sources ""` tells it not to load the
student's user or project settings files. It runs in an empty temporary
directory, so no `CLAUDE.md` from the install gets pulled in, and with
`ANTHROPIC_API_KEY` removed from its environment, so Claude Code uses the login
and not an API key. The runner never reads `~/.claude` or the keychain.

## Setup

1. In the Hub settings, choose My BehalfBot as the runner and copy the agent
   key. It is shown once.
2. On the install, run this and paste the key when asked (input is hidden):

   ```
   bin/vcl-runner setup
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
   `## vcl-runner` heading:

   ```yaml
   schedule: every 2m
   gather: ${VCL_RUNNER_GATHER_SCRIPT}
   condition: threshold count > 0
   prompt: <plugin dir>/scheduled-tasks/vcl-runner-prompt.md
   model: haiku
   budget: 0.05
   criticality: normal
   max_fires_per_day: 2
   realert_after: 24h
   ```

   Render the prompt from `scheduled-tasks/vcl-runner-prompt.md.template`
   like any other plugin prompt. It fires only when the student has to act:
   the Hub rejected the key, or `claude` is missing.

Moving from the old `founder-os` plugin: the key stays where it is
(`FOUNDER_OS_AGENT_KEY`, same name). Point the heartbeat's `gather:` at
`vendored-plugins/vcl-runner/scripts/gather-vcl-runner.sh` and its `prompt:` at
a copy of this plugin's template.

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
shows with a Retry. A step that would start within a minute of the 20-minute
lease ending posts an error instead of racing it. A 409 (the lease moved on)
is dropped quietly.

Each output the runner posts carries a `usage` object with what Claude Code
reported for that step: input, output, cache-read and cache-write tokens summed
over every model it ran, the model names, and its `total_cost_usd`. The Hub
prices the tokens at API list prices and shows the student what the job would
have cost on their API key.

## reMarkable (tablet_send jobs)

When the student turns on reMarkable in the Hub, "Send unread to my tablet"
queues a `tablet_send` job. It has no model steps and never starts `claude`.
The runner downloads the reading file the Hub built (a PDF, `tablet.file_url`, with
the agent key, and only from the Hub's own origin), then uploads it with
[rmapi](https://github.com/ddvk/rmapi):

```
rmapi -ni mkdir <folder>          # each missing level; an existing folder is fine
rmapi -ni put <file> <folder>
```

and posts `{"ok": true, "doc_path": "/Safari/Safari reading 2026-10-25"}`
(the folder plus the document name rmapi gives it: the file name without its
extension), or `{"error": "..."}` with one of `rmapi not found`,
`rmapi not paired`, `upload failed: ...` or `download failed: ...`. The Hub
shows the error on the thread. The reMarkable token stays in rmapi's own
config; the Hub never sees it.

Pairing is one time, on the install, as the account that runs the heartbeat:

1. Install rmapi and put it on that account's PATH, or set `RMAPI_BIN` to its
   full path in the install's `.env`.
2. Open https://my.remarkable.com/device/desktop/connect while logged in to
   your reMarkable account and copy the one-time code.
3. Run `rmapi` in a terminal and paste the code when it asks. Then `ls` should
   list your tablet's folders; `exit` to leave.

rmapi saves its token to `~/.rmapi`, or `rmapi/rmapi.conf` under the user
config directory (`RMAPI_CONFIG` overrides the path). The runner always passes
`-ni`, so an unpaired rmapi fails at once with `rmapi not paired` instead of
waiting for a code. If the tablet is unlinked in the reMarkable account, pair
again the same way. A file whose name is already in the folder fails with
`upload failed: put: entry already exists`.

## Reading annotations back (tablet_pull jobs)

The Hub can ask for the student's marks on a document it sent: "Pull my
annotations" on a reMarkable send, and on its own every six hours for sends of
the last 30 days. That is a `tablet_pull` job. It has no model steps either:
the runner never starts `claude` for it, and the Hub reads the handwriting.

```
rmapi -ni stat <doc_path>        # when the tablet last changed the document
rmapi -ni get <doc_path>         # only when it changed since the last pull
```

`stat` gives the document's `ModifiedClient`. When it equals the version the
Hub last pulled (`tablet.since`), the runner posts
`{"ok": true, "unchanged": true, "doc_version": ...}` and downloads nothing.
Otherwise it downloads the document into a temporary directory and reads every
page with [rmscene](https://github.com/ricklupton/rmscene):

- **highlights**: reMarkable snaps a PDF highlight to the text and stores the
  text itself, so these go to the Hub as text with their PDF page.
- **handwriting**: every pen, pencil, marker and highlighter stroke. A page
  that has any is drawn as a PNG of the ink alone on a transparent page, 1404
  x 1872 (the tablet's own page units), and posted to `tablet.pages_url` with
  its page number. Before the first page, the PDF inside the document goes to
  `tablet.document_url`, so the Hub can lay the ink over the printed page. A
  page whose image the Hub already has (`tablet.known_pages`, a hash per page)
  is not sent again.

Pages the student added on the tablet carry the PDF page before them and an
`inserted` count; deleted pages are left out. Then it posts
`{"ok": true, "doc_version": ..., "highlights": [...], "pages": [...]}`, or
`{"error": "..."}` with `rmapi not found`, `rmapi not paired`,
`pull failed: ...` (the document is gone, or rmscene is missing). Uploads go
only to the Hub's own origin, with the agent key; each is at most 4 MB.

rmscene is in the BehalfBot image (`rmscene>=0.6,<1`). On an install without
it, run `pip install 'rmscene>=0.6,<1'` for the account that runs the
heartbeat; until then every pull posts `pull failed: rmscene not installed`
and every other job is unaffected. The PNG is drawn with the standard library.

## Layout

```
bin/vcl-runner                    CLI: setup, tick
vcl_runner/                       claim Hub jobs, run them through claude -p (or rmapi), post results
vcl_runner/annotations.py         read highlights and handwriting off a reMarkable document (tablet_pull)
scripts/gather-vcl-runner.sh      the heartbeat gate (JSON on stdout, work done here)
scheduled-tasks/                  the heartbeat's prompt template
tests/test_vcl_runner.py          offline suite: fake Hub on 127.0.0.1, fake claude and rmapi
tests/rm_fixtures.py              a synthetic .rmdoc written with rmscene's own writer
```

Run the tests with `python3 vcl-runner/tests/test_vcl_runner.py`. The tests
that read a real .rm document skip when rmscene is not installed (CI has no pip
step); run them where it is, for example inside the BehalfBot container.
