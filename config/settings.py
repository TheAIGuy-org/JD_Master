# config/settings.py
"""
Global configuration settings loaded from environment variables.
Centralized configuration prevents scattered hardcoded values.
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application-wide configuration"""
    
    # Groq API Configuration
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_REASONING_MODEL: str = os.getenv("GROQ_REASONING_MODEL", "llama-3.1-70b-versatile")
    GROQ_SPEED_MODEL: str = os.getenv("GROQ_SPEED_MODEL", "llama-3.1-8b-instant")
    
    # Rate Limiting
    GROQ_CALL_DELAY: float = float(os.getenv("GROQ_CALL_DELAY", "2.0"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Paths
    CONFIG_DIR: str = os.path.join(os.path.dirname(__file__))
    SENIORITY_PROFILES_PATH: str = os.path.join(CONFIG_DIR, "seniority_profiles.json")
    
    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration values"""
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY environment variable is required")
    
    @classmethod
    def get_profile_path(cls) -> str:
        """Get absolute path to seniority profiles"""
        return cls.SENIORITY_PROFILES_PATH


settings = Settings()