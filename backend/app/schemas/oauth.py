"""
Wire shapes for the ONE authenticated half of the OAuth facade: the consent
screen's Approve and Cancel.

camelCase on the wire, matching app/schemas/api_token.py and for the same
reason — these routes are consumed by a single React page and nothing else.
Everything else in the facade (register, authorize, token) is spoken in OAuth's
own snake_case because an RFC fixes it, and none of it comes through here.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(word.capitalize() for word in rest)


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel, populate_by_name=True, from_attributes=True
    )


class OAuthConsentIn(_CamelModel):
    """
    What the consent page echoes back from the query string it was handed.

    Nothing here is trusted: the client and its callback are looked up and
    matched again server-side, because a therapist could have been sent
    straight to /connect/authorize with hand-written parameters.
    """

    client_id: str = Field(max_length=64)
    redirect_uri: str = Field(max_length=2048)
    state: Optional[str] = None
    code_challenge: str = Field(max_length=128)
    code_challenge_method: str = Field(default="S256", max_length=8)
    resource: Optional[str] = Field(default=None, max_length=512)


class OAuthRedirectOut(_CamelModel):
    """Where the browser should go next — the client's own callback, always."""

    redirect_url: str
