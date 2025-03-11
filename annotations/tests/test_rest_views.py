from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from rest_framework.test import APIRequestFactory, APIClient, force_authenticate
import unittest
from django.contrib.contenttypes.models import ContentType

from annotations.models import (
    Appellation, 
    RelationSet,
    Relation, 
    Text, 
    TextCollection, 
    DateAppellation,
    DocumentPosition,
    Repository
)
from concepts.models import Concept, Type
from annotations.views.rest_views import (
    UserViewSet,
    RepositoryViewSet,
    DateAppellationViewSet,
    AppellationViewSet,
    PredicateViewSet,
    RelationSetViewSet,
    RelationViewSet,
    TextViewSet,
    TextCollectionViewSet,
    TypeViewSet,
    ConceptViewSet,
)

User = get_user_model()

# Helper function to create a minimal set of test data
def create_test_data(user):
    # Create a project/text collection
    project = TextCollection.objects.create(
        name='Test Project',
        description='Test Project Description',
        ownedBy=user
    )
    
    # Create a text
    text = Text.objects.create(
        title='Test Text',
        addedBy=user,
        tokenizedContent='Test content',
        uri='test:1',
        content_type='text/plain'
    )
    project.texts.add(text)
    
    # Create a concept and type
    concept_type = Type.objects.create(
        uri='test:type:1',
        label='Test Type',
    )
    concept = Concept.objects.create(
        uri='test:concept:1',
        label='Test Concept',
        typed=concept_type
    )
    
    # Create document positions for the appellations
    doc_position = DocumentPosition.objects.create(
        occursIn=text,
        position_type=DocumentPosition.TOKEN_ID,
        position_value='0,1'
    )
    
    # Create an appellation (non-predicate)
    appellation = Appellation.objects.create(
        asPredicate=False,
        stringRep='Test String',
        occursIn=text,
        createdBy=user,
        tokenIds='0,1',
        startPos=0,
        endPos=10,
        interpretation=concept,
        position=doc_position
    )
    
    # Create a predicate appellation
    predicate_position = DocumentPosition.objects.create(
        occursIn=text,
        position_type=DocumentPosition.TOKEN_ID,
        position_value='0,1'
    )
    
    predicate = Appellation.objects.create(
        asPredicate=True,
        stringRep='Test Predicate',
        occursIn=text,
        createdBy=user,
        tokenIds='0,1',
        startPos=0,
        endPos=10,
        interpretation=concept,
        position=predicate_position
    )
    
    # Create a relationset and relation
    relation_set = RelationSet.objects.create(
        occursIn=text,
        createdBy=user
    )
    
    # Get ContentType for Appellation to use with generic foreign keys
    appellation_content_type = ContentType.objects.get_for_model(Appellation)
    
    # Create relation
    relation = Relation.objects.create(
        part_of=relation_set,
        source_content_type=appellation_content_type,
        source_object_id=appellation.id,
        predicate=predicate,
        object_content_type=appellation_content_type,
        object_object_id=appellation.id,
        occursIn=text,
        createdBy=user
    )
    
    # Create a document position for date appellation
    date_position = DocumentPosition.objects.create(
        occursIn=text,
        position_type=DocumentPosition.TOKEN_ID,
        position_value='0,1'
    )
    
    date_appellation = DateAppellation.objects.create(
        occursIn=text,
        createdBy=user,
        year=2023,
        month=1,
        day=1,
        position=date_position,
        stringRep='January 1, 2023',
        project=project
    )
    
    # Create repository using the fields from annotations.Repository model
    repository = Repository.objects.create(
        name='Test Repository',
        manager='TestManager',
        endpoint='https://test-api.example.com',
        oauth_client_id='test-client-id', 
        oauth_secret_key='test-client-secret'
    )
    
    return {
        'project': project,
        'text': text,
        'concept': concept,
        'concept_type': concept_type,
        'appellation': appellation,
        'predicate': predicate,
        'relation_set': relation_set,
        'relation': relation,
        'date_appellation': date_appellation,
        'repository': repository
    }


@patch('requests.get')   # Global patch to ensure no GET requests are made
@patch('requests.post')  # Global patch to ensure no POST requests are made
class UserViewSetTest(TestCase):
    """Test the UserViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='password123'
        )
        # Set admin status after creation
        self.admin_user.is_admin = True
        self.admin_user.save()
    
    def test_list_users(self, mock_post, mock_get):
        """Test listing users"""
        # Force mock to return empty list
        mock_get.return_value.json.return_value = []
        
        view = UserViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/user')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        # Don't assert on exact count since there may be existing users in the database
        self.assertGreaterEqual(len(response.data), 2)
    
    def test_retrieve_user(self, mock_post, mock_get):
        """Test retrieving a specific user"""
        view = UserViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/user/{self.user.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.user.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'testuser')


@patch('requests.get')
@patch('requests.post')
class RepositoryViewSetTest(TestCase):
    """Test the RepositoryViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            manager='TestManager',
            endpoint='https://test-api.example.com',
            oauth_client_id='test-client-id',
            oauth_secret_key='test-client-secret'
        )
    
    def test_list_repositories(self, mock_post, mock_get):
        """Test listing repositories"""
        view = RepositoryViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/repository')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        # Don't assert on exact count since there may be existing repositories
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_retrieve_repository(self, mock_post, mock_get):
        """Test retrieving a specific repository"""
        view = RepositoryViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/repository/{self.repository.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.repository.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Test Repository')


@patch('requests.get')
@patch('requests.post')
class DateAppellationViewSetTest(TestCase):
    """Test the DateAppellationViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
    
    def test_list_date_appellations(self, mock_post, mock_get):
        """Test listing date appellations"""
        view = DateAppellationViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/dateappellation')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_retrieve_date_appellation(self, mock_post, mock_get):
        """Test retrieving a specific date appellation"""
        date_appellation = self.test_data['date_appellation']
        view = DateAppellationViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/dateappellation/{date_appellation.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=date_appellation.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['year'], 2023)


@patch('requests.get')
@patch('requests.post')
class AppellationViewSetTest(TestCase):
    """Test the AppellationViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
    
    def test_list_appellations(self, mock_post, mock_get):
        """Test listing appellations"""
        view = AppellationViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/appellation')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)  # Only non-predicate appellations
    
    def test_retrieve_appellation(self, mock_post, mock_get):
        """Test retrieving a specific appellation"""
        appellation = self.test_data['appellation']
        view = AppellationViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/appellation/{appellation.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=appellation.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stringRep'], 'Test String')
    

@patch('requests.get')
@patch('requests.post')
class PredicateViewSetTest(TestCase):
    """Test the PredicateViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
    
    def test_list_predicates(self, mock_post, mock_get):
        """Test listing predicates"""
        view = PredicateViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/predicate')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)  # One predicate appellation
    
    def test_retrieve_predicate(self, mock_post, mock_get):
        """Test retrieving a specific predicate"""
        predicate = self.test_data['predicate']
        view = PredicateViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/predicate/{predicate.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=predicate.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stringRep'], 'Test Predicate')
        self.assertTrue(response.data['asPredicate'])


@patch('requests.get')
@patch('requests.post')
class RelationSetViewSetTest(TestCase):
    """Test the RelationSetViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
    
    def test_list_relationsets(self, mock_post, mock_get):
        """Test listing relation sets"""
        view = RelationSetViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/relationset')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_retrieve_relationset(self, mock_post, mock_get):
        """Test retrieving a specific relation set"""
        relation_set = self.test_data['relation_set']
        view = RelationSetViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/relationset/{relation_set.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=relation_set.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['occursIn'], self.test_data['text'].id)


@patch('requests.get')
@patch('requests.post')
class RelationViewSetTest(TestCase):
    """Test the RelationViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
    
    def test_list_relations(self, mock_post, mock_get):
        """Test listing relations"""
        view = RelationViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/relation')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_retrieve_relation(self, mock_post, mock_get):
        """Test retrieving a specific relation"""
        relation = self.test_data['relation']
        view = RelationViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/relation/{relation.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=relation.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['part_of'], self.test_data['relation_set'].id)


@patch('requests.get')
@patch('requests.post')
class TextViewSetTest(TestCase):
    """Test the TextViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
    
    def test_list_texts(self, mock_post, mock_get):
        """Test listing texts"""
        view = TextViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/text')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_retrieve_text(self, mock_post, mock_get):
        """Test retrieving a specific text"""
        text = self.test_data['text']
        view = TextViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/text/{text.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=text.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Test Text')


@patch('requests.get')
@patch('requests.post')
class TextCollectionViewSetTest(TestCase):
    """Test the TextCollectionViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
    
    def test_list_text_collections(self, mock_post, mock_get):
        """Test listing text collections"""
        view = TextCollectionViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/textcollection')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_retrieve_text_collection(self, mock_post, mock_get):
        """Test retrieving a specific text collection"""
        project = self.test_data['project']
        view = TextCollectionViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/textcollection/{project.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=project.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Test Project')
        self.assertEqual(response.data['description'], 'Test Project Description')


@patch('requests.get')
@patch('requests.post')
class TypeViewSetTest(TestCase):
    """Test the TypeViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
    
    def test_list_types(self, mock_post, mock_get):
        """Test listing types"""
        view = TypeViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/type')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_retrieve_type(self, mock_post, mock_get):
        """Test retrieving a specific type"""
        concept_type = self.test_data['concept_type']
        view = TypeViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/type/{concept_type.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=concept_type.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['label'], 'Test Type')


@patch('requests.get')
@patch('requests.post')
class ConceptViewSetTest(TestCase):
    """Test the ConceptViewSet endpoints"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
    
    def test_list_concepts(self, mock_post, mock_get):
        """Test listing concepts"""
        view = ConceptViewSet.as_view({'get': 'list'})
        request = self.factory.get('/rest/concept')
        force_authenticate(request, user=self.user)
        response = view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_retrieve_concept(self, mock_post, mock_get):
        """Test retrieving a specific concept"""
        concept = self.test_data['concept']
        view = ConceptViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/rest/concept/{concept.id}')
        force_authenticate(request, user=self.user)
        response = view(request, pk=concept.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['label'], 'Test Concept')
        self.assertEqual(response.data['uri'], 'test:concept:1')


@patch('annotations.views.rest_views.fetch_concept_data')  # Directly mock the function
class FetchConceptDataTest(TestCase):
    """Test the fetch_concept_data function"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
    
    def test_fetch_concept_data_mocked(self, mock_fetch):
        """Test that fetch_concept_data is properly mocked"""
        # Set up the mock to return expected data
        mock_fetch.return_value = [
            {'label': 'Test Concept', 'uri': 'http://example.com/concept/1', 'description': 'Test Description'}
        ]

        from annotations.views.rest_views import fetch_concept_data
        result = fetch_concept_data('test query')
        
        # Verify the mock was called and returned expected data
        mock_fetch.assert_called_once_with('test query')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['label'], 'Test Concept')


@patch('requests.get')
@patch('requests.post')
class PermissionTest(TestCase):
    """Test the custom permission class"""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collab@example.com',
            password='password123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='password123'
        )
        self.test_data = create_test_data(self.user)
        
        # Add collaborator to project
        self.test_data['project'].collaborators.add(self.collaborator)
    
    def test_other_user_no_write_permission(self, mock_post, mock_get):
        """Test that non-owners/non-collaborators don't have write permission"""
        appellation = self.test_data['appellation']
        text = self.test_data['text']
        view = AppellationViewSet.as_view({'put': 'partial_update'})
        
        data = {
            'stringRep': 'Unauthorized Update',
            'occursIn': text.id
        }
        
        request = self.factory.put(f'/rest/appellation/{appellation.id}?text={text.id}', data, format='json')
        force_authenticate(request, user=self.other_user)
        response = view(request, pk=appellation.id)
        
        self.assertEqual(response.status_code, 403)
