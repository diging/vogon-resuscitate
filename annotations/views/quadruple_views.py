"""
These views are mainly for debugging purposes; they provide quad-xml from
various scenarios.
"""

from django.http import HttpResponse

from annotations import quadriga
from annotations.models import (RelationSet, Appellation, Relation, VogonUser,
                                Text)

from django.shortcuts import redirect
from django.http import JsonResponse
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

def submit_quadruples(request, text_id):
    try:
        # Fetch the text and user
        text = Text.objects.get(pk=text_id)
        user = request.user

        # Filter pending and unsubmitted RelationSets for the current user and text
        relationsets = RelationSet.objects.filter(
            occursIn=text, createdBy=user, status='ready_to_submit', submitted=False
        )

        if not relationsets.exists():
            messages.warning(request, "No pending quadruples to submit.")
            return JsonResponse({'warning': 'No pending quadruples to submit.'}, status=400)

        # Ensure all RelationSets are ready for submission
        if any(not rs.ready() for rs in relationsets):
            messages.error(request, "Not all quadruples are ready for submission.")
            return JsonResponse({'error': 'Not all quadruples are ready.'}, status=400)

        # Set up the required graph data
        graph_data = generate_graph_data(relationsets, user)

        # Retrieve the access token from the Citesphere account
        citesphere_account = CitesphereAccount.objects.get(
            user=user, repository=text.repository
        )
        access_token = citesphere_account.access_token

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        # Define the Quadriga endpoint
        collection_id = settings.QUADRIGA_COLLECTION_ID
        endpoint = f"{settings.QUADRIGA_ENDPOINT}/api/v1/collection/{collection_id}/network/add/"

        # Submit the data to the Quadriga endpoint
        response = requests.post(endpoint, json=graph_data, headers=headers)
        response.raise_for_status()

        # Update submitted status and timestamp on successful submission
        relationsets.update(
            submitted=True, submittedOn=timezone.now(), status='submitted'
        )

        messages.success(request, "Quadruples submitted successfully.")
        return JsonResponse({'success': 'Quadruples submitted successfully.'})

    except Text.DoesNotExist:
        messages.error(request, "Text not found.")
        return JsonResponse({'error': 'Text not found.'}, status=404)

    except CitesphereAccount.DoesNotExist:
        messages.error(request, "Citesphere account not found.")
        return JsonResponse({'error': 'No Citesphere account found.'}, status=400)

    except requests.RequestException as e:
        messages.error(request, f"Submission failed: {e}")
        return JsonResponse({'error': 'Failed to submit quadruples.'}, status=500)
