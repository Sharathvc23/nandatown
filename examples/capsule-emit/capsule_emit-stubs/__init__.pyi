# SPDX-License-Identifier: Apache-2.0
"""Type stubs for the third-party ``capsule_emit`` package.

The installed ``capsule_emit`` distribution ships full inline annotations but no
PEP 561 ``py.typed`` marker, so pyright treats every symbol imported from it as
``Unknown``.  This stub-only package (PEP 561 ``<name>-stubs`` layout, resolved
via the ``examples/capsule-emit`` entry already on pyright's search path) mirrors
the exact public signatures this plugin depends on, so the plugin's own call
sites type-check cleanly without a single ``# type: ignore``.

Only the surface actually used by ``capsule_emit_nanda`` is declared here.
"""

import os
from typing import Any

class EmitResult:
    capsule_id: str
    anchored: bool
    capsule: dict[str, Any]
    def __repr__(self) -> str: ...

def emit(
    action: str,
    operator: str = ...,
    developer: str = ...,
    *,
    runtime: str | None = ...,
    agent_input: Any = ...,
    agent_output: Any = ...,
    model: dict[str, str] | None = ...,
    verdict: str = ...,
    effect: dict[str, Any] | None = ...,
    confirms: str | None = ...,
    relation: str = ...,
    anchor: bool = ...,
    ledger: str | os.PathLike[str] = ...,
    anchor_url: str | None = ...,
    human_disposed: bool = ...,
    approver: str = ...,
    decision: str = ...,
    action_type: str | None = ...,
    extra_compute: dict[str, Any] | None = ...,
    disposition_authority: str | None = ...,
) -> EmitResult: ...
def read_ledger(path: str | os.PathLike[str]) -> list[dict[str, Any]]: ...
def verify_input_digest(capsule: dict[str, Any], candidate_input: Any) -> bool: ...
