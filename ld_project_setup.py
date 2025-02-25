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

# Global cache for projects
_cached_projects = None

def list_projects(force_refresh=False):
    """List all projects with pagination, using cache if available"""
    global _cached_projects
    
    # Check if we have cached projects and not forcing refresh
    if _cached_projects is not None and not force_refresh:
        print("\nUsing cached project list...")
        if get_user_confirmation("Would you like to refresh the project list instead?", False):
            force_refresh = True
        else:
            return _cached_projects
    
    if force_refresh:
        print("\nRefreshing project list...")
    else:
        print("\nFetching projects...")
    
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
        print(f"Found {len(all_projects)} projects...", end='\r')
        
        time.sleep(1)  # Rate limiting
    
    print("\n")  # Clear the progress line
    
    # Cache the results
    _cached_projects = all_projects
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

def configure_approval_settings(current_settings=None, env_key=None):
    """Let the user choose and configure the approval system for a specific environment"""
    print("\n" + "="*50)
    print("APPROVAL SYSTEM CONFIGURATION")
    print("="*50)
    
    # Detect existing approval system
    current_system = None
    if current_settings:
        current_service_kind = current_settings.get('serviceKind', '')
        if current_service_kind == 'launchdarkly':
            current_system = "LaunchDarkly approval system"
            print(f"Current approval system: {current_system}")
        elif current_service_kind in ['servicenow', 'servicenow-normal', 'service-now']:
            current_system = "ServiceNow approvals"
            print(f"Current approval system: {current_system}")
        else:
            print("Current approval system: None")
    
    # Setup the approval settings with default values
    service_kind = current_settings.get('serviceKind', 'launchdarkly')
    if service_kind in ['service-now', 'servicenow-normal']:
        service_kind = 'servicenow'  # Normalize ServiceNow values
    
    # All settings default to "no" or most restrictive option
    approval_settings = {
        'required': True,  # Must be true for approvals to work
        'bypass_approvals_for_pending_changes': False,
        'min_num_approvals': 1,  # Must be at least 1 per API requirements
        'can_review_own_request': False,
        'can_apply_declined_changes': False,
        'auto_apply_approved_changes': False,
        'required_approval_tags': [],
        'service_kind': service_kind,
        'service_config': {},
        'flags_approval_settings': {
            'required': False,
            'required_approval_tags': [],
            'can_review_own_request': False,
            'min_num_approvals': 1,  # Must be at least 1 per API requirements
            'can_apply_declined_changes': False,
            'allow_delete_scheduled_changes': False
        },
        'segments_approval_settings': {
            'required': False,
            'required_approval_tags': [],
            'can_review_own_request': False,
            'min_num_approvals': 1,  # Must be at least 1 per API requirements
            'can_apply_declined_changes': False
        }
    }
    
    # Common approval settings
    print("\n" + "-"*50)
    print("COMMON APPROVAL SETTINGS")
    print("-"*50)
    
    approval_settings['bypass_approvals_for_pending_changes'] = get_user_confirmation(
        "Allow members with bypass permission to skip approval requirements? [Recommended for emergency situations]",
        False
    )
    
    approval_settings['auto_apply_approved_changes'] = get_user_confirmation(
        "Automatically apply changes when approved? [Changes will be applied without manual intervention]",
        False
    )
    
    # Configure system-specific settings
    if service_kind == 'launchdarkly':
        # We're configuring for a specific environment, so we set that environment as enabled
        # instead of asking for environment selection again
        if env_key:
            approval_settings['enabled_environments'] = [env_key]
        
        # ==== FLAG APPROVAL SETTINGS ====
        print("\n" + "-"*50)
        print("FLAG APPROVAL SETTINGS")
        print("-"*50)
        print("These settings control how flag targeting changes are approved in this environment.")
        print("Note: Changes to flag variations affect ALL environments in a project and use the strictest approval settings.")
        
        # First ask if flag approvals are required
        approval_settings['flags_approval_settings']['required'] = get_user_confirmation(
            "Require approvals for flag targeting changes? [When enabled, users must request approval for targeting changes]",
            False
        )
        
        if approval_settings['flags_approval_settings']['required']:
            # Ask about scope of flag approvals
            flag_req_type = get_user_choice(
                "Which flags require approval?",
                ["All flags (recommended for critical environments)", 
                 "Only flags with specific tags (more flexible)"]
            )
            
            if flag_req_type == "All flags (recommended for critical environments)":
                approval_settings['flags_approval_settings']['required_approval_tags'] = []
            else:  # Flags with specific tags
                print("\nFlags with specified tags will require approval for targeting changes.")
                print("Example tags: 'critical', 'customer-facing', 'financial'")
                print("Note: While tags are global across environments, this setting applies only to flags in this environment.")
                tags_input = get_user_input("Enter comma-separated tags for flag approval requirements")
                approval_settings['flags_approval_settings']['required_approval_tags'] = [tag.strip() for tag in tags_input.split(',')]
            
            # Configure scheduled changes
            print("\nScheduled changes are targeting changes that are set to apply at a future date.")
            approval_settings['flags_approval_settings']['allow_delete_scheduled_changes'] = get_user_confirmation(
                "Allow deleting scheduled changes without approval? [If enabled, users can cancel scheduled changes without approval]",
                False
            )
            
            # Configure self-review
            print("\nSelf-review allows requesters to approve their own changes.")
            approval_settings['flags_approval_settings']['can_review_own_request'] = get_user_confirmation(
                "Allow requesters to review their own flag change requests? [If enabled, users can approve their own changes]",
                False
            )
            
            # Configure minimum approvals (1-5)
            print("\nSpecify the minimum number of approvals required before a flag change can be applied.")
            while True:
                min_approvals = int(get_user_input(
                    "Minimum number of approvals required for flags (1-5)",
                    str(approval_settings['flags_approval_settings']['min_num_approvals'])
                ))
                if 1 <= min_approvals <= 5:
                    approval_settings['flags_approval_settings']['min_num_approvals'] = min_approvals
                    break
                print("Please enter a number between 1 and 5")
            
            # Configure declined changes behavior
            print("\nConfigure what happens when a reviewer declines a change request.")
            approval_settings['flags_approval_settings']['can_apply_declined_changes'] = not get_user_confirmation(
                "Prevent applying changes if any reviewer has declined? [If enabled, changes cannot be applied if any reviewer declines]",
                True  # Default to NOT allowing changes to be applied if declined (most secure)
            )
        
        # ==== SEGMENT APPROVAL SETTINGS ====
        print("\n" + "-"*50)
        print("SEGMENT APPROVAL SETTINGS")
        print("-"*50)
        print("These settings control how segment targeting changes are approved in this environment.")
        print("Note: Unlike flags, you cannot bypass required approvals for segments, even in emergency situations.")
        
        # First ask if segment approvals are required
        approval_settings['segments_approval_settings']['required'] = get_user_confirmation(
            "Require approvals for segment targeting changes? [When enabled, users must request approval for segment targeting changes]",
            False
        )
        
        if approval_settings['segments_approval_settings']['required']:
            # Ask about scope of segment approvals
            segment_req_type = get_user_choice(
                "Which segments require approval?",
                ["All segments (recommended for critical environments)", 
                 "Only segments with specific tags (more flexible)"]
            )
            
            if segment_req_type == "All segments (recommended for critical environments)":
                approval_settings['segments_approval_settings']['required_approval_tags'] = []
            else:  # Segments with specific tags
                print("\nSegments with specified tags will require approval for targeting changes.")
                print("Example tags: 'critical', 'customer-facing', 'financial'")
                print("Note: While tags are global across environments, this setting applies only to segments in this environment.")
                tags_input = get_user_input("Enter comma-separated tags for segment approval requirements")
                approval_settings['segments_approval_settings']['required_approval_tags'] = [tag.strip() for tag in tags_input.split(',')]
            
            # Configure self-review
            print("\nSelf-review allows requesters to approve their own changes.")
            approval_settings['segments_approval_settings']['can_review_own_request'] = get_user_confirmation(
                "Allow requesters to review their own segment change requests? [If enabled, users can approve their own changes]",
                False
            )
            
            # Configure minimum approvals (1-5)
            print("\nSpecify the minimum number of approvals required before a segment change can be applied.")
            while True:
                min_approvals = int(get_user_input(
                    "Minimum number of approvals required for segments (1-5)",
                    str(approval_settings['segments_approval_settings']['min_num_approvals'])
                ))
                if 1 <= min_approvals <= 5:
                    approval_settings['segments_approval_settings']['min_num_approvals'] = min_approvals
                    break
                print("Please enter a number between 1 and 5")
            
            # Configure declined changes behavior
            print("\nConfigure what happens when a reviewer declines a change request.")
            approval_settings['segments_approval_settings']['can_apply_declined_changes'] = not get_user_confirmation(
                "Prevent applying changes if any reviewer has declined? [If enabled, changes cannot be applied if any reviewer declines]",
                True  # Default to NOT allowing changes to be applied if declined (most secure)
            )
        
        logging.info("User selected LaunchDarkly approval system with detailed configuration")
    elif service_kind in ['servicenow', 'servicenow-normal', 'service-now']:
        # Normalize to 'servicenow' which is what the API expects
        approval_settings['service_kind'] = 'servicenow'
        
        print("\n" + "-"*50)
        print("SERVICENOW APPROVAL SETTINGS")
        print("-"*50)
        print("ServiceNow approvals integrate with your existing ServiceNow instance.")
        print("This allows you to use ServiceNow's approval workflows for LaunchDarkly changes.")
        print("Note: ServiceNow approval system does not support segment approvals.")
        
        # These are the only settings that matter for ServiceNow
        approval_settings['required'] = True  # Must be true for ServiceNow
    
        approval_settings['bypass_approvals_for_pending_changes'] = get_user_confirmation(
            "Allow members with permission to bypass ServiceNow approvals? [Useful for emergency situations]",
            False
        )
    
        print("\nSpecify the minimum number of ServiceNow approvals required before a change can be applied.")
        while True:
            min_approvals = int(get_user_input(
                "Minimum number of approvals required (1-5)",
                str(approval_settings['min_num_approvals'])
            ))
            if 1 <= min_approvals <= 5:
                approval_settings['min_num_approvals'] = min_approvals
                break
            print("Please enter a number between 1 and 5")
    
        # ServiceNow template ID is required
        if not SERVICENOW_TEMPLATE_SYS_ID:
            print("\nServiceNow integration requires a Template System ID.")
            print("This ID connects LaunchDarkly to the correct ServiceNow template.")
            template_id = get_user_input(
                "ServiceNow Template System ID not found in environment variables. Please enter it now"
            )
            os.environ['SERVICENOW_TEMPLATE_SYS_ID'] = template_id
        else:
            template_id = SERVICENOW_TEMPLATE_SYS_ID
            print(f"\nUsing ServiceNow Template System ID: {template_id}")
            print("To use a different template, update your .env file.")
        
        # Set up the ServiceNow config
        approval_settings['service_config'] = {
            'template': template_id,
            'detail_column': 'justification'  # Default value for ServiceNow integration
        }
        
        # Inform about ServiceNow integration limitations
        print("\nNote: With ServiceNow integration, the following settings are controlled by ServiceNow:")
        print("- Self-review capabilities")
        print("- Approval workflows")
        print("- Change application process")
        
        # Explicitly set segment approvals to false for ServiceNow
        approval_settings['segments_approval_settings']['required'] = False
        
        logging.info("User selected ServiceNow approval system")
    
    # Final confirmation of settings
    print("\n" + "="*50)
    print("APPROVAL SETTINGS SUMMARY")
    print("="*50)
    print(f"Approval System: {'LaunchDarkly approval system' if service_kind == 'launchdarkly' else 'ServiceNow approvals'}")
    print(f"Bypass Approvals for Emergencies: {'Yes' if approval_settings['bypass_approvals_for_pending_changes'] else 'No'}")
    print(f"Auto-apply Approved Changes: {'Yes' if approval_settings['auto_apply_approved_changes'] else 'No'}")
    
    if service_kind == 'launchdarkly':
        if approval_settings['flags_approval_settings']['required']:
            print("\nFlag Approval Settings:")
            tag_display = "All flags" if not approval_settings['flags_approval_settings']['required_approval_tags'] else f"Tags: {', '.join(approval_settings['flags_approval_settings']['required_approval_tags'])}"
            print(f"- Required for: {tag_display}")
            print(f"- Minimum Approvals: {approval_settings['flags_approval_settings']['min_num_approvals']}")
            print(f"- Self-review: {'Allowed' if approval_settings['flags_approval_settings']['can_review_own_request'] else 'Not allowed'}")
            print(f"- Apply if Declined: {'Allowed' if approval_settings['flags_approval_settings']['can_apply_declined_changes'] else 'Not allowed'}")
            print(f"- Delete Scheduled Changes: {'No approval needed' if approval_settings['flags_approval_settings']['allow_delete_scheduled_changes'] else 'Requires approval'}")
        else:
            print("\nFlag Approvals: Not required")
        
        if approval_settings['segments_approval_settings']['required']:
            print("\nSegment Approval Settings:")
            tag_display = "All segments" if not approval_settings['segments_approval_settings']['required_approval_tags'] else f"Tags: {', '.join(approval_settings['segments_approval_settings']['required_approval_tags'])}"
            print(f"- Required for: {tag_display}")
            print(f"- Minimum Approvals: {approval_settings['segments_approval_settings']['min_num_approvals']}")
            print(f"- Self-review: {'Allowed' if approval_settings['segments_approval_settings']['can_review_own_request'] else 'Not allowed'}")
            print(f"- Apply if Declined: {'Allowed' if approval_settings['segments_approval_settings']['can_apply_declined_changes'] else 'Not allowed'}")
        else:
            print("\nSegment Approvals: Not required")
    else:
        # ServiceNow summary
        print(f"ServiceNow Template ID: {approval_settings['service_config']['template']}")
        print(f"Minimum Approvals: {approval_settings['min_num_approvals']}")
        print("Segment Approvals: Not supported with ServiceNow")
    
    # Final confirmation
    confirm = get_user_confirmation("Apply these approval settings?", False)
    if not confirm:
        print("\nOperation cancelled. No changes made to approval settings.")
        return None
    
    return approval_settings

def create_environment(project_key, env_config, defaults, global_approval_settings):
    """Create a new environment in a project"""
    # Ensure key is lowercase
    project_key = project_key.lower()
    env_key = env_config['key'].lower()
    
    # Prepare environment payload
    payload = {
        'name': env_config['name'],
        'key': env_key,
        'color': env_config.get('color', defaults.get('color', '7B42BC')),  # Default to LaunchDarkly purple
        'defaultTtl': env_config.get('default_ttl', defaults.get('default_ttl', 0)),
        'secureMode': env_config.get('secure_mode', defaults.get('secure_mode', False)),
        'defaultTrackEvents': env_config.get('default_track_events', defaults.get('default_track_events', False)),
        'tags': env_config.get('tags', defaults.get('tags', [])),
        'requireComments': env_config.get('require_comments', defaults.get('require_comments', False)),
        'confirmChanges': env_config.get('confirm_changes', defaults.get('confirm_changes', False))
    }
    
    # Add approval settings if provided and this environment should have them enabled
    if global_approval_settings:
        # Check if this environment should have approvals enabled
        enabled_envs = global_approval_settings.get('enabled_environments')
        if enabled_envs is None or env_key in enabled_envs:
            env_approval_settings = global_approval_settings
            
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
            
            # Handle specific approval system types
            if approval_settings['serviceKind'] == 'launchdarkly':
                # Handle LaunchDarkly approval settings
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
                
                # Configure segment approvals under resourceApprovalSettings
                if segments_settings.get('required', False):
                    payload['resourceApprovalSettings'] = {
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
                
                # Add the main approvalSettings
                payload['approvalSettings'] = approval_settings
            
            elif approval_settings['serviceKind'] == 'servicenow':
                # For ServiceNow, we need to set both approvalSettings and resourceApprovalSettings
                # with matching serviceKind and serviceConfig
                servicenow_settings = {
                    'required': True,  # Must be true for ServiceNow
                    'bypassApprovalsForPendingChanges': approval_settings['bypassApprovalsForPendingChanges'],
                    'minNumApprovals': approval_settings['minNumApprovals'],
                    'canReviewOwnRequest': False,  # ServiceNow handles this
                    'canApplyDeclinedChanges': True,  # ServiceNow handles this
                    'autoApplyApprovedChanges': False,  # ServiceNow handles this
                    'serviceKind': 'servicenow',
                    'serviceConfig': approval_settings['serviceConfig'],
                    'requiredApprovalTags': []  # ServiceNow doesn't use tags
                }
                
                payload['approvalSettings'] = servicenow_settings
                payload['resourceApprovalSettings'] = {
                    'segment': {
                        'required': True,
                        'bypassApprovalsForPendingChanges': approval_settings['bypassApprovalsForPendingChanges'],
                        'minNumApprovals': approval_settings['minNumApprovals'],
                        'canReviewOwnRequest': False,  # ServiceNow handles this
                        'canApplyDeclinedChanges': True,  # ServiceNow handles this
                        'autoApplyApprovedChanges': False,  # ServiceNow handles this
                        'serviceKind': 'servicenow',
                        'serviceConfig': approval_settings['serviceConfig'],
                        'requiredApprovalTags': []  # ServiceNow doesn't use tags
                    }
                }
        
    
    # Create environment
    url = f'{BASE_URL}/projects/{project_key}/environments'
    logging.debug(f"Environment creation payload: {json.dumps(payload, indent=2)}")
    response = requests.post(url, headers=headers, json=payload)
    result = handle_response(response, f"environment creation ({env_key})")
    time.sleep(1)
    return result

def remove_approval_settings(project_key, env_key, env_name):
    """Remove workflow approvals from an environment"""
    # Ensure keys are lowercase
    project_key = project_key.lower()
    env_key = env_key.lower()
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    
    # Get current environment to see what needs to be updated
    current_env = get_environment(project_key, env_key)
    logging.debug(f"Current environment state for {env_key}: {json.dumps(current_env, indent=2)}")
    
    # Prepare patch operations to remove approval settings
    patch_operations = []
    
    # Create default settings with approvals disabled
    default_approval_settings = {
        'required': False,
        'bypassApprovalsForPendingChanges': False,
        'minNumApprovals': 1,
        'canReviewOwnRequest': False,
        'canApplyDeclinedChanges': True,
        'autoApplyApprovedChanges': False,
        'serviceKind': 'launchdarkly',
        'serviceConfig': {},
        'requiredApprovalTags': []
    }
    
    # Default segment settings with approvals disabled
    default_segment_settings = {
        'required': False,
        'bypassApprovalsForPendingChanges': False,
        'minNumApprovals': 1,
        'canReviewOwnRequest': False,
        'canApplyDeclinedChanges': True,
        'serviceKind': 'launchdarkly',
        'serviceConfig': {},
        'requiredApprovalTags': []
    }
    
    # Always replace/update approvalSettings
    patch_operations.append({
        'op': 'replace',
        'path': '/approvalSettings',
        'value': default_approval_settings
    })
    
    # Always replace/update resourceApprovalSettings if it exists
    if 'resourceApprovalSettings' in current_env:
        patch_operations.append({
            'op': 'replace',
            'path': '/resourceApprovalSettings',
            'value': {
                'segment': default_segment_settings
            }
        })
    else:
        # Add resourceApprovalSettings if it doesn't exist
        patch_operations.append({
            'op': 'add',
            'path': '/resourceApprovalSettings',
            'value': {
                'segment': default_segment_settings
            }
        })
    
    # Log the complete patch operations
    logging.info(f"JSON Patch operations to remove approvals: {json.dumps(patch_operations, indent=2)}")
    
    if patch_operations:
        patch_headers = headers.copy()
        patch_headers['Content-Type'] = 'application/json-patch+json'  # Ensure correct content type
        
        # Log the full request we're about to make
        logging.info(f"Making PATCH request to: {url}")
        logging.info(f"With headers: {json.dumps(patch_headers, indent=2)}")
        
        try:
            response = requests.patch(url, headers=patch_headers, json=patch_operations)
            result = handle_response(response, f"removing approval settings ({env_key})")
            
            # Check result
            if result:
                logging.info(f"PATCH response: {json.dumps(result, indent=2)}")
            
            # Verify the update was successful
            time.sleep(2)  # Give API time to process
            updated_env = get_environment(project_key, env_key)
            
            if not updated_env.get('approvalSettings', {}).get('required', False):
                logging.info(f"✅ Verified approval settings were successfully removed from {env_key}")
                print(f"✅ Successfully removed approval settings from {env_name} ({env_key})")
            else:
                logging.error(f"❌ Failed to remove approval settings from {env_key}. Environment still has required approvals.")
                print(f"❌ Warning: Could not verify removal of approval settings from {env_name} ({env_key})")
            
            time.sleep(1)
            return result
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error removing approval settings for {env_key}: {str(e)}")
            print(f"❌ Error removing approval settings for {env_name} ({env_key}): {str(e)}")
            return None
    
    return current_env

def update_environment(project_key, env_key, env_config, defaults, approval_settings):
    """Update an existing environment with approval settings"""
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
    if approval_settings:
        # Convert service_kind for ServiceNow
        if approval_settings.get('service_kind') == 'service-now':
            approval_settings['service_kind'] = 'servicenow'
            
        # Convert to the format expected by LaunchDarkly API
        api_approval_settings = {
            'required': approval_settings.get('required', True),
            'bypassApprovalsForPendingChanges': approval_settings.get('bypass_approvals_for_pending_changes', False),
            'minNumApprovals': max(1, approval_settings.get('min_num_approvals', 1)),  # Ensure min is at least 1
            'canReviewOwnRequest': approval_settings.get('can_review_own_request', False),
            'canApplyDeclinedChanges': approval_settings.get('can_apply_declined_changes', False),
            'autoApplyApprovedChanges': approval_settings.get('auto_apply_approved_changes', False),
            'serviceKind': approval_settings.get('service_kind', 'launchdarkly'),
            'serviceConfig': approval_settings.get('service_config', {}),
            'requiredApprovalTags': approval_settings.get('required_approval_tags', [])
        }
        
        # Handle specific approval system types
        if api_approval_settings['serviceKind'] == 'launchdarkly':
            # Handle LaunchDarkly native approval settings
            flags_settings = approval_settings.get('flags_approval_settings', {})
            segments_settings = approval_settings.get('segments_approval_settings', {})
            
            # Configure flag approvals in main approvalSettings
            if flags_settings.get('required', False):
                api_approval_settings.update({
                    'required': True,
                    'minNumApprovals': max(1, flags_settings.get('min_num_approvals', 1)),  # Ensure min is at least 1
                    'canReviewOwnRequest': flags_settings.get('can_review_own_request', False),
                    'canApplyDeclinedChanges': flags_settings.get('can_apply_declined_changes', False),
                    'requiredApprovalTags': flags_settings.get('required_approval_tags', [])
                })
                
                # The flagsApprovalSettings attribute might not be supported in all API versions
                # Only add it if the current environment already has it
                if 'flagsApprovalSettings' in current_env.get('approvalSettings', {}):
                    api_approval_settings['flagsApprovalSettings'] = {
                        'required': True,
                        'requiredApprovalTags': flags_settings.get('required_approval_tags', []),
                        'minNumApprovals': max(1, flags_settings.get('min_num_approvals', 1)),  # Ensure min is at least 1
                        'canReviewOwnRequest': flags_settings.get('can_review_own_request', False),
                        'canApplyDeclinedChanges': flags_settings.get('can_apply_declined_changes', False),
                        'allowDeleteScheduledChanges': flags_settings.get('allow_delete_scheduled_changes', False)
                    }
            
            # Configure segment approvals under resourceApprovalSettings.segment
            segment_approval_settings = None
            if segments_settings.get('required', False):
                segment_approval_settings = {
                    'required': True,
                    'bypassApprovalsForPendingChanges': api_approval_settings.get('bypassApprovalsForPendingChanges', False),
                    'minNumApprovals': max(1, segments_settings.get('min_num_approvals', 1)),  # Ensure min is at least 1
                    'canReviewOwnRequest': segments_settings.get('can_review_own_request', False),
                    'canApplyDeclinedChanges': segments_settings.get('can_apply_declined_changes', False),
                    'serviceKind': 'launchdarkly',
                    'serviceConfig': {},
                    'requiredApprovalTags': segments_settings.get('required_approval_tags', [])
                }
            else:
                segment_approval_settings = {
                    'required': False,
                    'minNumApprovals': 1,  # Always set minNumApprovals to at least 1
                    'serviceKind': 'launchdarkly',
                    'serviceConfig': {}
                }
            
            # Add segment settings to patch operations
            patch_operations.append({
                'op': 'replace',
                'path': '/resourceApprovalSettings',
                'value': {
                    'segment': segment_approval_settings
                }
            })
        
            # Add the main approvalSettings patch operation
            patch_operations.append({
                'op': 'replace',
                'path': '/approvalSettings',
                'value': api_approval_settings
            })
        
        elif api_approval_settings['serviceKind'] == 'servicenow':
            # For ServiceNow, only set the main approvalSettings without segment settings
            servicenow_settings = {
                'required': True,  # Must be true for ServiceNow
                'bypassApprovalsForPendingChanges': api_approval_settings['bypassApprovalsForPendingChanges'],
                'minNumApprovals': max(1, api_approval_settings['minNumApprovals']),  # Ensure min is at least 1
                'canReviewOwnRequest': False,  # ServiceNow handles this
                'canApplyDeclinedChanges': True,  # ServiceNow handles this
                'autoApplyApprovedChanges': False,  # ServiceNow handles this
                'serviceKind': 'servicenow',  # Use 'servicenow' instead of 'service-now'
                'serviceConfig': api_approval_settings['serviceConfig'],
                'requiredApprovalTags': []  # ServiceNow doesn't use tags
            }
            
            # Only update the main approvalSettings for ServiceNow
            patch_operations.append({
                'op': 'replace',
                'path': '/approvalSettings',
                'value': servicenow_settings
            })
            
            # For ServiceNow, we need to make sure segment settings are disabled
            # with a LaunchDarkly serviceKind (since ServiceNow isn't supported for segments)
            # Check if the environment already has resourceApprovalSettings.segment
            if 'resourceApprovalSettings' in current_env and 'segment' in current_env['resourceApprovalSettings']:
                patch_operations.append({
                    'op': 'replace',
                    'path': '/resourceApprovalSettings/segment',
                    'value': {
                        'required': False,
                        'minNumApprovals': 1,
                        'serviceKind': 'launchdarkly',  # Must be launchdarkly for segments
                        'serviceConfig': {}
                    }
                })
        
        # Log the approval settings we're about to apply
        logging.info(f"Approval settings to apply: {json.dumps(api_approval_settings, indent=2)}")
    
    # Log the complete patch operations
    logging.info(f"JSON Patch operations: {json.dumps(patch_operations, indent=2)}")
    
    if patch_operations:
        patch_headers = headers.copy()
        patch_headers['Content-Type'] = 'application/json-patch+json'  # Ensure correct content type
        
        # Log the full request we're about to make
        logging.info(f"Making PATCH request to: {url}")
        logging.info(f"With headers: {json.dumps(patch_headers, indent=2)}")
        
        try:
            response = requests.patch(url, headers=patch_headers, json=patch_operations)
            result = handle_response(response, f"environment update ({env_key})")
            
            # Check result
            if result:
                logging.info(f"PATCH response: {json.dumps(result, indent=2)}")
            
            # Verify the update was successful
            time.sleep(2)  # Give API time to process
            updated_env = get_environment(project_key, env_key)
            
            # Check if approval settings were updated correctly
            if approval_settings:
                expected_service_kind = 'servicenow' if approval_settings.get('service_kind') in ['servicenow', 'service-now'] else approval_settings.get('service_kind')
                actual_service_kind = updated_env.get('approvalSettings', {}).get('serviceKind')
                
                if 'approvalSettings' in updated_env and actual_service_kind == expected_service_kind:
                    logging.info(f"✅ Verified approval settings were successfully applied to {env_key}")
                    print(f"✅ Successfully updated approval settings for {env_key}")
                else:
                    logging.error(f"❌ Failed to update approval settings for {env_key}. Updated environment does not contain expected settings.")
                    print(f"❌ Warning: Could not verify approval settings for {env_key}")
            
            time.sleep(1)
            return result
            
        except Exception as e:
            logging.error(f"Error updating environment {env_key}: {str(e)}")
            print(f"❌ Error updating environment {env_key}: {str(e)}")
            
            # Enhanced error handling to extract API error message
            if hasattr(e, 'response') and e.response:
                try:
                    error_json = json.loads(e.response.text)
                    if 'message' in error_json:
                        logging.error(f"API Error message: {error_json['message']}")
                        print(f"API Error: {error_json['message']}")
                except:
                    logging.error(f"Response text: {e.response.text}")
            
            raise
    
    return current_env

def main():
    """Main entry point for the script"""
    # Set up graceful exit on Ctrl+C
    def signal_handler(sig, frame):
        print("\n\nReceived Ctrl+C. Exiting gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Setup logging
        log_file = setup_logging()
        logging.info("Starting LaunchDarkly project setup")
        logging.info(f"Log file: {log_file}")
        
        # Ask if user wants to create a new project or manage existing ones
        operation_mode = get_user_choice(
            "What would you like to do?",
            ["Create a new project and configure environments with workflow approvals", 
             "Manage approval systems for existing projects"]
        )
        
        if operation_mode == "Create a new project and configure environments with workflow approvals":
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
                update_environment(project_key, 'production', prod_config, defaults, None)
            else:
                logging.info("Production environment doesn't exist, creating it...")
                create_environment(project_key, prod_config, defaults, None)

            # Create all other environments from our config if they don't already exist
            existing_env_keys = set(env['key'] for env in environments)
            for env_config in config['environments']:
                if env_config['key'] != 'production' and env_config['key'] not in existing_env_keys:
                    env = create_environment(project_key, env_config, defaults, None)
                    logging.info(f'Created environment: {env["name"]} with key: {env["key"]}')
                elif env_config['key'] != 'production':
                    logging.info(f"Environment {env_config['name']} with key {env_config['key']} already exists, updating it...")
                    update_environment(project_key, env_config['key'], env_config, defaults, None)

            # Ask if user wants to configure approval workflows now
            print("\nWould you like to configure workflow approvals for any environments?")
            if get_user_confirmation("Configure workflow approvals", True):
                environments = list_environments(project_key)  # Get fresh list of all environments
                
                # Loop through each environment and ask if approvals should be configured
                for env in environments:
                    env_key = env['key']
                    env_name = env['name']
                    print(f"\nConfigure workflow approvals for {env_name} ({env_key})?")
                    if get_user_confirmation("Enable workflow approvals for this environment", False):
                        # Ask which approval system to use
                        approval_system = get_user_choice(
                            f"\nWhich approval system would you like to use for {env_name}?",
                            ["LaunchDarkly approval system", "ServiceNow approvals"]
                        )
                        
                        # Get current environment settings
                        env_details = get_environment(project_key, env_key)
                        existing_settings = env_details.get('approvalSettings')
                        
                        # Set the service kind based on user's choice
                        if existing_settings:
                            if approval_system == "LaunchDarkly approval system":
                                existing_settings['serviceKind'] = 'launchdarkly'
                            else:  # ServiceNow approvals
                                existing_settings['serviceKind'] = 'servicenow'
                        else:
                            # Create new settings object if none exists
                            existing_settings = {
                                'serviceKind': 'launchdarkly' if approval_system == "LaunchDarkly approval system" else 'servicenow'
                            }
                            
                        # Pass the environment key to configure_approval_settings
                        # This prevents it from asking for environment selection again
                        approval_settings = configure_approval_settings(existing_settings, env_key)
                        
                        if approval_settings:
                            try:
                                update_environment(project_key, env_key, None, None, approval_settings)
                                logging.info(f"Successfully configured approval settings for {env_name}")
                            except Exception as e:
                                logging.error(f"Error configuring approval settings for {env_name}: {str(e)}")
                                print(f"Error: {str(e)}")
                        else:
                            logging.info(f"Skipping approval settings for {env_name}")
                    else:
                        logging.info(f"Skipping approval settings for {env_name}")

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
            action = get_user_choice("Enter your choice", ["Configure approval systems", "Remove approval systems"])
            remove_settings = action == "Remove approval systems"
            
            print("\nHow would you like to proceed?")
            workflow = get_user_choice("Enter your choice", ["Update specific environments across all/selected projects", 
                                                           "Select environments individually for each project"])
            
            if workflow == "Update specific environments across all/selected projects":
                # Global environment update
                env_keys = get_environment_keys()
                
                print("\nHow would you like to proceed with projects?")
                project_mode = get_user_choice("Enter your choice", ["Process all projects", "Select specific projects"])
                target_projects = select_projects(projects) if project_mode == "Select specific projects" else projects
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
                    if workflow == "Update specific environments across all/selected projects":
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
                            if workflow == "Select environments individually for each project":
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
                            if workflow == "Select environments individually for each project":
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
