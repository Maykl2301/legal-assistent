"""
База даних SQLite для зберігання питань користувачів.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "lawyer_bot.db")


def get_connection():
    """Отримати підключення до БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Ініціалізація бази даних"""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                topic TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                question_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_user_id
            ON questions(user_id)
        """)
        conn.commit()
    print("✅ База даних ініціалізована")


def save_question(user_id: int, question: str, answer: str, topic: str = "general"):
    """Зберегти питання та відповідь"""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO questions (user_id, question, answer, topic)
                VALUES (?, ?, ?, ?)
            """, (user_id, question, answer, topic))

            conn.execute("""
                INSERT INTO users (user_id, question_count, last_seen)
                VALUES (?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    question_count = question_count + 1,
                    last_seen = CURRENT_TIMESTAMP
            """, (user_id,))
            conn.commit()
    except Exception as e:
        print(f"❌ Помилка збереження в БД: {e}")


def get_history(user_id: int, limit: int = 5) -> list:
    """Отримати останні питання користувача"""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT question, topic,
                    strftime('%d.%m.%Y %H:%M', created_at) as formatted_date
                FROM questions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            return [(row["question"], row["topic"], row["formatted_date"])
                    for row in cursor.fetchall()]
    except Exception as e:
        print(f"❌ Помилка читання з БД: {e}")
        return []


def get_stats() -> dict:
    """Статистика бота (для адміна)"""
    try:
        with get_connection() as conn:
            total_users = conn.execute(
                "SELECT COUNT(*) as cnt FROM users"
            ).fetchone()["cnt"]

            total_questions = conn.execute(
                "SELECT COUNT(*) as cnt FROM questions"
            ).fetchone()["cnt"]

            popular_topics = conn.execute("""
                SELECT topic, COUNT(*) as cnt
                FROM questions
                GROUP BY topic
                ORDER BY cnt DESC
                LIMIT 5
            """).fetchall()

            return {
                "total_users": total_users,
                "total_questions": total_questions,
                "popular_topics": [(r["topic"], r["cnt"]) for r in popular_topics]
            }
    except Exception as e:
        print(f"❌ Помилка отримання статистики: {e}")
        return {}
