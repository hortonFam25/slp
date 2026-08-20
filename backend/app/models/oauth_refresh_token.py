"""
A refresh token — the long-lived half of an OAuth grant, so the access half can
be short-lived.

Its own table rather than another flavour of `api_tokens`, because it is not a
credential for the API at all: it opens exactly one endpoint (/oauth/token) and
can never be presented to /mcp or to REST. Keeping the two apart means the door
code has nothing extra to check — anything that reaches a door is an `slp_` key
or it is nothing.

Rotation is single use, enforced by `used_at`: every refresh burns the row it
was presented on and issues a new one. That is what turns a stolen refresh
token into a detectable event instead of a permanent one — the thief and the
real client cannot both keep using the chain.

`oauth_code_id` is the GRANT FAMILY: every access key and every refresh token
descended from one approval carries it, so "revoke everything that came out of
that consent" is one UPDATE per table and cannot miss a descendant that was
minted three rotations later.
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


class OAuthRefreshToken(Base):
    __tablename__ = "oauth_refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_oauth_refresh_tokens_token_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # sha256 hex of the presented secret — the plaintext is never stored.
    token_hash = Column(String(64), nullable=False, index=True)

    oauth_client_id = Column(
        Integer, ForeignKey("oauth_clients.id"), nullable=False, index=True
    )
    oauth_code_id = Column(
        Integer, ForeignKey("oauth_codes.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    # Free-text note for the operator reading the table by hand ("rotated",
    # "code replay", "revoked by therapist"). Never shown to a client.
    revoked_reason = Column(String(40), nullable=True)

    @property
    def is_live(self) -> bool:
        return self.used_at is None and self.revoked_at is None
