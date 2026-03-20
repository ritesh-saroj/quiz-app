"""
gamification.py — XP calculation, level system, and streak logic.

Called by quiz_engine.py after a quiz is submitted to reward the player.
"""

from database import query_db, execute_db

# ---------------------------------------------------------------------------
# XP & Level configuration
# ---------------------------------------------------------------------------

# XP awarded per correct answer
XP_PER_CORRECT = 10

# Bonus XP tiers based on score percentage
BONUS_TIERS = [
    (100, 50),  # perfect score → +50 bonus XP
    (80, 30),  # ≥ 80 %        → +30 bonus XP
    (60, 15),  # ≥ 60 %        → +15 bonus XP
    (40, 5),  # ≥ 40 %        → + 5 bonus XP
]


# XP required to reach each level: level N needs XP_FOR_LEVEL[N-1]
# Level 1 = 0 XP, level 2 = 100 XP, …  Formula: 100 * (level - 1)^1.5


def xp_required_for_level(level: int) -> int:
    """Return cumulative XP needed to *reach* `level`."""
    if level <= 1:
        return 0
    return int(100 * (level - 1) ** 1.5)


def level_for_xp(total_xp: int) -> int:
    """Determine current level from total XP."""
    level = 1
    while xp_required_for_level(level + 1) <= total_xp:
        level += 1
    return level


def get_rank_title(level: int) -> str:
    """Determine user rank based on their level."""
    if level < 3: return "Beginner"
    elif level < 6: return "Learner"
    elif level < 10: return "Challenger"
    elif level < 20: return "Expert"
    elif level < 50: return "Quiz Master"
    else: return "Legend"


# ---------------------------------------------------------------------------
# XP calculation
# ---------------------------------------------------------------------------


def calculate_xp(score: int, total_questions: int, has_boost: bool = False) -> dict:
    """
    Calculate XP earned for a quiz result.

    Returns:
        {
            "base_xp":  <int>,    # XP from correct answers
            "bonus_xp": <int>,    # bonus for high score percentage
            "total_xp": <int>,    # base + bonus
            "percentage": <float>
        }
    """
    if total_questions == 0:
        return {"base_xp": 0, "bonus_xp": 0, "total_xp": 0, "percentage": 0.0}

    base_xp = score * XP_PER_CORRECT
    percentage = (score / total_questions) * 100
    bonus_xp = 0

    for threshold, bonus in BONUS_TIERS:
        if percentage >= threshold:
            bonus_xp = bonus
            break
            
    total_xp = base_xp + bonus_xp
    if has_boost:
        total_xp *= 2

    return {
        "base_xp": base_xp,
        "bonus_xp": bonus_xp,
        "total_xp": total_xp,
        "percentage": round(percentage, 1),
    }


# ---------------------------------------------------------------------------
# Apply XP to user (update DB)
# ---------------------------------------------------------------------------


def award_xp(user_id: int, xp_earned: int) -> dict:
    """
    Add `xp_earned` to the user's total XP and recalculate their level.

    Returns:
        {
            "new_xp":       <int>,
            "new_level":    <int>,
            "leveled_up":   <bool>,
            "old_level":    <int>,
        }
    """
    row = query_db(
        "SELECT xp, level FROM users WHERE id = ?", (user_id,), one=True
    )
    if row is None:
        return {}

    old_xp = row["xp"]
    old_level = row["level"]
    new_xp = old_xp + xp_earned
    new_level = level_for_xp(new_xp)

    execute_db(
        "UPDATE users SET xp = ?, level = ? WHERE id = ?",
        (new_xp, new_level, user_id),
    )

    return {
        "new_xp": new_xp,
        "new_level": new_level,
        "leveled_up": new_level > old_level,
        "old_level": old_level,
    }


# ---------------------------------------------------------------------------
# Streak helpers (stored in the quiz_results table via date field)
# ---------------------------------------------------------------------------


def get_current_streak(user_id: int) -> int:
    """
    Return the number of consecutive days the user has completed at least
    one quiz, ending today (or yesterday).
    """
    from datetime import date, timedelta

    rows = query_db(
        """
        SELECT DISTINCT DATE(date) AS quiz_date
        FROM   quiz_results
        WHERE  user_id = ?
        ORDER  BY quiz_date DESC
        """,
        (user_id,),
    )

    if not rows:
        return 0

    dates = [date.fromisoformat(r["quiz_date"]) for r in rows if r["quiz_date"]]
    if not dates:
        return 0
    today = date.today()

    # Allow streak to count if last quiz was today or yesterday
    if dates[0] < today - timedelta(days=1):
        return 0

    streak = 1
    for i in range(1, len(dates)):
        if dates[i - 1] - dates[i] == timedelta(days=1):
            streak += 1
        else:
            break

    return streak
