import logging
import requests

from config import ARCGIS_CLIENT_URL, ARCGIS_CLIENT_ID, ARCGIS_CLIENT_SECRET

# Set up logging to both console and a file
logging.basicConfig(level=logging.INFO)

# Create a file handler to log messages to a file
file_handler = logging.FileHandler('./arcgis_api.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger = logging.getLogger()
logger.addHandler(file_handler)

# Remove '/home/' from the end of ARCGIS_CLIENT_URL
ARCGIS_API_URL = ARCGIS_CLIENT_URL.rstrip('/home/') + '/'

# Print the result
print("ARCGIS_API_URL:", ARCGIS_API_URL)

def get_token():
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    parameters = {'username': ARCGIS_CLIENT_ID,
                  'password': ARCGIS_CLIENT_SECRET,
                  'client': 'referer',
                  'referer': ARCGIS_API_URL,
                  'expiration': 60,
                  'f': 'json'}
    url = f"{ARCGIS_API_URL}sharing/rest/generateToken?"
    logger.info(f"Requesting token from {url}")
    response = requests.post(url, data=parameters, headers=headers)

    try:
        logger.info(f"Response Status: {response.status_code}")
        logger.debug(f"Response content: {response.text}")
        jsonResponse = response.json()
        if 'token' in jsonResponse:
            logger.info("Token retrieved successfully.")
            return jsonResponse['token']
        elif 'error' in jsonResponse:
            logger.error(f"Error retrieving token: {jsonResponse['error']['message']}")
            for detail in jsonResponse['error']['details']:
                logger.error(detail)
    except ValueError:
        logger.exception("An error occurred while parsing the token response.")

def get_user_from_username(username):
    if username is None:
        logger.warning("Username is None.")
        return
    token = get_token()
    url = f"{ARCGIS_API_URL}sharing/rest/community/users/{username}"
    params = {
        'f': 'json',
        'token': token
    }
    logger.info(f"Getting user info for username: {username}")
    response = requests.get(url, params=params)
    try:
        response.raise_for_status()  # Raise an exception for any HTTP error
        logger.info(f"Response Status: {response.status_code}")
        logger.debug(f"Response content: {response.text}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None

def get_user_by_email(user_email):
    if user_email is None:
        logger.warning("User email is None.")
        return user_email
    token = get_token()
    url = f"{ARCGIS_API_URL}sharing/rest/community/users"
    
    email_query_params = {
        'f': 'json',
        'token': token,
        'q': f'email:{user_email}'
    }
    logger.info(f"Searching for user by email: {user_email}")
    email_query_response = requests.get(url, params=email_query_params)
    try:
        email_query_response.raise_for_status()
        response_json = email_query_response.json()
        if 'results' in response_json:
            email_matches = response_json['results']
        else:
            email_matches = []
            logger.warning("'results' key not found in email query response.")
    except ValueError:
        email_matches = []
        logger.error("Error parsing email query response as JSON.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        email_matches = []

    if email_matches:
        logger.info(f"User found by email: {user_email}")
        return email_matches[0]

    default_username = user_email.split('@')[0]
    username_query_params = {
        'f': 'json',
        'token': token,
        'q': f'username:{default_username}*'
    }
    logger.info(f"Searching for user by default username: {default_username}")
    username_query_response = requests.get(url, params=username_query_params)
    try:
        username_query_response.raise_for_status()
        response_json = username_query_response.json()
        if 'results' in response_json:
            username_matches = response_json['results']
        else:
            username_matches = []
            logger.warning("'results' key not found in username query response.")
    except ValueError:
        username_matches = []
        logger.error("Error parsing username query response as JSON.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        username_matches = []

    if username_matches:
        logger.info(f"User found by default username: {default_username}")
        return username_matches[0]
    
    logger.info(f"User {user_email} not found in ArcGIS")
    return None

def get_group_by_title(group_title):
    if group_title is None:
        logger.warning("Group title is None.")
        return group_title
    token = get_token()
    url = f"{ARCGIS_API_URL}sharing/rest/community/groups"
    params = {
        'f': 'json',
        'token': token,
        'q': f'title:{group_title}'
    }
    logger.info(f"Searching for group by title: {group_title}")
    response = requests.get(url, params=params)
    try:
        response.raise_for_status()
        response_json = response.json()
        logger.info(f"Response Status: {response.status_code}")
        logger.debug(f"Response content: {response.text}")
        if 'results' in response_json:
            arcgis_groups = response_json['results']
        else:
            arcgis_groups = []
            logger.warning("'results' key not found in group query response.")
    except ValueError:
        arcgis_groups = []
        logger.error("Error parsing group query response as JSON.")
    except requests.exceptions.RequestException as e:
        arcgis_groups = []
        logger.error(f"Request failed: {e}")
    
    if not arcgis_groups or not arcgis_groups[0].get('title'):
        logger.info(f"Group {group_title} not found.")
        return None

    arcgis_group_title = arcgis_groups[0].get('title')
    if group_title.lower() == arcgis_group_title.lower():
        logger.info(f"Group {group_title} found.")
        return arcgis_groups[0]
    
    logger.info(f"Group {group_title} not found.")
    return None

def add_user_to_groups(user, all_groups, proper_group_names):
    if not all([user, all_groups, proper_group_names]):
        logger.warning("User, all_groups, or proper_group_names is None.")
        return
    token = get_token()
    for group_name in all_groups:
        proper_group_name = proper_group_names[group_name]
        group = get_group_by_title(proper_group_name)
        if group:
            url = f"{ARCGIS_API_URL}sharing/rest/community/groups/{group['id']}/addUsers"
            params = {
                'f': 'json',
                'token': token,
                'users': user['username']
            }
            logger.info(f"Adding user {user['username']} to group {group['title']}.")
            response = requests.post(url, data=params)
            try:
                response.raise_for_status()
                logger.info(f"Add user response: {response.json()}")
            except ValueError:
                logger.error("Error parsing add user response as JSON.")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")

if __name__ == "__main__":
    # Example usage:
    user = get_user_from_username('andrea_borghi')
    if user:
        logger.info(f"User retrieved: {user.get('email')}")
    else:
        logger.warning("No user found.")
