from __future__ import annotations

from packages.services.src.auth.password import PasswordHasher

PASSWORD = 'a sufficiently long passphrase'


class TestPasswordHasher:
    def test_the_correct_password_verifies(self) -> None:
        hasher = PasswordHasher()

        password_hash, password_salt = hasher.hash(PASSWORD)

        assert hasher.matches(PASSWORD, password_hash, password_salt)

    def test_a_wrong_password_fails(self) -> None:
        hasher = PasswordHasher()
        password_hash, password_salt = hasher.hash(PASSWORD)

        assert not hasher.matches('a different passphrase', password_hash, password_salt)

    def test_the_stored_value_is_not_the_password(self) -> None:
        hasher = PasswordHasher()

        password_hash, password_salt = hasher.hash(PASSWORD)

        assert PASSWORD not in password_hash
        assert PASSWORD not in password_salt

    def test_two_accounts_with_one_password_store_different_values(self) -> None:
        hasher = PasswordHasher()

        first_hash, first_salt = hasher.hash(PASSWORD)
        second_hash, second_salt = hasher.hash(PASSWORD)

        assert first_hash != second_hash
        assert first_salt != second_salt
        assert hasher.matches(PASSWORD, first_hash, first_salt)
        assert hasher.matches(PASSWORD, second_hash, second_salt)

    def test_a_hash_does_not_verify_under_another_accounts_salt(self) -> None:
        hasher = PasswordHasher()
        password_hash, _first_salt = hasher.hash(PASSWORD)
        _other_hash, other_salt = hasher.hash(PASSWORD)

        assert not hasher.matches(PASSWORD, password_hash, other_salt)
