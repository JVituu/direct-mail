import unittest
from unittest.mock import patch

from app.shared.security import authenticator


class AuthenticatorTest(unittest.TestCase):
    def test_authenticates_configured_user(self) -> None:
        with patch.object(authenticator, "LOGIN_USERNAME", "eventos"), patch.object(
            authenticator,
            "PASSWORD_HASH",
            authenticator.password_hash("senha-teste"),
        ):
            self.assertTrue(authenticator.authenticate("eventos", "senha-teste"))
            self.assertTrue(authenticator.authenticate(" EVENTOS ", "senha-teste"))

    def test_rejects_invalid_credentials(self) -> None:
        with patch.object(authenticator, "LOGIN_USERNAME", "eventos"), patch.object(
            authenticator,
            "PASSWORD_HASH",
            authenticator.password_hash("senha-teste"),
        ):
            self.assertFalse(authenticator.authenticate("eventos", "senha-errada"))
            self.assertFalse(authenticator.authenticate("outro", "senha-teste"))

    def test_rejects_when_password_hash_is_not_configured(self) -> None:
        with patch.object(authenticator, "PASSWORD_HASH", ""):
            self.assertFalse(authenticator.authenticate("eventos", "senha-teste"))

    def test_password_hash_is_stable(self) -> None:
        self.assertEqual(
            authenticator.password_hash("mala-direta"),
            "0db052bca426544bfe05b15a0df161ed5c79c0b387ab628476f7f77ddff889ad",
        )


if __name__ == "__main__":
    unittest.main()
