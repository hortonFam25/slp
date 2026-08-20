from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import os
from typing import Any
from zoneinfo import ZoneInfo

from agents import Agent, set_default_openai_key
from agents.model_settings import ModelSettings
from openai.types.shared.reasoning import Reasoning

from app.settings import settings


@dataclass(frozen=True)
class AgentDefaults:
    model: str
    reasoning_effort: str
    verbosity: str
    max_output_tokens: int


def get_agent_defaults() -> AgentDefaults:
    return AgentDefaults(
        model=settings.ai_model,
        reasoning_effort=settings.ai_reasoning_effort,
        verbosity=settings.ai_verbosity,
        max_output_tokens=settings.ai_max_output_tokens,
    )


@lru_cache(maxsize=1)
def configure_agents_openai() -> None:
    """
    Ensure Agents SDK has an explicit OpenAI API key.

    Pydantic settings can read `.env` values without exporting them to process
    environment variables, while the Agents SDK expects an API key configured
    for its own OpenAI client.
    """
    key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
    if key:
        set_default_openai_key(key)


def create_agent(
    *,
    name: str,
    instructions: str,
    tools: list[Any] | None = None,
) -> Agent:
    """
    Shared factory for all agents so model/runtime defaults stay consistent.
    """
    configure_agents_openai()
    defaults = get_agent_defaults()
    try:
        eastern_now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p %Z")
        time_context_line = f"- Treat the current date/time as {eastern_now} (Eastern Time)."
    except Exception:
        utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %I:%M %p %Z")
        time_context_line = (
            f"- Treat the current date/time as {utc_now} (UTC). "
            "Eastern time zone data was unavailable on this host."
        )
    instructions_with_datetime = (
        f"{instructions.strip()}\n\n"
        "Current date/time context:\n"
        f"{time_context_line}\n"
    )
    return Agent(
        name=name,
        model=defaults.model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=defaults.reasoning_effort),
            verbosity=defaults.verbosity,
            max_tokens=defaults.max_output_tokens,
        ),
        instructions=instructions_with_datetime,
        tools=tools or [],
    )

