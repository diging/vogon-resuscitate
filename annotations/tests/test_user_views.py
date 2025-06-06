from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import Group
from annotations.models import VogonUser, TextCollection, Text
from django.conf import settings

class UserViewsTest(TestCase):
    """Test cases for user-oriented views"""

    def setUp(self):
        """Set up test data"""
        # Create test users
        self.user_password = 'testpassword123'
        self.user = VogonUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password=self.user_password,
            full_name='Test User',
            affiliation='Test University',
            location='Test Location',
            link='https://example.com',
        )
        
        # Create admin user - use is_admin instead of is_staff
        self.admin_user = VogonUser.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password=self.user_password,
            full_name='Admin User',
            affiliation='Admin University',
            location='Admin Location',
            link='https://admin-example.com',
        )
        self.admin_user.is_admin = True  # This will also make is_staff True via the property
        self.admin_user.save()
        
        # Create vogon admin user
        self.vogon_admin = VogonUser.objects.create_user(
            username='vogonadmin',
            email='vogon@example.com',
            password=self.user_password,
            full_name='Vogon Admin',
            affiliation='Vogon University',
            location='Vogon Location',
            link='https://vogon-example.com',
        )
        self.vogon_admin.vogon_admin = True
        self.vogon_admin.save()

        # Create a Public group if it doesn't exist
        public, _ = Group.objects.get_or_create(name='Public')
        
        # Create test project (TextCollection)
        self.test_project = TextCollection.objects.create(
            name='Test Project',
            description='Test Project Description',
            ownedBy=self.user
        )
        
        # Create a test text
        self.test_text = Text.objects.create(
            title='Test Text',
            uri='test:uri',
            addedBy=self.user,
            tokenizedContent='Test content'
        )
        self.test_project.texts.add(self.test_text)
        
        # Add client for making requests
        self.client = Client()
        
        # NOTE: Timezone warnings are occurring because `created` fields in Relation and Appellation
        # models receive naive datetimes (without timezone info) in tests, but the application has
        # timezone support enabled. This is a common warning in Django testing and doesn't affect
        # the actual test validation, so we're acknowledging it with this comment.
        
        # NOTE: The "Permission denied" warnings that appear during test execution for admin-related
        # tests are expected behavior. Tests like test_list_vogon_admin_users_non_admin_denied and
        # test_toggle_vogon_admin_status_non_admin_denied are specifically designed to verify that
        # non-admin users cannot access admin-only pages. The PermissionDenied exceptions that are
        # raised and logged are part of the expected behavior being tested.
    
    def test_login_view_get(self):
        """Test that login page loads correctly"""
        response = self.client.get(reverse('login_fallback'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/login.html')
    
    def test_login_view_post_valid(self):
        """Test login with valid credentials"""
        response = self.client.post(reverse('login_fallback'), {
            'username': 'testuser',
            'password': self.user_password,
        })
        self.assertEqual(response.status_code, 302)  # Redirect after successful login
        self.assertRedirects(response, reverse('dashboard'))
    
    def test_login_view_post_invalid(self):
        """Test login with invalid credentials"""
        response = self.client.post(reverse('login_fallback'), {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)  # Stays on login page
    
    def test_logout_view(self):
        """Test logout functionality"""
        # First login
        self.client.login(username='testuser', password=self.user_password)
        # Then logout
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)  # Redirect after logout
    
    # Skipping register tests as they're using allauth and not the direct view
    
    def test_user_settings_get(self):
        """Test that settings page loads correctly for logged in user"""
        self.client.login(username='testuser', password=self.user_password)
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/settings.html')
    
    def test_user_settings_post_valid(self):
        """Test updating user settings with valid data"""
        self.client.login(username='testuser', password=self.user_password)
        response = self.client.post(reverse('settings'), {
            'full_name': 'Updated Test User',
            'email': 'updated@example.com',
            'affiliation': 'Updated University',
            'location': 'Updated Location',
            'link': 'https://updated-example.com',
        })
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        # Verify user was updated
        updated_user = VogonUser.objects.get(username='testuser')
        self.assertEqual(updated_user.full_name, 'Updated Test User')
        self.assertEqual(updated_user.email, 'updated@example.com')
    
    def test_user_settings_unauthorized(self):
        """Test that settings page requires login"""
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        # Check that the response is a redirect to a login page
        self.assertTrue('login' in response.url or 'accounts/login' in response.url)
    
    # Skip user_annotated_texts tests since the URL is not defined in URLs config
    
    def test_dashboard_view(self):
        """Test that dashboard loads correctly for logged in user"""
        self.client.login(username='testuser', password=self.user_password)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/dashboard.html')
        
        # Verify context data
        self.assertEqual(response.context['user'], self.user)
        self.assertEqual(list(response.context['projects_owned']), list(self.user.collections.all().values('id', 'name', 'description', 'ownedBy__username')))
    
    def test_dashboard_unauthorized(self):
        """Test that dashboard requires login"""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        # Check that the response is a redirect to a login page
        self.assertTrue('login' in response.url or 'accounts/login' in response.url)
    
    def test_user_details_view(self):
        """Test that user details page loads correctly"""
        response = self.client.get(reverse('user_details', args=[self.user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/user_details_public.html')
        
        # Verify context data
        self.assertEqual(response.context['detail_user'], self.user)
    
    def test_user_projects_view(self):
        """Test that user projects page loads correctly for logged in user"""
        self.client.login(username='testuser', password=self.user_password)
        response = self.client.get(reverse('user_projects'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/project_user.html')
    
    def test_user_projects_unauthorized(self):
        """Test that user projects page requires login"""
        response = self.client.get(reverse('user_projects'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        # Check that the response is a redirect to a login page
        self.assertTrue('login' in response.url or 'accounts/login' in response.url)
    
    def test_list_user_view(self):
        """Test that user list page loads correctly"""
        response = self.client.get(reverse('users'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/contributors.html')
    
    def test_list_user_view_with_search(self):
        """Test user list with search functionality"""
        response = self.client.get(reverse('users') + '?search_term=Test')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/contributors.html')
        
        # Verify search term is in context
        self.assertEqual(response.context['search_term'], 'Test')
    
    def test_list_vogon_admin_users_admin_allowed(self):
        """Test that vogon admin list loads correctly for admin users"""
        self.client.login(username='adminuser', password=self.user_password)
        response = self.client.get(reverse('user_vogon_admin_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/user_vogon_admin_list.html')
    
    def test_list_vogon_admin_users_non_admin_denied(self):
        """Test that vogon admin list denies access to non-admin users"""
        # This test intentionally triggers a PermissionDenied exception, which is expected
        # and will be logged as a warning during test execution
        self.client.login(username='testuser', password=self.user_password)
        response = self.client.get(reverse('user_vogon_admin_list'))
        self.assertEqual(response.status_code, 403)  # Permission denied
    
    def test_toggle_vogon_admin_status_admin_allowed(self):
        """Test toggling vogon admin status by admin user"""
        self.client.login(username='adminuser', password=self.user_password)
        
        # Initial state
        target_user = VogonUser.objects.get(username='testuser')
        self.assertFalse(target_user.vogon_admin)
        
        # Toggle status
        response = self.client.post(reverse('toggle_vogon_admin_status', args=[target_user.id]))
        self.assertEqual(response.status_code, 302)  # Redirect after successful toggle
        
        # Verify status was toggled
        target_user.refresh_from_db()
        self.assertTrue(target_user.vogon_admin)
        
        # Toggle back
        response = self.client.post(reverse('toggle_vogon_admin_status', args=[target_user.id]))
        target_user.refresh_from_db()
        self.assertFalse(target_user.vogon_admin)
    
    def test_toggle_vogon_admin_status_non_admin_denied(self):
        """Test that toggling vogon admin status denies access to non-admin users"""
        # This test intentionally triggers a PermissionDenied exception, which is expected
        # and will be logged as a warning during test execution
        self.client.login(username='testuser', password=self.user_password)
        response = self.client.post(reverse('toggle_vogon_admin_status', args=[self.vogon_admin.id]))
        self.assertEqual(response.status_code, 403)  # Permission denied
