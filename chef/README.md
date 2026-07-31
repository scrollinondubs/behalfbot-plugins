# Chef - weekly variety advisory

**A mirror, not a doctor.** One weekly report built from a photo-logged meal
history: how many distinct plants you ate, what you kept repeating, and which
food groups never showed up.

## What it does

1. **Plant count.** Distinct plant species over a trailing 7 days against a target of 30, per the American Gut Project (McDonald 2018, mSystems, n approximately 10,000: 30+ distinct plants per week associates with greater gut-microbial diversity than 10 or fewer).
2. **Variety and rotation.** Protein and headline-dish frequency, framed as variety - which is the thing that actually drives adherence - rather than as a problem.
3. **Gap board.** Food groups absent from the window, ranked by how easy each is to add.
4. **Next week's shape.** Three to five concrete suggestions, one of them a species not seen in the window.

## Why a count, and only a count

Every other metric you could derive from a photographed meal depends on knowing
the portion, and portions from photos are guesses. A count does not. You either
ate a leek or you did not, and grams are irrelevant to that.

So this plugin counts. It does not estimate micronutrients, it does not infer
deficiency, and it does not describe a microbiome. Those numbers would look more
impressive and would be a division wearing a lab coat.

## The hard refusals

These are encoded in the skill and the prompt, not left to judgement:

- Never diagnose or hint at a deficiency. That word requires bloodwork.
- Never recommend a supplement, by dose, brand, or in general.
- Never recommend a calorie target, a deficit, or a weight-loss protocol.
- Never construct a restriction, elimination, or fasting protocol.
- Never assert a physiological state from food.
- Never do micronutrient or vitamin quantification.
- Never frame low-mercury fish repetition as a mercury problem. Salmon at roughly 0.022 ppm is about 7x below the FDA 0.15 ppm Best Choices threshold, so its repetition is a variety point and nothing more. The mercury frame is reserved for genuinely high-mercury species recurring three or more times, with the real ppm attached.

A tool that reads a food diary and talks back about it is exactly the shape of
thing that drifts into clinical claims it has no basis for. The refusals are why
it is safe to run unattended. `validate.sh` asserts the mercury gating rather
than trusting the comment.

## The count must not inflate

The shipped taxonomy has already been corrected once for exactly this. It was
counting red onion and green onion as two species, three varieties of lettuce as
three, and "mixed vegetables" as a plant despite naming no species. It produced
consecutive weeks above target against a log that showed the target reached once
in four months.

An inflated counter is a participation trophy. The canonicalization rules in
`data/plant-taxonomy.json` exist to keep it honest, and the standing instruction
is: report the number as it comes back, never adjust it upward, and if it jumps,
name the change that caused it rather than letting it read as progress.

## Data dependency

**This plugin reads a meal log it does not own.** It expects the tables written
by the companion food-logging plugin (`bfl_meals` and `bfl_days` by default,
both overridable) and it writes nothing back.

Without that plugin or an equivalent schema there is nothing to count.
`setup.sh` checks for the table and says so, because the alternative is
discovering it through silence on a Sunday afternoon.

## Install

Chassis installs: enable the module and re-bootstrap.

```yaml
# chassis.config.yaml
modules:
  chef:
    enabled: true
    market_note: "available at my local market and in season"
```

Then register the heartbeat, pointing it at `scripts/gather-chef-weekly.sh` with
`scheduled-tasks/chef-weekly-prompt.md.template` as the prompt.

The gate is free. It exits `count: 0` without touching a model on every day that
is not the report day, on report days where the log is too thin, and on any week
it has already run. Steady-state cost is zero tokens six days out of seven.

Dependencies: `python3` and `psycopg` (pinned to 3.x - the connection API
differs from psycopg2). Linux-first, no Homebrew assumptions.

## Configuration

| Key | Default | What it controls |
|---|---|---|
| `enabled` | `false` | Master switch |
| `plant_target` | `30` | The number the count is reported against. This is the American Gut figure; changing it detaches the number from its citation. |
| `window_days` | `7` | Trailing window |
| `min_logged_days` | `4` | Below this the heartbeat stays silent. A report off two logged days is noise pretending to be signal. |
| `report_day_of_week` | `7` | 1 = Monday through 7 = Sunday, matching `date +%u` |
| `output_mode` | `file` | `file` or `siyuan` |
| `output_dir` | `${CHASSIS_HOME}/briefings/chef` | Report destination in `file` mode |
| `siyuan_notebook_id` | *(none)* | Notebook for `siyuan` mode. Install-specific, no default. |
| `siyuan_parent_block_id` | *(none)* | Parent block for `siyuan` mode. Block ids are stable; resolve the readable path from the id at runtime. |
| `state_dir` | `${CHASSIS_HOME}/scheduled-tasks` | Holds the ISO-week dedup marker. Must persist across restarts or the report runs twice. |
| `taxonomy_path` | shipped taxonomy | Point at a copy to add local species without diverging from the plugin |
| `meals_table` | `bfl_meals` | Meal rows from the companion plugin |
| `days_table` | `bfl_days` | Day rows, joined on `day_id` |
| `market_note` | `locally available and in season` | What "available" means where you shop. Set it to something specific or the suggestions come out aspirational. |

## Extending the taxonomy

The analyzer returns `unresolved_tokens` - everything the deterministic mapper
could not place. That is the candidate list. Add real species to the `plants`
map, add catch-alls that name no species to `non_plants`, and re-read the
canonicalization rules first: the rule that keeps the count honest is that one
botanical species in one culinary form is one key.

## Layout

- `openclaw.plugin.json` - manifest (config schema, heartbeat and env contracts)
- `.claude-plugin/plugin.json` - Claude Code compatibility shim
- `setup.sh` / `validate.sh` - dependency setup + an offline analyzer self-check
- `skills/chef/SKILL.md` - the agent-facing skill, including the refusals
- `scheduled-tasks/chef-weekly-prompt.md.template` - the heartbeat prompt
- `scripts/chef_plant_count.py` - the deterministic analyzer
- `scripts/gather-chef-weekly.sh` - the free heartbeat gate
- `data/plant-taxonomy.json` - species map, non-plant list, FDA mercury table
