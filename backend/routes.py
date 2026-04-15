import os
import uuid
import random
import string
import json
import time
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    session,
    request,
    current_app,
    flash,
    jsonify,
)

from auth import (
    register_user,
    login_user,
    logout_user,
    login_required,
    get_current_user,
    login_or_register_google_user,
    admin_required,
)
from quiz_engine import (
    start_quiz,
    get_current_question,
    get_quiz_progress,
    submit_answer,
    finish_quiz,
    get_user_results,
)
from database import query_db, execute_db
from gamification import get_current_streak, xp_required_for_level, get_rank_title

from authlib.integrations.flask_client import OAuth

oauth = OAuth()
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Create a Blueprint so routes can be registered on the app from app.py
main = Blueprint("main", __name__)

@main.route("/login/google")
def google_login():
    # Google Login redirect
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        flash("Google Login is not configured. Please set GOOGLE_CLIENT_ID.", "error")
        return redirect(url_for("main.login"))
    redirect_uri = url_for("main.google_authorize", _external=True)
    return google.authorize_redirect(redirect_uri)


@main.route("/login/google/authorize")
def google_authorize():
    # Google Login callback
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if not user_info:
        flash("Google authentication failed.", "error")
        return redirect(url_for("main.login"))

    email = user_info.get("email")
    if not email:
        flash("Google did not provide an email address.", "error")
        return redirect(url_for("main.login"))

    name = user_info.get("name", "Player")
    picture = user_info.get("picture")

    result = login_or_register_google_user(email, name, picture)
    if result["success"]:
        return redirect(url_for("main.dashboard"))
    
    flash("Could not sign in with Google.", "error")
    return redirect(url_for("main.login"))

# Inject current user


@main.context_processor
def inject_user():
    return {"current_user": get_current_user()}


# Admin Routes

@main.route("/admin")
@admin_required
def admin_dashboard():
    # Admin dashboard stats
    # Fetch Stats
    total_users = query_db("SELECT COUNT(*) as count FROM users", one=True)["count"]
    total_quizzes = query_db("SELECT COUNT(*) as count FROM quiz_results", one=True)["count"]
    total_questions = query_db("SELECT COUNT(*) as count FROM questions", one=True)["count"]
    
    # Fetch questions (Limit to 150 for UI performance, order by newest)
    questions_rows = query_db("SELECT * FROM questions ORDER BY id DESC LIMIT 150")
    questions = [dict(q) for q in questions_rows] if questions_rows else []
    
    # Fetch recently registered users
    users_rows = query_db("SELECT id, username, email, level, xp, role, created_at FROM users ORDER BY id DESC LIMIT 100")
    users = [dict(u) for u in users_rows] if users_rows else []

    # Fetch categories
    categories_rows = query_db("SELECT * FROM categories ORDER BY name ASC")
    categories = [dict(c) for c in categories_rows] if categories_rows else []

    return render_template(
        "admin.html", 
        total_users=total_users, 
        total_quizzes=total_quizzes, 
        total_questions=total_questions,
        questions=questions,
        users=users,
        categories=categories
    )

@main.route("/admin/question/add", methods=["POST"])
@admin_required
def admin_add_question():
    # Add new question
    execute_db("""
        INSERT INTO questions (question_text, option_a, option_b, option_c, option_d, correct_answer, category, stage, level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request.form.get("question_text"), request.form.get("option_a"), 
        request.form.get("option_b"), request.form.get("option_c"), 
        request.form.get("option_d"), request.form.get("correct_answer"), 
        request.form.get("category"), int(request.form.get("stage", 1)), 
        int(request.form.get("level", 1))
    ))
    flash("Question successfully added to the database!", "success")
    return redirect(url_for("main.admin_dashboard"))

@main.route("/admin/question/edit/<int:q_id>", methods=["POST"])
@admin_required
def admin_edit_question(q_id):
    # Update existing question
    execute_db("""
        UPDATE questions SET 
            question_text = ?, option_a = ?, option_b = ?, option_c = ?, 
            option_d = ?, correct_answer = ?, category = ?, stage = ?, level = ?
        WHERE id = ?
    """, (
        request.form.get("question_text"), request.form.get("option_a"), 
        request.form.get("option_b"), request.form.get("option_c"), 
        request.form.get("option_d"), request.form.get("correct_answer"), 
        request.form.get("category"), int(request.form.get("stage", 1)), 
        int(request.form.get("level", 1)), q_id
    ))
    flash(f"Question #{q_id} updated successfully!", "success")
    return redirect(url_for("main.admin_dashboard"))

@main.route("/admin/question/delete", methods=["POST"])
@admin_required
def admin_delete_question():
    # Delete question logic
    q_id = request.form.get("question_id", type=int)
    if q_id:
        execute_db("DELETE FROM questions WHERE id = ?", (q_id,))
        flash("Question deleted permanently.", "success")
    return redirect(url_for("main.admin_dashboard"))

@main.route("/admin/user/delete", methods=["POST"])
@admin_required
def admin_delete_user():
    # Admin deletion of users
    u_id = request.form.get("user_id", type=int)
    admin = get_current_user()
    
    if not u_id:
        flash("Invalid user ID.", "error")
        return redirect(url_for("main.admin_dashboard"))
        
    if u_id == admin.id:
        flash("You cannot delete your own admin account from here.", "warning")
        return redirect(url_for("main.admin_dashboard"))
        
    # Manual cascading delete for integrity
    try:
        # Delete dependencies
        execute_db("DELETE FROM party_members WHERE user_id = ?", (u_id,))
        execute_db("DELETE FROM parties WHERE host_id = ?", (u_id,))
        execute_db("DELETE FROM friends WHERE user_id = ? OR friend_id = ?", (u_id, u_id))
        execute_db("DELETE FROM user_progress WHERE user_id = ?", (u_id,))
        execute_db("DELETE FROM leaderboard WHERE user_id = ?", (u_id,))
        execute_db("DELETE FROM quiz_results WHERE user_id = ?", (u_id,))
        
        # Finally delete the user
        execute_db("DELETE FROM users WHERE id = ?", (u_id,))
        
        flash(f"User #{u_id} and all related data have been permanently deleted.", "success")
    except Exception as e:
        flash(f"Error deleting user: {str(e)}", "error")
        
    return redirect(url_for("main.admin_dashboard"))


@main.route("/admin/category/add", methods=["POST"])
@admin_required
def admin_add_category():
    # Add new category
    name = request.form.get("name", "").strip()
    if not name:
        flash("Category name cannot be empty.", "error")
    else:
        try:
            execute_db("INSERT INTO categories (name) VALUES (?)", (name,))
            flash(f"Category '{name}' added successfully!", "success")
        except Exception:
            flash(f"Category '{name}' already exists or failed to add.", "error")
    return redirect(url_for("main.admin_dashboard"))


@main.route("/admin/category/delete", methods=["POST"])
@admin_required
def admin_delete_category():
    # Delete category
    cat_id = request.form.get("category_id", type=int)
    if not cat_id:
        flash("Invalid category ID.", "error")
        return redirect(url_for("main.admin_dashboard"))

    # Fetch category name to check for questions
    category = query_db("SELECT name FROM categories WHERE id = ?", (cat_id,), one=True)
    if not category:
        flash("Category not found.", "error")
        return redirect(url_for("main.admin_dashboard"))
    
    cat_name = category["name"]
    
    # Check if any questions are using this category
    question_count = query_db("SELECT COUNT(*) as count FROM questions WHERE category = ?", (cat_name,), one=True)["count"]
    
    if question_count > 0:
        flash(f"Cannot delete category '{cat_name}' because it contains {question_count} question(s). Please reassign or delete the questions first.", "warning")
    else:
        execute_db("DELETE FROM categories WHERE id = ?", (cat_id,))
        flash(f"Category '{cat_name}' deleted successfully.", "success")
        
    return redirect(url_for("main.admin_dashboard"))


# Public Routes


@main.route("/")
def home():
    # Home landing page
    return render_template("home.html")


@main.route("/login", methods=["GET", "POST"])
def login():
    # Login page view
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        result = login_user(username, password)
        if result["success"]:
            return redirect(url_for("main.dashboard"))
        error = result["error"]

    return render_template("login.html", error=error)


@main.route("/register", methods=["GET", "POST"])
def register():
    # Registration page view
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        result = register_user(username, email, password)
        if result["success"]:
            # Auto-login after registration
            login_user(username, password)
            return redirect(url_for("main.dashboard"))
        error = result["error"]

    return render_template("register.html", error=error)


@main.route("/leaderboard")
def leaderboard():
    # Public global leaderboard
    rows = query_db("""
        SELECT u.*,
               RANK() OVER (ORDER BY u.xp DESC) AS rank
        FROM   users u
        ORDER  BY u.xp DESC
        LIMIT  20
        """)
    entries = [dict(r) for r in rows] if rows else []
    for e in entries:
        e["rank_title"] = get_rank_title(e["level"])
    return render_template("leaderboard.html", entries=entries)


# Protected Routes


@main.route("/dashboard")
@login_required
def dashboard():
    # User stats dashboard
    user = get_current_user()
    results = get_user_results(user.id, limit=10)
    streak = get_current_streak(user.id)
    
    xp_next = xp_required_for_level(user.level + 1)
    rank_title = get_rank_title(user.level)

    # Prepare data for the interactive chart (chronological order)
    chart_labels = [r.date.strftime('%b %d') for r in reversed(results)]
    chart_data = [r.percentage for r in reversed(results)]
    
    return render_template(
        "dashboard.html", user=user, results=results[:5], streak=streak,
        chart_labels=chart_labels, chart_data=chart_data,
        xp_next=xp_next, rank_title=rank_title
    )


# Quiz Routes

@main.route("/clash")
@login_required
def clash():
    # Multiplayer clash page
    user = get_current_user()
    
    # Fetch categories from DB
    cat_rows = query_db("SELECT name FROM categories ORDER BY name ASC")
    categories = [r["name"] for r in cat_rows] if cat_rows else ["General Knowledge"]

    # 1. Safely ensure database has required schema for progression
    try:
        execute_db("ALTER TABLE questions ADD COLUMN category TEXT")
        execute_db("ALTER TABLE questions ADD COLUMN stage INTEGER")
        execute_db("ALTER TABLE questions ADD COLUMN level INTEGER")
    except Exception:
        pass
    execute_db("""
        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER, category TEXT, unlocked_stage INTEGER DEFAULT 1, unlocked_level INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, category)
        )
    """)

    # 2. Fetch User Progression
    progress_rows = query_db("SELECT category, unlocked_stage, unlocked_level FROM user_progress WHERE user_id = ?", (user.id,))
    prog_map = {cat: {"stage": 1, "level": 1} for cat in categories}
    if progress_rows:
        for r in progress_rows:
            if r["category"] in prog_map:
                prog_map[r["category"]] = {"stage": r["unlocked_stage"], "level": r["unlocked_level"]}

    # 3. Friends List Implementation
    try:
        execute_db("""
            CREATE TABLE IF NOT EXISTS friends (
                user_id INTEGER,
                friend_id INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'accepted',
                PRIMARY KEY (user_id, friend_id)
            )
        """)
    except Exception:
        pass
        
    try:
        execute_db("ALTER TABLE friends ADD COLUMN status TEXT DEFAULT 'accepted'")
    except Exception:
        pass

    friends_rows = query_db("""
        SELECT u.id, u.username, u.avatar_url, u.level
        FROM friends f
        JOIN users u ON u.id = CASE WHEN f.user_id = ? THEN f.friend_id ELSE f.user_id END
        WHERE (f.user_id = ? OR f.friend_id = ?) AND f.status = 'accepted'
        ORDER BY u.username ASC
    """, (user.id, user.id, user.id))
    friends = [dict(r) for r in friends_rows] if friends_rows else []

    pending_rows = query_db("""
        SELECT f.user_id as sender_id, u.username, u.avatar_url
        FROM friends f
        JOIN users u ON f.user_id = u.id
        WHERE f.friend_id = ? AND f.status = 'pending'
    """, (user.id,))
    pending_requests = [dict(r) for r in pending_rows] if pending_rows else []

    return render_template("clash.html", user=user, categories=categories, prog_map=prog_map, friends=friends, pending_requests=pending_requests)


@main.route("/quiz/start", methods=["POST"])
@login_required
def quiz_start():
    # Start quiz session
    try:
        num = int(request.form.get("num_questions", 10))
        category = request.form.get("category", "General Knowledge")
        stage = int(request.form.get("stage", 1))
        level = int(request.form.get("level", 1))
    except ValueError:
        flash("Invalid quiz configuration.", "error")
        return redirect(url_for("main.dashboard"))
    
    session["active_category"] = category
    session["active_stage"] = stage
    session["active_level"] = level
    
    result = start_quiz(num_questions=num, category=category, stage=stage, level=level)
    if not result["success"]:
        flash(result["error"], "error")
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.quiz"))


@main.route("/quiz", methods=["GET"])
@login_required
def quiz():
    # Show current question
    question = get_current_question()
    if question is None:
        # No active quiz — redirect to dashboard
        return redirect(url_for("main.dashboard"))
    progress = get_quiz_progress()
    active_party_room = session.get("active_party_room")
    return render_template("quiz.html", question=question, progress=progress, active_party_room=active_party_room)


@main.route("/quiz/answer", methods=["POST"])
@login_required
def quiz_answer():
    # Handle answer submission
    question_id = request.form.get("question_id", type=int)
    chosen = request.form.get("answer", "")
    user = get_current_user()

    if not question_id or not chosen:
        return jsonify({"error": "Missing question_id or answer"}), 400

    result = submit_answer(question_id, chosen, user.id)

    if result["is_last"]:
        return redirect(url_for("main.quiz_finish"))

    # AJAX callers expect JSON
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(result)

    return redirect(url_for("main.quiz"))


@main.route("/quiz/finish")
@login_required
def quiz_finish():
    # Finish and score
    user = get_current_user()
    result = finish_quiz(user.id)
    if not result["success"]:
        flash(result.get("error", "Something went wrong."), "error")
        return redirect(url_for("main.dashboard"))
        
    # Progression Unlock Logic: Requires 60% accuracy to pass a level
    if result.get("percentage", 0) >= 60.0:
        cat = session.get("active_category")
        stg = session.get("active_stage")
        lvl = session.get("active_level")
        
        if cat and stg and lvl:
            curr = query_db("SELECT unlocked_stage, unlocked_level FROM user_progress WHERE user_id=? AND category=?", (user.id, cat), one=True)
            curr_stg = curr["unlocked_stage"] if curr else 1
            curr_lvl = curr["unlocked_level"] if curr else 1
            
            # If they beat their highest unlocked level
            if stg == curr_stg and lvl == curr_lvl:
                new_lvl = lvl + 1
                new_stg = stg
                if new_lvl > 3:  # Move to next stage
                    new_lvl = 1
                    new_stg = stg + 1
                
                if new_stg <= 3: # Max Stage is 3
                    if curr: execute_db("UPDATE user_progress SET unlocked_stage=?, unlocked_level=? WHERE user_id=? AND category=?", (new_stg, new_lvl, user.id, cat))
                    else: execute_db("INSERT INTO user_progress (user_id, category, unlocked_stage, unlocked_level) VALUES (?, ?, ?, ?)", (user.id, cat, new_stg, new_lvl))

    session["last_result"] = result
    
    # Redirect to appropriate result page
    if result.get("party_mode"):
        room_code = result.get("room_code")
        return redirect(url_for("main.party_results", room_code=room_code))

    return redirect(url_for("main.result"))


@main.route("/result")
@login_required
def result():
    # Quiz result view
    data = session.pop("last_result", None)
    if data is None:
        return redirect(url_for("main.dashboard"))
    return render_template("result.html", result=data)


@main.route("/profile")
@login_required
def profile():
    # User profile view
    user = get_current_user()
    results = get_user_results(user.id, limit=20)
    streak = get_current_streak(user.id)
    
    xp_next = xp_required_for_level(user.level + 1)
    rank_title = get_rank_title(user.level)
    
    badges = {
        "first_quiz": len(results) >= 1,
        "streak_5": streak >= 5,
        "perfect_score": any(r.percentage >= 100 for r in results),
        "quiz_master": user.level >= 10,
        "dedicated": len(results) >= 50
    }

    return render_template(
        "profile.html", user=user, results=results, streak=streak,
        xp_next=xp_next, rank_title=rank_title, badges=badges
    )


@main.route("/profile/update", methods=["POST"])
@login_required
def profile_update():
    # Update profile settings
    user = get_current_user()
    action = request.form.get("action")

    # 1. Safely ensure the database has the avatar_url column
    try:
        execute_db("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    except Exception:
        pass  # Column already exists

    if action == "photo":
        file = request.files.get("avatar_file")
        if file and file.filename != '':
            file.seek(0, os.SEEK_END)
            if file.tell() > 2 * 1024 * 1024:
                flash("Image file size exceeds the 2MB limit.", "error")
                return redirect(url_for("main.profile"))
            file.seek(0, os.SEEK_SET)

            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1].lower()
            allowed_exts = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}
            
            if ext not in allowed_exts:
                flash("Unsupported file type. Please upload an image.", "error")
                return redirect(url_for("main.profile"))

            upload_folder = os.path.join(current_app.static_folder, 'images', 'avatars')
            os.makedirs(upload_folder, exist_ok=True)
            
            new_filename = f"user_{user.id}_{uuid.uuid4().hex[:8]}{ext}"
            file_path = os.path.join(upload_folder, new_filename)
            file.save(file_path)
            
            avatar_url = url_for('static', filename=f"images/avatars/{new_filename}")
            execute_db("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user.id))
            flash("Profile photo updated successfully!", "success")
        else:
            flash("Please select an image file to upload.", "error")

    elif action == "remove_photo":
        execute_db("UPDATE users SET avatar_url = NULL WHERE id = ?", (user.id,))
        flash("Profile photo removed successfully.", "success")

    elif action == "username":
        new_base = request.form.get("username", "").strip().replace('#', '')
        new_disc = request.form.get("discriminator", "").strip().replace('#', '')
        
        if not new_base or len(new_base) < 3:
            flash("Username must be at least 3 characters.", "error")
        elif not new_disc or len(new_disc) > 6 or not new_disc.isalnum():
            flash("Discriminator tag must be up to 6 letters or numbers.", "error")
        else:
            full_username = f"{new_base}#{new_disc}"
            if full_username == user.username:
                flash("Username is the same. No changes made.", "warning")
            else:
                existing = query_db("SELECT id FROM users WHERE username = ?", (full_username,), one=True)
                if existing:
                    flash(f"The tag #{new_disc} is already taken for the name {new_base}.", "error")
                else:
                    execute_db("UPDATE users SET username = ? WHERE id = ?", (full_username, user.id))
                    session["username"] = full_username
                    flash(f"Username updated successfully to {full_username}!", "success")

    elif action == "password":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        if not new_password or not confirm_password:
            flash("Please fill out both password fields.", "error")
        elif new_password != confirm_password:
            flash("Passwords do not match.", "error")
        elif len(new_password) < 6:
            flash("Password must be at least 6 characters.", "error")
        else:
            hashed = generate_password_hash(new_password)
            execute_db("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, user.id))
            flash("Password updated successfully!", "success")
            
    return redirect(url_for("main.profile"))


@main.route("/api/search_users")
@login_required
def search_users():
    # Live user search
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])
        
    user = get_current_user()
    rows = query_db("""
        SELECT id, username, avatar_url, level
        FROM users
        WHERE username LIKE ? AND id != ?
        LIMIT 5
    """, (f"%{q}%", user.id))
    
    return jsonify([dict(r) for r in rows] if rows else [])

@main.route("/friend/add", methods=["POST"])
@login_required
def add_friend():
    # Add user friend
    friend_username = request.form.get("friend_username", "").strip()
    user = get_current_user()
    
    if not friend_username:
        flash("Please enter a username.", "error")
        return redirect(url_for("main.clash"))
        
    if friend_username.lower() == user.username.lower():
        flash("You can't add yourself as a friend!", "error")
        return redirect(url_for("main.clash"))
        
    friend = query_db("SELECT id, username FROM users WHERE LOWER(username) = ?", (friend_username.lower(),), one=True)
    if not friend:
        flash(f"Player '{friend_username}' not found.", "error")
        return redirect(url_for("main.clash"))
        
    # Check if a relationship already exists in either direction
    existing = query_db("SELECT status FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)", (user.id, friend["id"], friend["id"], user.id), one=True)
    if existing:
        if existing["status"] == "accepted":
            flash(f"You are already friends with {friend['username']}.", "error")
        else:
            flash(f"A friend request is already pending with {friend['username']}.", "warning")
        return redirect(url_for("main.clash"))
        
    execute_db("INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, 'pending')", (user.id, friend["id"]))
    flash(f"Friend request sent to {friend['username']}!", "success")
    return redirect(url_for("main.clash"))


@main.route("/friend/accept", methods=["POST"])
@login_required
def accept_friend():
    sender_id = request.form.get("sender_id", type=int)
    user = get_current_user()
    if sender_id:
        execute_db("UPDATE friends SET status = 'accepted' WHERE user_id = ? AND friend_id = ?", (sender_id, user.id))
        flash("Friend request accepted!", "success")
    return redirect(url_for("main.clash"))

@main.route("/friend/reject", methods=["POST"])
@login_required
def reject_friend():
    sender_id = request.form.get("sender_id", type=int)
    user = get_current_user()
    if sender_id:
        execute_db("DELETE FROM friends WHERE user_id = ? AND friend_id = ?", (sender_id, user.id))
        flash("Friend request rejected.", "success")
    return redirect(url_for("main.clash"))

@main.route("/friend/remove", methods=["POST"])
@login_required
def remove_friend():
    friend_id = request.form.get("friend_id", type=int)
    user = get_current_user()
    if friend_id:
        execute_db("DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)", (user.id, friend_id, friend_id, user.id))
        flash("Friend removed.", "success")
    return redirect(url_for("main.clash"))

def generate_room_code(length=6):
    # Generate room code
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@main.route("/party/create", methods=["POST"])
@login_required
def create_party():
    # Create party room
    user = get_current_user()
    try:
        party_size = int(request.form.get("party_size", 2))
        num_questions = int(request.form.get("num_questions", 10))
        category = request.form.get("category", "General Knowledge")
    except ValueError:
        flash("Invalid party configuration.", "error")
        return redirect(url_for("main.clash"))

    # Fetch questions for the party quiz
    q_rows = query_db(
        "SELECT id FROM questions WHERE category = ?",
        (category,)
    )
    if not q_rows or len(q_rows) < num_questions:
        flash(f"Not enough questions in the '{category}' category to start a match. Please pick another.", "error")
        return redirect(url_for('main.clash'))

    q_ids = [r["id"] for r in q_rows]
    selected_ids = random.sample(q_ids, num_questions)
    question_ids_json = json.dumps(selected_ids)
    
    try:
        execute_db("""
            CREATE TABLE IF NOT EXISTS parties (
                room_code TEXT PRIMARY KEY,
                host_id INTEGER,
                max_size INTEGER,
                status TEXT DEFAULT 'waiting',
                question_ids_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        execute_db("""
            CREATE TABLE IF NOT EXISTS party_members (
                room_code TEXT,
                user_id INTEGER,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_index INTEGER DEFAULT 0,
                score INTEGER DEFAULT 0,
                PRIMARY KEY (room_code, user_id)
            )
        """)
    except Exception:
        pass
        
    # Patch existing databases that were created before the multiplayer update
    try:
        execute_db("ALTER TABLE parties ADD COLUMN question_ids_json TEXT")
    except Exception:
        pass
    try:
        execute_db("ALTER TABLE party_members ADD COLUMN current_index INTEGER DEFAULT 0")
        execute_db("ALTER TABLE party_members ADD COLUMN score INTEGER DEFAULT 0")
    except Exception:
        pass

    room_code = generate_room_code()
    # Ensure code is unique
    while query_db("SELECT room_code FROM parties WHERE room_code = ?", (room_code,), one=True):
        room_code = generate_room_code()
        
    execute_db("INSERT INTO parties (room_code, host_id, max_size, question_ids_json) VALUES (?, ?, ?, ?)", (room_code, user.id, party_size, question_ids_json))
    execute_db("INSERT INTO party_members (room_code, user_id) VALUES (?, ?)", (room_code, user.id))
    
    return redirect(url_for("main.party_lobby", room_code=room_code))


@main.route("/party/join", methods=["POST"])
@login_required
def join_party():
    # Join party room
    room_code = request.form.get("room_code", "").strip().upper()
    user = get_current_user()
    
    party = query_db("SELECT * FROM parties WHERE room_code = ?", (room_code,), one=True)
    if not party:
        flash("Invalid Room Code. Please try again.", "error")
        return redirect(url_for("main.clash"))
        
    if party["status"] != "waiting":
        flash("This match has already started or ended.", "error")
        return redirect(url_for("main.clash"))
        
    members = query_db("SELECT COUNT(*) as count FROM party_members WHERE room_code = ?", (room_code,), one=True)
    existing = query_db("SELECT * FROM party_members WHERE room_code = ? AND user_id = ?", (room_code, user.id), one=True)
    
    if members["count"] >= party["max_size"] and not existing:
        flash("This party is currently full.", "error")
        return redirect(url_for("main.clash"))
    
    execute_db("INSERT OR IGNORE INTO party_members (room_code, user_id) VALUES (?, ?)", (room_code, user.id))
    return redirect(url_for("main.party_lobby", room_code=room_code))


@main.route("/party/<room_code>")
@login_required
def party_lobby(room_code):
    # Party lobby view
    user = get_current_user()
    party = query_db("SELECT * FROM parties WHERE room_code = ?", (room_code,), one=True)
    
    if not party:
        flash("Room not found.", "error")
        return redirect(url_for("main.clash"))
        
    if party["status"] == "in_progress":
        # Match has started, redirect to the quiz setup route
        return redirect(url_for("main.party_quiz_setup", room_code=room_code))
        
    members = query_db("""
        SELECT u.id, u.username, u.avatar_url, u.level 
        FROM party_members pm 
        JOIN users u ON pm.user_id = u.id 
        WHERE pm.room_code = ?
        ORDER BY pm.joined_at ASC
    """, (room_code,))
    
    is_host = (party["host_id"] == user.id)
    return render_template("party_lobby.html", party=party, members=members, is_host=is_host)


@main.route("/party/<room_code>/setup")
@login_required
def party_quiz_setup(room_code):
    # Setup party quiz
    user = get_current_user()
    party = query_db("SELECT * FROM parties WHERE room_code = ?", (room_code,), one=True)
    
    # Basic validation
    if not party:
        flash("Party not found.", "error")
        return redirect(url_for('main.clash'))
    
    members = query_db("SELECT user_id FROM party_members WHERE room_code = ?", (room_code,))
    member_ids = [m['user_id'] for m in members]
    if user.id not in member_ids:
        flash("You are not a member of this party.", "error")
        return redirect(url_for('main.clash'))

    # If user is already in this quiz, don't reset their session
    if session.get("active_party_room") == room_code:
        return redirect(url_for("main.quiz"))

    # Setup session for the quiz
    question_ids = json.loads(party['question_ids_json'])
    
    session["quiz_question_ids"] = question_ids
    session["quiz_current_index"] = 0
    session["quiz_answers"] = {}
    session["quiz_num_questions"] = len(question_ids)
    session["active_party_room"] = room_code # Mark this as a party quiz

    try:
        execute_db("UPDATE party_members SET current_index = 0, score = 0 WHERE room_code = ? AND user_id = ?", (room_code, user.id))
    except Exception:
        pass

    now = int(time.time())
    session["quiz_deadline"] = now + (len(question_ids) * 10) # 10 seconds per question

    return redirect(url_for("main.quiz"))

@main.route("/party/<room_code>/start", methods=["POST"])
@login_required
def start_party_match(room_code):
    # Start party match
    user = get_current_user()
    party = query_db("SELECT * FROM parties WHERE room_code = ?", (room_code,), one=True)
    
    if not party or party["host_id"] != user.id:
        flash("Only the host can start the match.", "error")
        return redirect(url_for("main.party_lobby", room_code=room_code))
        
    execute_db("UPDATE parties SET status = 'in_progress' WHERE room_code = ?", (room_code,))
    return redirect(url_for("main.party_lobby", room_code=room_code))


@main.route("/party/<room_code>/results")
@login_required
def party_results(room_code):
    # Party result view
    party = query_db("SELECT * FROM parties WHERE room_code = ?", (room_code,), one=True)
    if not party:
        flash("Party not found.", "error")
        return redirect(url_for('main.clash'))
        
    results_rows = query_db("""
        SELECT pr.score, pr.total_questions, pr.finished_at, u.username, u.avatar_url, u.level
        FROM party_results pr
        JOIN users u ON pr.user_id = u.id
        WHERE pr.room_code = ?
        ORDER BY pr.score DESC, pr.finished_at ASC
    """, (room_code,))
    
    results = [dict(r) for r in results_rows] if results_rows else []
    
    return render_template("party_results.html", room_code=room_code, results=results, party=party)


@main.route("/party/<room_code>/progress")
@login_required
def party_progress(room_code):
    # Real-time party progress
    rows = query_db("""
        SELECT u.username, u.avatar_url, pm.current_index, pm.score
        FROM party_members pm
        JOIN users u ON pm.user_id = u.id
        WHERE pm.room_code = ?
    """, (room_code,))
    
    progress_data = [dict(r) for r in rows] if rows else []
    return jsonify({"members": progress_data})


@main.route("/profile/delete", methods=["POST"])
@login_required
def delete_account():
    # Delete user account
    user = get_current_user()
    # Clean up all records referencing the user
    execute_db("DELETE FROM quiz_results WHERE user_id = ?", (user.id,))
    execute_db("DELETE FROM leaderboard WHERE user_id = ?", (user.id,))
    execute_db("DELETE FROM user_progress WHERE user_id = ?", (user.id,))
    execute_db("DELETE FROM friends WHERE user_id = ? OR friend_id = ?", (user.id, user.id))
    execute_db("DELETE FROM party_members WHERE user_id = ?", (user.id,))
    execute_db("DELETE FROM parties WHERE host_id = ?", (user.id,))
    execute_db("DELETE FROM users WHERE id = ?", (user.id,))
    
    logout_user()
    flash("Your account has been successfully and permanently deleted.", "success")
    return redirect(url_for("main.home"))

@main.route("/logout")
def logout():
    # Logout user logic
    logout_user()
    return redirect(url_for("main.home"))
