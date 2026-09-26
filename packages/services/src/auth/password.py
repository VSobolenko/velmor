from __future__ import annotations

import hashlib
import hmac
import secrets


class PasswordHasher:
    SALT_BYTES = 16

    def hash(self, password: str) -> tuple[str, str]:
        salt = secrets.token_bytes(self.SALT_BYTES)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return digest.hex(), salt.hex()

    def matches(self, password: str, password_hash: str, password_salt: str) -> bool:
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(password_salt), n=2**14, r=8, p=1
        )
        return hmac.compare_digest(digest.hex(), password_hash)
