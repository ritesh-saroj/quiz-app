# Database model wrappers


class User:
    # User model

    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.email = row["email"]
        self.password_hash = row["password_hash"]
        self.xp = row["xp"]
        self.level = row["level"]
        self.created_at = row["created_at"]

    def __repr__(self):
        return f"<User id={self.id} username={self.username!r}>"


class Question:
    # Question model

    def __init__(self, row):
        self.id = row["id"]
        self.question_text = row["question_text"]
        self.option_a = row["option_a"]
        self.option_b = row["option_b"]
        self.option_c = row["option_c"]
        self.option_d = row["option_d"]
        self.correct_answer = row["correct_answer"]

    @property
    def options(self):
        # Options as dict
        return {
            "A": self.option_a,
            "B": self.option_b,
            "C": self.option_c,
            "D": self.option_d,
        }

    def __repr__(self):
        return f"<Question id={self.id}>"


class QuizResult:
    # QuizResult model

    def __init__(self, row):
        self.id = row["id"]
        self.user_id = row["user_id"]
        self.score = row["score"]
        self.total_questions = row["total_questions"]
        self.date = row["date"]

    @property
    def percentage(self):
        if self.total_questions == 0:
            return 0
        return round((self.score / self.total_questions) * 100, 1)

    def __repr__(self):
        return f"<QuizResult user={self.user_id} score={self.score}/{self.total_questions}>"


class LeaderboardEntry:
    # LeaderboardEntry model

    def __init__(self, row):
        self.user_id = row["user_id"]
        self.score = row["score"]
        self.rank = row["rank"]
        # These come from a JOIN with users
        self.username = row["username"] if "username" in row.keys() else None

    def __repr__(self):
        return f"<LeaderboardEntry rank={self.rank} user={self.username}>"
