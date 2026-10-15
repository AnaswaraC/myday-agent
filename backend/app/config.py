from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    llm_api_key: str = ""
    default_city: str = "Coimbatore"
    timezone: str = "Asia/Kolkata"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
settings = Settings()
