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
project:
  name: "Your Project Name"
  key: "your-project-key"
  tags: ["created-via-api"]

environments:
  - name: "Production"
    key: "production"
    color: "417505"    # Green
    production: true
    confirm_changes: true
    require_comments: true
    approval_settings:
      required: true
      bypass_approvals_for_pending_changes: false
      min_num_approvals: 1
      can_review_own_request: false
      can_apply_declined_changes: true
      auto_apply_approved_changes: true
      service_kind: "servicenow"
      service_config:
        detail_column: "justification"
        template: "${SERVICENOW_TEMPLATE_SYS_ID}"
      required_approval_tags: []

  - name: "Staging"
    key: "staging"
    color: "F5A623"  # Orange
    production: false

  # Additional environments...

defaults:
  environment:
    confirm_changes: false
    require_comments: false
    tags: ["created-via-api"]
  remove_default_test_env: true
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
   - Lists all available projects
   - Offers to configure or remove approval systems
   - Provides flexible environment selection
   - Supports batch operations across multiple projects
   - Shows clear progress and results

For both modes:
- Interactive prompts guide you through the process
- Clear explanations of each setting's impact
- Validation of inputs (e.g., 1-5 approvals)
- Comprehensive error handling
- Detailed logging of all operations

### Managing Workflow Approvals

The `update_workflow_approvals.py` script provides a robust way to manage workflow approvals across your LaunchDarkly projects:

```bash
python update_workflow_approvals.py
```

The script offers two operation modes:

1. **Add ServiceNow Workflow Approvals**
   - Configures environments with ServiceNow integration
   - Sets up all necessary approval settings:
     * Required approvals with minimum count
     * ServiceNow integration configuration
     * Auto-apply and review settings
     * Approval tags and bypass settings

2. **Remove Workflow Approvals**
   - Safely removes approval settings
   - Handles both approvalSettings and resourceApprovalSettings
   - Ensures clean removal of service configurations
   - Maintains environment stability during removal

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

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the terms of the LICENSE file included in the repository.
