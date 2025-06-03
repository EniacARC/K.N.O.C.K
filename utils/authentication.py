# from db_comms import DatabaseConnector # for final execution
import hashlib
import random
import string
import time

TEMP_H1 = "dawdawdafd"


class AuthService:
    def __init__(self, name):
        # the db connector object
        self.name = name

    @staticmethod
    def generate_nonce():
        characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
        random_part = ''.join(random.choices(characters, k=16))  # Generate random string
        timestamp = int(time.time())  # Current UNIX timestamp
        return f"{timestamp}-{random_part}"  # Combine timestamp and random part

    def _calculate_ha1(self, username, realm, password):
        # in real imp use database connector to get the ha1
        return hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()

    def _get_ha2(self, method, realm):
        return hashlib.md5(f"{method}:{realm}".encode()).hexdigest()

    def calculate_hash_auth(self, username, ha1, method, nonce, realm=None):
        if not realm:
            realm = self.name
        if ha1:
            ha2 = str(self._get_ha2(method, realm))
            return hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        return None

    def calculate_expected(self, ha1, method, nonce, realm=None):
        if not realm:
            realm = self.name
        ha2 = str(self._get_ha2(method, realm))
        return hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
