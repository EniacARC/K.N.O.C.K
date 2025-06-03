import multiprocessing
import re
import sqlite3
import string
from typing import Optional

class UserDatabase:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.lock = multiprocessing.Lock()
        self._create_table()

    def is_valid_username(self, username: str) -> bool:
        """Allow only alphanumeric usernames with underscores or hyphens (3–30 chars)."""
        return bool(re.fullmatch(r"[a-zA-Z0-9_-]{3,30}", username))



    def is_valid_password(self, password: str) -> bool:
        """Disallow control characters and enforce length (8–64 chars)."""
        if not (6 <= len(password) <= 16):
            return False
        allowed_chars = set(string.printable) - set(string.whitespace[:6])  # no \n \r \t etc.
        return all(c in allowed_chars for c in password)

    def _create_table(self):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        username TEXT NOT NULL UNIQUE PRIMARY KEY,
                        password TEXT NOT NULL
                    )
                """)
                conn.commit()

    def add_user(self, username: str, password: str) -> tuple[bool, str]:
        try:
            with self.lock:
                if self.is_valid_username(username) and self.is_valid_password(password):
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                        conn.commit()
                    return True, "success"
                return False, "invalid username or password"
        except sqlite3.IntegrityError:
            return False, "user exists"  # Username already exists

    def get_password(self, username: str) -> Optional[str]:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                return row[0] if row else None

    def delete_user(self, username: str) -> bool:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE username = ?", (username,))
                conn.commit()
                return cursor.rowcount > 0

    def list_users(self):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM users")
                return [row[0] for row in cursor.fetchall()]


if __name__ == '__main__':
    my_db = UserDatabase()
    print(my_db.get_password('user4'))
