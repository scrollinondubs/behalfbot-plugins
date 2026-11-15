---
name: run-fos
description: Run the VCL runner now when the owner of this BehalfBot says "run fos" (or "check the fos runner"), so work they queued in the Vibecode Lisboa Hub on My BehalfBot is claimed at once instead of on the next heartbeat tick. Use when a FounderOS job shows "Waiting on BehalfBot" and they want it started.
plugin: behalfbot-vcl-runner
enabled_when: "chassis.config.yaml modules.vcl-runner.enabled == true"
---

# Run fos

The owner queues FounderOS work in the Vibecode Lisboa Hub with "My BehalfBot"
as the runner, and the Hub shows "Waiting on BehalfBot". The `vcl-runner`
heartbeat claims it, but the dispatcher ticks every 15 minutes by default.
This runs the same tick now, once, on this install, with this install's own
agent key.

## When

A message that is `run fos` or `check the fos runner`, any letter case, with
nothing else in it.

**Only from the owner of this install** (the principal). The work it starts
runs on their Claude plan. Anyone else who sends it gets no action and no
explanation of what it would have done.

## What to do

1. Acknowledge with a reaction, not a message.
2. Run the handler in the background, **on the install, where the heartbeat
   runs**. A tick can take several minutes: it stops claiming new jobs after
   10 minutes and each step can take 5.

   From the install's root folder (the one holding `HEARTBEATS.md` and
   `vendored-plugins/`):

   ```
   bash vendored-plugins/vcl-runner/triggers/run-fos.sh
   ```

   If this session is on the host and the heartbeat runs in the BehalfBot
   container, run it in the container, the same way:

   ```
   docker exec behalfbot bash -c 'bash "$CUSTOMER_HOME/vendored-plugins/vcl-runner/triggers/run-fos.sh"'
   ```

   The handler finds the install from its own location, so it reads that
   install's halt flags and agent key even when `CUSTOMER_HOME` is not set in
   this session. It is `triggers/run-fos.sh` in the plugin's own directory,
   two levels above this file, if the plugin lives somewhere else.

   Use plain `bash`, not a login shell (`bash -l`). A login shell resets PATH
   and can drop the directory `claude` is installed in, and then every step
   fails with "claude CLI not found" and the job is posted to the Hub as
   failed.
3. When it exits, reply once with the line it printed. That line is already
   written for the owner: jobs run and posted, "Nothing queued in the Hub",
   or what they have to fix.

## Rules

- The handler does not run while the install is halted or in conservation
  mode, and says so. Do not work around it: those jobs are meant to wait.
- Never print the environment, never read `.env`, never ask for the agent
  key in chat. The handler reads the key itself.
- Do not call the Hub yourself and do not do the queued work in this session.
  The runner does it through `claude -p` with no tools.
- Running it while the heartbeat is also ticking is safe. The Hub leases each
  job to one claimer, so nothing is worked twice.
- No em dashes in the reply. Use " - " (space-dash-space).
