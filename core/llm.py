from collections.abc import Callable

from app.config import settings


class LLMClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, generator: Callable[[str], str] | None = None):
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.model = model or settings.llm_model
        self.generator = generator

    def generate(self, prompt: str) -> str | None:
        if self.generator is not None:
            return self.generator(prompt)
        if not self.api_key:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception:
            return None
