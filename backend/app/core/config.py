from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "DealFlow360 API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"

    # Database Configuration
    # Defaults to local SQLite if DATABASE_URL is not set in environment or .env
    DATABASE_URL: str = "sqlite:///./dealflow360.db"

    # Security & Authentication
    JWT_SECRET: str = "dealflow360-hackathon-secret-key-super-secure-32char"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
