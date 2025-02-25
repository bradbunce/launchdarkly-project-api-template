import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path to import script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ld_project_setup import configure_approval_settings, update_environment, remove_approval_settings

class TestApprovalSettings(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'LD_API_KEY': 'fake-api-key',
            'SERVICENOW_TEMPLATE_SYS_ID': 'fake-template-id'
        })
        self.env_patcher.start()
        
        # Sample test data
        self.project_key = 'test-project'
        self.env_key = 'test-env'
        self.env_name = 'Test Environment'
        
    def tearDown(self):
        self.env_patcher.stop()

    @patch('builtins.input')
    def test_configure_launchdarkly_approvals(self, mock_input):
        """Test configuring LaunchDarkly native approvals"""
        # Mock user inputs for LaunchDarkly approval configuration
        mock_input.side_effect = [
            '1',    # Choose LaunchDarkly system
            'yes',  # Allow bypass
            'no',   # Don't auto-apply
            'yes',  # Require flag approvals
            '1',    # All flags
            'no',   # Don't allow delete without approval
            'no',   # Don't allow self-review
            '2',    # 2 minimum approvals for flags
            'yes',  # Prevent applying declined changes
            'yes',  # Require segment approvals
            '1',    # All segments
            'no',   # Don't allow self-review
            '2',    # 2 minimum approvals for segments
            'yes',  # Prevent applying declined changes
            'yes'   # Confirm settings
        ]
        
        # Create minimal existing settings
        existing_settings = {
            'serviceKind': 'launchdarkly',
            'required': True
        }
        
        # Test with existing settings
        settings = configure_approval_settings(existing_settings, self.env_key)
        
        # Verify the settings
        self.assertEqual(settings['service_kind'], 'launchdarkly')
        self.assertTrue(settings['bypass_approvals_for_pending_changes'])
        self.assertFalse(settings['auto_apply_approved_changes'])
        self.assertEqual(settings['min_num_approvals'], 2)
        
        # Verify flag settings
        flag_settings = settings['flags_approval_settings']
        self.assertTrue(flag_settings['required'])
        self.assertEqual(len(flag_settings['required_approval_tags']), 0)
        self.assertEqual(flag_settings['min_num_approvals'], 2)
        self.assertFalse(flag_settings['can_review_own_request'])
        self.assertFalse(flag_settings['can_apply_declined_changes'])
        
        # Verify segment settings
        segment_settings = settings['segments_approval_settings']
        self.assertTrue(segment_settings['required'])
        self.assertEqual(len(segment_settings['required_approval_tags']), 0)
        self.assertEqual(segment_settings['min_num_approvals'], 2)
        self.assertFalse(segment_settings['can_review_own_request'])
        self.assertFalse(segment_settings['can_apply_declined_changes'])

    @patch('builtins.input')
    def test_configure_servicenow_approvals(self, mock_input):
        """Test configuring ServiceNow approvals"""
        # Mock user inputs for ServiceNow approval configuration
        mock_input.side_effect = [
            '2',    # Choose ServiceNow system
            'yes',  # Allow bypass
            'no',   # Don't auto-apply
            '2',    # 2 minimum approvals (as string)
            'yes'   # Confirm settings
        ]
        
        # Create minimal existing settings
        existing_settings = {
            'serviceKind': 'servicenow',
            'required': True,
            'minNumApprovals': 2,  # Set default for get_user_input
            'min_num_approvals': 2  # Set both formats to ensure correct default
        }
        
        # Test with existing settings
        settings = configure_approval_settings(existing_settings, self.env_key)
        
        # Verify the settings
        self.assertEqual(settings['service_kind'], 'servicenow')
        self.assertTrue(settings['bypass_approvals_for_pending_changes'])
        self.assertFalse(settings['auto_apply_approved_changes'])
        self.assertEqual(settings['min_num_approvals'], 2)
        self.assertEqual(settings['service_config']['template'], 'fake-template-id')
        self.assertEqual(settings['service_config']['detail_column'], 'justification')

    @patch('requests.patch')
    @patch('ld_project_setup.get_environment')
    def test_remove_approval_settings(self, mock_get_env, mock_patch):
        """Test removing approval settings"""
        # Mock get_environment responses - first with approvals, then without
        mock_get_env.side_effect = [
            # First call - return environment with approval settings
            {
                'key': self.env_key,
                'name': self.env_name,
                'approvalSettings': {
                    'required': True,
                    'serviceKind': 'launchdarkly'
                },
                'resourceApprovalSettings': {
                    'segment': {
                        'required': True,
                        'serviceKind': 'launchdarkly'
                    }
                }
            },
            # Second call after removal - return environment without approval settings
            {
                'key': self.env_key,
                'name': self.env_name,
                'approvalSettings': {
                    'required': False,
                    'serviceKind': 'launchdarkly'
                },
                'resourceApprovalSettings': {
                    'segment': {
                        'required': False,
                        'serviceKind': 'launchdarkly'
                    }
                }
            }
        ]
    
        # Mock patch response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'approvalSettings': {'required': False},
            'resourceApprovalSettings': {'segment': {'required': False}}
        }
        mock_patch.return_value = mock_response
    
        # Test removing settings
        result = remove_approval_settings(self.project_key, self.env_key, self.env_name)
    
        # Verify the API was called correctly
        self.assertTrue(mock_patch.called)
        call_args = mock_patch.call_args
        self.assertIn('/projects/test-project/environments/test-env', call_args[0][0])
    
        # Verify the patch operations
        patch_operations = call_args[1]['json']
        self.assertTrue(any(op['path'] == '/approvalSettings' for op in patch_operations))
        self.assertTrue(any(op['path'] == '/resourceApprovalSettings' for op in patch_operations))
    
        # Verify all settings are disabled
        for op in patch_operations:
            if op['path'] == '/approvalSettings':
                self.assertFalse(op['value']['required'])
            elif op['path'] == '/resourceApprovalSettings':
                self.assertFalse(op['value']['segment']['required'])

if __name__ == '__main__':
    unittest.main()
