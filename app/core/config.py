"""Configuration management module for MyResumo.

This module defines the Settings class using Pydantic Settings, providing
a centralized and validated way to manage environment variables and
application-wide configurations.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment variables.

    Attributes:
        PROJECT_NAME (str): Name of the project.
        VERSION (str): Application version.
        SUPABASE_URL (str): URL for the Supabase project.
        SUPABASE_ANON_KEY (str): Anonymous key for Supabase.
        SUPABASE_SERVICE_ROLE_KEY (Optional[str]): Service role key for Supabase (admin access).
        MODEL_NAME (str): Default AI model name.
        API_KEY (str): API key for the AI service.
        API_BASE (Optional[str]): Base URL for the AI API.
    """

    PROJECT_NAME: str = "DailSmart AI"
    VERSION: str = "2.0.0"

    # Supabase Configuration
    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_ANON_KEY: str = "placeholder-key"
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # AI Service Configuration (OpenRouter + DeepSeek)
    MODEL_NAME: str = "deepseek/deepseek-chat"
    API_KEY: str = "placeholder-api-key"
    API_BASE: str = "https://openrouter.ai/api/v1"
    
    # Scaling & Performance
    MAX_CONCURRENT_REQUESTS: int = 50
    REQUEST_TIMEOUT: int = 120
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
