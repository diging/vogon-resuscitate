"""
Provides all of the class-based views for the REST API.
"""

from django.db.models import Q
from django.conf import settings

from rest_framework import status
from rest_framework.settings import api_settings

from rest_framework import viewsets, exceptions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework.decorators import action
from rest_framework.pagination import (LimitOffsetPagination,
                                       PageNumberPagination)

from annotations.serializers import *
from annotations.models import *
from concepts.models import Concept, Type
from concepts.lifecycle import *

import uuid

import requests
from django.conf import settings

import json

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOGLEVEL)


# Custom permission class that restricts write access (POST/PUT/DELETE) to only project owners and collaborators,
# while allowing read access (GET) to any authenticated user. This is used to ensure that only authorized users
# can modify annotations within their projects.
class ProjectOwnerOrCollaboratorAccessOrReadOnly(IsAuthenticatedOrReadOnly):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
            
        # Allow GET requests for authenticated users
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True

        # check if user is owner or collaborator For POST/PUT/DELETE 
        text_id = None
        if request.method == 'POST':
            text_id = request.data.get('occursIn')
        elif request.method in ['PUT', 'DELETE']:
            text_id = request.query_params.get('text')
            
        if text_id:
            try:
                text = Text.objects.get(id=text_id)
                collections = text.partOf.all()
                for collection in collections:
                    if (request.user == collection.ownedBy or 
                        request.user in collection.collaborators.all()):
                        return True
            except Text.DoesNotExist:
                return False
                
        return False

    def has_object_permission(self, request, view, annotation):
        # Allow GET requests for authenticated users
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
            
        # Check if user is owner or collaborator of the text's collection
        text = None
        if hasattr(annotation, 'occursIn'):
            text = annotation.occursIn
        
        if text:
            collections = text.partOf.all()
            for collection in collections:
                if (request.user == collection.ownedBy or 
                    request.user in collection.collaborators.all()):
                    return True
                    
        return False

# http://stackoverflow.com/questions/17769814/django-rest-framework-model-serializers-read-nested-write-flat
class SwappableSerializerMixin(object):
    def get_serializer_class(self):
        try:
            return self.serializer_classes[self.request.method]
        except AttributeError:
            logger.debug('%(cls)s does not have the required serializer_classes'
                         'property' % {'cls': self.__class__.__name__})
            raise AttributeError
        except KeyError:
            logger.debug('request method %(method)s is not listed'
                         ' in %(cls)s serializer_classes' %
                         {'cls': self.__class__.__name__,
                          'method': self.request.method})
            # required if you don't include all the methods (option, etc) in your serializer_class
            return super(SwappableSerializerMixin, self).get_serializer_class()


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000


class AnnotationFilterMixin(object):
    """
    Mixin for :class:`viewsets.ModelViewSet` that provides filtering by
    :class:`.Text` and :class:`.User`\.
    """
    def get_queryset(self, *args, **kwargs):
        queryset = super(AnnotationFilterMixin, self).get_queryset(*args, **kwargs)

        textid = self.request.query_params.get('text', None)
        texturi = self.request.query_params.get('text_uri', None)
        userid = self.request.query_params.get('user', None)
        position_type = self.request.query_params.get('position_type', None)
        if position_type:
            queryset = queryset.filter(position__position_type=position_type )
        if textid:
            queryset = queryset.filter(occursIn=int(textid))
        if texturi:
            queryset = queryset.filter(occursIn__uri=texturi)
        if userid:
            queryset = queryset.filter(createdBy__pk=userid)
        elif userid is not None:
            queryset = queryset.filter(createdBy__pk=self.request.user.id)
        return queryset


class UserViewSet(viewsets.ModelViewSet):
    queryset = VogonUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )


class RepositoryViewSet(viewsets.ModelViewSet):
    queryset = Repository.objects.all()
    serializer_class = RepositorySerializer
    permission_classes = (IsAuthenticated, )


class DateAppellationViewSet(AnnotationFilterMixin, viewsets.ModelViewSet):
    queryset = DateAppellation.objects.all()
    serializer_class = DateAppellationSerializer
    permission_classes = (ProjectOwnerOrCollaboratorAccessOrReadOnly, )

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        position = data.pop('position', None)
        if 'month' in data and data['month'] is None:
            data.pop('month')
        if 'day' in data and data['day'] is None:
            data.pop('day')
        serializer_class = self.get_serializer_class()

        try:
            serializer = serializer_class(data=data)
        except Exception as E:
            print((serializer.errors))
            raise E

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as E:
            print((serializer.errors))
            raise E

        try:
            instance = serializer.save()
        except Exception as E:
            print((":::", E))
            raise E

        text_id = serializer.data.get('occursIn')

        if position:
            if type(position) is not DocumentPosition:
                position_serializer = DocumentPositionSerializer(data=position)
                try:
                    position_serializer.is_valid(raise_exception=True)
                except Exception as E:
                    print(("DocumentPosition::", position_serializer.errors))
                    raise E
                position = position_serializer.save()

            instance.position = position
            instance.save()

        instance.refresh_from_db()
        reserializer = DateAppellationSerializer(instance, context={'request': request})

        headers = self.get_success_headers(serializer.data)
        return Response(reserializer.data, status=status.HTTP_201_CREATED,
                        headers=headers)


class AppellationViewSet(SwappableSerializerMixin, AnnotationFilterMixin, viewsets.ModelViewSet):
    queryset = Appellation.objects.filter(asPredicate=False)
    serializer_class = AppellationSerializer
    permission_classes = (ProjectOwnerOrCollaboratorAccessOrReadOnly, )
    serializer_classes = {
        'GET': AppellationSerializer,
        'POST': AppellationPOSTSerializer
    }

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        position = data.get('position')
        pos = data.get('pos')
        label = data.get('label')
        interpretation = data.get('interpretation')  # The old logic checks for this

        try:
            # Check if interpretation (a concept URI) was passed directly
            if isinstance(interpretation, str) and interpretation.startswith('http'):
                try:
                    concept = Concept.objects.get(uri=interpretation)
                except Concept.DoesNotExist:
                    concept_data = fetch_concept_data(interpretation, pos)
                    type_data = concept_data.get('concept_type')
                    type_instance = None
                    
                    # Handle concept type creation if necessary
                    if type_data:
                        try:
                            type_instance = Type.objects.get(uri=type_data.get('type_uri'))
                        except Type.DoesNotExist:
                            # Create a new Type instance if it doesn't exist
                            type_instance = Type.objects.create(
                                uri=type_data.get('type_uri'),
                                label=type_data.get('type_name'),
                                description=type_data.get('description',''),
                                authority=concept_data.get('authority', {}),
                            )

                    # Create a new concept instance
                    concept = ConceptLifecycle.create(
                        uri=interpretation,
                        label=label,
                        description=concept_data.get('description'),
                        typed=type_instance,
                        authority=concept_data.get('authority', {}),
                    ).instance

                data['interpretation'] = concept.id

            else:
                # If interpretation is not a URI, fetch concept based on label and pos
                concept = ConceptLifecycle.create(
                    uri=interpretation,
                    label=label,
                    description=concept_data.get('description'),
                    typed=type_instance,
                    authority=concept_data.get('authority', {}),
                ).instance

                # Set the interpretation to the concept ID
                data['interpretation'] = concept.id

        except ValueError as e:
            return Response({'error': str(e)}, status=400)

        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=data)

        try:
            serializer = serializer_class(data=data)
        except Exception as E:
            print((serializer.errors))
            raise E

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as E:
            print((serializer.errors))
            raise E

        try:
            instance = serializer.save()
        except Exception as E:
            print((":::", E))
            raise E

        tokenIDs = serializer.data.get('tokenIds', None)
        text_id = serializer.data.get('occursIn')

        if tokenIDs:
            position = DocumentPosition.objects.create(
                occursIn_id=text_id,
                position_type=DocumentPosition.TOKEN_ID,
                position_value=tokenIDs
            )
            instance.position = position
            instance.save()

        if position:
            if not isinstance(position, DocumentPosition):
                position_serializer = DocumentPositionSerializer(data=position)
                try:
                    position_serializer.is_valid(raise_exception=True)
                except Exception as E:
                    print(("DocumentPosition::", position_serializer.errors))
                    raise E
                position = position_serializer.save()

            instance.position = position
            instance.save()

        instance.refresh_from_db()
        reserializer = AppellationSerializer(instance, context={'request': request})

        headers = self.get_success_headers(serializer.data)
        return Response(reserializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset(self, *args, **kwargs):
        queryset = AnnotationFilterMixin.get_queryset(self, *args, **kwargs)

        concept = self.request.query_params.get('concept', None)
        text = self.request.query_params.get('text', None)
        thisuser = self.request.query_params.get('thisuser', False)
        project_id = self.request.query_params.get('project', None)
        position_type = self.request.query_params.get('position_type', None)
        if thisuser:
            queryset = queryset.filter(createdBy_id=self.request.user.id)
        if concept:
            queryset = queryset.filter(interpretation_id=concept)
        if text:
            queryset = queryset.filter(occursIn_id=text)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if position_type and position_type in DocumentPosition.TYPES:
            queryset = queryset.filter(position__position_type=position_type)
        return queryset.order_by('-created')


class PredicateViewSet(AnnotationFilterMixin, viewsets.ModelViewSet):
    queryset = Appellation.objects.filter(asPredicate=True)
    serializer_class = AppellationSerializer
    permission_classes = (ProjectOwnerOrCollaboratorAccessOrReadOnly, )


class RelationSetViewSet(viewsets.ModelViewSet):
    queryset = RelationSet.objects.all()
    serializer_class = RelationSetSerializer
    permission_classes = (ProjectOwnerOrCollaboratorAccessOrReadOnly, )

    def get_queryset(self, *args, **kwargs):
        queryset = super(RelationSetViewSet, self).get_queryset(*args, **kwargs)

        textid = self.request.query_params.getlist('text')
        userid = self.request.query_params.getlist('user')

        if len(textid) > 0:
            queryset = queryset.filter(occursIn__in=[int(t) for t in textid])
        if len(userid) > 0:
            queryset = queryset.filter(createdBy__pk__in=[int(i) for i in userid])
        elif userid is not None and type(userid) is not list:
            queryset = queryset.filter(createdBy__pk=self.request.user.id)

        thisuser = self.request.query_params.get('thisuser', False)
        project_id = self.request.query_params.get('project', None)
        if thisuser:
            queryset = queryset.filter(createdBy_id=self.request.user.id)
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        return queryset.order_by('-created')


class RelationViewSet(viewsets.ModelViewSet):
    queryset = Relation.objects.all()
    serializer_class = RelationSerializer
    permission_classes = (ProjectOwnerOrCollaboratorAccessOrReadOnly, )

    def get_queryset(self, *args, **kwargs):
        """
        Supports filtering by :class:`.Text`\, :class:`.User`\, node concept
        type, and predicate concept type.
        """

        queryset = super(RelationViewSet, self).get_queryset(*args, **kwargs)

        textid = self.request.query_params.getlist('text')
        userid = self.request.query_params.getlist('user')
        typeid = self.request.query_params.getlist('type')
        conceptid = self.request.query_params.getlist('concept')
        related_concepts = self.request.query_params.getlist('related_concepts')

        # Refers to the predicate's interpretation, not the predicate itself.
        predicate_conceptid = self.request.query_params.getlist('predicate')

        # TODO: clean this up.
        if len(textid) > 0:
            queryset = queryset.filter(occursIn__in=[int(t) for t in textid])
        if len(typeid) > 0:
            queryset = queryset.filter(source__interpretation__typed__pk__in=[int(t) for t in typeid]).filter(object__interpretation__typed__pk__in=[int(t) for t in typeid])
        if len(predicate_conceptid) > 0:
            queryset = queryset.filter(predicate__interpretation__pk__in=[int(t) for t in predicate_conceptid])
        if len(conceptid) > 0:  # Source or target concept in `concept`.
            queryset = queryset.filter(Q(source__interpretation__id__in=[int(c) for c in conceptid]) | Q(object__interpretation__id__in=[int(c) for c in conceptid]))
        if len(related_concepts) > 0:  # Source or target concept in `concept`.
            queryset = queryset.filter(Q(source__interpretation__id__in=[int(c) for c in related_concepts]) & Q(object__interpretation__id__in=[int(c) for c in related_concepts]))
        if len(userid) > 0:
            queryset = queryset.filter(createdBy__pk__in=[int(i) for i in userid])
        elif userid is not None and type(userid) is not list:
            queryset = queryset.filter(createdBy__pk=self.request.user.id)

        thisuser = self.request.query_params.get('thisuser', False)
        if thisuser:
            queryset = queryset.filter(createdBy_id=self.request.user.id)

        return queryset


# TODO: do we need this anymore?
class TemporalBoundsViewSet(viewsets.ModelViewSet, AnnotationFilterMixin):
    queryset = TemporalBounds.objects.all()
    serializer_class = TemporalBoundsSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )


class TextViewSet(viewsets.ModelViewSet):
    queryset = Text.objects.all()
    serializer_class = TextSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )
    # pagination_class = StandardResultsSetPagination

    def get_queryset(self, *args, **kwargs):
        """
        A user can see only their own :class:`.TextCollection`\s.
        """

        queryset = super(TextViewSet, self).get_queryset(*args, **kwargs)

        textcollectionid = self.request.query_params.get('textcollection', None)
        conceptid = self.request.query_params.getlist('concept')
        related_concepts = self.request.query_params.getlist('related_concepts')
        uri = self.request.query_params.get('uri', None)

        if textcollectionid:
            queryset = queryset.filter(partOf=int(textcollectionid))
        if uri:
            queryset = queryset.filter(uri=uri)
        if len(conceptid) > 0:
            queryset = queryset.filter(appellation__interpretation__pk__in=[int(c) for c in conceptid])
        if len(related_concepts) > 1:
            queryset = queryset.filter(appellation__interpretation_id=int(related_concepts[0])).filter(appellation__interpretation_id=int(related_concepts[1]))

        return queryset.distinct()


class TextCollectionViewSet(viewsets.ModelViewSet):
    queryset = TextCollection.objects.all()
    serializer_class = TextCollectionSerializer
    permission_classes = (IsAuthenticated, )

    def get_queryset(self, *args, **kwargs):
        """
        """
        queryset = super(TextCollectionViewSet, self).get_queryset(*args, **kwargs)

        userid = self.request.query_params.get('user', None)
        if userid:
            queryset = queryset.filter(ownedBy__pk=userid)
        else:
            queryset = queryset.filter(Q(ownedBy__pk=self.request.user.id) | Q(participants=self.request.user.id))
        return queryset

    def create(self, request, *args, **kwargs):

        data = request.data
        if 'ownedBy' not in data:
            data['ownedBy'] = request.user.id
        if 'participants' not in data:
            data['participants'] = []

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)
        headers = self.get_success_headers(data)

        return Response(serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers)


class TypeViewSet(viewsets.ModelViewSet):
    queryset = Type.objects.all()
    serializer_class = TypeSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )


class ConceptViewSet(viewsets.ModelViewSet):
    queryset = Concept.objects.filter(~Q(concept_state=Concept.REJECTED))
    serializer_class = ConceptSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )

    def create(self, request, *args, **kwargs):
        data = request.data
        if data['uri'] == 'generate':
            data['uri'] = 'http://vogonweb.net/{0}'.format(uuid.uuid4())

        if 'lemma' not in data:
            data['lemma'] = data['label']

        concept_type = data.get('typed', '')
        try:
            int(concept_type)
        except:
            data['typed'] = Type.objects.get(uri=concept_type).id

        serializer = self.get_serializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as E:
            print((serializer.errors))
            raise E

        self.perform_create(serializer)
        headers = self.get_success_headers(data)
        return Response(serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers)

    @action(detail=False)
    def search(self, request, **kwargs):
        q = request.GET.get('search', None)
        if not q:
            return Response({'results': []})
        pos = request.GET.get('pos', None)

        # Search ConceptPower
        cp_concepts = self._search_conceptpower(q, pos)
        
        # Search VIAF
        viaf_concepts = self._search_viaf(q)

        # Combine and sort results
        exact_matches = []
        other_matches = []

        for concept in cp_concepts:
            if concept['label'].lower() == q.lower():
                exact_matches.append(concept)
            else:
                other_matches.append(concept)

        for concept in viaf_concepts:
            if concept['label'].lower() == q.lower():
                exact_matches.append(concept)
            else:
                other_matches.append(concept)

        # Sort results to show ConceptPower results first in each category
        exact_matches.sort(key=lambda x: x['authority']['name'] != 'Conceptpower')
        other_matches.sort(key=lambda x: x['authority']['name'] != 'Conceptpower')

        # Combine all results with exact matches first
        all_results = exact_matches + other_matches
        return Response({'results': all_results})

    def _search_conceptpower(self, q, pos=None):
        url = f"{settings.CONCEPTPOWER_ENDPOINT}ConceptSearch"
        parameters = {
            'word': q,
            'pos': pos if pos else None,
        }
        headers = {
            'Accept': 'application/json',
        }
        try:
            response = requests.get(url, headers=headers, params=parameters)
            if response.status_code == 200:
                data = response.json()
                concepts = []
                for concept_entry in data['conceptEntries']:
                    concept = parse_concept(concept_entry)
                    concept = _relabel(concept)
                    concept['authority']['name'] = 'Conceptpower'
                    concepts.append(concept)
                return concepts
        except Exception as e:
            logger.error(f"Error searching ConceptPower: {str(e)}")
            return []
        return []

    def _search_viaf(self, q):
        encoded_query = requests.utils.quote(f'local.names all "{q}"')
        url = f"http://viaf.org/viaf/search?query={encoded_query}&httpAccept=application/json"
        
        try:
            response = requests.get(url)
            print(response.text) # DEBUG
            if response.status_code == 200:
                data = response.json()
                concepts = []
                
                if 'searchRetrieveResponse' in data:
                    records = data['searchRetrieveResponse'].get('records', [])
                    
                    for record in records:
                        record_data = record.get('record', {}).get('recordData', {})
                        if record_data:
                            concept = parse_viaf_concept(record_data)
                            concept['authority']['name'] = 'VIAF'
                            concepts.append(concept)
                return concepts
        except Exception as e:
            logger.error(f"Error searching VIAF: {str(e)}")
            return []
        return []

    def get_queryset(self, *args, **kwargs):
        """
        Filter by part of speach (``pos``).
        """
        queryset = super(ConceptViewSet, self).get_queryset(*args, **kwargs)

        # Limit results to those with ``pos``.
        pos = self.request.query_params.get('pos', None)
        if pos:
            if pos != 'all':
                queryset = queryset.filter(pos__in=[pos.upper(), pos.lower()])

        # Search Concept labels for ``search`` param.
        query = self.request.query_params.get('search', None)
        remote = self.request.query_params.get('remote', False)
        uri = self.request.query_params.get('uri', None)
        type_id = self.request.query_params.get('typed', None)
        type_strict = self.request.query_params.get('strict', None)
        type_uri = self.request.query_params.get('type_uri', None)
        max_results = self.request.query_params.get('max', None)

        if uri:
            queryset = queryset.filter(uri=uri)
        if type_uri:
            queryset = queryset.filter(type__uri=uri)
        if type_id:
            if type_strict:
                queryset = queryset.filter(typed_id=type_id)
            else:
                queryset = queryset.filter(Q(typed_id=type_id) | Q(typed=None))
        if query:
            if pos == 'all':
                pos = None

            queryset = queryset.filter(label__icontains=query)

        if max_results:
            return queryset[:max_results]
        return queryset


def fetch_concept_data(concept_uri, pos=None):
    """
    Fetch concept data from ConceptPower based on the given URI (unique identifier) and part of speech (pos).
    Returns the concept data in a suitable format for the create function.
    """

    url = f"{settings.CONCEPTPOWER_ENDPOINT}Concept?id={concept_uri}"
    headers = {
        'Accept': 'application/json',
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            concept_entry = data.get('conceptEntries', [None])[0]
            return parse_concept(concept_entry) if concept_entry else {}
        except Exception as e:
            raise ValueError(f"Error parsing ConceptPower response: {str(e)}")
    else:
        raise ValueError(f"Error fetching concept data: {response.status_code}")


def _relabel(datum):
    """
    Relabel fields to match a standardized structure.
    """
    _fields = {
        'name': 'label',
        'id': 'alt_id',
        'concept_uri': 'uri'
    }
    return {_fields.get(k, k): v for k, v in datum.items()}

def parse_concept(concept_entry):
    """
    Parse a concept and return a dictionary with the required fields.
    """
    concept = {}
    concept['uri'] = concept_entry.get('concept_uri', '')
    concept['label'] = concept_entry.get('lemma', '')
    concept['id'] = concept_entry.get('id', '')
    concept['pos'] = concept_entry.get('pos', '')
    concept['concept_type'] = concept_entry.get('type','')

    description = concept_entry.get('description', '')
    try:
        concept['description'] = json.loads(f'"{description}"')
    except json.JSONDecodeError:
        concept['description'] = description
    
    if concept['uri'].startswith(tuple(settings.CONCEPT_URI_PREFIXES)):
        concept['authority'] = {'name': 'Conceptpower'}
    else:
        concept['authority'] = {'name': 'Unknown'}
    
    return concept

def parse_viaf_concept(record_data):
    """
      - Handle 'mainHeadings.data' as either a dict or list
      - If no 'mainHeadings' field, safely fall back to ''
    """
    concept = {}

    viaf_id = record_data.get('viafID', '')
    concept['uri'] = f'https://viaf.org/viaf/{viaf_id}'

    main_headings = record_data.get('mainHeadings', {})
    data_field = main_headings.get('data', {})
    label = ''

    # 'data' is a dict with a 'text' key, parse it
    if isinstance(data_field, dict):
        label = data_field.get('text', '')

    # 'data' is a list, parse the first entry that has 'text'
    elif isinstance(data_field, list) and len(data_field) > 0:
        first_heading = data_field[0] or {}
        label = first_heading.get('text', '')

    concept['label'] = label.split('|')[0].strip() if label else ''

    concept['id'] = viaf_id
    concept['pos'] = ''

    # Name type from VIAF (e.g., "Personal", "Corporate", etc.), fallback "Person"
    concept['concept_type'] = record_data.get('nameType', 'Person')

    # Build optional description (here it's just empty, but you could parse more)
    concept['description'] = ''
    concept['authority'] = {'name': 'VIAF'}

    return concept