from rest_framework_simplejwt.tokens import AccessToken

from app.modules.users.models import UserRefreshToken


def generate_auth_tokens(user):
    access_token = AccessToken.for_user(user=user)
    refresh_obj = UserRefreshToken.objects.create(user=user)
    return {"access": str(access_token), "refresh": refresh_obj.token}


# class AccessTokenPayload(TypedDict):
#     sub: str
#     exp: int
#     iat: int
#     jti: str
#
#
# class InvalidAccessToken(Exception):
#     """Raised when an access token cannot be trusted."""
#
#
# def create_access_token(user_id: int | str) -> str:
#     issued_at = int(time())
#     expires_at = issued_at + int(settings.ACCESS_TOKEN_LIFETIME.total_seconds())
#
#     return jwt.encode(
#         {
#             "sub": str(user_id),
#             "iat": issued_at,
#             "exp": expires_at,
#             "jti": uuid4().hex,
#         },
#         settings.ACCESS_TOKEN_SECRET,
#         algorithm=settings.ACCESS_TOKEN_ALGORITHM,
#     )
#
#
# def decode_access_token(token: str) -> AccessTokenPayload:
#     try:
#         payload = jwt.decode(
#             token,
#             settings.ACCESS_TOKEN_SECRET,
#             algorithms=[settings.ACCESS_TOKEN_ALGORITHM],
#             options={"require": ["sub", "exp", "iat", "jti"]},
#         )
#     except InvalidTokenError as exc:
#         raise InvalidAccessToken("Access token is invalid or expired") from exc
#
#     return {
#         "sub": payload["sub"],
#         "exp": payload["exp"],
#         "iat": payload["iat"],
#         "jti": payload["jti"],
#     }
#
#
# def generate_refresh_token() -> str:
#     return token_urlsafe(32)
#
#
# def hash_refresh_token(token: str) -> str:
#     return sha256(token.encode()).hexdigest()
