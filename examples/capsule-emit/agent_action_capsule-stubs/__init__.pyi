# SPDX-License-Identifier: Apache-2.0
"""Type stubs for the third-party ``agent_action_capsule`` package.

The installed ``agent_action_capsule`` distribution ships full inline
annotations but no PEP 561 ``py.typed`` marker, so pyright treats every symbol
imported from it as ``Unknown`` (and reports ``reportMissingModuleSource`` /
``Stub file not found``).  This stub-only package (PEP 561 ``<name>-stubs``
layout, resolved via the ``examples/capsule-emit`` entry already on pyright's
search path) declares just the surface this project's tests import.

Only ``agent_action_capsule.canonical.json_digest`` is used here; see
``canonical.pyi``.
"""
