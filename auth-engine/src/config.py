"""Config for auth engine."""
import os
from pathlib import Path

# Store
STORE_PATH = os.getenv(
    "AIPROXY_STORE_PATH",
    str(Path(__file__).parent.parent.parent / "proxy" / "data" / "proxy.db.json"),
)
CODEBUDDY_BASE_URL = "https://www.codebuddy.ai"
CODEBUDDY_AUTH_URL = "https://www.codebuddy.ai/auth/realms/copilot/protocol/openid-connect/auth?client_id=console&redirect_uri=https://www.codebuddy.ai/&response_type=code&scope=openid+profile+email+offline_access"

# Camoufox
CAMOUFOX_HEADLESS = os.getenv("CAMOUFOX_HEADLESS", "true").lower() == "true"
CAMOUFOX_BLOCK_WEBRTC = True
CAMOUFOX_MAX_WIDTH = 1920
CAMOUFOX_MAX_HEIGHT = 1080

# Proxy (residential proxy for anti-detection)
PROXY_URL = os.getenv("PROXY_URL", "")  # e.g., socks5://user:pass@host:port

# Batch settings
BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "3"))
BATCH_DELAY_BETWEEN = float(os.getenv("BATCH_DELAY", "10.0"))
TYPING_DELAY_MS = int(os.getenv("TYPING_DELAY_MS", "50"))

# Accounts file
ACCOUNTS_FILE = os.getenv("ACCOUNTS_FILE", str(Path(__file__).parent.parent / "accounts.txt"))
