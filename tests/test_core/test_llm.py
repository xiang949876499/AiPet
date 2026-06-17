def test_llm_client_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from core.llm import LLMClient

    client = LLMClient(api_key="")

    assert client.generate("hello") is None


def test_llm_client_uses_injected_generator():
    from core.llm import LLMClient

    client = LLMClient(generator=lambda prompt: f"ok:{prompt}")

    assert client.generate("prompt") == "ok:prompt"
