import sys
import os
import unittest
from unittest.mock import patch, MagicMock


# Add the 'app/routes' directory to the sys.path so Python can find _auth
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'routes')))


import _auth  # Import the module being tested

class TestAuthUtils(unittest.TestCase):

    @patch("builtins.open", new_callable=MagicMock)
    @patch("cryptography.hazmat.primitives.serialization.load_pem_private_key")
    def test_load_pem_key(self, mock_load_pem_key, mock_open):
        """Ensure PEM key loads correctly"""
        mock_load_pem_key.return_value.private_bytes.return_value = b"mocked_pem_key"
        pem_key = _auth.load_pem_key()
        self.assertEqual(pem_key, b"mocked_pem_key")
        mock_open.assert_called_once()
        mock_load_pem_key.assert_called_once()

    @patch("_auth.generate_jwt_token", return_value="mock_jwt_token")
    def test_construct_idp_token_post(self, mock_generate_jwt_token):
        """Ensure IDP token POST request is constructed correctly"""
        token_url, headers, data = _auth.construct_idp_token_post("mock_code")
        self.assertIn("grant_type", data)
        self.assertEqual(headers["Content-Type"], "application/x-www-form-urlencoded")
        self.assertTrue("IDP" in dir(_auth.AUTH))  # Ensure IDP config exists

    @patch("requests.post")
    def test_handle_idp_token_response_success(self, mock_post):
        """Ensure IDP token response is handled successfully"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "mock_access_token"}
        access_token = _auth.handle_idp_token_response(mock_response)
        self.assertEqual(access_token, "mock_access_token")

    @patch("requests.post")
    def test_handle_idp_token_response_failure(self, mock_post):
        """Ensure failure in IDP token response handling"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error_description": "Invalid request"}
        error_message, status_code = _auth.handle_idp_token_response(mock_response)
        self.assertIn("Invalid request", error_message)
        self.assertEqual(status_code, 400)

if __name__ == "__main__":
    unittest.main()
