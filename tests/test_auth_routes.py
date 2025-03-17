import unittest
import sys
import os
from unittest.mock import patch

from flask import Flask

# Add the 'app/routes' directory to the sys.path so Python can find _auth
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'routes')))

from routes.auth import auth_blueprint  # Ensure correct import

class TestAuthRoutes(unittest.TestCase):

    def setUp(self):
        """Set up Flask test client"""
        self.app = Flask(__name__)
        self.app.secret_key = "test_secret"
        self.app.register_blueprint(auth_blueprint, url_prefix="/auth")
        self.client = self.app.test_client()

    @patch("routes.auth.get_auth_code_from_idp", return_value="mock_redirect_response")
    def test_auth_route(self, mock_get_auth_code_from_idp):
        """Test the /auth route"""
        response = self.client.get("/auth")
        self.assertIn(response.status_code, [200, 302])  # Allow redirects
        cookies = response.headers.getlist("Set-Cookie")
        self.assertTrue(any("session=" in cookie for cookie in cookies))

if __name__ == "__main__":
    unittest.main()
