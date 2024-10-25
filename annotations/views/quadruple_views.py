"""
These views are mainly for debugging purposes; they provide quad-xml from
various scenarios.
"""

from django.http import HttpResponse

from annotations import quadriga
from annotations.models import (RelationSet, Appellation, Relation, VogonUser,
                                Text)

from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
import requests

from external_accounts.models import CitesphereAccount

def appellation_xml(request, appellation_id):
    """
    Return partial quad-xml for an :class:`.Appellation`\.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    appellation_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    appellation = Appellation.objects.get(pk=appellation_id)
    appellation_xml = quadriga.to_appellationevent(appellation, toString=True)
    return HttpResponse(appellation_xml, content_type='application/xml')


def relation_xml(request, relation_id):
    """
    Return partial quad-xml for an :class:`.Appellation`\.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    relation_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    relation = Relation.objects.get(pk=relation_id)
    relation_xml = quadriga.to_relationevent(relation, toString=True)
    return HttpResponse(relation_xml, content_type='application/xml')


def relationset_xml(request, relationset_id):
    """
    Return partial quad-xml for an :class:`.Appellation`\.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    relationset_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    relationset = RelationSet.objects.get(pk=relationset_id)
    relation_xml = quadriga.to_relationevent(relationset.root, toString=True)
    return HttpResponse(relation_xml, content_type='application/xml')


def text_xml(request, text_id, user_id):
    """
    Return complete quad-xml for the annotations in a :class:`.Text`\.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    text_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    text = Text.objects.get(pk=text_id)
    user = VogonUser.objects.get(pk=user_id)
    relationsets = RelationSet.objects.filter(occursIn_id=text_id, createdBy_id=user_id)
    text_xml, _ = quadriga.to_quadruples(relationsets, text, user, toString=True)
    return HttpResponse(text_xml, content_type='application/xml')


def submit_quadruples(request, text_id):
    """
    Submit quadruples to Quadriga for a given text and user.
    """
    text = Text.objects.get(pk=text_id)
    user = request.user
    relationsets = RelationSet.objects.filter(occursIn_id=text_id, createdBy_id=user, submitted=False)

    # Get the repository associated with this text
    repository = text.repository

    try:
        citesphere_account = CitesphereAccount.objects.get(user=user, repository=repository)
    except CitesphereAccount.DoesNotExist:
        messages.error(request, 'No Citesphere account found for this user and repository.')
        return redirect('annotate', text_id=text_id)

    if not all(rs.ready() for rs in relationsets):
        messages.error(request, 'Not all concepts are resolved or merged.')
        return redirect('annotate', text_id=text_id)

    nodes = {}
    edges = []
    node_counter = 0  # Ensure sequential node IDs

    def get_node_id():
        nonlocal node_counter
        node_id = str(node_counter)
        node_counter += 1
        return node_id

    for rs in relationsets:
        relations = rs.constituents.all()
        
        for relation in relations:
            subject = relation.source_content_object.interpretation if hasattr(relation.source_content_object, 'interpretation') else None
            obj = relation.object_content_object.interpretation if hasattr(relation.object_content_object, 'interpretation') else None
            predicate = relation.predicate.interpretation if hasattr(relation.predicate, 'interpretation') else None

            # Add nodes
            if subject:
                subject_id = get_node_id()
                if subject_id not in nodes:
                    nodes[subject_id] = build_concept_node(subject, user)

            if obj:
                obj_id = get_node_id()
                if obj_id not in nodes:
                    nodes[obj_id] = build_concept_node(obj, user)

            if predicate:
                predicate_id = get_node_id()
                if predicate_id not in nodes:
                    nodes[predicate_id] = build_concept_node(predicate, user)

            # Add edges
            if subject and predicate:
                edges.append({
                    "source": subject_id,
                    "relation": "subject",
                    "target": predicate_id
                })

            if predicate and obj:
                edges.append({
                    "source": predicate_id,
                    "relation": "predicate",
                    "target": obj_id
                })

    graph_data = {
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
                    "sourceUri": text.uri
                }
            },
            "nodes": nodes,
            "edges": edges
        }
    }

    collection_id = "671c131c717d316af555a8c2"
    endpoint = f"{settings.QUADRIGA_ENDPOINT}/api/v1/collection/{collection_id}/network/add/"

    headers = {
        'Authorization': f'Bearer {citesphere_account.access_token}',
        'Content-Type': 'application/json'
    }

    print(graph_data)

    try:
        response = requests.post(endpoint, json=graph_data, headers=headers)
        response.raise_for_status()

        # relationsets.update(submitted=True, pending=False, submittedOn=timezone.now())
        messages.success(request, 'Quadruples submitted successfully.')
        return redirect('text_public', text_id=text_id)
    except requests.RequestException as e:
        print(f'Failed to submit quadruples. Error: {str(e)}')
        return redirect('annotate', text_id=text_id)

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

