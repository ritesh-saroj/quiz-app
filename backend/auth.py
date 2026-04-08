# User Authentication Logic

import secrets
import random
import string
from flask import session, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from database import query_db, execute_db
from models import User


# Google OAuth logic

def login_or_register_google_user(email: str, name: str, avatar_url: str) -> dict:
    # Login or register google user
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

# Auth Constants

SESSION_USER_ID = "user_id"
SESSION_USERNAME = "username"


# User Registration


def register_user(username: str, email: str, password: str) -> dict:
    # Register user logic
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


# User Login


def login_user(username: str, password: str) -> dict:
    # Log user in
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


# User Logout


def logout_user():
    # Clear user session
    session.clear()


# Session Helpers


def _set_session(user: User):
    # Set user session
    session[SESSION_USER_ID] = user.id
    session[SESSION_USERNAME] = user.username
    if current_app.config.get("SESSION_PERMANENT"):
        session.permanent = True


def get_current_user() -> User | None:
    # Get current user
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
    # Requires user login
    from functools import wraps
    from flask import redirect, url_for

    @wraps(f)
    def decorated(*args, **kwargs):
        if SESSION_USER_ID not in session:
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    # Requires admin role
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
