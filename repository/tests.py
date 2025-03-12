from django.test import TestCase
from unittest.mock import patch, MagicMock, ANY
from requests.exceptions import RequestException

# Replace the default User model with the custom VogonUser model
from annotations.models import VogonUser
from repository.models import Repository
from repository.managers import CitesphereAPIError, CitesphereAPIv1, RepositoryManager
from repository.exceptions import GilesTextExtractionError
from external_accounts.giles import GilesAPI


class CitesphereAPIErrorTest(TestCase):
    """Test cases for the CitesphereAPIError class."""

    def test_init(self):
        """Test the initialization of CitesphereAPIError."""
        # Test with all parameters
        error = CitesphereAPIError(
            message="Test error",
            error_code="TEST_ERROR",
            details="Test details"
        )
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.error_code, "TEST_ERROR")
        self.assertEqual(error.details, "Test details")
        
        # Test with just the message parameter
        error = CitesphereAPIError(message="Test error")
        self.assertEqual(error.message, "Test error")
        self.assertIsNone(error.error_code)
        self.assertIsNone(error.details)


@patch('requests.post')  # Global patch to ensure no POST requests are made
@patch('requests.get')   # Global patch to ensure no GET requests are made
class CitesphereAPIv1Test(TestCase):
    """
    Test cases for the CitesphereAPIv1 class.
    
    Note: Some tests in this class intentionally trigger error conditions
    to verify proper error handling. The following log messages are expected
    and do not reflect a test failure:
    - ERROR:repository.managers:Invalid JSON response
    - ERROR:repository.managers:Failed to fetch data: Request error
    """

    def setUp(self):
        """Set up test data."""
        # Use VogonUser instead of User
        self.user = VogonUser.objects.create_user(
            username='testuser', 
            email='test@example.com',
            password='testpass'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
        self.api = CitesphereAPIv1(self.user, self.repository)

    @patch('repository.auth.citesphere_auth')
    def test_get_headers(self, mock_auth, mock_get, mock_post):
        """Test the _get_headers method."""
        # Setup mock return value
        expected_headers = {'Authorization': 'Bearer test-token'}
        mock_auth.return_value = expected_headers
        
        # Call the method and verify
        headers = self.api._get_headers()
        self.assertEqual(headers, expected_headers)
        mock_auth.assert_called_once_with(self.user, self.repository)
        
        # Verify no HTTP requests were made
        mock_get.assert_not_called()
        mock_post.assert_not_called()
    
    @patch('repository.auth.citesphere_auth')
    def test_get_headers_exception(self, mock_auth, mock_get, mock_post):
        """Test exception handling in _get_headers method."""
        # Setup mock to raise an exception
        mock_auth.side_effect = Exception("Auth error")
        
        # Call the method and verify exception
        with self.assertRaises(CitesphereAPIError) as context:
            self.api._get_headers()
        
        self.assertEqual(context.exception.message, "Authentication failed, please try again.")
        self.assertEqual(context.exception.error_code, "AUTH_ERROR")
        self.assertEqual(context.exception.details, "Auth error")
        
        # Verify no HTTP requests were made
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1._get_headers')
    def test_make_request(self, mock_get_headers, mock_get, mock_post):
        """Test the _make_request method."""
        # Setup mocks
        mock_get_headers.return_value = {'Authorization': 'Bearer test-token'}
        mock_response = MagicMock()
        mock_response.json.return_value = {'key': 'value'}
        mock_get.return_value = mock_response
        
        # Call the method and verify
        result = self.api._make_request('/endpoint', params={'param': 'value'})
        
        # Verify response
        self.assertEqual(result, {'key': 'value'})
        
        # Verify API call
        mock_get.assert_called_once_with(
            'https://test-api.example.com/api/v1/endpoint',
            headers={'Authorization': 'Bearer test-token'},
            params={'param': 'value'}
        )
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1._get_headers')
    def test_make_request_request_exception(self, mock_get_headers, mock_get, mock_post):
        """Test RequestException handling in _make_request method."""
        # Setup mocks
        mock_get_headers.return_value = {'Authorization': 'Bearer test-token'}
        mock_get.side_effect = RequestException("Request error")
        
        # Call the method and verify exception
        with self.assertRaises(CitesphereAPIError) as context:
            self.api._make_request('/endpoint')
        
        self.assertEqual(context.exception.message, "API request failed")
        self.assertEqual(context.exception.error_code, "REQUEST_ERROR")
        self.assertEqual(context.exception.details, "Request error")
        
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1._get_headers')
    def test_make_request_value_error(self, mock_get_headers, mock_get, mock_post):
        """Test ValueError handling in _make_request method."""
        # Setup mocks
        mock_get_headers.return_value = {'Authorization': 'Bearer test-token'}
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        # Call the method and verify exception
        with self.assertRaises(CitesphereAPIError) as context:
            self.api._make_request('/endpoint')
        
        self.assertEqual(context.exception.message, "Invalid JSON response")
        self.assertEqual(context.exception.error_code, "RESPONSE_ERROR")
        self.assertEqual(context.exception.details, "Invalid JSON")
        
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1._make_request')
    def test_get_groups(self, mock_make_request, mock_get, mock_post):
        """Test the get_groups method."""
        # Setup mock
        expected_result = {'groups': [{'id': 1, 'name': 'Group 1'}]}
        mock_make_request.return_value = expected_result
        
        # Call the method and verify
        result = self.api.get_groups(params={'param': 'value'})
        
        # Verify response and API call
        self.assertEqual(result, expected_result)
        mock_make_request.assert_called_once_with('/groups/', params={'param': 'value'})
        
        # Verify no direct HTTP requests
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1._make_request')
    def test_get_group_items(self, mock_make_request, mock_get, mock_post):
        """Test the get_group_items method."""
        # Setup mock
        expected_result = {'items': [{'id': 1, 'title': 'Item 1'}]}
        mock_make_request.return_value = expected_result
        
        # Call the method and verify
        result = self.api.get_group_items('group1', params={'param': 'value'})
        
        # Verify response and API call
        self.assertEqual(result, expected_result)
        mock_make_request.assert_called_once_with('/groups/group1/items/', params={'param': 'value'})
        
        # Verify no direct HTTP requests
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1._make_request')
    def test_get_group_collections(self, mock_make_request, mock_get, mock_post):
        """Test the get_group_collections method."""
        # Setup mock
        expected_result = {'collections': [{'id': 1, 'name': 'Collection 1'}]}
        mock_make_request.return_value = expected_result
        
        # Call the method and verify
        result = self.api.get_group_collections('group1', params={'param': 'value'})
        
        # Verify response and API call
        self.assertEqual(result, expected_result)
        mock_make_request.assert_called_once_with('/groups/group1/collections/', params={'param': 'value'})
        
        # Verify no direct HTTP requests
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1._make_request')
    def test_get_collection_items(self, mock_make_request, mock_get, mock_post):
        """Test the get_collection_items method."""
        # Setup mock
        expected_result = {'items': [{'id': 1, 'title': 'Item 1'}]}
        mock_make_request.return_value = expected_result
        
        # Call the method and verify
        result = self.api.get_collection_items('group1', 'collection1', params={'param': 'value'})
        
        # Verify response and API call
        self.assertEqual(result, expected_result)
        mock_make_request.assert_called_once_with('/groups/group1/collections/collection1/items/', params={'param': 'value'})
        
        # Verify no direct HTTP requests
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1._make_request')
    def test_get_item_details(self, mock_make_request, mock_get, mock_post):
        """Test the get_item_details method."""
        # Setup mock
        expected_result = {'item': {'id': 1, 'title': 'Item 1'}}
        mock_make_request.return_value = expected_result
        
        # Call the method and verify
        result = self.api.get_item_details('group1', 'item1', params={'param': 'value'})
        
        # Verify response and API call
        self.assertEqual(result, expected_result)
        mock_make_request.assert_called_once_with('/groups/group1/items/item1/', params={'param': 'value'})
        
        # Verify no direct HTTP requests
        mock_get.assert_not_called()
        mock_post.assert_not_called()


@patch('requests.post')  # Global patch to ensure no POST requests are made
@patch('requests.get')   # Global patch to ensure no GET requests are made
class RepositoryManagerTest(TestCase):
    """
    Test cases for the RepositoryManager class.

    Note: Several tests in this class deliberately trigger error conditions
    to verify proper error handling. The following log messages are expected
    during test execution and do not indicate test failures:
    - ERROR:repository.managers:Invalid page number: Page must be a positive integer
    - ERROR:repository.managers:Failed to fetch data: Request error
    - ERROR:repository.managers:Invalid item data received: missing 'item' key
    - ERROR:repository.managers:Failed to retrieve text content from Giles for file ID: file1
    - ERROR:repository.managers:Unexpected error retrieving Giles document: [Error message]
    """

    def setUp(self):
        """Set up test data."""
        # Use VogonUser instead of User
        self.user = VogonUser.objects.create_user(
            username='testuser', 
            email='test@example.com',
            password='testpass'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            description='Test Description',
            endpoint='https://test-api.example.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
        self.manager = RepositoryManager(self.user, self.repository)

    @patch('repository.auth.citesphere_auth')
    def test_get_raw(self, mock_auth, mock_get, mock_post):
        """Test the get_raw method."""
        # Setup mocks
        mock_auth.return_value = {'Authorization': 'Bearer test-token'}
        mock_response = MagicMock()
        mock_response.content = b'raw data'
        mock_get.return_value = mock_response
        
        # Call the method and verify
        result = self.manager.get_raw('https://example.com/data', param='value')
        
        # Verify response
        self.assertEqual(result, b'raw data')
        
        # Verify API call
        mock_get.assert_called_once_with(
            'https://example.com/data', 
            headers={'Authorization': 'Bearer test-token'},
            params={'param': 'value'}
        )
        mock_post.assert_not_called()

    @patch('repository.auth.citesphere_auth')
    def test_get_raw_exception(self, mock_auth, mock_get, mock_post):
        """Test exception handling in get_raw method."""
        # Setup mocks
        mock_auth.return_value = {'Authorization': 'Bearer test-token'}
        mock_get.side_effect = RequestException("Request error")
        
        # Call the method and verify exception
        with self.assertRaises(CitesphereAPIError) as context:
            self.manager.get_raw('https://example.com/data')
        
        self.assertEqual(context.exception.message, "Failed to fetch data")
        self.assertEqual(context.exception.error_code, "RAW_DATA_ERROR")
        self.assertEqual(context.exception.details, "Request error")
        
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1.get_groups')
    def test_groups(self, mock_get_groups, mock_get, mock_post):
        """Test the groups method."""
        # Setup mock
        expected_result = {'groups': [{'id': 1, 'name': 'Group 1'}]}
        mock_get_groups.return_value = expected_result
        
        # Call the method and verify
        result = self.manager.groups()
        
        # Verify response and API call
        self.assertEqual(result, expected_result)
        mock_get_groups.assert_called_once()
        
        # Verify no direct HTTP requests
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1.get_group_items')
    def test_group_items(self, mock_get_group_items, mock_get, mock_post):
        """Test the group_items method."""
        # Setup mock
        mock_response = {
            'group': {'numItems': 10},
            'items': [{'id': 1, 'title': 'Item 1'}]
        }
        mock_get_group_items.return_value = mock_response
        
        # Call the method and verify
        result = self.manager.group_items('group1', page=2)
        
        # Verify response
        self.assertEqual(result['group'], {'numItems': 10})
        self.assertEqual(result['items'], [{'id': 1, 'title': 'Item 1'}])
        self.assertEqual(result['total_items'], 10)
        
        # Verify API call
        mock_get_group_items.assert_called_once_with('group1', params={'page': 2})
        
        # Verify no direct HTTP requests
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    def test_group_items_invalid_page(self, mock_get, mock_post):
        """Test group_items with invalid page number."""
        with self.assertRaises(CitesphereAPIError) as context:
            self.manager.group_items('group1', page=0)
        
        self.assertEqual(context.exception.message, "Invalid page number")
        self.assertEqual(context.exception.error_code, "INVALID_PAGE")

        with self.assertRaises(CitesphereAPIError):
            self.manager.group_items('group1', page='invalid')
            
        # Verify no HTTP requests were made
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1.get_group_collections')
    def test_collections(self, mock_get_group_collections, mock_get, mock_post):
        """Test the collections method."""
        # Setup mock
        expected_result = {'collections': [{'id': 1, 'name': 'Collection 1'}]}
        mock_get_group_collections.return_value = expected_result
        
        # Call the method and verify
        result = self.manager.collections('group1')
        
        # Verify response and API call
        self.assertEqual(result, expected_result)
        mock_get_group_collections.assert_called_once_with('group1')
        
        # Verify no direct HTTP requests
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1.get_collection_items')
    @patch('repository.managers.CitesphereAPIv1.get_group_collections')
    def test_collection_items(self, mock_get_group_collections, mock_get_collection_items, mock_get, mock_post):
        """Test the collection_items method."""
        # Setup mocks
        collections_data = {
            'collections': [
                {'key': 'collection1', 'numberOfItems': 5}
            ]
        }
        mock_get_group_collections.return_value = collections_data
        
        items_data = {'items': [{'id': 1, 'title': 'Item 1'}]}
        mock_get_collection_items.return_value = items_data
        
        # Call the method and verify
        result = self.manager.collection_items('group1', 'collection1', page=2)
        
        # Verify response
        self.assertEqual(result['group'], collections_data['collections'])
        self.assertEqual(result['items'], items_data['items'])
        self.assertEqual(result['total_items'], 5)
        
        # Verify API calls
        mock_get_group_collections.assert_called_once_with('group1')
        mock_get_collection_items.assert_called_once_with('group1', 'collection1', params={'page': 2})
        
        # Verify no direct HTTP requests
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    def test_collection_items_invalid_page(self, mock_get, mock_post):
        """Test collection_items with invalid page number."""
        with self.assertRaises(CitesphereAPIError) as context:
            self.manager.collection_items('group1', 'collection1', page=0)
        
        self.assertEqual(context.exception.message, "Invalid page number")
        self.assertEqual(context.exception.error_code, "INVALID_PAGE")

        with self.assertRaises(CitesphereAPIError):
            self.manager.collection_items('group1', 'collection1', page='invalid')
            
        # Verify no HTTP requests were made
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    # @patch('repository.managers.CitesphereAPIv1.get_group_collections')
    # def test_collection_items_collection_not_found(self, mock_get_group_collections, mock_get, mock_post):
    #     """Test collection_items when collection is not found."""
    #     # Setup mock to return collections that don't include the requested one
    #     collections_data = {
    #         'collections': []  # Empty list to trigger the collection not found error
    #     }
    #     mock_get_group_collections.return_value = collections_data
        
    #     # Call the method and verify exception
    #     with self.assertRaises(CitesphereAPIError) as context:
    #         self.manager.collection_items('group1', 'collection1', page=1)
        
    #     self.assertEqual(context.exception.message, "Collection not found")
    #     self.assertEqual(context.exception.error_code, "COLLECTION_NOT_FOUND")
        
    #     # Verify no direct HTTP requests
    #     mock_get.assert_not_called()
    #     mock_post.assert_not_called()

    @patch('repository.auth.citesphere_auth')
    def test_item_files(self, mock_auth, mock_get, mock_post):
        """Test the item_files method."""
        # Setup mocks
        mock_auth.return_value = {'Authorization': 'Bearer test-token'}
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'item': {
                'gilesUploads': [
                    {
                        'extractedText': {
                            'content-type': 'text/plain',
                            'id': 'file1',
                            'filename': 'document.txt',
                            'url': 'https://example.com/file1'
                        }
                    },
                    {
                        'progressId': 'upload1'  # This indicates a processing file
                    }
                ]
            }
        }
        mock_get.return_value = mock_response
        
        # Call the method and verify
        result = self.manager.item_files('group1', 'item1')
        
        # Verify response
        self.assertEqual(len(result['files']), 1)
        self.assertEqual(result['files'][0]['id'], 'file1')
        self.assertEqual(result['files'][0]['filename'], 'document.txt')
        self.assertEqual(result['files'][0]['url'], 'https://example.com/file1')
        self.assertTrue(result['is_file_processing'])
        
        # Verify API call
        mock_get.assert_called_once_with(
            'https://test-api.example.com/api/v1/groups/group1/items/item1/',
            headers={'Authorization': 'Bearer test-token'}
        )
        mock_post.assert_not_called()

    @patch('repository.managers.CitesphereAPIv1.get_item_details')
    @patch('external_accounts.giles.GilesAPI.get_file_content')
    def test_item(self, mock_get_file_content, mock_get_item_details, mock_get, mock_post):
        """
        Test the item method.
        """
        # Mocks
        item_data = {
            'item': {
                'key': 'item1',
                'title': 'Test Item',
                'authors': ['Author 1'],
                'itemType': 'article',
                'dateAdded': '2023-01-01',
                'url': 'https://example.com/item1'
            }
        }
        mock_get_item_details.return_value = item_data
        mock_get_file_content.return_value = "This is the document text."

        # Call the method
        repository = Repository.objects.create(
            name='Test Repository',
            endpoint='https://test-repository.com',
            client_id='test-client-id',
            client_secret='test-client-secret',
            giles_endpoint='https://giles.test/'
        )
        result = self.manager.item('group1', 'item1', 'file1', repository)

        # Assertions
        self.assertEqual(result['item']['key'], 'item1')
        self.assertEqual(result['item']['text'], "This is the document text.")
        self.assertEqual(result['item']['details']['title'], 'Test Item')
        mock_get_item_details.assert_called_once_with('group1', 'item1')
        # No need to assert on get_file_content as it's called internally by the GilesAPI instance
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch('external_accounts.giles.GilesAPI.get_file_content')
    @patch('repository.managers.CitesphereAPIv1.get_item_details')
    def test_item_missing_file(self, mock_get_item_details, mock_get_file_content, mock_get, mock_post):
        """Test the item method when the file is missing."""
        # Setup mocks
        item_data = {
            'item': {
                'key': 'item1',
                'title': 'Test Item'
            }
        }
        mock_get_item_details.return_value = item_data
        
        # Explicitly set return value to None to simulate missing file
        mock_get_file_content.return_value = None
        
        # Call the method and verify exception
        repository = Repository.objects.create(
            name='Test Repository',
            endpoint='https://test-repository.com',
            client_id='test-client-id',
            client_secret='test-client-secret',
            giles_endpoint='https://giles.test/'
        )
        
        with self.assertRaises(GilesTextExtractionError) as context:
            self.manager.item('group1', 'item1', 'file1', repository)
        
        self.assertIn("Failed to retrieve text content from Giles", str(context.exception))
        
    @patch('repository.managers.CitesphereAPIv1.get_item_details')
    def test_item_invalid_data(self, mock_get_item_details, mock_get, mock_post):
        """Test the item method with invalid item data."""
        # Setup mock
        mock_get_item_details.return_value = {
            'wrong_key': 'wrong_value'  # Missing 'item' key
        }
        
        repository = Repository.objects.create(
            name='Test Repository',
            endpoint='https://test-repository.com',
            client_id='test-client-id',
            client_secret='test-client-secret',
            giles_endpoint='https://giles.test'
        )
        
        # Call the method and verify exception
        with self.assertRaises(CitesphereAPIError) as context:
            self.manager.item('group1', 'item1', 'file1', repository)
        
        self.assertEqual(context.exception.error_code, "INVALID_ITEM_DATA")
        
        # Verify interactions
        mock_get_item_details.assert_called_once_with('group1', 'item1')
        mock_get.assert_not_called()
        mock_post.assert_not_called()
