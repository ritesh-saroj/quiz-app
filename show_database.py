import sqlite3
import os

def show_database():
    # Make path relative to the script file for robustness
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'database', 'quiz_app.db')

    if not os.path.exists(db_path):
        print(f"Database file not found at: {db_path}")
        return

    try:
        # Use 'with' statement for automatic connection management
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            if not tables:
                print("The database does not contain any tables.")
                return

            print(f"--- Database Contents from '{db_path}' ---")
            print()

            for table_tuple in tables:
                table_name = table_tuple[0]
                if table_name == 'sqlite_sequence':
                    continue

                print(f"--- Table: {table_name} ---")

                try:
                    cursor.execute(f'PRAGMA table_info({table_name})')
                    columns_info = cursor.fetchall()
                    column_names = [info[1] for info in columns_info]
                    print(f"Columns: {', '.join(column_names)}")

                    cursor.execute(f"SELECT * FROM {table_name}")
                    rows = cursor.fetchall()

                    if not rows:
                        print("(This table is empty)")
                    else:
                        for row in rows:
                            print(row)
                    print("-" * (len(table_name) + 12))
                    print()

                except sqlite3.OperationalError as e:
                    print(f"Error reading from table {table_name}: {e}")
                    print()

    except sqlite3.Error as e:
        print(f"An error occurred while accessing the database: {e}")

if __name__ == "__main__":
    show_database()
