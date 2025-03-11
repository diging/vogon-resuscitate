from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
import json

from repository.models import Repository
from .models import CitesphereAccount
from .decorators import citesphere_authenticated
from .utils import parse_iso_datetimes, get_giles_document_details

User = get_user_model()

# Global mock for all tests to prevent any real HTTP requests
@patch('requests.get')
class CitesphereAccountModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            endpoint='https://citesphere.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
        
        # Setup default mock response for post_save signal
        self.mock_response = MagicMock()
        self.mock_response.json.return_value = [{"user": "citesphere123"}]
        self.mock_response.raise_for_status.return_value = None
    
    def test_string_representation(self, mock_get):
        """Test the string representation of CitesphereAccount"""
        # Configure mock for post_save signal
        mock_get.return_value = self.mock_response
        
        account = CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='citesphere123',
            access_token='access123',
            refresh_token='refresh123',
            token_expires_at=timezone.now() + timedelta(hours=1),
            extra_data=json.dumps({"scope": "read"})
        )
        
        expected = f"Citesphere account:{self.user.username} Repository: {self.repository.name}"
        self.assertEqual(str(account), expected)

    def test_is_token_expired_not_expired(self, mock_get):
        """Test is_token_expired returns False when token is not expired"""
        # Configure mock for post_save signal
        mock_get.return_value = self.mock_response
        
        account = CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='citesphere123',
            access_token='access123',
            refresh_token='refresh123',
            token_expires_at=timezone.now() + timedelta(hours=1),
            extra_data=json.dumps({"scope": "read"})
        )
        
        self.assertFalse(account.is_token_expired())

    def test_is_token_expired_when_expired(self, mock_get):
        """Test is_token_expired returns True when token is expired"""
        # Configure mock for post_save signal
        mock_get.return_value = self.mock_response
        
        account = CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='citesphere123',
            access_token='access123',
            refresh_token='refresh123',
            token_expires_at=timezone.now() - timedelta(minutes=5),
            extra_data=json.dumps({"scope": "read"})
        )
        
        self.assertTrue(account.is_token_expired())

    def test_extra_data_json_property(self, mock_get):
        """Test the extra_data_json property getter and setter"""
        # Configure mock for post_save signal
        mock_get.return_value = self.mock_response
        
        account = CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='citesphere123',
            access_token='access123',
            refresh_token='refresh123',
            token_expires_at=timezone.now() + timedelta(hours=1),
            extra_data='{}'
        )
        
        test_data = {"key": "value", "list": [1, 2, 3]}
        account.extra_data_json = test_data
        self.assertEqual(account.extra_data, json.dumps(test_data))
        self.assertEqual(account.extra_data_json, test_data)

    def test_post_save_signal_fetch_citesphere_user_id(self, mock_get):
        """Test the post_save signal to fetch citesphere_user_id"""
        # Configure mock with specific response for this test
        mock_response = MagicMock()
        mock_response.json.return_value = [{"user": "new_user_id"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Create a new account to trigger the signal
        new_account = CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='',  # Empty to test if it gets filled
            access_token='new_access123',
            refresh_token='new_refresh123',
            token_expires_at=timezone.now() + timedelta(hours=1),
            extra_data='{}'
        )

        # Verify the signal made the request with correct parameters
        mock_get.assert_called_with(
            f'{self.repository.endpoint}/api/v1/test/',
            headers={'Authorization': f'Bearer {new_account.access_token}'}
        )

        # Refresh from database
        new_account.refresh_from_db()
        
        # Verify citesphere_user_id was updated
        self.assertEqual(new_account.citesphere_user_id, "new_user_id")


class CitesphereUtilsTests(TestCase):
    def test_parse_iso_datetimes(self):
        """Test parsing ISO format datetime strings to dates"""
        test_dates = [
            "2023-04-18T14:30:00Z",
            "2023-04-19T10:15:30+00:00",
            "",  # Empty string
            None  # None value
        ]
        expected = ["2023-04-18", "2023-04-19", None, None]
        
        result = parse_iso_datetimes(test_dates)
        self.assertEqual(result, expected)

    @patch('requests.get')
    def test_get_giles_document_details(self, mock_get):
        """Test retrieving document details from Giles"""
        # Setup
        user = User.objects.create_user('user', 'user@example.com', 'password')
        repository = Repository.objects.create(
            name='Test Repo',
            endpoint='https://test.org',
            client_id='client',
            client_secret='secret'
        )
        
        # Mock for the CitesphereAccount creation (signal)
        with patch('requests.get') as mock_signal_get:
            mock_signal_response = MagicMock()
            mock_signal_response.json.return_value = [{"user": "user123"}]
            mock_signal_response.raise_for_status.return_value = None
            mock_signal_get.return_value = mock_signal_response
            
            # Now create the account
            CitesphereAccount.objects.create(
                user=user,
                repository=repository,
                citesphere_user_id='user123',
                access_token='access123',
                refresh_token='refresh123',
                token_expires_at=timezone.now() + timedelta(hours=1),
                extra_data='{}'
            )
        
        # Configure mock for the get_giles_document_details function
        mock_response = MagicMock()
        mock_response.text = "Document content"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with self.settings(GILES_ENDPOINT='https://giles.test/'):
            result = get_giles_document_details(user, 'file123')
            
            # Verify the result
            self.assertEqual(result, "Document content")
            
            # Verify the request
            mock_get.assert_called_once_with(
                'https://giles.test/api/v2/resources/files/file123/content/',
                headers={'Authorization': 'Bearer access123'}
            )


@patch('requests.get')
class CitesphereDecoratorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            endpoint='https://test-citesphere.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
        
        # Mock response for post_save signal
        self.mock_response = MagicMock()
        self.mock_response.json.return_value = [{"user": "citesphere123"}]
        self.mock_response.raise_for_status.return_value = None

    def test_decorator_with_valid_account(self, mock_get):
        """Test the decorator when user has a valid Citesphere account"""
        # Configure mock for post_save signal
        mock_get.return_value = self.mock_response
        
        # Create account with valid token
        CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='citesphere123',
            access_token='access123',
            refresh_token='refresh123',
            token_expires_at=timezone.now() + timedelta(hours=1),
            extra_data='{}'
        )
        
        # Create a test view
        @citesphere_authenticated
        def test_view(request, repository_id):
            return "SUCCESS"
        
        # Make the request
        request = self.factory.get('/test/')
        request.user = self.user
        
        # Call the view
        response = test_view(request, repository_id=self.repository.id)
        
        # Check that the view ran successfully
        self.assertEqual(response, "SUCCESS")

    def test_decorator_with_expired_token(self, mock_get):
        """Test the decorator redirects when token is expired"""
        # Configure mock for post_save signal
        mock_get.return_value = self.mock_response
        
        # Create account with expired token
        CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='citesphere123',
            access_token='access123',
            refresh_token='refresh123',
            token_expires_at=timezone.now() - timedelta(minutes=5),
            extra_data='{}'
        )
        
        # Create a test view
        @citesphere_authenticated
        def test_view(request, repository_id):
            return "SUCCESS"
        
        # Make the request
        request = self.factory.get('/test/')
        request.user = self.user
        
        # Call the view
        response = test_view(request, repository_id=self.repository.id)
        
        # Check that we got redirected to refresh token
        self.assertEqual(response.status_code, 302)
        self.assertTrue(reverse('citesphere_refresh_token', args=[self.repository.id]) in response.url)

    def test_decorator_with_no_account(self, mock_get):
        """Test the decorator redirects when no Citesphere account exists"""
        # Create a test view
        @citesphere_authenticated
        def test_view(request, repository_id):
            return "SUCCESS"
        
        # Make the request
        request = self.factory.get('/test/')
        request.user = self.user
        
        # Call the view
        response = test_view(request, repository_id=self.repository.id)
        
        # Check that we got redirected to login
        self.assertEqual(response.status_code, 302)
        self.assertTrue(reverse('citesphere_login') in response.url)


class CitesphereViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.repository = Repository.objects.create(
            name='Test Repository',
            endpoint='https://test-citesphere.com',
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
        self.client.login(username='testuser', password='password123')

    def test_citesphere_login_redirects_to_oauth(self):
        """Test the citesphere_login view redirects to the OAuth endpoint"""
        with self.settings(BASE_URL='http://testserver/'):
            response = self.client.get(
                reverse('citesphere_login') + f'?repository_id={self.repository.id}'
            )
            
            self.assertEqual(response.status_code, 302)
            self.assertTrue(self.repository.endpoint in response.url)
            self.assertTrue('api/oauth/authorize' in response.url)
            self.assertTrue('client_id=test-client-id' in response.url)

    @patch('requests.post')
    @patch('requests.get')  # Mock for signal handler
    def test_citesphere_callback_success(self, mock_get, mock_post):
        """Test successful OAuth callback creates account"""
        # Configure mock response for signal
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = [{"user": "citesphere123"}]
        mock_get_response.raise_for_status.return_value = None
        mock_get.return_value = mock_get_response
        
        # Configure mock response for post
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            'access_token': 'new_access',
            'refresh_token': 'new_refresh',
            'expires_in': '3600'
        }
        mock_post.return_value = mock_post_response
        
        # Set up session
        session = self.client.session
        session['oauth_state'] = 'test_state'
        session['oauth_next'] = '/dashboard/'
        session['repository_id'] = self.repository.id
        session.save()
        
        # Make callback request
        with self.settings(BASE_URL='http://testserver/'):
            response = self.client.get(
                reverse('citesphere_callback') + '?code=test_code&state=test_state'
            )
            
            # Check we got redirected to dashboard
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, '/vogon/accounts/profile/')
            
            # Check account was created
            self.assertTrue(CitesphereAccount.objects.filter(
                user=self.user,
                repository=self.repository
            ).exists())

    @patch('requests.post')
    @patch('requests.get')  # Mock for signal handler
    def test_citesphere_refresh_token_success(self, mock_get, mock_post):
        """Test successful token refresh"""
        # Configure mock response for signal
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = [{"user": "citesphere123"}]
        mock_get_response.raise_for_status.return_value = None
        mock_get.return_value = mock_get_response
        
        # Create account with expired token
        old_account = CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='citesphere123',
            access_token='old_access',
            refresh_token='old_refresh',
            token_expires_at=timezone.now() - timedelta(minutes=5),
            extra_data='{}'
        )
        
        # Configure mock response for post
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            'access_token': 'new_access',
            'refresh_token': 'new_refresh',
            'expires_in': '3600'
        }
        mock_post.return_value = mock_post_response
        
        # Make refresh request
        response = self.client.get(
            reverse('citesphere_refresh_token', args=[self.repository.id]) + '?next=/dashboard/'
        )
        
        # Check we got redirected
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/dashboard/')
        
        # Check token was updated
        old_account.refresh_from_db()
        self.assertEqual(old_account.access_token, 'new_access')
        self.assertEqual(old_account.refresh_token, 'new_refresh')

    @patch('requests.get')  # Mock for signal handler
    def test_citesphere_disconnect(self, mock_get):
        """Test disconnecting Citesphere account"""
        # Configure mock response for signal
        mock_response = MagicMock()
        mock_response.json.return_value = [{"user": "citesphere123"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Create account
        CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='citesphere123',
            access_token='access123',
            refresh_token='refresh123',
            token_expires_at=timezone.now() + timedelta(hours=1),
            extra_data='{}'
        )
        
        # Make disconnect request
        response = self.client.get(reverse('citesphere_disconnect', args=[self.repository.id]))
        
        # Check we got redirected
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        
        # Check account was deleted
        self.assertFalse(CitesphereAccount.objects.filter(
            user=self.user,
            repository=self.repository
        ).exists())
