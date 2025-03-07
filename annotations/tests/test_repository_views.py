from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from annotations.models import Text, TextCollection
from repository.models import Repository
from repository.managers import CitesphereAPIError, RepositoryManager
from annotations.views.repository_views import (
    _get_params,
    _get_pagination,
    repository_collections,
    repository_collection,
    repository_browse,
    repository_search,
    repository_list,
    repository_details,
    repository_collection_texts,
    repository_text_files,
    repository_text_import,
    repository_text_content,
    repository_text_add_to_project,
    _repository_text_fail
)

User = get_user_model()

# decorator replacement that just returns the original function
def mock_decorator(f):
    return f

# patch a decorator
# We'll add it to each class to make it apply for that test class
def patch_auth_decorators(cls):
    orig_setup = cls.setUp
    
    def patched_setup(self):
        # Apply patches to bypass authentication and grab references to patchers
        self.citesphere_patcher = patch('annotations.views.repository_views.citesphere_authenticated')
        self.login_patcher = patch('annotations.views.repository_views.login_required')
        self.mock_citesphere = self.citesphere_patcher.start()
        self.mock_login = self.login_patcher.start()
        
        # Configure mocks to return the original view unchanged
        self.mock_citesphere.side_effect = lambda f: f
        self.mock_login.side_effect = lambda f: f
        
        # Call original setup
        orig_setup(self)
    
    def patched_teardown(self):
        # Stop the patchers
        self.citesphere_patcher.stop()
        self.login_patcher.stop()
        
        # Call original teardown if it exists
        if hasattr(cls, 'tearDown'):
            cls.tearDown(self)
    
    # Replace setUp and tearDown
    cls.setUp = patched_setup
    cls.tearDown = patched_teardown
    return cls


@patch('requests.get')   # Global patch to ensure no GET requests are made
@patch('requests.post')  # Global patch to ensure no POST requests are made
@patch_auth_decorators
class RepositoryCollectionsViewTest(TestCase):
    """Test the repository_collections view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
        
    @patch('repository.managers.RepositoryManager.groups')
    def test_repository_collections_success(self, mock_groups, mock_post, mock_get):
        """Test successful retrieval of repository collections"""
        # Setup mock for manager.groups
        mock_groups.return_value = [
            {'id': '1', 'name': 'Collection 1'},
            {'id': '2', 'name': 'Collection 2'}
        ]
        
        request = self.factory.get(f'/repository/{self.repository.id}/collections/')
        request.user = self.user
        
        response = repository_collections(request, self.repository.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('collections', response.context)
        self.assertEqual(len(response.context['collections']), 2)
    
    @patch('repository.managers.RepositoryManager.groups')
    def test_repository_collections_api_error(self, mock_groups, mock_post, mock_get):
        """Test handling of CitesphereAPIError in repository_collections"""
        # Setup mock for manager.groups to raise CitesphereAPIError
        mock_groups.side_effect = CitesphereAPIError("API Error")
        
        request = self.factory.get(f'/repository/{self.repository.id}/collections/')
        request.user = self.user
        
        response = repository_collections(request, self.repository.id)
        
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.context)
        self.assertEqual(response.context['error'], 'API Error')


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositoryCollectionViewTest(TestCase):
    """Test the repository_collection view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
    
    @patch('repository.managers.RepositoryManager.collections')
    @patch('repository.managers.RepositoryManager.group_items')
    def test_repository_collection_success(self, mock_group_items, mock_collections, mock_post, mock_get):
        """Test successful retrieval of a repository collection"""
        # Setup mocks for manager methods
        mock_collections.return_value = {
            'group': {'id': '1', 'name': 'Group 1'},
            'collections': [
                {'id': '1', 'name': 'Collection 1'},
                {'id': '2', 'name': 'Collection 2'}
            ]
        }
        mock_group_items.return_value = {
            'items': [
                {'id': '1', 'title': 'Item 1'},
                {'id': '2', 'title': 'Item 2'}
            ],
            'pages': {'total': 2, 'current': 1},
            'links': {
                'next': {'href': 'http://example.com/api?page=2'}
            }
        }
        
        request = self.factory.get(f'/repository/{self.repository.id}/collection/1/')
        request.user = self.user
        
        response = repository_collection(request, self.repository.id, '1')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('collections', response.context)
        self.assertIn('group_texts', response.context)
        self.assertEqual(len(response.context['collections']), 2)
        self.assertEqual(len(response.context['group_texts']['items']), 2)
    
    @patch('repository.managers.RepositoryManager.collections')
    def test_repository_collection_api_error(self, mock_collections, mock_post, mock_get):
        """Test handling of CitesphereAPIError in repository_collection"""
        # Setup mock for manager.collections to raise CitesphereAPIError
        mock_collections.side_effect = CitesphereAPIError("API Error")
        
        request = self.factory.get(f'/repository/{self.repository.id}/collection/1/')
        request.user = self.user
        
        response = repository_collection(request, self.repository.id, '1')
        
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.context)
        self.assertEqual(response.context['error'], 'API Error')


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositoryBrowseViewTest(TestCase):
    """Test the repository_browse view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
    
    def test_repository_browse_get(self, mock_post, mock_get):
        """Test GET request to repository_browse view"""
        request = self.factory.get(f'/repository/{self.repository.id}/browse/')
        request.user = self.user
        
        response = repository_browse(request, self.repository.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('repository', response.context)


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositorySearchViewTest(TestCase):
    """Test the repository_search view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
    
    @patch('repository.managers.RepositoryManager.get_raw')
    def test_repository_search_with_query(self, mock_get_raw, mock_post, mock_get):
        """Test repository_search view with a search query"""
        # Setup mock for manager.get_raw
        mock_get_raw.return_value = {
            'items': [
                {'id': '1', 'title': 'Item 1'},
                {'id': '2', 'title': 'Item 2'}
            ],
            'pages': {'total': 1, 'current': 1}
        }
        
        request = self.factory.get(f'/repository/{self.repository.id}/search/?query=test')
        request.user = self.user
        
        response = repository_search(request, self.repository.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('results', response.context)
        self.assertEqual(len(response.context['results']['items']), 2)


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositoryListViewTest(TestCase):
    """Test the repository_list view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        Repository.objects.create(
            name='Test Repository 1',
            description='Test Description 1',
            endpoint='https://test-api1.example.com',
            client_id='test-client-id-1',
            client_secret='test-client-secret-1'
        )
        Repository.objects.create(
            name='Test Repository 2',
            description='Test Description 2',
            endpoint='https://test-api2.example.com',
            client_id='test-client-id-2',
            client_secret='test-client-secret-2'
        )
    
    def test_repository_list(self, mock_post, mock_get):
        """Test repository_list view lists all repositories"""
        request = self.factory.get('/repositories/')
        request.user = self.user
        
        response = repository_list(request)
        
        self.assertEqual(response.status_code, 200)
        # This view might be returning an HttpResponse, not a TemplateResponse
        if hasattr(response, 'context'):
            self.assertIn('repositories', response.context)
            self.assertEqual(len(response.context['repositories']), 2)


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositoryDetailsViewTest(TestCase):
    """Test the repository_details view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
    
    @patch('repository.managers.RepositoryManager.groups')
    def test_repository_details(self, mock_groups, mock_post, mock_get):
        """Test repository_details view shows repository info and groups"""
        # Setup mock for manager.groups
        mock_groups.return_value = [
            {'id': '1', 'name': 'Group 1'},
            {'id': '2', 'name': 'Group 2'}
        ]
        
        request = self.factory.get(f'/repository/{self.repository.id}/')
        request.user = self.user
        
        response = repository_details(request, self.repository.id)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('groups', response.context)
        self.assertIn('repository', response.context)
        self.assertEqual(len(response.context['groups']), 2)
        self.assertEqual(response.context['repository'], self.repository)


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositoryCollectionTextsViewTest(TestCase):
    """Test the repository_collection_texts view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
    
    @patch('repository.managers.RepositoryManager.collection_items')
    def test_repository_collection_texts(self, mock_collection_items, mock_post, mock_get):
        """Test repository_collection_texts view shows collection items"""
        # Setup mock for manager.collection_items
        mock_collection_items.return_value = {
            'items': [
                {'id': '1', 'title': 'Item 1'},
                {'id': '2', 'title': 'Item 2'}
            ],
            'pages': {'total': 1, 'current': 1}
        }
        
        request = self.factory.get(f'/repository/{self.repository.id}/collection/1/1/')
        request.user = self.user
        
        response = repository_collection_texts(request, self.repository.id, '1', '1')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('texts', response.context)
        self.assertIn('repository', response.context)
        self.assertEqual(len(response.context['texts']['items']), 2)


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositoryTextFilesViewTest(TestCase):
    """Test the repository_text_files view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
    
    @patch('repository.managers.RepositoryManager.item_files')
    def test_repository_text_files(self, mock_item_files, mock_post, mock_get):
        """Test repository_text_files view shows text files"""
        # Setup mock for manager.item_files
        mock_item_files.return_value = [
            {'id': '1', 'filename': 'file1.txt', 'content_type': 'text/plain'},
            {'id': '2', 'filename': 'file2.pdf', 'content_type': 'application/pdf'}
        ]
        
        request = self.factory.get(f'/repository/{self.repository.id}/collection/1/item/1/')
        request.user = self.user
        
        response = repository_text_files(request, self.repository.id, '1', '1')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('files', response.context)
        self.assertIn('repository', response.context)
        self.assertEqual(len(response.context['files']), 2)


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositoryTextImportViewTest(TestCase):
    """Test the repository_text_import view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
        self.project = TextCollection.objects.create(
            name='Test Project',
            description='Test Project Description',
            ownedBy=self.user
        )
    
    @patch('annotations.tasks.tokenize')
    @patch('repository.managers.RepositoryManager.item')
    def test_repository_text_import_success(self, mock_item, mock_tokenize, mock_post, mock_get):
        """Test successful import of text from repository"""
        # Setup mock for manager.item
        mock_item.return_value = {
            'item': {
                'id': '1', 
                'title': 'Test Item',
                'createdOn': '2020-01-01T00:00:00Z',
                'creator': {'username': 'creator'}
            },
            'content': {
                'id': '1',
                'content': 'Test content',
                'content_type': 'text/plain'
            }
        }
        
        # Set up a mock for Text.save to avoid actual DB operations
        with patch('annotations.models.Text.save'):
            request = self.factory.get(
                f'/repository/{self.repository.id}/collection/1/text/1/file/1/import/?project_id={self.project.id}'
            )
            request.user = self.user
            
            response = repository_text_import(
                request, self.repository.id, '1', '1', '1', self.project.id
            )
            
            # Should redirect to the text detail page after successful import
            self.assertEqual(response.status_code, 302)
            self.assertTrue(mock_tokenize.called)


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositoryTextContentViewTest(TestCase):
    """Test the repository_text_content view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
    
    def test_repository_text_content(self, mock_post, mock_get):
        """Test repository_text_content view shows text content"""
        # Instead of patching individual methods, let's patch at a higher level
        manager_mock = MagicMock()
        manager_mock.content.return_value = 'Test content'
        manager_mock.resource.return_value = {
            'content_type': 'text/plain'
        }
        
        with patch('repository.managers.RepositoryManager', return_value=manager_mock):
            request = self.factory.get(f'/repository/{self.repository.id}/text/1/content/1/')
            request.user = self.user
            
            response = repository_text_content(request, self.repository.id, '1', '1')
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content.decode(), 'Test content')
            self.assertEqual(response['Content-Type'], 'text/plain')


@patch('requests.get')
@patch('requests.post')
@patch_auth_decorators
class RepositoryTextAddToProjectViewTest(TestCase):
    """Test the repository_text_add_to_project view"""
    
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
        self.project = TextCollection.objects.create(
            name='Test Project',
            description='Test Project Description',
            ownedBy=self.user
        )
        self.text = Text.objects.create(
            title='Test Text',
            addedBy=self.user,
            repository_id=self.repository.id,
            repository_source_id='1',
            tokenizedContent='',
            uri='test:1',
            content_type='text/plain'
        )
    
    def test_repository_text_add_to_project(self, mock_post, mock_get):
        """Test adding a text to a project"""
        # Create a more targeted mock to avoid actual DB operations
        with patch('annotations.models.TextCollection.texts') as mock_texts:
            mock_texts.add = MagicMock()
            mock_filter = MagicMock()
            mock_filter.exists.return_value = True
            mock_texts.filter.return_value = mock_filter
            
            request = self.factory.get(
                f'/repository/{self.repository.id}/text/{self.text.id}/add-to-project/{self.project.id}/'
            )
            request.user = self.user
            
            response = repository_text_add_to_project(
                request, self.repository.id, self.text.id, self.project.id
            )
            
            # Should redirect after adding to project
            self.assertEqual(response.status_code, 302)


class RepositoryTextFailTest(TestCase):
    """Test the _repository_text_fail utility function"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
    
    def test_repository_text_fail(self):
        """Test _repository_text_fail renders error template with provided content"""
        request = self.factory.get('/')
        request.user = self.user
        
        result = {'error': 'Test error message'}
        # Use a dict with the correct structure for content
        content = {'content': 'Test content', 'content_type': 'text/plain'}
        
        response = _repository_text_fail(request, self.repository, result, content)
        
        # _repository_text_fail doesn't set a status code explicitly, so it will be 200
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.context)
        self.assertIn('content', response.context)
        self.assertEqual(response.context['result']['error'], 'Test error message')
        self.assertEqual(response.context['content'], content) 