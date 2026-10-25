"""rm_fixtures.py - build a reMarkable document (.rmdoc) the way `rmapi get` returns it.

The pages are written with rmscene's own block writer, so they are real v6
.rm files: the same blocks the tablet writes (author ids, scene tree, a layer
group, line and glyph items). Nothing here comes from a real tablet. Needs
rmscene; the suite skips the tests that use it when it is missing.

The document has six pages in this order:

    PDF page 1   two highlights on one line each, and a legacy .highlights file
    PDF page 2   handwriting: two pen strokes and a highlighter stroke
    inserted     a page the student added after PDF page 2, with one stroke
    PDF page 3   deleted on the tablet; it carries a stroke that must not appear
    PDF page 4   no marks
    PDF page 5   a stroke that was erased (only an eraser line), so no marks
"""
from __future__ import annotations

import io
import json
import zipfile
from uuid import UUID

DOC_ID = "0a1b2c3d-0000-4000-8000-000000000001"
PDF_BYTES = b"%PDF-1.7\n% reading file\n" + b"0" * 64
HIGHLIGHT_1 = "ReMarkable uses its own operating system"
HIGHLIGHT_2 = "named Codex."
LEGACY_HIGHLIGHT = "a highlight from older firmware"


def _blocks(items):
    from rmscene import scene_items as si
    from rmscene.crdt_sequence import CrdtSequenceItem
    from rmscene.scene_stream import (AuthorIdsBlock, MigrationInfoBlock, PageInfoBlock, SceneGlyphItemBlock,
                                      SceneGroupItemBlock, SceneLineItemBlock, SceneTreeBlock, TreeNodeBlock)
    from rmscene.tagged_block_common import CrdtId, LwwValue

    yield AuthorIdsBlock(author_uuids={1: UUID("495ba59f-c943-2b5c-b455-3682f6948906")})
    yield MigrationInfoBlock(migration_id=CrdtId(1, 1), is_device=True)
    yield PageInfoBlock(loads_count=1, merges_count=0, text_chars_count=0, text_lines_count=0)
    yield SceneTreeBlock(tree_id=CrdtId(0, 11), node_id=CrdtId(0, 0), is_update=True, parent_id=CrdtId(0, 1))
    yield TreeNodeBlock(si.Group(node_id=CrdtId(0, 1)))
    yield TreeNodeBlock(si.Group(node_id=CrdtId(0, 11), label=LwwValue(timestamp=CrdtId(0, 12), value="Layer 1")))
    yield SceneGroupItemBlock(parent_id=CrdtId(0, 1), item=CrdtSequenceItem(
        item_id=CrdtId(0, 13), left_id=CrdtId(0, 0), right_id=CrdtId(0, 0), deleted_length=0, value=CrdtId(0, 11)))
    left = CrdtId(0, 0)
    for n, item in enumerate(items):
        item_id = CrdtId(1, 100 + n)
        seq = CrdtSequenceItem(item_id=item_id, left_id=left, right_id=CrdtId(0, 0), deleted_length=0, value=item)
        if isinstance(item, si.GlyphRange):
            yield SceneGlyphItemBlock(parent_id=CrdtId(0, 11), item=seq)
        else:
            yield SceneLineItemBlock(parent_id=CrdtId(0, 11), item=seq)
        left = item_id


def _rm(items) -> bytes:
    from rmscene.scene_stream import write_blocks
    buf = io.BytesIO()
    write_blocks(buf, _blocks(items), options={"version": "3.6"})
    return buf.getvalue()


def _line(points, tool=15):
    from rmscene import scene_items as si
    return si.Line(color=si.PenColor.BLACK, tool=si.Pen(tool),
                   points=[si.Point(x=x, y=y, speed=0, direction=0, width=8, pressure=100) for x, y in points],
                   thickness_scale=2.0, starting_length=0.0)


def _glyph(text, y):
    from rmscene import scene_items as si
    return si.GlyphRange(start=None, length=len(text), text=text, color=si.PenColor.YELLOW,
                         rectangles=[si.Rectangle(x=-600, y=y, w=600, h=50)])


def _page(pid, redir=None, idx="ba", deleted=False):
    page = {"id": pid, "idx": {"timestamp": "1:2", "value": idx}, "template": {"timestamp": "1:1", "value": "Blank"}}
    if redir is not None:
        page["redir"] = {"timestamp": "1:2", "value": redir}
    if deleted:
        page["deleted"] = {"timestamp": "1:3", "value": 1}
    return page


def build_rmdoc() -> bytes:
    pages = [
        ("p-one", 0, "ba", False, [_glyph(HIGHLIGHT_1, 1632), _glyph(HIGHLIGHT_2, 1677)]),
        ("p-two", 1, "bb", False, [_line([(-650, 300), (-500, 320), (-400, 300)]),
                                   _line([(-650, 400), (-400, 400)]),
                                   _line([(-300, 900), (300, 900)], tool=18)]),
        ("p-added", None, "bc", False, [_line([(0, 100), (100, 200)])]),
        ("p-three", 2, "bd", True, [_line([(0, 0), (50, 50)])]),
        ("p-four", 3, "be", False, []),
        ("p-five", 4, "bf", False, [_line([(0, 500), (200, 500)], tool=6)]),
    ]
    content = {"cPages": {"pages": [_page(pid, redir, idx, deleted) for pid, redir, idx, deleted, _ in pages],
                          "original": {"timestamp": "1:1", "value": 5}},
               "fileType": "pdf", "formatVersion": 2, "pageCount": 5}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr(f"{DOC_ID}.content", json.dumps(content))
        zf.writestr(f"{DOC_ID}.metadata", json.dumps({"visibleName": "Safari reading", "type": "DocumentType"}))
        zf.writestr(f"{DOC_ID}.pdf", PDF_BYTES)
        for pid, _, _, _, items in pages:
            if items:
                zf.writestr(f"{DOC_ID}/{pid}.rm", _rm(items))
        zf.writestr(f"{DOC_ID}.highlights/p-one.json",
                    json.dumps({"highlights": [[{"text": LEGACY_HIGHLIGHT, "color": 3, "start": 10, "length": 31}]]}))
    return out.getvalue()
