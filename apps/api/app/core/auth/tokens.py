# def hash_token(raw_token: str) -> str:
#     return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
#
#
# def generate_raw_token() -> str:
#     return secrets.token_urlsafe(32)


# def generate_auth_tokens(user) -> dict[str, str]:
#     from app.modules.users.services import UserService
#
#     access_token = str(AccessToken.for_user(user))
#     raw_refresh_token, _ = UserService.create_refresh_token_for_user(user)
#
#     return {
#         "access": access_token,
#         "refresh": raw_refresh_token,
#     }


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
