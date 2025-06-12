from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Hash import HMAC, SHA256

TAG_SIZE = 16

KEY_SIZE = 32
NONCE_SIZE = 16
HMAC_SIZE = 32  # SHA-256 digest size
class AESCryptGCM:
    # uses GCM aes encryption for sip
    def __init__(self, key = None):
        self.key = key if key else get_random_bytes(KEY_SIZE)

    def encrypt(self, data):
        """
        Encrypt raw bytes using AES-GCM.
        Returns: nonce + ciphertext + tag as raw bytes concatenated.
        """
        nonce = get_random_bytes(NONCE_SIZE)  # Recommended size for GCM nonce is 12 bytes
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        # Return nonce + ciphertext + tag, all raw bytes concatenated
        return nonce + ciphertext + tag

    def decrypt(self, encrypted_data):
        """
        Decrypt raw bytes (nonce + ciphertext + tag).
        Returns original plaintext bytes if authentication passes.
        Raises ValueError if tag verification fails.
        """
        nonce = encrypted_data[:NONCE_SIZE]
        tag = encrypted_data[-TAG_SIZE:]
        ciphertext = encrypted_data[NONCE_SIZE:-TAG_SIZE]
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext


    def export_key(self) -> bytes:
        """
        Export raw AES key bytes.
        """
        return self.key

class AESCryptCTR:
    # uses GCM aes encryption for rtp
    def __init__(self):
        self.key = get_random_bytes(KEY_SIZE)  # AES key
        self.hmac_key = get_random_bytes(KEY_SIZE)  # Separate key for HMAC

    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypt raw bytes using AES-CTR and append HMAC-SHA256 for integrity.
        Returns: nonce + ciphertext + hmac
        """
        nonce = get_random_bytes(NONCE_SIZE)
        cipher = AES.new(self.key, AES.MODE_CTR, nonce=nonce)
        ciphertext = cipher.encrypt(data)

        # Compute HMAC over nonce + ciphertext
        mac = HMAC.new(self.hmac_key, nonce + ciphertext, digestmod=SHA256).digest()

        return nonce + ciphertext + mac

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt raw bytes using AES-CTR and verify HMAC.
        Expects input format: nonce + ciphertext + hmac
        Raises ValueError if HMAC is invalid.
        """
        nonce = encrypted_data[:NONCE_SIZE]
        mac = encrypted_data[-HMAC_SIZE:]
        ciphertext = encrypted_data[NONCE_SIZE:-HMAC_SIZE]

        # Verify HMAC
        hmac_calculated = HMAC.new(self.hmac_key, nonce + ciphertext, digestmod=SHA256)
        hmac_calculated.verify(mac)  # raises ValueError if invalid

        cipher = AES.new(self.key, AES.MODE_CTR, nonce=nonce)
        plaintext = cipher.decrypt(ciphertext)
        return plaintext

    def export_key(self) -> tuple:
        """
        Export AES and HMAC keys as raw bytes.
        """
        return self.key, self.hmac_key