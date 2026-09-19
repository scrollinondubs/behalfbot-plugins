#!/usr/bin/env python3
"""
animated-video.py - render a storyboard as an animated video via Remotion.

    animated-video.py storyboard.json out.mp4 [--template DIR]

Consumes the same storyboard JSON as narrated-video.py. The difference is what
it does with a slide's `marks`: the slide renderer flattens them onto a still
frame, this one animates them, honouring each mark's `at`, `to` and
`travelSeconds`.

It generates the narration, measures it, copies the visuals into the template's
public/ directory, writes the template's src/storyboard.json, and invokes the
locally installed Remotion binary. It never calls npx: the dependency is pinned
in the template's lockfile and running it from node_modules is what keeps the
pin meaningful.

Requires the animated path to be installed:  ../../setup.sh --remotion
That step is licence gated. Remotion is source-available, not open source.
See LICENSING.md at the plugin root.
"""
import json
import os
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(os.path.dirname(_HERE))
DEFAULT_TEMPLATE = os.environ.get(
    "VIDEO_EXPLAINER_REMOTION_TEMPLATE", os.path.join(_PLUGIN_DIR, "remotion-template")
)


def tts_binary():
    override = os.environ.get("VIDEO_EXPLAINER_TTS_BIN")
    if override and os.path.exists(override):
        return override
    return os.path.join(_HERE, "tts.sh")


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nk=1:nw=1", path]).stdout.strip()
    return float(out)


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 1
    board_path, out_path = args[0], args[1]
    template = args[args.index("--template") + 1] if "--template" in args else DEFAULT_TEMPLATE

    remotion = os.path.join(template, "node_modules", ".bin", "remotion")
    if not os.path.exists(remotion):
        print(
            "Remotion is not installed in %s\n"
            "Run: %s --remotion\n"
            "That step asks about licensing first, deliberately." % (template, os.path.join(_PLUGIN_DIR, "setup.sh")),
            file=sys.stderr,
        )
        return 2

    board = json.load(open(board_path))
    public = os.path.join(template, "public")
    os.makedirs(public, exist_ok=True)

    pad = float(board.get("pad", 0.7))
    engine = os.environ.get("VIDEO_EXPLAINER_TTS", "")
    segments = []

    for i, slide in enumerate(board["slides"]):
        seg = {
            "title": slide.get("title", ""),
            "kicker": slide.get("kicker", ""),
            "lines": [list(line) for line in slide.get("lines", [])],
            "marks": slide.get("marks", []),
            "footer": slide.get("footer", ""),
        }

        visual = slide.get("visual") or slide.get("image")
        if visual:
            name = "visual%03d%s" % (i, os.path.splitext(visual)[1] or ".png")
            shutil.copyfile(visual, os.path.join(public, name))
            seg["visual"] = name

        narration = (slide.get("narration") or "").strip()
        if narration:
            if len(narration) > 4000:
                raise SystemExit("slide %d: narration over the 4096 char TTS cap" % (i + 1))
            audio_name = "seg%03d.mp3" % i
            audio_path = os.path.join(public, audio_name)
            cmd = ["bash", tts_binary()]
            if engine:
                cmd.append("--%s" % engine)
            cmd += [narration, audio_path]
            subprocess.run(cmd, check=True, capture_output=True)
            seg["audio"] = audio_name
            seg["durationSeconds"] = round(duration(audio_path) + pad, 3)
        else:
            seg["durationSeconds"] = float(slide.get("durationSeconds", 4))

        segments.append(seg)
        print("segment %d/%d: %.1fs" % (i + 1, len(board["slides"]), seg["durationSeconds"]), flush=True)

    with open(os.path.join(template, "src", "storyboard.json"), "w") as fh:
        json.dump(
            {
                "width": board.get("width", 1920),
                "height": board.get("height", 1080),
                "fps": board.get("fps", 30),
                "segments": segments,
            },
            fh,
            indent=2,
        )

    run([remotion, "render", "Explainer", os.path.abspath(out_path)], cwd=template)
    size = os.path.getsize(out_path) / 1e6
    print("wrote %s: %.1fs, %.1f MB" % (out_path, duration(out_path), size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
