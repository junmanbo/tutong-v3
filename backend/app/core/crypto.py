"""AES-256-GCM 암호화/복호화 유틸리티.

복호화된 API Key를 로그/응답에 절대 노출하지 않는다.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt(plaintext: str, key_hex: str) -> str:
    """AES-256-GCM 암호화.

    Args:
        plaintext: 암호화할 평문 문자열
        key_hex: 64자 hex 문자열 (32바이트 키)

    Returns:
        base64 인코딩된 (nonce + ciphertext) 문자열
    """
    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(encrypted: str, key_hex: str) -> str:
    """AES-256-GCM 복호화.

    Args:
        encrypted: base64 인코딩된 (nonce + ciphertext) 문자열
        key_hex: 64자 hex 문자열 (32바이트 키)

    Returns:
        복호화된 평문 문자열
    """
    key = bytes.fromhex(key_hex)
    data = base64.b64decode(encrypted)
    nonce, ct = data[:12], data[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode()
