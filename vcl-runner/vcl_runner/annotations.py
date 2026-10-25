"""Read a student's marks off a reMarkable document, for a tablet_pull job.

`rmapi get` writes the document as a zip (.rmdoc): `<id>.content` lists the
pages in order, `<id>/<page id>.rm` holds each page's marks in the v6 scene
format, and `<id>.pdf` is the file that was sent. This module returns, per
page:

    highlights   the text the student highlighted (reMarkable snaps a PDF
                 highlight to the text layer and stores the text itself)
    strokes      everything drawn by hand: pen, pencil, marker, highlighter

and renders a page that has strokes as a PNG of the ink alone on a
transparent background, 1404 x 1872 (the tablet's page in its own units), so
the Hub can lay it over the PDF page it printed.

The .rm parse needs rmscene (github.com/ricklupton/rmscene, MIT), which the
BehalfBot image installs; it is imported only when a pull runs, so every other
job works without it. The PNG is written with the standard library.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import posixpath
import struct
import zipfile
import zlib
from dataclasses import dataclass, field

PAGE_WIDTH = 1404
PAGE_HEIGHT = 1872
# A page can be scrolled past its bottom and written on; the render grows to
# hold that, up to twice the page.
MAX_HEIGHT = PAGE_HEIGHT * 2
MAX_ZIP_BYTES = 200 * 1024 * 1024
MAX_HIGHLIGHT_CHARS = 2000

# rmscene's Pen ids. Erasers leave no ink of their own.
ERASERS = {6, 8}
HIGHLIGHTERS = {5, 18, 23}
INK_ALPHA = 255
HIGHLIGHT_ALPHA = 90


class AnnotationsUnavailable(Exception):
    """The document cannot be read here. The message is the error posted."""


@dataclass
class Stroke:
    points: list[tuple[float, float]]
    highlighter: bool = False


@dataclass
class PageMarks:
    """One page of the document. `page` is the PDF page (1-based); a page
    the student inserted on the tablet carries the PDF page before it and
    `inserted` counts from 1."""

    page: int
    inserted: int = 0
    highlights: list[dict] = field(default_factory=list)
    strokes: list[Stroke] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.page}" if not self.inserted else f"{self.page}+{self.inserted}"


@dataclass
class DocumentMarks:
    pages: list[PageMarks]
    pdf: bytes | None


def _load_rmscene():
    try:
        import rmscene  # noqa: F401
        from rmscene import read_tree, scene_items
    except ImportError:
        raise AnnotationsUnavailable(
            "rmscene not installed: pip install 'rmscene>=0.6,<1' on the BehalfBot") from None
    return read_tree, scene_items


def _lww(value):
    """The value of a last-writer-wins field: {"timestamp", "value"} in
    .content JSON, an LwwValue in rmscene, or already plain."""
    if isinstance(value, dict):
        return value.get("value")
    return getattr(value, "value", value)


def _page_order(content: dict) -> list[tuple[str, int | None]]:
    """(page id, 0-based PDF page or None for an inserted page), in reading
    order, deleted pages left out. Handles both .content formats."""
    cpages = content.get("cPages")
    if isinstance(cpages, dict) and isinstance(cpages.get("pages"), list):
        out = []
        pages = [p for p in cpages["pages"] if isinstance(p, dict) and isinstance(p.get("id"), str)]
        pages.sort(key=lambda p: str(_lww(p.get("idx")) or ""))
        for p in pages:
            if _lww(p.get("deleted")):
                continue
            redir = _lww(p.get("redir"))
            out.append((p["id"], redir if isinstance(redir, int) and redir >= 0 else None))
        return out
    ids = content.get("pages")
    if isinstance(ids, list):
        redirs = content.get("redirectionPageMap")
        out = []
        for i, pid in enumerate(ids):
            if not isinstance(pid, str):
                continue
            r = redirs[i] if isinstance(redirs, list) and i < len(redirs) else i
            out.append((pid, r if isinstance(r, int) and r >= 0 else None))
        return out
    return []


def _safe_members(zf: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    total = 0
    members = {}
    for info in zf.infolist():
        name = info.filename
        if name.startswith("/") or ".." in name.split("/") or info.is_dir():
            continue
        total += info.file_size
        if total > MAX_ZIP_BYTES:
            raise AnnotationsUnavailable("the document is too large to read")
        members[posixpath.normpath(name)] = info
    return members


def _legacy_highlights(raw: bytes) -> list[dict]:
    """Highlights from firmware before 3.x, in <id>.highlights/<page>.json."""
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    out = []
    for group in data.get("highlights", []) if isinstance(data, dict) else []:
        for h in group if isinstance(group, list) else []:
            if isinstance(h, dict) and isinstance(h.get("text"), str) and h["text"].strip():
                out.append({"text": h["text"].strip()[:MAX_HIGHLIGHT_CHARS], "color": h.get("color")})
    return out


def _scene_marks(raw: bytes, read_tree, si) -> tuple[list[dict], list[Stroke]]:
    try:
        tree = read_tree(io.BytesIO(raw))
    except Exception as exc:  # rmscene raises plain ValueError/struct.error on a block it cannot read
        raise AnnotationsUnavailable(f"could not read a page ({type(exc).__name__})") from None
    highlights: list[dict] = []
    strokes: list[Stroke] = []

    def walk(group, dx: float):
        if _lww(getattr(group, "visible", True)) is False:
            return
        dx += float(_lww(getattr(group, "anchor_origin_x", None)) or 0)
        for child in group.children.values():
            if child is None:
                continue
            if isinstance(child, si.Group):
                walk(child, dx)
            elif isinstance(child, si.GlyphRange):
                text = (child.text or "").strip()
                if text:
                    highlights.append({"text": text[:MAX_HIGHLIGHT_CHARS], "color": int(child.color)})
            elif isinstance(child, si.Line):
                tool = int(child.tool)
                if tool in ERASERS or not child.points:
                    continue
                strokes.append(Stroke([(p.x + dx, p.y) for p in child.points], tool in HIGHLIGHTERS))

    walk(tree.root, 0.0)
    return highlights, strokes


def read_document(path: str) -> DocumentMarks:
    """Every page that carries a highlight or a stroke, in reading order, and
    the PDF bytes in the document."""
    read_tree, si = _load_rmscene()
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise AnnotationsUnavailable("rmapi did not return a readable document") from None
    with zf:
        members = _safe_members(zf)
        contents = [n for n in members if n.endswith(".content") and "/" not in n]
        if len(contents) != 1:
            raise AnnotationsUnavailable("the document has no page list")
        doc_id = contents[0][: -len(".content")]
        try:
            content = json.loads(zf.read(members[contents[0]]))
        except ValueError:
            raise AnnotationsUnavailable("the document's page list is not JSON") from None
        pdf_info = members.get(f"{doc_id}.pdf")
        pdf = zf.read(pdf_info) if pdf_info else None
        pages: list[PageMarks] = []
        last_pdf_page = 0
        inserted = 0
        for page_id, redir in _page_order(content if isinstance(content, dict) else {}):
            if redir is None:
                inserted += 1
                marks = PageMarks(page=max(1, last_pdf_page), inserted=inserted)
            else:
                last_pdf_page = redir + 1
                inserted = 0
                marks = PageMarks(page=last_pdf_page)
            rm = members.get(f"{doc_id}/{page_id}.rm")
            if rm is not None:
                marks.highlights, marks.strokes = _scene_marks(zf.read(rm), read_tree, si)
            legacy = members.get(f"{doc_id}.highlights/{page_id}.json")
            if legacy is not None:
                seen = {h["text"] for h in marks.highlights}
                marks.highlights += [h for h in _legacy_highlights(zf.read(legacy)) if h["text"] not in seen]
            if marks.highlights or marks.strokes:
                pages.append(marks)
    return DocumentMarks(pages=pages, pdf=pdf)


# --- the PNG ----------------------------------------------------------------------


def _png(width: int, height: int, gray_alpha: bytearray) -> bytes:
    """An 8-bit grey + alpha PNG (colour type 4)."""
    stride = width * 2
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += gray_alpha[y * stride:(y + 1) * stride]

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 4, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def render_page(strokes: list[Stroke]) -> bytes:
    """The ink of one page: black strokes, highlighter strokes as a light
    wash, on a transparent page 1404 wide, its x origin at the centre as on
    the tablet."""
    max_y = max((y for s in strokes for _, y in s.points), default=0)
    height = min(MAX_HEIGHT, max(PAGE_HEIGHT, int(math.ceil(max_y)) + 8))
    width = PAGE_WIDTH
    alpha = bytearray(width * height)

    def dab(cx: float, cy: float, r: int, a: int):
        x0, y0 = int(cx), int(cy)
        for yy in range(max(0, y0 - r), min(height, y0 + r + 1)):
            row = yy * width
            for xx in range(max(0, x0 - r), min(width, x0 + r + 1)):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r + r and alpha[row + xx] < a:
                    alpha[row + xx] = a

    for s in strokes:
        r, a = (10, HIGHLIGHT_ALPHA) if s.highlighter else (2, INK_ALPHA)
        pts = [(x + width / 2, y) for x, y in s.points]
        if len(pts) == 1:
            dab(pts[0][0], pts[0][1], r, a)
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / max(1, r // 2)))
            for i in range(steps + 1):
                t = i / steps
                dab(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r, a)

    pixels = bytearray(width * height * 2)
    pixels[1::2] = alpha
    return _png(width, height, pixels)


def page_hash(png: bytes) -> str:
    return hashlib.sha256(png).hexdigest()


def find_download(directory: str) -> str:
    """The one file `rmapi get` wrote into an empty directory."""
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    if len(files) != 1:
        raise AnnotationsUnavailable("rmapi get wrote no document")
    return os.path.join(directory, files[0])
