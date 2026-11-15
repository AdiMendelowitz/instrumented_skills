"""Pagination helpers for the listing API.

The API numbers pages from 1. Items are plain Python sequences.
"""


def _check_size(size):
    if size < 1:
        raise ValueError("size must be at least 1")


def _check_page(page):
    if page < 1:
        raise ValueError("page must be at least 1")


def page_slice(items, page, size):
    """Return the items shown on one page. Page 1 holds the first size items.

    A page past the last one gives an empty list.
    """
    _check_size(size)
    _check_page(page)
    start = (page - 1) * size
    return items[start:start + size]


def total_pages(count, size):
    """Return how many pages are needed to show count items, counting a partial last page."""
    _check_size(size)
    if count < 0:
        raise ValueError("count cannot be negative")
    return (count + size - 1) // size


def next_page(page, count, size):
    """Return the number of the page after page, or None when page is the last one."""
    _check_page(page)
    last = total_pages(count, size)
    if page < last:
        return page + 1
    return None
