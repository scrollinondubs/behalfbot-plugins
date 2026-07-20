# Plugin manifest schema - `openclaw.plugin.json`

Every plugin directory ships an `openclaw.plugin.json` at its root. (The
filename is load-bearing: chassis tooling - trigger merge, activation,
registry sanity checks - keys on it. A rename to `plugin.json` is deliberately
deferred; see behalfbot#53 review history.)

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Globally unique plugin id, e.g. `behalfbot-loom-vision`. Stamped onto merged trigger entries as the authoritative `plugin` value. |
| `name` | string | yes | Human-readable display name. |
| `description` | string | yes | One-paragraph description shown in registries and docs. |
| `version` | string | yes | Semver, informational. Recorded per-plugin in the install's `plugins.lock` for drift diffing; the repo-level tag is the actual release unit. |
| `configSchema` | object | no | JSON Schema for the plugin's per-install knobs. Defaults here document env-var defaults consumed by the plugin's scripts. |
| `contracts` | object | yes | What the plugin plugs into the chassis - see below. |
| `activation` | object | no | `{ "onStartup": bool }` plus notes. `onStartup: false` means on-demand only (trigger/skill-invoked). |
| `dependencies` | object | no | `{ "system": [ { "name", "install", "_explanation" } ] }`. Documentation for humans; `setup.sh` is the executable truth and MUST pin versions. |

## `contracts.*` - the chassis integration surface

| Key | Type | Consumed by | Meaning |
|---|---|---|---|
| `contracts.skills` | string[] | chassis skill discovery | Skill names shipped under `skills/<name>/SKILL.md`. Scripts a skill calls are co-located in the same directory. |
| `contracts.triggers` | object[] | `merge-plugin-triggers.sh` | Message triggers merged into the install's `triggers.yaml` when the module is enabled. Entry fields: `name`, `keyword_regex`, optional `channel_filter`, `parser`, `handler`, `react_emoji`. `plugin` is stamped from the manifest `id`. |
| `contracts.env` | object (map) | `activate-plugins.sh` | Env exports written into the install's generated `chassis-env.sh`. Values may use `${CHASSIS_HOME}`, `${CUSTOMER_HOME}`, `${PLUGIN_DIR}` - expanded at activation time. |
| `contracts.mcpServers` | object (map) | `activate-plugins.sh` | MCP server entries merged into the install's `.mcp.json`, same object shape Claude Code expects (`command`, `args`, `env`). `${PLUGIN_DIR}` etc. expand at activation; other `${VAR}` placeholders are left for the harness's own env expansion. Injected entries carry a `_managed_by` marker so re-activation replaces them and never touches manually added servers. |
| `contracts.tools` | string[] | reserved | Reserved for future tool registration. |
| `contracts.hooks` | string[] | reserved | Reserved for future hook registration. |

## Install / setup contract

- `setup.sh` - idempotent; safe to run on every bootstrap. Checks and installs
  the plugin's dependencies. Rules:
  - Linux-first: the chassis container is Debian slim. Never assume Homebrew;
    a missing dep on a non-Linux host is an ERROR message with manual
    instructions, not a `brew install` attempt.
  - Pin versions (`npm install -g pkg@x.y.z`, `pip install pkg==x.y.z`).
    The lockfile pins plugin SOURCE; pinned setup keeps the dep layer from
    drifting underneath it.
  - Soft dependencies degrade with a WARN, never a hard failure, when the
    plugin can still deliver partial value without them.
- `validate.sh` - optional post-setup smoke check. Exit nonzero to flag a
  broken install; the chassis reports it but does not fail bootstrap.
- `install.sh` is a dead filename from an earlier design - do not ship one.

## Gating

A plugin runs only when the install's `chassis.config.yaml` enables it:

```yaml
modules:
  loom-vision:
    enabled: true
```

Activation (setup, env, MCP registration, triggers) is applied and re-applied
by the chassis's `activate-plugins.sh` on every bootstrap; disabling a module
removes its triggers and managed MCP entries on the next bootstrap.
