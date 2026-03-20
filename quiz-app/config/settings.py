import os

# Base directory of the config folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Flask Core Settings ---
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = True

# --- Database Settings ---
DATABASE_PATH = os.path.join(BASE_DIR, "..", "database", "quiz_app.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "..", "database", "schema.sql")

# --- Session Settings ---
SESSION_PERMANENT = False
SESSION_TYPE = "filesystem"
