"""URL slugs for article pages."""

import re
import unicodedata


def _base_slug(title):
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def slugify(title, max_length=None):
    """Return a lowercase ASCII slug with words joined by hyphens.

    Accents are removed, so 'Café Olé 2026!' becomes 'cafe-ole-2026'.
    A title with no letters or digits gives an empty string. With a
    max_length, only whole words that fit are kept; a first word longer
    than the limit is cut down to the limit.
    """
    slug = _base_slug(title)
    if max_length is None:
        return slug
    if max_length < 1:
        raise ValueError("max_length must be at least 1")
    if len(slug) <= max_length:
        return slug
    return slug[:max_length].rstrip("-")
