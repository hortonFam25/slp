"""
A client that registered itself through RFC 7591 Dynamic Client Registration
— in practice, claude.ai.

DCR exists because the MCP authorization spec assumes the client has never met
this server before: a therapist pastes the /mcp URL into claude.ai as a custom
connector, and claude.ai has to become a known client of THIS installation
before any human is ever asked to approve anything. Entra ID, where SLP Pro's
therapists actually sign in, does not implement DCR, which is the whole reason
this app runs its own authorization-server facade.

Every client here is PUBLIC (token_endpoint_auth_method = "none"): there is no
secret to keep, because a browser-side or SaaS client cannot keep one. What
stands in for the secret is PKCE plus an EXACT-match redirect list —
`redirect_uris` is JSON and is compared string-for-string, never by prefix,
because prefix matching is how authorization codes get delivered to an
attacker's path on somebody else's host.

`client_id` is opaque random rather than a guessable name, so registering does
not let anyone enumerate who else has registered.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from app.db.base import Base


class OAuthClient(Base):
    __tablename__ = "oauth_clients"
    __table_args__ = (
        UniqueConstraint("client_id", name="uq_oauth_clients_client_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # The public identifier the client sends on /oauth/authorize and
    # /oauth/token. 32 hex characters of `secrets` randomness.
    client_id = Column(String(64), nullable=False, index=True)

    # Whatever the client called itself at registration; shown to the therapist
    # on the consent screen and baked into the name of every key it is issued.
    client_name = Column(String(120), nullable=True)

    # JSON arrays exactly as registered. Text (VARCHAR(MAX) on SQL Server)
    # because a client may register several callbacks and RFC 7591 puts no
    # length cap on them.
    redirect_uris = Column(Text, nullable=False)
    grant_types = Column(Text, nullable=True)
    response_types = Column(Text, nullable=True)

    # "none" only — see the module docstring.
    token_endpoint_auth_method = Column(String(32), nullable=False, default="none")

    # Written by the application (datetime.utcnow) rather than by a server
    # default, exactly as api_tokens does: the rest of this schema uses
    # GETDATE(), which is SQL Server only, and these rows are also created
    # against SQLite in development.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
