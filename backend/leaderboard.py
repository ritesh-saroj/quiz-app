# Leaderboard ranking logic

from database import query_db, execute_db
from models import LeaderboardEntry
from gamification import get_rank_title

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

    # Ranking is now dynamic, no need to refresh stored ranks


# Model wrappers


def get_top_entries(limit: int = 20) -> list[LeaderboardEntry]:
    # Get top entries with dynamic ranking by total XP
    rows = query_db(
        """
        SELECT 
            lb.user_id, 
            lb.score, 
            u.username,
            u.xp,
            u.level,
            u.avatar_url,
            ROW_NUMBER() OVER (ORDER BY u.xp DESC) as rank
        FROM leaderboard lb
        JOIN users u ON u.id = lb.user_id
        ORDER BY rank ASC
        LIMIT ?
        """,
        (limit,),
    )
    
    entries = []
    if rows:
        for r in rows:
            data = dict(r)
            # Add rank title dynamically based on level
            data["rank_title"] = get_rank_title(data["level"])
            entries.append(LeaderboardEntry(data))
    
    return entries
