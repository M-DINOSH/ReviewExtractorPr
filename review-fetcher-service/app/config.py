import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        # Don't use env_file since we're using Docker environment variables
        pass


settings = Settings()