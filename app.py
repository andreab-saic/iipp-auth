import logging
import json
import os


from flask import Flask, redirect, request, make_response, session, jsonify, render_template_string
from flask_cors import CORS
from flask_session import Session

# gevent.monkey.patch_all()

from config import redis_client, AUTH_SERVICE_DOMAIN, FLASK_SECRET_KEY
from routes import routes_blueprint


# Logging setup
def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        file_handler = logging.FileHandler(os.path.join(os.getcwd(), 'app.log'))
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s-%(lineno)d - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger

logger = setup_logging()

def create_app():
    # Initialize the Flask application
    app = Flask(__name__)

    # Configure the app
    app.secret_key = FLASK_SECRET_KEY
    app.config.update({
        'SESSION_TYPE': 'redis',
        'SESSION_REDIS': redis_client,
        'SESSION_COOKIE_NAME': 'iipp_gms',
        'SESSION_COOKIE_DOMAIN': AUTH_SERVICE_DOMAIN,
        'SESSION_COOKIE_SAMESITE': None,
        'SESSION_COOKIE_SECURE': True,
        'SESSION_PERMANENT': False,
        'SESSION_USE_SIGNER': True,
        'SESSION_JSON': json,
        'DEBUG': True
    })

    # Initialize CORS after app is created
    CORS(app, supports_credentials=True)

    # Initialize session after app creation
    Session(app)
    # Register before_request function
    @app.before_request
    def log_request():
      app.logger.info(f"Request URL: {request.url} Method: {request.method}")

    # Register after_request function
    @app.after_request
    def commit_session(response):
        session.modified = True
        return response

    # Register the blueprint for routing
    app.register_blueprint(routes_blueprint)


    return app

# Ensure the app is created properly and the application starts
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
