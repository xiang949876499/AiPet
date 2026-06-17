def test_orchestrator_routes_registered_agent():
    from core.orchestrator import AgentOrchestrator

    class FakeAgent:
        def execute(self, context):
            return {"ok": context["value"]}

    orchestrator = AgentOrchestrator()
    orchestrator.register("fake", FakeAgent())

    assert orchestrator.execute("fake", {"value": 3}) == {"ok": 3}


def test_orchestrator_rejects_unknown_agent():
    from core.orchestrator import AgentOrchestrator

    orchestrator = AgentOrchestrator()

    result = orchestrator.execute("missing", {})

    assert result["error"] == "unknown_agent"
