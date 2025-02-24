import requests
import json
import time
import os
import sys
import signal
import yaml
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variables
API_KEY = os.getenv('LD_API_KEY')
if not API_KEY:
    raise ValueError("LD_API_KEY not found in environment variables")

# ServiceNow template ID is now optional
SERVICENOW_TEMPLATE_SYS_ID = os.getenv('SERVICENOW_TEMPLATE_SYS_ID')

BASE_URL = 'https://app.launchdarkly.com/api/v2'

headers = {
    'Authorization': API_KEY,
    'Content-Type': 'application/json'
}

# Set up logging
def setup_logging():
    """Configure logging to both file and console"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Create a timestamp for the log file name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'logs/launchdarkly_setup_{timestamp}.log'

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # This will also print to console
        ]
    )
    return log_file

def load_config(config_path='config.yml'):
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML configuration: {str(e)}")
        raise ValueError(f"Error parsing YAML configuration: {str(e)}")

def handle_response(response, operation):
    """Handle API response and check for errors"""
    try:
        response.raise_for_status()
        # Log the successful response
        logging.info(f"Successfully completed {operation}")
        logging.debug(f"Response for {operation}: {response.text}")
        
        # For successful DELETE operations (204 No Content)
        if response.status_code == 204:
            return None
        return response.json()
    except requests.exceptions.RequestException as e:
        error_msg = f"Error during {operation}:"
        logging.error(error_msg)
        logging.error(f"Status code: {response.status_code}")
        logging.error(f"Response body: {response.text}")
        raise Exception(f"API error during {operation}: {str(e)}")

def list_projects():
    """List all projects with pagination"""
    all_projects = []
    offset = 0
    limit = 20  # LaunchDarkly's default limit
    
    while True:
        url = f'{BASE_URL}/projects?limit={limit}&offset={offset}'
        response = requests.get(url, headers=headers)
        result = handle_response(response, f"listing projects (offset: {offset})")
        
        items = result.get('items', [])
        if not items:
            break
            
        all_projects.extend(items)
        offset += limit
        
        # Show progress
        print(f"Fetching projects... ({len(all_projects)} found)", end='\r')
        
        time.sleep(1)  # Rate limiting
    
    print("\n")  # Clear the progress line
    return all_projects

def get_project(project_key):
    """Get a project by key"""
    # Ensure key is lowercase
    project_key = project_key.lower()
    url = f'{BASE_URL}/projects/{project_key}'
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            return None
        result = handle_response(response, f"getting project ({project_key})")
        time.sleep(1)
        return result
    except Exception as e:
        logging.warning(f"Error retrieving project {project_key}: {str(e)}")
        return None

def list_environments(project_key):
    """List all environments in a project"""
    # Ensure key is lowercase
    project_key = project_key.lower()
    url = f'{BASE_URL}/projects/{project_key}/environments'
    response = requests.get(url, headers=headers)
    result = handle_response(response, "listing environments")
    time.sleep(1)
    return result.get('items', [])

def get_environment(project_key, env_key):
    """Get environment details"""
    # Ensure keys are lowercase
    project_key = project_key.lower()
    env_key = env_key.lower()
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    response = requests.get(url, headers=headers)
    result = handle_response(response, f"getting environment ({env_key})")
    time.sleep(1)
    return result

def delete_environment(project_key, env_key):
    """Delete an environment from a project"""
    # Ensure keys are lowercase
    project_key = project_key.lower()
    env_key = env_key.lower()
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    response = requests.delete(url, headers=headers)
    handle_response(response, f"deleting environment ({env_key})")
    time.sleep(1)
    
def get_user_confirmation(prompt, default=None):
    """Get user confirmation with yes/no prompt and optional default"""
    default_text = ""
    if default is not None:
        default_text = f" (default: {'yes' if default else 'no'})"
        
    while True:
        response = input(f"{prompt}{default_text} (yes/no/quit): ").lower().strip()
        if response == 'quit':
            print("\nExiting script...")
            sys.exit(0)
        if response == '' and default is not None:
            return default
        if response in ['yes', 'no']:
            return response == 'yes'
        print("Please enter 'yes', 'no', or 'quit'")

def get_user_choice(prompt, options):
    """Get user choice from a list of options"""
    print(prompt)
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")
    
    while True:
        try:
            choice = input("Enter your choice (number) or 'quit' to exit: ").strip()
            if choice.lower() == 'quit':
                print("\nExiting script...")
                sys.exit(0)
            choice = int(choice)
            if 1 <= choice <= len(options):
                return options[choice-1]
            else:
                print(f"Please enter a number between 1 and {len(options)}")
        except ValueError:
            print("Please enter a valid number or 'quit'")

def get_user_input(prompt, default=None):
    """Get user input with optional default value"""
    if default:
        response = input(f"{prompt} (default: {default}, or 'quit' to exit): ").strip()
        if response.lower() == 'quit':
            print("\nExiting script...")
            sys.exit(0)
        return response if response else default
    else:
        while True:
            response = input(f"{prompt} (or 'quit' to exit): ").strip()
            if response.lower() == 'quit':
                print("\nExiting script...")
                sys.exit(0)
            if response:
                return response
            print("Please provide a value")

def display_projects(projects):
    """Display projects in a paginated view"""
    total = len(projects)
    page_size = 20
    current_page = 0
    
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, total)
        
        print(f"\nProjects (showing {start_idx + 1}-{end_idx} of {total}):")
        for i, project in enumerate(projects[start_idx:end_idx], start_idx + 1):
            print(f"{i}. {project['name']} ({project['key']})")
        
        print("\nNavigation:")
        print("n - next page")
        print("p - previous page")
        print("c - continue to next step")
        print("q - quit")
        
        choice = input("\nEnter your choice: ").lower().strip()
        
        if choice == 'q':
            print("\nExiting script...")
            sys.exit(0)
        elif choice == 'n' and end_idx < total:
            current_page += 1
        elif choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice == 'c':
            break
        else:
            if choice == 'n' and end_idx >= total:
                print("\nAlready at last page")
            elif choice == 'p' and current_page <= 0:
                print("\nAlready at first page")
            else:
                print("\nInvalid choice")
            time.sleep(1)

def select_projects(projects):
    """Get user selection of projects"""
    selected_projects = []
    total = len(projects)
    page_size = 20
    current_page = 0
    
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, total)
        
        print(f"\nProjects (showing {start_idx + 1}-{end_idx} of {total}):")
        for i, project in enumerate(projects[start_idx:end_idx], start_idx + 1):
            print(f"{i}. {project['name']} ({project['key']})")
        
        print("\nNavigation:")
        print("n - next page")
        print("p - previous page")
        print("s - select projects on this page")
        print("d - done selecting")
        print("q - quit")
        
        choice = input("\nEnter your choice: ").lower().strip()
        
        if choice == 'q':
            print("\nExiting script...")
            sys.exit(0)
        elif choice == 'n' and end_idx < total:
            current_page += 1
        elif choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice == 's':
            print("\nEnter project numbers to select (comma-separated):")
            try:
                selections = [int(x.strip()) for x in input().split(',')]
                for sel in selections:
                    if 1 <= sel <= total and projects[sel-1] not in selected_projects:
                        selected_projects.append(projects[sel-1])
                print(f"Currently selected: {len(selected_projects)} projects")
            except ValueError:
                print("Please enter valid numbers")
                time.sleep(1)
        elif choice == 'd':
            if selected_projects:
                return selected_projects
            print("Please select at least one project")
            time.sleep(1)
        else:
            if choice == 'n' and end_idx >= total:
                print("\nAlready at last page")
            elif choice == 'p' and current_page <= 0:
                print("\nAlready at first page")
            else:
                print("\nInvalid choice")
            time.sleep(1)

def select_environments_for_project(environments):
    """Select environments from a specific project"""
    if not environments:
        return []
        
    print("\nAvailable environments:")
    for i, env in enumerate(environments, 1):
        print(f"{i}. {env['name']} ({env['key']})")
    
    selected_envs = []
    while True:
        print("\nEnter environment numbers to select (comma-separated), or 'all'/'done':")
        response = input().lower().strip()
        
        if response == 'quit':
            print("\nExiting script...")
            sys.exit(0)
        
        if response == 'all':
            return environments
            
        if response == 'done':
            if selected_envs:
                return selected_envs
            print("Please select at least one environment")
            continue
        
        try:
            selections = [int(x.strip()) for x in response.split(',')]
            for sel in selections:
                if 1 <= sel <= len(environments) and environments[sel-1] not in selected_envs:
                    selected_envs.append(environments[sel-1])
            print(f"Currently selected: {', '.join(env['name'] for env in selected_envs)}")
        except ValueError:
            print("Please enter valid numbers")

def get_environment_keys():
    """Get environment keys from user input"""
    print("\nEnter environment keys to process (comma-separated), or 'all' for all environments:")
    print("Common environment keys: production, staging, development, test")
    while True:
        response = input().lower().strip()
        
        if response == 'quit':
            print("\nExiting script...")
            sys.exit(0)
        
        if response == 'all':
            return None  # None means all environments
        
        if response:
            env_keys = [key.strip() for key in response.split(',')]
            print(f"Selected environments: {', '.join(env_keys)}")
            return env_keys
        
        print("Please enter environment keys or 'all'")

def get_project_environments(project_key, env_keys=None):
    """Get environments for a project, filtered by keys if provided"""
    environments = list_environments(project_key)
    if env_keys is None:
        return environments
    return [env for env in environments if env['key'] in env_keys]

def create_or_get_project(config):
    """Create a new project or get existing one using configuration"""
    project_config = config['project']
    project_key = project_config['key']
    project_name = project_config['name']
    
    # Check if project already exists
    existing_project = get_project(project_key)
    if existing_project:
        logging.info(f"Project with key '{project_key}' already exists")
        
        # Ask user if they want to use the existing project or create a new one with a different key
        use_existing = get_user_confirmation(
            f"Project '{existing_project['name']}' with key '{project_key}' already exists. Do you want to use this existing project?"
        )
        
        if use_existing:
            logging.info(f"Using existing project: {existing_project['name']} ({project_key})")
            return existing_project
        else:
            # Ask for a new project key and name
            print("\nPlease provide new project information:")
            new_project_key = get_user_input("Enter a new project key (must be unique)", f"{project_key}-new")
            new_project_name = get_user_input("Enter a new project name", f"{project_name} (New)")
            
            # Update config with new values
            project_config['key'] = new_project_key
            project_config['name'] = new_project_name
            
            # Recursive call to try with the new key
            return create_or_get_project(config)
    
    # Project doesn't exist, create a new one
    logging.info(f"Creating new project: {project_name} ({project_key})...")
    url = f'{BASE_URL}/projects'
    
    payload = {
        'name': project_name,
        'key': project_key,
        'tags': project_config.get('tags', []),
        'defaultClientSideAvailability': {
            'usingEnvironmentId': True,
            'usingMobileKey': False
        }
    }
    
    logging.debug(f"Project creation payload: {json.dumps(payload, indent=2)}")
    response = requests.post(url, headers=headers, json=payload)
    result = handle_response(response, "project creation")
    time.sleep(1)
    return result

def configure_approval_settings(current_settings=None):
    """Let the user choose and configure the approval system"""
    print("\n=== Approval System Configuration ===")
    
    # Detect existing approval system if any
    current_system = None
    if current_settings:
        current_service_kind = current_settings.get('serviceKind', '')
        if current_service_kind == 'launchdarkly':
            current_system = "LaunchDarkly native approvals"
            print(f"Current approval system: LaunchDarkly native approvals")
        elif current_service_kind == 'service-now' or current_service_kind == 'servicenow':
            current_system = "ServiceNow approvals"
            print(f"Current approval system: ServiceNow approvals")
        else:
            print("Current approval system: None")
    
    # Ask user to choose approval system
    approval_system = get_user_choice(
        "Which approval system would you like to use?",
        ["LaunchDarkly native approvals", "ServiceNow approvals", "No approval system"]
    )
    
    if approval_system == "No approval system":
        logging.info("User selected no approval system")
        return None
    
    # Setup the approval settings with default values
    approval_settings = {
        'required': True,
        'bypass_approvals_for_pending_changes': False,
        'min_num_approvals': 1,
        'can_review_own_request': False,
        'can_apply_declined_changes': True,
        'auto_apply_approved_changes': False,
        'required_approval_tags': [],
        'flags_approval_settings': {
            'required': True,
            'required_approval_tags': [],
            'can_review_own_request': False,
            'min_num_approvals': 1,
            'can_apply_declined_changes': True,
            'allow_delete_scheduled_changes': False
        },
        'segments_approval_settings': {
            'required': True,
            'required_approval_tags': [],
            'can_review_own_request': False,
            'min_num_approvals': 1,
            'can_apply_declined_changes': True
        }
    }
    
    # If there are existing settings, use them as defaults
    if current_settings:
        approval_settings['required'] = current_settings.get('required', True)
        approval_settings['bypass_approvals_for_pending_changes'] = current_settings.get('bypassApprovalsForPendingChanges', False)
        approval_settings['min_num_approvals'] = current_settings.get('minNumApprovals', 1)
        approval_settings['can_review_own_request'] = current_settings.get('canReviewOwnRequest', False)
        approval_settings['can_apply_declined_changes'] = current_settings.get('canApplyDeclinedChanges', True)
        approval_settings['auto_apply_approved_changes'] = current_settings.get('autoApplyApprovedChanges', False)
        approval_settings['required_approval_tags'] = current_settings.get('requiredApprovalTags', [])
        
        # Extract flag and segment settings if available
        if 'flagsApprovalSettings' in current_settings:
            flag_settings = current_settings.get('flagsApprovalSettings', {})
            approval_settings['flags_approval_settings'] = {
                'required': flag_settings.get('required', True),
                'required_approval_tags': flag_settings.get('requiredApprovalTags', []),
                'can_review_own_request': flag_settings.get('canReviewOwnRequest', False),
                'min_num_approvals': flag_settings.get('minNumApprovals', 1),
                'can_apply_declined_changes': flag_settings.get('canApplyDeclinedChanges', True),
                'allow_delete_scheduled_changes': flag_settings.get('allowDeleteScheduledChanges', False)
            }
        
        if 'segmentsApprovalSettings' in current_settings:
            segment_settings = current_settings.get('segmentsApprovalSettings', {})
            approval_settings['segments_approval_settings'] = {
                'required': segment_settings.get('required', True),
                'required_approval_tags': segment_settings.get('requiredApprovalTags', []),
                'can_review_own_request': segment_settings.get('canReviewOwnRequest', False),
                'min_num_approvals': segment_settings.get('minNumApprovals', 1),
                'can_apply_declined_changes': segment_settings.get('canApplyDeclinedChanges', True)
            }
    
    # Now prompt for each setting
    print("\n=== Common Approval Settings ===")
    approval_settings['bypass_approvals_for_pending_changes'] = get_user_confirmation(
        "Allow members with permission to bypass required approvals? [Recommended for emergencies]",
        approval_settings['bypass_approvals_for_pending_changes']
    )
    
    approval_settings['auto_apply_approved_changes'] = get_user_confirmation(
        "Automatically apply changes when approved?",
        approval_settings['auto_apply_approved_changes']
    )
    
    # Configure system-specific settings
    if approval_system == "LaunchDarkly native approvals":
        approval_settings['service_kind'] = 'launchdarkly'
        approval_settings['service_config'] = {}
        
        print("\n=== Flag Approval Settings ===")
        flag_req_type = get_user_choice(
            "Require approvals for which flags?",
            ["All flags", "Flags with specific tags", "No flag approvals required"]
        )
        
        if flag_req_type == "All flags":
            approval_settings['flags_approval_settings']['required'] = True
            approval_settings['flags_approval_settings']['required_approval_tags'] = []
        elif flag_req_type == "Flags with specific tags":
            approval_settings['flags_approval_settings']['required'] = True
            tags_input = get_user_input("Enter comma-separated tags for flag approval requirements")
            approval_settings['flags_approval_settings']['required_approval_tags'] = [tag.strip() for tag in tags_input.split(',')]
        else:
            approval_settings['flags_approval_settings']['required'] = False
        
        if approval_settings['flags_approval_settings']['required']:
            approval_settings['flags_approval_settings']['allow_delete_scheduled_changes'] = get_user_confirmation(
                "Allow deleting scheduled changes without approval?",
                approval_settings['flags_approval_settings']['allow_delete_scheduled_changes']
            )
            
            approval_settings['flags_approval_settings']['can_review_own_request'] = get_user_confirmation(
                "Allow requestors to review their own flag change requests?",
                approval_settings['flags_approval_settings']['can_review_own_request']
            )
            
            approval_settings['flags_approval_settings']['min_num_approvals'] = int(get_user_input(
                "Minimum number of approvals required for flags",
                str(approval_settings['flags_approval_settings']['min_num_approvals'])
            ))
            
            approval_settings['flags_approval_settings']['can_apply_declined_changes'] = not get_user_confirmation(
                "Disable the option to 'Apply Changes' if any reviewers have declined a flag request?",
                not approval_settings['flags_approval_settings']['can_apply_declined_changes']
            )
        
        print("\n=== Segment Approval Settings ===")
        segment_req_type = get_user_choice(
            "Require approvals for which segments?",
            ["All segments", "Segments with specific tags", "No segment approvals required"]
        )
        
        if segment_req_type == "All segments":
            approval_settings['segments_approval_settings']['required'] = True
            approval_settings['segments_approval_settings']['required_approval_tags'] = []
        elif segment_req_type == "Segments with specific tags":
            approval_settings['segments_approval_settings']['required'] = True
            tags_input = get_user_input("Enter comma-separated tags for segment approval requirements")
            approval_settings['segments_approval_settings']['required_approval_tags'] = [tag.strip() for tag in tags_input.split(',')]
        else:
            approval_settings['segments_approval_settings']['required'] = False
        
        if approval_settings['segments_approval_settings']['required']:
            approval_settings['segments_approval_settings']['can_review_own_request'] = get_user_confirmation(
                "Allow requestors to review their own segment change requests?",
                approval_settings['segments_approval_settings']['can_review_own_request']
            )
            
            approval_settings['segments_approval_settings']['min_num_approvals'] = int(get_user_input(
                "Minimum number of approvals required for segments",
                str(approval_settings['segments_approval_settings']['min_num_approvals'])
            ))
            
            approval_settings['segments_approval_settings']['can_apply_declined_changes'] = not get_user_confirmation(
                "Disable the option to 'Apply Changes' if any reviewers have declined a segment request?",
                not approval_settings['segments_approval_settings']['can_apply_declined_changes']
            )
        
        logging.info("User selected LaunchDarkly native approval system")
    else:  # ServiceNow approvals
        approval_settings['service_kind'] = 'service-now'
        
        # Common approval settings
        approval_settings['min_num_approvals'] = int(get_user_input(
            "Minimum number of approvals required",
            str(approval_settings['min_num_approvals'])
        ))
        
        approval_settings['can_review_own_request'] = get_user_confirmation(
            "Should users be allowed to review their own requests?",
            approval_settings['can_review_own_request']
        )
        
        approval_settings['can_apply_declined_changes'] = get_user_confirmation(
            "Should users be allowed to apply declined changes?",
            approval_settings['can_apply_declined_changes']
        )
        
        # Ask if required approval tags should be added
        tag_req_type = get_user_choice(
            "Require approvals for which items?",
            ["All items", "Items with specific tags"]
        )
        
        if tag_req_type == "Items with specific tags":
            tags_input = get_user_input("Enter comma-separated tags")
            approval_settings['required_approval_tags'] = [tag.strip() for tag in tags_input.split(',')]
        
        # Check if SERVICENOW_TEMPLATE_SYS_ID is available
        if not SERVICENOW_TEMPLATE_SYS_ID:
            template_id = get_user_input(
                "ServiceNow Template Sys ID not found in environment variables. Please enter it"
            )
            os.environ['SERVICENOW_TEMPLATE_SYS_ID'] = template_id
        else:
            template_id = SERVICENOW_TEMPLATE_SYS_ID
            
        approval_settings['service_config'] = {
            'template': template_id,
            'detail_column': 'justification'  # Default value from the update script
        }
        logging.info("User selected ServiceNow approval system")
    
    # Check if changing approval systems and confirm
    if current_system and current_system != approval_system:
        change_confirmed = get_user_confirmation(
            f"Warning: You are changing the approval system from {current_system} to {approval_system}. Continue?"
        )
        if not change_confirmed:
            print("Operation cancelled. Keeping the existing approval system.")
            return None
    
    return approval_settings

def update_environment(project_key, env_key, env_config, defaults, global_approval_settings):
    """Update an existing environment with new configuration using JSON Patch"""
    # Ensure keys are lowercase
    project_key = project_key.lower()
    env_key = env_key.lower()
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    
    # Get current environment to see what needs to be updated
    current_env = get_environment(project_key, env_key)
    logging.debug(f"Current environment state for {env_key}: {json.dumps(current_env, indent=2)}")
    
    # Prepare patch operations
    patch_operations = []
    
    # Update approval settings if needed
    if global_approval_settings:
        # If environment has specific approval settings in config, those take precedence
        # Otherwise, use the global settings
        env_approval_settings = env_config.get('approval_settings', global_approval_settings) if env_config else global_approval_settings
        
        # Convert to the format expected by LaunchDarkly API
        approval_settings = {
            'required': env_approval_settings.get('required', True),
            'bypassApprovalsForPendingChanges': env_approval_settings.get('bypass_approvals_for_pending_changes', False),
            'minNumApprovals': env_approval_settings.get('min_num_approvals', 1),
            'canReviewOwnRequest': env_approval_settings.get('can_review_own_request', False),
            'canApplyDeclinedChanges': env_approval_settings.get('can_apply_declined_changes', True),
            'autoApplyApprovedChanges': env_approval_settings.get('auto_apply_approved_changes', False),
            'serviceKind': env_approval_settings.get('service_kind', 'launchdarkly'),
            'serviceConfig': env_approval_settings.get('service_config', {}),
            'requiredApprovalTags': env_approval_settings.get('required_approval_tags', [])
        }
        
        # Handle LaunchDarkly native approval settings
        if approval_settings['serviceKind'] == 'launchdarkly':
            flags_settings = env_approval_settings.get('flags_approval_settings', {})
            segments_settings = env_approval_settings.get('segments_approval_settings', {})
            
            # Configure flag approvals in main approvalSettings
            if flags_settings.get('required', False):
                approval_settings.update({
                    'required': True,
                    'minNumApprovals': flags_settings.get('min_num_approvals', 1),
                    'canReviewOwnRequest': flags_settings.get('can_review_own_request', False),
                    'canApplyDeclinedChanges': flags_settings.get('can_apply_declined_changes', True),
                    'requiredApprovalTags': flags_settings.get('required_approval_tags', [])
                })
            
            # Configure segment approvals under resourceApprovalSettings.segment
            if segments_settings.get('required', False):
                patch_operations.append({
                    'op': 'replace',
                    'path': '/resourceApprovalSettings',
                    'value': {
                        'segment': {
                            'required': True,
                            'bypassApprovalsForPendingChanges': approval_settings.get('bypassApprovalsForPendingChanges', False),
                            'minNumApprovals': segments_settings.get('min_num_approvals', 1),
                            'canReviewOwnRequest': segments_settings.get('can_review_own_request', False),
                            'canApplyDeclinedChanges': segments_settings.get('can_apply_declined_changes', True),
                            'serviceKind': 'launchdarkly',
                            'serviceConfig': {},
                            'requiredApprovalTags': segments_settings.get('required_approval_tags', [])
                        }
                    }
                })
        
        # Log the approval settings we're about to apply
        logging.info(f"Approval settings to apply: {json.dumps(approval_settings, indent=2)}")
        
        # Create a proper JSON Patch operation
        patch_operations.append({
            'op': 'replace',
            'path': '/approvalSettings',
            'value': approval_settings
        })
        
        # If using ServiceNow, also update resourceApprovalSettings
        if approval_settings['serviceKind'] == 'service-now':
            patch_operations.append({
                'op': 'replace',
                'path': '/resourceApprovalSettings',
                'value': approval_settings
            })
    
    # Log the complete patch operations
    logging.info(f"JSON Patch operations: {json.dumps(patch_operations, indent=2)}")
    
    if patch_operations:
        patch_headers = headers.copy()
        patch_headers['Content-Type'] = 'application/json-patch+json'  # Ensure correct content type
        
        # Log the full request we're about to make
        logging.info(f"Making PATCH request to: {url}")
        logging.info(f"With headers: {json.dumps(patch_headers, indent=2)}")
        
        response = requests.patch(url, headers=patch_headers, json=patch_operations)
        result = handle_response(response, f"environment update ({env_key})")
        
        # Check result
        if result:
            logging.info(f"PATCH response: {json.dumps(result, indent=2)}")
        
        # Verify the update was successful
        time.sleep(2)  # Give API time to process
        updated_env = get_environment(project_key, env_key)
        logging.info(f"Environment after update: {json.dumps(updated_env.get('approvalSettings', {}), indent=2)}")
        
        if 'approvalSettings' in updated_env and updated_env['approvalSettings'].get('serviceKind') == approval_settings['serviceKind']:
            logging.info(f"✅ Verified approval settings were successfully applied to {env_key}")
        else:
            logging.error(f"❌ Failed to update approval settings for {env_key}. Updated environment does not contain expected settings.")
        
        time.sleep(1)
        return result
    
    return current_env

def create_environment(project_key, env_config, defaults, global_approval_settings):
    """Create a new environment using configuration"""
    # Ensure keys are lowercase
    project_key = project_key.lower()
    # Also ensure the environment key in the config is lowercase
    if env_config and 'key' in env_config:
        env_config['key'] = env_config['key'].lower()
    url = f'{BASE_URL}/projects/{project_key}/environments'
    
    payload = {
        'name': env_config['name'],
        'key': env_config['key'],
        'color': env_config['color'],
        'tags': env_config.get('tags', defaults.get('environment', {}).get('tags', [])),
        'production': env_config.get('production', False),
        'confirmChanges': env_config.get('confirm_changes', 
                                       defaults.get('environment', {}).get('confirm_changes', False)),
        'requireComments': env_config.get('require_comments', 
                                        defaults.get('environment', {}).get('require_comments', False))
    }
    
    response = requests.post(url, headers=headers, json=payload)
    result = handle_response(response, f"environment creation ({env_config['name']})")
    time.sleep(1)
    
    # If approval settings are configured, update the environment with them
    if global_approval_settings:
        update_environment(project_key, env_config['key'], env_config, defaults, global_approval_settings)
    
    return result

def remove_approval_settings(project_key, env_key, env_name):
    """Remove approval settings from an environment"""
    # Ensure keys are lowercase
    project_key = project_key.lower()
    env_key = env_key.lower()
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    
    # Get current environment
    current_env = get_environment(project_key, env_key)
    
    # Create a standard JSON patch with operations in the RFC 6902 format
    patch_operations = []
    
    # For each settings object, we'll first check if it exists and has required=true
    # If so, we'll add a replace operation to set required=false
    
    if current_env.get('approvalSettings', {}).get('required', False):
        patch_operations.append({
            "op": "replace",
            "path": "/approvalSettings/required",
            "value": False
        })
    
    if current_env.get('resourceApprovalSettings', {}).get('required', False):
        patch_operations.append({
            "op": "replace",
            "path": "/resourceApprovalSettings/required",
            "value": False
        })
    
    if not patch_operations:
        logging.info(f"No approval settings to remove for {env_name}")
        return None
    
    logging.info(f"Applying JSON Patch with {len(patch_operations)} operations for {env_name}")
    logging.debug(f"JSON Patch operations: {json.dumps(patch_operations)}")
    
    # Apply the JSON patch
    patch_headers = headers.copy()
    patch_headers['Content-Type'] = 'application/json'
    
    response = requests.patch(url, headers=patch_headers, json=patch_operations)
    result = handle_response(response, f"removing approval settings for {env_name}")
    time.sleep(1)
    return result

def main():
    # Set up graceful exit on Ctrl+C
    def signal_handler(sig, frame):
        print("\n\nReceived Ctrl+C. Exiting gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Setup logging
        log_file = setup_logging()
        logging.info("Starting LaunchDarkly approval management")
        logging.info(f"Log file: {log_file}")
        
        # Ask if user wants to create a new project or manage existing ones
        operation_mode = get_user_choice(
            "What would you like to do?",
            ["Create a new project and configure environments", 
             "Manage approval systems for existing projects"]
        )
        
        if operation_mode == "Create a new project and configure environments":
            # ===== Project Creation Mode =====
            # Load configuration
            try:
                config_path = get_user_input("Enter the path to your config file", "config.yml")
                config = load_config(config_path)
                logging.info("Configuration loaded successfully")
            except Exception as e:
                logging.error(f"Error loading configuration: {str(e)}")
                print(f"Error loading configuration: {str(e)}")
                return
            
            # Check if production environment exists to get existing approval settings
            existing_project = get_project(config['project']['key'])
            existing_approval_settings = None
            
            if existing_project:
                try:
                    # Get detailed environment settings for production to check for approval system
                    prod_envs = [env for env in list_environments(existing_project['key']) if env['key'] == 'production']
                    if prod_envs:
                        prod_env_details = get_environment(existing_project['key'], 'production')
                        existing_approval_settings = prod_env_details.get('approvalSettings')
                        
                        if existing_approval_settings:
                            logging.info(f"Found existing approval settings with service kind: {existing_approval_settings.get('serviceKind', 'unknown')}")
                except Exception as e:
                    logging.warning(f"Error retrieving existing approval settings: {str(e)}")
            
            # Get global approval settings from user
            print("\nBefore setting up your LaunchDarkly project, let's configure your approval system.")
            print("This will apply to all environments unless overridden in specific environments.")
            global_approval_settings = configure_approval_settings(existing_approval_settings)
            
            # Create project or get existing one with user interaction
            project = create_or_get_project(config)
            project_key = project['key']
            logging.info(f'Using project: {project["name"]} with key: {project_key}')

            # Get default settings
            defaults = config.get('defaults', {})
            remove_test_env = defaults.get('remove_default_test_env', False)

            # List existing environments
            environments = list_environments(project_key)
            logging.info(f"Found {len(environments)} existing environments")
            
            # Delete the test environment if configured to do so and it exists
            if remove_test_env:
                for env in environments:
                    if env['key'] == 'test':
                        logging.info(f"Removing default 'test' environment as specified in config...")
                        delete_environment(project_key, env['key'])
            else:
                logging.info("Keeping default 'test' environment as specified in config...")

            # Get the production environment configuration from our config
            prod_config = next((env for env in config['environments'] if env['key'] == 'production'), None)
            if not prod_config:
                logging.error("Production environment configuration not found in config.yml")
                raise ValueError("Production environment configuration not found in config.yml")

            # Update the existing production environment with our desired settings
            # Check if production environment exists first
            prod_env_exists = any(env['key'] == 'production' for env in environments)
            if prod_env_exists:
                logging.info("Updating production environment settings...")
                update_environment(project_key, 'production', prod_config, defaults, global_approval_settings)
            else:
                logging.info("Production environment doesn't exist, creating it...")
                create_environment(project_key, prod_config, defaults, global_approval_settings)

            # Create all other environments from our config if they don't already exist
            existing_env_keys = set(env['key'] for env in environments)
            for env_config in config['environments']:
                if env_config['key'] != 'production' and env_config['key'] not in existing_env_keys:
                    env = create_environment(project_key, env_config, defaults, global_approval_settings)
                    logging.info(f'Created environment: {env["name"]} with key: {env["key"]}')
                elif env_config['key'] != 'production':
                    logging.info(f"Environment {env_config['name']} with key {env_config['key']} already exists, updating it...")
                    update_environment(project_key, env_config['key'], env_config, defaults, global_approval_settings)

            logging.info("LaunchDarkly project setup completed successfully")
            
        else:
            # ===== Manage Existing Projects Mode =====
            # Get all projects
            projects = list_projects()
            logging.info(f"Found {len(projects)} projects")
            
            if not projects:
                print("No projects found")
                return
            
            print(f"\nFound {len(projects)} projects")
            display_projects(projects)
            
            print("\nWhat action would you like to take?")
            print("1. Configure approval systems")
            print("2. Remove approval systems")
            
            action = get_user_choice("Enter your choice", ["1. Configure approval systems", "2. Remove approval systems"])
            remove_settings = "2" in action
            
            print("\nHow would you like to proceed?")
            print("1. Update specific environments across all/selected projects")
            print("2. Select environments individually for each project")
            
            workflow = get_user_choice("Enter your choice", ["1. Update specific environments", "2. Select environments individually"])
            
            if "1" in workflow:
                # Global environment update
                env_keys = get_environment_keys()
                
                print("\nHow would you like to proceed with projects?")
                print("1. Process all projects")
                print("2. Select specific projects")
                
                project_mode = get_user_choice("Enter your choice", ["1. Process all projects", "2. Select specific projects"])
                target_projects = select_projects(projects) if "2" in project_mode else projects
            else:
                # Project-specific environment selection
                target_projects = select_projects(projects)
            
            # Track statistics
            updated_count = 0
            skipped_count = 0
            error_count = 0
            
            # Process projects
            for project in target_projects:
                project_key = project['key']
                project_name = project['name']
                logging.info(f"\nProcessing project: {project_name} ({project_key})")
                
                try:
                    if "1" in workflow:
                        # Global environment update
                        environments = get_project_environments(project_key, env_keys)
                        if not environments:
                            logging.info(f"No matching environments found in {project_name}")
                            continue
                    else:
                        # Project-specific environment selection
                        print(f"\nSelecting environments for {project_name}")
                        all_envs = get_project_environments(project_key)
                        environments = select_environments_for_project(all_envs)
                    
                    # For the first environment, get existing settings to use as default
                    if environments and not remove_settings:
                        env = environments[0]
                        env_details = get_environment(project_key, env['key'])
                        existing_settings = env_details.get('approvalSettings')
                        
                        # Configure approval settings for this project
                        print(f"\nConfiguring approval settings for project: {project_name}")
                        approval_settings = configure_approval_settings(existing_settings)
                        
                        if approval_settings is None:
                            logging.info(f"Skipping project {project_name} - no approval settings configured")
                            continue
                    
                    for env in environments:
                        env_key = env['key']
                        env_name = env['name']
                        
                        if remove_settings:
                            # Remove approval settings
                            action_desc = "remove workflow approvals from"
                            # For project-specific workflow, confirm each update
                            if "2" in workflow:
                                print(f"\nEnvironment {env_name} in {project_name}: {action_desc}?")
                                if not get_user_confirmation("Would you like to proceed"):
                                    logging.info(f"Skipping environment {env_name} by user choice")
                                    skipped_count += 1
                                    continue
                            
                            logging.info(f"Removing approval settings for {env_name} in {project_name}")
                            remove_approval_settings(project_key, env_key, env_name)
                            updated_count += 1
                            logging.info(f"Successfully processed {env_name}")
                        else:
                            # Update approval settings
                            action_desc = "add/update workflow approvals for"
                            # For project-specific workflow, confirm each update
                            if "2" in workflow:
                                print(f"\nEnvironment {env_name} in {project_name}: {action_desc}?")
                                if not get_user_confirmation("Would you like to proceed"):
                                    logging.info(f"Skipping environment {env_name} by user choice")
                                    skipped_count += 1
                                    continue
                            
                            logging.info(f"Updating approval settings for {env_name} in {project_name}")
                            update_environment(project_key, env_key, None, None, approval_settings)
                            updated_count += 1
                            logging.info(f"Successfully processed {env_name}")
                    
                except Exception as e:
                    logging.error(f"Error processing project {project_name}: {str(e)}")
                    error_count += 1
                    continue
            
            # Log final statistics
            logging.info("\nUpdate complete!")
            logging.info(f"Environments updated: {updated_count}")
            logging.info(f"Environments skipped: {skipped_count}")
            logging.info(f"Errors encountered: {error_count}")
            print("\nUpdate complete!")
            print(f"Environments updated: {updated_count}")
            print(f"Environments skipped: {skipped_count}")
            print(f"Errors encountered: {error_count}")

    except Exception as e:
        logging.error(f"Error during execution: {str(e)}")
        raise

if __name__ == '__main__':
    main()
