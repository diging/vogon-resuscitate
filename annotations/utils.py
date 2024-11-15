"""
General-purpose helper functions.
"""

from django.conf import settings

from itertools import chain, combinations, groupby
from django.db.models import Q, Count, F
import re
import math

from annotations import models

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

def get_ordering_metadata(request, default_field='title', allowed_fields=None):
    """
    Get ordering metadata from request parameters.
    
    Parameters
    ----------
    request : HttpRequest
        The request object containing GET parameters
    default_field : str
        Default field to order by if none specified
    allowed_fields : list
        List of fields that are allowed for ordering
        
    Returns
    -------
    dict
        Dictionary containing order_by parameter and order_field to use in query
    """
    if allowed_fields is None:
        allowed_fields = [default_field]
        
    # Get order_by from request, default to default_field
    order_by = request.GET.get('order_by', default_field)
    
    # Parse direction and field
    if order_by.startswith('-'):
        order_field = order_by[1:]
        order_direction = '-'
    else:
        order_field = order_by
        order_direction = ''
    
    # Validate order field
    if order_field not in allowed_fields:
        order_field = default_field
        order_direction = ''
        order_by = default_field
        
    order_param = f"{order_direction}{order_field}"
    
    return {
        'order_by': order_by,
        'order_param': order_param
    }

def get_user_project_stats(user, project):
    """
    Get statistics for a user's contributions to a project.
    
    Parameters
    ----------
    user : VogonUser
        The user to get stats for
    project : TextCollection
        The project to get stats from
        
    Returns
    -------
    dict
        Dictionary containing user stats including:
        - number of texts added
        - number of appellations
        - number of relations
        - user object reference
    """
    stats = {
        'user': user,
        'num_texts_added': models.Text.objects.filter(
            addedBy=user,
            partOf=project
        ).count(),
        'num_appellations': models.Appellation.objects.filter(
            createdBy=user,
            occursIn__partOf=project
        ).count(),
        'num_relations': models.RelationSet.objects.filter(
            createdBy=user,
            occursIn__partOf=project,
        ).count(),
    }
    
    return stats

def _annotate_project_counts(queryset):
    """
    Helper function to annotate project queryset with counts of texts, relations and collaborators.
    
    Parameters
    ----------
    queryset : QuerySet
        Base queryset of TextCollection objects
        
    Returns
    -------
    QuerySet
        Annotated queryset with num_texts, num_relations, and num_collaborators
    """
    return queryset.annotate(
        num_texts=Count('texts', distinct=True),
        # Count relations created by either collaborators or project owner
        # texts__relationsets: Access relationsets through texts
        # filter: Only count relations where creator is either:
        #   - One of the project collaborators (createdBy__in=collaborators)
        #   - The project owner (createdBy=ownedBy)
        num_relations=Count('texts__relationsets', 
                          filter=Q(texts__relationsets__createdBy__in=F('collaborators')) | 
                                Q(texts__relationsets__createdBy=F('ownedBy')),
                          distinct=True),
        num_collaborators=Count('collaborators', distinct=True)
    )