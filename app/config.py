"""Configuration management for Personal Manager."""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class Settings(BaseSettings):
    """Application settings loaded from config.yaml and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )

    # Application
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")

    # Database
    database_url: str = Field(
        default="sqlite:///data/agent.db",
        alias="DATABASE_URL"
    )
    activity_tracker_db: str = Field(
        default="/media/shared/personalProjects/ActivityTracker/activity.db",
        alias="ACTIVITY_TRACKER_DB"
    )

    # LLM API Keys
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    default_llm_provider: str = Field(default="anthropic", alias="DEFAULT_LLM_PROVIDER")

    # Google Calendar
    google_credentials_path: str = Field(
        default="~/.personal-manager/credentials/google_credentials.json",
        alias="GOOGLE_CREDENTIALS_PATH"
    )
    google_token_path: str = Field(
        default="~/.personal-manager/tokens/google_token.json",
        alias="GOOGLE_TOKEN_PATH"
    )

    # CalDAV
    caldav_url: Optional[str] = Field(default=None, alias="CALDAV_URL")
    caldav_username: Optional[str] = Field(default=None, alias="CALDAV_USERNAME")
    caldav_password: Optional[str] = Field(default=None, alias="CALDAV_PASSWORD")

    @property
    def base_dir(self) -> Path:
        """Get base directory of the project."""
        return Path(__file__).parent.parent

    @property
    def data_dir(self) -> Path:
        """Get data directory."""
        return self.base_dir / "data"

    def load_config_yaml(self, config_path: Optional[Path] = None) -> dict:
        """Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml file. Defaults to config.yaml in base dir.

        Returns:
            Dictionary of configuration values
        """
        if config_path is None:
            config_path = self.base_dir / "config.yaml"

        if not config_path.exists():
            return {}

        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}


# Global settings instance
settings = Settings()
