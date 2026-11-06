from app.core.security import hash_password, verify_password


def test_hash_password_verifies_original_password() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash)


def test_hash_password_uses_a_unique_salt() -> None:
    first_hash = hash_password("same password")
    second_hash = hash_password("same password")

    assert first_hash != second_hash
    assert verify_password("same password", first_hash)
    assert verify_password("same password", second_hash)


def test_verify_password_rejects_wrong_password() -> None:
    password_hash = hash_password("correct password")

    assert not verify_password("wrong password", password_hash)


def test_verify_password_rejects_invalid_hash() -> None:
    assert not verify_password("any password", "not-an-argon2-hash")
