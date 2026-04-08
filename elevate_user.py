import sqlite3
import os

db_path = os.path.join("database", "quiz_app.db")
conn = sqlite3.connect(db_path)
print(f"Connected to {db_path}")

# Elevate user ID 9
conn.execute("UPDATE users SET role='admin' WHERE id=9")
conn.commit()
print("User ID 9 elevated to admin.")

# Check the change
user = conn.execute("SELECT id, username, role FROM users WHERE id=9").fetchone()
print(f"Current role for {user[1]}: {user[2]}")

conn.close()
