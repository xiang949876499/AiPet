def test_base_agent_falls_back_when_llm_unavailable(db_session):
    from agents.base import BaseAgent

    class DemoAgent(BaseAgent):
        name = "demo"

        def execute(self, context):
            return {"message": self.render_or_fallback("prompt", "fallback")}

    agent = DemoAgent(db_session=db_session, llm_client=None)

    assert agent.execute({}) == {"message": "fallback"}
