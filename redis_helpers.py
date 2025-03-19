import redis
import json
import logging

# Initialize Redis client
from config import redis_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('./redis.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Define Redis Keys 
AUTH_CODE_TO_ACCESS_TOKEN_KEY = 'auth-code-to-access-token'
ACCESS_TOKEN_TO_USERINFO_KEY = 'access-token-to-userinfo'
USERNAME_TO_EMAIL_KEY = 'username-to-email'
USER_AUTH_ACCESS_KEY = 'user-auth-access'
USER_EMAIL_TO_USER_GROUPS_KEY = 'user-email-to-user-groups'
ARCGIS_USER_GROUPS = 'arcgis_groups'

# Helper function to set data in Redis 
def redis_set(key, item):
    try:
        redis_client.hmset(key, item)  # Use hash mapping for structured data
        logger.info(f"Item inserted in Redis: {item}")
    except Exception as e:
        logger.error(f"Error writing to Redis: {e}")

# Helper function to get data from Redis
def redis_get(key):
    try:
        item = redis_client.hgetall(key)
        if item:
            logger.info(f"Item retrieved from Redis: {item}")
            return item
        else:
            logger.info(f"No item found in Redis for key: {key}")
            return None
    except Exception as e:
        logger.error(f"Error reading from Redis: {e}")
        return None

# Helper function to delete data from Redis
def redis_delete(key):
    try:
        redis_client.delete(key)
        logger.info(f"Item deleted from Redis: {key}")
    except Exception as e:
        logger.error(f"Error deleting from Redis: {e}")

# Functions

def put_auth_code_to_access_token(auth_code, access_token):
    item = {
        'auth_code': auth_code,
        'access_token': access_token
    }
    redis_set(f"{AUTH_CODE_TO_ACCESS_TOKEN_KEY}:{auth_code}", item)
    logger.info(f"put_auth_code_to_access_token - Auth Code: {auth_code}, Access Token: {access_token}")

def put_access_token_to_userinfo(access_token, userinfo):
    item = {
        'access_token': access_token,
        'userinfo': userinfo
    }
    redis_set(f"{ACCESS_TOKEN_TO_USERINFO_KEY}:{access_token}", item)
    logger.info(f"put_access_token_to_userinfo - Access Token: {access_token}, User Info: {userinfo}")

def put_username_to_email(username, email):
    item = {
        'username': username,
        'user_email': email
    }
    redis_set(f"{USERNAME_TO_EMAIL_KEY}:{username}", item)
    logger.info(f"put_username_to_email - Username: {username}, Email: {email}")

def put_user_auth_access(email, auth_access):
    item = {
        'user_email': email,
        'auth_access': json.dumps(auth_access)  # Store as JSON string
    }
    redis_set(f"{USER_AUTH_ACCESS_KEY}:{email}", item)
    logger.info(f"put_user_auth_access - Email: {email}, Auth Access: {auth_access}")

def put_email_to_user_groups(email, user_groups):
    item = {
        'user_email': email,
        'user_groups': json.dumps(user_groups)  # Store as JSON string
    }
    redis_set(f"{USER_EMAIL_TO_USER_GROUPS_KEY}:{email}", item)
    logger.info(f"put_email_to_user_groups - Email: {email}, User Groups: {user_groups}")

# Functions to get data from Redis

def get_auth_code_to_access_token(auth_code):
    response = redis_get(f"{AUTH_CODE_TO_ACCESS_TOKEN_KEY}:{auth_code}")
    logger.info(f"get_auth_code_to_access_token - Response: {response}")
    return response

def get_access_token_to_userinfo(access_token):
    response = redis_get(f"{ACCESS_TOKEN_TO_USERINFO_KEY}:{access_token}")
    logger.info(f"get_access_token_to_userinfo - Response: {response}")
    return response

def get_username_to_email(username):
    response = redis_get(f"{USERNAME_TO_EMAIL_KEY}:{username}")
    logger.info(f"get_username_to_email - Response: {response}")
    return response

def get_user_auth_access(email):
    response = redis_get(f"{USER_AUTH_ACCESS_KEY}:{email}")
    logger.info(f"get_user_auth_access - Response: {response}")
    return response

def get_email_to_user_groups(email):
    response = redis_get(f"{USER_EMAIL_TO_USER_GROUPS_KEY}:{email}")
    logger.info(f"get_email_to_user_groups - Response: {response}")
    return response

def get_arcgis_groups():
    response = redis_get(ARCGIS_USER_GROUPS)
    logger.info(f"get_arcgis_groups - Response: {response}")
    return response

# Functions to delete data from Redis

def delete_auth_code_to_access_token(auth_code):
    redis_delete(f"{AUTH_CODE_TO_ACCESS_TOKEN_KEY}:{auth_code}")
    logger.info(f"delete_auth_code_to_access_token - Auth Code: {auth_code}")

def delete_access_token_to_userinfo(access_token):
    redis_delete(f"{ACCESS_TOKEN_TO_USERINFO_KEY}:{access_token}")
    logger.info(f"delete_access_token_to_userinfo - Access Token: {access_token}")

def delete_username_to_email(username):
    redis_delete(f"{USERNAME_TO_EMAIL_KEY}:{username}")
    logger.info(f"delete_username_to_email - Username: {username}")

def delete_user_auth_access(email):
    redis_delete(f"{USER_AUTH_ACCESS_KEY}:{email}")
    logger.info(f"delete_user_auth_access - Email: {email}")

def delete_email_to_user_groups(email):
    redis_delete(f"{USER_EMAIL_TO_USER_GROUPS_KEY}:{email}")
    logger.info(f"delete_email_to_user_groups - Email: {email}")

# Functions to check things

def does_user_exist(email):
    return get_user_auth_access(email) is not None

def create_user(email, auth_access={}):
    if does_user_exist(email):
        return False
    put_user_auth_access(email, auth_access)
    return True

def is_user_disallowed(auth_access):
    return auth_access.get('is_disallowed') if auth_access else None

def has_user_selected_group(auth_access):
    return auth_access.get('has_selected_group') if auth_access else None

def update_auth_access(email, field_name, new_value):
    key = f"{USER_AUTH_ACCESS_KEY}:{email}"
    try:
        redis_client.hset(key, field_name, new_value)
        logger.info(f"update_auth_access - Email: {email}, Field: {field_name}, New Value: {new_value}")
    except Exception as e:
        logger.error(f"Error updating item in Redis: {e}")
