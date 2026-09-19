# video-explainer

Answer with a narrated video instead of text.

The counterpart to `loom-vision`. That plugin lets an agent watch a screen
recording; this one lets it produce one. Together they make "reply with a Loom"
something software can do.

## What it does

You write a storyboard - a list of slides, each with narration and optionally a
visual, some text and some marks to point at things. Two renderers consume it:

- **`narrated-video.py`** holds each slide for exactly the length of its own
  narration. Python, Pillow, ffmpeg and a text-to-speech engine. Near instant.
- **`animated-video.py`** renders the same storyboard through Remotion, so the
  marks appear on cue, travel and transform. Optional, licence gated.

The same storyboard file drives both. Marks are expressed in fractions of the
visual's own area, so the animated renderer's `at` / `to` / `travelSeconds`
fields are simply ignored by the slide renderer rather than breaking it.

## Setup

```bash
./setup.sh              # slide path: python3, Pillow, ffmpeg, narration engine
./setup.sh --remotion   # additionally the animated path (states the licence first)
./validate.sh           # smoke check: renders one slide, encodes one second
```

Idempotent. A second run reports what is already present and installs nothing.

## Use

```bash
python3 skills/video-explainer/narrated-video.py storyboard.json out.mp4
python3 skills/video-explainer/animated-video.py storyboard.json out.mp4
```

Storyboard schema, the rubric for which renderer to reach for, and the rules for
writing narration that a speech engine reads correctly are all in
[`skills/video-explainer/SKILL.md`](skills/video-explainer/SKILL.md).

## Narration engines

Picked in this order:

1. `$VIDEO_EXPLAINER_TTS_BIN`, if the install already has its own TTS script
2. OpenAI, if `OPENAI_API_KEY` is in the environment (billed per character to that key)
3. the macOS `say` command: free, offline, robotic

Force one with `VIDEO_EXPLAINER_TTS=openai` or `VIDEO_EXPLAINER_TTS=say`.

On Linux there is no `say`, so a narrated render needs `OPENAI_API_KEY` or your
own engine wired to `$VIDEO_EXPLAINER_TTS_BIN`. Everything else here is
platform neutral; `setup.sh` installs through `apt-get` where it can.

## Licensing

Nothing third party is vendored. ffmpeg comes from the system package manager
and Remotion comes from npm, so each install acquires them under its own
licence rather than receiving a copy from this repo.

Remotion in particular is source-available, not open source, and licensed per
organization: free for individuals, teams of up to 3 and non-profits, paid above
that. The animated path is off by default and `setup.sh --remotion` states the
terms before installing anything. The slide path carries no such constraint.

Reasoning, terms and the ffmpeg GPL question: [`LICENSING.md`](LICENSING.md).

## Tests

```bash
bash tests/test-license-gate.sh
python3 tests/test_storyboard.py
```

Both are self-contained: no network, no package manager, no Node. The licence
gate test stubs every external command on `PATH` and asserts that `npm ci` is
never reached without an acknowledgement, because that is the one behaviour here
with a legal consequence attached.
