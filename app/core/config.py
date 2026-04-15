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

    PROJECT_NAME: str = "AuraRise"
    VERSION: str = "2.0.0"

    # Supabase Configuration
    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_ANON_KEY: str = "sb_publishable_2MMUfh6MHkHhsITxqe3Q_w_t2zPFlCD"
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # AI Service Configuration (OpenRouter + DeepSeek)
    MODEL_NAME: str = "deepseek/deepseek-v3.2"
    API_KEY: str = "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"
    API_BASE: str = "https://openrouter.ai/api/v1"
    
    # Scaling & Performance
    MAX_CONCURRENT_REQUESTS: int = 100
    REQUEST_TIMEOUT: int = 150
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
