from __future__ import annotations

from agents import Agent, WebSearchTool

from app.ai.factory import create_agent


def create_web_research_agent() -> Agent:
    instructions = """
You are the web research specialist for an SLP workflow.
Use web search to find public, general, non-student-specific information.
Never include or request student names, aliases, IDs, birth dates, schools, or any personally identifying student details.
If a request appears student-specific, rewrite it into a general research query before searching.
All responses should be in clean markdown format.
Do not wrap your full answer in triple backticks (for example ```markdown ... ```).
If you include a table, output it as a normal markdown table, not inside a code fence.
""".strip()
    return create_agent(
        name="WebResearchSpecialist",
        instructions=instructions,
        tools=[WebSearchTool()],
    )

