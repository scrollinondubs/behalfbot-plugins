# Perplexity research briefs

**A research question in, a citation-solid epub out.** Designed queries against
a scholar-filtered research UI, real citation URLs harvested from the DOM, a
sectioned brief with an inline DOI on every claim, built to epub and delivered
wherever you read.

## What it does

1. **Designs the queries.** 4-6 of them, each phrased the way researchers title their own papers, each carrying its own citation and becoming one section of the brief.
2. **Runs them** through a signed-in browser session with the scholar filter applied server-side.
3. **Harvests the real citations.** The accessibility tree shows only domain fragments; the actual hrefs live on anchors that exist only after the sources panel expands. The skill clicks it open and reads them directly, which is also several times cheaper in tokens than snapshotting the page.
4. **Synthesizes the brief** to house rules: lead with the honest nuance, prefer meta-analyses and RCTs with n >= 30, flag small studies explicitly, inline DOI on every claim, source-summary table at the end.
5. **Builds the epub** with pandoc, with a table of contents and metadata from the frontmatter.
6. **Delivers** to a file, a chat channel, an e-reader, or all three.

Optional **deep path** appends the full text of every cited article as a numbered
appendix, with a five-rung fallback chain when the scrape cannot get through:
PMC mirror, then the browser session, then `pdftotext`, then abstract-only, then
an honest "not retrievable" note. It never invents an article it could not read.

## Why the brief is shaped the way it is

The rules in the skill are opinionated on purpose, and the one that earns its
keep is **lead with the honest nuance**. A brief exists so that somebody can
make a claim in front of an audience without getting caught out. Naming the
disputed finding in the first paragraph of the affected section is the single
biggest credibility move available, and an n=12 study smuggled in as though it
were load-bearing is exactly what a sharp audience finds.

## Install

Chassis installs: enable the module and re-bootstrap.

```yaml
# chassis.config.yaml
modules:
  perplexity-research:
    enabled: true
    delivery_targets: ["file", "chat"]
    delivery_channel_id: "<your channel id>"
```

Off by default: the pipeline drives a signed-in research account through browser
automation, which is an operator decision.

Dependencies: `pandoc` (hard - the epub is the deliverable), a Playwright-capable
browser session provided by the chassis, and `poppler-utils` (soft, deep path
only). Linux-first, no Homebrew assumptions.

## Configuration

| Key | Default | What it controls |
|---|---|---|
| `enabled` | `false` | Master switch |
| `research_ui_url` | `https://www.perplexity.ai` | The research interface driven by the browser. Swappable for any UI that renders an answer plus a sources panel. |
| `source_filter` | `scholar` | Query-string source filter. Empty disables it. |
| `queries_per_brief` | `5` | Sections in the brief. Below 4 is thin; above 6 the sections restate each other. |
| `output_dir` | `${CHASSIS_HOME}/briefings` | Where the markdown and epub land |
| `scratch_dir` | `${CHASSIS_HOME}/temp/research-scratch` | Per-query browser dumps. Not the working directory, deliberately - that is how they get committed. |
| `author_line` | `${ASSISTANT_NAME} for ${PRINCIPAL_NAME}` | Epub author metadata |
| `language` | `en-US` | Frontmatter and epub language tag |
| `pandoc_bin` | `pandoc` | Bare name so PATH wins; set absolute where PATH is not reliable |
| `toc_depth` | `2` | Table-of-contents depth |
| `delivery_targets` | `["file"]` | `file`, `chat`, `ereader`, in order. One failing does not abort the others. |
| `delivery_channel_id` | *(none)* | **No default and no fallback.** An unset value makes chat delivery refuse rather than post a brief into whatever channel is first. |
| `brief_base_url` | *(empty)* | Optional HTTP base serving `output_dir`. When set, chat delivery includes a direct link alongside the attachment. |
| `ereader_send_command` | *(empty)* | Command run with the epub path as its only argument. A command rather than a hardwired integration, so any e-reader with a CLI works - installs running the companion reMarkable plugin point it at that plugin's send script. |
| `deep_path_warn_mb` | `5` | Projected appendix size that triggers a warning before the fetch loop |
| `deep_path_split_mb` | `10` | Projected size above which splitting into two epubs becomes the default |

## The build script standalone

```bash
bash scripts/build-brief-epub.sh briefings/2026-01-01-topic-research.md
```

Reads `title`, `author` and `date` from the YAML frontmatter, falls back to the
configured author line and today's date, warns on em dashes, warns when the
output is implausibly small for a real brief, and prints the epub path on stdout.

## Limitations

- The browser session must already be signed in. The plugin never handles those credentials. An unauthenticated session does not error - it returns a thinner answer with fewer sources, which is the more dangerous failure because it looks like success.
- Research UIs occasionally get an author name or a publication year wrong. The skill's standing instruction is to verify the DOI supports the claim before the claim ships.
- Deep-path coverage depends on what is actually open access. Hard-paywalled articles come back as abstract plus an explicit note.

## Layout

- `openclaw.plugin.json` - manifest (config schema, env contract)
- `.claude-plugin/plugin.json` - Claude Code compatibility shim
- `setup.sh` / `validate.sh` - dependency setup + an epub build round-trip
- `skills/perplexity-research/SKILL.md` - the agent-facing skill
- `scripts/build-brief-epub.sh` - markdown to epub
