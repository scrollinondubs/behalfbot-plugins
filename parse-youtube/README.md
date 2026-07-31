# Parse YouTube

**Read the video instead of watching it.** Any public YouTube URL in, a
timestamped transcript plus title, channel, duration and chapters out - as JSON
for code, or as markdown that pastes into a draft.

## What it does

1. Resolves the video id from whatever URL shape it was handed - `watch?v=`, `youtu.be/`, `/embed/`, or a bare 11-character id.
2. Pulls the caption track through `youtube-transcript-api`: your preferred language first, then the configured fallback chain, then the auto-generated track, then whatever the video actually has.
3. Adds title, channel, duration, description and chapters via `yt-dlp`.
4. Emits JSON, or markdown with a bold `[M:SS]` anchor on every transcript line.

No API key. No headless browser. No YouTube account.

## Example uses

- "Here is a 90-minute conference talk - what does the speaker actually claim about latency, and at what timestamp?"
- "Pull the transcript of this tutorial so I can cite the exact wording."
- "Six videos on the same topic - where do they disagree?"
- Feed `transcript[]` into a vector store so a long back catalogue becomes searchable by meaning rather than by title.

## Install

Chassis installs: enable the module and re-bootstrap. `setup.sh` runs automatically.

```yaml
# chassis.config.yaml
modules:
  parse-youtube:
    enabled: true
```

Standalone: run `bash setup.sh` once (idempotent). Dependencies are `python3`,
`youtube-transcript-api==1.2.4` (pinned - the 0.x and 1.x APIs differ in shape),
and `yt-dlp` (soft, metadata only). Linux-first, no Homebrew assumptions.

## Configuration

| Key | Default | What it controls |
|---|---|---|
| `enabled` | `true` | Master switch |
| `default_language` | `en` | Caption language tried first |
| `fallback_languages` | `["en"]` | Tried after the preferred one, in order. Set this to the languages you actually read. |
| `metadata` | `true` | Whether to spend the `yt-dlp` call on title, channel, duration and chapters |
| `metadata_timeout_seconds` | `30` | When `yt-dlp` is abandoned. Metadata goes null; the transcript is unaffected. |
| `description_max_chars` | `1000` | Description truncation. YouTube descriptions are frequently link dumps. |

Each key is surfaced to the script as a `PARSE_YOUTUBE_*` env var and every one
has a working default, so the script also runs standalone with no environment
set at all.

## Usage

```bash
python3 scripts/parse-youtube.py "https://youtu.be/VIDEOID"                   # JSON
python3 scripts/parse-youtube.py "https://youtu.be/VIDEOID" --format markdown # markdown
python3 scripts/parse-youtube.py "https://youtu.be/VIDEOID" --lang pt         # prefer PT captions
python3 scripts/parse-youtube.py "https://youtu.be/VIDEOID" --no-metadata     # transcript only, faster
```

## Limitations

- Captions must exist. A video with captions disabled errors out; there is no speech-to-text fallback here.
- Age-restricted, private and members-only videos fail. There is deliberately no authenticated path.
- `yt-dlp` needs periodic updating as YouTube changes its player. That failure mode is null metadata, never a failed transcript.

## Layout

- `openclaw.plugin.json` - manifest (config schema, env contract)
- `.claude-plugin/plugin.json` - Claude Code compatibility shim
- `setup.sh` / `validate.sh` - dependency setup + smoke check
- `skills/parse-youtube/SKILL.md` - the agent-facing skill
- `scripts/parse-youtube.py` - the extractor
