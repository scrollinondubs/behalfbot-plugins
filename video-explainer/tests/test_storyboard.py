"""narrated-video.py contract tests. No network, no ffmpeg, stdlib only.

Two things are worth pinning down here. The first is the narration length cap:
the hosted TTS API rejects anything over 4096 characters, and finding that out
halfway through a seven segment render wastes every segment before it. The
second is the engine flag, which decides whether a machine with no API key can
render at all.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(os.path.dirname(HERE), "skills", "video-explainer")
SCRIPT = os.path.join(SKILL_DIR, "narrated-video.py")


class StoryboardContract(unittest.TestCase):
    def test_script_is_present_and_executable(self):
        self.assertTrue(os.path.exists(SCRIPT), SCRIPT)
        self.assertTrue(os.access(SCRIPT, os.X_OK), "narrated-video.py is not executable")

    def test_no_args_prints_usage_and_does_not_crash(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT], capture_output=True, text=True, timeout=30
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("storyboard.json", proc.stdout)

    def test_overlong_narration_is_refused_before_any_render(self):
        """The cap must fire on the offending slide, not after paying for the
        earlier ones."""
        with tempfile.TemporaryDirectory() as tmp:
            board = {
                "slides": [
                    {"image": os.path.join(tmp, "a.png"), "narration": "x" * 5000}
                ]
            }
            path = os.path.join(tmp, "board.json")
            with open(path, "w") as fh:
                json.dump(board, fh)
            proc = subprocess.run(
                [sys.executable, SCRIPT, path, os.path.join(tmp, "out.mp4")],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("4096", proc.stderr + proc.stdout)

    def test_engine_defaults_to_letting_tts_decide(self):
        """An empty engine means tts.sh picks: OpenAI when a key is present,
        otherwise the free offline fallback. Hardcoding 'openai' here would
        break every install without an API key."""
        with open(SCRIPT) as fh:
            source = fh.read()
        self.assertIn('os.environ.get("VIDEO_EXPLAINER_TTS", "")', source)
        self.assertIn("if engine:", source)


class SlidekitContract(unittest.TestCase):
    def test_bold_fallbacks_are_explicit(self):
        """Pillow degrades to a bitmap font silently when a bold face is
        missing, which is invisible until a render looks wrong. Every fallback
        entry must name its bold file rather than assuming a collection index."""
        with open(os.path.join(SKILL_DIR, "slidekit.py")) as fh:
            source = fh.read()
        self.assertIn("DejaVuSans-Bold.ttf", source)
        self.assertIn("LiberationSans-Bold.ttf", source)

    def test_renders_a_slide_when_pillow_is_available(self):
        try:
            sys.path.insert(0, SKILL_DIR)
            from slidekit import H, Slide, W, render
        except ImportError:
            self.skipTest("Pillow not installed in this environment")
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "s.png")
            render(Slide(title="Title", kicker="kicker", lines=[("body", "bullet")]), out)
            with Image.open(out) as im:
                self.assertEqual(im.size, (W, H))


if __name__ == "__main__":
    unittest.main()
