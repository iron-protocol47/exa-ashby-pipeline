from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Exa
    exa_api_key: str = Field(default="", validation_alias="EXA_API_KEY")
    exa_webhook_secret: str = Field(default="", validation_alias="EXA_WEBHOOK_SECRET")
    exa_base_url: str = Field(
        default="https://api.exa.ai/websets",
        validation_alias="EXA_BASE_URL",
    )
    exa_skip_webhook_signature_verify: bool = Field(
        default=False,
        validation_alias="EXA_SKIP_WEBHOOK_SIGNATURE_VERIFY",
    )

    # Ashby (Basic auth: API key as username)
    ashby_api_key: str = Field(default="", validation_alias="ASHBY_API_KEY")
    brandon_ashby_user_id: str = Field(default="", validation_alias="BRANDON_ASHBY_USER_ID")

    # Slack
    slack_incoming_webhook_url: str = Field(
        default="", validation_alias="SLACK_INCOMING_WEBHOOK_URL"
    )
    slack_bot_token: str = Field(default="", validation_alias="SLACK_BOT_TOKEN")
    brandon_slack_user_id: str = Field(
        default="", validation_alias="BRANDON_SLACK_USER_ID"
    )

    # Admin HTTP Basic
    admin_basic_user: str = Field(default="", validation_alias="ADMIN_BASIC_USER")
    admin_basic_password: str = Field(default="", validation_alias="ADMIN_BASIC_PASSWORD")

    # Cron / catch-up
    catch_up_secret: str = Field(default="", validation_alias="CATCH_UP_SECRET")

    # SQLite — Railway: mount volume at /data and set DATABASE_PATH=/data/app.db
    database_path: Path = Field(
        default=Path("data/app.db"),
        validation_alias="DATABASE_PATH",
    )

    dry_run: bool = Field(default=False, validation_alias="DRY_RUN")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def ensure_database_parent_dir(path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
