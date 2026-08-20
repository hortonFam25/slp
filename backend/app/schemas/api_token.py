"""Wire shapes for the personal API keys ("connection keys")."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(word.capitalize() for word in rest)


class _CamelModel(BaseModel):
    """
    camelCase on the wire, snake_case in Python.

    The rest of this API is snake_case, but these three routes are consumed by
    a single React card and nothing else, so the JS-native spelling costs
    nothing and reads better there. `populate_by_name` keeps the Python names
    accepted on input.
    """

    model_config = ConfigDict(
        alias_generator=_camel, populate_by_name=True, from_attributes=True
    )


class ApiTokenCreate(_CamelModel):
    """POST /api/tokens — the user names the key so a list of them means something."""

    name: str = Field(max_length=80)

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        # A key called "   " is indistinguishable from an unnamed one in the
        # list, which is the only place the name is ever read.
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("name must not be blank")
        return cleaned


class ApiTokenOut(_CamelModel):
    """List shape. The secret is NOT here and cannot be recovered."""

    id: int
    name: str
    prefix: str
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    kind: str = "manual"
    expires_at: Optional[datetime] = None


class ApiTokenCreatedOut(ApiTokenOut):
    """
    The 201 body, and the ONLY time the plaintext secret exists outside the
    client that will use it — the server keeps a sha256 digest and nothing else.
    """

    token: str
