"""
auth.py — Authentication logic: registration, login, logout.

Uses werkzeug.security for password hashing and Flask's session
for keeping a user logged in across requests.
"""

import secrets
import random
import string
from flask import session, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from database import query_db, execute_db
from models import User


# ---------------------------------------------------------------------------
# Google OAuth Login / Register
# ---------------------------------------------------------------------------

def login_or_register_google_user(email: str, name: str, avatar_url: str) -> dict:
    """
    Check if email exists. If so, log them in.
    If not, create a new user with a random unguessable password.
    """
    if not email:
        return {"success": False, "error": "Email is required"}

    email = email.strip().lower()
    row = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)

    # Ensure avatar_url column exists safely
    try:
        execute_db("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    except Exception:
        pass

    if row:
        user = User(row)
        _set_session(user)
        # Grab their Google avatar if they don't have a profile picture yet
        if not dict(row).get("avatar_url") and avatar_url:
            execute_db("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user.id))
        return {"success": True, "user": user}

    # User doesn't exist, create a new one!
    base_username = name.replace(" ", "").replace("#", "").lower()
    if not base_username:
        base_username = "player"
        
    discriminator = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    username = f"{base_username}#{discriminator}"
    
    while query_db("SELECT id FROM users WHERE username = ?", (username,), one=True):
        discriminator = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        username = f"{base_username}#{discriminator}"

    # Insert new user with a completely random unguessable password
    dummy_password = secrets.token_urlsafe(32)
    password_hash = generate_password_hash(dummy_password)

    user_id = execute_db(
        """
        INSERT INTO users (username, email, password_hash, xp, level, avatar_url)
        VALUES (?, ?, ?, 0, 1, ?)
        """,
        (username, email, password_hash, avatar_url),
    )

    row = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    user = User(row)
    _set_session(user)
    return {"success": True, "user": user}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_USER_ID = "user_id"
SESSION_USERNAME = "username"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_user(username: str, email: str, password: str) -> dict:
    """
    Validate input and create a new user record.

    Returns:
        {"success": True, "user_id": <int>}
        {"success": False, "error": "<message>"}
    """
    base_username = (username or "").strip().replace("#", "")
    email = (email or "").strip().lower()

    # --- Basic validation ---
    if not base_username or not email or not password:
        return {"success": False, "error": "All fields are required."}

    if len(base_username) < 3:
        return {
            "success": False,
            "error": "Username base must be at least 3 characters.",
        }

    if len(password) < 6:
        return {
            "success": False,
            "error": "Password must be at least 6 characters.",
        }

    if "@" not in email:
        return {
            "success": False,
            "error": "Please enter a valid email address.",
        }

    # --- Duplicate check for email ---
    existing = query_db(
        "SELECT id FROM users WHERE email = ?",
        (email,),
        one=True,
    )
    if existing:
        return {"success": False, "error": "Email is already taken."}

    # --- Generate unique full username ---
    discriminator = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    full_username = f"{base_username}#{discriminator}"
    while query_db("SELECT id FROM users WHERE username = ?", (full_username,), one=True):
        discriminator = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        full_username = f"{base_username}#{discriminator}"

    # --- Insert new user ---
    password_hash = generate_password_hash(password)
    user_id = execute_db(
        """
        INSERT INTO users (username, email, password_hash, xp, level)
        VALUES (?, ?, ?, 0, 1)
        """,
        (full_username, email, password_hash),
    )

    return {"success": True, "user_id": user_id}


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def login_user(username: str, password: str) -> dict:
    """
    Verify credentials and store user info in the session.
    The `username` parameter can be either the username or the email address.

    Returns:
        {"success": True, "user": User}
        {"success": False, "error": "<message>"}
    """
    username = (username or "").strip()

    if not username or not password:
        return {
            "success": False,
            "error": "Username or email and password are required.",
        }

    row = query_db(
        "SELECT * FROM users WHERE username = ? OR email = ?",
        (username, username.lower()),
        one=True,
    )

    if row is None:
        return {"success": False, "error": "Invalid username/email or password."}

    if not check_password_hash(row["password_hash"], password):
        return {"success": False, "error": "Invalid username/email or password."}

    # Persist login in Flask session
    user = User(row)
    _set_session(user)

    return {"success": True, "user": user}


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


def logout_user():
    """Clear the session to log the current user out."""
    session.clear()


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _set_session(user: User):
    """Write user info to the Flask session."""
    session[SESSION_USER_ID] = user.id
    session[SESSION_USERNAME] = user.username
    if current_app.config.get("SESSION_PERMANENT"):
        session.permanent = True


def get_current_user() -> User | None:
    """
    Return the logged-in User object, or None if not authenticated.
    Makes a DB round-trip; call sparingly (e.g. once per request in a
    before_request hook or a context processor).
    """
    user_id = session.get(SESSION_USER_ID)
    if user_id is None:
        return None

    # Safely ensure the role column exists
    try:
        execute_db("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    except Exception:
        pass

    row = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if row:
        user = User(row)
        user.avatar_url = row["avatar_url"] if "avatar_url" in row.keys() else None
        user.role = row["role"] if "role" in row.keys() else "user"
        return user
    return None


def login_required(f):
    """
    Decorator that redirects unauthenticated users to the login page.

    Usage::

        @main.route("/dashboard")
        @login_required
        def dashboard():
            ...
    """
    from functools import wraps
    from flask import redirect, url_for

    @wraps(f)
    def decorated(*args, **kwargs):
        if SESSION_USER_ID not in session:
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    """
    Decorator that restricts access to users with the 'admin' role.
    """
    from functools import wraps
    from flask import redirect, url_for, flash

    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or getattr(user, "role", "user") != "admin":
            flash("Access Denied. Administrator privileges required.", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)

    return decorated
