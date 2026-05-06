"""Auth engine configuration."""
import os
from pathlib import Path


class Settings:
    # Database (shared with Go proxy)
    DB_PATH: str = os.getenv("AIPROXY_DB_PATH", str(Path(__file__).parent.parent.parent.parent / "proxy" / "data" / "proxy.db"))

    # CodeBuddy
    CODEBUDDY_BASE_URL: str = "https://www.codebuddy.ai"
    CODEBUDDY_USER_AGENT: str = "CLI/2.54.0 CodeBuddy/2.54.0"
    CODEBUDDY_REGION_CODE: str = "65"
    CODEBUDDY_REGION_NAME: str = "SG"
    CODEBUDDY_REGION_FULL: str = "Singapore"

    # Camoufox
    CAMOUFOX_HEADLESS: bool = os.getenv("AIPROXY_HEADLESS", "true").lower() == "true"
    CAMOUFOX_BLOCK_WEBRTC: bool = True
    CAMOUFOX_MAX_WIDTH: int = 1920
    CAMOUFOX_MAX_HEIGHT: int = 1080

    # Proxy (optional)
    PROXY_URL: str = os.getenv("AIPROXY_PROXY_URL", "")

    # Timing
    LOGIN_TIMEOUT: int = 180  # seconds
    TYPING_DELAY_MS: int = 65  # human-like typing
    KEY_EXPIRE_DAYS: int = -1  # never expire

    # Accounts file
    ACCOUNTS_FILE: str = os.getenv("AIPROXY_ACCOUNTS_FILE", str(Path(__file__).parent.parent / "accounts.txt"))


settings = Settings()
