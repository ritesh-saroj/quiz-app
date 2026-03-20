import sqlite3
import os

def make_admin():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'quiz_app.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    username = input("Enter your exact Username (e.g. Player#1234): ").strip()
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = 'admin' WHERE username = ?", (username,))
        if cursor.rowcount > 0:
            print(f"✅ Success! '{username}' has been granted Admin privileges.")
        else:
            print(f"❌ User '{username}' not found. Please check the spelling/tag and try again.")
        conn.commit()

if __name__ == "__main__":
    make_admin()