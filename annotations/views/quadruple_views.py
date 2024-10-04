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

from django.utils import timezone

def submit_quadruples(request, text_id):
    """
    Submit quadruples to Quadriga for a given text and user.
    
    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    text_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponseRedirect`
    """
    text = Text.objects.get(pk=text_id)
    user = request.user
    relationsets = RelationSet.objects.filter(occursIn_id=text_id, createdBy_id=user, submitted=False)
    citesphere_account = CitesphereAccount.objects.get(user=user)

    if not all(rs.ready() for rs in relationsets):
        messages.error(request, 'Not all concepts are resolved or merged.')
        return redirect('annotate', text_id=text_id)

    nodes = {}
    edges = []

    # Loop through each RelationSet
    for rs in relationsets:
        relations = rs.constituents.all()  # Retrieve all relations for this RelationSet

        for relation in relations:
            # Fetch subject, predicate, object data
            subject_concept = relation.source_content_object.interpretation if hasattr(relation.source_content_object, 'interpretation') else None
            object_concept = relation.object_content_object.interpretation if hasattr(relation.object_content_object, 'interpretation') else None
            predicate_concept = relation.predicate.interpretation if hasattr(relation.predicate, 'interpretation') else None

            # Build subject node if it exists
            if subject_concept:
                subject_id = str(subject_concept.id)
                if subject_id not in nodes:
                    nodes[subject_id] = build_concept_node(subject_concept, user)

            # Build object node if it exists
            if object_concept:
                object_id = str(object_concept.id)
                if object_id not in nodes:
                    nodes[object_id] = build_concept_node(object_concept, user)

            # Build predicate node if it exists
            if predicate_concept:
                predicate_id = str(predicate_concept.id)
                if predicate_id not in nodes:
                    nodes[predicate_id] = build_concept_node(predicate_concept, user)

            # Create edges connecting source -> predicate -> object
            if subject_concept and predicate_concept:
                edges.append({
                    "source": subject_id,
                    "relation": "subject",
                    "target": predicate_id
                })
            if predicate_concept and object_concept:
                edges.append({
                    "source": predicate_id,
                    "relation": "predicate",
                    "target": object_id
                })

    # Construct JSON payload dynamically from the database data
    graph_data = {
        "graph": {
            "metadata": {
                "defaultMapping": {
                    "subject": {
                        "type": "REF",
                        "reference": "0"  # Updated dynamically
                    },
                    "predicate": {
                        "type": "URI",
                        "uri": "",  # Updated dynamically
                        "label": ""
                    },
                    "object": {
                        "type": "REF",
                        "reference": "3"  # Updated dynamically
                    }
                },
                "context": {
                    "creator": user.username,
                    "creationTime": timezone.now().strftime('%Y-%m-%d'),
                    "creationPlace": "phoenix",
                    "sourceUri": text.uri
                }
            },
            "nodes": nodes,  # Populated from database content
            "edges": edges   # Populated from database content
        }
    }

    # Retrieve collection ID from settings
    collection_id = settings.QUADRIGA_COLLECTION_ID
    endpoint = f"{settings.QUADRIGA_ENDPOINT}/api/v1/collection/{collection_id}/network/add/"

    # Prepare request headers
    headers = {
        'Authorization': f'Bearer {citesphere_account.access_token}',
        'Content-Type': 'application/json'
    }

    print("GRAPH DATA", graph_data)

    # Submit to Quadriga
    try:
        response = requests.post(endpoint, json=graph_data, headers=headers)
        response.raise_for_status()
        print("QUADRIGA RESPONSE", response.text)

        # Update relationsets as submitted
        relationsets.update(submitted=True, pending=False, submittedOn=timezone.now())
        
        messages.success(request, f'Quadruples submitted successfully.')
        return redirect('text_public', text_id=text_id)
    except requests.RequestException as e:
        print(f'Failed to submit quadruples. Error: {str(e)}')
        return redirect('annotate', text_id=text_id)

def build_concept_node(concept, user):
    """
    Helper function to build a concept node dictionary.
    """
    return {
        "label": concept.label,
        "metadata": {
            "type": "concept",
            "interpretation": concept.uri,
            "termParts": [
                {
                    "position": 1,
                    "expression": concept.label 
                }
            ]
        },
        "context": {
            "creator": user.username,
            "creationTime": timezone.now().strftime('%Y-%m-%d'),
            "creationPlace": "phoenix",
            "sourceUri": concept.authority if hasattr(concept, 'authority') else ''
        }
    }
