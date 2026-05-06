"""Config for auth engine."""
import os
from pathlib import Path

STORE_PATH = os.getenv(
    "AIPROXY_STORE_PATH",
    str(Path(__file__).parent.parent.parent / "proxy" / "data" / "proxy.db.json"),
)
CODEBUDDY_BASE_URL = "https://www.codebuddy.ai"
