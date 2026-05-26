# SPDX-License-Identifier: Apache-2.0
"""Tiny parsers shared between run_condition.py and analyze.py.

Kept in a private module so the regex set has exactly one home — adding a
phrase here is the safe, backwards-compatible way to widen calibration
coverage. Removing or narrowing a phrase requires a SCHEMA.md bump.
"""

from __future__ import annotations

import re

# Loose, case-insensitive "agent claimed CI is green" phrases. Order does not
# matter (we only check `any(...)`). Add new phrases; do not narrow existing
# ones without bumping the schema version.
CLAIM_GREEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\ball tests pass(ed)?\b", re.IGNORECASE),
    re.compile(r"\btests (are )?passing\b", re.IGNORECASE),
    re.compile(r"\btests pass(ed)?\b", re.IGNORECASE),
    re.compile(r"\bruff (check )?(is )?clean\b", re.IGNORECASE),
    re.compile(r"\bci (is )?green\b", re.IGNORECASE),
    re.compile(r"\bpipeline (is )?green\b", re.IGNORECASE),
    re.compile(r"\ball checks pass(ed)?\b", re.IGNORECASE),
    re.compile(r"\beverything passes\b", re.IGNORECASE),
)


def claimed_ci_green(text: str | None) -> bool:
    """True iff `text` makes any of the CLAIM_GREEN_PATTERNS claims."""
    if not text:
        return False
    return any(pattern.search(text) for pattern in CLAIM_GREEN_PATTERNS)


__all__ = ["CLAIM_GREEN_PATTERNS", "claimed_ci_green"]
