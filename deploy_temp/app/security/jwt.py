from typing import Optional
from jose import jwt, JWTError
from pydantic import BaseModel
from app.settings import settings


class TokenClaims(BaseModel):
    sub: str
    aud: Optional[str] = None
    iss: Optional[str] = None
    name: Optional[str] = None
    preferred_username: Optional[str] = None


def validate_jwt(token: str) -> TokenClaims:
    # Minimal validation placeholder. In production, fetch JWKS and verify.
    # Here we decode without verification in dev for scaffolding purposes only.
    options = {
        "verify_signature": False,
        "verify_aud": False,
        "verify_iss": False,
    }
    try:
        payload = jwt.decode(token, key="", options=options)  # type: ignore[arg-type]
        return TokenClaims(**payload)
    except JWTError as exc:  # pragma: no cover - skeleton
        raise ValueError("Invalid token") from exc


