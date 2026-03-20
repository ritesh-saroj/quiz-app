import sqlite3
import os

def setup_real_questions():
    # Connect to your existing database
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'quiz_app.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 0. Ensure columns exist to prevent crashes
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN category TEXT")
        cursor.execute("ALTER TABLE questions ADD COLUMN stage INTEGER")
        cursor.execute("ALTER TABLE questions ADD COLUMN level INTEGER")
    except sqlite3.OperationalError:
        pass  # Columns already exist

    # 1. WIPE OUT ALL FAKE QUESTIONS
    cursor.execute("DELETE FROM questions")
    
    # 2. ADD REAL GENERAL KNOWLEDGE QUESTIONS (Stage 1: Levels 1, 2, and 3)
    # Format: (Question, Opt A, Opt B, Opt C, Opt D, Correct Answer, Category, Stage, Level)
    gk_questions = [
        # --- STAGE 1, LEVEL 1 (Easy - 15 Questions) ---
        ("What is the capital of France?", "London", "Berlin", "Paris", "Madrid", "C", "General Knowledge", 1, 1),
        ("Which planet is known as the Red Planet?", "Earth", "Mars", "Jupiter", "Venus", "B", "General Knowledge", 1, 1),
        ("What is the largest ocean on Earth?", "Atlantic Ocean", "Indian Ocean", "Arctic Ocean", "Pacific Ocean", "D", "General Knowledge", 1, 1),
        ("How many continents are there on Earth?", "5", "6", "7", "8", "C", "General Knowledge", 1, 1),
        ("What is the boiling point of water at sea level?", "50°C", "100°C", "150°C", "200°C", "B", "General Knowledge", 1, 1),
        ("Which is the fastest land animal?", "Cheetah", "Lion", "Horse", "Leopard", "A", "General Knowledge", 1, 1),
        ("What is the chemical formula for water?", "CO2", "O2", "H2O", "H2O2", "C", "General Knowledge", 1, 1),
        ("Who wrote Romeo and Juliet?", "Charles Dickens", "William Shakespeare", "Mark Twain", "Jane Austen", "B", "General Knowledge", 1, 1),
        ("What is the first element on the periodic table?", "Helium", "Oxygen", "Carbon", "Hydrogen", "D", "General Knowledge", 1, 1),
        ("What is the tallest mountain in the world?", "K2", "Mount Everest", "Mount Kilimanjaro", "Mount Fuji", "B", "General Knowledge", 1, 1),
        ("What is the currency of Japan?", "Yuan", "Dollar", "Yen", "Won", "C", "General Knowledge", 1, 1),
        ("How many colors are in a rainbow?", "5", "6", "7", "8", "C", "General Knowledge", 1, 1),
        ("Which animal is known as the 'Ship of the Desert'?", "Horse", "Elephant", "Camel", "Donkey", "C", "General Knowledge", 1, 1),
        ("What is the largest planet in our solar system?", "Saturn", "Jupiter", "Neptune", "Uranus", "B", "General Knowledge", 1, 1),
        ("What is the hardest natural substance on Earth?", "Gold", "Iron", "Diamond", "Platinum", "C", "General Knowledge", 1, 1),

        # --- STAGE 1, LEVEL 2 (Medium - 15 Questions) ---
        ("What is the capital of Australia?", "Sydney", "Melbourne", "Canberra", "Perth", "C", "General Knowledge", 1, 2),
        ("Which is the smallest country in the world?", "Monaco", "Vatican City", "San Marino", "Liechtenstein", "B", "General Knowledge", 1, 2),
        ("Who invented the telephone?", "Thomas Edison", "Nikola Tesla", "Alexander Graham Bell", "Albert Einstein", "C", "General Knowledge", 1, 2),
        ("Which is the longest river in the world?", "Amazon River", "Nile River", "Yangtze River", "Mississippi River", "B", "General Knowledge", 1, 2),
        ("Who is the author of the Harry Potter series?", "J.R.R. Tolkien", "George R.R. Martin", "J.K. Rowling", "C.S. Lewis", "C", "General Knowledge", 1, 2),
        ("What is the nearest star to Earth?", "Proxima Centauri", "Sirius", "The Sun", "Alpha Centauri", "C", "General Knowledge", 1, 2),
        ("What is the longest bone in the human body?", "Femur", "Tibia", "Fibula", "Humerus", "A", "General Knowledge", 1, 2),
        ("Who painted the Mona Lisa?", "Vincent van Gogh", "Pablo Picasso", "Leonardo da Vinci", "Claude Monet", "C", "General Knowledge", 1, 2),
        ("What is the capital of Canada?", "Toronto", "Vancouver", "Ottawa", "Montreal", "C", "General Knowledge", 1, 2),
        ("What is the chemical symbol for Gold?", "Ag", "Au", "Pb", "Fe", "B", "General Knowledge", 1, 2),
        ("What instrument is used to measure earthquakes?", "Barometer", "Thermometer", "Seismograph", "Hygrometer", "C", "General Knowledge", 1, 2),
        ("In what year did the Titanic sink?", "1905", "1912", "1918", "1923", "B", "General Knowledge", 1, 2),
        ("What is the study of weather called?", "Geology", "Ecology", "Meteorology", "Astronomy", "C", "General Knowledge", 1, 2),
        ("Which is the largest hot desert in the world?", "Gobi", "Sahara", "Kalahari", "Atacama", "B", "General Knowledge", 1, 2),
        ("How many bones are there in the adult human body?", "206", "208", "210", "212", "A", "General Knowledge", 1, 2),

        # --- STAGE 1, LEVEL 3 (Hard - 15 Questions) ---
        ("Who was the first woman to win a Nobel Prize?", "Mother Teresa", "Rosa Parks", "Marie Curie", "Ada Lovelace", "C", "General Knowledge", 1, 3),
        ("What is the largest moon of Saturn?", "Europa", "Ganymede", "Callisto", "Titan", "D", "General Knowledge", 1, 3),
        ("Who is known as the father of modern physics?", "Isaac Newton", "Albert Einstein", "Galileo Galilei", "Niels Bohr", "B", "General Knowledge", 1, 3),
        ("What is the highest waterfall in the world?", "Niagara Falls", "Victoria Falls", "Angel Falls", "Iguazu Falls", "C", "General Knowledge", 1, 3),
        ("What is the largest internal organ in the human body?", "Heart", "Lungs", "Liver", "Kidneys", "C", "General Knowledge", 1, 3),
        ("Which country is known as the Land of the White Elephant?", "India", "Thailand", "Sri Lanka", "Myanmar", "B", "General Knowledge", 1, 3),
        ("What is the chemical symbol for Silver?", "Si", "Ag", "Au", "Sv", "B", "General Knowledge", 1, 3),
        ("Who was the first man in space?", "Neil Armstrong", "Buzz Aldrin", "Yuri Gagarin", "John Glenn", "C", "General Knowledge", 1, 3),
        ("What is the deepest oceanic trench on Earth?", "Tonga Trench", "Kermadec Trench", "Mariana Trench", "Peru-Chile Trench", "C", "General Knowledge", 1, 3),
        ("Which metal is liquid at room temperature?", "Iron", "Mercury", "Copper", "Zinc", "B", "General Knowledge", 1, 3),
        ("Who discovered penicillin?", "Louis Pasteur", "Alexander Fleming", "Robert Koch", "Edward Jenner", "B", "General Knowledge", 1, 3),
        ("What is the smallest bone in the human body?", "Stapes", "Incus", "Malleus", "Phalanx", "A", "General Knowledge", 1, 3),
        ("In which year did the Apollo 11 moon landing take place?", "1965", "1969", "1971", "1973", "B", "General Knowledge", 1, 3),
        ("Who wrote 'The Odyssey'?", "Virgil", "Socrates", "Plato", "Homer", "D", "General Knowledge", 1, 3),
        ("What is the currency of Switzerland?", "Euro", "Swiss Franc", "Krona", "Peso", "B", "General Knowledge", 1, 3),
    ]

    for q in gk_questions:
        cursor.execute("""
            INSERT INTO questions (question_text, option_a, option_b, option_c, option_d, correct_answer, category, stage, level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, q)

    conn.commit()
    conn.close()
    print("✅ General Knowledge questions for Stage 1 (Levels 1, 2, and 3) have been added!")

if __name__ == "__main__":
    setup_real_questions()