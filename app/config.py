"""StorySpark Configuration & Environment Variable Handler."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if it exists
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class Settings:
    """Application settings loaded securely from environment variables."""

    PROJECT_NAME: str = "StorySpark"
    VERSION: str = "0.2.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Primary and fallback Gemini models
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")

    # Validation constants
    MIN_TOPIC_LENGTH: int = 2
    MAX_TOPIC_LENGTH: int = 100
    MIN_AGE: int = 4
    MAX_AGE: int = 14

    @property
    def gemini_api_key(self) -> str:
        """Dynamically fetch the Gemini API key from environment."""
        if "GEMINI_API_KEY" not in os.environ and ENV_PATH.exists():
            load_dotenv(dotenv_path=ENV_PATH)
        return os.getenv("GEMINI_API_KEY", "").strip()

    @property
    def is_gemini_configured(self) -> bool:
        """Returns True if a valid-looking Gemini API key is configured."""
        key = self.gemini_api_key
        return bool(key and key != "your_gemini_api_key_here")


settings = Settings()
