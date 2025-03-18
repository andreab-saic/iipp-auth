import redis
from types import SimpleNamespace
from dotenv import load_dotenv
import os
import sys

load_dotenv()

AUTH_SERVICE_DOMAIN = os.environ.get('AUTH_SERVICE_DOMAIN')
REDIS_SERVER = os.environ.get('REDIS_SERVER')

FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')

ARCGIS_GROUPS_KEY = "arcgis_groups"

ARCGIS_CLIENT_URL  =  os.environ.get('ARCGIS_CLIENT_URL')
ARCGIS_CLIENT_ID = os.environ.get('ARCGIS_CLIENT_ID')
ARCGIS_CLIENT_SECRET = os.environ.get('ARCGIS_CLIENT_SECRET')
ARCGIS_OIDC_CLIENT_ID = os.environ.get('ARCGIS_OIDC_CLIENT_ID')
ARCGIS_WEBHOOK_SECRET = os.environ.get('ARCGIS_WEBHOOK_SECRET')
REDIRECT_URL = f'https://{AUTH_SERVICE_DOMAIN}/callback'
USER_NOT_IN_ALLOWED_AGENCY_URL = f'https://{AUTH_SERVICE_DOMAIN}/user_not_in_allowed_groups'
USER_NOT_IN_ALLOWED_AGENCY_REDIRECT_DELAY_SECONDS = 60
SELF_SELECT_GROUP_FORM_URL = f'https://{AUTH_SERVICE_DOMAIN}/select_user_groups'
PUBLIC_URL = ARCGIS_CLIENT_URL
ARCGIS_LOGIN_CALLBACK_URL = f'https://{AUTH_SERVICE_DOMAIN}/arcgis_callback'
ARCGIS_LOGIN_REDIRECT_URL = os.environ.get('ARCGIS_LOGIN_REDIRECT_URL')
ADD_USER_TO_GROUP_ASSIGNMENT_QUEUE_URL = f'https://{AUTH_SERVICE_DOMAIN}/add_user_to_group_assignment_queue'

# AUTH = os.environ.get('AUTH_LOGIN_GOV')

# This is imported from secret auth-secret  that contains a python script with the authentication configuration to login.gov

sys.path.insert(0, "/etc/config")

from auth_config import AUTH

# Import Private Key from secrets

AUTH_PRIVATE_KEY = os.environ.get('AUTH_PRIVATE_KEY')

# Initialize Redis client with SSL enabled
redis_client = redis.Redis(
    host=REDIS_SERVER,
    port=6379,
    db=0,
    decode_responses=True,
    ssl=True,  # Enable SSL explicitly
    ssl_cert_reqs=None,  # Disable certificate verification (safe in AWS)
    socket_timeout=10,  # Increase timeout for slow responses
    socket_connect_timeout=10,
    retry_on_timeout=True,
    health_check_interval=30,  # Automatically check connection health
)
