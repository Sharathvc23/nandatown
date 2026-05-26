# SPDX-License-Identifier: Apache-2.0
"""NEST research harness — A/B experiment infrastructure for hackathon-style runs.

See `scripts/harness/README.md` for usage. Schema version is exposed as
``HARNESS_VERSION`` and stamped on every JSONL row for reproducibility.
"""

from __future__ import annotations

HARNESS_VERSION = "0.1.0"
"""Schema/harness version. Bump on any breaking change to the JSONL row schema."""

SCHEMA_VERSION = 1
"""Integer schema version. Bumped only on backwards-incompatible row changes."""
