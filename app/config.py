from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_provider: str = ""
    model_name: str = ""
    model_base_url: str = ""
    model_api_key_env: str = "OPENAI_API_KEY"
    model_fixed_name: str = ""
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_tokens: int = 300
    local_llm_base_url: str = "http://127.0.0.1:11434/v1"
    local_llm_api_key: str = ""
    local_llm_model: str = "qwen2.5:7b"
    database_url: str = "sqlite:///data/pet_agent.db"
    app_name: str = "宠物店 AI 复购提醒助手"
    shop_name: str = "示例宠物店"
    wecom_corp_id: str = ""
    wecom_agent_id: str = ""
    wecom_app_secret: str = ""
    wecom_token: str = ""
    wecom_encoding_aes_key: str = ""
    wecom_redirect_uri: str = ""
    wecom_oauth_enabled: bool = False
    wecom_callback_enabled: bool = False
    wecom_contact_sync_enabled: bool = False
    wecom_internal_notify_enabled: bool = False
    wecom_customer_send_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
