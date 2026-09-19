#!/usr/bin/env python3
"""
slidekit.py - render a standard explainer slide: a visual on the left, a text
panel on the right. Import it, or run it against a JSON deck.

    from slidekit import Slide, render
    render(Slide(
        visual="board.png",          # any image, or None for a text-only slide
        kicker="root cause",
        title="A four cell 16 is not unique",
        lines=[("Eight ways to make 16", "bullet"), ("You picked one.", "muted")],
        marks=[{"box": [0.55, 0.70, 0.22, 0.12], "color": "red", "style": "ring"}],
    ), "slide1.png")

`marks` are drawn over the visual in fractions of the visual's own box, so they
survive any resize: {"box": [x, y, w, h]} with each value between 0 and 1.
Styles: "fill", "ring", "outline".

Nothing here is domain specific. The visual can be a screenshot, a photo, a
chart, a scanned page or a rendered diagram.
"""
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
VIS_X, VIS_Y, VIS_MAX = 45, 40, 1000
PANEL_GAP = 55

PALETTE = {
    "ink": (25, 28, 33),
    "grey": (110, 116, 125),
    "bg": (252, 251, 248),
    "red": (214, 45, 45),
    "blue": (30, 95, 220),
    "amber": (232, 150, 20),
    "green": (20, 150, 100),
}

# (regular, bold) pairs. An index means "font at this index of a .ttc
# collection"; a separate path means a separate bold file, which is how Linux
# ships DejaVu. Getting this wrong degrades silently to a bitmap font, so the
# bold entry is always explicit.
FONT_FALLBACKS = [
    (("/System/Library/Fonts/Helvetica.ttc", 0), ("/System/Library/Fonts/Helvetica.ttc", 1)),
    (("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
     ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0)),
    (("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 0),
     ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 0)),
    (("/Library/Fonts/Arial.ttf", 0), ("/Library/Fonts/Arial Bold.ttf", 0)),
]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for regular, bold_face in FONT_FALLBACKS:
        path, index = bold_face if bold else regular
        try:
            return ImageFont.truetype(path, size, index=index)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


@dataclass
class Slide:
    title: str
    kicker: str = ""
    visual: Optional[str] = None
    lines: Sequence[Tuple[str, str]] = field(default_factory=tuple)  # (text, style)
    marks: Sequence[dict] = field(default_factory=tuple)
    footer: str = ""


def _wrap(draw, text, font, max_w) -> List[str]:
    out, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def _draw_marks(vis: Image.Image, marks: Iterable[dict]) -> Image.Image:
    vis = vis.convert("RGBA")
    overlay = Image.new("RGBA", vis.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    vw, vh = vis.size
    for m in marks:
        x, y, w, h = m["box"]
        rect = [x * vw, y * vh, (x + w) * vw, (y + h) * vh]
        colour = PALETTE.get(m.get("color", "red"), PALETTE["red"])
        style = m.get("style", "fill")
        width = int(m.get("width", 7))
        if style == "fill":
            d.rectangle(rect, fill=colour + (int(255 * m.get("alpha", 0.25)),))
        elif style == "ring":
            d.ellipse(rect, outline=colour + (255,), width=width)
        else:
            d.rectangle(rect, outline=colour + (255,), width=width)
    return Image.alpha_composite(vis, overlay).convert("RGB")


def render(slide: Slide, out_path: str) -> str:
    canvas = Image.new("RGB", (W, H), PALETTE["bg"])
    d = ImageDraw.Draw(canvas)

    panel_x = VIS_X
    if slide.visual:
        vis = Image.open(slide.visual)
        if slide.marks:
            vis = _draw_marks(vis, slide.marks)
        scale = min(VIS_MAX / vis.width, (H - 2 * VIS_Y) / vis.height)
        vis = vis.resize((int(vis.width * scale), int(vis.height * scale)), Image.LANCZOS)
        canvas.paste(vis, (VIS_X, VIS_Y))
        d.rectangle(
            [VIS_X - 2, VIS_Y - 2, VIS_X + vis.width + 2, VIS_Y + vis.height + 2],
            outline=(225, 222, 215),
            width=3,
        )
        panel_x = VIS_X + vis.width + PANEL_GAP

    panel_w = W - panel_x - 50
    y = 70

    if slide.kicker:
        f = _font(30, True)
        d.text((panel_x, y), slide.kicker.upper(), fill=PALETTE["amber"], font=f)
        y += 52

    ft = _font(58, True)
    for line in _wrap(d, slide.title, ft, panel_w):
        d.text((panel_x, y), line, fill=PALETTE["ink"], font=ft)
        y += 70
    y += 26

    fb = _font(37)
    for text, style in slide.lines:
        if not text:
            y += 22
            continue
        bullet = style == "bullet"
        colour = PALETTE["grey"] if style == "muted" else PALETTE["ink"]
        for i, line in enumerate(_wrap(d, text, fb, panel_w - (34 if bullet else 0))):
            if bullet and i == 0:
                d.ellipse([panel_x + 4, y + 16, panel_x + 16, y + 28], fill=PALETTE["amber"])
            d.text((panel_x + (34 if bullet else 0), y), line, fill=colour, font=fb)
            y += 48
        y += 12

    if slide.footer:
        d.text((panel_x, H - 70), slide.footer, fill=PALETTE["grey"], font=_font(26))

    canvas.save(out_path)
    return out_path


if __name__ == "__main__":
    import json
    import sys

    deck = json.load(open(sys.argv[1]))
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    for i, raw in enumerate(deck["slides"], 1):
        s = Slide(
            title=raw["title"],
            kicker=raw.get("kicker", ""),
            visual=raw.get("visual"),
            lines=[tuple(l) for l in raw.get("lines", [])],
            marks=raw.get("marks", []),
            footer=raw.get("footer", ""),
        )
        print(render(s, f"{out_dir}/slide{i:02d}.png"))
