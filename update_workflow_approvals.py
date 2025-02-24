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
    """List all projects"""
    url = f'{BASE_URL}/projects'
    response = requests.get(url, headers=headers)
    result = handle_response(response, "listing projects")
    time.sleep(2)
    return result.get('items', [])

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

def update_environment_approvals(project_key, env_key, env_name):
    """Update environment with ServiceNow approval settings"""
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    
    # Define approval settings
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

    # Create patch operation
    patch_operations = [{
        'op': 'replace',
        'path': '/approvalSettings',
        'value': approval_settings
    }]

    patch_headers = headers.copy()
    patch_headers['Content-Type'] = 'application/json'
    
    response = requests.patch(url, headers=patch_headers, json=patch_operations)
    result = handle_response(response, f"environment update ({env_name})")
    time.sleep(2)
    return result

def needs_approval_settings(env):
    """Check if environment needs approval settings update"""
    current_settings = env.get('approvalSettings', {})
    
    # Check if ServiceNow approvals are already configured
    if current_settings.get('serviceKind') == 'servicenow':
        return False
    
    return True

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
        
        # Ask user for update mode
        print("\nFound the following projects:")
        for i, project in enumerate(projects, 1):
            print(f"{i}. {project['name']} ({project['key']})")
        
        print("\nHow would you like to proceed?")
        print("1. Update all projects")
        print("2. Select projects individually")
        
        mode = get_user_choice("Enter your choice", ['1', '2'])
        
        # Track statistics
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Process projects based on user choice
        for project in projects:
            project_key = project['key']
            project_name = project['name']
            
            # If mode is 2 (individual selection), ask for confirmation
            if mode == '2':
                print(f"\nProcess project: {project_name} ({project_key})?")
                if not get_user_confirmation("Would you like to update this project"):
                    logging.info(f"Skipping project {project_name} by user choice")
                    continue
            
            logging.info(f"\nProcessing project: {project_name} ({project_key})")
            
            try:
                # Get environments for this project
                environments = list_environments(project_key)
                
                # Find production environments
                prod_envs = [env for env in environments if env['key'] == 'production']
                
                for env in prod_envs:
                    env_key = env['key']
                    env_name = env['name']
                    
                    # Check if environment needs approval settings
                    if needs_approval_settings(env):
                        # For individual selection mode, confirm each update
                        if mode == '2':
                            print(f"\nProduction environment {env_name} in {project_name} needs workflow approval settings.")
                            if not get_user_confirmation("Would you like to update this environment"):
                                logging.info(f"Skipping environment {env_name} by user choice")
                                continue
                        
                        logging.info(f"Updating approval settings for {env_name} in {project_name}")
                        update_environment_approvals(project_key, env_key, env_name)
                        updated_count += 1
                        logging.info(f"Successfully updated {env_name}")
                    else:
                        logging.info(f"Skipping {env_name} - already configured")
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
