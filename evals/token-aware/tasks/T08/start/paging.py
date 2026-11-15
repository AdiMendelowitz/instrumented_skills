"""Pagination helpers for the listing API.

The API numbers pages from 1. Items are plain Python sequences.
"""


def page_slice(items, page, size):
    """Return the items shown on one page. Page 1 holds the first size items."""
    start = page * size
    return items[start:start + size]


def total_pages(count, size):
    """Return how many pages are needed to show count items."""
    return count // size
