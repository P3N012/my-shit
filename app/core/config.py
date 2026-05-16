"""
Application configuration using Pydantic Settings

This module handles all environment variables and configuration.
Settings are loaded from .env file and environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL database URL")
    
    # JWT
    ACCESS_TOKEN_SECRET: str = Field(..., description="Secret key for access tokens")
    REFRESH_TOKEN_SECRET: str = Field(..., description="Secret key for refresh tokens")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="Access token expiry in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, description="Refresh token expiry in days")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    
    # Application
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")
    API_V1_PREFIX: str = Field(default="/api/v1", description="API version 1 prefix")
    PROJECT_NAME: str = Field(default="InsightPlus", description="Project name")
    
    # CORS
    CORS_ORIGINS: str = Field(default="http://localhost:3000", description="Allowed CORS origins (comma-separated)")

    # Server
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")

    # Observability + rate limiting
    LOG_LEVEL: str = Field(default="INFO", description="Root log level")
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Toggle slowapi rate limits globally")
    RATE_LIMIT_LOGIN: str = Field(default="5/minute", description="Per-IP login rate limit")
    RATE_LIMIT_REGISTER: str = Field(default="5/minute", description="Per-IP register rate limit")
    RATE_LIMIT_REFRESH: str = Field(default="20/minute", description="Per-IP refresh rate limit")
    RATE_LIMIT_AI: str = Field(default="30/minute", description="Per-IP rate limit on AI endpoints")

    # AI
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key. Required for AI features.")
    ANTHROPIC_MODEL: str = Field(default="claude-opus-4-7", description="Default Claude model")
    ANTHROPIC_MAX_TOKENS: int = Field(default=4096, description="Default max output tokens")
    AI_ENABLED: bool = Field(default=True, description="Toggle AI endpoints globally")

    # Background jobs
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis URL for arq job queue")

    # Stripe Connect
    STRIPE_SECRET_KEY: str = Field(default="", description="Your platform's Stripe secret key (sk_test_... or sk_live_...). Used to exchange OAuth codes for connected-account tokens.")
    STRIPE_CONNECT_CLIENT_ID: str = Field(default="", description="Your Stripe Connect client ID (ca_...) from Stripe Dashboard → Settings → Connect.")
    STRIPE_OAUTH_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/v1/connections/stripe/callback",
        description="Where Stripe redirects after the user authorizes. Must match a Redirect URI configured in your Stripe Connect settings.",
    )
    STRIPE_OAUTH_SUCCESS_URL: str = Field(
        default="http://localhost:3000/oauth/stripe?stripe=ok",
        description="Frontend URL the callback redirects to after a successful connect.",
    )
    STRIPE_OAUTH_FAILURE_URL: str = Field(
        default="http://localhost:3000/oauth/stripe?stripe=error",
        description="Frontend URL the callback redirects to on failure.",
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.ENVIRONMENT == "production"


# Global settings instance
settings = Settings()