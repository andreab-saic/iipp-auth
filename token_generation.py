import base64
import json
import os
import secrets
import time
import re
import jwt
import logging
from flask import redirect
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from config import redis_client, AUTH, AUTH_PRIVATE_KEY

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('./token_generation.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# -------------------------
# ✅ Auth Functions (Integrated)
# -------------------------

def generate_nonce():
    """Generate a secure nonce."""
    logger.debug("Generating nonce")
    nonce = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8')[:50]
    logger.debug("Generated nonce: %s", nonce)
    return nonce

def load_pem_key():
    """Load private key for JWT signing from the AUTH_PRIVATE_KEY environment variable."""
    logger.debug("Loading PEM private key from environment variable")
    try:
        private_key_pem = os.getenv('AUTH_PRIVATE_KEY')
        
        if not private_key_pem:
            raise ValueError("AUTH_PRIVATE_KEY environment variable is not set")

        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )

        pem_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        logger.info("Successfully loaded PEM key from environment variable")
        return pem_key
    except Exception as e:
        logger.error("Error loading PEM key: %s", e)
        raise


pem_key = load_pem_key()

def generate_auth_code(length=30):
    """Generate a secure authentication code."""
    logger.debug("Generating authorization code of length %d", length)
    auth_code = secrets.token_urlsafe(length)
    logger.debug("Generated authorization code: %s", auth_code)
    # redis_client.setex(f"auth_code:{auth_code}", 3600, auth_code)
    return auth_code

def generate_jwt_token(aud, client_id):
    """Generate a JWT token."""
    logger.debug("Generating JWT token for audience: %s, client_id: %s", aud, client_id)
    nonce = generate_nonce()
    jwt_token = jwt.encode({
        'iss': client_id,
        'sub': client_id,
        'aud': aud,
        'jti': nonce,
        'exp': int(time.time()) + 300,
    }, pem_key, algorithm='RS256')
    logger.debug("Generated JWT token: %s", jwt_token)
    return jwt_token

def generate_oidc_state(length=16):
    """Generate an OIDC state value."""
    logger.debug("Generating OIDC state of length %d", length)
    state = secrets.token_urlsafe(length)
    logger.debug("Generated OIDC state: %s", state)
    return state

oidc_state = generate_oidc_state()

def get_auth_code_from_idp():
    """Redirect user to Identity Provider (IDP) for authentication."""
    client_id = AUTH.IDP.CLIENT_ID
    base_url = AUTH.IDP.BASE_URL
    logger.info("Redirecting to IDP authorization endpoint")
    redirect_url = (
        f"{base_url}"
        f"{AUTH.IDP.AUTHORIZATION_ROUTE}?"
        f"acr_values={AUTH.IDP.ACR_VALUE}&"
        f"client_id={client_id}&"
        f"nonce={generate_nonce()}&"
        f"prompt={AUTH.IDP.PROMPT}&"
        f"redirect_uri={AUTH.IDP.REDIRECT_URI}&"
        f"response_type={AUTH.IDP.RESPONSE_TYPE}&"
        f"scope={AUTH.IDP.SCOPE}&"
        f"state={oidc_state}&"
        f"client_assertion_type={AUTH.IDP.CLIENT_ASSERTION_TYPE}&"
        f"client_assertion={generate_jwt_token(base_url, client_id)}"
    )
    logger.debug("Redirect URL: %s", redirect_url)
    return redirect(redirect_url)

def construct_idp_token_post(idp_code):
    """Construct IDP token POST request."""
    logger.info("Constructing IDP token POST request")
    token_url = f"{AUTH.IDP.BASE_URL}{AUTH.IDP.TOKEN_ROUTE}"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    jwt_token = generate_jwt_token(token_url, AUTH.IDP.CLIENT_ID)
    data = {
        'grant_type': 'authorization_code',
        'code': idp_code,
        'client_assertion_type': AUTH.IDP.CLIENT_ASSERTION_TYPE,
        'client_assertion': jwt_token,
    }
    logger.debug("Constructed token POST data: %s", json.dumps(data, indent=2))
    return token_url, headers, data

def handle_idp_token_response(idp_token_response):
    """Process IDP token response and store data in Redis session."""
    logger.info("Handling IDP token response")
    if idp_token_response.status_code != 200:
        error_message = 'Error: Failed to exchange code for token'
        try:
            error_data = idp_token_response.json()
            logger.error("IDP token response error (JSON): %s", json.dumps(error_data, indent=2))
            error_description = error_data.get('error_description', 'No description provided')
            error_message += f' - {error_description}'
        except json.JSONDecodeError:
            raw_response = idp_token_response.text or 'No additional error info'
            logger.error("IDP token response error (RAW): %s", raw_response)
            error_message += f' - Raw response: {raw_response}'
        
        logger.error(
            "Full IDP token response:\n"
            "Status Code: %s\n"
            "Headers: %s\n"
            "Content: %s",
            idp_token_response.status_code,
            idp_token_response.headers,
            idp_token_response.text
        )

        return error_message, idp_token_response.status_code

    try:
        token_data = idp_token_response.json()
    except json.JSONDecodeError:
        logger.error("Failed to decode IDP token response JSON: %s", idp_token_response.text)
        return "Error: Invalid token response format", 500

    access_token = token_data.get('access_token')
    if not access_token:
        logger.error("IDP token response missing access token: %s", json.dumps(token_data, indent=2))
        return "Error: Missing access token in response", 500

    logger.info("IDP token exchange successful")
    redis_client.setex(f"access_token:{access_token}", 3600, json.dumps(token_data))
    return access_token

def construct_idp_userinfo_get(access_token):
    """Construct IDP userinfo request."""
    logger.info("Constructing IDP userinfo GET request")
    userinfo_url = f"{AUTH.IDP.BASE_URL}{AUTH.IDP.USERINFO_ROUTE}"
    headers = {'Authorization': f'Bearer {access_token}'}
    logger.debug("Userinfo GET request URL: %s", userinfo_url)
    return userinfo_url, headers

def handle_userinfo_response(userinfo_response):
    """Handle IDP userinfo response."""
    logger.info("Handling IDP userinfo response")
    if userinfo_response.status_code != 200:
        error_message = 'Error: Failed to exchange token for userinfo'
        try:
            error_data = userinfo_response.json()
            logger.error("IDP userinfo response error: %s", error_data)
            error_description = error_data.get('error_description', '')
            if error_description:
                error_message += f' - {error_description}'
        except json.JSONDecodeError:
            res = userinfo_response.text or 'no additional error info'
            error_message += f' - {res}'
        logger.error("IDP userinfo response error: %s", error_message)
        return error_message, 500

    logger.info("IDP userinfo exchange successful")
    return userinfo_response.json()

def parse_name_and_organizations(data: str):
    """Parse name and organizations from data."""
    # Extracting the name and removing the value in parentheses
    possible_delimiters = ['+', ',', ';', '/']
    name_delimiter = None
    for delimiter in possible_delimiters:
        if delimiter in data:
            name_delimiter = delimiter
            break
    name_match = re.search(fr'CN=([^\{name_delimiter}]+)', data)
    name = name_match.group(1).strip() if name_match else None
    name = re.sub(r'\(.*\)', '', name).strip()
    name = name.title()

    # Extracting the organizations
    organizations = re.findall(r'OU=([^,]+)', data)
    organizations_str = ', '.join(organizations) if organizations else None

    return name, organizations_str


def parse_x509_subject(x509_subject):
    """Parse x509 subject for user name and organizations."""
    logger.info("Parsing x509 subject for user name and organizations")
    name, organizations = parse_name_and_organizations(x509_subject)
    given_name = name.split(' ')[0].split(',')[0].split(';')[0].split('+')[0]
    family_name = name.split(' ', 1)[1].split(',')[0].split(';')[0].split('+')[0]
    return given_name, family_name, organizations


def parse_auth_access(user_auth_access):
    user_auth_access_dict = json.loads(user_auth_access)
    user_is_disallowed = user_auth_access_dict.get('is_disallowed')
    user_has_selected_group = user_auth_access_dict.get('has_selected_group')
    user_previous_selected_group = user_auth_access_dict.get('disallowed_selected_group')
    logger.info(f'User permissions loaded: {user_auth_access_dict}')
    return user_is_disallowed, user_has_selected_group, user_previous_selected_group
