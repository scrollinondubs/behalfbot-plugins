# Contributing plugins

Thanks for looking. This is the most contributable of the three Behalf.bot repos
and it is the one where a new plugin is genuinely welcome, not merely tolerated.
This document exists so you know the bar before you spend a weekend on something.

## Licence

This repo is **MIT** (see [`LICENSE`](LICENSE)), so the usual convention applies:
your contribution arrives under the same licence the project ships under. You
keep your copyright. There is no CLA and no sign-off requirement here.

(The two chassis repos use a custom source-available licence and do require a
DCO sign-off. This one does not. If you contribute to all three, that difference
is deliberate.)

## What a plugin is

One directory at the repo root, with a manifest. Read
[`docs/MANIFEST.md`](docs/MANIFEST.md) for the schema, and read an existing
plugin before writing your own - `loom-vision/` is the smallest complete example.

```
<your-plugin>/
  openclaw.plugin.json   manifest: metadata, config schema, contracts
  setup.sh               idempotent dependency setup (Linux-first, no brew fallback)
  validate.sh            optional post-setup smoke check
  skills/<name>/SKILL.md the agent-facing skill and its co-located scripts
```

**Add your entry to `registry.json`.** CI enforces this in both directions: a
plugin directory with a manifest that is not registered fails, and a registered
path that does not exist fails. An unregistered plugin is invisible to every
chassis, which is a silent failure nobody notices until an install goes wrong.

## The two rules that actually matter

**`setup.sh` must be idempotent and Linux-first.** It will be run repeatedly, on
machines that already have half of what it installs, by an agent with no human
watching. Re-running it must be a no-op, not a duplicate install or an error.
Assume Debian/Ubuntu; do not fall back to Homebrew.

**Declare everything your plugin touches.** Credentials, network egress,
filesystem paths, databases. The manifest's config schema is how an operator
decides whether to enable you. A plugin that quietly reaches something it did not
declare is the failure mode this whole repo is shaped to avoid - these run with
broad access on someone's personal machine.

## Before you open a PR

Open an issue first for a new plugin. Partly so it does not duplicate one that
exists or was declined, and partly because "should this be a plugin at all"
is worth five minutes before it is worth a weekend.

Bug fixes to an existing plugin can go straight to a PR.

## What CI will check

Every PR, regardless of what it touches:

| Check | What it wants |
|---|---|
| `shellcheck` | Shell passes at `severity: error` |
| `validate` | `registry.json` and the plugin manifests agree, both directions |
| `scanner-self-test` | The credential scanner itself still works |
| `credential-scan` | No credential-shaped strings in your added lines |

One more runs **only on pull requests from a fork**:
`fork-touches-sensitive-paths`. It fails if the PR touches `.github/`,
`scripts/`, `registry.json` or hook files. **That is not an accusation and it
does not mean your PR is rejected** - CI contributions from outside are welcome
and are expected to trip it. It means a human reads the diff by hand before
merging, which for a change to how CI or plugin discovery behaves is right.

The shell bar is "contains no real bug", not "matches our style".

## What gets a PR declined

- A plugin whose `setup.sh` is not idempotent, or assumes macOS
- Credentials or install-specific values committed anywhere
- A plugin that reaches credentials, paths or network endpoints it did not
  declare in its manifest
- A new plugin directory with no `registry.json` entry (CI catches this, but it
  is the single most common miss)
- Vendoring a copy of something from a chassis repo. This repo is the source of
  truth and the chassis fetch from it; a copy going the other way defeats the
  point.
- Broad reformatting or style-only churn mixed into a functional change

## Security

**Do not open a public issue for a vulnerability.** See
[`SECURITY.md`](SECURITY.md) for the private disclosure channel. Plugins run with
real access on real machines, so this matters more here than in a normal
library repo.

## Review, and what to expect

Small project, one maintainer. Reviews are best-effort, not same-day. A PR that
sits for a few days has not been ignored.

An assistant does a first pass on inbound PRs - size, paths touched, CI state,
whether it duplicates earlier work - and surfaces a summary. **Every merge
decision is a human one.** Nothing is merged by a bot, and no submitted code is
executed during review.
