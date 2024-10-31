"""
General-purpose helper functions.
"""

from django.conf import settings

from itertools import chain, combinations, groupby
import re
import math

def help_text(text):
    """
    Remove excess whitespace from a string. Intended for use in model and form
    fields when writing long help_texts.
    """
    return re.sub('(\s+)', ' ', text)


def basepath(request):
    """
    Generate the base path (domain + path) for the site.

    TODO: Do we need this anymore?

    Parameters
    ----------
    request : :class:`django.http.request.HttpRequest`

    Returns
    -------
    str
    """
    if request.is_secure():
        scheme = 'https://'
    else:
        scheme = 'http://'
    return scheme + request.get_host() + settings.SUBPATH


def get_pagination_metadata(total_items, page, items_per_page):
    """
    Calculate pagination metadata including total pages, page range, and the current page.
    Args:
        total_items (int): Total number of items.
        page (int): The current page number requested.
        items_per_page (int): Number of items per page.
    Returns:
        dict: Pagination metadata including total pages, page range, and the validated current page.
    """

    # Calculate total pages by rounding up the division of total_items / items_per_page
    total_pages = math.ceil(total_items / items_per_page)

    # Ensure the requested page is within the valid range
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    # Create a list of page numbers for pagination navigation
    page_range = list(range(1, total_pages + 1))

    return {
        'total_pages': total_pages,
        'current_page': page,
        'page_range': page_range,
    }