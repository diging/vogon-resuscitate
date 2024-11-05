"""
General-purpose helper functions.
"""

from django.conf import settings

from itertools import chain, combinations, groupby
import re
from django.utils import timezone
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


def build_concept_node(concept, user):
    """
    Helper function to build a concept node dictionary.
    """
    return {
        "label": concept.label or "",
        "metadata": {
            "type": "appellation_event",
            "interpretation": concept.uri,
            "termParts": [
                {
                    "position": 1,
                    "expression": concept.label or "",
                    "normalization": "",
                    "formattedPointer": "",
                    "format": ""
                }
            ]
        },
        "context": {
            "creator": user.username,
            "creationTime": timezone.now().strftime('%Y-%m-%d'),
            "creationPlace": "phoenix",
            "sourceUri": concept.authority if hasattr(concept, 'authority') else ""
        }
    }

def get_relation_node(user):
    """
    Helper function to build a relation node.
    """
    return {
        "label": "",
        "metadata": {
            "type": "relation_event"
        },
        "context": {
            "creator": user.username,
            "creationTime": timezone.now().strftime('%Y-%m-%d'),
            "creationPlace": "phoenix",
            "sourceUri": ""
        }
    }

def generate_graph_data(relationsets, user):
    nodes = {}
    edges = []
    node_counter = 0

    def get_node_id():
        nonlocal node_counter
        node_id = str(node_counter)
        node_counter += 1
        return node_id

    for rs in relationsets:
        for relation in rs.constituents.all():
            subject = getattr(relation.source_content_object, 'interpretation', None)
            obj = getattr(relation.object_content_object, 'interpretation', None)
            predicate = getattr(relation.predicate, 'interpretation', None)

            if subject and subject.uri not in nodes:
                subject_id = get_node_id()
                nodes[subject_id] = build_concept_node(subject, user)

            if obj and obj.uri not in nodes:
                obj_id = get_node_id()
                nodes[obj_id] = build_concept_node(obj, user)

            if predicate and predicate.uri not in nodes:
                predicate_id = get_node_id()
                nodes[predicate_id] = build_concept_node(predicate, user)

            relation_id = get_node_id()
            nodes[relation_id] = get_relation_node(user)

            if subject and predicate:
                edges.append({"source": subject_id, "relation": "subject", "target": predicate_id})

            if predicate and obj:
                edges.append({"source": predicate_id, "relation": "predicate", "target": obj_id})

            edges.append({"source": relation_id, "relation": "object", "target": obj_id})

    return {
        "graph": {
            "metadata": {
                "defaultMapping": {
                    "subject": {"type": "REF", "reference": "0"},
                    "predicate": {"type": "URI", "uri": "", "label": ""},
                    "object": {"type": "REF", "reference": "3"}
                },
                "context": {
                    "creator": user.username,
                    "creationTime": timezone.now().strftime('%Y-%m-%d'),
                    "creationPlace": "phoenix",
                    "sourceUri": ""
                }
            },
            "nodes": nodes,
            "edges": edges
        }
    }

def generate_graph_data(relationset, user):
    nodes = {}
    edges = []
    node_counter = 0

    def get_node_id():
        nonlocal node_counter
        node_id = str(node_counter)
        node_counter += 1
        return node_id

    for relation in relationset.constituents.all():
        subject = getattr(relation.source_content_object, 'interpretation', None)
        obj = getattr(relation.object_content_object, 'interpretation', None)
        predicate = getattr(relation.predicate, 'interpretation', None)

        if subject and subject.uri not in nodes:
            subject_id = get_node_id()
            nodes[subject_id] = build_concept_node(subject, user)

        if obj and obj.uri not in nodes:
            obj_id = get_node_id()
            nodes[obj_id] = build_concept_node(obj, user)

        if predicate and predicate.uri not in nodes:
            predicate_id = get_node_id()
            nodes[predicate_id] = build_concept_node(predicate, user)

        relation_id = get_node_id()
        nodes[relation_id] = get_relation_node(user)

        if subject and predicate:
            edges.append({"source": subject_id, "relation": "subject", "target": predicate_id})

        if predicate and obj:
            edges.append({"source": predicate_id, "relation": "predicate", "target": obj_id})

        edges.append({"source": relation_id, "relation": "object", "target": obj_id})

    return {
        "graph": {
            "metadata": {
                "defaultMapping": {
                    "subject": {"type": "REF", "reference": "0"},
                    "predicate": {"type": "URI", "uri": "", "label": ""},
                    "object": {"type": "REF", "reference": "3"}
                },
                "context": {
                    "creator": user.username,
                    "creationTime": timezone.now().strftime('%Y-%m-%d'),
                    "creationPlace": "phoenix",
                    "sourceUri": ""
                }
            },
            "nodes": nodes,
            "edges": edges
        }
    }


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
