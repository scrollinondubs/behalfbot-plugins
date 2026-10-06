# Skills

Every skill is one directory, `skills/<name>/SKILL.md`, because that is the
only place chassis skill discovery looks (see `docs/MANIFEST.md` at the repo
root). Each one is listed in `contracts.skills` in `openclaw.plugin.json`, and
`scripts/lint_content.py` fails when the two disagree. There are four kinds.

| Kind | `type:` | Names | Gate |
|---|---|---|---|
| Stage skill | `stage-skill` | `founder-os-stage-<N>-<slug>` | Walks a founder through one stage and hands over to its gate |
| Auditor skill | `auditor-skill` | `founder-os-<auditor>` | Judges one kind of evidence; a stage skill calls it |
| Coach skill | `coach-skill` | `founder-os-coach-<name>` | None, ever |
| Basic skill | `basic-skill` | `founder-os-basic-<role>` | Serves the Basic track in `basic/` |

## Coach skills

Coach skills can be used at any FounderOS stage. They gate nothing. They never
pass or fail a founder, and they write nothing to the gate record. A coach
reaches for one when a founder gets stuck on something outside the current
stage's cards: blaming others for a miss (`founder-os-coach-extreme-ownership`),
too many priorities (`founder-os-coach-the-one-thing`), a decision going in
circles (`founder-os-coach-mental-models`), or a need for the right thing to read
(`founder-os-coach-pg-essays`).

The lint checks them like any other skill: frontmatter, `plugin`, the name
matching the directory, and a manifest entry. It also fails a coach skill that
names a `gate` or a `stage`, since it has neither.

## Basic skills

The Basic track (`basic/`) has its own two skills, `type: basic-skill` with
`track: basic` and a `role`. `founder-os-basic-coach` (`role: coach`) chats with
a founder at any Basic stage and never writes the work for them.
`founder-os-basic-review` (`role: review`) reviews one submission against one
card and ends its reply with a `founderos-verdict` block; the host app reads
that block to mark the card accepted or needing work. The lint requires each
role's sections, fails a review skill with no verdict block, and fails a basic
skill that names a `gate` or `stage`.
