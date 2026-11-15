"""URL slugs for article pages."""

import re
import unicodedata


def slugify(title):
    """Return a lowercase ASCII slug with words joined by hyphens.

    Accents are removed, so 'Café Olé 2026!' becomes 'cafe-ole-2026'.
    A title with no letters or digits gives an empty string.
    """
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")
