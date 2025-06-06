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

from external_accounts.models import CitesphereAccount
from annotations.quadriga import submit_to_quadriga, generate_graph_data

import uuid

import requests
from django.conf import settings
from django.utils import timezone 

import json

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOGLEVEL)


# Set concept property constants for VIAF and ConceptPower utility functionsq
CONCEPT_POS = 'NOUN'
CONCEPT_AUTHORITY = {'name': 'VIAF'}
CONCEPT_STATE = 'Resolved'

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
    r"""
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
        user_id = data.get('createdBy')
        position = data.get('position')
        pos = data.get('pos')
        label = data.get('label')
        interpretation = data.get('interpretation')  # The old logic checks for this

        try:
            # Check if interpretation (a concept URI) was passed directly
            if isinstance(interpretation, str) and interpretation.startswith('http'):
                try:
                    concept = Concept.objects.get(uri=interpretation)
                    print(f"Concept found: {concept.id}", concept)
                except Concept.DoesNotExist:
                    # Special handling for VIAF URIs
                    if 'viaf.org' in interpretation:
                        concept = create_viaf_concept(interpretation, label, user_id)
                    else:
                        # Regular ConceptPower handling
                        concept_data = fetch_concept_data(interpretation, pos)
                        type_data = concept_data.get('concept_type')
                        type_instance = None
                        
                        # Handle concept type creation if necessary
                        if type_data:
                            type_instance = get_or_create_type(
                                type_data.get('type_uri'),
                                type_data.get('type_name'),
                                type_data.get('description', ''),
                                concept_data.get('authority', {})
                            )

                        # Create a new concept instance for ConceptPower
                        concept = ConceptLifecycle.create(
                            uri=interpretation,
                            label=label,
                            description=concept_data.get('description'),
                            typed=type_instance,
                            authority=concept_data.get('authority', {}),
                            createdBy=VogonUser.objects.get(id=user_id)
                        ).instance

                data['interpretation'] = concept.id
                print(f"Using concept id {concept.id} with pos: {concept.pos}")

            else:
                # If interpretation is not a URI, fetch concept based on label and pos
                try:
                    # Check if it's a numeric concept ID
                    concept_id = int(interpretation)
                    data['interpretation'] = concept_id
                    print(f"Using existing concept ID: {concept_id}")
                except (ValueError, TypeError):
                    # Otherwise create a new concept
                    new_uri = f"http://vogonweb.net/{uuid.uuid4()}"
                    concept = ConceptLifecycle.create(
                        uri=new_uri,
                        label=label,
                        description="",
                        pos='NOUN',  # Ensure POS is set
                        typed=None,
                        authority={'name': 'Vogon'},
                        createdBy=VogonUser.objects.get(id=user_id)
                    ).instance
                    
                    # Set the interpretation to the concept ID
                    data['interpretation'] = concept.id
                    print(f"Created new concept with ID: {concept.id}, pos: {concept.pos}")

        except ValueError as e:
            print(f"Error in create: {str(e)}")
            return Response({'error': str(e)}, status=400)
        except Exception as e:
            print(f"Unexpected error in create: {str(e)}")
            return Response({'error': str(e)}, status=500)

        print(f"Final data object: {data}")
        
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
        result_data = reserializer.data
        
        # Add the pos field to the interpretation if it's missing
        if 'interpretation' in result_data and result_data['interpretation'] and 'pos' not in result_data['interpretation']:
            concept_id = result_data['interpretation'].get('id')
            try:
                concept = Concept.objects.get(id=concept_id)
                result_data['interpretation']['pos'] = concept.pos or 'NOUN'
            except Concept.DoesNotExist:
                result_data['interpretation']['pos'] = 'NOUN'
                
        print(f"Final response data: {result_data}")

        headers = self.get_success_headers(serializer.data)
        return Response(result_data, status=status.HTTP_201_CREATED, headers=headers)

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

        # Perform readiness checks only for fetched RelationSets
        for relationset in queryset:
            relationset.update_status()

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

        user = request.user
        quadruple_id = request.data.get('pk')
        
        project_id = request.data.get('project_id')
        project = TextCollection.objects.get(pk=project_id)
        
        try:
            relationset = RelationSet.objects.get(pk=quadruple_id)

        except RelationSet.DoesNotExist:
            return Response({'error': 'RelationSet not found.'}, status=status.HTTP_404_NOT_FOUND)

        if relationset.createdBy != user:
            return Response({'error': 'You are not authorized to submit this RelationSet.'},
                            status=status.HTTP_403_FORBIDDEN)

        if relationset.status != RelationSet.STATUS_READY_TO_SUBMIT:
            return Response({'error': 'Quadruple(s) is not ready to submit.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if relationset.submitted:
            return Response({'error': 'Quadruple(s) has already been submitted.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not project.quadriga_id:
            return Response({'error': 'Project does not have a Quadriga ID configured. Please configure a Quadriga ID in the project settings.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            submit_to_quadriga(relationset, user, project)
            return Response({'success': 'Quadruples submitted successfully.'}, status=status.HTTP_200_OK)

        except CitesphereAccount.DoesNotExist:
            return Response({'error': 'No Citesphere account found.'},
                            status=status.HTTP_400_BAD_REQUEST)
        except requests.RequestException as e:
            logger.error("ERROR %s", e)
            return Response({'error': 'Internal Server Error Occured. Please try again later!'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RelationViewSet(viewsets.ModelViewSet):
    queryset = Relation.objects.all()
    serializer_class = RelationSerializer
    permission_classes = (ProjectOwnerOrCollaboratorAccessOrReadOnly, )

    def get_queryset(self, *args, **kwargs):
        r"""
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
        r"""
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
        results = []
        
        # Search ConceptPower
        cp_results = search_conceptpower(q, pos)
        results.extend(cp_results)
        
        # Search VIAF
        viaf_results = search_viaf(q)
        results.extend(viaf_results)
        
        return Response({'results': results})


    @action(detail=False)
    def search_paginated(self, request, **kwargs):
        """
        A paginated version of the concept search endpoint.
        First tries the full query, then individual parts if less than 10 results.
        """
        q = request.GET.get('search', None)
        if not q:
            return Response({'results': []})
            
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        pos = request.GET.get('pos', None)
        
        filtered_words = [word for word in q.split() if len(word) > 3]
        all_concepts = []
        seen_uris = set()
        
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
                for concept_entry in data.get('conceptEntries', []):
                    concept = parse_concept(concept_entry)
                    concept = _relabel(concept)
                    if concept['uri'] not in seen_uris:
                        seen_uris.add(concept['uri'])
                        all_concepts.append(concept)
            else:
                error_msg = 'ConceptPower service is currently unavailable. Please try again later.'
                return Response({'error': error_msg}, status=response.status_code)
        except Exception as e:
            logger.error(f'Error searching concepts: {str(e)}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        if len(all_concepts) < per_page:
            for word in filtered_words:
                try:
                    parameters['word'] = word
                    response = requests.get(url, headers=headers, params=parameters)
                    
                    if response.status_code == 200:
                        data = response.json()
                        for concept_entry in data.get('conceptEntries', []):
                            concept = parse_concept(concept_entry)
                            concept = _relabel(concept)
                            if concept['uri'] not in seen_uris:
                                seen_uris.add(concept['uri'])
                                all_concepts.append(concept)
                    else:
                        error_msg = 'ConceptPower service is currently unavailable. Please try again later.'
                        return Response({'error': error_msg}, status=response.status_code)
                except Exception as e:
                    logger.error(f'Error searching concepts for word "{word}": {str(e)}')
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        total_concepts = len(all_concepts)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        paginated_concepts = all_concepts[start_idx:end_idx]
        
        return Response({
            'results': paginated_concepts,
            'has_more': end_idx < total_concepts,
            'total': total_concepts,
            'page': page,
            'per_page': per_page
        })

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

# Utility functions
def get_or_create_type(type_uri, type_label, type_description, authority=None):
    """
    Get an existing Type or create a new one
    
    Parameters:
    -----------
    type_uri : str
        The URI of the type
    type_label : str
        The label of the type
    type_description : str
        The description of the type
    authority : dict, optional
        Authority information
        
    Returns:
    --------
    Type
        The retrieved or created Type instance
    """
    try:
        return Type.objects.get(uri=type_uri)
    except Type.DoesNotExist:
        return Type.objects.create(
            uri=type_uri,
            label=type_label,
            description=type_description,
            authority=authority or {},
        )

def create_viaf_concept(viaf_uri, label, user_id):
    """
    Create a new Concept from a VIAF URI
    
    Parameters:
    -----------
    viaf_uri : str
        The VIAF URI
    label : str
        The label for the concept
    user_id : int
        The ID of the user creating the concept
        
    Returns:
    --------
    Concept
        The created Concept instance
    """
    viaf_id = viaf_uri.split('/')[-1]
    
    # Get VIAF description from search results
    viaf_description = ""
    try:
        viaf_api = ViafAPI()
        viaf_info = viaf_api.get_record(viaf_id)
        if viaf_info:
            viaf_description = label  # Use label as fallback
            
            if hasattr(viaf_info, 'titles') and viaf_info.titles:
                viaf_description = viaf_info.titles[0]
            elif hasattr(viaf_info, 'namedetails') and viaf_info.namedetails:
                viaf_description = str(viaf_info.namedetails)
    except Exception as e:
        logger.error(f"Error getting VIAF description: {e}")
        viaf_description = label

    # Create the VIAF concept directly
    concept = Concept.objects.create(
        uri=viaf_uri,
        label=label,
        description=viaf_description,
        typed=None,  # No type needed
        concept_state=CONCEPT_STATE,
        pos=CONCEPT_POS,
        authority=CONCEPT_AUTHORITY,
        createdBy_id=user_id
    )
    
    # Force reload to ensure all fields are set
    concept.refresh_from_db()
    
    return concept

def process_viaf_search_result(viaf_api, entry):
    """
    Process a VIAF search result entry into the expected format
    
    Parameters:
    -----------
    viaf_api : ViafAPI
        The VIAF API instance
    entry : dict
        The VIAF entry to process
        
    Returns:
    --------
    dict
        Processed VIAF entry in the format expected by the UI
    """
    # Convert to the format expected by the UI
    viaf_result = {
        'uri': viaf_api.uri_from_id(entry['viafid']),
        'label': entry['displayForm'],
        'description': f"{entry.get('displayForm', '')} - {entry.get('nametype', 'Person')}",
        'type': 'VIAF',
        'pos': CONCEPT_POS,
        'authority': {
            'name': 'VIAF',
            'uri': viaf_api.uri_from_id(entry['viafid'])
        }
    }
    
    # Add dates to description if available
    if 'dateOfBirth' in entry or 'dateOfDeath' in entry:
        birth = entry.get('dateOfBirth', '')
        death = entry.get('dateOfDeath', '')
        if birth or death:
            date_info = f" ({birth}-{death})"
            viaf_result['description'] += date_info
    
    return viaf_result

def search_conceptpower(query, pos=None):
    """
    Search ConceptPower for concepts
    
    Parameters:
    -----------
    query : str
        The search query
    pos : str, optional
        Part of speech to filter by
        
    Returns:
    --------
    list
        List of concept results
    """
    results = []
    
    conceptpower_url = f"{settings.CONCEPTPOWER_ENDPOINT}ConceptSearch"
    conceptpower_params = {
        'word': query,
        'pos': pos if pos else None,
    }
    headers = {
        'Accept': 'application/json',
        "Cache-Control": "no-cache",
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        conceptpower_response = requests.get(conceptpower_url, headers=headers, params=conceptpower_params)
        
        if conceptpower_response.status_code == 200:
            data = conceptpower_response.json()
            for concept_entry in data.get('conceptEntries', []):
                try:
                    concept = parse_concept(concept_entry)
                    concept = _relabel(concept)
                    results.append(concept)
                except Exception as e:
                    # Skip entries that fail to parse
                    continue
    except Exception as e:
        logger.error(f'Error searching ConceptPower: {str(e)}')
    
    return results

def search_viaf(query):
    """
    Search VIAF for entities
    
    Parameters:
    -----------
    query : str
        The search query
        
    Returns:
    --------
    list
        List of VIAF results
    """
    results = []
    viaf_api = ViafAPI()
    
    try:
        # Get suggestions from VIAF API
        viaf_results = viaf_api.suggest(query)
        
        if viaf_results:
            for entry in viaf_results:
                try:
                    result = process_viaf_search_result(viaf_api, entry)
                    results.append(result)
                except Exception as e:
                    # Skip entries that fail to process
                    continue
    except Exception as e:
        logger.error(f'Error searching VIAF: {str(e)}')
    
    return results
