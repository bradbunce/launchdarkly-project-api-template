import requests
import json
import time
import os
import sys
import signal
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variables
API_KEY = os.getenv('LD_API_KEY')
if not API_KEY:
    raise ValueError("LD_API_KEY not found in environment variables")

SERVICENOW_TEMPLATE_SYS_ID = os.getenv('SERVICENOW_TEMPLATE_SYS_ID')
if not SERVICENOW_TEMPLATE_SYS_ID:
    raise ValueError("SERVICENOW_TEMPLATE_SYS_ID not found in environment variables")

BASE_URL = 'https://app.launchdarkly.com/api/v2'

headers = {
    'Authorization': API_KEY,
    'Content-Type': 'application/json'
}

def setup_logging():
    """Configure logging to both file and console"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Create a timestamp for the log file name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'logs/workflow_approvals_update_{timestamp}.log'

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
        print("c - continue to environment selection")
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

def get_environment(project_key, env_key):
    """Get environment details"""
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    response = requests.get(url, headers=headers)
    result = handle_response(response, f"getting environment ({env_key})")
    time.sleep(2)
    return result

def list_environments(project_key):
    """List all environments in a project"""
    url = f'{BASE_URL}/projects/{project_key}/environments'
    response = requests.get(url, headers=headers)
    result = handle_response(response, "listing environments")
    time.sleep(2)
    return result.get('items', [])

def update_environment_approvals(project_key, env_key, env_name, remove=False):
    """Update environment approval settings using standard JSON patch format"""
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    
    # Get current environment
    current_env = get_environment(project_key, env_key)
    
    if remove:
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
        time.sleep(2)
        return result
    else:
        # Add ServiceNow approval settings with the existing approach that works
        approval_settings = {
            'required': True,
            'bypassApprovalsForPendingChanges': False,
            'minNumApprovals': 1,
            'canReviewOwnRequest': False,
            'canApplyDeclinedChanges': True,
            'autoApplyApprovedChanges': True,
            'serviceKind': 'servicenow',
            'serviceConfig': {
                'detail_column': 'justification',
                'template': SERVICENOW_TEMPLATE_SYS_ID
            },
            'requiredApprovalTags': []
        }
        
        # Apply settings to both approvalSettings and resourceApprovalSettings using the patch object approach
        # This is what's currently working in your script
        patch = {
            'approvalSettings': approval_settings,
            'resourceApprovalSettings': approval_settings
        }
        
        # Apply the patch
        patch_headers = headers.copy()
        patch_headers['Content-Type'] = 'application/json'
        response = requests.patch(url, headers=patch_headers, json=patch)
        result = handle_response(response, f"adding approval settings for {env_name}")
        time.sleep(2)
        return result

def needs_approval_settings(env, remove=False):
    """Check if environment needs approval settings update"""
    current_settings = env.get('approvalSettings', {})
    current_resource_settings = env.get('resourceApprovalSettings', {})
    
    if remove:
        # Check if there are any approval settings to remove
        return bool(current_settings) or bool(current_resource_settings)
    else:
        # Check if ServiceNow approvals are already configured
        has_servicenow = current_settings.get('serviceKind') == 'servicenow'
        has_resource_servicenow = current_resource_settings.get('serviceKind') == 'servicenow'
        return not (has_servicenow and has_resource_servicenow)

def get_user_confirmation(prompt):
    """Get user confirmation with yes/no/quit prompt"""
    while True:
        response = input(f"{prompt} (yes/no/quit): ").lower().strip()
        if response == 'quit':
            print("\nExiting script...")
            sys.exit(0)
        if response in ['yes', 'no']:
            return response == 'yes'
        print("Please enter 'yes', 'no', or 'quit'")

def get_user_choice(prompt, options):
    """Get user choice with quit option"""
    while True:
        response = input(f"\n{prompt} (or 'quit' to exit): ").strip()
        if response.lower() == 'quit':
            print("\nExiting script...")
            sys.exit(0)
        if response in options:
            return response
        print(f"Please enter one of: {', '.join(options)}, or 'quit'")

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

def get_project_environments(project_key, env_keys=None):
    """Get environments for a project, filtered by keys if provided"""
    environments = list_environments(project_key)
    if env_keys is None:
        return environments
    return [env for env in environments if env['key'] in env_keys]

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

def main():
    # Set up graceful exit on Ctrl+C
    def signal_handler(sig, frame):
        print("\n\nReceived Ctrl+C. Exiting gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Setup logging
        log_file = setup_logging()
        logging.info("Starting workflow approvals update")
        logging.info(f"Log file: {log_file}")
        
        # Get all projects
        projects = list_projects()
        logging.info(f"Found {len(projects)} projects")
        
        # Display projects and get first project's environments
        if not projects:
            print("No projects found")
            return
        
        print(f"\nFound {len(projects)} projects")
        display_projects(projects)
        
        print("\nWhat action would you like to take?")
        print("1. Add ServiceNow workflow approvals")
        print("2. Remove workflow approvals")
        
        action = get_user_choice("Enter your choice", ['1', '2'])
        remove_settings = action == '2'
        
        print("\nHow would you like to proceed?")
        print("1. Update specific environments across all/selected projects")
        print("2. Select environments individually for each project")
        
        workflow = get_user_choice("Enter your choice", ['1', '2'])
        
        if workflow == '1':
            # Global environment update
            env_keys = get_environment_keys()
            
            print("\nHow would you like to proceed with projects?")
            print("1. Process all projects")
            print("2. Select specific projects")
            
            project_mode = get_user_choice("Enter your choice", ['1', '2'])
            target_projects = select_projects(projects) if project_mode == '2' else projects
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
                if workflow == '1':
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
                
                for env in environments:
                    env_key = env['key']
                    env_name = env['name']
                    
                    # Check if environment needs update
                    if needs_approval_settings(env, remove_settings):
                        action_desc = "remove workflow approvals from" if remove_settings else "add workflow approvals to"
                        # For project-specific workflow, confirm each update
                        if workflow == '2':
                            print(f"\nEnvironment {env_name} in {project_name}: {action_desc}?")
                            if not get_user_confirmation("Would you like to proceed"):
                                logging.info(f"Skipping environment {env_name} by user choice")
                                continue
                        
                        logging.info(f"Processing approval settings for {env_name} in {project_name}")
                        update_environment_approvals(project_key, env_key, env_name, remove_settings)
                        updated_count += 1
                        logging.info(f"Successfully processed {env_name}")
                    else:
                        status = "has no approval settings" if remove_settings else "already has ServiceNow approvals"
                        logging.info(f"Skipping {env_name} - {status}")
                        skipped_count += 1
                
            except Exception as e:
                logging.error(f"Error processing project {project_name}: {str(e)}")
                error_count += 1
                continue
        
        # Log final statistics
        logging.info("\nUpdate complete!")
        logging.info(f"Environments updated: {updated_count}")
        logging.info(f"Environments skipped (already configured): {skipped_count}")
        logging.info(f"Errors encountered: {error_count}")
        
    except Exception as e:
        logging.error(f"Error during execution: {str(e)}")
        raise

if __name__ == '__main__':
    main()
