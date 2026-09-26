# Contributing plugins

Thanks for looking. This is the most contributable of the three Behalf.bot repos
and it is the one where a new plugin is genuinely welcome, not merely tolerated.
This document exists so you know the bar before you spend a weekend on something.

## Licence and the sign-off

This repo is **MIT** (see [`LICENSE`](LICENSE)), so the usual convention applies:
your contribution arrives under the same licence the project ships under. You
keep your copyright.

We also ask for a [Developer Certificate of Origin](https://developercertificate.org/)
sign-off, the same as the two chassis repos. **This is not a CLA.** There is no
form, no signing ceremony, and no copyright assignment. It is one line in your
commit message:

```
Signed-off-by: Your Name <your@email.com>
```

`git commit -s` adds it for you. It records that you wrote the change, or have
the right to submit it, and are submitting it under this project's licence.

MIT does not strictly need it - the licence convention already answers the legal
question on its own. We ask anyway because this repo ships executable code that
runs with real access on other people's machines, and provenance is the one
thing worth having on record for every commit that gets there.

CI checks it. If you forget:

```bash
git commit --amend -s --no-edit        # most recent commit
git rebase --signoff origin/main       # every commit on your branch
git push --force-with-lease
```

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

## The three rules that actually matter

**`setup.sh` must be idempotent and Linux-first.** It will be run repeatedly, on
machines that already have half of what it installs, by an agent with no human
watching. Re-running it must be a no-op, not a duplicate install or an error.
Assume Debian/Ubuntu; do not fall back to Homebrew.

**Declare everything your plugin touches.** Credentials, network egress,
filesystem paths, databases. The manifest's config schema is how an operator
decides whether to enable you. A plugin that quietly reaches something it did not
declare is the failure mode this whole repo is shaped to avoid - these run with
broad access on someone's personal machine.

**Pin every third-party dependency to an exact version, and commit the lockfile.**
Nothing may execute on an install that is not pinned to something a human chose.

- Exact versions in `package.json` and `requirements.txt`. Not `^1.2.0`, not
  `latest`, not a bare package name.
- Commit `package-lock.json`, or the pip equivalent. npm's `integrity` field is a
  SHA-512 of the tarball, which is the same guarantee `PLUGINS_PIN` gives for
  this repo's own code, one layer down.
- Install with `npm ci`, never `npm install`. `npm ci` fails when the lockfile
  and the manifest disagree; `npm install` quietly rewrites the lockfile.
- **Never `npx -y <package>`.** That fetches and runs whatever is latest at that
  moment, on someone's personal machine, with nobody having read it. If your
  plugin drives an external CLI or MCP server, depend on it at a pinned version
  and invoke the local binary.
- Vendoring third-party source is not the answer either. Depend on it, pin it,
  and bump the pin deliberately after reading the diff. Fork only what you
  actually modify, and only where the licence allows it.

The reasoning is the one already behind the SHA gate in `tools/fetch-plugins.sh`:
this repo's own code cannot change under an install without a human moving a pin.
A dependency that resolves at install time can, and the person running the agent
would never see it happen.

## Check the licence before you depend on anything

A repo with no `LICENSE` file is not permissively licensed. It is all rights
reserved by default, whatever its README implies. Plugins here get distributed to
other people's machines, so "it is public on GitHub" is not permission.

If the upstream you want has no licence, ask the author to add one before you
build on it. Most say yes. Until they do, it cannot ship from here.

Watch for the mismatch between a package and the repo it claims to come from.
A published npm or PyPI package whose stated source repository does not exist,
or does not match what the package actually contains, is the shape a supply-chain
problem arrives in. Pinning the package version is what protects an install;
trusting the README does not.

## FounderOS content

Cards, concept notes and gates for `founder-os/` have their own rules on top of
this file: core vs contrib, the per-stage card budget, eval-gated promotion and
how to credit sources. Read [`founder-os/CONTRIBUTING.md`](founder-os/CONTRIBUTING.md)
first.

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
| `dco-self-test` | The sign-off checker itself still fails on an unsigned commit |
| `dco` | Every non-merge commit has a `Signed-off-by` line |

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
- An unpinned dependency, a missing lockfile, or an `npx -y` invocation
- A dependency on an upstream with no licence
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
