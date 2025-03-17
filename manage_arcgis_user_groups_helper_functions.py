import time
import os
import logging
import redis
import json
import arcgis_api
from config import redis_client, ARCGIS_GROUPS_KEY
from redis_helpers import get_email_to_user_groups, get_username_to_email, delete_username_to_email, \
    delete_user_auth_access, delete_email_to_user_groups, get_arcgis_groups

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler('./add_users_to_group.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# -------------------------
# ✅ User Group Functions (Updated)
# -------------------------
allowed_orgs = [
    'ars', 'bia', 'blm', 'doi', 'epa', 'fws', 'nps', 'usda', 'usfs', 'usgs', 'census'
]
group_names = allowed_orgs[:] + ['all_government']

proper_group_names = {
    'ars': 'ARS', 'bia': 'BIA', 'blm': 'BLM', 'doc': 'DOC', 'doi': 'DOI',
    'epa': 'EPA', 'fas': 'FAS', 'fpac': 'FPAC', 'fsa': 'FSA', 'fws': 'FWS',
    'nass': 'NASS', 'nps': 'NPS', 'nrcs': 'NRCS', 'usda': 'USDA', 'usfs': 'USFS',
    'usgs': 'USGS', 'census': 'Census', 'all_government': 'All_Government'
}

allowed_domains = [f'{name}.gov' for name in allowed_orgs]

parent_groups = {
    'all_government': ['usda', 'doi', 'doc'],
    'usda': ['ars', 'fas', 'fpac', 'fsa', 'nass', 'nrcs', 'usfs', 'usgs', 'fws'],
    'doi': ['usgs', 'fws', 'nps', 'blm', 'epa', 'bia'],
    'doc': ['census']
}

def get_user_group(user_email):
    """Determine user's group based on email domain."""
    for domain in allowed_domains:
        if user_email.endswith(domain):
            return domain.replace(".gov", "")
    return None

def get_parent_groups(user_group):
    """Get all parent groups for a user group."""
    return parent_groups.get(user_group, [])

# -------------------------
# ✅ Authorization & Group Validation (Fully Integrated)
# -------------------------
def is_user_org_in_allowed_orgs(user_email):
    """Check if user belongs to an allowed organization."""
    session_key = f"user:{user_email}"

    user_orgs = redis_client.get(f"{session_key}:organizations")

    if user_orgs:
        user_orgs = json.loads(user_orgs)
    else:
        user_group = get_user_group(user_email)
        if user_group is None:
            return False
        proper_group_name = proper_group_names.get(user_group)
        groups_in_arcgis = json.loads(get_arcgis_groups())
        return proper_group_name in groups_in_arcgis

    return any(org in ["USDA", "DOI"] for org in user_orgs)

def is_user_selected_group_in_arcgis_groups(user_selected_group):
    """Check if a user-selected group exists in ArcGIS."""
    proper_group_name = proper_group_names.get(user_selected_group)

    cache_key = f"group_exists:{proper_group_name}"
    cached_group_exists = redis_client.get(cache_key)
    if cached_group_exists is not None:
        return cached_group_exists == 'True'

    return False  # Assume group doesn't exist if not in cache

# Helper Functions

def get_arcgis_group_titles():
    """
    Fetches the list of ArcGIS group titles stored in Redis.
    The data is stored under a Redis key with JSON structure.
    """
    try:
        groups_data = redis_client.get(ARCGIS_GROUPS_KEY)
        if groups_data:
            titles = json.loads(groups_data).get("Titles", [])
            logger.info(f"Fetched group titles from Redis: {titles}")
            return titles
        else:
            logger.info("No ArcGIS group titles found in Redis.")
            return []
    except Exception as e:
        logger.error(f"Error fetching group titles from Redis: {e}", exc_info=True)
        return []

def is_user_group_in_arcgis(search_title):
    """
    Check if a given group title exists in the ArcGIS groups stored in Redis.
    """
    logger.info(f"Checking if user group '{search_title}' exists in Redis.")
    titles = get_arcgis_group_titles()
    return search_title in titles

def store_arcgis_group_titles(titles):
    """
    Store a list of ArcGIS group titles in Redis.
    """
    try:
        redis_client.set(ARCGIS_GROUPS_KEY, json.dumps({"Titles": titles}))
        logger.info(f"Stored ArcGIS group titles in Redis: {titles}")
    except Exception as e:
        logger.error(f"Error storing group titles in Redis: {e}", exc_info=True)

def add_arcgis_group_title(new_title):
    """
    Add a new ArcGIS group title to the existing list in Redis.
    """
    titles = get_arcgis_group_titles()
    if new_title not in titles:
        titles.append(new_title)
        store_arcgis_group_titles(titles)
        logger.info(f"Added new ArcGIS group title: {new_title}")
        return True
    logger.info(f"Group title '{new_title}' already exists.")
    return False

def remove_arcgis_group_title(title_to_remove):
    """
    Remove a specific ArcGIS group title from Redis.
    """
    titles = get_arcgis_group_titles()
    if title_to_remove in titles:
        titles.remove(title_to_remove)
        store_arcgis_group_titles(titles)
        logger.info(f"Removed ArcGIS group title: {title_to_remove}")
        return True
    logger.info(f"Group title '{title_to_remove}' not found.")
    return False

# Main Logic for Assigning Users to Groups

def arcgis_webhook_assign_user_to_groups(username):
    logger.info(f"Webhook triggered for user '{username}' to assign them to groups.")
    user = arcgis_api.get_user_from_username(username)
    user_email = user.get('email')
    user_group = get_user_group(user_email)
    parent_groups = get_parent_groups(user_group)
    all_groups = parent_groups[:]
    all_groups.append(user_group)
    # proper_group_names = proper_group_names
    arcgis_api.add_user_to_groups(user, all_groups, proper_group_names)
    logger.info(f"Added user {user_email} to groups {all_groups}")

def arcgis_webhook_assign_user_to_self_selected_group(username, user_groups_list):
    logger.info(f"Webhook triggered for user '{username}' to assign them to their self-selected group.")
    user = arcgis_api.get_user_from_username(username)
    user_email = user.get('email')
    user_group = user_groups_list[-1]
    parent_groups = get_parent_groups(user_group)
    all_groups = parent_groups[:]
    all_groups.append(user_group)
    # proper_group_names = get_user_group.proper_group_names
    arcgis_api.add_user_to_groups(user, all_groups, proper_group_names)
    logger.info(f"Added user {user_email} to groups {all_groups}")

def assign_user_to_groups(user_email, user=None, user_self_selected_group=None):
    logger.info(f"Assigning user '{user_email}' to groups.")
    if user is None:
        user = arcgis_api.get_user_by_email(user_email)
    user_group = user_self_selected_group or get_user_group(user_email)
    parent_groups = get_parent_groups(user_group)
    all_groups = parent_groups[:]
    all_groups.append(user_group)
    # proper_group_names = proper_group_names
    arcgis_api.add_user_to_groups(user, all_groups, proper_group_names)
    logger.info(f"Assigned user {user_email} to groups {all_groups}")

def add_user_to_groups(data):
    """
    This function processes the incoming user data and assigns them to appropriate ArcGIS groups.
    """
    operation = data['events'][0]['operation']
    source = data['events'][0]['source']
    user_was_created = operation == 'add' and source == 'users'
    user_was_updated = operation == 'update' and source == 'users'

    if user_was_updated or user_was_created:
        username = data['events'][0]['username']
        user = arcgis_api.get_user_from_username(username)
        user_email = user.get('email')
        # Store mapping from username to email in Redis
        add_arcgis_group_title(user_email)  # Ensure the email is stored correctly as a title or group

        if user_was_created:
            user_groups = get_email_to_user_groups(user_email)
            if user_groups:
                # Assign user to their self-selected groups
                arcgis_webhook_assign_user_to_self_selected_group(
                    username, json.loads(user_groups['user_groups'])
                )
            else:
                # If no groups selected, assign user to default groups
                arcgis_webhook_assign_user_to_groups(username)

    user_was_deleted = operation == 'delete' and source == 'user'
    if user_was_deleted:
        username = data['events'][0]['id']
        user_email_dict = get_username_to_email(username)
        user_email = user_email_dict['user_email']
        # Remove user mappings and access
        delete_username_to_email(username)
        delete_user_auth_access(user_email)
        delete_email_to_user_groups(user_email)

    return 'OK', 200
