from sqlalchemy.orm import Session

from core.llm import LLMClient


class BaseAgent:
    name = "base"

    def __init__(self, db_session: Session, llm_client: LLMClient | None = None):
        self.db_session = db_session
        self.llm = llm_client or LLMClient()

    def render_or_fallback(self, prompt: str, fallback: str) -> str:
        message = self.llm.generate(prompt) if self.llm is not None else None
        return message or fallback

    def execute(self, context: dict) -> dict:
        raise NotImplementedError
