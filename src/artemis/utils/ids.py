"""Identifier generation and utility helpers."""

from __future__ import annotations

import uuid


def generate_id(prefix: str = "artemis") -> str:
    """Generate a prefixed unique identifier using UUID4."""
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}_{uid}"
