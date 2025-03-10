"""
Tests for the main views.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings

from annotations.models import VogonUser, Text, RelationSet


class HomeViewTest(TestCase):
    """Test the home view."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.home_url = reverse('home')
        
        # Create test data
        self.user = VogonUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create a test Text for the RelationSet
        self.text = Text.objects.create(
            uri="test-uri",
            title="Test Text",
            tokenizedContent="<word>test</word>",
            addedBy=self.user
        )
        
        # Create test RelationSet objects with the correct fields
        self.relation_set = RelationSet.objects.create(
            createdBy=self.user,
            occursIn=self.text,
        )
    
    def test_home_view_GET(self):
        """Test that the home view returns a 200 response."""
        response = self.client.get(self.home_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/home.html')
    
    def test_home_view_context(self):
        """Test that the home view returns the correct context."""
        response = self.client.get(self.home_url)
        
        # Check context variables
        self.assertIn('user_count', response.context)
        self.assertIn('text_count', response.context)
        self.assertIn('relation_count', response.context)
        self.assertIn('appellation_count', response.context)
        self.assertIn('relations', response.context)
        self.assertIn('title', response.context)
        
        # Check counts
        self.assertEqual(response.context['user_count'], 1)
        self.assertEqual(response.context['text_count'], 1)
        self.assertEqual(response.context['title'], 'Build the epistemic web')
        
        # Check that RelationSet objects are in context
        self.assertIn(self.relation_set, response.context['relations'])


class AboutViewTest(TestCase):
    """Test the about view."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.about_url = reverse('about')
    
    def test_about_view_GET(self):
        """Test that the about view returns a 200 response."""
        response = self.client.get(self.about_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/about.html')
    
    def test_about_view_context(self):
        """Test that the about view returns the correct context."""
        response = self.client.get(self.about_url)
        
        self.assertIn('title', response.context)
        self.assertEqual(response.context['title'], 'About VogonWeb')


class RecentActivityViewTest(TestCase):
    """Test the recent activity view."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.activity_url = f'/{settings.APP_ROOT}activity/'
    
    def test_recent_activity_view_GET(self):
        """Test that the recent activity view returns a 200 response."""
        response = self.client.get(self.activity_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'annotations/recent_activity.html')
    
    def test_recent_activity_view_context(self):
        """Test that the recent activity view returns the correct context."""
        response = self.client.get(self.activity_url)
        
        self.assertIn('recent_texts', response.context)
        self.assertEqual(len(response.context['recent_texts']), 0)
