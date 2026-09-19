#!/usr/bin/env python3
"""
narrated-video.py - build a narrated slide video from a storyboard JSON.

Usage:
    narrated-video.py storyboard.json out.mp4 [--voice onyx] [--engine openai|say]

Storyboard JSON, the same file both render paths consume:
    {
      "width": 1920, "height": 1080, "fps": 30,
      "pad": 0.7,                      # silence held after each narration
      "slides": [
        {
          "narration": "Text spoken over this slide.",

          # Either hand over a finished 1920x1080 frame:
          "image": "/abs/path/slide1.png",

          # ...or describe the slide and let slidekit compose it:
          "visual": "/abs/path/screenshot.png",
          "kicker": "root cause",
          "title": "What went wrong",
          "lines": [["The first point", "bullet"], ["An aside", "muted"]],
          "marks": [{"box": [0.1, 0.2, 0.3, 0.1], "color": "red", "style": "ring"}]
        }
      ]
    }

`marks` are fractions of the visual's own box, so they survive any resize.
The animated renderer reads the same fields and moves them instead.

Each slide is held for exactly the length of its narration plus `pad`. Audio is
generated with tts.sh (OpenAI TTS, Onyx by default; macOS `say` fallback).

Reusable for any explainer: render slides however you like, then hand them here.
slidekit.py in this directory renders a standard slide if you do not want to
draw your own.

Requires: ffmpeg and ffprobe on PATH, Python Pillow for slidekit, and a TTS
engine (OPENAI_API_KEY, or macOS `say` as a free fallback).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))


def tts_binary():
    """Prefer a TTS script the host install already provides, else the bundled one."""
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


def _compose_missing_images(slides, work):
    """A slide may arrive as a finished frame, or as a description to compose.

    Composing here rather than making the caller do it is what lets one
    storyboard drive both render paths: the animated renderer reads the same
    description and animates it instead of flattening it.
    """
    needs_compose = [s for s in slides if not s.get("image")]
    if not needs_compose:
        return
    sys.path.insert(0, _HERE)
    try:
        from slidekit import Slide, render
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "a slide has no 'image' and Pillow is not installed to compose one: %s" % exc
        )
    for i, s in enumerate(slides):
        if s.get("image"):
            continue
        if not s.get("title"):
            raise SystemExit("slide %d has neither 'image' nor 'title'" % (i + 1))
        out = os.path.join(work, "slide%03d.png" % i)
        render(
            Slide(
                title=s["title"],
                kicker=s.get("kicker", ""),
                visual=s.get("visual"),
                lines=[tuple(line) for line in s.get("lines", [])],
                marks=s.get("marks", []),
                footer=s.get("footer", ""),
            ),
            out,
        )
        s["image"] = out


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 1
    board_path, out_path = args[0], args[1]
    voice = os.environ.get("OPENAI_TTS_VOICE", "onyx")
    # Empty means "let tts.sh decide": OpenAI when a key is present, else `say`.
    engine = os.environ.get("VIDEO_EXPLAINER_TTS", "")
    if "--voice" in args:
        voice = args[args.index("--voice") + 1]
    if "--engine" in args:
        engine = args[args.index("--engine") + 1]

    board = json.load(open(board_path))
    slides = board["slides"]
    W = board.get("width", 1920)
    H = board.get("height", 1080)
    fps = board.get("fps", 30)
    pad = float(board.get("pad", 0.5))

    work = tempfile.mkdtemp(prefix="narrvid-")
    slides = [dict(s) for s in slides]
    _compose_missing_images(slides, work)
    env = dict(os.environ, OPENAI_TTS_VOICE=voice)
    segs = []

    for i, s in enumerate(slides):
        mp3 = os.path.join(work, f"seg{i:03d}.mp3")
        text = s["narration"].strip()
        if len(text) > 4000:
            raise SystemExit(f"slide {i}: narration over the 4096 char TTS cap")
        cmd = ["bash", tts_binary()]
        if engine:
            cmd.append(f"--{engine}")
        cmd += [text, mp3]
        subprocess.run(cmd, check=True, capture_output=True, env=env)
        dur = duration(mp3) + pad
        seg = os.path.join(work, f"seg{i:03d}.mp4")
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-i", s["image"],
             "-i", mp3,
             "-t", f"{dur:.3f}",
             "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                    f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,format=yuv420p",
             "-c:v", "libx264", "-tune", "stillimage", "-crf", "23", "-preset", "medium",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
             "-movflags", "+faststart", seg])
        segs.append(seg)
        print(f"slide {i+1}/{len(slides)}: {dur:.1f}s", flush=True)

    listing = os.path.join(work, "list.txt")
    with open(listing, "w") as fh:
        for seg in segs:
            fh.write(f"file '{seg}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listing,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", out_path])

    total = duration(out_path)
    size = os.path.getsize(out_path) / 1e6
    print(f"wrote {out_path}: {total:.1f}s, {size:.1f} MB")
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
