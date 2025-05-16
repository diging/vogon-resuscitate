from django.conf import settings

from urllib.parse import urlparse

from concepts.models import *
from concepts.conceptpower import Conceptpower
from requests.auth import HTTPBasicAuth
import requests
import json

TYPES = settings.CONCEPT_TYPES


class ConceptLifecycleException(Exception):
    pass


class ConceptUpstreamException(Exception):
    pass


class ConceptData(object):
    """
    Container for raw data from Conceptpower.
    """
    def __init__(self, label=None, description=None, typed=None, uri=None,
                 pos='noun', equal_to=[]):
        self.label = label
        self.description = description
        self.typed = typed
        self.uri = uri
        self.pos=pos
        self.equal_to = equal_to


class ConceptLifecycle(object):
    """
    Shepherds :class:`.Concept` instances through their life cycle in VW.
    """

    CONCEPTPOWER = 'http://www.digitalhps.org/'
    VOGONWEB = 'http://vogonweb.net/'
    DEFAULT_TYPE = 'c7d0bec3-ea90-4cde-8698-3bb08c47d4f2'   # E1 Entity.
    DEFAULT_LIST = "Vogon"    # This seems kind of unneecessary, but oh well.

    def __init__(self, instance):
        assert isinstance(instance, Concept)
        self.conceptpower = Conceptpower(settings.CONCEPTPOWER_ENDPOINT, settings.CONCEPTPOWER_NAMESPACE)

        self.instance = instance
        self.user = settings.CONCEPTPOWER_USERID
        self.password = settings.CONCEPTPOWER_PASSWORD

    @staticmethod
    def get_namespace(uri):
        """
        Extract namespace from URI.
        """

        o = urlparse(uri)
        namespace = o.scheme + "://" + o.netloc + "/"

        if o.scheme == '' or o.netloc == '':
            return None
            # raise ConceptLifecycleException("Could not determine namespace for %s." % uri)

        return namespace

    def _get_namespace(self):
        return ConceptLifecycle.get_namespace(self.instance.uri)

    @property
    def is_native(self):
        """
        A native concept is one that exists in the Conceptpower namespace.
        """
        return self._get_namespace() == self.CONCEPTPOWER

    @property
    def is_created(self):
        return self._get_namespace() == self.VOGONWEB

    @property
    def is_external(self):
        return not (self.is_native or self.is_created)

    @property
    def default_state(self):
        """
        The state that a :class:`.Concept` should adopt upon instantiation
        depends on whether it is native, created, or external.
        """
        if self.is_native:
            return Concept.RESOLVED
        else:
            return Concept.PENDING

    @staticmethod
    def create(**params):
        """
        Create a new :class:`.Concept` instance, and return its
        :class:`.ConceptLifecycle` manager.
        """
        resolve = params.pop('resolve', True)
        if 'pos' not in params:
            params['pos'] = 'noun'
        concept = ConceptLifecycle(Concept(**params))
        concept.instance.concept_state = concept.default_state
        concept.instance.save()
        return concept

    @staticmethod
    def get_or_create(**params):
        try:
            return Concept.objects.get(uri=params.get('uri'))
        except Concept.DoesNotExist:
            return ConceptLifecycle.create(**params)

    @staticmethod
    def create_from_raw(data):
        # Helper for stripping or returning None if empty after strip
        def strip_if_str_else_none(val):
            if isinstance(val, str):
                stripped = val.strip()
                return stripped if stripped else None
            return None

        _type_data = data.get('type')
        _type_uri = None

        if isinstance(_type_data, str):
            _type_uri = strip_if_str_else_none(_type_data)
        elif isinstance(_type_data, dict):
            _type_uri = strip_if_str_else_none(_type_data.get('type_uri'))
        
        # Fallback to top-level 'type_uri' if not found in 'type' field or 'type' is not as expected
        if not _type_uri:
            _type_uri = strip_if_str_else_none(data.get('type_uri'))

        _typed = None
        if _type_uri:
            try:
                # Attempt to get or create the Type.
                _typed, _ = Type.objects.get_or_create(uri=_type_uri)
            except Exception: # Broad exception to catch issues like invalid URI format for Type model
                _typed = None # Or log an error, depending on desired behavior

        # URI processing
        uri_from_data = strip_if_str_else_none(data.get('uri'))
        concept_uri_from_data = strip_if_str_else_none(data.get('concept_uri'))
        processed_uri = uri_from_data if uri_from_data else concept_uri_from_data

        # Label processing
        label_from_word = strip_if_str_else_none(data.get('word'))
        label_from_lemma = strip_if_str_else_none(data.get('lemma'))
        processed_label = label_from_word if label_from_word else label_from_lemma
        
        processed_description = strip_if_str_else_none(data.get('description'))
        processed_pos = strip_if_str_else_none(data.get('pos'))

        # Authority processing - default to 'Conceptpower'
        authority_val = data.get('authority', 'Conceptpower')
        processed_authority = strip_if_str_else_none(authority_val)
        if not processed_authority: # If authority was empty string, None, or not a string
            processed_authority = 'Conceptpower'

        concept = ConceptLifecycle.create(
            uri=processed_uri,
            label=processed_label,
            description=processed_description,
            pos=processed_pos,
            typed=_typed,
            authority=processed_authority,
        )
        return concept

    def merge_with(self, uri):
        """
        Merge the managed :class:`.Concept` with some other concept.
        """
        if self.is_native:
            raise ConceptLifecycleException("Cannot merge a native concept")

        # We use the boilerplate try..except here to avoid making unneecessary
        #  API calls.
        try:
            target = Concept.objects.get(uri=uri)
        except Concept.DoesNotExist:
            try:
                data = self.get_concept(uri)
            except Exception as E:
                raise ConceptUpstreamException("Whoops: %s" % str(E))
            target = ConceptLifecycle.create_from_raw(data).instance

        self.instance.merged_with = target
        self.instance.concept_state = Concept.MERGED
        self.instance.save()

        # It may be the case that other concepts have been merged into these
        #  unresolved concepts. Therefore, we recursively collect all of
        #  these "child" concepts, and point them to the master concept.
        children_queryset = Concept.objects.filter(pk__in=self.instance.children)
        children_queryset.update(merged_with=target)

    def add(self):
        """
        Use data from the managed :class:`.Concept` instance to create a new
        native entry in Conceptpower.
        """
        if self.instance.concept_state == Concept.RESOLVED:
            raise ConceptLifecycleException("This concept is already resolved.")
        if self.instance.concept_state == Concept.MERGED:
            raise ConceptLifecycleException("This concept is merged, and cannot"
                                            " be resolved.")
        if self.is_native:
            raise ConceptLifecycleException("This concept already exists in"
                                            " Conceptpower, genius!")

        # If the managed Concept is external (e.g. from VIAF), we want to be
        #  sure to reference it in the new Conceptpower entry so that other
        #  users can benefit. Ideally this would happen with BlackGoat
        #  identities, but we have some  use-cases that depend on the
        #  equal_to field in Conceptpower.
        equal_uri = ""
        if self.is_external:
            equal_uri = self.instance.uri

        # It is possible that the managed Concept does not have a type, and
        #  sometimes we just don't care.
        concept_type = getattr(self.instance.typed, 'uri', self.DEFAULT_TYPE)
        if ConceptLifecycle.get_namespace(concept_type) != ConceptLifecycle.CONCEPTPOWER:
            concept_type = TYPES.get(concept_type)
        if not concept_type:
            raise ConceptLifecycleException("Cannot create a new concept"
                                            " without a valid Conceptpower"
                                            " type id.")

        pos = self.instance.pos
        if not pos:
            pos = 'noun'
        try:
            data = self.conceptpower.create(self.user, self.password,
                                            self.instance.label, pos,
                                            self.DEFAULT_LIST,
                                            self.instance.description,
                                            concept_type,
                                            equal_to=equal_uri)
        except Exception as E:
            raise ConceptUpstreamException("There was an error adding the"
                                           " concept to Conceptpower:"
                                           " %s" % str(E))
        if not self.is_created:
            target = ConceptLifecycle.create_from_raw(data).instance
            self.instance.merged_with = target
            self.instance.concept_state = Concept.MERGED
        else:
            self.instance.concept_state = Concept.RESOLVED
        self.instance.save()

    def get_similar(self):
        """
        Retrieve data about similar entries in Conceptpower.

        Returns
        -------
        list
            A list of dicts with raw data from Conceptpower.
        """
        import re, string
        from unidecode import unidecode
        equals = []
        if self.is_external:
            equals = self.get_equal()
        q = re.sub("[0-9]", "", unidecode(self.instance.label).translate(string.punctuation).lower())
        if not q:
            return []
        try:
            parameters = {
                'word': q,
                'pos': None,
            }
            headers = {
                    'Accept': 'application/json',
            }
            concepts = self.conceptpower.search(params=parameters, headers=headers)
        except Exception as E:
            raise ConceptUpstreamException("Whoops: %s" % str(E))
        return concepts if not equals else equals

    def get_equal(self):
        r"""
        Retrieve data about Conceptpower entries that are "equal to" the
        managed :class:`.Concept`\.

        Returns
        -------
        list
            A list of dicts with raw data from Conceptpower.
        """
        try:
            parameters = {
                'equal_to': self.instance.uri
            }
            headers = {
                'Accept': 'application/json',
            }
            concepts = self.conceptpower.search(params=parameters, headers=headers)
        except Exception as E:
            raise ConceptUpstreamException("Whoops: %s" % str(E))
        return list(concepts)   
    
    def get_matching(self):
        r"""
        Retrieve data about Conceptpower entries that are "equal to" the
        managed :class:`.Concept`\.

        Returns
        -------
        list
            A list containing a single ConceptData object if a match is found,
            otherwise an empty list.
        """
        try:
            data = self.get_concept(self.instance.uri)
        except Exception as E:
            # It might be more user-friendly to return an empty list on error
            # or let the specific exception propagate if that's desired.
            # For now, re-raising as per original behavior for upstream errors.
            raise ConceptUpstreamException("Whoops: %s" % str(E))

        if not data or not isinstance(data, dict):
            return []

        # Create ConceptData instance from the data dictionary
        _type_obj = None
        type_info = data.get('type')
        type_uri_str = None

        if isinstance(type_info, dict):
            type_uri_str = type_info.get('type_uri')
        elif isinstance(type_info, str):
            type_uri_str = type_info
        
        if type_uri_str:
            type_uri_str = type_uri_str.strip()
            if type_uri_str: # Ensure not empty after strip
                try:
                    _type_obj, _ = Type.objects.get_or_create(uri=type_uri_str)
                except Exception: # Catch any error during Type creation/retrieval
                    _type_obj = None
            else:
                _type_obj = None # type_uri_str was all whitespace

        # Helper for stripping or returning None if empty after strip
        def strip_if_str_else_none(val):
            if isinstance(val, str):
                stripped = val.strip()
                return stripped if stripped else None
            return None

        label = strip_if_str_else_none(data.get('lemma')) or strip_if_str_else_none(data.get('word'))
        uri = strip_if_str_else_none(data.get('concept_uri')) or strip_if_str_else_none(data.get('uri'))
        description = strip_if_str_else_none(data.get('description'))
        pos = strip_if_str_else_none(data.get('pos')) or 'noun' # Default pos if missing

        concept_data_instance = ConceptData(
            label=label,
            description=description,
            typed=_type_obj,
            uri=uri,
            pos=pos,
            # equal_to is not typically part of a single concept record from get_concept
        )
        return [concept_data_instance]

    def get_concept(self, uri):
        try:
            headers = {
                'Accept': 'application/json',
            }
            concept_entry = self.conceptpower.get(uri, headers=headers)
        except Exception as E:
            raise ConceptUpstreamException("Whoops: %s" % str(E))
        return concept_entry