from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "openai"
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
