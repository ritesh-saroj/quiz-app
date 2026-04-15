# SQLite database helpers

from flask import g, current_app
import sqlite3
import os
import sys

# Ensure project root is on the path so config is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# DB Connection helpers


def get_db():
    # Get DB connection
    if "db" not in g:
        db_path = current_app.config["DATABASE_PATH"]
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row  # rows behave like dicts
    return g.db


def close_db(e=None):
    # Close DB connection
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    # Initialize database tables
    schema_path = app.config["SCHEMA_PATH"]
    db_path = app.config["DATABASE_PATH"]

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                conn.executescript(f.read())
        else:
            # Fallback: create a minimal users table so auth works
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT    NOT NULL UNIQUE,
                    email         TEXT    NOT NULL UNIQUE,
                    password_hash TEXT    NOT NULL,
                    xp            INTEGER NOT NULL DEFAULT 0,
                    level         INTEGER NOT NULL DEFAULT 1,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_text  TEXT NOT NULL,
                    option_a       TEXT NOT NULL,
                    option_b       TEXT NOT NULL,
                    option_c       TEXT NOT NULL,
                    option_d       TEXT NOT NULL,
                    correct_answer TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS quiz_results (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER NOT NULL,
                    score           INTEGER NOT NULL,
                    total_questions INTEGER NOT NULL,
                    date            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS leaderboard (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    score   INTEGER NOT NULL DEFAULT 0,
                    rank    INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );
            """)

    # Register teardown so connections are closed after each request
    app.teardown_appcontext(close_db)


# SQL Query helpers


def query_db(sql, args=(), one=False):
    # Execute SELECT query
    cur = get_db().execute(sql, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(sql, args=()):
    # Execute DML query
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id
