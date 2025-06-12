from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Random import get_random_bytes

KEY_SIZE = 2048

class RSACrypt:
    def __init__(self):
        self.private_key = None
        self.public_key = None

    def generate_keys(self):
        key = RSA.generate(KEY_SIZE)
        self.private_key = key
        self.public_key = key.publickey()

    def export_public_key(self):
        return self.public_key.export_key()

    def import_public_key(self, public_pem):
        self.public_key = RSA.import_key(public_pem)

    def encrypt(self, data):
        """
        data in bytes. encrypts with public
        """
        if not self.public_key:
            raise ValueError("Public key not loaded.")
        cipher = PKCS1_OAEP.new(self.public_key)
        return cipher.encrypt(data)

    def decrypt(self, encrypted_data):
        """
        encrypted_data in bytes. decrypts with private
        """
        if not self.private_key:
            raise ValueError("Private key not loaded.")
        cipher = PKCS1_OAEP.new(self.private_key)
        return cipher.decrypt(encrypted_data)

