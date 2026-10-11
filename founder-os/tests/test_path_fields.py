#!/usr/bin/env python3
"""test_path_fields.py - the shipped tracks carry the path fields the path
compiler will read.

The lint keeps `requires`/`teaches` optional so any content root can leave them
out. The real basic/ and post-revenue/ trees may not: every card says what it
teaches, every card but the first of its track names what it builds on, every
`requires` id exists, the graph has no cycle, and walking the cards in
(stage, order) is a valid topological order, so a compiler that tie-breaks on
(stage, order) reproduces what learners see today.

Stdlib only, no network. Run:
    python3 founder-os/tests/test_path_fields.py
"""
from __future__ import annotations

import pathlib
import sys
import unittest

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR / "scripts"))

import lint_content  # noqa: E402


def load_track(spec: lint_content.TrackSpec) -> list[lint_content.Item]:
    problems: list[str] = []
    cards, _ = lint_content.collect_track(PLUGIN_DIR, spec, problems)
    assert not problems, problems
    return sorted(cards, key=lambda c: (int(c.fields["stage"]), int(c.fields["order"])))


def topo_order(cards: list[lint_content.Item]) -> list[str]:
    """Kahn's algorithm, always taking the ready card earliest in (stage, order)."""
    position = {c.fields["id"]: (int(c.fields["stage"]), int(c.fields["order"])) for c in cards}
    pending = {c.fields["id"]: set(lint_content.requires_of(c)) for c in cards}
    done: list[str] = []
    while pending:
        ready = [i for i, reqs in pending.items() if reqs <= set(done)]
        if not ready:
            raise AssertionError(f"requires has a cycle among {sorted(pending)}")
        nxt = min(ready, key=position.__getitem__)
        done.append(nxt)
        del pending[nxt]
    return done


class PathFieldsTest(unittest.TestCase):
    def test_every_card_has_teaches_and_requires(self) -> None:
        for spec in lint_content.TRACKS:
            cards = load_track(spec)
            self.assertTrue(cards, spec.name)
            for n, card in enumerate(cards):
                with self.subTest(card=card.rel):
                    teaches = card.fields.get("teaches")
                    self.assertIsInstance(teaches, list, "teaches must be a list")
                    self.assertTrue(teaches, "teaches is empty")
                    if n == 0:
                        self.assertIn(card.fields.get("requires", []), ([],), "the first card requires nothing")
                    else:
                        self.assertTrue(lint_content.requires_of(card), "requires is missing or empty")

    def test_requires_resolve_inside_the_track(self) -> None:
        for spec in lint_content.TRACKS:
            cards = load_track(spec)
            ids = {c.fields["id"] for c in cards}
            for card in cards:
                for req in lint_content.requires_of(card):
                    with self.subTest(card=card.rel, requires=req):
                        self.assertIn(req, ids)

    def test_stage_order_is_the_topological_order(self) -> None:
        for spec in lint_content.TRACKS:
            with self.subTest(track=spec.name):
                cards = load_track(spec)
                self.assertEqual(topo_order(cards), [c.fields["id"] for c in cards])

    def test_lint_finds_no_path_problems(self) -> None:
        problems: list[str] = []
        cards: list[lint_content.Item] = []
        for spec in lint_content.TRACKS:
            cards += load_track(spec)
        lint_content.check_path_fields(cards, problems)
        self.assertEqual(problems, [])

    def test_topo_order_catches_a_forward_requires(self) -> None:
        cards = load_track(lint_content.TRACKS[0])
        by_id = {c.fields["id"]: c for c in cards}
        by_id["basic-find-where-they-talk"].fields["requires"] = ["basic-protect-your-research-time"]
        self.assertNotEqual(topo_order(cards), [c.fields["id"] for c in cards])
        problems: list[str] = []
        lint_content.check_path_fields(cards, problems)
        self.assertTrue(any("does not come before" in p for p in problems), problems)

    def test_topo_order_catches_a_cycle(self) -> None:
        cards = load_track(lint_content.TRACKS[0])
        cards[0].fields["requires"] = [cards[1].fields["id"]]
        self.assertIn(cards[0].fields["id"], lint_content.requires_of(cards[1]))
        with self.assertRaises(AssertionError):
            topo_order(cards)
        problems: list[str] = []
        lint_content.check_path_fields(cards, problems)
        self.assertTrue(any("requires forms a cycle" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
