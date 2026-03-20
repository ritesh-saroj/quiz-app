import os
import sys

# ---------------------------------------------------------------------------
# Make sure sibling packages (config/) are importable when running app.py
# directly from the backend/ directory.
# ---------------------------------------------------------------------------
# Root of the project (one level up from backend/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask  # noqa: E402

# Import configuration values from config/settings.py
import config.settings as settings  # noqa: E402

# ---------------------------------------------------------------------------
# Factory: create and configure the Flask application
# ---------------------------------------------------------------------------


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )

    # --- Load configuration ---
    app.secret_key = settings.SECRET_KEY
    app.config["DEBUG"] = settings.DEBUG
    app.config["DATABASE_PATH"] = settings.DATABASE_PATH
    app.config["SCHEMA_PATH"] = settings.SCHEMA_PATH
    app.config["SESSION_PERMANENT"] = settings.SESSION_PERMANENT

    # --- Initialize OAuth ---
    from routes import oauth  # noqa: E402
    oauth.init_app(app)

    # --- Register routes Blueprint ---
    from routes import main as main_blueprint  # noqa: E402

    app.register_blueprint(main_blueprint)

    # --- Initialise database (creates tables if they don't exist) ---
    from database import init_db

    init_db(app)

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
