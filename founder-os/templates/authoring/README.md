# Authoring templates

FounderOS content comes in four kinds. Each has a template in this directory.
There is a filled example of each in [`../examples/`](../examples/).

| Kind | Template | Lives in | `type:` |
|---|---|---|---|
| Framework card | [`framework-card.md`](framework-card.md) | `core/` or `contrib/` | `framework-card` |
| Concept note | [`concept-note.md`](concept-note.md) | `core/` or `contrib/` | `concept` |
| Stage skill | [`stage-skill.md`](stage-skill.md) | `skills/<name>/SKILL.md` | `stage-skill` |
| Gate spec | [`gate-spec.md`](gate-spec.md) | `gates/` | `gate` |

Copy the template, fill every section, and delete the guidance in angle
brackets. `scripts/lint_content.py` enforces the rules below. `validate.sh` runs
it over the plugin and over `templates/examples/`, and CI runs its tests.

Everything here must be original writing. Credit sources in the card's
`Sources` section and link to the original. Never paste text from a book or a
course.

## Frontmatter

Every file opens with frontmatter between two `---` lines. It is a small
subset of YAML, so the lint can parse it with the standard library alone:

- one `key: value` per line
- lists are inline only: `sources: [thirty-x-500, mom-test]`
- no nesting, no multi-line values
- a line starting with `#` is a comment

Required fields by kind:

| Kind | Required fields |
|---|---|
| Framework card | `id`, `type`, `title`, `stage`, `tier`, `sources`. Core cards also need `gate`. |
| Concept note | `id`, `type`, `title`, `tier` |
| Stage skill | `name`, `description`, `plugin`, `type`, `stage`, `gate` |
| Gate spec | `id`, `type`, `title`, `stage`, `signoff`, `fail_routes_to` |

Rules on those fields:

- `id` (or `name` for a skill) is lowercase kebab-case. It must match the file
  name without `.md`, or for a skill the directory name. Ids are unique across
  the whole plugin.
- `stage` is an integer from 0 to 9.
- `tier` is `core` or `contrib`, and must match the directory the file sits in.
- `gate` names the id of a gate spec in `gates/`. **Every core card names the
  gate it serves.** A contrib card may leave it out, but if it names one, the
  gate must exist.
- `status` is optional on framework cards: `draft`, `candidate` or `core`.
  A card under `contrib/` is `draft` (the default) or `candidate`. A card under
  `core/` is `core` or leaves it out. `status: core` in contrib fails: promotion
  moves the file, it is not a field edit. See [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).
- No stage may hold more core framework cards than [`budget.yml`](../../budget.yml)
  allows. Concept notes do not count against it.
- `signoff` is `claude` or `claude+sean`. Gates at stage 3 and later must be
  `claude+sean`.
- `fail_routes_to` is the stage a failed founder goes back to. It can be the
  gate's own stage, never a later one.
- A stage skill's `plugin` is `behalfbot-founder-os`.

## Required sections

Sections are `##` headings, spelled exactly as below. Add more sections if you
need them, but never drop or rename one of these.

- **Framework card:** Purpose, When to use, Principles, Procedure, Artifacts
  produced, Anti-patterns, Gate criteria, Sources, Sean's notes
- **Gate spec:** Required evidence, Auditor checks, Pass/fail rubric, Failure
  routing
- **Stage skill:** Read the founder context first, Current stage only,
  Procedure, Ledger writes
- **Concept note:** none. It is one idea in a few paragraphs.

## Wiki-links

Content links to other content with `[[id]]`, or `[[id|text to show]]` when the
sentence reads better with different words.

- The target is the `id` of a concept note or a framework card. Gates and skills
  are not link targets. A card names its gate in frontmatter instead.
- Core content may link only to core. Contrib may link to core or contrib. Core
  never depends on something a founder does not load by default.
- A link that does not resolve fails the lint. Rename a note and every link to
  it has to change in the same PR.
- Links are resolved at build time. The build that feeds the coach and the
  retrieval index looks up each `[[id]]`, rewrites it to a relative link to the
  target file, and records the edge so retrieval can follow it. The markdown in
  git keeps the `[[id]]` form, which is shorter to write and does not break
  when a file moves between directories.

## One idea per concept note

A concept note holds one idea. If you are writing "and also" in a concept note,
split it into two notes and link them.
