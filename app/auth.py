from fastapi import HTTPException, status, Request
from .config import settings

def validate_token(token: str) -> None:
    valid_tokens = []
    if settings.API_AUTH_TOKEN:
        valid_tokens.append(settings.API_AUTH_TOKEN)

    if token not in valid_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing token",
        )

def verify_header_auth(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing Bearer token",
        )

    token = auth_header.split(" ", 1)[1]
    validate_token(token)
    return token
