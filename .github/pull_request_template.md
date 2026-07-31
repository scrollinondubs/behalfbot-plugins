<!--
Thanks for contributing. CONTRIBUTING.md has the full detail; this template is
just the shape a reviewer needs. Delete any section that does not apply rather
than writing "n/a" in it.
-->

## What this changes

<!-- One or two sentences. New plugin, or a change to an existing one? -->

## Why

<!-- The problem, not the patch. Link an issue if there is one - a new plugin
should have started as one. -->

## What it touches on the operator's machine

<!-- The section that matters most here. Plugins run with real access on
someone's personal machine. List every credential, filesystem path, network
endpoint and database this needs, and confirm each one is declared in the
manifest's config schema. "Nothing beyond what the manifest declares" is a
perfectly good answer. -->

## How it was verified

<!-- What you actually ran or observed. For a new plugin: did you run setup.sh
twice on a clean Linux box and confirm the second run is a no-op? -->

## Checklist

<!-- The sign-off is one line, not a CLA. `git commit -s` adds it; for a branch
that already exists, `git rebase --signoff origin/main`. See CONTRIBUTING.md. -->

- [ ] Every commit is signed off (`git commit -s`) - CI checks this
- [ ] `registry.json` has an entry for this plugin (CI enforces it; it is the most common miss)
- [ ] `setup.sh` is idempotent and Linux-first, no Homebrew fallback
- [ ] Everything the plugin touches is declared in the manifest's config schema
- [ ] No credentials, tokens, or install-specific values anywhere
- [ ] Nothing vendored from a chassis repo - this repo is the source of truth
- [ ] I read CONTRIBUTING.md's "what gets a PR declined" list

## Anything you are unsure about

<!-- Genuinely useful. Naming the part you are least confident in gets you a
better review than presenting it as finished. -->

---

<!--
If you opened this from a fork and `fork-touches-sensitive-paths` fails: that is
expected when a PR touches .github/, scripts/, registry.json or hook files. It is
not a rejection. It means a human reads the diff by hand before merging.
-->
