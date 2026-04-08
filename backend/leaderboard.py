# Leaderboard ranking logic

from database import query_db, execute_db
from models import LeaderboardEntry

# Fetch top players


def get_top_players(limit: int = 20) -> list[dict]:
    # Get top players ranked by XP
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
    # Get user rank info
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


# Update leaderboard scores


def update_leaderboard(user_id: int, quiz_score: int) -> None:
    # Update user best score
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
    # Refresh leaderboard ranks
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


# Model wrappers


def get_top_entries(limit: int = 20) -> list[LeaderboardEntry]:
    # Get top entries as objects
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
