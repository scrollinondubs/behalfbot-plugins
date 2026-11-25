# SaaS exit

**Leave the platform, keep every file, customer, link and sale.** A playbook
skill for an agent helping its owner move off a hosted SaaS - course and
membership platforms (Podia, Kajabi, Teachable, Thinkific), storefronts,
newsletters - onto a self-hosted parity app the agent builds.

It is a common first project on a managed install: the platform's renewal often
costs more than the install.

## What it covers

1. Deadline first, capture before build
2. Inventory from the platform's own product list, prioritised by buyers
3. Find the originals before scraping anything
4. Media capture the owner can do in one pass, verified against the inventory
5. Verbatim text and link capture
6. What each product promises beyond its files
7. Customer, sales and subscriber exports
8. A cutover checklist: redirects, codes, affiliates, automations, payments,
   customer access, DNS
9. Build order: parity first, design sign-off before backend
10. Reference-led design rounds
11. Read-only discipline on the old platform
12. ROI framing for the owner

Plus vendor notes per platform, starting with Podia.

## Install

```yaml
# chassis.config.yaml
modules:
  saas-exit:
    enabled: true
```

No dependencies and no `setup.sh`. It uses the chassis browser automation and
whatever shared storage the install already has, both optional.

## Layout

- `openclaw.plugin.json` - manifest
- `.claude-plugin/plugin.json` - Claude Code compatibility shim
- `skills/saas-exit/SKILL.md` - the agent-facing skill
