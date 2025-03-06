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
from .views import citesphere_login, citesphere_callback, citesphere_refresh_token, citesphere_disconnect

User = get_user_model()

class CitesphereAccountModelTests(TestCase):
    def setUp(self):
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
        self.account = CitesphereAccount.objects.create(
            user=self.user,
            repository=self.repository,
            citesphere_user_id='citesphere123',
            access_token='access123',
            refresh_token='refresh123',
            token_expires_at=timezone.now() + timedelta(hours=1),
            extra_data=json.dumps({"scope": "read"})
        )

    def test_string_representation(self):
        """Test the string representation of CitesphereAccount"""
        expected = f"Citesphere account:{self.user.username} Repository: {self.repository.name}"
        self.assertEqual(str(self.account), expected)

    def test_is_token_expired_not_expired(self):
        """Test is_token_expired returns False when token is not expired"""
        self.assertFalse(self.account.is_token_expired())

    def test_is_token_expired_when_expired(self):
        """Test is_token_expired returns True when token is expired"""
        self.account.token_expires_at = timezone.now() - timedelta(minutes=5)
        self.account.save()
        self.assertTrue(self.account.is_token_expired())

    def test_extra_data_json_property(self):
        """Test the extra_data_json property getter and setter"""
        test_data = {"key": "value", "list": [1, 2, 3]}
        self.account.extra_data_json = test_data
        self.assertEqual(self.account.extra_data, json.dumps(test_data))
        self.assertEqual(self.account.extra_data_json, test_data)

    @patch('requests.get')
    def test_post_save_signal_fetch_citesphere_user_id(self, mock_get):
        """Test the post_save signal to fetch citesphere_user_id"""
        # Set up the mock
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
        mock_get.assert_called_once_with(
            f'{self.repository.endpoint}/api/v1/test/',
            headers={'Authorization': f'Bearer {new_account.access_token}'}
        )

        # Refresh from database
        new_account.refresh_from_db()
        
        # Verify citesphere_user_id was updated
        self.assertEqual(new_account.citesphere_user_id, "new_user_id")

