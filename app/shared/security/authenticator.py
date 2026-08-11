import hashlib
import hmac

try:
    from app.shared.security.login_credentials import (
        LOGIN_USERNAME,
        PASSWORD_HASH,
        PASSWORD_ITERATIONS,
        PASSWORD_SALT,
    )
except ModuleNotFoundError as exc:
    if exc.name != "app.shared.security.login_credentials":
        raise
    from app.shared.security.login_credentials_example import (
        LOGIN_USERNAME,
        PASSWORD_HASH,
        PASSWORD_ITERATIONS,
        PASSWORD_SALT,
    )


def password_hash(password: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        PASSWORD_SALT.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()


def authenticate(username: str, password: str) -> bool:
    clean_username = str(username or "").strip().casefold()
    expected_username = str(LOGIN_USERNAME or "").strip().casefold()
    expected_hash = str(PASSWORD_HASH or "").strip()
    if not expected_username or not expected_hash:
        return False
    if not hmac.compare_digest(clean_username, expected_username):
        return False
    return hmac.compare_digest(password_hash(password), expected_hash)
