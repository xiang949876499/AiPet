def test_llm_client_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from core.llm import LLMClient

    client = LLMClient(api_key="")

    assert client.generate("hello") is None


def test_llm_client_uses_injected_generator():
    from core.llm import LLMClient

    client = LLMClient(generator=lambda prompt: f"ok:{prompt}")

    assert client.generate("prompt") == "ok:prompt"


def test_llm_client_uses_local_openai_compatible_endpoint(monkeypatch):
    import sys
    import types

    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls["create"] = kwargs
            message = types.SimpleNamespace(content="本地模型润色结果")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = FakeChat()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    from core.llm import LLMClient

    client = LLMClient(
        provider="local",
        api_key="",
        model="qwen2.5:7b",
        base_url="http://127.0.0.1:11434/v1",
    )

    assert client.generate("把这句话说得更自然") == "本地模型润色结果"
    assert calls["client"] == {"api_key": "local-model", "base_url": "http://127.0.0.1:11434/v1", "timeout": 30.0}
    assert calls["create"]["model"] == "qwen2.5:7b"
    assert calls["create"]["max_tokens"] == 300
    assert calls["create"]["messages"][-1] == {"role": "user", "content": "把这句话说得更自然"}


def test_llm_client_uses_openai_env_external_endpoint(monkeypatch):
    import importlib
    import sys
    import types

    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls["create"] = kwargs
            message = types.SimpleNamespace(content="外部接口生成的话术")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = FakeChat()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.example/v1/")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("LLM_MAX_TOKENS", "256")
    monkeypatch.setenv("MODEL_PROVIDER", "")
    monkeypatch.setenv("MODEL_NAME", "")
    monkeypatch.setenv("MODEL_BASE_URL", "")
    monkeypatch.setenv("MODEL_API_KEY_ENV", "")
    monkeypatch.setenv("MODEL_FIXED_NAME", "")
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    import app.config
    import core.llm

    importlib.reload(app.config)
    llm_module = importlib.reload(core.llm)

    client = llm_module.LLMClient()

    assert client.generate("给客户写一句提醒") == "外部接口生成的话术"
    assert calls["client"] == {
        "api_key": "sk-test",
        "base_url": "https://api.openai.example/v1",
        "timeout": 12.0,
    }
    assert calls["create"]["model"] == "gpt-4.1-mini"
    assert calls["create"]["max_tokens"] == 256
    assert calls["create"]["messages"][-1] == {"role": "user", "content": "给客户写一句提醒"}


def test_llm_client_prefers_model_env_openai_compatible_config(monkeypatch):
    import importlib
    import sys
    import types

    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls["create"] = kwargs
            message = types.SimpleNamespace(content="局域网模型生成的话术")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = FakeChat()

    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("MODEL_NAME", "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf")
    monkeypatch.setenv("MODEL_BASE_URL", "http://192.168.0.131:9901/v1")
    monkeypatch.setenv("MODEL_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "local-llm")
    monkeypatch.setenv("MODEL_FIXED_NAME", "")
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    import app.config
    import core.llm

    importlib.reload(app.config)
    llm_module = importlib.reload(core.llm)

    client = llm_module.LLMClient()

    assert client.generate("给小七写一句洗护提醒") == "局域网模型生成的话术"
    assert calls["client"]["api_key"] == "local-llm"
    assert calls["client"]["base_url"] == "http://192.168.0.131:9901/v1"
    assert calls["create"]["model"] == "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
    assert calls["create"]["messages"][-1] == {"role": "user", "content": "给小七写一句洗护提醒"}


def test_llm_client_records_last_error_on_openai_failure(monkeypatch):
    import sys
    import types

    class FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError("network unavailable")

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    from core.llm import LLMClient

    client = LLMClient(api_key="sk-test")

    assert client.generate("hello") is None
    assert "network unavailable" in client.last_error
