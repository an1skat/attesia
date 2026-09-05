# from time import time
# from uuid import UUID, uuid4
#
# import jwt
# import pytest
# from django.conf import settings
# from django.test import override_settings
#
# from app.core.auth.tokens import (
#     InvalidAccessToken,
#     create_access_token,
#     decode_access_token,
#     generate_refresh_token,
#     hash_refresh_token,
# )
#
#
# def test_access_token_round_trip():
#     before = int(time())
#     token = create_access_token(123)
#     payload = decode_access_token(token)
#     after = int(time())
#
#     assert payload["sub"] == "123"
#     assert before <= payload["iat"] <= after
#     assert payload["exp"] - payload["iat"] == 10 * 60
#     assert UUID(payload["jti"]).version == 4
#
#
# def test_access_token_rejects_invalid_signature():
#     with override_settings(ACCESS_TOKEN_SECRET="a" * 64):
#         token = create_access_token(123)
#
#     with (
#         override_settings(ACCESS_TOKEN_SECRET="b" * 64),
#         pytest.raises(InvalidAccessToken),
#     ):
#         decode_access_token(token)
#
#
# def test_access_token_rejects_expired_token():
#     expired_at = int(time()) - 1
#     token = jwt.encode(
#         {
#             "sub": "123",
#             "iat": expired_at - 10 * 60,
#             "exp": expired_at,
#             "jti": uuid4().hex,
#         },
#         settings.ACCESS_TOKEN_SECRET,
#         algorithm=settings.ACCESS_TOKEN_ALGORITHM,
#     )
#
#     with pytest.raises(InvalidAccessToken):
#         decode_access_token(token)
#
#
# def test_access_token_rejects_missing_required_claim():
#     issued_at = int(time())
#     token = jwt.encode(
#         {
#             "sub": "123",
#             "iat": issued_at,
#             "exp": issued_at + 10 * 60,
#         },
#         settings.ACCESS_TOKEN_SECRET,
#         algorithm=settings.ACCESS_TOKEN_ALGORITHM,
#     )
#
#     with pytest.raises(InvalidAccessToken):
#         decode_access_token(token)
#
#
# def test_refresh_tokens_are_random_and_long_enough():
#     first = generate_refresh_token()
#     second = generate_refresh_token()
#
#     assert first != second
#     assert len(first) >= 43
#     assert len(second) >= 43
#
#
# def test_refresh_token_hash_is_stable_and_does_not_expose_token():
#     token = generate_refresh_token()
#     other_token = generate_refresh_token()
#
#     token_hash = hash_refresh_token(token)
#
#     assert token_hash == hash_refresh_token(token)
#     assert token_hash != hash_refresh_token(other_token)
#     assert token_hash != token
#     assert len(token_hash) == 64
