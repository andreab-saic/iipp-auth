import sys
import os
import unittest
from unittest import mock, TestCase
from unittest.mock import patch, MagicMock
import jwt
import time


# Add the 'app/routes' directory to the sys.path so Python can find _auth
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'routes')))

import _auth  # Import the module being tested

class TestAuth(unittest.TestCase):

    @patch("os.urandom", return_value=os.urandom(50))
    def test_generate_nonce(self, mock_urandom):
        """Ensure nonce is 50 characters long"""
        nonce = _auth.generate_nonce()
        self.assertEqual(len(nonce), 50)

    def test_generate_auth_code(self):
        """Ensure auth code generation returns a string"""
        auth_code = _auth.generate_auth_code(30)
        self.assertIsInstance(auth_code, str)
        self.assertGreaterEqual(len(auth_code), 30)

    @patch("_auth.generate_nonce", return_value="mock_nonce")
    @patch("jwt.encode", return_value="mock_jwt_token")
    def test_generate_jwt_token(self, mock_jwt_encode, mock_generate_nonce):
        """Ensure JWT token is generated properly"""
        aud = "mock_audience"
        client_id = "mock_client_id"
        token = _auth.generate_jwt_token(aud, client_id)
        self.assertEqual(token, "mock_jwt_token")
        mock_jwt_encode.assert_called_once()

if __name__ == "__main__":
    unittest.main()
