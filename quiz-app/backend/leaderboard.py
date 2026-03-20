"""
leaderboard.py — Leaderboard management.

Responsibilities:
    - Rank users by their cumulative XP (stored on the users table)
    - Upsert a user's best score into the leaderboard table after a quiz
    - Expose helpers for the leaderboard page and profile page

The `leaderboard` table acts as a materialised cache of
(user_id, best_single_quiz_score, rank).  Global ranking by XP is
derived live from the `users` table so it is always up-to-date.
"""

from database import query_db, execute_db
from models import LeaderboardEntry

# ---------------------------------------------------------------------------
# Fetching top players
# ---------------------------------------------------------------------------


def get_top_players(limit: int = 20) -> list[dict]:
    """
    Return the top `limit` players ranked by their total XP.

    Each dict contains:
        rank, username, xp, level, best_score, quizzes_played
    """
    rows = query_db(
        """
        SELECT
            u.*,
            COUNT(qr.id)       AS quizzes_played,
            MAX(qr.score)      AS best_score,
            ROW_NUMBER() OVER (ORDER BY u.xp DESC) AS rank
        FROM   users u
        LEFT JOIN quiz_results qr ON qr.user_id = u.id
        GROUP  BY u.id
        ORDER  BY u.xp DESC
        LIMIT  ?
        """,
        (limit,),
    )
    return [dict(r) for r in rows] if rows else []


def get_user_rank(user_id: int) -> dict | None:
    """
    Return rank information for a single user.

    Returns a dict with keys: rank, username, xp, level, quizzes_played, best_score
    or None if the user doesn't exist.
    """
    row = query_db(
        """
        SELECT
            rank_sub.rank,
            rank_sub.username,
            rank_sub.xp,
            rank_sub.level,
            rank_sub.quizzes_played,
            rank_sub.best_score
        FROM (
            SELECT
                u.*,
                COUNT(qr.id)  AS quizzes_played,
                MAX(qr.score) AS best_score,
                ROW_NUMBER() OVER (ORDER BY u.xp DESC) AS rank
            FROM   users u
            LEFT JOIN quiz_results qr ON qr.user_id = u.id
            GROUP  BY u.id
        ) rank_sub
        WHERE rank_sub.id = ?
        """,
        (user_id,),
        one=True,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Update leaderboard after a quiz
# ---------------------------------------------------------------------------


def update_leaderboard(user_id: int, quiz_score: int) -> None:
    """
    Upsert the user's best quiz score in the `leaderboard` table, then
    refresh the stored rank for the top 20 players.

    Call this from quiz_engine.finish_quiz() after every completed quiz.
    """
    # Upsert: keep the higher of the stored score vs. the new score
    existing = query_db(
        "SELECT id, score FROM leaderboard WHERE user_id = ?",
        (user_id,),
        one=True,
    )

    if existing is None:
        execute_db(
            "INSERT INTO leaderboard (user_id, score) VALUES (?, ?)",
            (user_id, quiz_score),
        )
    elif quiz_score > existing["score"]:
        execute_db(
            "UPDATE leaderboard SET score = ? WHERE user_id = ?",
            (quiz_score, user_id),
        )

    # Recompute stored ranks for all entries (keeps the rank column in sync)
    _refresh_ranks()


def _refresh_ranks() -> None:
    """
    Recalculate and persist the `rank` column in the leaderboard table.
    Uses XP (from users) as the primary sort criterion, consistent with
    get_top_players().
    """
    rows = query_db("""
        SELECT lb.id
        FROM   leaderboard lb
        JOIN   users u ON u.id = lb.user_id
        ORDER  BY u.xp DESC
        """)
    for rank, row in enumerate(rows, start=1):
        execute_db(
            "UPDATE leaderboard SET rank = ? WHERE id = ?",
            (rank, row["id"]),
        )


# ---------------------------------------------------------------------------
# Convenience: LeaderboardEntry model wrappers
# ---------------------------------------------------------------------------


def get_top_entries(limit: int = 20) -> list[LeaderboardEntry]:
    """
    Return top leaderboard rows as LeaderboardEntry model objects
    (joins leaderboard table with users for username).
    """
    rows = query_db(
        """
        SELECT lb.user_id, lb.score, lb.rank, u.username
        FROM   leaderboard lb
        JOIN   users u ON u.id = lb.user_id
        ORDER  BY lb.rank ASC
        LIMIT  ?
        """,
        (limit,),
    )
    return [LeaderboardEntry(r) for r in rows] if rows else []
