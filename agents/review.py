from sqlalchemy.orm import Session

from agents.base import BaseAgent
from core.llm import LLMClient


class ReviewAgent(BaseAgent):
    """Generate manual-copy review replies for local-life pet store scenarios."""

    def __init__(self, db_session: Session, llm: LLMClient | None = None):
        super().__init__(db_session, llm)

    def execute(self, context: dict) -> dict:
        scenario = str(context.get("scenario") or "positive")
        review_text = str(context.get("review_text") or "").strip()
        store_name = str(context.get("store_name") or "本店").strip()

        if scenario == "negative":
            fallback = (
                f"您好，非常抱歉这次在{store_name}没有让您完全满意。"
                "我们会复盘等待时间和服务衔接，也欢迎您私信我们补充细节，"
                "下次到店前可以提前预约，我们会优先安排。"
            )
        elif scenario == "guide":
            fallback = (
                f"如果您觉得{store_name}这次服务还不错，方便的话可以帮我们写几句真实感受。"
                "比如宠物洗完后的状态、店员沟通、环境卫生，这些都会帮到其他家长。"
            )
        else:
            fallback = (
                f"感谢您认可{store_name}，看到毛孩子洗完更舒服、更放松，我们也特别开心。"
                "后续护理或预约有任何需要，随时联系我们。"
            )

        prompt = (
            "你是宠物店点评回复助手。请生成一段可复制的人工确认回复，"
            "不要承诺自动发送，不要做医疗诊断。"
            f"\n门店：{store_name}\n场景：{scenario}\n用户评价：{review_text}"
        )
        reply = self.render_or_fallback(prompt, fallback)
        return {"scenario": scenario, "reply": reply, "review_text": review_text}
