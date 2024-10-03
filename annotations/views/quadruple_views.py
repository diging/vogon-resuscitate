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
from requests.auth import HTTPBasicAuth
import requests
import datetime

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


def submit_quadruples(request, text_id, user_id):
    """
    Submit quadruples to Quadriga for a given text and user.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    text_id : int
    user_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponseRedirect`
    """
    text = Text.objects.get(pk=text_id)
    user = request.user
    relationsets = RelationSet.objects.filter(occursIn_id=text_id, createdBy_id=user_id)

    # Check if all concepts are ready
    if not all(rs.ready() for rs in relationsets):
        messages.error(request, 'Not all concepts are resolved or merged.')
        return redirect('annotate', text_id=text_id)

    # Generate XML payload
    payload, _ = quadriga.to_quadruples(relationsets, text, user, toString=True)

    # Prepare request
    headers = {'Accept': 'application/xml'}

    # Get collection ID from settings and construct the endpoint URL
    collection_id = settings.QUADRIGA_CollectionID
    endpoint = f"{settings.QUADRIGA_ENDPOINT}api/v1/collection/{collection_id}/network/"

    # Submit to Quadriga
    try:
        response = requests.post(endpoint, 
                                 data=payload, 
                                 headers=headers)
        response.raise_for_status()
        
        # Parse response
        response_data = quadriga.parse_response(response.text)
        
        messages.success(request, f'Quadruples submitted successfully. Network ID: {response_data.get("networkId")}')
        return redirect('text_public', text_id=text_id)
    except requests.RequestException as e:
        messages.error(request, f'Failed to submit quadruples. Error: {str(e)}')
        return redirect('annotate', text_id=text_id)

