from __future__ import annotations

import re

from ..extraction.html_parser import clean_text


def concept_id(value: str) -> str:
    """Create a stable concept id from a human label."""
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "unknown"
