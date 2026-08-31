"""Identifier helpers."""

from __future__ import annotations

import re


def slugify(value: str, fallback: str = "scene") -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    return slug or fallback
