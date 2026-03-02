"""bot_engine/utils/crypto.py 단위 테스트.

DB 불필요 — 순수 함수 테스트.
"""
import pytest

from bot_engine.utils.crypto import decrypt, encrypt

# 테스트용 256비트(32바이트) AES 키 (64자 hex)
TEST_KEY = "0" * 64
ALT_KEY = "1" * 64


class TestEncryptDecrypt:
    def test_round_trip(self):
        plaintext = "my-secret-api-key"
        encrypted = encrypt(plaintext, TEST_KEY)
        assert decrypt(encrypted, TEST_KEY) == plaintext

    def test_empty_string(self):
        plaintext = ""
        encrypted = encrypt(plaintext, TEST_KEY)
        assert decrypt(encrypted, TEST_KEY) == plaintext

    def test_unicode_string(self):
        plaintext = "한국어 API 키 테스트 🔑"
        encrypted = encrypt(plaintext, TEST_KEY)
        assert decrypt(encrypted, TEST_KEY) == plaintext

    def test_long_string(self):
        plaintext = "x" * 10000
        encrypted = encrypt(plaintext, TEST_KEY)
        assert decrypt(encrypted, TEST_KEY) == plaintext

    def test_encrypted_differs_from_plaintext(self):
        plaintext = "secret"
        encrypted = encrypt(plaintext, TEST_KEY)
        assert encrypted != plaintext

    def test_two_encryptions_of_same_text_differ(self):
        """랜덤 nonce 덕분에 동일 평문도 암호화할 때마다 다른 결과."""
        plaintext = "same-text"
        enc1 = encrypt(plaintext, TEST_KEY)
        enc2 = encrypt(plaintext, TEST_KEY)
        assert enc1 != enc2

    def test_different_key_cannot_decrypt(self):
        """다른 키로 복호화 시 예외 발생."""
        encrypted = encrypt("secret", TEST_KEY)
        with pytest.raises(Exception):
            decrypt(encrypted, ALT_KEY)

    def test_encrypted_is_base64_string(self):
        import base64
        encrypted = encrypt("test", TEST_KEY)
        # base64 디코딩이 가능해야 함
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > 12  # nonce(12) + ciphertext

    def test_nonce_length(self):
        """복호화된 raw 데이터에서 nonce(12바이트) 분리 확인."""
        import base64
        encrypted = encrypt("test-data", TEST_KEY)
        raw = base64.b64decode(encrypted)
        nonce = raw[:12]
        assert len(nonce) == 12

    def test_tampered_ciphertext_fails(self):
        """암호문 변조 시 복호화 실패."""
        import base64
        encrypted = encrypt("original", TEST_KEY)
        raw = bytearray(base64.b64decode(encrypted))
        # 마지막 바이트 변조
        raw[-1] ^= 0xFF
        tampered = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(Exception):
            decrypt(tampered, TEST_KEY)
