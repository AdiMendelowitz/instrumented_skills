"""URL slug helpers for the publishing service.

A slug is lower-case ASCII, with words separated by single hyphens and no
leading or trailing hyphen.
"""

import re

MAX_LEN = 60

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def make_slug(title: str, max_len: int = MAX_LEN) -> str:
    """Return the slug for a title, no longer than max_len characters.

    Accented letters are reduced to their base letters. If the slug is too
    long it is cut back to whole words. A single word longer than max_len is
    cut at max_len. An empty result becomes "untitled".
    """
    text = _NON_ALNUM.sub("-", title.lower()).strip("-")
    if len(text) > max_len:
        text = text[:max_len]
    return text or "untitled"
