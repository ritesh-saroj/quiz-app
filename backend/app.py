import os
import sys

# Path setup 
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Backend path
BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from flask import Flask  # noqa: E402

# Load settings
import config.settings as settings  # noqa: E402

# App factory
def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )

    # Config app
    app.secret_key = settings.SECRET_KEY
    app.config["DEBUG"] = settings.DEBUG
    app.config["DATABASE_PATH"] = settings.DATABASE_PATH
    app.config["SCHEMA_PATH"] = settings.SCHEMA_PATH
    app.config["SESSION_PERMANENT"] = settings.SESSION_PERMANENT

    # Init OAuth
    from routes import oauth  # noqa: E402
    oauth.init_app(app)

    # Register blueprints
    from routes import main as main_blueprint  # noqa: E402

    app.register_blueprint(main_blueprint)

    # Init database
    from database import init_db

    init_db(app)

    return app


# Main entry
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
