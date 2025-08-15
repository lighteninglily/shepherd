import json
from pathlib import Path

import pytest

from backend.app.orchestration.scrubber import scrub_books_if_gated


def _load_marriage_rules():
    repo_root = Path(__file__).resolve().parents[1]
    rules_path = repo_root / "app" / "pastoral" / "rules" / "marriage.json"
    with rules_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_scrubber_noop_when_allowed():
    text = "We recommend reading together and praying."
    cleaned, scrubs = scrub_books_if_gated(text, allow_books=True)
    assert cleaned == text
    assert scrubs == []


def test_scrubber_scrubs_known_title_if_gated():
    data = _load_marriage_rules()
    books = data.get("books") or []
    if not books:
        pytest.skip("No books configured in marriage.json")
    pretty = (books[0].get("pretty") or books[0].get("title") or "").strip()
    assert pretty, "Expected a book title in rules file"
    text = f"A helpful idea from {pretty} is to prioritize grace."
    cleaned, scrubs = scrub_books_if_gated(text, allow_books=False)
    assert "[resource removed]" in cleaned
    # Ensure the pretty title appears captured in scrubbed snippets
    assert any(pretty.lower() in s.lower() for s in scrubs)


def test_scrubber_scrubs_author_name_if_gated():
    data = _load_marriage_rules()
    books = data.get("books") or []
    # Try to find any book with an author field
    author = None
    for b in books:
        a = (b.get("author") or "").strip()
        if a:
            author = a
            break
    if not author:
        pytest.skip("No author found in marriage.json")
    text = f"There's a great thought by {author} that applies here."
    cleaned, scrubs = scrub_books_if_gated(text, allow_books=False)
    assert "[resource removed]" in cleaned
    assert any(author.split()[0].lower() in s.lower() for s in scrubs)


def test_scrubber_scrubs_generic_quoted_title():
    text = 'Consider reading "A Made Up Title" together.'
    cleaned, scrubs = scrub_books_if_gated(text, allow_books=False)
    assert "[resource removed]" in cleaned
    # Quoted title should appear in scrubs
    assert any("made up title" in s.lower() for s in scrubs)


essay_texts = [
    "This week, try the workbook titled \"Repairing Trust\".",
    "Try the devotional by John Smith.",
]


@pytest.mark.parametrize("txt", essay_texts)
def test_scrubber_generic_patterns_cover_workbook_and_by_name(txt):
    cleaned, scrubs = scrub_books_if_gated(txt, allow_books=False)
    assert "[resource removed]" in cleaned
    assert len(scrubs) >= 1
