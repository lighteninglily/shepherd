from __future__ import annotations

import json
import os
from typing import List

# Lightweight loader for paraphrased, title-free insight clauses.
# Pulls short, actionable principles from vetted rules JSON.

def _rules_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, "pastoral", "rules", "marriage.json")


def get_insight_clauses(topic: str | None = None, limit: int = 8) -> List[str]:
    """Return up to `limit` short insight clauses for the given topic.

    Currently sources from marriage.json book_sources fields like
    key_principles/practical_patterns/principles/core_convictions.
    """
    path = _rules_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    seen = set()
    out: List[str] = []
    book_sources = (data.get("book_sources") or {})
    for _key, src in book_sources.items():
        for fld in ("key_principles", "practical_patterns", "principles", "core_convictions"):
            items = src.get(fld) or []
            if not isinstance(items, list):
                continue
            for s in items:
                if not isinstance(s, str):
                    continue
                s_clean = s.strip().strip('"\u201C\u201D')
                # Keep moderate-length actionable clauses
                if 20 <= len(s_clean) <= 180 and s_clean.lower().startswith((
                    "live", "pursue", "let ", "serve", "commit", "make ", "pray", "remove", "agree", "speak", "listen", "guard", "schedule", "confess", "forgive", "replace", "set ", "share", "use ", "avoid"
                )):
                    if s_clean not in seen:
                        seen.add(s_clean)
                        out.append(s_clean)
                        if len(out) >= limit:
                            return out
    return out
