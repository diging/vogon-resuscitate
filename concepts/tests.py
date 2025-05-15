from django.test import TestCase
from django.db.models.signals import post_save
from concepts.authorities import resolve, search
from concepts.models import Concept, Type
from concepts.signals import concept_post_save_receiver
import mock, json
from concepts.lifecycle import *
from unittest.mock import patch
import uuid


class MockResponse(object):
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code

    def json(self):
        return json.loads(self.content)


def disconnect_signal(signal, receiver, sender):
    disconnect = getattr(signal, 'disconnect')
    disconnect(receiver, sender)


def reconnect_signal(signal, receiver, sender):
    connect = getattr(signal, 'connect')
    connect(receiver, sender=sender)


class TestConceptLifeCycle(TestCase):
    """
    Tests the :class:`.ConceptLifecycle` manager.

    We're not creating new :class:`.Concept`\\s at this point, just getting
    them from Conceptpower. So this is an important distinction from the
    :class:`.TestConcept` tests.
    """
    maxDiff = None

    def setUp(self):
        disconnect_signal(post_save, concept_post_save_receiver, Concept)
        # Mock the conceptpower namespace to fix XML parsing issues
        self.namespace_patcher = mock.patch('concepts.lifecycle.settings')
        self.mock_settings = self.namespace_patcher.start()
        self.mock_settings.CONCEPTPOWER_ENDPOINT = 'http://chps.asu.edu/conceptpower/rest/'
        self.mock_settings.CONCEPTPOWER_NAMESPACE = '{http://www.digitalhps.org/}'

    def test_is_native(self):
        """
        A :class:`.ConceptLifecycle` should know if its constituent is from
        Conceptpower or not.
        """

        instance = Concept.objects.create(
            label = "Test",
            uri = "http://asdf.com/test",
        )
        manager = ConceptLifecycle(instance)
        self.assertFalse(manager.is_native)    # A dynamic property!

        instance = Concept.objects.create(
            label = "test_concept",
            uri = "http://www.digitalhps.org/concepts/WID-02416519-N-01-test_concept",
        )
        manager = ConceptLifecycle(instance)
        self.assertTrue(manager.is_native)    # A dynamic property!

    def test_is_created(self):
        """
        A :class:`.ConceptLifecycle` should know if its constituent was created
        by a user or not.
        """
        instance = Concept.objects.create(
            label = "User created nonsense",
            uri = "http://vogonweb.net/12345",
        )
        manager = ConceptLifecycle(instance)
        self.assertTrue(manager.is_created)

        instance = Concept.objects.create(
            label = "test_concept",
            uri = "http://www.digitalhps.org/concepts/WID-02416519-N-01-test_concept",
        )
        manager = ConceptLifecycle(instance)
        self.assertFalse(manager.is_created)

    def test_native_default_state(self):
        """
        Native concepts (from Conceptpower) should be resolved immediately.
        """
        instance = Concept.objects.create(
            label = "test_concept",
            uri = "http://www.digitalhps.org/concepts/WID-02416519-N-01-test_concept",
        )
        manager = ConceptLifecycle(instance)
        self.assertEqual(manager.default_state, Concept.RESOLVED)

    def test_external_default_state(self):
        """
        Non-native external concepts (from other external authorities) should be
        set to PENDING by default.
        """
        manager = ConceptLifecycle(Concept(
            uri = 'http://viaf.org/viaf/12345',
            label = 'Test',
            typed = Type.objects.get_or_create(uri='viaf:personal')[0]
        ))
        self.assertEqual(manager.default_state, Concept.PENDING)

    def test_user_created_default_state(self):
        """
        User-created concepts should be PENDING by default; they require admin
        review.
        """
        instance = Concept.objects.create(
            label = "Test",
            uri = "http://vogonweb.net/12345",
        )
        manager = ConceptLifecycle(instance)
        self.assertEqual(manager.default_state, Concept.PENDING)

    @patch('requests.get')
    def test_get_similar_suggestions(self, mock_get):
        """
        The :class:`.ConceptLifecycle` should handle retrieving suggestions.

        We're not creating new :class:`.Concept`\\s at this point, just getting
        data.
        """
        # This is the data that will be returned by Conceptpower.search().
        mock_data = [{
            "label": "Bradshaw 1965",
            "id": "CON76832db2-7abb-4c77-b08e-239017b6a585",
            "pos": "noun",
            "type": {
                "type_id": "94d05eb7-bcee-4f4b-b18e-819dd1ffb20a",
                "type_uri": "http://www.digitalhps.org/types/TYPE_94d05eb7-bcee-4f4b-b18e-819dd1ffb20a",
                "type_name": "E28 Conceptual Object"
            },
            "conceptList": "Publications",
            "uri": "http://www.digitalhps.org/concepts/CON76832db2-7abb-4c77-b08e-239017b6a585",
            "description": "Bradshaw, Anthony David. 1965. \"The evolutionary significance of phenotypic plasticity in plants.\" Advances in Genetics 13: 115-155."
        }]
        mock_get.return_value = MockResponse(json.dumps(mock_data))

        concept = Concept.objects.create(
            uri = 'http://vogonweb.net/' + uuid.uuid4().hex,
            label = 'Test',
            typed = Type.objects.get_or_create(uri='http://example.com/type')[0]
        )
        manager = ConceptLifecycle(concept)
        suggestions = manager.get_similar()

        self.assertEqual(len(suggestions), 1)
        self.assertIsInstance(suggestions[0], dict)  # Expect a dict, not ConceptData
        self.assertEqual(suggestions[0]['label'], "Bradshaw 1965")
        self.assertEqual(suggestions[0]['id'], "CON76832db2-7abb-4c77-b08e-239017b6a585")

    @mock.patch("requests.get")
    def test_get_matching_suggestions(self, mock_get):
        """
        The :class:`.ConceptLifecycle` should handle retrieving matching
        concepts. A matching concepts is a Conceptpower concept that wraps
        (via the equal_to field) an external concept (e.g. a VIAF entry).
        """

        instance = Concept.objects.create(
            label = "Test",
            uri = "http://viaf.org/viaf/12345",
        )
        manager = ConceptLifecycle(instance)

        mock_get.return_value = MockResponse(json.dumps({
            "conceptEntries": [{
                "id": "CON76832db2-7abb-4c77-b08e-239017b6a585",
                "lemma": "Bradshaw 1965",
                "pos": "noun",
                "description": "Bradshaw, Anthony David. 1965. \"The evolutionary significance of phenotypic plasticity in plants.\" Advances in Genetics 13: 115-155.",
                "conceptList": "Publications",
                "type": {"type_id": "94d05eb7-bcee-4f4b-b18e-819dd1ffb20a", "type_uri": "http://www.digitalhps.org/types/TYPE_94d05eb7-bcee-4f4b-b18e-819dd1ffb20a", "type_name": "E28 Conceptual Object"},
                "concept_uri": "http://www.digitalhps.org/concepts/CON76832db2-7abb-4c77-b08e-239017b6a585"
                # Add other fields 'word', etc. if needed by how the result is processed further,
                # though get_matching just returns the list of ConceptData objects.
                # The ConceptData object is initialized from the parsed concept.
            }]
        }))
        
        matches = manager.get_matching()
        self.assertIsInstance(matches, list)
        self.assertEqual(len(matches), 1)
        self.assertIsInstance(matches[0], ConceptData)
        self.assertEqual(matches[0].label, 'Bradshaw 1965')
        self.assertEqual(matches[0].uri, 'http://www.digitalhps.org/concepts/CON76832db2-7abb-4c77-b08e-239017b6a585')

    def test_create(self):
        """
        The :class:`.ConceptLifecycle` can create new :class:`.Concept`
        instances.
        """

        manager = ConceptLifecycle.create(
            label = "test_concept",
            uri = "http://www.digitalhps.org/concepts/WID-02416519-N-01-test_concept"
        )
        self.assertIsInstance(manager, ConceptLifecycle)
        self.assertIsInstance(manager.instance, Concept)
        self.assertEqual(manager.instance.label, "test_concept")
        self.assertEqual(manager.instance.uri, "http://www.digitalhps.org/concepts/WID-02416519-N-01-test_concept")

    def test_cannot_merge_resolved_concepts(self):
        """
        If a :class:`.Concept` is resolved, it can't be merged with any other
        concepts.
        """
        manager = ConceptLifecycle.create(
            label = "test_concept",
            uri = "http://www.digitalhps.org/concepts/WID-02416519-N-01-test_concept"
        )

        with self.assertRaises(ConceptLifecycleException):
            manager.merge_with('http://www.digitalhps.org/concepts/WID-02416519-N-02-test_concept')

    @patch('requests.get')
    def test_merge_with_conceptpower(self, mock_get):
        """
        A non-native :class:`.Concept` can be merged with an existing native
        :class:`.Concept`.
        """
        # This is the data that will be returned by Conceptpower.get().
        mock_response_data = {
            "uri": "http://www.digitalhps.org/concepts/CON76832db2-7abb-4c77-b08e-239017b6a585",
            "word": "Bradshaw 1965",
            "lemma": "Bradshaw 1965",
            "pos": "noun",
            "description": "Bradshaw, Anthony David. 1965. \"The evolutionary significance of phenotypic plasticity in plants.\" Advances in Genetics 13: 115-155.",
            "type": {
                "type_id": "94d05eb7-bcee-4f4b-b18e-819dd1ffb20a",
                "type_uri": "http://www.digitalhps.org/types/TYPE_94d05eb7-bcee-4f4b-b18e-819dd1ffb20a",
                "type_name": "E28 Conceptual Object"
            },
            "conceptList": "Publications",
            "id": "CON76832db2-7abb-4c77-b08e-239017b6a585"
        }
        mock_get.return_value = MockResponse(json.dumps(mock_response_data))

        manager = ConceptLifecycle.create(
            uri = 'http://vogonweb.net/concept/12345',
            label = 'My Test Concept',
            typed = Type.objects.get_or_create(uri='http://example.com/type')[0]
        )
        manager.merge_with('http://www.digitalhps.org/concepts/CON76832db2-7abb-4c77-b08e-239017b6a585')

        instance = manager.instance
        self.assertEqual(instance.concept_state, Concept.MERGED)
        self.assertIsNotNone(instance.merged_with)
        self.assertEqual(instance.merged_with.uri, 'http://www.digitalhps.org/concepts/CON76832db2-7abb-4c77-b08e-239017b6a585')

    @patch('requests.post')
    def test_add(self, mock_post):
        r"""
        When a non-native, non-Conceptpower :class:`.Concept` is "added" to Conceptpower, a new
        native :class:`.Concept` is created (representing the Conceptpower entry),
        and the original :class:`.Concept` has its ``concept_state`` set to ``MERGED``,
        pointing to the new native :class:`.Concept`.
        """
        # Configure the mock response for a successful POST request
        mock_post.return_value = MockResponse({
            "uri": "http://www.digitalhps.org/concepts/CONkLHTIeUQqM7m", # Native Conceptpower URI
            "word": "kitty_cp",
            "lemma": "kitty_cp",
            "pos": "noun",
            "description": "Soft kitty in Conceptpower.",
            "type": {"type_id": "0d5d1992-957b-49b6-ad7d-117daaf28108"},
            "conceptList": "TestList",
            "id": "CONkLHTIeUQqM7m"
        })

        manager = ConceptLifecycle.create(
            label="kitty",
            description="Soft kitty, sleepy kitty, little ball of fur.",
            uri="http://some.external.authority/concept/original_kitty",  # External, non-VogonWeb, non-Conceptpower URI
            typed=Type.objects.get_or_create(uri='http://example.com/type')[0],
            resolve=False
        )
        concept = manager.instance
        self.assertEqual(concept.concept_state, Concept.PENDING) # Initial state for external

        manager.add()
        concept.refresh_from_db() # Important to get updated state and merged_with

        self.assertEqual(concept.concept_state, Concept.MERGED)
        self.assertIsNotNone(concept.merged_with)
        self.assertIsInstance(concept.merged_with, Concept)
        self.assertEqual(concept.merged_with.uri, "http://www.digitalhps.org/concepts/CONkLHTIeUQqM7m")
        self.assertEqual(concept.merged_with.label, "kitty_cp")
        self.assertEqual(concept.merged_with.concept_state, Concept.RESOLVED) # The new native concept is resolved

    @patch('requests.post')
    def test_add_wrapper(self, mock_post):
        r"""
        For non-created :class:`.Concept`\\s, the only difference is that the
        original :class:`.Concept` is updated directly.
        """
        mock_post.return_value = MockResponse({
            "uri": "http://example.com/new_concept",
            "label": "New Concept",
            "description": "A new concept",
            "pos": "noun",
            "conceptlist": "Persons",
            "type": "0d5d1992-957b-49b6-ad7d-117daaf28108",
            "word": "new_concept",
            "equal_to": "http://viaf.org/viaf/12345",
        })

        manager = ConceptLifecycle.create(
            label="kitty2",
            description="Soft kitty, sleepy kitty, little ball of fur.",
            uri="http://viaf.org/viaf/12345",  # External URI
            resolve=False
        )
        concept = manager.instance
        manager.add()  # This should update the existing concept

        # Retrieve the potentially updated concept
        updated_concept = Concept.objects.get(uri="http://viaf.org/viaf/12345")

        self.assertEqual(updated_concept.concept_state, Concept.RESOLVED)
        # Since it's an update in place for non-created, merged_with should not be set.
        self.assertIsNone(updated_concept.merged_with)
        # The URI should remain the original external URI
        self.assertEqual(updated_concept.uri, "http://viaf.org/viaf/12345")

    def tearDown(self):
        Concept.objects.all().delete()
        Type.objects.all().delete()
        reconnect_signal(post_save, concept_post_save_receiver, Concept)
        self.namespace_patcher.stop()
