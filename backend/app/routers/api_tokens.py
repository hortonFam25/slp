"""
Personal API keys — the three calls behind a "Connect Claude" card.

Every route here demands a REAL SESSION. Two things follow from that:

  * An `slp_` key can never reach these routes. It cannot: this router hangs
    off `get_auth_context`, which runs the bearer through JWT validation, and
    an `slp_` secret is not a JWT — it fails to decode and comes back 401
    before any handler runs. A key that could mint or revoke keys would be a
    key that survives its own revocation.
  * The anonymous fallback user (the one `auth_require_bearer=False` invents
    when no bearer is present) is refused as well — EXCEPT in development,
    where it is the only user there is and refusing it would mean no local
    developer could ever mint a key to test /mcp with.

Keys belong to one user. He sees only his own, and somebody else's id is a 404
rather than a 403, which leaks nothing about what exists.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.api_token import KIND_OAUTH
from app.schemas.api_token import ApiTokenCreate, ApiTokenCreatedOut, ApiTokenOut
from app.services import api_tokens as tokens_service
from app.services import oauth as oauth_service
from app.services.api_tokens import TokenLimitError
from app.settings import settings

router = APIRouter(prefix="/api/tokens", tags=["api-tokens"])


def require_session_auth(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """
    A signed-in human, not a machine and not the anonymous stand-in.

    In development the fallback user is allowed through on purpose: local dev
    runs with `auth_require_bearer=False` and no Entra tenant, so the fallback
    IS the developer, and without this exception there would be no way to mint
    the key that /mcp needs in order to be testable at all.
    """
    if auth.is_authenticated:
        return auth
    if settings.environment.strip().lower() == "development":
        return auth
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign in to manage connection keys",
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Connection key not found"
    )


@router.get("", response_model=list[ApiTokenOut])
@router.get("/", response_model=list[ApiTokenOut])
def list_tokens(
    auth: AuthContext = Depends(require_session_auth),
    db: Session = Depends(get_db),
):
    """This user's live connection keys, newest first."""
    return [
        tokens_service.to_out(row)
        for row in tokens_service.list_tokens(db, auth.user.id)
    ]


@router.post("", response_model=ApiTokenCreatedOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ApiTokenCreatedOut, status_code=status.HTTP_201_CREATED)
def create_token(
    payload: ApiTokenCreate,
    auth: AuthContext = Depends(require_session_auth),
    db: Session = Depends(get_db),
):
    """
    Mint a key for the signed-in user.

    The 201 body carries `token` — the ONLY time the plaintext exists outside
    the client. Nothing on the server can produce it again.
    """
    try:
        row, secret = tokens_service.create_token(db, auth.user.id, payload.name)
    except TokenLimitError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "code": "TOKEN_LIMIT"},
        )
    return {**tokens_service.to_out(row), "token": secret}


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(
    token_id: int,
    auth: AuthContext = Depends(require_session_auth),
    db: Session = Depends(get_db),
) -> None:
    """
    Revoke a key. The row is kept (revoked_at is stamped) rather than deleted,
    so a digest can never be reissued to a different key by accident.

    Revoking an OAuth-minted key cuts the WHOLE grant — its siblings go with
    it. Killing only the access key would be a button that appears to work and
    stops working within the day, because the connector would simply refresh
    itself a new one; "revoke" has to mean the connection is over.
    """
    row = tokens_service.get_token(db, auth.user.id, token_id)
    if row is None:
        raise _not_found()
    if row.kind == KIND_OAUTH and row.oauth_code_id is not None:
        # The refresh half first: an access key alone would come straight back
        # on the connector's next refresh, so cutting one without the other
        # would be a button that silently stops working within the hour.
        oauth_service.revoke_refresh_tokens_for_family(
            db, row.oauth_code_id, reason="revoked by therapist"
        )
        tokens_service.revoke_grant_family(db, row.oauth_code_id)
        return
    tokens_service.revoke_token(db, row)
