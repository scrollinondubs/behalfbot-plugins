# Loom Vision

**See the frames, not just the transcript.** Drop a Loom share URL into the agent and get full visual + audio context for code reviews, bug repros, walkthroughs, and demos.

## What it does

Loom's auto-transcript captures only what was said aloud. For most technical Loom videos - code walkthroughs, design reviews, bug repros - the screen contents matter more than the audio. Loom Vision closes that gap:

1. Downloads the source video and Loom's auto-transcript.
2. Converts the transcript JSON into WebVTT + plaintext.
3. Samples frames at 1 frame per 5 seconds (configurable).
4. Hands all of it to the agent as multimodal context.

The agent reads the transcript to anchor timing and browses the frames in the relevant window - IDE state, error popups, on-screen code, design mockups, and UI transitions that the audio narration skipped.

## Example uses

- "Here's a 7-minute Loom of the bug - what did I click on at minute 4 that triggered the 500?"
- "Walk me through this design review and pull out every comment about contrast ratios."
- "Loom of my PR walkthrough - summarize the diff strategy I described."
- "I recorded my onboarding flow - where does the UX get confusing?"

## Install

Chassis installs: enable the module and re-bootstrap - `setup.sh` runs automatically.

```yaml
# chassis.config.yaml
modules:
  loom-vision:
    enabled: true
```

Standalone: run `bash setup.sh` once (idempotent). Dependencies: `node`, `loom-dl@1.1.1` (pinned, via npm), `ffmpeg` - all checked/installed by setup.sh, Linux-first, no Homebrew assumptions.

## Layout

- `openclaw.plugin.json` - manifest (config schema, trigger, env contract)
- `setup.sh` / `validate.sh` - dependency setup + smoke check
- `skills/loom-vision/SKILL.md` - the agent-facing skill
- `skills/loom-vision/process-loom.sh` - the processor (co-located with the skill)
