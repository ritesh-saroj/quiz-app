import sqlite3
import os

def clear_questions():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'quiz_app.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Clear existing questions
    cursor.execute("DELETE FROM questions")
    
    conn.commit()
    conn.close()
    print("All questions have been removed from the database.")

if __name__ == "__main__":
    clear_questions()