from __future__ import annotations

import json
from pathlib import Path


SENSITIVE_WORDS_PATH = Path(__file__).with_name("sensitive_words.json")


def load_sensitive_words(path: str | Path | None = None) -> dict[str, list[str]]:
    target = Path(path) if path else SENSITIVE_WORDS_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def audit_content(content: str, path: str | Path | None = None) -> dict:
    words = load_sensitive_words(path)
    normalized = content.lower()
    blocked = []
    categories = []
    for category, terms in words.items():
        for term in terms:
            if term.lower() in normalized:
                blocked.append(term)
                categories.append(category)
    return {
        "passed": not blocked,
        "blocked_terms": blocked,
        "categories": sorted(set(categories)),
    }
