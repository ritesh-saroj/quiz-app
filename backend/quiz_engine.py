# Quiz lifecycle management

import random
import time
from flask import session

from database import query_db, execute_db
from models import Question, QuizResult
from gamification import calculate_xp, award_xp
from leaderboard import update_leaderboard

# Session keys config
SESSION_QUESTION_IDS = "quiz_question_ids"  # list of question IDs in play
# which question we're on (0-based)
SESSION_CURRENT_INDEX = "quiz_current_index"
SESSION_ANSWERS = "quiz_answers"  # {question_id: chosen_option}
SESSION_NUM_QUESTIONS = "quiz_num_questions"


# Start new quiz logic


def start_quiz(num_questions: int = 10, category: str = "General Knowledge", stage: int = 1, level: int = 1) -> dict:
    # Pick random questions
    rows = query_db(
        "SELECT id FROM questions WHERE category = ? AND stage = ? AND level = ?",
        (category, stage, level)
    )
        
    if not rows:
        return {
            "success": False,
            "error": f"No questions found for {category} (Stage {stage}, Level {level}).",
        }

    ids = [r["id"] for r in rows]
    selected = random.sample(ids, min(num_questions, len(ids)))
    random.shuffle(selected)

    session[SESSION_QUESTION_IDS] = selected
    session[SESSION_CURRENT_INDEX] = 0
    session[SESSION_ANSWERS] = {}
    session[SESSION_NUM_QUESTIONS] = len(selected)

    now = int(time.time())
    if num_questions == 5:
        session["quiz_deadline"] = now + 30
    elif num_questions == 10:
        session["quiz_deadline"] = now + 60
    elif num_questions == 20:
        session["quiz_deadline"] = now + 90
    else:
        session["quiz_deadline"] = now + 60

    return {"success": True, "total": len(selected)}


# Get quiz question


def get_current_question() -> Question | None:
    # Current question object
    ids = session.get(SESSION_QUESTION_IDS)
    index = session.get(SESSION_CURRENT_INDEX, 0)

    if not ids or index >= len(ids):
        return None

    question_id = ids[index]
    row = query_db(
        "SELECT * FROM questions WHERE id = ?", (question_id,), one=True
    )
    return Question(row) if row else None


def get_quiz_progress() -> dict:
    # Quiz progress info
    ids = session.get(SESSION_QUESTION_IDS, [])
    index = session.get(SESSION_CURRENT_INDEX, 0)
    deadline = session.get("quiz_deadline", int(time.time()) + 30)
    return {
        "current": index + 1,
        "total": len(ids),
        "percent": int((index / len(ids)) * 100) if ids else 0,
        "time_left": max(0, deadline - int(time.time())),
    }


# Submit answer logic


def submit_answer(question_id: int, chosen_option: str, user_id: int = None) -> dict:
    # Record player answer
    row = query_db(
        "SELECT correct_answer FROM questions WHERE id = ?",
        (question_id,),
        one=True,
    )
    if row is None:
        return {"correct": False, "correct_answer": "", "is_last": False}

    correct_answer = row["correct_answer"].upper()
    chosen_option = chosen_option.upper()
    is_correct = chosen_option == correct_answer

    # Persist answer in session
    answers = session.get(SESSION_ANSWERS, {})
    answers[str(question_id)] = chosen_option
    session[SESSION_ANSWERS] = answers

    # Advance index
    index = session.get(SESSION_CURRENT_INDEX, 0)
    session[SESSION_CURRENT_INDEX] = index + 1

    ids = session.get(SESSION_QUESTION_IDS, [])
    is_last = (index + 1) >= len(ids)

    active_party_room = session.get("active_party_room")
    if active_party_room and user_id:
        try:
            row = query_db("SELECT score FROM party_members WHERE room_code = ? AND user_id = ?", (active_party_room, user_id), one=True)
            if row:
                new_score = row["score"] + (1 if is_correct else 0)
                new_index = index + 1
                execute_db("UPDATE party_members SET current_index = ?, score = ? WHERE room_code = ? AND user_id = ?", (new_index, new_score, active_party_room, user_id))
        except Exception:
            pass

    return {
        "correct": is_correct,
        "correct_answer": correct_answer,
        "is_last": is_last,
    }


# Finish quiz logic


def finish_quiz(user_id: int) -> dict:
    # Score and award XP
    ids = session.get(SESSION_QUESTION_IDS, [])
    answers = session.get(SESSION_ANSWERS, {})
    active_party_room = session.get("active_party_room")

    if not ids:
        return {"success": False, "error": "No active quiz found."}

    # --- Score calculation ---
    score = 0
    breakdown = []  # [{question, chosen, correct, is_correct}, …]

    rows = query_db(
        f"SELECT * FROM questions WHERE id IN ({','.join('?' * len(ids))})",
        tuple(ids),
    )
    # Re-order rows to match session order
    row_map = {r["id"]: r for r in rows}

    for qid in ids:
        row = row_map.get(qid)
        if not row:
            continue
        q = Question(row)
        chosen = answers.get(str(qid), "").upper()
        correct = q.correct_answer.upper()
        is_correct = chosen == correct
        if is_correct:
            score += 1
        breakdown.append(
            {
                "question": q.question_text,
                "options": q.options,
                "chosen": chosen,
                "correct": correct,
                "is_correct": is_correct,
            }
        )

    total = len(ids)
    
    def _clear_quiz_session():
        for key in (
            SESSION_QUESTION_IDS,
            SESSION_CURRENT_INDEX,
            SESSION_ANSWERS,
            SESSION_NUM_QUESTIONS,
            "quiz_deadline",
            "active_party_room"
        ):
            session.pop(key, None)

    # --- Handle Party Match Finish ---
    if active_party_room:
        try:
            execute_db("""
                CREATE TABLE IF NOT EXISTS party_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_code TEXT,
                    user_id INTEGER,
                    score INTEGER,
                    total_questions INTEGER,
                    finished_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        except Exception:
            pass
        
        execute_db(
            "INSERT INTO party_results (room_code, user_id, score, total_questions) VALUES (?, ?, ?, ?)",
            (active_party_room, user_id, score, total)
        )
        
        _clear_quiz_session()
        return {
            "success": True,
            "party_mode": True,
            "room_code": active_party_room,
            "score": score,
            "total": total
        }

    # --- Persist result ---
    result_id = execute_db(
        "INSERT INTO quiz_results (user_id, score, total_questions) VALUES (?, ?, ?)",
        (user_id, score, total),
    )

    # --- Award XP ---
    xp_info = calculate_xp(score, total)
    level_info = award_xp(user_id, xp_info["total_xp"])

    # --- Update leaderboard ---
    update_leaderboard(user_id, score)

    _clear_quiz_session()
    return {
        "success": True,
        "result_id": result_id,
        "score": score,
        "total": total,
        "percentage": xp_info["percentage"],
        "xp_earned": xp_info["total_xp"],
        "base_xp": xp_info["base_xp"],
        "bonus_xp": xp_info["bonus_xp"],
        "leveled_up": level_info.get("leveled_up", False),
        "new_level": level_info.get("new_level"),
        "new_xp": level_info.get("new_xp"),
        "breakdown": breakdown,
    }


# Fetch user results


def get_user_results(user_id: int, limit: int = 10) -> list[QuizResult]:
    # Get recent results
    rows = query_db(
        """
        SELECT * FROM quiz_results
        WHERE  user_id = ?
        ORDER  BY date DESC
        LIMIT  ?
        """,
        (user_id, limit),
    )
    return [QuizResult(r) for r in rows]


def get_result_by_id(result_id: int) -> QuizResult | None:
    # Get result by ID
    row = query_db(
        "SELECT * FROM quiz_results WHERE id = ?", (result_id,), one=True
    )
    return QuizResult(row) if row else None
