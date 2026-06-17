from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "openai"
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    database_url: str = "sqlite:///data/pet_agent.db"
    app_name: str = "宠物店 AI 复购提醒助手"
    shop_name: str = "示例宠物店"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
