from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.utils import timezone

from annotations.models import Relation, Appellation, DateAppellation, DocumentPosition
from external_accounts.models import CitesphereAccount

import xml.etree.ElementTree as ET
import datetime
import requests
import re

from rest_framework.response import Response
from rest_framework import status

def _created_element(element, annotation):
    ET.SubElement(element, 'id')
    creator = ET.SubElement(element, 'creator')
    creator.text = annotation.createdBy.uri
    creation_date = ET.SubElement(element, 'creation_date')
    creation_date.text = annotation.created.isoformat()
    creation_place = ET.SubElement(element, 'creation_place')
    source_reference = ET.SubElement(element, 'source_reference')
    source_reference.text = annotation.occursIn.uri
    return element


def _get_token(tokenId, tokenizedContent):
    """
    Get the starting character-offset position for the token identified by
    ``tokenId`` in the ``tokenizedContent``.

    Parameters
    ----------
    tokenId : str
    tokenizedContent : str

    Returns
    -------
    position : int
        If the token is not found, returns -1.
    expression : str

    """
    match = re.search(r'(<word id="'+str(tokenId)+'">[^<]*</word>)',
                      tokenizedContent,
                      re.M|re.I)
    if not match:
        return None, None

    before_token = tokenizedContent[:match.start()]
    before_token_stripped = re.sub('<[^>]*>', '', before_token)
    pos = len(before_token_stripped)

    match_token = re.search(r'<word id="'+str(tokenId)+'">([^<]*)</word>',
                      match.group(0),
                      re.M|re.I)
    return pos, match_token.groups()[0]


def to_appellationevent(appellation, toString=False):
    appellation_event = _created_element(ET.Element('appellation_event'), appellation)
    term = _created_element(ET.SubElement(appellation_event, 'term'), appellation)
    interpretation = ET.SubElement(term, 'interpretation')
    interpretation.text = appellation.interpretation.master.uri

    printed_representation = _created_element(ET.SubElement(term, 'printed_representation'), appellation)

    if appellation.position and appellation.position.position_type == DocumentPosition.TOKEN_ID:
        for tokenId in appellation.position.position_value.split(','):
            term_part = _created_element(ET.SubElement(printed_representation, 'term_part'), appellation)
            pos, exp = _get_token(tokenId, appellation.occursIn.tokenizedContent)
            if pos:
                position = ET.SubElement(term_part, 'position')
                position.text = str(pos)
            if exp:
                expression = ET.SubElement(term_part, 'expression')
                expression.text = exp

    if toString:
        return ET.tostring(appellation_event)
    return appellation_event


def to_dateappellationevent(dateappellation, toString=False):
    appellation_event = _created_element(ET.Element('appellation_event'), dateappellation)
    term = _created_element(ET.SubElement(appellation_event, 'term'), dateappellation)
    interpretation = ET.SubElement(term, 'interpretation', datatype="date")
    interpretation.text = dateappellation.__unicode__()
    if toString:
        return ET.tostring(appellation_event)
    return appellation_event


def to_relationevent(relation, toString=False):
    appellation_type = ContentType.objects.get_for_model(Appellation)
    relation_type = ContentType.objects.get_for_model(Relation)
    dateappellation_type = ContentType.objects.get_for_model(DateAppellation)

    relation_event = _created_element(ET.Element('relation_event'), relation)

    # The relation itself.
    relation_element = _created_element(ET.SubElement(relation_event, 'relation'), relation)

    subject = ET.SubElement(relation_element, 'subject')
    if relation.source_content_type.id == relation_type.id:
        source_relation = Relation.objects.get(pk=relation.source_object_id)
        subject.append(to_relationevent(source_relation))
    elif relation.source_content_type.id == appellation_type.id:
        source_appellation = Appellation.objects.get(pk=relation.source_object_id)
        subject.append(to_appellationevent(source_appellation))
    elif relation.source_content_type.id == dateappellation_type.id:
        source_dateappellation = DateAppellation.objects.get(pk=relation.source_object_id)
        subject.append(to_dateappellationevent(source_dateappellation))

    predicate = ET.SubElement(relation_element, 'predicate')
    predicate.append(to_appellationevent(relation.predicate))

    object_ = ET.SubElement(relation_element, 'object')
    if relation.object_content_type.id == relation_type.id:
        object_relation = Relation.objects.get(pk=relation.object_object_id)
        object_.append(to_relationevent(object_relation))
    elif relation.object_content_type.id == appellation_type.id:
        object_appellation = Appellation.objects.get(pk=relation.object_object_id)
        object_.append(to_appellationevent(object_appellation))
    elif relation.object_content_type.id == dateappellation_type.id:
        object_dateappellation = DateAppellation.objects.get(pk=relation.object_object_id)
        object_.append(to_dateappellationevent(object_dateappellation))

    if toString:
        return ET.tostring(relation_event)
    return relation_event


def _generate_network_label(occursIn, createdBy):
    now = datetime.datetime.now()
    return 'Graph for text %s, submitted by %s on %s from VogonWeb' % (occursIn.title, createdBy.username, now.isoformat())


def _generate_workspace_label(createdBy):
    return 'VogonWeb workspace for %s' % createdBy.username


def to_quadruples(relationsets, text, user, network_label=None,
                  workspace_id=None, workspace_label=None,
                  project_id=None, toString=False):
    """
    Generate quadruple XML for a collection of :class:`.RelationSet`\s.

    Parameters
    ----------
    relationsets : :class:`django.db.models.query.QuerySet`
    user : :class:`.VogonUser`
    network_label : str
    workspace_id : str
    workspace_label : str
    project_id : str

    Returns
    -------
    str
    """

    # The root element of the XML is project. That element can have an
    #  attribute ``id`` that contains a project id. This project id does not
    #  have to exist. If it doesn't exist, Quadriga will create a new project.
    #
    # to resolve external ids, we need to know the client that the id belongs to
    # the easisest would be to have a convention, something like
    #  : .../externalId+client
    # then all exising paths could continue to work
    if not project_id:
        project_id = '%s+%s' % (settings.QUADRIGA_PROJECT, settings.QUADRIGA_CLIENTID)

    # If project_id is provided, we assume that it is a -native- Quadriga
    #  project id and use it without deliberation.
    project = ET.Element('project', id=project_id)

    # project has two subelements: details and network.
    details = ET.SubElement(project, "details")
    network = ET.SubElement(project, "network")

    # The details part contains information about the project and workspace a
    #  network should be submitted to and about the client. The following
    #  subelements can be specified:
    #
    # <user_name>: The name of the user submitting a network on client side.
    user_name = ET.SubElement(details, "user_name")
    user_name.text = user.full_name

    # <user_id>: The username of the user submitting a network on client side.
    #  (The user does not have to have an account in Quadriga.)
    user_id = ET.SubElement(details, "user_id")
    user_id.text = user.username

    # <name>: If the project doesn't exist, this element can be used to specify
    #  a project name. If a project with the provided ID already exists, then
    #  this element is ignored.

    # <workspace>: Use this element to specify the workspace that a network
    #  should be stored in. This element is the only one that is required. Use
    #  an id attribute to specify the id of the workspace a networks should be
    #  added to. If such a workspace doesn't exist, then Quadriga will create a
    #  new workspace. Use the content of the workspace tag to specify the name
    #  of a new workspace.
    if not workspace_id:
        # For now, we'll create a separate workspace for each user. Later on,
        #  we may want to provide the user with more control.
        workspace_id = 'ws-%s+%s' % (user.username, settings.QUADRIGA_CLIENTID)

    # to resolve external ids, we need to know the client that the id belongs to
    # the easisest would be to have a convention, something like
    #  : .../externalId+client
    # then all exisint path could continue to work
    if not workspace_id.endswith('+%s' % settings.QUADRIGA_CLIENTID):
        workspace_id += '+%s' % settings.QUADRIGA_CLIENTID
    if not workspace_label:
        workspace_label = _generate_workspace_label(user)
    workspace = ET.SubElement(details, "workspace", id=workspace_id)
    workspace.text = workspace_label

    # <sender>: A designator for the client that is sending the request.
    sender = ET.SubElement(details, 'sender')
    sender.text = 'VogonWeb'

    # The network part contains the submitted network. It has two subelements:
    #  network_name and element_events.
    #
    # <network_name>: The content of this element specifies the name of a network
    network_name = ET.SubElement(network, "network_name")
    if not network_label:
        network_label = _generate_network_label(text, user)
    network_name.text = network_label

    # <element_events>: The network itself.
    element_events = ET.SubElement(network, "element_events")

    for relationset in relationsets:
        element_events.append(to_relationevent(relationset.root))

    params = {
        'project_id': project_id,
        'workspace_id': workspace_id,
    }
    if toString:
        return ET.tostring(project), params
    return project, params


def parse_response(raw_response):
    QDNS = '{http://www.digitalhps.org/Quadriga}'
    root = ET.fromstring(raw_response)
    project = root.find(QDNS + 'passthroughproject')

    data = {}
    for child in project:
        tag = child.tag.replace(QDNS, '')
        data[tag] = child.text
    return data



def build_concept_node(concept, user, creation_time, source_uri):
    """
    Helper function to build a concept node dictionary.
    """
    # Get the appellation that created this concept and add stringRep (annotated text)
    appellation = Appellation.objects.filter(interpretation=concept).first()
    expression = appellation.stringRep or ""
    
    term_parts = []
    term_parts.append({
        "position": appellation.position.position_value if appellation.position else 0,
        "expression": expression,
        "normalization": "",
        "formattedPointer": "",
        "format": ""
    })

    return {
        "label": concept.label or "",
        "metadata": {
            "type": "appellation_event",
            "interpretation": concept.uri,
            "termParts": term_parts
        },
        "context": {
            "creator": user.username,
            "creationTime": creation_time.strftime('%Y-%m-%d'),
            "creationPlace": "",
            "sourceUri": source_uri
        }
    }

def get_relation_node(user, creation_time, source_uri):
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
            "creationTime": creation_time.strftime('%Y-%m-%d'),
            "creationPlace": "",
            "sourceUri": source_uri
        }
    }

def generate_graph_data(relationset, user):
    nodes = {}
    edges = []
    node_counter = 0
    source_uri = relationset.occursIn.uri

    def get_node_id():
        nonlocal node_counter
        node_id = str(node_counter)
        node_counter += 1
        return node_id

    for relation in relationset.constituents.all():
        subject = getattr(relation.source_content_object, 'interpretation', None)
        obj = getattr(relation.object_content_object, 'interpretation', None)
        predicate = getattr(relation.predicate, 'interpretation', None)

        # Extract the creation time from the appellation
        creation_time = relationset.occursIn.created

        if subject and subject.uri not in nodes:
            subject_id = get_node_id()
            nodes[subject_id] = build_concept_node(subject, user, creation_time, source_uri)

        if obj and obj.uri not in nodes:
            obj_id = get_node_id()
            nodes[obj_id] = build_concept_node(obj, user, creation_time, source_uri)

        if predicate and predicate.uri not in nodes:
            predicate_id = get_node_id()
            nodes[predicate_id] = build_concept_node(predicate, user, creation_time, source_uri)

        relation_id = get_node_id()
        nodes[relation_id] = get_relation_node(user, creation_time, source_uri)

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
                    "creationPlace": "",
                    "sourceUri": source_uri
                }
            },
            "nodes": nodes,
            "edges": edges
        }
    }


def submit_to_quadriga(relationset, user, project):
    """
    Helper function to handle all Quadriga-related submission logic for a RelationSet.
    
    Raises:
        CitesphereAccount.DoesNotExist: If the user does not have a Citesphere account.
        requests.RequestException: If there is an error when making the request to Quadriga.
    
    Returns:
        requests.Response: The response object returned by the Quadriga submission request.
    """
    citesphere_account = CitesphereAccount.objects.get(user=user, repository=relationset.occursIn.repository)
    access_token = citesphere_account.access_token

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    collection_id = project.quadriga_id
    endpoint = f"{settings.QUADRIGA_ENDPOINT}/api/v1/collection/{collection_id}/network/add/"

    graph_data = generate_graph_data(relationset, user)

    response = requests.post(endpoint, json=graph_data, headers=headers)
    response.raise_for_status()

    # Update the status of the RelationSet
    relationset.status = 'submitted'
    relationset.submitted = True
    relationset.submittedOn = timezone.now()
    relationset.save()