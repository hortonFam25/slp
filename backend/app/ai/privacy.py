from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StudentAliasContext:
    student_id: int
    alias: str
    first_name: str
    last_name: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


def build_student_alias(student_id: int) -> str:
    return f"student_{student_id}"


def build_alias_context(student_id: int, first_name: str, last_name: str) -> StudentAliasContext:
    return StudentAliasContext(
        student_id=student_id,
        alias=build_student_alias(student_id),
        first_name=first_name or "",
        last_name=last_name or "",
    )


def _replace_name_tokens(text: str, ctx: StudentAliasContext) -> str:
    redacted = text
    full_name = ctx.full_name.strip()
    if full_name:
        redacted = re.sub(re.escape(full_name), ctx.alias, redacted, flags=re.IGNORECASE)
    if ctx.first_name:
        redacted = re.sub(re.escape(ctx.first_name), ctx.alias, redacted, flags=re.IGNORECASE)
    if ctx.last_name:
        redacted = re.sub(re.escape(ctx.last_name), ctx.alias, redacted, flags=re.IGNORECASE)
    return redacted


def redact_student_name_from_value(value: Any, ctx: StudentAliasContext) -> Any:
    if isinstance(value, str):
        return _replace_name_tokens(value, ctx)
    if isinstance(value, list):
        return [redact_student_name_from_value(item, ctx) for item in value]
    if isinstance(value, dict):
        return {key: redact_student_name_from_value(val, ctx) for key, val in value.items()}
    return value


def hydrate_aliases_for_ui(text: str, ctx: StudentAliasContext) -> str:
    display_name = ctx.full_name.strip()
    if not display_name:
        return text
    return re.sub(re.escape(ctx.alias), display_name, text, flags=re.IGNORECASE)

