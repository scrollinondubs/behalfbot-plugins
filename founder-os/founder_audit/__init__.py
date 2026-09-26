"""FounderOS auditors: Laya does the per-item tagging, Claude writes the feedback.

    import sys; sys.path.insert(0, os.environ["FOUNDER_OS_DIR"])
    from founder_audit import LayaClient, mom_test

    result = mom_test.audit(transcript, client=LayaClient())

Each auditor returns a JSON-able dict with a `mode`: "laya" when Laya tagged
every item, "claude-only" when it could not (not configured, down, timed out),
in which case the tags are None and the skill has Claude do the tagging. The
SKILL.md files in skills/ drive these through scripts/audit.py.

Stdlib only.
"""
from __future__ import annotations

from .laya import LayaClient, LayaRequestError, LayaUnavailable
from .questions import QuestionSet, QuestionSetError, load

__all__ = ["LayaClient", "LayaRequestError", "LayaUnavailable", "QuestionSet", "QuestionSetError", "load"]
