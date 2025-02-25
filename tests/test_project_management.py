import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path to import script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ld_project_setup import create_or_get_project, list_projects, get_project

class TestProjectManagement(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'LD_API_KEY': 'fake-api-key',
            'SERVICENOW_TEMPLATE_SYS_ID': 'fake-template-id'
        })
        self.env_patcher.start()
        
        # Sample test data
        self.config = {
            'project': {
                'name': 'Test Project',
                'key': 'test-project',
                'tags': ['test']
            }
        }
        
        # Reset the project cache before each test
        import ld_project_setup
        ld_project_setup._cached_projects = None
        
    def tearDown(self):
        self.env_patcher.stop()
        
        # Reset the project cache after each test
        import ld_project_setup
        ld_project_setup._cached_projects = None

    @patch('requests.get')
    @patch('builtins.input')
    def test_project_caching(self, mock_input, mock_get):
        """Test project list caching functionality"""
        # Mock paginated API responses
        first_page = MagicMock()
        first_page.status_code = 200
        first_page.json.return_value = {
            'items': [
                {'name': 'Project 1', 'key': 'project-1'},
                {'name': 'Project 2', 'key': 'project-2'}
            ]
        }
        
        empty_page = MagicMock()
        empty_page.status_code = 200
        empty_page.json.return_value = {
            'items': []
        }
        
        mock_get.side_effect = [first_page, empty_page]  # First call gets items, second call gets empty page to end pagination
        
        # First call should hit the API (will make two requests due to pagination)
        projects = list_projects()
        self.assertEqual(len(projects), 2)
        self.assertTrue(mock_get.called)
        self.assertEqual(mock_get.call_count, 2)  # One for first page, one for empty page
        mock_get.reset_mock()
        
        # Second call should use cache
        mock_input.return_value = 'no'  # Don't refresh cache
        projects = list_projects()
        self.assertEqual(len(projects), 2)
        self.assertFalse(mock_get.called)  # API should not be called
        
        # Force refresh should hit API again (two more requests)
        mock_input.return_value = 'yes'  # Refresh cache
        mock_get.side_effect = [first_page, empty_page]  # Reset side effect for new calls
        projects = list_projects()
        self.assertEqual(len(projects), 2)
        self.assertTrue(mock_get.called)
        self.assertEqual(mock_get.call_count, 2)  # Two more API calls for pagination

    @patch('requests.post')
    @patch('requests.get')
    @patch('builtins.input')
    def test_create_new_project(self, mock_input, mock_get, mock_post):
        """Test creating a new project"""
        # Mock get project returns None (project doesn't exist)
        mock_get_response = MagicMock()
        mock_get_response.status_code = 404
        mock_get.return_value = mock_get_response
        
        # Mock successful project creation
        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {
            'name': 'Test Project',
            'key': 'test-project',
            'tags': ['test']
        }
        mock_post.return_value = mock_post_response
        
        # Create new project
        project = create_or_get_project(self.config)
        
        # Verify project was created
        self.assertTrue(mock_post.called)
        self.assertEqual(project['name'], 'Test Project')
        self.assertEqual(project['key'], 'test-project')
        
        # Verify API call
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['name'], 'Test Project')
        self.assertEqual(payload['key'], 'test-project')
        self.assertEqual(payload['tags'], ['test'])

    @patch('requests.get')
    @patch('builtins.input')
    def test_use_existing_project(self, mock_input, mock_get):
        """Test using an existing project"""
        # Mock get project returns existing project
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'name': 'Test Project',
            'key': 'test-project',
            'tags': ['test']
        }
        mock_get.return_value = mock_response
        
        # Mock user input to use existing project
        mock_input.return_value = 'yes'
        
        # Try to create project
        project = create_or_get_project(self.config)
        
        # Verify existing project was returned
        self.assertEqual(project['name'], 'Test Project')
        self.assertEqual(project['key'], 'test-project')
        
        # Verify no POST request was made
        self.assertTrue(mock_get.called)
        self.assertEqual(mock_get.call_count, 1)

    @patch('requests.get')
    def test_get_project(self, mock_get):
        """Test getting a project by key"""
        # Mock successful project retrieval
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'name': 'Test Project',
            'key': 'test-project',
            'tags': ['test']
        }
        mock_get.return_value = mock_response
        
        # Get project
        project = get_project('test-project')
        
        # Verify project was retrieved
        self.assertEqual(project['name'], 'Test Project')
        self.assertEqual(project['key'], 'test-project')
        
        # Test non-existent project
        mock_response.status_code = 404
        project = get_project('non-existent')
        self.assertIsNone(project)

if __name__ == '__main__':
    unittest.main()
