from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.db import models
from unittest.mock import patch, MagicMock
from annotations.models import TextCollection, Text
from annotations.forms import ProjectForm
from annotations.views.project_views import (
    view_project,
    edit_project,
    create_project,
    list_projects,
    add_collaborator,
    remove_collaborator,
)

User = get_user_model()

# Helper function to add session and messages to request
def add_session_to_request(request):
    """Add session and messages middleware to request"""
    middleware = SessionMiddleware(lambda x: x)
    middleware.process_request(request)
    request.session.save()
    
    # Add messages storage
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)
    return request


class ViewProjectTest(TestCase):
    """Test the view_project view function"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collaborator@example.com',
            password='password123'
        )
        self.project = TextCollection.objects.create(
            name='Test Project',
            description='Test Project Description',
            ownedBy=self.user
        )
        self.project.collaborators.add(self.collaborator)
        
        # Create some test texts for the project
        for i in range(3):
            text = Text.objects.create(
                title=f'Test Text {i}',
                tokenizedContent=f'Test content {i}',
                uri=f'test:text:{i}',
                content_type='text/plain',
                addedBy=self.user
            )
            self.project.texts.add(text)
        
        # Patch login_required decorator
        self.login_patcher = patch('annotations.views.project_views.login_required', lambda f: f)
        self.login_patcher.start()
    
    def tearDown(self):
        self.login_patcher.stop()
    
    @patch('annotations.views.project_views._annotate_project_counts')
    @patch('annotations.views.project_views.get_user_project_stats')
    @patch('annotations.views.project_views.render')
    def test_view_project_as_owner(self, mock_render, mock_stats, mock_annotate):
        """Test that an owner can view their project"""
        # Setup mocks
        mock_annotate.return_value = TextCollection.objects
        mock_stats.return_value = {
            'user': self.user,
            'annotations_count': 5,
            'relations_count': 2
        }
        mock_render.return_value = MagicMock(status_code=200)
        
        # Create request
        request = self.factory.get(f'/project/{self.project.id}/')
        request.user = self.user
        
        # Call the view
        view_project(request, self.project.id)
        
        # Check the render call
        context = mock_render.call_args[0][2]
        self.assertEqual(context['project'], self.project)
        self.assertEqual(context['title'], self.project.name)
        self.assertIn('owner_stats', context)
        self.assertIn('collaborator_stats', context)
        self.assertIn('texts', context)
    
    @patch('annotations.views.project_views._annotate_project_counts')
    @patch('annotations.views.project_views.get_user_project_stats')
    @patch('annotations.views.project_views.render')
    def test_view_project_as_collaborator(self, mock_render, mock_stats, mock_annotate):
        """Test that a collaborator can view the project"""
        # Setup mocks
        mock_annotate.return_value = TextCollection.objects
        mock_stats.return_value = {
            'user': self.collaborator,
            'annotations_count': 3,
            'relations_count': 1
        }
        mock_render.return_value = MagicMock(status_code=200)
        
        # Create request
        request = self.factory.get(f'/project/{self.project.id}/')
        request.user = self.collaborator
        
        # Call the view
        view_project(request, self.project.id)
        
        # Check the render call
        context = mock_render.call_args[0][2]
        self.assertEqual(context['project'], self.project)
    
    @patch('annotations.views.project_views._annotate_project_counts')
    def test_view_project_unauthorized(self, mock_annotate):
        """Test that an unauthorized user cannot view the project"""
        # Setup mocks
        mock_annotate.return_value = TextCollection.objects
        
        # Create an unauthorized user
        unauthorized_user = User.objects.create_user(
            username='unauthorized',
            email='unauthorized@example.com',
            password='password123'
        )
        
        # Create request
        request = self.factory.get(f'/project/{self.project.id}/')
        request.user = unauthorized_user
        
        # Call the view and expect PermissionDenied
        with self.assertRaises(PermissionDenied):
            view_project(request, self.project.id)
    
    @patch('annotations.views.project_views._annotate_project_counts')
    def test_view_project_not_found(self, mock_annotate):
        """Test handling of project not found"""
        # Setup mocks
        mock_annotate.return_value = TextCollection.objects
        
        # Create request with non-existent project id
        request = self.factory.get('/project/999/')
        request.user = self.user
        
        # Call the view and expect Http404
        with self.assertRaises(Http404):
            view_project(request, 999)


class EditProjectTest(TestCase):
    """Test the edit_project view function"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collaborator@example.com',
            password='password123'
        )
        self.project = TextCollection.objects.create(
            name='Test Project',
            description='Test Project Description',
            ownedBy=self.user
        )
        self.project.collaborators.add(self.collaborator)
        
        # Patch login_required decorator
        self.login_patcher = patch('annotations.views.project_views.login_required', lambda f: f)
        self.login_patcher.start()
    
    def tearDown(self):
        self.login_patcher.stop()
    
    @patch('annotations.views.project_views.render')
    def test_edit_project_get(self, mock_render):
        """Test GET request to edit_project view"""
        # Setup mock
        mock_render.return_value = MagicMock(status_code=200)
        
        # Create request
        request = self.factory.get(f'/project/{self.project.id}/edit/')
        request.user = self.user
        
        # Call the view
        edit_project(request, self.project.id)
        
        # Check the render call
        context = mock_render.call_args[0][2]
        self.assertIsInstance(context['form'], ProjectForm)
        self.assertEqual(context['project'], self.project)
        self.assertEqual(context['title'], f'Editing project: {self.project.name}')
    
    def test_edit_project_post_valid(self):
        """Test POST request with valid data to edit_project view"""
        # Create request with valid form data
        request = self.factory.post(f'/project/{self.project.id}/edit/', {
            'name': 'Updated Project Name',
            'description': 'Updated project description',
        })
        request.user = self.user
        
        # Call the view
        response = edit_project(request, self.project.id)
        
        # Check response is a redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('view_project', args=[self.project.id]))
        
        # Check project was updated
        updated_project = TextCollection.objects.get(pk=self.project.id)
        self.assertEqual(updated_project.name, 'Updated Project Name')
        self.assertEqual(updated_project.description, 'Updated project description')
    
    @patch('annotations.views.project_views.render')
    def test_edit_project_post_invalid(self, mock_render):
        """Test POST request with invalid data to edit_project view"""
        # Setup mock
        mock_render.return_value = MagicMock(status_code=200)
        
        # Create request with invalid form data (empty name)
        request = self.factory.post(f'/project/{self.project.id}/edit/', {
            'name': '',  # Name is required
            'description': 'Updated project description',
        })
        request.user = self.user
        
        # Call the view
        edit_project(request, self.project.id)
        
        # Check the render call
        context = mock_render.call_args[0][2]
        self.assertIn('form', context)
        self.assertFalse(context['form'].is_valid())
        
        # NOTE: This test causes Django to print HTML validation error messages to the console
        # like: <ul class="errorlist"><li>name<ul class="errorlist"><li>This field is required.</li></ul></li></ul>
        # This is normal behavior when testing form validation and isn't an actual test error
    
    def test_edit_project_unauthorized(self):
        """Test that a collaborator cannot edit the project"""
        # Create request
        request = self.factory.get(f'/project/{self.project.id}/edit/')
        request.user = self.collaborator
        
        # Call the view and expect PermissionDenied
        with self.assertRaises(PermissionDenied):
            edit_project(request, self.project.id)
    
    def test_edit_project_not_found(self):
        """Test handling of project not found"""
        # Create request with non-existent project id
        request = self.factory.get('/project/999/edit/')
        request.user = self.user
        
        # Call the view and expect Http404
        with self.assertRaises(Http404):
            edit_project(request, 999)


class CreateProjectTest(TestCase):
    """Test the create_project view function"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        # Patch login_required decorator
        self.login_patcher = patch('annotations.views.project_views.login_required', lambda f: f)
        self.login_patcher.start()
    
    def tearDown(self):
        self.login_patcher.stop()
    
    @patch('annotations.views.project_views.render')
    def test_create_project_get(self, mock_render):
        """Test GET request to create_project view"""
        # Setup mock
        mock_render.return_value = MagicMock(status_code=200)
        
        # Create request
        request = self.factory.get('/project/create/')
        request.user = self.user
        
        # Call the view
        create_project(request)
        
        # Check the render call
        context = mock_render.call_args[0][2]
        self.assertIsInstance(context['form'], ProjectForm)
        self.assertEqual(context['title'], 'Create a new project')
    
    def test_create_project_post_valid(self):
        """Test POST request with valid data to create_project view"""
        # Create request with valid form data
        request = self.factory.post('/project/create/', {
            'name': 'New Project',
            'description': 'New project description',
        })
        request.user = self.user
        
        # Call the view
        response = create_project(request)
        
        # Check that a new project was created
        self.assertTrue(TextCollection.objects.filter(name='New Project').exists())
        new_project = TextCollection.objects.get(name='New Project')
        
        # Check response is a redirect to the new project
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('view_project', args=[new_project.id]))
        
        # Verify project attributes
        self.assertEqual(new_project.ownedBy, self.user)
        self.assertEqual(new_project.description, 'New project description')
    
    @patch('annotations.views.project_views.render')
    def test_create_project_post_invalid(self, mock_render):
        """Test POST request with invalid data to create_project view"""
        # Setup mock
        mock_render.return_value = MagicMock(status_code=200)
        
        # Create request with invalid form data (empty name)
        request = self.factory.post('/project/create/', {
            'name': '',  # Name is required
            'description': 'New project description',
        })
        request.user = self.user
        
        # Call the view
        create_project(request)
        
        # Check the render call
        context = mock_render.call_args[0][2]
        self.assertIn('form', context)
        self.assertFalse(context['form'].is_valid())
        
        # NOTE: This test causes Django to print HTML validation error messages to the console
        # like: <ul class="errorlist"><li>name<ul class="errorlist"><li>This field is required.</li></ul></li></ul>
        # This is normal behavior when testing form validation and isn't an actual test error
        
        # Verify no project was created
        self.assertFalse(TextCollection.objects.filter(description='New project description').exists())


class ListProjectsTest(TestCase):
    """Test the list_projects view function"""
    
    def setUp(self):
        self.factory = RequestFactory()
        
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='password123'
        )
        
        # Create projects owned by test user
        for i in range(3):
            TextCollection.objects.create(
                name=f'Own Project {i}',
                description=f'Own project description {i}',
                ownedBy=self.user
            )
        
        # Create projects owned by another user where test user is collaborator
        for i in range(2):
            project = TextCollection.objects.create(
                name=f'Collab Project {i}',
                description=f'Collab project description {i}',
                ownedBy=self.another_user
            )
            project.collaborators.add(self.user)
        
        # Create projects owned by another user where test user is not involved
        for i in range(2):
            TextCollection.objects.create(
                name=f'Other Project {i}',
                description=f'Other project description {i}',
                ownedBy=self.another_user
            )
        
        # Patch login_required decorator
        self.login_patcher = patch('annotations.views.project_views.login_required', lambda f: f)
        self.login_patcher.start()
    
    def tearDown(self):
        self.login_patcher.stop()
    
    @patch('annotations.views.project_views._annotate_project_counts')
    @patch('annotations.views.project_views.render')
    def test_list_projects(self, mock_render, mock_annotate):
        """Test that list_projects shows only projects the user owns or collaborates on"""
        # Setup mocks
        mock_annotate.return_value = TextCollection.objects
        mock_render.return_value = MagicMock(status_code=200)
        
        # Create a mock return value for the values method
        mock_projects = []
        for project in TextCollection.objects.filter(
            models.Q(ownedBy=self.user) | models.Q(collaborators=self.user)
        ).distinct():
            mock_projects.append({
                'id': project.id,
                'name': project.name,
                'description': project.description
            })
        
        # Mock the values method to return our simplified data
        with patch.object(TextCollection.objects, 'values', return_value=mock_projects):
            # Create request
            request = self.factory.get('/projects/')
            request.user = self.user
            
            # Call the view
            list_projects(request)
            
            # Check the render call
            context = mock_render.call_args[0][2]
            self.assertEqual(context['title'], 'Projects')
            
            # Should contain 5 projects (3 owned + 2 collaborator)
            self.assertEqual(len(context['projects']), 5)
    
    @patch('annotations.views.project_views._annotate_project_counts')
    @patch('annotations.views.project_views.render')
    def test_list_projects_with_redirect_params(self, mock_render, mock_annotate):
        """Test list_projects with redirect parameters for repository text import"""
        # Setup mocks
        mock_annotate.return_value = TextCollection.objects
        mock_render.return_value = MagicMock(status_code=200)
        
        # Create a mock return value for the values method
        mock_projects = []
        for project in TextCollection.objects.filter(
            models.Q(ownedBy=self.user) | models.Q(collaborators=self.user)
        ).distinct():
            mock_projects.append({
                'id': project.id,
                'name': project.name,
                'description': project.description
            })
        
        # Mock the values method to return our simplified data
        with patch.object(TextCollection.objects, 'values', return_value=mock_projects):
            # Create request with redirect parameters
            request = self.factory.get('/projects/?redirect_to_text_import=true&repository_id=1&group_id=2&text_key=abc&file_id=123')
            request.user = self.user
            
            # Call the view
            list_projects(request)
            
            # Check the render call
            context = mock_render.call_args[0][2]
            self.assertTrue(context['redirect_to_text_import'])
            self.assertEqual(context['repository_id'], '1')
            self.assertEqual(context['group_id'], '2')
            self.assertEqual(context['text_key'], 'abc')
            self.assertEqual(context['file_id'], '123')
            self.assertEqual(context['title'], 'Select a Project for to import this text:')


class AddCollaboratorTest(TestCase):
    """Test the add_collaborator view function"""
    
    def setUp(self):
        self.factory = RequestFactory()
        
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collaborator@example.com',
            password='password123'
        )
        self.another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='password123'
        )
        
        # Create a project
        self.project = TextCollection.objects.create(
            name='Test Project',
            description='Test Project Description',
            ownedBy=self.user
        )
        
        # Patch login_required decorator
        self.login_patcher = patch('annotations.views.project_views.login_required', lambda f: f)
        self.login_patcher.start()
    
    def tearDown(self):
        self.login_patcher.stop()
    
    def test_add_collaborator_success(self):
        """Test successfully adding a collaborator to a project"""
        # Create POST request
        request = self.factory.post(f'/project/{self.project.id}/add_collaborator/', {
            'username': 'collaborator'
        })
        request.user = self.user
        
        # Add session and messages
        request = add_session_to_request(request)
        
        # Call the view
        response = add_collaborator(request, self.project.id)
        
        # Check response is a redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('view_project', args=[self.project.id]))
        
        # Check collaborator was added
        self.project.refresh_from_db()
        self.assertIn(self.collaborator, self.project.collaborators.all())
        
        # Check success message was added
        messages = list(request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), f'Successfully added {self.collaborator.username} as a collaborator.')
    
    @patch('annotations.views.project_views.get_object_or_404')
    def test_add_collaborator_user_not_found(self, mock_get_object):
        """Test adding a non-existent collaborator"""
        # Setup the mock to raise Http404
        mock_get_object.side_effect = Http404("User nonexistent not found")
        
        # Create POST request with non-existent username
        request = self.factory.post(f'/project/{self.project.id}/add_collaborator/', {
            'username': 'nonexistent'
        })
        request.user = self.user
        
        # Add session and messages
        request = add_session_to_request(request)
        
        # Call the view and expect Http404
        with self.assertRaises(Http404):
            add_collaborator(request, self.project.id)
    
    def test_add_collaborator_unauthorized(self):
        """Test that a non-owner cannot add collaborators"""
        # Create POST request
        request = self.factory.post(f'/project/{self.project.id}/add_collaborator/', {
            'username': 'anotheruser'
        })
        request.user = self.collaborator  # Not the owner
        
        # Call the view and expect PermissionDenied
        with self.assertRaises(PermissionDenied):
            add_collaborator(request, self.project.id)


class RemoveCollaboratorTest(TestCase):
    """Test the remove_collaborator view function"""
    
    def setUp(self):
        self.factory = RequestFactory()
        
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collaborator@example.com',
            password='password123'
        )
        self.another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='password123'
        )
        
        # Create a project
        self.project = TextCollection.objects.create(
            name='Test Project',
            description='Test Project Description',
            ownedBy=self.user
        )
        
        # Add collaborator
        self.project.collaborators.add(self.collaborator)
        
        # Patch login_required decorator
        self.login_patcher = patch('annotations.views.project_views.login_required', lambda f: f)
        self.login_patcher.start()
    
    def tearDown(self):
        self.login_patcher.stop()
    
    def test_remove_collaborator_success(self):
        """Test successfully removing a collaborator from a project"""
        # Create POST request
        request = self.factory.post(f'/project/{self.project.id}/remove_collaborator/', {
            'username': 'collaborator'
        })
        request.user = self.user
        
        # Add session and messages
        request = add_session_to_request(request)
        
        # Call the view
        response = remove_collaborator(request, self.project.id)
        
        # Check response is a redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('view_project', args=[self.project.id]))
        
        # Check collaborator was removed
        self.project.refresh_from_db()
        self.assertNotIn(self.collaborator, self.project.collaborators.all())
        
        # Check success message was added
        messages = list(request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), f'Successfully removed {self.collaborator.username} from the project.')
    
    @patch('annotations.views.project_views.get_object_or_404')
    def test_remove_collaborator_user_not_found(self, mock_get_object):
        """Test removing a non-existent collaborator"""
        # Setup the mock to raise Http404
        mock_get_object.side_effect = Http404("User nonexistent not found")
        
        # Create POST request with non-existent username
        request = self.factory.post(f'/project/{self.project.id}/remove_collaborator/', {
            'username': 'nonexistent'
        })
        request.user = self.user
        
        # Add session and messages
        request = add_session_to_request(request)
        
        # Call the view and expect Http404
        with self.assertRaises(Http404):
            remove_collaborator(request, self.project.id)
    
    def test_remove_collaborator_unauthorized(self):
        """Test that a non-owner cannot remove collaborators"""
        # Create POST request
        request = self.factory.post(f'/project/{self.project.id}/remove_collaborator/', {
            'username': 'collaborator'
        })
        request.user = self.another_user  # Not the owner
        
        # Call the view and expect PermissionDenied
        with self.assertRaises(PermissionDenied):
            remove_collaborator(request, self.project.id)
