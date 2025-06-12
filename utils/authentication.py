# from db_comms import DatabaseConnector # for final execution
import hashlib
import random
import string
import time

TEMP_H1 = "dawdawdafd"



def generate_nonce():
    """
    Generate a unique nonce using current timestamp and random characters.

    :returns: generated nonce string (format: "<timestamp>-<random_string>")
    :rtype: str
    """
    characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
    random_part = ''.join(random.choices(characters, k=16))  # Generate random string
    timestamp = int(time.time())  # Current UNIX timestamp
    return f"{timestamp}-{random_part}"  # Combine timestamp and random part



def calculate_ha1(username, password, realm):
    """
    Calculate HA1 hash using the formula: MD5(username:realm:password).

    :param username: the user's username
    :type username: str

    :param realm: the authentication realm
    :type realm: str

    :param password: the user's password
    :type password: str

    :return: HA1 hash
    :rtype: str
    """
    # in real imp use database connector to get the ha1
    return hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()

def get_ha2(method, realm):
    """
    Calculate HA2 hash using the formula: MD5(method:realm).

    :param method: SIP method (e.g., INVITE, REGISTER)
    :type method: str

    :param realm: the authentication realm
    :type realm: str

    :return: HA2 hash
    :rtype: str
    """
    return hashlib.md5(f"{method}:{realm}".encode()).hexdigest()

def calculate_hash_auth(ha1, method, nonce, realm):
    """
    Calculate the final digest authentication response hash.

    :param ha1: HA1 hash (precomputed or fetched from database)
    :type ha1: str

    :param method: SIP method (e.g., INVITE, REGISTER)
    :type method: str

    :param nonce: the nonce received from the server
    :type nonce: str

    :param realm: optional realm (if not given, uses self.name)
    :type realm: str or None

    :return: response hash for comparison with client response
    :rtype: str or None
    """
    if ha1:
        ha2 = str(get_ha2(method, realm))
        return hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    return None

# class AuthService:
#     def __init__(self, name):
#         # the db connector object
#         self.name = name





    # def calculate_expected(self, ha1, method, nonce, realm=None):
    #     if not realm:
    #         realm = self.name
    #     ha2 = str(self._get_ha2(method, realm))
    #     return hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
