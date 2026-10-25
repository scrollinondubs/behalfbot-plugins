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

## Layout

```
bin/vcl-runner                    CLI: setup, tick
vcl_runner/                       claim Hub jobs, run them through claude -p, post results
scripts/gather-vcl-runner.sh      the heartbeat gate (JSON on stdout, work done here)
scheduled-tasks/                  the heartbeat's prompt template
tests/test_vcl_runner.py          offline suite: fake Hub on 127.0.0.1, fake claude on PATH
```

Run the tests with `python3 vcl-runner/tests/test_vcl_runner.py`.
