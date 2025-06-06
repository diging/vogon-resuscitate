import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from unittest import mock
from django.http import HttpResponse
from django.contrib.contenttypes.models import ContentType

from annotations.models import VogonUser
from annotations.serializers import (
    UserSerializer,
    RemoteCollectionSerializer,
    RemoteResourceSerializer,
    RepositorySerializer,
    RelationSerializer,
    DocumentPositionSerializer,
    DateAppellationSerializer,
    TextSerializer,
    AppellationSerializer,
    AppellationPOSTSerializer,
    RelationSetSerializer,
    TemporalBoundsSerializer,
    TextCollectionSerializer,
    TemplatePartSerializer,
    TemplateSerializer
)
from annotations.models import (
    Repository,
    Relation,
    DocumentPosition,
    DateAppellation,
    Text,
    Appellation,
    RelationSet,
    TemporalBounds,
    TextCollection,
    RelationTemplate,
    RelationTemplatePart
)
from concepts.models import Concept, Type
from annotations.tasks import tokenize, retrieve


class UserSerializerTest(TestCase):
    def setUp(self):
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'affiliation': 'Test University',
            'location': 'Test City',
            'full_name': 'Test User',
            'link': 'https://example.com/testuser',
        }
        self.user = VogonUser.objects.create(**self.user_data)
        self.serializer = UserSerializer(instance=self.user)

    def test_user_serializer_contains_expected_fields(self):
        """Test that UserSerializer contains the expected fields."""
        data = self.serializer.data
        self.assertEqual(set(data.keys()), {'username', 'email', 'id', 'affiliation', 'location', 'full_name', 'link'})
        
    def test_user_serializer_content(self):
        """Test that UserSerializer serializes a user correctly."""
        data = self.serializer.data
        self.assertEqual(data['username'], self.user_data['username'])
        self.assertEqual(data['email'], self.user_data['email'])
        self.assertEqual(data['affiliation'], self.user_data['affiliation'])
        self.assertEqual(data['location'], self.user_data['location'])
        self.assertEqual(data['full_name'], self.user_data['full_name'])
        self.assertEqual(data['link'], self.user_data['link'])


class RemoteCollectionSerializerTest(TestCase):
    def test_valid_data(self):
        """Test that RemoteCollectionSerializer validates and deserializes valid data correctly."""
        data = {
            'source': 1,
            'id_or_uri': 'test-uri',
            'name': 'Test Collection'
        }
        serializer = RemoteCollectionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['source'], data['source'])
        self.assertEqual(serializer.validated_data['id_or_uri'], data['id_or_uri'])
        self.assertEqual(serializer.validated_data['name'], data['name'])
    
    def test_invalid_data(self):
        """Test that RemoteCollectionSerializer validates invalid data correctly."""
        # Missing required field
        data = {
            'source': 1,
            'id_or_uri': 'test-uri'
            # Missing 'name'
        }
        serializer = RemoteCollectionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        
        # Invalid data type
        data = {
            'source': 'not-an-integer',  # Should be an integer
            'id_or_uri': 'test-uri',
            'name': 'Test Collection'
        }
        serializer = RemoteCollectionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('source', serializer.errors)


class RemoteResourceSerializerTest(TestCase):
    def test_valid_data(self):
        """Test that RemoteResourceSerializer validates and deserializes valid data correctly."""
        data = {
            'source': 1,
            'id_or_uri': 'test-uri',
            'title': 'Test Resource'
        }
        serializer = RemoteResourceSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['source'], data['source'])
        self.assertEqual(serializer.validated_data['id_or_uri'], data['id_or_uri'])
        self.assertEqual(serializer.validated_data['title'], data['title'])


class RepositorySerializerTest(TestCase):
    def setUp(self):
        self.repo_data = {
            'name': 'Test Repository',
            'manager': 'JARSManager',
            'endpoint': 'https://example.com/repo',
            'oauth_client_id': 'test-client-id',
            'oauth_secret_key': 'test-secret-key',
        }
        self.repository = Repository.objects.create(**self.repo_data)
        self.serializer = RepositorySerializer(instance=self.repository)
    
    def test_repository_serializer(self):
        """Test that RepositorySerializer serializes a Repository correctly."""
        data = self.serializer.data
        self.assertEqual(data['name'], self.repo_data['name'])
        self.assertEqual(data['endpoint'], self.repo_data['endpoint'])


class RelationSerializerTest(TestCase):
    def setUp(self):
        self.user = VogonUser.objects.create(
            username='testuser',
            email='test@example.com'
        )
        
        self.repository = Repository.objects.create(
            name='Test Repository',
            manager='JARSManager',
            endpoint='https://example.com',
            oauth_client_id='test-client-id',
            oauth_secret_key='test-secret-key'
        )
        
        self.text = Text.objects.create(
            uri='https://example.com/test',
            title='Test Text',
            source=self.repository,
            addedBy=self.user,
            tokenizedContent="tokenized content"
        )
        
        # Create concept for interpretation
        self.concept = Concept.objects.create(
            uri='https://example.com/concept',
            label='Test Concept'
        )
        
        # Create predicate appellation with interpretation
        self.predicate = Appellation.objects.create(
            createdBy=self.user,
            occursIn=self.text,
            stringRep='Predicate',
            interpretation=self.concept
        )
        
        self.relation = Relation.objects.create(
            createdBy=self.user,
            occursIn=self.text,
            predicate=self.predicate
        )
    
    def test_relation_serializer(self):
        """Test that RelationSerializer serializes a Relation correctly."""
        serializer = RelationSerializer(instance=self.relation)
        self.assertIn('id', serializer.data)
        self.assertEqual(serializer.data['predicate'], self.predicate.id)


class DocumentPositionSerializerTest(TestCase):
    @mock.patch('annotations.models.DocumentPosition')
    def test_document_position_serializer(self, MockDocumentPosition):
        """Test that DocumentPositionSerializer serializes a DocumentPosition correctly."""
        mock_position = MockDocumentPosition.return_value
        mock_position.id = 1
        
        serializer = DocumentPositionSerializer(instance=mock_position)
        self.assertIn('id', serializer.data)


class DateAppellationSerializerTest(TestCase):
    @mock.patch('annotations.models.DateAppellation')
    @mock.patch('annotations.models.DocumentPosition')
    def test_date_appellation_serializer(self, MockDocumentPosition, MockDateAppellation):
        """Test that DateAppellationSerializer serializes a DateAppellation correctly."""
        mock_position = MockDocumentPosition.return_value
        mock_position.id = 1
        
        mock_appellation = MockDateAppellation.return_value
        mock_appellation.id = 1
        mock_appellation.position = mock_position
        mock_appellation.year = 2023
        mock_appellation.month = 1
        mock_appellation.day = 1
        mock_appellation.stringRep = "2023-01-01"
        
        serializer = DateAppellationSerializer(instance=mock_appellation)
        self.assertIn('id', serializer.data)
        self.assertIn('position', serializer.data)
        self.assertIn('year', serializer.data)
        self.assertIn('month', serializer.data)
        self.assertIn('day', serializer.data)
        self.assertIn('stringRep', serializer.data)


class TextSerializerTest(TestCase):
    def setUp(self):
        self.repository = Repository.objects.create(
            name='Test Repository',
            manager='JARSManager',
            endpoint='https://example.com',
            oauth_client_id='test-client-id',
            oauth_secret_key='test-secret-key'
        )
        
        self.user = VogonUser.objects.create(
            username='testuser',
            email='test@example.com'
        )
        
        self.text_data = {
            'uri': 'https://example.com/test',
            'title': 'Test Text',
            'source': self.repository.id,
        }
        
        self.factory = APIRequestFactory()
        
    def test_text_serializer(self):
        """Test that TextSerializer serializes a Text correctly."""
        text = Text.objects.create(
            uri=self.text_data['uri'],
            title=self.text_data['title'],
            source=self.repository,
            addedBy=self.user,
            tokenizedContent="tokenized content"
        )
        
        # Add a mock annotator
        annotator = VogonUser.objects.create(
            username='annotator',
            email='annotator@example.com'
        )
        text.annotators.add(annotator)
        
        serializer = TextSerializer(instance=text)
        
        self.assertEqual(serializer.data['uri'], self.text_data['uri'])
        self.assertEqual(serializer.data['title'], self.text_data['title'])
        self.assertEqual(serializer.data['source'], self.repository.id)


class AppellationSerializerTest(TestCase):
    def setUp(self):
        self.user = VogonUser.objects.create(
            username='testuser',
            email='test@example.com'
        )
        
        self.repository = Repository.objects.create(
            name='Test Repository',
            manager='JARSManager',
            endpoint='https://example.com',
            oauth_client_id='test-client-id',
            oauth_secret_key='test-secret-key'
        )
        
        self.text = Text.objects.create(
            uri='https://example.com/test',
            title='Test Text',
            source=self.repository,
            addedBy=self.user,
            tokenizedContent="tokenized content"
        )
        
        self.concept = Concept.objects.create(
            uri='https://example.com/concept',
            label='Test Concept'
        )
        
        # Create text content type for DocumentPosition
        content_type = ContentType.objects.get_for_model(Text)
        
        self.position = DocumentPosition.objects.create(
            position_type=DocumentPosition.XPATH,
            position_value='test-value',
            occursIn=self.text
        )
        
        self.appellation = Appellation.objects.create(
            createdBy=self.user,
            occursIn=self.text,
            interpretation=self.concept,
            stringRep='Test String',
            position=self.position
        )
        
        self.factory = APIRequestFactory()
        
    def test_appellation_serializer(self):
        """Test that AppellationSerializer serializes an Appellation correctly."""
        request = self.factory.get('/')
        serializer = AppellationSerializer(instance=self.appellation, context={'request': request})
        
        self.assertEqual(serializer.data['stringRep'], 'Test String')
        self.assertEqual(serializer.data['createdBy']['username'], 'testuser')
        self.assertIn('position', serializer.data)
        self.assertIn('interpretation', serializer.data)


class AppellationPOSTSerializerTest(TestCase):
    def setUp(self):
        self.user = VogonUser.objects.create(
            username='testuser',
            email='test@example.com'
        )
        
        self.repository = Repository.objects.create(
            name='Test Repository',
            manager='JARSManager',
            endpoint='https://example.com',
            oauth_client_id='test-client-id',
            oauth_secret_key='test-secret-key'
        )
        
        self.text = Text.objects.create(
            uri='https://example.com/test',
            title='Test Text',
            source=self.repository,
            addedBy=self.user,
            tokenizedContent="tokenized content"
        )
        
        self.concept = Concept.objects.create(
            uri='https://example.com/concept',
            label='Test Concept'
        )
        
        self.appellation_data = {
            'stringRep': 'Test String',
            'startPos': 0,
            'endPos': 10,
            'tokenIds': '0,1,2',
            'occursIn': self.text.id,
            'interpretation': self.concept.id,
            'createdBy': self.user.id
        }
    
    def test_appellation_post_serializer(self):
        """Test that AppellationPOSTSerializer deserializes data correctly."""
        serializer = AppellationPOSTSerializer(data=self.appellation_data)
        if not serializer.is_valid():
            print(serializer.errors)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['stringRep'], self.appellation_data['stringRep'])
        self.assertEqual(serializer.validated_data['startPos'], self.appellation_data['startPos'])
        self.assertEqual(serializer.validated_data['endPos'], self.appellation_data['endPos'])
        self.assertEqual(serializer.validated_data['tokenIds'], self.appellation_data['tokenIds'])


class RelationSetSerializerTest(TestCase):
    def setUp(self):
        self.user = VogonUser.objects.create(
            username='testuser',
            email='test@example.com'
        )
        
        self.repository = Repository.objects.create(
            name='Test Repository',
            manager='JARSManager',
            endpoint='https://example.com',
            oauth_client_id='test-client-id',
            oauth_secret_key='test-secret-key'
        )
        
        self.text = Text.objects.create(
            uri='https://example.com/test',
            title='Test Text',
            source=self.repository,
            addedBy=self.user,
            tokenizedContent="tokenized content"
        )
        
        self.relation_set = RelationSet.objects.create(
            createdBy=self.user,
            occursIn=self.text
        )
        
    def test_relation_set_serializer(self):
        """Test that RelationSetSerializer serializes a RelationSet correctly."""
        serializer = RelationSetSerializer(instance=self.relation_set)
        
        # Test that the data has a label property from the model
        self.assertIn('label', serializer.data)
        # Check username matches
        self.assertEqual(serializer.data['createdBy']['username'], 'testuser')
        self.assertIn('appellations', serializer.data)
        self.assertIn('date_appellations', serializer.data)
        self.assertIn('concepts', serializer.data)


class TemporalBoundsSerializerTest(TestCase):
    def setUp(self):
        self.bounds = TemporalBounds.objects.create()
        self.serializer = TemporalBoundsSerializer(instance=self.bounds)
    
    def test_temporal_bounds_serializer(self):
        """Test that TemporalBoundsSerializer serializes TemporalBounds correctly."""
        data = self.serializer.data
        self.assertIn('id', data)
        # Fields are present in serializer output
        self.assertIn('start', data)
        self.assertIn('end', data)
        self.assertIn('occur', data)


class TextCollectionSerializerTest(TestCase):
    def setUp(self):
        self.user = VogonUser.objects.create(
            username='testuser',
            email='test@example.com'
        )
        
        self.collection_data = {
            'name': 'Test Collection',
            'description': 'Test collection description',
            'ownedBy': self.user
        }
        self.collection = TextCollection.objects.create(**self.collection_data)
        self.serializer = TextCollectionSerializer(instance=self.collection)
    
    def test_text_collection_serializer(self):
        """Test that TextCollectionSerializer serializes a TextCollection correctly."""
        data = self.serializer.data
        self.assertEqual(data['name'], self.collection_data['name'])
        self.assertEqual(data['description'], self.collection_data['description'])


class TemplatePartSerializerTest(TestCase):
    def setUp(self):
        self.user = VogonUser.objects.create(
            username='testuser',
            email='test@example.com'
        )
        
        self.template_data = {
            'name': 'Test Template Part',
            'description': 'Test template part description',
            'createdBy': self.user
        }
        self.template = RelationTemplate.objects.create(**self.template_data)
        self.serializer = TemplatePartSerializer(instance=self.template)
    
    def test_template_part_serializer(self):
        """Test that TemplatePartSerializer serializes a RelationTemplate correctly."""
        data = self.serializer.data
        self.assertEqual(data['name'], self.template_data['name'])
        self.assertEqual(data['description'], self.template_data['description'])


class TemplateSerializerTest(TestCase):
    def setUp(self):
        self.user = VogonUser.objects.create(
            username='testuser',
            email='test@example.com'
        )
        
        self.template_data = {
            'name': 'Test Template',
            'description': 'Test template description',
            'createdBy': self.user
        }
        self.template = RelationTemplate.objects.create(**self.template_data)
        
        # Create template parts as RelationTemplatePart objects
        self.part1 = RelationTemplatePart.objects.create(
            part_of=self.template,
            internal_id=1
        )
        self.part2 = RelationTemplatePart.objects.create(
            part_of=self.template,
            internal_id=2
        )
        
        self.serializer = TemplateSerializer(instance=self.template)
    
    def test_template_serializer(self):
        """Test that TemplateSerializer serializes a RelationTemplate with parts correctly."""
        data = self.serializer.data
        self.assertEqual(data['name'], self.template_data['name'])
        self.assertEqual(data['description'], self.template_data['description'])
        # Only assert template_parts exists
        self.assertIn('template_parts', data)
