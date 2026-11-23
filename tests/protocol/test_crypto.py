from Crypto.Cipher import AES

from mt5direct.protocol.crypto import AesCipher

KEY = bytes(range(32))


def test_roundtrip():
    c = AesCipher(KEY)
    assert c.decrypt(c.encrypt(b'hello')) == b'hello'


def test_decrypt_rejects_bad_length():
    c = AesCipher(KEY)
    assert c.decrypt(b'') is None
    assert c.decrypt(b'x' * 15) is None


def test_zero_iv_and_pkcs7_padding():
    c = AesCipher(KEY)
    expected = AES.new(KEY, AES.MODE_CBC, b'\x00' * 16).encrypt(b'\x10' * 16)
    assert c.encrypt(b'') == expected
