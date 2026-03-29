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
    
    # Google Ads API
    GOOGLE_ADS_DEVELOPER_TOKEN: str = Field(..., description="Google Ads developer token")
    GOOGLE_ADS_CLIENT_ID: str = Field(..., description="Google OAuth client ID")
    GOOGLE_ADS_CLIENT_SECRET: str = Field(..., description="Google OAuth client secret")
    GOOGLE_ADS_REDIRECT_URI: str = Field(..., description="Google OAuth redirect URI")
    
    # Meta Ads API
    META_APP_ID: str = Field(..., description="Meta (Facebook) app ID")
    META_APP_SECRET: str = Field(..., description="Meta app secret")
    META_REDIRECT_URI: str = Field(..., description="Meta OAuth redirect URI")
    
    # CORS
    CORS_ORIGINS: str = Field(default="http://localhost:3000", description="Allowed CORS origins (comma-separated)")
    
    # Server
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    
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