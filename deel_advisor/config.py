"""Settings from the environment (and `.env` for local runs)."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The server's .env carries deploy credentials too; they are none of the bot's business.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: SecretStr
    # Gets /stats and a message when the daily data check finds something. Optional.
    owner_id: int | None = None
    data_dir: Path = Path("data")
    log_level: str = "INFO"
    # Written by the heartbeat task, read by the Docker healthcheck.
    heartbeat_file: Path = Path("/tmp/deel-advisor.heartbeat")  # noqa: S108 - tmpfs in the container
