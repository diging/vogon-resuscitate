from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.utils import timezone
import logging
import json
import urllib.request
import lxml.etree as ET
import requests
import xml.etree.ElementTree as ET
import datetime
import re

from rest_framework.response import Response
from rest_framework import status

from annotations.models import (
    Relation, Appellation, DateAppellation, DocumentPosition, 
    RelationTemplate, RelationTemplatePart, DefaultMapping
)
from external_accounts.models import CitesphereAccount

logger = logging.getLogger(__name__)

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
    r"""
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

def build_concept_node(appellation, user, creation_time, source_uri):
    """
    Build a node dictionary for an appellation event.
    Each appellation gets its own node even if it points to the same concept.
    The node's termParts come only from the given appellation.

    """
    term_parts = []
    pos = appellation.startPos
    appellation_expression = appellation.stringRep if appellation.stringRep is not None else ""
    term_parts.append({
        "position": pos,
        "expression": appellation_expression,
        "normalization": "",
        "formattedPointer": "",
        "format": ""
    })
    
    # concept's label for the interpretation.
    interpretation_label = appellation.interpretation.label
    
    # concept's source URI
    concept_source_uri = appellation.interpretation.uri

    return {
        "label": interpretation_label,
        "metadata": {
            "type": "appellation_event",
            "interpretation": concept_source_uri,
            "termParts": term_parts
        },
        "context": {
            "creator": user.username,
            "creationTime": creation_time.strftime('%Y-%m-%d'),
            "creationPlace": settings.QUADRIGA_CREATION_PLACE,
            # Get the URI from the Text model that this appellation occurs in:
            # 1. appellation.occursIn -> Text model instance
            # 2. Text.uri contains the full URI like "urn:repository:1:item:W2BW4HMG:file:FILENf0m6N7QEY46"
            # 3. Split on ':' and take last part to get just the file ID "FILENf0m6N7QEY46"
            # 4. Prepend QUADRIGA_GILES_TEXT_ENDPOINT to get full Giles text URL
            "sourceUri": settings.QUADRIGA_GILES_TEXT_ENDPOINT + appellation.occursIn.uri.split(':')[-1] + "/content"
        }
    }

def create_default_mapping(relationset, node_mapping):
    """
    Create the default mapping structure for a RelationSet based on its template structure.
    
    Args:
        relationset: The RelationSet instance to create a mapping for
        node_mapping: Dictionary mapping appellation/relation IDs to their node IDs
    
    Returns:
        default_mapping: A dictionary containing subject, predicate, and object mappings
    """
    top_relation = relationset.root
    # Get the template part from the relationset's template
    template_part = relationset.template.template_parts.first()
    
    # Get the subject, predicate, and object nodes
    subject_node = top_relation.source_content_object
    predicate_node = top_relation.predicate
    object_node = top_relation.object_content_object
    
    # Create keys for looking up node IDs
    subj_key = f"rel-{subject_node.id}-{subject_node.created.isoformat()}" if subject_node and hasattr(subject_node, 'source_content_type_id') else f"app-{subject_node.id}-{subject_node.created.isoformat()}" if subject_node else None
    obj_key = f"rel-{object_node.id}-{object_node.created.isoformat()}" if object_node and hasattr(object_node, 'source_content_type_id') else f"app-{object_node.id}-{object_node.created.isoformat()}" if object_node else None
    
    # Get the structured mapping (guaranteed to be present now)
    default_mapping_instance = relationset.template.default_mapping
    
    # Build the defaultMapping structure using the default_mapping_instance
    default_mapping = {}
    
    # Map source to subject based on default_mapping_instance.subject_type
    if default_mapping_instance.subject_type == DefaultMapping.NODE:
        default_mapping['subject'] = {
            'type': 'REF',
            'reference': node_mapping.get(subj_key, "0")
        }
    else:  # URI
        default_mapping['subject'] = {
            'type': 'URI',
            'uri': default_mapping_instance.subject_value
        }
    
    # Map predicate based on default_mapping_instance.predicate_type
    if default_mapping_instance.predicate_type == DefaultMapping.NODE:
        default_mapping['predicate'] = {
            'type': 'REF',
            'reference': node_mapping.get(f"app-{predicate_node.id}-{predicate_node.created.isoformat()}", "0")
        }
    else:  # URI
        default_mapping['predicate'] = {
            'type': 'URI',
            'uri': default_mapping_instance.predicate_value
        }
    
    # Map object based on default_mapping_instance.object_type
    if default_mapping_instance.object_type == DefaultMapping.NODE:
        default_mapping['object'] = {
            'type': 'REF',
            'reference': node_mapping.get(obj_key, "0")
        }
    else:  # URI
        default_mapping['object'] = {
            'type': 'URI',
            'uri': default_mapping_instance.object_value
        }
    
    return default_mapping


def process_relationset(relationset, user):
    """
    Process a RelationSet by traversing its relations and appellations to create nodes and edges.
    
    Args:
        relationset: The RelationSet instance to process
        user: The user instance for context information
    
    Returns:
        tuple: (nodes, edges, node_mapping) - dictionaries of nodes and edges, and a mapping of IDs to node IDs
    """
    nodes = {}
    edges = []
    node_counter = 0
    node_mapping = {}  # This mapping tracks appellation/relation IDs to their node IDs
    
    def get_node_id():
        nonlocal node_counter
        node_id = str(node_counter)
        node_counter += 1
        return node_id
    
    # Recursive function to process relations
    def process_relation(relation):
        from django.contrib.contenttypes.models import ContentType
        from annotations.models import Relation, Appellation
        
        appellation_type = ContentType.objects.get_for_model(Appellation)
        relation_type = ContentType.objects.get_for_model(Relation)
        
        # Process source (subject)
        source_node_id = None
        if relation.source_content_type_id == relation_type.id:
            # Source is another relation
            source_relation = Relation.objects.get(pk=relation.source_object_id)
            source_node_id = process_relation(source_relation)
        elif relation.source_content_type_id == appellation_type.id:
            # Source is an appellation
            source_appellation = Appellation.objects.get(pk=relation.source_object_id)
            source_node_id = process_appellation(source_appellation)
        
        # Process predicate
        predicate_node_id = process_appellation(relation.predicate)
        
        # Process object
        object_node_id = None
        if relation.object_content_type_id == relation_type.id:
            # Object is another relation
            object_relation = Relation.objects.get(pk=relation.object_object_id)
            object_node_id = process_relation(object_relation)
        elif relation.object_content_type_id == appellation_type.id:
            # Object is an appellation
            object_appellation = Appellation.objects.get(pk=relation.object_object_id)
            object_node_id = process_appellation(object_appellation)
        
        # Create relation node
        relation_id = f"rel-{relation.id}-{relation.created.isoformat()}"
        if relation_id not in node_mapping:
            node_id = get_node_id()
            node_mapping[relation_id] = node_id
            
            source_uri = settings.QUADRIGA_GILES_TEXT_ENDPOINT + relation.part_of.occursIn.uri.split(':')[-1] + "/content"
            nodes[node_id] = get_relation_node(user, relation.created, source_uri)
            
            # Add edges
            if source_node_id:
                edges.append({
                    "source": node_id,
                    "relation": "subject",
                    "target": source_node_id
                })
            
            if predicate_node_id:
                edges.append({
                    "source": node_id,
                    "relation": "predicate",
                    "target": predicate_node_id
                })
            
            if object_node_id:
                edges.append({
                    "source": node_id,
                    "relation": "object",
                    "target": object_node_id
                })
                
        return node_mapping[relation_id]
    
    def process_appellation(appellation):
        appellation_id = f"app-{appellation.id}-{appellation.created.isoformat()}"
        if appellation_id not in node_mapping:
            node_id = get_node_id()
            node_mapping[appellation_id] = node_id
            
            # Get the source URI from the document or default to empty
            source_uri = appellation.occursIn.uri if hasattr(appellation.occursIn, 'uri') else ""
            
            # Build the node
            concept_node = build_concept_node(appellation, user, appellation.created, source_uri)
            nodes[node_id] = concept_node
            
        return node_mapping[appellation_id]
    
    # Process the top-level relation
    top_relation = relationset.root
    process_relation(top_relation)
    
    return nodes, edges, node_mapping


def create_graph_context(relationset, user):
    """
    Create the context metadata for a graph.
    
    Args:
        relationset: The RelationSet instance 
        user: The user instance
        
    Returns:
        dict: Context metadata dictionary
    """
    return {
        "creator": user.username,
        "creationTime": relationset.occursIn.created.strftime('%Y-%m-%d'),
        "creationPlace": settings.QUADRIGA_CREATION_PLACE,
        "sourceUri": relationset.occursIn.uri if hasattr(relationset.occursIn, 'uri') else ""
    }


def generate_graph_data(relationset, user):
    """
    JSON-serializable graph structure with unique nodes for each
    appellation event and separate relation event nodes.
    
    Processes nested relations recursively so that each event gets a unique node.
    This function calls the updated build_concept_node so that:
      - metadata.interpretation is the concept label, and
      - context.sourceUri is the URL of the concept source.
    """
    # Process the relationset to generate nodes and edges
    nodes, edges, node_mapping = process_relationset(relationset, user)
    
    # Create the default mapping
    default_mapping = create_default_mapping(relationset, node_mapping)
    
    # Create the context metadata
    context = create_graph_context(relationset, user)
    
    # Build and return the complete graph data structure
    return {
        "graph": {
            "metadata": {
                "defaultMapping": default_mapping,
                "context": context
            },
            "nodes": nodes,
            "edges": edges
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
    endpoint = f"{settings.QUADRIGA_ENDPOINT}/api/v1/collection/{collection_id}/network/add"

    graph_data = generate_graph_data(relationset, user)
    response = requests.post(endpoint, json=graph_data, headers=headers)
    response.raise_for_status()

    # Update the status of the RelationSet
    relationset.status = 'submitted'
    relationset.submitted = True
    relationset.submittedOn = timezone.now()
    relationset.save()