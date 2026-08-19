from collections.abc import Callable
import os

from app.config import settings


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        generator: Callable[[str], str] | None = None,
        provider: str | None = None,
        base_url: str | None = None,
    ):
        self.provider = (provider or settings.model_provider or settings.llm_provider or "openai").strip().lower()
        self.base_url = self._normalize_base_url(base_url if base_url is not None else self._default_base_url())
        self.api_key = self._resolve_api_key(api_key)
        self.model = model or self._default_model()
        self.generator = generator
        self.timeout_seconds = settings.llm_timeout_seconds
        self.max_tokens = settings.llm_max_tokens
        self.last_error = ""

    def generate(self, prompt: str) -> str | None:
        self.last_error = ""
        if self.generator is not None:
            return self.generator(prompt)
        if self.provider != "local" and not self.api_key:
            self.last_error = "missing_api_key"
            return None
        if self.provider == "local" and not self.base_url:
            self.last_error = "missing_local_base_url"
            return None
        try:
            from openai import OpenAI

            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            if self.timeout_seconds and self.timeout_seconds > 0:
                client_kwargs["timeout"] = float(self.timeout_seconds)
            client = OpenAI(**client_kwargs)
            request_kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            }
            if self.max_tokens and self.max_tokens > 0:
                request_kwargs["max_tokens"] = int(self.max_tokens)
            response = client.chat.completions.create(**request_kwargs)
            return response.choices[0].message.content
        except Exception as exc:
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            return None

    def _default_base_url(self) -> str:
        if settings.model_base_url.strip():
            return settings.model_base_url
        if self.provider == "local":
            return settings.local_llm_base_url
        return settings.openai_base_url

    def _default_model(self) -> str:
        if settings.model_fixed_name.strip():
            return settings.model_fixed_name.strip()
        if settings.model_name.strip():
            return settings.model_name.strip()
        if self.provider == "local":
            return settings.local_llm_model or settings.llm_model
        return settings.llm_model

    def _resolve_api_key(self, api_key: str | None) -> str:
        if api_key is not None:
            if self.provider == "local" and not api_key:
                return settings.local_llm_api_key or "local-model"
            return api_key.strip()
        model_api_key = self._model_api_key()
        if model_api_key:
            return model_api_key
        if self.provider == "local":
            return settings.local_llm_api_key.strip() or "local-model"
        return settings.openai_api_key.strip()

    def _normalize_base_url(self, base_url: str | None) -> str:
        return (base_url or "").strip().rstrip("/")

    def _model_api_key(self) -> str:
        env_name = settings.model_api_key_env.strip()
        if not env_name:
            return ""
        value = os.getenv(env_name, "").strip()
        if value:
            return value
        if env_name == "OPENAI_API_KEY":
            return settings.openai_api_key.strip()
        if env_name == "LOCAL_LLM_API_KEY":
            return settings.local_llm_api_key.strip()
        return ""
