"""founder_stage: what the stage skills need on top of the raw ledger calls.

- content: read gate specs, stage skills and the current stage's core cards
  from the plugin tree (git is canonical, so this reads markdown, not a DB)
- evidence: parse a gate's `evidence:` minimums and count them in the ledger
- gate: assemble a gate submission and record a decision under the rules
  founders cannot talk their way around

scripts/stage.py is the CLI the SKILL.md files call. Stdlib only.
"""
from __future__ import annotations

from .content import Content
from .evidence import Requirement, count_requirements, parse_requirement
from .gate import GateError, assemble_submission, record_decision, record_signoff

__all__ = [
    "Content", "Requirement", "parse_requirement", "count_requirements",
    "GateError", "assemble_submission", "record_decision", "record_signoff",
]
