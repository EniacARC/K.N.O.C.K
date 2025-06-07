from multiprocessing import Semaphore, Process
import re
import sqlite3
import string
from typing import Optional

NUM_OF_AQ = 5
LOCK = Semaphore(NUM_OF_AQ)

class UserDatabase:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.num_of_aqs = NUM_OF_AQ
        self.lock = LOCK
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
        # write access
        for _ in range(self.num_of_aqs):
            self.lock.acquire()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT NOT NULL UNIQUE PRIMARY KEY,
                    password TEXT NOT NULL
                )
            """)
            conn.commit()
        for _ in range(self.num_of_aqs):
            self.lock.release()

    def add_user(self, username: str, password: str) -> tuple[bool, str]:
        return_bool = False
        return_msg = "invalid username or password"
        # write access
        for _ in range(self.num_of_aqs):
            self.lock.acquire()

        try:
            if self.is_valid_username(username) and self.is_valid_password(password):
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                    conn.commit()
                return_bool = True
                return_msg = "success"
        except sqlite3.IntegrityError:
            return_msg = "user exists"  # Username already exists
        finally:
            for _ in range(self.num_of_aqs):
                self.lock.release()
            return return_bool, return_msg

    def get_password(self, username: str) -> Optional[str]:
        return_val = None
        self.lock.acquire()
        with sqlite3.connect(self.db_path) as conn:
            if self.is_valid_username(username):
                cursor = conn.cursor()
                cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                return_val = row[0] if row else None
        self.lock.release()
        return return_val


    def user_exists(self, username: str) -> bool:
        """
        Check if a user with the given username exists in the database.

        :param username: The username to check for existence
        :return: True if the user exists, False otherwise
        """
        return_val = False
        self.lock.acquire()
        print(f"username: {username}")
        if self.is_valid_username(username):
            print("valid")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
                return_val = cursor.fetchone() is not None
        self.lock.release()
        return return_val


    # def delete_user(self, username: str) -> bool:
    #     with self.lock:
    #         with sqlite3.connect(self.db_path) as conn:
    #             cursor = conn.cursor()
    #             cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    #             conn.commit()
    #             return cursor.rowcount > 0

    def list_users(self):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM users WHERE username = 'user1'")
                return [row for row in cursor.fetchone()]


if __name__ == '__main__':
    my_db = UserDatabase()
    # print(my_db.add_user('user6', '122345453'))
    print(my_db.user_exists('user1'))
