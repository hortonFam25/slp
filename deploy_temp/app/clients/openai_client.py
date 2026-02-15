from typing import List
from openai import OpenAI


class OpenAIClient:
    def __init__(self, api_key: str | None = None):
        self.client = OpenAI(api_key=api_key)

    def summarize_text(self, text: str) -> str:
        prompt = f"Summarize the following text for an SLP progress note:\n\n{text}"
        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return completion.choices[0].message.content or ""


