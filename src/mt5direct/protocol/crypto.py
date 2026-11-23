"""AES-256-CBC with a zero IV and PKCS#7 padding, as used by the terminal protocol."""

from Crypto.Cipher import AES

_ZERO_IV = b'\x00' * 16


class AesCipher:
    __slots__ = ('key',)

    def __init__(self, key: bytes):
        self.key = key

    def encrypt(self, plaintext: bytes) -> bytes:
        pad_len = 16 - (len(plaintext) % 16)
        return AES.new(self.key, AES.MODE_CBC, _ZERO_IV).encrypt(
            plaintext + bytes([pad_len] * pad_len))

    def decrypt(self, ciphertext: bytes):
        """Return plaintext, or ``None`` if the length is not a multiple of 16."""
        if len(ciphertext) == 0 or len(ciphertext) % 16 != 0:
            return None
        pt = AES.new(self.key, AES.MODE_CBC, _ZERO_IV).decrypt(ciphertext)
        pad = pt[-1]
        if 1 <= pad <= 16 and all(b == pad for b in pt[-pad:]):
            pt = pt[:-pad]
        return pt
