"""Configuration management for the AI automation agent."""

from typing import Optional
from pydantic import BaseSettings, validator
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings using Pydantic BaseSettings for validation."""
    
    # LLM Configuration (supports multiple providers)
    llm_provider: str = "openai"  # openai, anthropic, deepseek, qwen, ollama, groq, etc.
    llm_api_key: str
    llm_base_url: Optional[str] = None  # For custom endpoints like Ollama, vLLM, etc.
    llm_model: str = "gpt-3.5-turbo"
    llm_max_tokens: int = 2000
    llm_temperature: float = 0.1
    
    # Legacy OpenAI support (backwards compatibility)
    openai_api_key: Optional[str] = None
    
    # Database Configuration
    database_url: str
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "automation_agent"
    database_user: str
    database_password: str
    
    # Application Configuration
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Slack OAuth2 Configuration
    slack_client_id: str
    slack_client_secret: str
    slack_redirect_uri: str = "http://localhost:8000/auth/slack/callback"
    
    # Jira OAuth2 Configuration
    jira_client_id: str
    jira_client_secret: str
    jira_redirect_uri: str = "http://localhost:8000/auth/jira/callback"
    jira_base_url: str
    
    # AWS Configuration
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    aws_s3_bucket: str
    
    # GitHub OAuth2 Configuration
    github_client_id: str
    github_client_secret: str
    github_redirect_uri: str = "http://localhost:8000/auth/github/callback"
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"
    
    @validator("secret_key")
    def validate_secret_key(cls, v):
        """Ensure secret key is at least 32 characters long."""
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v
    
    @validator("llm_api_key")
    def validate_llm_api_key(cls, v):
        """Ensure LLM API key is provided."""
        if not v or v in ["your_api_key_here", "your_openai_api_key_here"]:
            raise ValueError("LLM API key must be provided")
        return v
    
    @validator("llm_provider")
    def validate_llm_provider(cls, v):
        """Validate LLM provider is supported."""
        supported_providers = [
            "openai", "anthropic", "deepseek", "qwen", "ollama", 
            "groq", "together", "perplexity", "openrouter", "local"
        ]
        if v.lower() not in supported_providers:
            raise ValueError(f"LLM provider must be one of: {', '.join(supported_providers)}")
        return v.lower()
    
    def __init__(self, **kwargs):
        """Initialize settings with backwards compatibility for OpenAI."""
        super().__init__(**kwargs)
        
        # Backwards compatibility: if openai_api_key is set but llm_api_key is not, use it
        if self.openai_api_key and not self.llm_api_key:
            self.llm_api_key = self.openai_api_key
            self.llm_provider = "openai"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


# Global settings instance
settings = get_settings() 