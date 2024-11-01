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
from annotations.utils import generate_graph_data
from concepts.models import Concept, Type
from concepts.lifecycle import *

from external_accounts.models import CitesphereAccount

import uuid
import xml.etree.ElementTree as ET

import requests
from django.conf import settings
from django.utils import timezone 

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOGLEVEL)



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
    permission_classes = (IsAuthenticatedOrReadOnly, )

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

        # raise AttributeError('asdf')
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
    permission_classes = (IsAuthenticatedOrReadOnly, )
    serializer_classes = {
        'GET': AppellationSerializer,
        'POST': AppellationPOSTSerializer
    }
    # pagination_class = LimitOffsetPagination

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
                    concept_data = fetch_concept_data(label, pos)
                    type_data = concept_data.get('concept_type')
                    type_instance = None
                    
                    # Handle concept type creation if necessary
                    if type_data:
                        try:
                            type_instance = Type.objects.get(uri=type_data.get('identifier'))
                        except Type.DoesNotExist:
                            # Create a new Type instance if it doesn't exist
                            type_instance = Type.objects.create(
                                uri=type_data.get('identifier'),
                                label=label,
                                description=type_data.get('description'),
                                authority=concept_data.data.get('authority', {}),
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

    # TODO: implement some real filters!
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
    permission_classes = (IsAuthenticatedOrReadOnly, )


from django.forms.models import model_to_dict

class RelationSetViewSet(viewsets.ModelViewSet):
    queryset = RelationSet.objects.all()
    serializer_class = RelationSetSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )

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
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_name='submit')
    def submit(self, request):

        print(request.data)

        user = request.user
        pk = request.data.get('pk')

        try:
            relationset = RelationSet.objects.get(pk=pk)
            print(model_to_dict(relationset))

        except RelationSet.DoesNotExist:
            return Response({'error': 'RelationSet not found.'}, status=status.HTTP_404_NOT_FOUND)

        if relationset.createdBy != user:
            return Response({'error': 'You are not authorized to submit this RelationSet.'},
                            status=status.HTTP_403_FORBIDDEN)

        if relationset.status != 'ready_to_submit':
            return Response({'error': 'RelationSet is not ready to submit.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if relationset.submitted:
            return Response({'error': 'RelationSet has already been submitted.'},
                            status=status.HTTP_400_BAD_REQUEST)


        try:
            citesphere_account = CitesphereAccount.objects.get(user=user, repository=relationset.occursIn.repository)
            access_token = citesphere_account.access_token

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }

            collection_id = settings.QUADRIGA_COLLECTION_ID
            endpoint = f"{settings.QUADRIGA_ENDPOINT}/api/v1/collection/{collection_id}/network/add/"

            graph_data = generate_graph_data(relationset, user)
            print(graph_data)

            response = requests.post(endpoint, json=graph_data, headers=headers)
            response.raise_for_status()

            # Update the status of the RelationSet
            relationset.status = 'submitted'
            relationset.submitted = True
            relationset.submittedOn = timezone.now()
            relationset.save()

            return Response({'success': 'Quadruples submitted successfully.'}, status=status.HTTP_200_OK)

        except CitesphereAccount.DoesNotExist:
            return Response({'error': 'No Citesphere account found.'},
                            status=status.HTTP_400_BAD_REQUEST)
        except requests.RequestException as e:
            return Response({'error': 'Failed to submit quadruples.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RelationViewSet(viewsets.ModelViewSet):
    queryset = Relation.objects.all()
    serializer_class = RelationSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )

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
        url = f"{settings.CONCEPTPOWER_ENDPOINT}ConceptLookup/{q}/{pos if pos else ''}"
        response = requests.get(url, auth=(settings.CONCEPTPOWER_USERID, settings.CONCEPTPOWER_PASSWORD))
        if response.status_code == 200:
            try:
                # Parse the XML response
                root = ET.fromstring(response.content)
                # Define the namespaces used in the XML
                ns = {
                    'madsrdf': 'http://www.loc.gov/mads/rdf/v1#',
                    'schema': 'http://schema.org/',
                    'skos': 'http://www.w3.org/2004/02/skos/core#',
                    'owl': 'http://www.w3.org/2002/07/owl#',
                    'dcterms': 'http://purl.org/dc/terms/',
                    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
                }
                concepts = []
                for concept_entry in root.findall('.//madsrdf:Authority', ns) + root.findall('.//skos:Concept', ns):
                    concept = {}
                    # Extract the rdf:about attribute as the 'uri'
                    concept['uri'] = concept_entry.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
                    # Extract the 'name'
                    name_elem = concept_entry.find('schema:name', ns)
                    if name_elem is not None:
                        concept['label'] = name_elem.text.strip()
                    else:
                        # Fallback to 'madsrdf:authoritativeLabel' or 'skos:prefLabel'
                        label_elem = concept_entry.find('madsrdf:authoritativeLabel', ns) or concept_entry.find('skos:prefLabel', ns)
                        if label_elem is not None:
                            concept['label'] = label_elem.text.strip()
                    # Extract 'description'
                    desc_elem = concept_entry.find('schema:description', ns)
                    if desc_elem is not None:
                        concept['description'] = desc_elem.text.strip()
                    # Extract 'id' from 'dcterms:identifiers'
                    id_elem = concept_entry.find('dcterms:identifiers', ns)
                    if id_elem is not None:
                        concept['id'] = id_elem.text.strip()
                    # Extract 'pos' from the id if possible
                    if 'id' in concept:
                        parts = concept['id'].split('-')
                        if len(parts) > 2:
                            concept['pos'] = parts[2]
                    # Extract 'authority'
                    authority_elem = concept_entry.find('madsrdf:isMemberOfMADSCollection', ns)
                    if authority_elem is not None:
                        authority_uri = authority_elem.text.strip()
                        # Map the authority URI to a name
                        if 'wordnet' in authority_uri.lower():
                            concept['authority'] = {'name': 'WordNet'}
                        else:
                            concept['authority'] = {'name': authority_uri}
                    else:
                        concept['authority'] = {'name': 'Unknown'}
                    # Now relabel the fields
                    concept = _relabel(concept)
                    concepts.append(concept)
                return Response({'results': concepts})
            except Exception as e:
                return Response({'error': f'Error parsing ConceptPower response: {str(e)}'}, status=400)
        else:
            return Response({'error': 'Error fetching concepts from ConceptPower'}, status=response.status_code)


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


def fetch_concept_data(label, pos=None):
    """
    Fetch concept data from ConceptPower based on the given URI (unique identifier) and part of speech (pos).
    Returns the concept data in a suitable format for the create function.
    """

    if pos is 'N':
        pos = 'noun'
    elif pos is 'V':
        pos = 'verb'
    else:
        pos = None

    url = f"{settings.CONCEPTPOWER_ENDPOINT}ConceptLookup/{label}/{pos}"
    response = requests.get(url, auth=(settings.CONCEPTPOWER_USERID, settings.CONCEPTPOWER_PASSWORD))

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.content)
            namespace = {
                'madsrdf': 'http://www.loc.gov/mads/rdf/v1#',
                'schema': 'http://schema.org/',
                'skos': 'http://www.w3.org/2004/02/skos/core#',
                'owl': 'http://www.w3.org/2002/07/owl#',
                'dcterms': 'http://purl.org/dc/terms/',
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
            }
            concept_entry = root.find('.//madsrdf:Authority', namespace) or root.find('.//skos:Concept', namespace)

            if concept_entry is not None:
                concept = {}

                # Extract fields
                concept['uri'] = concept_entry.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')

                # Extract name
                name_elem = concept_entry.find('schema:name', namespace) or \
                            concept_entry.find('madsrdf:authoritativeLabel', namespace) or \
                            concept_entry.find('skos:prefLabel', namespace)
                if name_elem is not None:
                    concept['label'] = name_elem.text.strip()
                else:
                    concept['label'] = " "

                # Extract description
                desc_elem = concept_entry.find('schema:description', namespace)
                if desc_elem is not None:
                    concept['description'] = desc_elem.text.strip()

                # Extract authority
                authority_elem = concept_entry.find('madsrdf:isMemberOfMADSCollection', namespace)
                if authority_elem is not None:
                    concept['authority'] = authority_elem.text.strip()

                # Extract pos (if available)
                pos_elem = concept_entry.find('skos:note', namespace)
                if pos_elem is not None:
                    concept['concept_type'] = pos_elem.text.strip()

                return concept

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