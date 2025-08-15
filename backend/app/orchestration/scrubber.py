from __future__ import annotations

import json
import os
import re
from typing import List, Tuple

# Simple module-level cache
_TITLES: List[str] | None = None
_AUTHORS: List[str] | None = None


def _load_resources() -> Tuple[List[str], List[str]]:
    global _TITLES, _AUTHORS
    if _TITLES is not None and _AUTHORS is not None:
        return _TITLES, _AUTHORS
    base_dir = os.path.dirname(os.path.dirname(__file__))
    rules_path = os.path.join(base_dir, "pastoral", "rules", "marriage.json")
    titles: List[str] = []
    authors: List[str] = []
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Expected structure: { books: [ { key, pretty, author, ... }, ... ] }
        books = data.get("books") or []
        for b in books:
            t = (b.get("pretty") or b.get("title") or "").strip()
            a = (b.get("author") or "").strip()
            if t:
                titles.append(t)
            if a:
                authors.append(a)
    except Exception:
        # Fallback to empty lists if file missing or invalid
        titles, authors = [], []
    _TITLES, _AUTHORS = titles, authors
    return titles, authors


def scrub_books_if_gated(text: str, allow_books: bool) -> Tuple[str, List[str]]:
    """Scrub book/resource mentions when gating disallows them.

    Returns (clean_text, scrubbed_titles)
    """
    if allow_books:
        return text, []

    titles, authors = _load_resources()
    to_scrub: List[str] = []
    original = text or ""

    # Known titles/authors (escape for regex)
    title_patterns = [re.escape(t) for t in titles if t]
    author_patterns = [re.escape(a) for a in authors if a]

    # Generic patterns: quoted titles, explicit resource words, URLs, "by <Name>"
    generic_patterns = [
        r"https?://\S+",  # URLs
        r"[\u201C\u201D\"]([^\u201C\u201D\"]{2,})[\u201C\u201D\"]",  # “Title” or "Title"
        r"\b(?:book|devotional|study|workbook|resource|author|curriculum)\b\s+(?:called|named|titled)?\s*[\u201C\u201D\"]?[^\s,.;:!?]{2,}",
        r"\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}",
    ]

    patterns: List[Tuple[re.Pattern, str]] = []
    if title_patterns:
        patterns.append((re.compile(r"(?:" + "|".join(title_patterns) + r")", re.I), "title"))
    if author_patterns:
        patterns.append((re.compile(r"(?:" + "|".join(author_patterns) + r")", re.I), "author"))
    for gp in generic_patterns:
        patterns.append((re.compile(gp, re.I), "generic"))

    def repl(match: re.Match) -> str:
        val = match.group(0)
        # Capture recognizable title/author tokens for metadata
        snippet = val.strip().strip('"\u201C\u201D')
        if snippet and snippet not in to_scrub:
            # Only store short, readable tokens
            to_scrub.append(snippet[:120])
        # Return a canonical placeholder expected by tests and downstream UI
        return "[resource removed]"

    cleaned = original
    for pat, _kind in patterns:
        cleaned = pat.sub(repl, cleaned)

    # Minor whitespace cleanup and stray punctuation
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+[.,;:!?]", lambda m: m.group(0).strip(), cleaned)
    cleaned = cleaned.strip()

    return cleaned, to_scrub
