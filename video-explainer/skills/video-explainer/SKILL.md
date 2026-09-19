---
name: video-explainer
description: Answer with a narrated video instead of text. Renders an explainer from a storyboard - a slide path needing only Python, ffmpeg and a text-to-speech engine, and an optional animated path on Remotion for when motion carries the argument. Use when a reply would land better as a walkthrough, demo, lesson or annotated screen recording, or when the user asks to be shown rather than told. The counterpart to loom-vision: that one ingests a recording, this one produces one.
plugin: behalfbot-video-explainer
enabled_when: "chassis.config.yaml modules.video-explainer.enabled == true"
metadata: { "openclaw": { "emoji": "🎬", "homepage": "https://behalf.bot", "requires": { "bins": ["python3", "ffmpeg", "ffprobe"] } } }
---

# Video Explainer

Use this skill when:

- The user asks you to "show me", "walk me through", "record a", or "make a video".
- A text reply is about to run past four paragraphs of spatial or sequential explanation - anything where the reader has to hold a picture in their head while you describe changes to it.
- You are answering a screen recording. Someone who sent a Loom is telling you which medium they think in.
- The deliverable gets handed to a third party: an install walkthrough, an onboarding lesson, a post-mortem, a demo.
- The same explanation will be produced repeatedly with different data - weekly metrics, per-customer summaries, per-student feedback.

Do not use it for a quick factual answer. A video is slower to make, slower to consume, and cannot be skimmed or quoted. Text is the default; this is the escalation.

## The two render paths

Both consume the same storyboard file and both size each segment to the length of its own narration, so audio is never clipped and visuals never run long.

| | Slides | Animated |
|---|---|---|
| Script | `narrated-video.py` | `animated-video.py` |
| Needs | python3, Pillow, ffmpeg, a TTS engine | the above plus Node and Remotion |
| Build | minutes | tens of minutes |
| Render | near instant | roughly 1s per 1s of output |
| Motion | none, slides are held | marks appear, travel and transform |
| Licensing | none beyond ordinary ffmpeg use | Remotion is licensed per organization |

### The rubric

**Start with slides.** If you are unsure, slides is the answer.

Use slides when the content is a list, a table, a comparison, a set of rules; when the image does not change and you are pointing at different parts of it; when someone is waiting on the answer now; when it is a one-off nobody will regenerate.

**Escalate to the animated path only when one of these is true:**

1. **Motion carries the argument.** Something propagates, blocks, flows or transforms, and a still frame cannot show it.
2. **Order in time is the point.** Before and after, a sequence of states, a diff arriving step by step.
3. **The reveal has to land on a word**, rather than everything appearing at once.
4. **A real component has to render.** Charts, syntax-highlighted code, a terminal replay, a map - anything that is a web page rather than a picture.
5. **A screen recording needs annotation over it.** Capture underneath, callouts on top.
6. **The same composition will be rendered many times with different data.**

**Not reasons to escalate:** making it look more impressive; a single moving highlight that a static circle would have said just as well; anything the user is actively waiting on, unless the motion is load bearing.

**The mid-build tell.** If you find yourself writing narration that says "watch what happens when" or "notice how this pushes that", stop. A held slide cannot deliver that sentence. Switch paths.

## How to invoke

Write a storyboard JSON, then call one of the two renderers.

```bash
python3 {baseDir}/narrated-video.py storyboard.json out.mp4     # slides
python3 {baseDir}/animated-video.py storyboard.json out.mp4     # animated
```

`{baseDir}` expands to the directory holding this `SKILL.md`; the scripts ship beside it.

## The storyboard

One file, both renderers.

```json
{
  "width": 1920, "height": 1080, "fps": 30, "pad": 0.7,
  "slides": [
    {
      "narration": "What is said over this slide.",
      "visual": "/abs/path/screenshot.png",
      "kicker": "root cause",
      "title": "What went wrong",
      "lines": [["The first point", "bullet"], ["An aside", "muted"]],
      "marks": [
        {"box": [0.66, 0.77, 0.33, 0.22], "color": "blue", "style": "outline", "at": 1.0},
        {"box": [0.67, 0.78, 0.11, 0.11], "color": "red", "style": "ring",
         "at": 3.0, "to": [0.0, 0.78], "travelSeconds": 2}
      ]
    }
  ]
}
```

- `marks.box` is `[x, y, width, height]` **in fractions of the visual's own area**, 0 to 1, so a mark stays put whatever size the image is rendered at. Styles: `fill`, `ring`, `outline`. Colors: `red`, `blue`, `amber`, `green`.
- `at`, `to` and `travelSeconds` are read by the animated renderer and ignored by the slide renderer, which draws the mark at its starting box. The same storyboard therefore works on both paths without editing.
- `image` instead of `visual` hands over a finished full-frame PNG and skips the layout entirely. Use it when you have drawn the whole frame yourself.
- Line styles: `plain`, `bullet`, `muted`.

`slidekit.py` sits beside the renderers if you want to compose frames yourself in Python rather than describing them.

## Narration

Narration is spoken text, and spoken text has different rules than written text.

- **No em dashes.** They read as a pause the engine does not take.
- **Spell out what the engine will mangle.** "the twenty four cage", not "the 24 cage". "R seven C one", not "R7C1".
- **Read it in your head before generating.** Hosted TTS bills per character and a re-record is a full round trip.
- **Cap is 4096 characters per segment.** The renderer refuses earlier rather than failing halfway through.
- **One idea per segment.** Segment boundaries are where a viewer can scrub to.

## Engines and cost

Narration comes from `tts.sh`, which picks in this order: `$VIDEO_EXPLAINER_TTS_BIN` if the install already has its own script, then OpenAI if `OPENAI_API_KEY` is present, then the macOS `say` command. The `say` fallback is free, offline and robotic - fine for a draft, wrong for anything a customer sees. Force one with `VIDEO_EXPLAINER_TTS=openai` or `=say`.

## Delivering the result

- Check the render before sending it. Pull a frame and look: `ffmpeg -ss 10 -i out.mp4 -frames:v 1 check.png`. A mark that covers the thing it points at is the usual failure, and it is invisible until you look.
- Chat platforms cap uploads, commonly at 10MB for bot accounts. 1080p30 lands around 7.5MB for 90 seconds. Over the cap, drop to 720p or raise the CRF before you split the video.
- Output is h264 + aac, `yuv420p`, faststart, which plays everywhere that matters.

## Licensing, before you use the animated path

Remotion is source-available software, **not** open source, and it is licensed per organization: free for individuals, teams of up to 3, and non-profits, paid above that. `remotion render`, which `animated-video.py` calls, counts as an "automation" under their terms, which puts a non-eligible organization on the per-render pricing tier.

The animated path is off by default for that reason and `setup.sh --remotion` states the terms before installing. Nothing is vendored into this repo: Remotion is fetched from npm so every install acquires it under its own licence. Full detail in `LICENSING.md` at the plugin root.

The slide path has no such constraint and is never gated.

## Why this exists

Most assistants can only reply in text. That is fine for a fact and poor for a process: the moment an explanation involves a thing that changes over time, or a place on a screen, prose makes the reader rebuild the picture from scratch on every sentence.

The pairing matters more than either half. `loom-vision` lets an agent watch what you did. This lets it show you back. Together they close the loop on a medium people already use to explain things to each other, and they make "reply with a Loom" a thing software can do.
