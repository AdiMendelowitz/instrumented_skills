"""URL slug helpers for the publishing service.

A slug is lower-case ASCII, with words separated by single hyphens and no
leading or trailing hyphen.
"""

import re
import unicodedata
from collections.abc import Container

MAX_LEN = 60

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _fold_accents(text: str) -> str:
    """Decompose characters and drop the combining marks, keeping base letters."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def make_slug(title: str, max_len: int = MAX_LEN) -> str:
    """Return the slug for a title, no longer than max_len characters.

    Accented letters are reduced to their base letters. If the slug is too
    long it is cut back to whole words. A single word longer than max_len is
    cut at max_len. An empty result becomes "untitled".
    """
    text = _NON_ALNUM.sub("-", _fold_accents(title).lower()).strip("-")
    if len(text) > max_len:
        cut = text.rfind("-", 0, max_len + 1)
        text = text[:cut] if cut > 0 else text[:max_len]
    return text or "untitled"


def unique_slug(slug: str, taken: Container[str]) -> str:
    """Return slug if it is free, otherwise slug-2, slug-3, and so on.

    The first free candidate is returned. The taken container is not changed.
    """
    if slug not in taken:
        return slug
    n = 2
    while f"{slug}-{n}" in taken:
        n += 1
    return f"{slug}-{n}"
