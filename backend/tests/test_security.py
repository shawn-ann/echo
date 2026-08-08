import re

import pytest

from app.core import security


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self):
        hashed = security.hash_password("demo1234")
        assert hashed != "demo1234"
        assert security.verify_password("demo1234", hashed) is True

    def test_wrong_password_rejected(self):
        hashed = security.hash_password("demo1234")
        assert security.verify_password("wrong", hashed) is False

    def test_hash_is_salted(self):
        assert security.hash_password("demo1234") != security.hash_password("demo1234")


class TestToken:
    def test_generate_token_is_urlsafe_and_long(self):
        token = security.generate_token()
        assert len(token) >= 43
        assert re.fullmatch(r"[A-Za-z0-9_-]+", token)

    def test_generate_token_is_unique(self):
        assert security.generate_token() != security.generate_token()

    def test_hash_token_sha256_hex(self):
        token = "some-token"
        digest = security.hash_token(token)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)

    def test_hash_token_is_deterministic(self):
        assert security.hash_token("abc") == security.hash_token("abc")

    @pytest.mark.parametrize(
        "password",
        ["demo1234", "", "very long password with spaces 123 !@#"],
    )
    def test_any_password_hashable_and_verifiable(self, password):
        hashed = security.hash_password(password)
        assert security.verify_password(password, hashed) is True
