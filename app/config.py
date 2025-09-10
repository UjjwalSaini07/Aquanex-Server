from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")

    API_AUTH_TOKEN: str | None = None

    REDIS_URL: str | None = None
    CORS_ORIGINS: str = Field(default="*")

    APP_NAME: str = Field(default="Aquanex FastAPI")
    APP_ENV: str = Field(default="dev")

settings = Settings()
