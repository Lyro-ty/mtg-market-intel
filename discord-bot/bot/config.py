"""Bot configuration loaded from environment variables."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BotConfig:
    """Configuration for the Discord bot."""

    # Discord
    discord_token: str
    discord_guild_id: int | None  # Optional: restrict to specific guild

    # Backend API
    api_base_url: str
    api_token: str  # X-Bot-Token for backend auth

    # Feature flags
    enable_alerts: bool = True
    alert_poll_interval: int = 30  # seconds

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables."""
        discord_token = os.getenv("DISCORD_BOT_TOKEN", "")
        if not discord_token:
            raise ValueError("DISCORD_BOT_TOKEN is required")

        api_token = os.getenv("DISCORD_BOT_API_KEY", "")
        if not api_token:
            raise ValueError("DISCORD_BOT_API_KEY is required")

        guild_id_str = os.getenv("DISCORD_GUILD_ID")
        guild_id = int(guild_id_str) if guild_id_str else None

        return cls(
            discord_token=discord_token,
            discord_guild_id=guild_id,
            api_base_url=os.getenv("API_BASE_URL", "http://backend:8000"),
            api_token=api_token,
            enable_alerts=os.getenv("ENABLE_ALERTS", "true").lower() == "true",
            alert_poll_interval=int(os.getenv("ALERT_POLL_INTERVAL", "30")),
        )


# Global config instance
config = BotConfig.from_env() if os.getenv("DISCORD_BOT_TOKEN") else None
