"""
Configuration settings for the application.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """Application settings loaded from environment variables."""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    
    # JWT
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    
    # API Keys (FAKE - for testing only)
    api_key: str = os.getenv("API_KEY", "fake-api-key-for-testing")
    stripe_key: str = os.getenv("STRIPE_KEY", "sk_test_fake_key")
    
    # External Services
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    sentry_dsn: Optional[str] = os.getenv("SENTRY_DSN")
    
    # Feature Flags
    enable_metrics: bool = True
    debug_mode: bool = os.getenv("DEBUG", "false").lower() == "true"


# Global settings instance
settings = Settings()