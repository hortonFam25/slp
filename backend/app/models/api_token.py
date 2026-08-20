"""
Personal API keys — the credential a machine presents at /mcp.

The secret is `slp_` + 40 hex characters and is shown EXACTLY ONCE, at
creation. Only its sha256 hex digest is stored, so a stolen database gives an
attacker nothing to present at the door; `prefix` is the literal first 12
characters ("slp_a1b2c3d4") and exists purely so the therapist can tell his
keys apart in a list.

A key is "me" and nothing more: it carries a user_id, and every scope decision
made for it (which students, which access mode) is recomputed from that user's
CURRENT grants on every call. There is no snapshot of permissions in this row,
which is what lets a student being taken off somebody's caseload take effect on
the next MCP call rather than the next time somebody thinks to revoke a key.

State is derived from timestamps rather than a status column: a key is live
while revoked_at IS NULL and it has not passed expires_at. `last_used_at` is a
courtesy for the UI ("is this old Claude key still talking to us?") and is
written with a cheap UPDATE outside the request's transaction — losing one is
not a correctness problem.
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
from sqlalchemy.orm import relationship

from app.db.base import Base

# How a key came to exist. 'manual' is a therapist pressing "create connection
# key"; 'oauth' is a claude.ai connector that ran the consent flow.
KIND_MANUAL = "manual"
KIND_OAUTH = "oauth"


class ApiToken(Base):
    __tablename__ = "api_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_api_tokens_token_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # What the therapist called it ("Claude", "my laptop").
    name = Column(String(80), nullable=False)

    # sha256 hex of the full secret — 64 characters, always.
    token_hash = Column(String(64), nullable=False, index=True)

    # The literal first 12 characters of the secret, for display only.
    prefix = Column(String(12), nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    # ---- lifetime and provenance ------------------------------------------
    # 'manual' | 'oauth'. Defaulted in the DATABASE as well as in Python so a
    # row written by anything that predates this column still reads back as a
    # manual key rather than as NULL.
    kind = Column(String(16), nullable=False, default=KIND_MANUAL, server_default=KIND_MANUAL)

    # NULL = never expires. Manual keys carry NULL and keep working forever;
    # an OAuth access key gets a short TTL.
    expires_at = Column(DateTime, nullable=True)

    # OAuth hooks, deliberately PLAIN NULLABLE INTEGERS with NO ForeignKey for
    # now: the oauth_clients / oauth_codes tables do not exist yet (they arrive
    # with the OAuth facade). Declaring FKs against absent tables would make
    # this table's migration dangle and fail to create on SQL Server. When
    # those tables land, a follow-up migration can add the constraints; nothing
    # here has to change shape.
    oauth_client_id = Column(Integer, nullable=True, index=True)
    oauth_code_id = Column(Integer, nullable=True, index=True)

    user = relationship("User", lazy="selectin")

    def is_active(self, now: datetime | None = None) -> bool:
        """
        May this key still open a door?

        Revocation and expiry are one question with one answer, asked in one
        place: an expired key must fail EXACTLY like a revoked one, at /mcp and
        at REST alike, and a caller that only remembered to check revoked_at
        would be a silent hole. A NULL expires_at never expires.
        """
        if self.revoked_at is not None:
            return False
        if self.expires_at is None:
            return True
        return self.expires_at > (now or datetime.utcnow())
