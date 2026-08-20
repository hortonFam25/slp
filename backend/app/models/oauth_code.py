"""
One authorization code: the ten-minute, single-use ticket a therapist hands to
claude.ai when he presses Approve.

It is stored as a sha256 digest for the same reason the API keys are — the
plaintext lives in a redirect URL and in the client's memory, and nowhere on
our disk. A stolen database yields no redeemable code.

Everything the token endpoint must re-check is FROZEN here at approval time:
which client, which callback, which PKCE challenge, which therapist. The token
request re-presents client_id and redirect_uri and they must equal these, so a
code intercepted in transit is useless to a different client or a different
callback, and the `code_verifier` proves the redeemer is the same party that
started the flow.

There is no team or caseload column, and that is deliberate: an SLP Pro key IS
its user, and what it may touch is recomputed from that user's current grants
on every MCP call (see app.mcp.auth). Freezing a scope here would be a
permission snapshot that outlives the permission.

`consumed_at` is what makes it single use. The row stays afterwards rather than
being deleted, because the OAuth 2.1 replay rule needs it: a SECOND redemption
does not merely fail, it revokes everything the first one produced — every
access key and every refresh token still pointing back at this code — since a
second redemption means somebody other than the legitimate client is holding it.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class OAuthCode(Base):
    __tablename__ = "oauth_codes"
    __table_args__ = (
        UniqueConstraint("code_hash", name="uq_oauth_codes_code_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # sha256 hex of the code the client will present — 64 characters, always.
    code_hash = Column(String(64), nullable=False, index=True)

    oauth_client_id = Column(
        Integer, ForeignKey("oauth_clients.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Compared string-for-string against the token request. 2048 is far past
    # any real callback and stays comparable on Azure SQL.
    redirect_uri = Column(String(2048), nullable=False)

    # RFC 7636: base64url of sha256(verifier), 43 characters for S256. The
    # method column exists so the stored value can never be read as anything
    # other than what it is — `plain` is rejected at the door, never stored.
    code_challenge = Column(String(128), nullable=False)
    code_challenge_method = Column(String(8), nullable=False)

    # RFC 8707 audience, when the client sent one. Always the canonical /mcp.
    resource = Column(String(512), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None
