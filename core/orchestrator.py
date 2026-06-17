class AgentOrchestrator:
    def __init__(self) -> None:
        self._agents = {}

    def register(self, name: str, agent) -> None:
        self._agents[name] = agent

    def execute(self, agent_name: str, context: dict) -> dict:
        agent = self._agents.get(agent_name)
        if agent is None:
            return {"error": "unknown_agent", "agent": agent_name}
        return agent.execute(context)
