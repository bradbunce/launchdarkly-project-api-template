# LaunchDarkly Project API Template

This project provides an automated setup script for creating and configuring LaunchDarkly projects with multiple environments and specific settings, including workflow approvals with ServiceNow integration.

## Overview

The script (`ld_project_setup.py`) provides two main functions:

1. **Create and Configure New Projects**
   - Creates a new LaunchDarkly project
   - Configures multiple environments (Production, Staging, Testing, Development)
   - Sets up workflow approvals with either LaunchDarkly's native system or ServiceNow integration
   - Configures environment-specific settings like requiring comments and confirming changes
   - Handles environment tags and other customizations

2. **Manage Approval Systems for Existing Projects**
   - Configure or remove approval systems across multiple projects
   - Flexible environment selection (all, specific, or individual)
   - Support for both LaunchDarkly native approvals and ServiceNow integration

## Prerequisites

Before using this script, ensure you have:

1. **ServiceNow Integration Setup**
   - The ServiceNow integration must be enabled and configured on your LaunchDarkly instance
   - Follow the [LaunchDarkly ServiceNow Integration Guide](https://launchdarkly.com/docs/integrations/servicenow) to set this up
   - Once configured, workflow approvals will use ServiceNow on environments where they are defined

2. **Technical Requirements**
   - Python 3.x
   - LaunchDarkly API access token
   - ServiceNow template system ID (obtained after ServiceNow integration setup)
   - Required Python packages (see Installation)

## Installation

1. Clone this repository:
```bash
git clone [repository-url]
cd launchdarkly-project-api-template
```

2. Install required packages:
```bash
pip install requests pyyaml python-dotenv
```

3. Copy the example environment file:
```bash
cp .env.example .env
```

4. Copy the example configuration file:
```bash
cp configy.yml.example config.yml
```

## Configuration

### Environment Variables (.env)

Create a `.env` file with the following variables:
```
LD_API_KEY=your-launchdarkly-api-token
SERVICENOW_TEMPLATE_SYS_ID=your-servicenow-template-id
```

### Project Configuration (config.yml)

The `config.yml` file defines your project structure and settings:

```yaml
# Project configuration
project:
  name: "Example Project Name"
  key: "example-project-key"
  tags: ["created-via-api"]

# Default environment handling
defaults:
  environment:
    confirm_changes: false
    require_comments: false
    tags: ["created-via-api"]
  
  # Control whether to remove the default 'test' environment
  remove_default_test_env: false  # Set to true if you want to remove the default test environment

# Environment configuration
# Note: LaunchDarkly creates two default environments when a project is created:
# - 'production': This environment is required and cannot be deleted. You can update its settings below.
# - 'test': This environment will be kept or deleted based on 'remove_default_test_env' setting above.

environments:
  # Production environment is required. These settings will update the default production environment.
  - name: "Production"
    key: "production"  # Must be 'production' to match default environment
    color: "417505"    # Green
    production: true
    confirm_changes: true
    require_comments: true

  - name: "Staging"
    key: "staging"
    color: "F5A623"  # Orange
    production: false

  - name: "Testing"
    key: "testing"
    color: "0275d8"  # Blue
    production: false

  - name: "Development"
    key: "development"
    color: "666666"  # Gray
    production: false

# Optional: Feature flags configuration
# Uncomment and modify this section to create feature flags
# feature_flags:
#   - key: "enable-new-feature"
#     name: "Enable New Feature"
#     description: "Controls the release of new feature"
#     type: "boolean"
```

### Configuration Options

#### Project Settings
- `name`: Display name of your project
- `key`: Unique identifier for your project (automatically converted to lowercase)
- `tags`: List of tags to apply to the project

#### Environment Settings
- `name`: Display name of the environment
- `key`: Unique identifier for the environment (automatically converted to lowercase)
- `color`: Hex color code for the environment
- `production`: Boolean indicating if this is a production environment
- `confirm_changes`: Require confirmation for flag changes
- `require_comments`: Require comments for flag changes
- `tags`: List of tags to apply to the environment

#### Approval Settings

The script supports comprehensive configuration of approval settings for both LaunchDarkly's native system and ServiceNow integration.

**Common Settings (Both Systems)**:
- `bypass_approvals_for_pending_changes`: Allow bypassing approvals for scheduled changes [Recommended for emergencies]
- `min_num_approvals`: Number of required approvals (1-5)
- `auto_apply_approved_changes`: Automatically apply changes after approval

**LaunchDarkly Native Approvals**:

*Flag Approval Settings*:
- Controls how flag targeting changes are approved in each environment
- Changes to flag variations affect all environments and use the strictest approval settings
- Options:
  - Require approvals for all flags or only flags with specific tags
  - Allow/prevent deleting scheduled changes without approval
  - Allow/prevent self-review of flag changes
  - Set minimum approvals required (1-5)
  - Control behavior when changes are declined

*Segment Approval Settings*:
- Controls how segment targeting changes are approved
- Note: Unlike flags, you cannot bypass required approvals for segments
- Options:
  - Require approvals for all segments or only segments with specific tags
  - Allow/prevent self-review of segment changes
  - Set minimum approvals required (1-5)
  - Control behavior when changes are declined

**ServiceNow Integration**:
- Requires ServiceNow template ID (configured via environment variable)
- Simplified settings focused on ServiceNow's approval flow
- Options:
  - Allow bypassing approvals with proper permissions
  - Set minimum required approvals
  - Configure template and justification settings

#### Default Settings
- `confirm_changes`: Default setting for requiring change confirmation
- `require_comments`: Default setting for requiring comments
- `tags`: Default tags for all environments
- `remove_default_test_env`: Whether to remove the default test environment

## Usage

### Key Case Sensitivity

Both scripts (`ld_project_setup.py` and `update_workflow_approvals.py`) handle case sensitivity automatically:
- Project keys are converted to lowercase before any API operations
- Environment keys are converted to lowercase before any API operations
- This ensures consistency with LaunchDarkly's API requirements
- Display names can still use any case format
- You can use any case in your configuration files - the scripts will handle the conversion

### Using the Script

Run the script:
```bash
python ld_project_setup.py
```

The script will present two options:

1. **Create a new project and configure environments with workflow approvals**
   - Prompts for configuration file path
   - Creates project and environments as specified
   - Offers to configure workflow approvals for each environment
   - Provides clear prompts for all approval settings
   - Generates detailed logs of the process

2. **Manage approval systems for existing projects**
   - Lists all available projects (with efficient caching)
   - Offers to configure or remove approval systems
   - Provides flexible environment selection
   - Supports batch operations across multiple projects
   - Shows clear progress and results

**Performance Optimization**:
- Project list is cached after first fetch
- Subsequent operations reuse cached data
- Option to refresh cache when needed
- Significantly faster for multiple operations

**Interactive Configuration**:
- Step-by-step guidance through each setting
- Clear explanations of each option's impact
- Validation of all inputs (e.g., 1-5 approvals)
- Helpful descriptions of recommended settings
- Option to quit at any point

**Flag Approval Configuration**:
- Configure targeting change approvals
- Set approval requirements (all flags or tagged)
- Control scheduled change deletions
- Set minimum approval counts
- Configure self-review permissions
- Manage declined change behavior

**Segment Approval Configuration**:
- Independent from flag approvals
- Cannot be bypassed (unlike flags)
- Configure targeting change approvals
- Set approval requirements
- Manage review permissions
- Control declined changes

**Common Features**:
- Comprehensive error handling
- Detailed logging of all operations
- Clear progress indicators
- Confirmation prompts for important actions
- Multiple exit points (quit/Ctrl+C)

### Managing Workflow Approvals

The script provides comprehensive workflow approval management:

**LaunchDarkly Native Approvals**:
- Complete control over approval workflows
- Separate flag and segment configurations
- Granular permission settings
- Support for tag-based approvals
- Flexible review requirements

**ServiceNow Integration**:
- Seamless ServiceNow approval flow
- Template-based configuration
- Justification field customization
- Automatic status synchronization
- Emergency bypass options

**Approval Removal**:
- Safe removal of approval settings
- Handles both approval types:
  * Flag targeting approvals
  * Segment targeting approvals
- Maintains environment stability
- Verifies removal success

Two workflow options are available:

1. **Global Environment Update**
   - Update specific environments across multiple projects
   - Options:
     * Enter environment keys (e.g., "production, staging")
     * Use 'all' to process all environments
     * Process all projects or select specific ones
   - Efficient for consistent environment structures

2. **Project-Specific Updates**
   - Granular control over individual projects
   - For each project:
     * View available environments
     * Select specific environments to update
     * Confirm changes individually
   - Ideal for varied environment structures

Common Features:
- Interactive selection of projects and environments
- Clear status messages and confirmations
- Skip detection for already configured environments
- Comprehensive error handling and logging
- Multiple exit points:
  * 'quit' at any prompt
  * Ctrl+C for graceful exit
  * 'done' when finished selecting

Operation Flow:
1. Lists all available projects
2. Allows environment selection based on chosen workflow
3. Verifies current approval settings
4. Applies changes with proper error handling
5. Provides detailed operation statistics:
   - Number of environments updated
   - Number of environments skipped
   - Any errors encountered

The script maintains consistency by:
- Checking existing settings before modifications
- Ensuring matching configurations between approval types
- Using standardized PATCH operations for reliability
- Providing detailed logs of all operations

Both scripts use the same environment variables and logging system, making them easy to use together or independently.

## Logging

The script creates detailed logs in the `logs/` directory with timestamps. Each log file contains information about:
- Script execution progress
- API responses
- Any errors or issues encountered

## Error Handling

The script includes comprehensive error handling for:
- Missing environment variables
- Invalid configuration files
- API request failures
- Invalid responses

Errors are both logged to files and displayed in the console.

## Testing

The project includes a comprehensive test suite that verifies core functionality without making actual API calls.

### Test Structure

1. **Approval Settings Tests** (`tests/test_approval_settings.py`):
   - LaunchDarkly native approval configuration
     * Flag approval settings
     * Segment approval settings
     * Minimum approval requirements
     * Self-review permissions
   - ServiceNow approval configuration
     * Template integration
     * Approval requirements
     * Bypass settings
   - Approval settings removal
     * Clean removal of all settings
     * Environment stability checks
   - User input handling and validation

2. **Project Management Tests** (`tests/test_project_management.py`):
   - Project list caching functionality
     * Initial fetch behavior
     * Cache reuse verification
     * Cache refresh operations
   - Project creation and retrieval
     * New project creation
     * Existing project handling
     * Project key validation
   - API interaction verification
     * Request formatting
     * Response handling
     * Error scenarios

### Development Testing

For developers working on the project:

1. **Setup Test Environment**:
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   
   # Install development dependencies
   pip install requests pyyaml python-dotenv pytest
   ```

2. **Run Tests**:
   ```bash
   # Run all tests with detailed output
   cd tests
   python run_tests.py
   
   # Run specific test file
   python -m unittest test_approval_settings.py
   
   # Run specific test case
   python -m unittest test_approval_settings.py -k test_configure_launchdarkly_approvals
   ```

3. **Test Output**:
   - Detailed test execution logs
   - Summary of passed/failed tests
   - Coverage statistics
   - Exit codes for CI/CD integration

### Test Coverage

The test suite provides comprehensive coverage of:

1. **Core Functionality**:
   - Project management operations
   - Approval system configuration
   - Environment management
   - Settings validation

2. **Edge Cases**:
   - Invalid inputs
   - API error responses
   - Cache invalidation
   - Configuration conflicts

3. **User Interactions**:
   - Input validation
   - Confirmation prompts
   - Error messages
   - Progress indicators

### Mock Implementation

All tests use mocking to avoid real API calls:
- Simulated API responses
- User input simulation
- Environment variable handling
- File system operations

This ensures:
- Tests run quickly and reliably
- No accidental modifications to real resources
- Consistent test environment
- Predictable test outcomes

### Adding New Tests

When adding new functionality:

1. Create test cases that verify:
   - Happy path execution
   - Error handling
   - Edge cases
   - User input validation

2. Follow existing patterns for:
   - Mock setup
   - Test organization
   - Assertion style
   - Documentation

3. Ensure tests are:
   - Independent
   - Deterministic
   - Well-documented
   - Performance-conscious

## Contributing

Feel free to submit issues and enhancement requests!

When contributing code:
1. Ensure all tests pass
2. Add tests for new functionality
3. Follow existing code style
4. Update documentation as needed

## License

This project is licensed under the terms of the LICENSE file included in the repository.
