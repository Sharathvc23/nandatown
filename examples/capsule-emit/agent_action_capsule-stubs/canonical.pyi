# SPDX-License-Identifier: Apache-2.0
"""Stub for ``agent_action_capsule.canonical`` (the RFC 8785 JCS digest helper).

Mirrors the exact public signature the tests depend on:
``json_digest(value) -> str`` returns the lowercase-hex SHA-256 of the RFC 8785
canonicalization of ``value``.
"""

from typing import Any

def json_digest(v: Any) -> str: ...
