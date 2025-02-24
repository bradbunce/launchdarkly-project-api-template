import requests
import json
import time
import os
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

SERVICENOW_TEMPLATE_SYS_ID = os.getenv('SERVICENOW_TEMPLATE_SYS_ID')
if not SERVICENOW_TEMPLATE_SYS_ID:
    raise ValueError("SERVICENOW_TEMPLATE_SYS_ID not found in environment variables")

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

def get_project(project_key):
    """Get a project by key"""
    url = f'{BASE_URL}/projects/{project_key}'
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            return None
        result = handle_response(response, f"getting project ({project_key})")
        time.sleep(2)
        return result
    except Exception as e:
        logging.warning(f"Error retrieving project {project_key}: {str(e)}")
        return None

def get_user_confirmation(prompt):
    """Get user confirmation with yes/no prompt"""
    while True:
        response = input(f"{prompt} (yes/no): ").lower().strip()
        if response in ['yes', 'no']:
            return response == 'yes'
        print("Please enter 'yes' or 'no'")

def get_user_input(prompt, default=None):
    """Get user input with optional default value"""
    if default:
        response = input(f"{prompt} (default: {default}): ").strip()
        return response if response else default
    else:
        while True:
            response = input(f"{prompt}: ").strip()
            if response:
                return response
            print("Please provide a value")

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
    time.sleep(2)
    return result

def list_environments(project_key):
    """List all environments in a project"""
    url = f'{BASE_URL}/projects/{project_key}/environments'
    response = requests.get(url, headers=headers)
    result = handle_response(response, "listing environments")
    time.sleep(2)
    return result.get('items', [])

def delete_environment(project_key, env_key):
    """Delete an environment from a project"""
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    response = requests.delete(url, headers=headers)
    handle_response(response, f"deleting environment ({env_key})")
    time.sleep(2)

def get_environment(project_key, env_key):
    """Get environment details"""
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    response = requests.get(url, headers=headers)
    result = handle_response(response, f"getting environment ({env_key})")
    time.sleep(2)
    return result

def update_environment(project_key, env_key, env_config, defaults):
    """Update an existing environment with new configuration using JSON Patch"""
    url = f'{BASE_URL}/projects/{project_key}/environments/{env_key}'
    
    # Get current environment to see what needs to be updated
    current_env = get_environment(project_key, env_key)
    
    # Prepare patch operations
    patch_operations = []
    
    # Update name if different
    if env_config.get('name') != current_env.get('name'):
        patch_operations.append({
            'op': 'replace',
            'path': '/name',
            'value': env_config['name']
        })
    
    # Update color if different
    if env_config.get('color') != current_env.get('color'):
        patch_operations.append({
            'op': 'replace',
            'path': '/color',
            'value': env_config['color']
        })

    # Update confirmChanges if different
    confirm_changes = env_config.get('confirm_changes', 
                                   defaults.get('environment', {}).get('confirm_changes', False))
    if confirm_changes != current_env.get('confirmChanges'):
        patch_operations.append({
            'op': 'replace',
            'path': '/confirmChanges',
            'value': confirm_changes
        })

    # Update requireComments if different
    require_comments = env_config.get('require_comments', 
                                    defaults.get('environment', {}).get('require_comments', False))
    if require_comments != current_env.get('requireComments'):
        patch_operations.append({
            'op': 'replace',
            'path': '/requireComments',
            'value': require_comments
        })

    # Update tags if different
    new_tags = env_config.get('tags', defaults.get('environment', {}).get('tags', []))
    if new_tags != current_env.get('tags', []):
        patch_operations.append({
            'op': 'replace',
            'path': '/tags',
            'value': new_tags
        })

    # Update approval settings if configured
    if 'approval_settings' in env_config:
        approval_settings = {
            'required': env_config['approval_settings']['required'],
            'bypassApprovalsForPendingChanges': env_config['approval_settings']['bypass_approvals_for_pending_changes'],
            'minNumApprovals': env_config['approval_settings']['min_num_approvals'],
            'canReviewOwnRequest': env_config['approval_settings']['can_review_own_request'],
            'canApplyDeclinedChanges': env_config['approval_settings']['can_apply_declined_changes'],
            'autoApplyApprovedChanges': env_config['approval_settings']['auto_apply_approved_changes'],
            'serviceKind': env_config['approval_settings']['service_kind'],
            'serviceConfig': env_config['approval_settings']['service_config'],
            'requiredApprovalTags': env_config['approval_settings']['required_approval_tags']
        }
        # Replace template placeholder with actual value
        if approval_settings['serviceConfig'].get('template') == '${SERVICENOW_TEMPLATE_SYS_ID}':
            approval_settings['serviceConfig']['template'] = SERVICENOW_TEMPLATE_SYS_ID
            
        patch_operations.append({
            'op': 'replace',
            'path': '/approvalSettings',
            'value': approval_settings
        })

    if patch_operations:
        patch_headers = headers.copy()
        patch_headers['Content-Type'] = 'application/json'
        
        response = requests.patch(url, headers=patch_headers, json=patch_operations)
        result = handle_response(response, f"environment update ({env_config['name']})")
        time.sleep(2)
        return result
    
    return current_env

def create_environment(project_key, env_config, defaults):
    """Create a new environment using configuration"""
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
    time.sleep(2)
    return result

def main():
    try:
        # Setup logging
        log_file = setup_logging()
        logging.info("Starting LaunchDarkly project setup")
        logging.info(f"Log file: {log_file}")
        
        # Load configuration
        config = load_config()
        logging.info("Configuration loaded successfully")
        
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
            update_environment(project_key, 'production', prod_config, defaults)
        else:
            logging.info("Production environment doesn't exist, creating it...")
            create_environment(project_key, prod_config, defaults)

        # Create all other environments from our config if they don't already exist
        existing_env_keys = set(env['key'] for env in environments)
        for env_config in config['environments']:
            if env_config['key'] != 'production' and env_config['key'] not in existing_env_keys:
                env = create_environment(project_key, env_config, defaults)
                logging.info(f'Created environment: {env["name"]} with key: {env["key"]}')
            elif env_config['key'] != 'production':
                logging.info(f"Environment {env_config['name']} with key {env_config['key']} already exists, updating it...")
                update_environment(project_key, env_config['key'], env_config, defaults)

        logging.info("LaunchDarkly project setup completed successfully")

    except Exception as e:
        logging.error(f"Error during execution: {str(e)}")
        raise

if __name__ == '__main__':
    main()