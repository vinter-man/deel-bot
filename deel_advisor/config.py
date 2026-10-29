"""Settings from the environment (and `.env` for local runs)."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # A local .env may hold other projects' variables: unknown ones are ignored, and an empty
    # `OWNER_ID=` (as .env.example ships it) means "not set" rather than a validation error.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    bot_token: SecretStr
    # Gets /stats and a message when the daily data check finds something. Optional.
    owner_id: int | None = None
    data_dir: Path = Path("data")
    log_level: str = "INFO"
    # Written by the heartbeat task, read by the Docker healthcheck.
    heartbeat_file: Path = Path("/tmp/deel-advisor.heartbeat")  # noqa: S108 - tmpfs in the container
    # Set by the image build, so the log says which commit is running.
    git_sha: str = "unknown"
