# Content research

**Research in, blog-post architecture out.** A structured stub the writer
expands - headline, angle, hook, section skeleton, sources, tone notes - filed
into a staged content pipeline.

## What it does

1. **Checks memory first.** If the topic has been researched in the last 30 days, it builds on that instead of paying for the same searches again.
2. **Finds the dominant narrative** - what everyone is already saying about the topic.
3. **Then finds the angle underneath it.** The contrarian or underexplored read is the only part of a stub that cannot be got anywhere else, so that is where the work goes.
4. **Anchors it.** Two or three concrete examples, data points, or stories. An abstract point with no anchor is where a draft stalls at paragraph four.
5. **Writes the stub** in the install's own voice, per the configured voice guide.
6. **Files it** into stage one of the pipeline.

## What it deliberately does not do

**It does not write the post.** A stub is architecture, not prose. Handing back
a finished draft in an approximation of someone else's voice produces something
that reads fine and gets thrown away - which costs more than writing nothing,
because it also costs the outline.

**It ships no voice guide.** Voice is personal and install-local. The plugin
knows where to look (`voice_guide_path`) and reads whatever is there. If the
file is missing it says so in the tone notes rather than inventing a house style.

## Install

Chassis installs: enable the module and re-bootstrap.

```yaml
# chassis.config.yaml
modules:
  content-research:
    enabled: true
    publication_url: "https://your.publication"
```

No dependencies to install. It uses whatever search and memory tooling the
chassis already exposes, and the default `files` pipeline backend needs nothing
external.

## The pipeline

Content moves forward one stage at a time through `pipeline_stages`, which
defaults to:

```
1-researching -> 2-writing -> 3-published -> 4-socials-drafted -> 5-promoted
```

Two backends:

- **`files`** (default). One directory per stage under `pipeline_root`. A stub is a markdown file; moving it forward is moving the file. Nothing external, and the pipeline state is visible with `ls`.
- **`siyuan`**. Stubs become sub-documents under configured stage block ids. Stages are identified by **block id, never by path** - folder names and the paths above them get renamed and moved, ids do not.

The stage list is read, not assumed, so an install with three stages or seven
works without touching the skill.

## Configuration

| Key | Default | What it controls |
|---|---|---|
| `enabled` | `true` | Master switch |
| `pipeline_backend` | `files` | `files` or `siyuan` |
| `pipeline_root` | `${CHASSIS_HOME}/content-pipeline` | Root for the `files` backend |
| `pipeline_stages` | five stages, above | Ordered stage names. Rename or reorder to match reality. |
| `siyuan_notebook_id` | *(none)* | Notebook holding the pipeline. Install-specific, no default - a wrong id files content where nobody looks. |
| `siyuan_stage_ids` | *(none)* | Stage name to block id. Required for the `siyuan` backend. |
| `publication_url` | *(empty)* | The writer's own publication, checked so a stub does not restate a published post. Empty skips that check. |
| `voice_guide_path` | `${CHASSIS_HOME}/skills/brand-voice.md` | Where the style guide lives |
| `cta_target` | *(empty)* | What the closing section bridges to. Empty ends on the takeaway, which is the honest default for an install not selling anything. |
| `priority_topics` | `[]` | Themes to prefer when choosing autonomously. Empty means pick on merit. |
| `stubs_per_session` | `1` | Stubs per unattended session. One, deliberately. |
| `task_label` | *(empty)* | Issue label that marks a content request. Empty means never triggered from an issue tracker. |

## Layout

- `openclaw.plugin.json` - manifest (config schema)
- `.claude-plugin/plugin.json` - Claude Code compatibility shim
- `skills/content-research/SKILL.md` - the agent-facing skill

No scripts. The work is research and judgement, and there is nothing here worth
wrapping in a shell script.
