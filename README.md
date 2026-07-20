# behalfbot-plugins

Single source-of-truth repo for public Behalf.bot chassis plugins. Both chassis
(`scrollinondubs/behalfbot` and `scrollinondubs/BehalfBot-open`) FETCH plugins
from here at install/update time instead of vendoring copies - one copy,
fetched fresh, nothing local to fall out of sync (decision record:
scrollinondubs/behalfbot#53).

## Layout

```
registry.json            index of plugins: {name, path, description, min_chassis_version}
tools/fetch-plugins.sh   the canonical fetcher (each chassis carries a seed copy)
docs/MANIFEST.md         plugin manifest schema (openclaw.plugin.json)
<plugin-name>/           one directory per plugin
  openclaw.plugin.json   manifest - metadata, config schema, contracts
  setup.sh               idempotent dependency setup (Linux-first, no brew fallback)
  validate.sh            optional post-setup smoke check
  skills/<name>/SKILL.md the agent-facing skill + its co-located scripts
```

## How fetching works

1. Each chassis commits a `PLUGINS_PIN` file next to its `VERSION` file. Format
   is a single line: `<tag> <40-hex-commit-sha>`. The pin moves ONLY at a
   chassis VERSION bump.
2. `tools/fetch-plugins.sh` (run by the chassis at boot and via its
   `update-plugins` command) resolves the pinned tag against this repo,
   **requires the resolved SHA to equal the pinned SHA**, downloads the tarball
   at that SHA, sanity-checks the tree against `registry.json`, and atomically
   installs it into the install's `vendored-plugins/` directory.
3. It then writes `plugins.lock` install-side: repo, tag, commit, fetch time,
   and per-plugin `{version, tag, sha}`. The lockfile is committed in each
   customer repo - its diff is the audit trail for every plugin change.

The SHA requirement is the security gate: tags can be force-moved, SHAs cannot.
If a tag here ever stops resolving to the SHA a chassis has pinned, every
fetcher refuses to fetch and keeps its previous tree. Compromising this repo's
tags is therefore not sufficient to push code to installs - the pinned SHA in
each chassis repo must move too, and that file only changes through a reviewed
chassis PR.

Releases are repo-level tags (`vX.Y.Z`). One pin covers the whole plugin set;
per-plugin `version` fields are informational and recorded in the lockfile for
drift diffing. Emergency hotfix path: cut a patch tag.

## Offline / air-gapped installs

`fetch-plugins.sh --freeze` marks the lockfile frozen; subsequent boots skip
fetching entirely and run whatever is on disk. `--unfreeze` re-enters the flow.

## What does NOT belong here

Only public-safe plugins. Customer-private plugins (anything an install is not
willing to publish) live install-side in the customer's `plugins-local/`
directory, which the chassis layers ON TOP of the fetched set with higher
precedence - same manifest format, same `modules.<name>.enabled` gating, never
published.

## Adding a plugin

1. Create `<name>/` with `openclaw.plugin.json` per `docs/MANIFEST.md`.
2. `setup.sh` must be idempotent, Linux-first, and pin dependency versions
   (e.g. `npm install -g pkg@x.y.z`) - unpinned deps reintroduce the drift
   class this repo exists to kill, one layer down.
3. Add the plugin to `registry.json`.
4. PR, review, merge, tag. Chassis installs pick it up at their next pin bump.
