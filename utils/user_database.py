import contextvars
from multiprocessing import Semaphore, Process
import re
import sqlite3
import string
from typing import Optional
# from authentication import AuthService

NUM_OF_AQ = 5
LOCK = Semaphore(NUM_OF_AQ)
in_write_context = contextvars.ContextVar("in_write_context", default=False)

class UserDatabase:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.num_of_aqs = NUM_OF_AQ
        self.lock = LOCK
        self._create_table()

    def _acquire_read(self):
        if not in_write_context.get():
            self.lock.acquire()

    def _release_read(self):
        if not in_write_context.get():
            self.lock.release()

    def _acquire_write(self):
        if not in_write_context.get():
            for _ in range(self.num_of_aqs):
                self.lock.acquire()
            in_write_context.set(True)

    def _release_write(self):
        if in_write_context.get():
            for _ in range(self.num_of_aqs):
                self.lock.release()
            in_write_context.set(False)

    def is_valid_username(self, username: str) -> bool:
        """Allow only alphanumeric usernames with underscores or hyphens (3–30 chars)."""
        return bool(re.fullmatch(r"[a-zA-Z0-9_-]{3,30}", username))



    def is_valid_password(self, password: str) -> bool:
        """Disallow control characters and enforce length (8–64 chars)."""
        if not (6 <= len(password) <= 32):
            print("too long")
            return False
        allowed_chars = set(string.printable) - set(string.whitespace[:6])  # no \n \r \t etc.
        return all(c in allowed_chars for c in password)

    def _create_table(self):
        # write access
        self._acquire_write()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT NOT NULL UNIQUE PRIMARY KEY,
                    password TEXT NOT NULL
                )
            """)
            conn.commit()
        self._release_write()

    def add_user(self, username: str, password: str) -> bool:
        print(username)
        print(password)
        print(self.user_exists(username))
        return_bool = False
        # write access
        self._acquire_write()
        if self.is_valid_username(username) and self.is_valid_password(password) and not self.user_exists(username):
            print("can addd user")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
            return_bool = True
        self._release_write()
        return return_bool
    def get_password(self, username: str) -> Optional[str]:
        return_val = None
        self._acquire_read()
        with sqlite3.connect(self.db_path) as conn:
            if self.is_valid_username(username):
                cursor = conn.cursor()
                cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                return_val = row[0] if row else None
        self._release_read()
        return return_val


    def user_exists(self, username: str) -> bool:
        """
        Check if a user with the given username exists in the database.

        :param username: The username to check for existence
        :return: True if the user exists, False otherwise
        """
        print("entedred")
        return_val = False
        self._acquire_read()
        print("aquired")
        print(f"username: {username}")
        if self.is_valid_username(username):
            print("valid")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
                return_val = cursor.fetchone() is not None
        self._release_read()
        print(return_val)
        return return_val


    # def delete_user(self, username: str) -> bool:
    #     with self.lock:
    #         with sqlite3.connect(self.db_path) as conn:
    #             cursor = conn.cursor()
    #             cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    #             conn.commit()
    #             return cursor.rowcount > 0

    def list_users(self):
        r_vals = None
        self._acquire_read()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE username = 'user1'")
            r_vals = [row for row in cursor.fetchone()]
        self._release_read()
        return r_vals



if __name__ == '__main__':
    my_db = UserDatabase()
    # auth = AuthService("myserver")
    # ha1 = auth.calculate_ha1('ts2', '123456')
    # print(ha1)
    # print(len(ha1))
    # print(my_db.is_valid_password(ha1))
    # print(my_db.add_user('user6', '122345453'))
    print(my_db.add_user('ts2', '231rwr324'))
